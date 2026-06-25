"""STORE stage (Stage 5): persist pipeline outputs to the DB, idempotently.

PURE orchestration: stdlib + ``domain`` (the entities + the ports) only. No
``sqlmodel`` / ``sqlalchemy`` / ``Session`` here -- the stage persists through the
:class:`~downlow.domain.ports.Repository` *port* (one per entity type, injected),
and the binaries themselves stay on the filesystem behind the
:class:`~downlow.domain.ports.ArtifactStore` (the stage records only their *refs*,
never blobs in the DB). This is the unification the journal wanted: kills the
legacy ``pdf_texts.json`` / ``research_data.json`` / ``document_data.json`` / the
implicit ``users/`` tree, with structured data in SQLite and binaries on disk.

Flow (PROJECT_PLAN.md -> Stage 5 STORE):

1. upsert the :class:`Paper` keyed on ``source_hash`` (dedupe; display title from
   the F5 heuristic / extracted metadata);
2. upsert the :class:`Summary` keyed on ``(paper_id, content_hash)``;
3. upsert the :class:`ReportAsset` keyed on ``(paper_id, pdf_ref)`` -- the ref is
   deterministic in the report slug, so a re-render with the same content lands the
   same ref and does not duplicate;
4. upsert the :class:`Episode` (per-paper now, via the :class:`EpisodePaper` join)
   + its :class:`PodcastAsset` keyed on ``(episode_id, mp3_ref)``.

**Idempotent by construction.** Every persist is an upsert keyed on the content
hash / deterministic ref the upstream stage produced, so re-running STORE on an
unchanged pipeline output is a no-op (it returns the existing rows, inserts
nothing). A stage's content hash is the *durable* dedupe key (not the row id), so
this survives a wiped-and-rebuilt run history.

Each persist method is independent (RENDER and NARRATE are independent stages), so
a caller may STORE only the artifacts a partial run produced.
"""

from __future__ import annotations

from dataclasses import dataclass

from downlow.domain.entities import (
    Episode,
    EpisodePaper,
    Paper,
    PodcastAsset,
    ReportAsset,
    Summary,
)
from downlow.domain.enums import RunStatus
from downlow.domain.ports import Repository
from downlow.domain.schemas import NarrationScript, PaperSummary


@dataclass
class StoredArtifacts:
    """The DB rows STORE persisted in a run (each ``None`` for a stage not run).

    Carries the upserted entities back so the orchestrator can record their ids on
    the :class:`~downlow.domain.entities.StageRun` ``output_ref`` and a caller can
    inspect what landed without re-reading the DB.
    """

    paper: Paper
    summary: Summary | None = None
    report: ReportAsset | None = None
    episode: Episode | None = None
    podcast: PodcastAsset | None = None


