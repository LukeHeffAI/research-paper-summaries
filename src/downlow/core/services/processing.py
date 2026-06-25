"""Processing orchestrator: run the persisted INGEST->...->STORE pipeline.

PURE orchestration: stdlib + ``domain`` (the entities + ports) + the pure stage
objects + the typed config only. No ``sqlmodel`` / SDK here -- the service drives
the injected stage objects (each pure, each owning its content-hash file cache) and
persists the run/stage provenance + the artifacts through the
:class:`~downlow.domain.ports.Repository` port and the
:class:`~downlow.core.stages.store.StoreStage`. This is the application seam the
CLI calls now and a FastAPI route will call unchanged.

``process_paper`` produces a :class:`~downlow.domain.entities.PipelineRun` with a
:class:`~downlow.domain.entities.StageRun` per stage, and is:

* **status-tracked** -- the run goes PENDING -> RUNNING -> SUCCEEDED/FAILED; each
  stage PENDING -> RUNNING -> SUCCEEDED/FAILED/SKIPPED, persisted as it transitions
  (so a crash mid-pipeline leaves a faithful, resumable record);
* **cache-aware** -- a stage whose durable DB output already exists for its input
  hash is SKIPPED (no recompute, no API call) and its existing row reused;
* **retryable-from-failure** -- a re-run resumes at the first stage the latest prior
  run did not SUCCEED, replaying succeeded stages from their DB output rather than
  redoing them (their underlying file caches make even a forced replay cheap).

RENDER and NARRATE both consume the summary and are independent; they are ordered
(RENDER then NARRATE) but a NARRATE failure does not undo a succeeded RENDER, and a
RENDER failure still lets the run record it and stop cleanly (graceful degradation).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from downlow.config.profiles import DownLowConfig
from downlow.core.stages.ingest import IngestStage
from downlow.core.stages.narrate import NarrateStage
from downlow.core.stages.render import RenderStage
from downlow.core.stages.store import StoreStage
from downlow.core.stages.summarise import SummariseStage
from downlow.domain.entities import Paper, PipelineRun, StageRun, Summary
from downlow.domain.enums import RunStatus, StageStatus
from downlow.domain.errors import DownLowError
from downlow.domain.ports import Clock, Repository
from downlow.domain.schemas import ExtractedText, KeyFinding, NarrationScript, PaperSummary

# The pipeline stage names, in execution order. RENDER + NARRATE both consume the
# summary and are independent; they are ordered but neither depends on the other's
# success (a NARRATE failure does not undo a succeeded RENDER).
INGEST = IngestStage.name
SUMMARISE = SummariseStage.name
RENDER = RenderStage.name
NARRATE = NarrateStage.name
STORE = StoreStage.name

DEFAULT_STAGES: tuple[str, ...] = (INGEST, SUMMARISE, RENDER, NARRATE, STORE)


@dataclass
class ProcessResult:
    """The outcome of a ``process_paper`` call: the run + the artifacts it landed.

    The :class:`PipelineRun` carries the final status + per-stage history (read back
    via the StageRun repository); ``paper_id`` / ``summary`` are surfaced so a caller
    (CLI, test) can report what was produced without re-querying.
    """

    run: PipelineRun
    paper_id: int
    summary: PaperSummary | None = None


class ProcessingService:
    """Orchestrate the persisted pipeline over one paper (the Job runner).

    Takes the stage objects + the persistence repositories + the STORE stage by
    constructor injection (the composition root wires concretes). Drives the stages,
    records the run/stage lifecycle, and upserts every artifact -- all through ports.
    """

    def __init__(
        self,
        *,
        ingest: IngestStage,
        summarise: SummariseStage,
        render: RenderStage,
        narrate: NarrateStage | None,
        store: StoreStage,
        papers: Repository[Paper],
        runs: Repository[PipelineRun],
        stage_runs: Repository[StageRun],
        summaries: Repository[Summary],
        clock: Clock,
    ) -> None:
        """Wire the orchestrator.

        Args:
            ingest/summarise/render: the pure pipeline stage objects.
            narrate: the NARRATE stage, or ``None`` to skip narration (it needs an
                ElevenLabs key the other stages do not, so a summary-only run omits
                it -- the NARRATE stage records as SKIPPED).
            store: the STORE stage (the DB upserts behind the Repository port).
            papers: the Paper repository (title lookup on a replayed summary).
            runs/stage_runs: repositories for the run/stage provenance rows.
            summaries: the Summary repository, used for the cache-skip check (does a
                Summary already exist for the paper at the new input hash?).
            clock: the injected time source for run/stage timestamps.
        """
        self._ingest = ingest
        self._summarise = summarise
        self._render = render
        self._narrate = narrate
        self._store = store
        self._papers = papers
        self._runs = runs
        self._stage_runs = stage_runs
        self._summaries = summaries
        self._clock = clock

    def process_paper(
        self,
        pdf_path: Path,
        config: DownLowConfig,
        *,
        user_id: int,
        force: bool = False,
    ) -> ProcessResult:
        """Run the full persisted pipeline over ``pdf_path``; return the run + result.

        Steps INGEST -> SUMMARISE -> RENDER -> NARRATE -> STORE, persisting a
        PipelineRun + a StageRun per stage. A stage already SUCCEEDED by the latest
        prior run (whose durable output still exists) is replayed from that output
        and recorded SKIPPED -- so a re-run resumes from the first non-succeeded
        stage. ``force`` bypasses both the stage file caches and the
        resume/cache-skip (a full rebuild).

        Args:
            pdf_path: the source PDF to process.
            config: the resolved typed config (steering profiles + per-stage config).
            user_id: the owning user (multi-user-ready; single owner today).
            force: rebuild everything (bypass caches + resume).

        Returns:
            A :class:`ProcessResult` with the finished run + the paper id + summary.

        Raises:
            FileNotFoundError: if ``pdf_path`` does not exist (a programmer error;
                the CLI validates first, but the service guards too).
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"cannot process a PDF that does not exist: {pdf_path}")

        source_hash = self._source_hash(pdf_path)
        # The paper must exist before the run can reference it (the run is FK'd to a
        # paper). We upsert it now from the source hash; INGEST/F5 backfill its
        # title/metadata at STORE time.
        paper = self._store.upsert_paper(user_id=user_id, source_hash=source_hash, title=pdf_path.stem)
        assert paper.id is not None  # the store assigns the id on upsert
        paper_id = paper.id

        prior = set() if force else self._latest_succeeded_stages(paper_id)
        run = self._start_run(paper_id)
        runner = _RunExecution(
            svc=self,
            run=run,
            config=config,
            pdf_path=pdf_path,
            paper_id=paper_id,
            user_id=user_id,
            prior_succeeded=prior,
            force=force,
        )
        return runner.execute()

    # --- run lifecycle helpers (used by _RunExecution) ----------------------- #

    def _start_run(self, paper_id: int) -> PipelineRun:
        """Create the PipelineRun row in RUNNING with its requested stages."""
        return self._runs.add(
            PipelineRun(
                paper_id=paper_id,
                status=RunStatus.RUNNING,
                requested_stages=list(DEFAULT_STAGES),
                started_at=self._now(),
            )
        )

    def _finish_run(self, run: PipelineRun, status: RunStatus, *, error: str | None = None) -> PipelineRun:
        """Flip the run to its terminal status with the finish timestamp."""
        return self._runs.add(
            run.model_copy(update={"id": run.id, "status": status, "error": error, "finished_at": self._now()})
        )

    def _record_stage(
        self,
        run_id: int,
        stage_name: str,
        status: StageStatus,
        *,
        cache_hit: bool = False,
        output_ref: str | None = None,
        model_id: str | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
    ) -> StageRun:
        """Persist a StageRun row in its current status (one row per stage attempt)."""
        now = self._now()
        terminal = status in (StageStatus.SUCCEEDED, StageStatus.FAILED, StageStatus.SKIPPED)
        return self._stage_runs.add(
            StageRun(
                run_id=run_id,
                stage_name=stage_name,
                status=status,
                cache_hit=cache_hit,
                model_id=model_id,
                output_ref=output_ref,
                error=error,
                started_at=started_at or now,
                finished_at=now if terminal else None,
            )
        )

    def _latest_succeeded_stages(self, paper_id: int) -> set[str]:
        """The stage names the most recent prior run SUCCEEDED (for resume).

        Resume basis: a re-run replays the stages the latest run already succeeded
        and resumes at the first it did not. We take only the *latest* run's stage
        set (not the union across all history) so a re-run after deliberately failing
        an earlier stage re-attempts it. A SKIPPED stage counts as
        succeeded-equivalent (its output was reused), so it is replayable.
        """
        runs = self._runs.list(paper_id=paper_id)
        if not runs:
            return set()
        latest = max(runs, key=lambda r: r.id or 0)
        if latest.id is None:
            return set()
        done = {StageStatus.SUCCEEDED, StageStatus.SKIPPED}
        return {sr.stage_name for sr in self._stage_runs.list(run_id=latest.id) if sr.status in done}

    def _existing_summary(self, paper_id: int, content_hash: str) -> Summary | None:
        """The persisted Summary for this paper at ``content_hash``, or ``None``.

        The SUMMARISE cache-skip key: when a Summary row already exists for the
        paper's current input hash, the DB output is satisfied and the stage is
        SKIPPED (the LLM call + the upsert are both avoided).
        """
        matches = self._summaries.list(paper_id=paper_id, content_hash=content_hash)
        return matches[0] if matches else None

    def _existing_report(self, paper_id: int) -> object | None:
        """The persisted report asset for the paper (RENDER resume read-back)."""
        return self._store.latest_report(paper_id)

    def _existing_episode(self, paper_id: int) -> object | None:
        """The persisted episode for the paper (NARRATE resume read-back)."""
        return self._store.episode_for_paper(paper_id)

    def _paper_title(self, paper_id: int) -> str:
        """The stored paper title (restores the title a replayed Summary lacks)."""
        paper = self._papers.get(paper_id)
        return paper.title if paper is not None else ""

    def _now(self) -> datetime:
        return self._clock.now()

    @staticmethod
    def _source_hash(pdf_path: Path) -> str:
        """sha256 of the raw PDF bytes (the paper dedupe + run anchor)."""
        return hashlib.sha256(pdf_path.read_bytes()).hexdigest()


