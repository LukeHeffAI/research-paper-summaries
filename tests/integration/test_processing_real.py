"""Integration test: the persisted pipeline over a REAL SqlModelRepository.

The regression guard for the B1-B3 bugs the fake-only unit tests masked: it drives
``ProcessingService`` + ``StoreStage`` over the real ``SqlModelRepository`` + a real
``Session`` on a temp-file SQLite DB (FK pragma on), with fakes ONLY for the
external boundaries (LLM / TTS / mixer / PDF / renderer / artifact store). No
network, no real ``typst`` / ``ffmpeg`` binary.

It proves on real SQLite what the fakes could not:

* **idempotency (B2/B3):** running ``process_paper`` twice yields exactly ONE Paper
  row (deduped by ``source_hash``) and the run is flipped IN PLACE -- two runs, two
  PipelineRun rows, each a single terminal row, never a duplicated/orphaned run;
* **cache-skip resume:** the 2nd run records SUMMARISE SKIPPED and the LLM is not
  called again;
* **resume-from-failure:** a forced RENDER failure leaves ONE FAILED run with the
  Summary already persisted (incremental persist), and the retry resumes to
  SUCCEEDED replaying SUMMARISE from the DB with NO new LLM call;
* **the User FK seed (B1):** seeding ``User(id=1)`` first means the first paper write
  does not raise a foreign-key error.

Marked ``integration`` (real DB), though it needs no external service/binary.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session

from downlow.adapters.db.engine import SystemClock
from downlow.adapters.db.repositories import SqlModelRepository
from downlow.config.models import ModelConfig
from downlow.config.profiles import (
    DownLowConfig,
    MetadataConfig,
    NarrationConfig,
    ReportConfig,
    SummaryConfig,
)
from downlow.core.services.processing import RENDER, SUMMARISE, ProcessingService
from downlow.core.stages.ingest import IngestStage
from downlow.core.stages.narrate import NarrateStage
from downlow.core.stages.render import RenderStage
from downlow.core.stages.store import StoreStage
from downlow.core.stages.summarise import SummariseStage
from downlow.domain.entities import (
    Episode,
    EpisodePaper,
    Paper,
    PipelineRun,
    PodcastAsset,
    ReportAsset,
    StageRun,
    Summary,
    User,
)
from downlow.domain.enums import RunStatus, SpeakerRole, StageStatus
from downlow.domain.schemas import (
    NarrationScript,
    OutputProfile,
    ResearchProfile,
    Turn,
    VoiceRef,
)
from tests.fakes.audio import FakeAudioMixer
from tests.fakes.llm import FakeLLMClient
from tests.fakes.pdf import FakePdfExtractor
from tests.fakes.render import FakeArtifactStore, FakeReportRenderer
from tests.fakes.tts import FakeTTSClient

pytestmark = pytest.mark.integration


def _config() -> DownLowConfig:
    model = ModelConfig(id="claude-sonnet-4-6", max_tokens=8000, effort="low")
    return DownLowConfig(
        research_profile=ResearchProfile(
            name="luke", research_field="ML", research_topic="generalisation", research_focus="transfer"
        ),
        output_profile=OutputProfile(name="lit", document_type="Literature Review"),
        summary=SummaryConfig(model=model),
        report=ReportConfig(),
        narration=NarrationConfig(
            model=model,
            voices=[
                VoiceRef(role=SpeakerRole.HOST, voice_id="host-v"),
                VoiceRef(role=SpeakerRole.AUTHOR, voice_id="author-v"),
            ],
        ),
        metadata=MetadataConfig(),
    )


def _narration_script() -> NarrationScript:
    turns = [
        Turn(type="speech", role=SpeakerRole.HOST, text="Welcome to the show, what is the core idea?"),
        Turn(
            type="speech",
            role=SpeakerRole.AUTHOR,
            text="A new training objective that improves cross-domain transfer markedly across two domains.",
        ),
        Turn(type="speech", role=SpeakerRole.HOST, text="And what surprised you most about the result?"),
        Turn(
            type="speech",
            role=SpeakerRole.AUTHOR,
            text="That the gains held across two very different domains without any per-domain tuning at all.",
        ),
    ]
    return NarrationScript(
        episode_title="A Surprising Result",
        voices=[
            VoiceRef(role=SpeakerRole.HOST, voice_id="host-v"),
            VoiceRef(role=SpeakerRole.AUTHOR, voice_id="author-v"),
        ],
        turns=turns,
    )


@pytest.fixture
def engine(db_engine: Engine) -> Engine:
    """A real engine with the schema created -- SQLite locally, Postgres in CI.

    Backend-agnostic (Phase 2.2): delegates to the shared ``db_engine`` fixture,
    which honours ``DATABASE_URL`` (temp-file SQLite by default, Postgres when set,
    with a clean schema per test). The same ProcessingService idempotency / FK /
    resume-from-failure assertions therefore run unchanged on both backends.
    """
    return db_engine


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"%PDF-1.7\nreal-db integration test pdf bytes\n")
    return p


class _RealHarness:
    """Wires ProcessingService over REAL repositories on one real session.

    Fakes only the external boundaries (LLM/TTS/mixer/PDF/renderer/artifact store);
    every persistence path is the real SqlModelRepository so insert-vs-update and FK
    enforcement are exercised for real.
    """

    def __init__(self, session: Session, cache_dir: Path, *, render_fails: bool = False) -> None:
        clock = SystemClock()
        self.session = session
        self.llm = FakeLLMClient()
        self.extractor = FakePdfExtractor()
        self.renderer = FakeReportRenderer(fail=render_fails)
        self.tts = FakeTTSClient()
        self.mixer = FakeAudioMixer()

        narrate = NarrateStage(
            FakeLLMClient(result=_narration_script()),
            self.tts,
            self.mixer,
            cache_dir=cache_dir,
            assets_dir=cache_dir / "assets",
            extractor=self.extractor,
        )
        store_stage = StoreStage(
            papers=SqlModelRepository(session, Paper, clock=clock),
            summaries=SqlModelRepository(session, Summary, clock=clock),
            reports=SqlModelRepository(session, ReportAsset, clock=clock),
            episodes=SqlModelRepository(session, Episode, clock=clock),
            episode_papers=SqlModelRepository(session, EpisodePaper, clock=clock),
            podcasts=SqlModelRepository(session, PodcastAsset, clock=clock),
        )
        self.runs: SqlModelRepository[PipelineRun] = SqlModelRepository(session, PipelineRun, clock=clock)
        self.stage_runs: SqlModelRepository[StageRun] = SqlModelRepository(session, StageRun, clock=clock)
        self.papers: SqlModelRepository[Paper] = SqlModelRepository(session, Paper, clock=clock)
        self.service = ProcessingService(
            ingest=IngestStage(self.extractor, cache_dir=cache_dir),
            summarise=SummariseStage(self.llm, cache_dir=cache_dir, extractor=self.extractor),
            render=RenderStage(self.renderer, FakeArtifactStore(), cache_dir=cache_dir),
            narrate=narrate,
            store=store_stage,
            papers=SqlModelRepository(session, Paper, clock=clock),
            runs=self.runs,
            stage_runs=self.stage_runs,
            summaries=SqlModelRepository(session, Summary, clock=clock),
            clock=clock,
        )

    def stages_of(self, run_id: int) -> dict[str, StageStatus]:
        """Final status per stage_name for one run (latest StageRun row wins)."""
        final: dict[str, StageStatus] = {}
        for sr in sorted(self.stage_runs.list(run_id=run_id), key=lambda s: s.id or 0):
            final[sr.stage_name] = sr.status
        return final


def _seed_user(session: Session) -> None:
    """Seed the owning User(id=1) -- the FK every paper write depends on (B1)."""
    users: SqlModelRepository[User] = SqlModelRepository(session, User, clock=SystemClock())
    if users.get(1) is None:
        users.add(User(id=1, username="luke", display_name="Luke"))


def test_user_seed_lets_first_write_succeed_without_fk_error(engine: Engine, pdf: Path, tmp_path: Path) -> None:
    """B1: with the User seeded, the first paper write does not raise an FK error."""
    with Session(engine) as session:
        _seed_user(session)
        harness = _RealHarness(session, tmp_path / "cache")
        result = harness.service.process_paper(pdf, _config(), user_id=1)
        assert result.run.status is RunStatus.SUCCEEDED


def test_running_twice_is_idempotent_on_real_sqlite(engine: Engine, pdf: Path, tmp_path: Path) -> None:
    """B2/B3: two runs -> one Paper, two single terminal runs, no duplicates."""
    with Session(engine) as session:
        _seed_user(session)
        harness = _RealHarness(session, tmp_path / "cache")

        first = harness.service.process_paper(pdf, _config(), user_id=1)
        assert first.run.status is RunStatus.SUCCEEDED
        llm_calls_after_first = harness.llm.call_count
        assert llm_calls_after_first >= 1

        second = harness.service.process_paper(pdf, _config(), user_id=1)
        assert second.run.status is RunStatus.SUCCEEDED

        # Exactly ONE Paper row (deduped by source_hash) despite two runs.
        papers = harness.papers.list()
        assert len(papers) == 1, [p.id for p in papers]

        # Two runs, each flipped IN PLACE to a terminal status (no duplicate/orphan).
        runs = harness.runs.list()
        assert len(runs) == 2
        assert all(r.status is RunStatus.SUCCEEDED for r in runs)
        assert all(r.finished_at is not None for r in runs)

        # The 2nd run cache-skipped SUMMARISE -- no second LLM call.
        assert harness.llm.call_count == llm_calls_after_first
        assert second.run.id is not None
        assert harness.stages_of(second.run.id)[SUMMARISE] is StageStatus.SKIPPED

        # Still exactly one Summary row (the dedupe held on the real DB).
        summaries: SqlModelRepository[Summary] = SqlModelRepository(session, Summary, clock=SystemClock())
        assert len(summaries.list()) == 1


def test_resume_after_render_failure_on_real_sqlite(engine: Engine, pdf: Path, tmp_path: Path) -> None:
    """Resume-from-failure on real SQLite: one FAILED run, Summary persisted, retry OK."""
    cache_dir = tmp_path / "cache"
    with Session(engine) as session:
        _seed_user(session)

        # First run: RENDER forced to fail. INGEST + SUMMARISE succeed (Summary
        # incrementally persisted BEFORE render), then the run is FAILED.
        failing = _RealHarness(session, cache_dir, render_fails=True)
        failed = failing.service.process_paper(pdf, _config(), user_id=1)
        assert failed.run.status is RunStatus.FAILED
        assert failed.run.error
        llm_calls_after_failure = failing.llm.call_count
        assert llm_calls_after_failure >= 1

        assert failed.run.id is not None
        statuses = failing.stages_of(failed.run.id)
        assert statuses[SUMMARISE] is StageStatus.SUCCEEDED
        assert statuses[RENDER] is StageStatus.FAILED

        # The Summary was persisted incrementally despite the later RENDER failure.
        summaries: SqlModelRepository[Summary] = SqlModelRepository(session, Summary, clock=SystemClock())
        assert len(summaries.list()) == 1

        # Exactly one FAILED PipelineRun so far (flipped in place, not duplicated).
        runs: SqlModelRepository[PipelineRun] = SqlModelRepository(session, PipelineRun, clock=SystemClock())
        assert len(runs.list()) == 1
        assert runs.list()[0].status is RunStatus.FAILED

        # Retry with a working renderer: resume SUMMARISE from the DB (no new LLM
        # call), RENDER succeeds, the run completes SUCCEEDED.
        working = _RealHarness(session, cache_dir, render_fails=False)
        retry = working.service.process_paper(pdf, _config(), user_id=1)
        assert retry.run.status is RunStatus.SUCCEEDED
        assert working.llm.call_count == 0  # this harness's LLM never called: summary replayed from DB

        assert retry.run.id is not None
        retry_statuses = working.stages_of(retry.run.id)
        assert retry_statuses[SUMMARISE] is StageStatus.SKIPPED
        assert retry_statuses[RENDER] is StageStatus.SUCCEEDED

        # One Paper, one Summary, two runs (FAILED then SUCCEEDED) -- no duplication.
        assert len(SqlModelRepository(session, Paper, clock=SystemClock()).list()) == 1
        assert len(summaries.list()) == 1
        assert len(runs.list()) == 2