class StoreStage:
    """Upsert pipeline outputs to the DB behind the :class:`Repository` port.

    Holds one repository per entity type it persists (all bound to the same session
    at the composition root). Pure orchestration: the stage knows the *upsert keys*
    (content hashes, deterministic refs) and the entity shape; it knows nothing
    about SQL, sessions, or dialects.
    """

    name = "store"

    def __init__(
        self,
        *,
        papers: Repository[Paper],
        summaries: Repository[Summary],
        reports: Repository[ReportAsset],
        episodes: Repository[Episode],
        episode_papers: Repository[EpisodePaper],
        podcasts: Repository[PodcastAsset],
    ) -> None:
        """Wire the stage with one repository per persisted entity type."""
        self._papers = papers
        self._summaries = summaries
        self._reports = reports
        self._episodes = episodes
        self._episode_papers = episode_papers
        self._podcasts = podcasts

    # --- Paper (dedupe by source_hash) -------------------------------------- #

    def upsert_paper(
        self,
        *,
        user_id: int,
        source_hash: str,
        title: str,
        source_pdf_ref: str = "",
        extracted_text_ref: str | None = None,
        page_count: int | None = None,
        authors: list[str] | None = None,
        doi: str | None = None,
    ) -> Paper:
        """Insert (or return the existing) :class:`Paper` keyed on ``source_hash``.

        ``source_hash`` = ``sha256(pdf_bytes)`` is the dedupe key -- a re-added
        identical PDF resolves to the same paper rather than a duplicate row. On a
        hit the durable identity (id, created_at) is preserved; the mutable display
        fields (title, refs, page_count, authors, doi) are refreshed only when the
        caller supplies a non-empty value, so a later run that learned the title
        (F5) backfills it without clobbering it with a blank.
        """
        existing = self._paper_by_hash(source_hash)
        if existing is None:
            return self._papers.add(
                Paper(
                    user_id=user_id,
                    title=title,
                    source_pdf_ref=source_pdf_ref,
                    source_hash=source_hash,
                    extracted_text_ref=extracted_text_ref,
                    page_count=page_count,
                    authors=authors or [],
                    doi=doi,
                )
            )
        return self._refresh_paper(
            existing,
            title=title,
            source_pdf_ref=source_pdf_ref,
            extracted_text_ref=extracted_text_ref,
            page_count=page_count,
            authors=authors,
            doi=doi,
        )

    def _refresh_paper(
        self,
        paper: Paper,
        *,
        title: str,
        source_pdf_ref: str,
        extracted_text_ref: str | None,
        page_count: int | None,
        authors: list[str] | None,
        doi: str | None,
    ) -> Paper:
        """Backfill an existing paper's mutable fields without losing its identity.

        Only non-empty incoming values overwrite -- a blank title / ref / None
        page_count from a partial run never erases a value an earlier run learned.
        If nothing changed, the existing row is returned untouched (a true no-op,
        the re-run-unchanged case). No-op short-circuits the write so re-running
        STORE on identical input issues zero DB writes.
        """
        changes: dict[str, object] = {}
        if title and title != paper.title:
            changes["title"] = title
        if source_pdf_ref and source_pdf_ref != paper.source_pdf_ref:
            changes["source_pdf_ref"] = source_pdf_ref
        if extracted_text_ref and extracted_text_ref != paper.extracted_text_ref:
            changes["extracted_text_ref"] = extracted_text_ref
        if page_count is not None and page_count != paper.page_count:
            changes["page_count"] = page_count
        if authors and authors != paper.authors:
            changes["authors"] = authors
        if doi and doi != paper.doi:
            changes["doi"] = doi
        if not changes:
            return paper
        return self._papers.add(paper.model_copy(update={**changes, "id": paper.id}))

    def _paper_by_hash(self, source_hash: str) -> Paper | None:
        matches = self._papers.list(source_hash=source_hash)
        return matches[0] if matches else None

    # --- Summary (dedupe by paper + content_hash) --------------------------- #

    def upsert_summary(self, paper_id: int, summary: PaperSummary) -> Summary:
        """Insert (or return the existing) :class:`Summary` for this paper + content.

        Keyed on ``(paper_id, content_hash)`` where ``content_hash`` is the summary
        DTO's ``input_hash`` (the source/content hash of the summarised input). The
        SUMMARISE provenance (model, prompt_version, the two hashes) is persisted so
        regeneration and cache invalidation stay explicit. Re-storing the same
        summary returns the existing row (no duplicate).
        """
        content_hash = summary.input_hash
        existing = self._summary_by_content(paper_id, content_hash)
        if existing is not None:
            return existing
        return self._summaries.add(
            Summary(
                paper_id=paper_id,
                overall_summary=summary.overall_summary,
                key_findings=[finding.model_dump() for finding in summary.key_findings],
                contributions=list(summary.contributions),
                gaps_and_limitations=list(summary.gaps_and_limitations),
                methods=summary.methods,
                relevance_to_profile=summary.relevance_to_profile,
                model_id=summary.model,
                prompt_version=summary.prompt_version,
                content_hash=content_hash,
                profile_hash=summary.profile_hash,
            )
        )

    def _summary_by_content(self, paper_id: int, content_hash: str) -> Summary | None:
        matches = self._summaries.list(paper_id=paper_id, content_hash=content_hash)
        return matches[0] if matches else None

    # --- ReportAsset (dedupe by paper + deterministic pdf_ref) -------------- #

    def upsert_report(
        self,
        paper_id: int,
        *,
        pdf_ref: str,
        filename: str,
        template_version: str,
        run_id: int | None = None,
    ) -> ReportAsset:
        """Insert (or return the existing) :class:`ReportAsset` for this paper + ref.

        Keyed on ``(paper_id, pdf_ref)``: the RENDER stage's ``ref`` is deterministic
        in the report slug + content, so a re-render of unchanged content lands the
        same ref and STORE returns the existing row. The PDF binary itself already
        lives on the filesystem (the ArtifactStore wrote it in RENDER); this records
        only the reference.
        """
        existing = self._report_by_ref(paper_id, pdf_ref)
        if existing is not None:
            return existing
        return self._reports.add(
            ReportAsset(
                paper_id=paper_id,
                run_id=run_id,
                pdf_ref=pdf_ref,
                filename=filename,
                template_version=template_version,
            )
        )

    def _report_by_ref(self, paper_id: int, pdf_ref: str) -> ReportAsset | None:
        matches = self._reports.list(paper_id=paper_id, pdf_ref=pdf_ref)
        return matches[0] if matches else None

    def latest_report(self, paper_id: int) -> ReportAsset | None:
        """The paper's most-recently-stored report asset, or ``None`` if none yet.

        The resume read-back for RENDER: when a prior run already persisted a report
        for the paper, the stage replays as SKIPPED rather than recompiling.
        """
        reports = self._reports.list(paper_id=paper_id)
        return reports[-1] if reports else None

    # --- Episode + PodcastAsset (per-paper now; multi-paper-ready) ---------- #

    def upsert_episode_podcast(
        self,
        paper_id: int,
        *,
        user_id: int,
        mp3_ref: str,
        script: NarrationScript,
        host_voice_id: int | None = None,
        duration_seconds: float | None = None,
    ) -> tuple[Episode, PodcastAsset]:
        """Upsert the per-paper :class:`Episode` + its :class:`PodcastAsset`.

        The episode is found via its :class:`EpisodePaper` join (single-paper now:
        one join row), created with its join row if absent. The podcast asset is
        keyed on ``(episode_id, mp3_ref)`` -- the NARRATE mp3 ref is deterministic
        in the script + voices, so re-narrating unchanged content returns the
        existing asset. The mp3 binary already lives on disk; only its ref + the
        regenerable :class:`NarrationScript` blob are stored.
        """
        episode = self.episode_for_paper(paper_id)
        if episode is None:
            episode = self._episodes.add(
                Episode(user_id=user_id, title=script.episode_title, status=RunStatus.SUCCEEDED)
            )
            assert episode.id is not None  # the store assigns the id on add
            self._episode_papers.add(EpisodePaper(episode_id=episode.id, paper_id=paper_id, order=0))

        assert episode.id is not None
        existing = self._podcast_by_ref(episode.id, mp3_ref)
        if existing is not None:
            return episode, existing

        podcast = self._podcasts.add(
            PodcastAsset(
                episode_id=episode.id,
                mp3_ref=mp3_ref,
                narration_script=script.model_dump(),
                host_voice_id=host_voice_id,
                model_id=script.model,
                duration_seconds=duration_seconds,
            )
        )
        return episode, podcast

    def episode_for_paper(self, paper_id: int) -> Episode | None:
        """The existing per-paper episode (via the EpisodePaper join), or ``None``.

        Single-paper today: a paper maps to at most one episode. The join is queried
        first (the durable link), then the episode resolved by id -- so this works
        unchanged when a multi-paper episode references several papers. Public so the
        orchestrator can read it back for NARRATE's resume (skip when already done).
        """
        joins = self._episode_papers.list(paper_id=paper_id)
        if not joins:
            return None
        return self._episodes.get(joins[0].episode_id)

    def _podcast_by_ref(self, episode_id: int, mp3_ref: str) -> PodcastAsset | None:
        matches = self._podcasts.list(episode_id=episode_id, mp3_ref=mp3_ref)
        return matches[0] if matches else None