class _RunExecution:
    """One in-flight run's mutable execution state (keeps ``process_paper`` flat).

    Threads the stage outputs (extracted text, summary, render/narrate refs) between
    stages and records each StageRun, so the public method stays a readable sequence
    rather than a long parameter-passing chain.
    """

    def __init__(
        self,
        *,
        svc: ProcessingService,
        run: PipelineRun,
        config: DownLowConfig,
        pdf_path: Path,
        paper_id: int,
        user_id: int,
        prior_succeeded: set[str],
        force: bool,
    ) -> None:
        self._svc = svc
        self._run = run
        self._cfg = config
        self._pdf = pdf_path
        self._paper_id = paper_id
        self._user_id = user_id
        self._prior = prior_succeeded
        self._force = force
        # Stage outputs threaded downstream.
        self._extracted: ExtractedText | None = None
        self._summary: PaperSummary | None = None
        self._script: NarrationScript | None = None
        self._mp3: bytes | None = None
        # The RUNNING instant of the in-flight stage, so a FAILED row stamped by the
        # _guard wrapper shares its predecessor's started_at.
        self._stage_started: datetime = self._svc._now()

    @property
    def _run_id(self) -> int:
        assert self._run.id is not None  # created in RUNNING with an assigned id
        return self._run.id

    def execute(self) -> ProcessResult:
        """Run the compute stages then the terminal STORE; FAIL on the first error.

        Each compute stage (INGEST/SUMMARISE/RENDER/NARRATE) persists its own output
        through the StoreStage *immediately on success*, so partial progress is
        durable before the next (possibly-failing) stage runs. The terminal STORE
        finalizer runs only if every compute stage succeeded; it does the final
        cross-artifact assembly (the Episode/EpisodePaper link). On a compute-stage
        failure the run is FAILED and STORE never runs -- but everything that did
        succeed is already persisted, so a re-run resumes from the DB.
        """
        try:
            self._guard(INGEST, self._run_ingest)
            self._guard(SUMMARISE, self._run_summarise)
            self._guard(RENDER, self._run_render)
            self._guard(NARRATE, self._run_narrate)
            self._guard(STORE, self._run_store)
        except DownLowError as exc:
            finished = self._svc._finish_run(self._run, RunStatus.FAILED, error=str(exc))
            return ProcessResult(run=finished, paper_id=self._paper_id, summary=self._summary)

        finished = self._svc._finish_run(self._run, RunStatus.SUCCEEDED)
        return ProcessResult(run=finished, paper_id=self._paper_id, summary=self._summary)

    def _guard(self, stage_name: str, body: Callable[[], None]) -> None:
        """Run a stage body; on a modelled failure, record it FAILED then re-raise.

        Each stage records its own RUNNING/SUCCEEDED/SKIPPED transitions; this wrapper
        adds the FAILED transition in one place, so a stage that raises a
        :class:`DownLowError` leaves a faithful StageRun (status FAILED, the error)
        before the run itself is flipped to FAILED in :meth:`execute`. The
        ``_stage_started`` instant (set by the stage when it recorded RUNNING) keeps
        the FAILED row's ``started_at`` consistent with its RUNNING row.
        """
        try:
            body()
        except DownLowError as exc:
            self._svc._record_stage(
                self._run_id,
                stage_name,
                StageStatus.FAILED,
                error=str(exc),
                started_at=self._stage_started,
            )
            raise

    # --- individual stages (each persists its own output on success) --------- #

    def _run_ingest(self) -> None:
        """INGEST: extract text + persist the paper's page_count immediately.

        Produces the extracted text (cheap behind its source-hash file cache) and
        incrementally persists the paper's page_count so it is durable before the
        downstream stages run. When the latest prior run succeeded INGEST and we are
        not forcing, the replay is recorded SKIPPED (resume semantics) -- the
        extracted text is still produced from cache so downstream has page_count.
        """
        started = self._stage_started = self._svc._now()
        self._extracted = self._svc._ingest.run(self._pdf, force=self._force)
        if self._can_skip(INGEST):
            self._svc._record_stage(self._run_id, INGEST, StageStatus.SKIPPED, cache_hit=True, started_at=started)
            return
        # Incremental persist: backfill the paper's page_count now (the title is
        # learned at SUMMARISE; upsert_paper preserves identity + does not clobber).
        self._svc._store.upsert_paper(
            user_id=self._user_id,
            source_hash=self._extracted.source_hash,
            title="",
            page_count=self._extracted.page_count,
        )
        self._svc._record_stage(
            self._run_id, INGEST, StageStatus.SUCCEEDED, output_ref=self._extracted.content_hash, started_at=started
        )

    def _run_summarise(self) -> None:
        """SUMMARISE: replay-from-DB when satisfied; else generate + persist now.

        Resume / cache-skip: if a persisted Summary exists for this paper at the
        current input hash (and we are not forcing), load it back as the
        :class:`PaperSummary` DTO -- no LLM call, no re-persist -- and record
        SKIPPED. Otherwise generate, **upsert the Summary immediately** (before
        RENDER, so it survives a later RENDER failure), and record SUCCEEDED.
        """
        started = self._stage_started = self._svc._now()
        input_hash = self._summary_input_hash()
        existing = None if self._force else self._svc._existing_summary(self._paper_id, input_hash)
        if existing is not None:
            self._summary = self._summary_from_row(existing)
            self._svc._record_stage(
                self._run_id,
                SUMMARISE,
                StageStatus.SKIPPED,
                cache_hit=True,
                output_ref=str(existing.id),
                model_id=existing.model_id,
                started_at=started,
            )
            return

        self._svc._record_stage(self._run_id, SUMMARISE, StageStatus.RUNNING, started_at=started)
        summary = self._svc._summarise.run(
            self._pdf,
            self._cfg.research_profile,
            self._cfg.output_profile,
            self._cfg.summary,
            force=self._force,
        )
        self._summary = summary
        # Incremental persist: the Summary lands BEFORE RENDER, so a RENDER failure
        # leaves it durable and a resume replays it from the DB (no new LLM call).
        self._svc._store.upsert_paper(
            user_id=self._user_id,
            source_hash=input_hash,
            title=summary.title,
        )
        stored = self._svc._store.upsert_summary(self._paper_id, summary)
        self._svc._record_stage(
            self._run_id,
            SUMMARISE,
            StageStatus.SUCCEEDED,
            output_ref=str(stored.id),
            model_id=summary.model,
            started_at=started,
        )

    def _run_render(self) -> None:
        """RENDER: replay-from-DB when satisfied; else compile + persist now.

        Independent of NARRATE. On a clean resume (the prior run succeeded RENDER and
        the report asset is still persisted) the compile is skipped and the stage is
        recorded SKIPPED. Otherwise the report PDF is compiled, the
        :class:`ReportAsset` is **upserted immediately**, and SUCCEEDED recorded.
        """
        started = self._stage_started = self._svc._now()
        assert self._summary is not None  # SUMMARISE ran before RENDER
        if self._can_skip(RENDER) and self._svc._existing_report(self._paper_id) is not None:
            self._svc._record_stage(self._run_id, RENDER, StageStatus.SKIPPED, cache_hit=True, started_at=started)
            return

        self._svc._record_stage(self._run_id, RENDER, StageStatus.RUNNING, started_at=started)
        result = self._svc._render.run([self._summary], self._cfg.report, force=self._force)
        stored = self._svc._store.upsert_report(
            self._paper_id,
            pdf_ref=result.ref,
            filename=f"{result.slug}.pdf",
            template_version=self._cfg.report.template_version,
            run_id=self._run_id,
        )
        self._svc._record_stage(
            self._run_id, RENDER, StageStatus.SUCCEEDED, output_ref=str(stored.id), started_at=started
        )

    def _run_narrate(self) -> None:
        """NARRATE: generate the episode + persist now, or SKIP if not wired.

        Independent of RENDER's success. When no NARRATE stage is injected (a
        summary-only deployment lacking the ElevenLabs key) the stage is recorded
        SKIPPED so the run still SUCCEEDS with the report it produced (graceful
        degradation). Otherwise the script + mp3 are produced and the Episode /
        EpisodePaper / PodcastAsset are **upserted immediately**.
        """
        started = self._stage_started = self._svc._now()
        if self._svc._narrate is None:
            self._svc._record_stage(self._run_id, NARRATE, StageStatus.SKIPPED, started_at=started)
            return
        if self._can_skip(NARRATE) and self._svc._existing_episode(self._paper_id) is not None:
            self._svc._record_stage(self._run_id, NARRATE, StageStatus.SKIPPED, cache_hit=True, started_at=started)
            return

        assert self._summary is not None  # SUMMARISE ran before NARRATE
        self._svc._record_stage(self._run_id, NARRATE, StageStatus.RUNNING, started_at=started)
        script = self._svc._narrate.generate_script(
            self._pdf, self._cfg.narration, summary=self._summary, force=self._force
        )
        mp3 = self._svc._narrate.run(self._pdf, self._cfg.narration, summary=self._summary, force=self._force)
        self._script = script
        self._mp3 = mp3
        self._svc._store.upsert_episode_podcast(
            self._paper_id,
            user_id=self._user_id,
            mp3_ref=self._mp3_ref(mp3),
            script=script,
        )
        self._svc._record_stage(self._run_id, NARRATE, StageStatus.SUCCEEDED, model_id=script.model, started_at=started)

    def _run_store(self) -> None:
        """Terminal STORE finalizer: runs only after every compute stage succeeded.

        The compute stages already persisted their own outputs incrementally, so this
        finalizer does the final cross-artifact assembly -- ensuring the per-paper
        Episode/EpisodePaper link exists when narration was produced -- and records
        the STORE stage SUCCEEDED. It is idempotent (every operation is an upsert),
        and it never runs on a failed run (the failing compute stage raises first).
        """
        started = self._stage_started = self._svc._now()
        self._svc._record_stage(self._run_id, STORE, StageStatus.RUNNING, started_at=started)
        # Final assembly: the Episode/PodcastAsset were upserted in NARRATE; this
        # re-asserts the link idempotently so the finalizer is the single place the
        # run's outputs are confirmed complete (a no-op when already linked).
        if self._mp3 is not None and self._script is not None:
            self._svc._store.upsert_episode_podcast(
                self._paper_id,
                user_id=self._user_id,
                mp3_ref=self._mp3_ref(self._mp3),
                script=self._script,
            )
        self._svc._record_stage(self._run_id, STORE, StageStatus.SUCCEEDED, started_at=started)

    # --- cache-skip / resume helpers ---------------------------------------- #

    def _can_skip(self, stage_name: str) -> bool:
        """True when resume allows replaying ``stage_name`` from its prior success."""
        return not self._force and self._prior_has(stage_name)

    def _prior_has(self, stage_name: str) -> bool:
        return stage_name in self._prior

    def _summary_input_hash(self) -> str:
        """The summary's cache-skip input hash.

        Mirrors the SUMMARISE stage's native-PDF path, which stamps the source hash
        as the summary ``input_hash``; INGEST has already produced it. We use it as
        the persisted ``content_hash`` anchor so the cache-skip check matches what
        STORE persisted on the prior run.
        """
        if self._extracted is not None:
            return self._extracted.source_hash
        return ProcessingService._source_hash(self._pdf)

    def _summary_from_row(self, row: Summary) -> PaperSummary:
        """Reconstruct the summary DTO from its persisted row (for a SKIPPED stage).

        Lets RENDER/NARRATE consume a replayed summary without re-calling the LLM.
        The :class:`Summary` row does not persist the paper title (it lives on
        :class:`Paper`), so the title is restored from the paper row -- keeping the
        rendered report's heading correct on a resumed run.
        """
        return PaperSummary(
            title=self._svc._paper_title(self._paper_id),
            overall_summary=row.overall_summary,
            key_findings=[KeyFinding.model_validate(kf) for kf in row.key_findings],
            contributions=list(row.contributions),
            methods=row.methods,
            gaps_and_limitations=list(row.gaps_and_limitations),
            relevance_to_profile=row.relevance_to_profile,
            input_hash=row.content_hash,
            profile_hash=row.profile_hash,
            model=row.model_id,
            prompt_version=row.prompt_version,
        )

    @staticmethod
    def _mp3_ref(mp3: bytes) -> str:
        """A deterministic mp3 ref for the episode (content-keyed, stable on re-run).

        The NARRATE stage returns the mp3 *bytes* (it has no ArtifactStore today);
        we derive a deterministic ref from the bytes so STORE's
        ``(episode_id, mp3_ref)`` upsert is stable across re-runs of unchanged
        content (a future ArtifactStore-backed NARRATE supplies the real ref).
        """
        digest = hashlib.sha256(mp3).hexdigest()[:16]
        return f"audio/{digest}.mp3"
