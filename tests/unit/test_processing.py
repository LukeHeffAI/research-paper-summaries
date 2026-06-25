"""Unit tests for the processing orchestrator (Phase 2.1).

Real pipeline stages wired with the F1-F4 fakes (LLM/PDF/renderer/store/TTS/mixer)
+ in-memory fake repositories + a temp cache dir + a temp PDF -- no network, no
binaries. Asserts:

* the run/stage lifecycle: a PipelineRun + one StageRun per stage, with the right
  status transitions (RUNNING then SUCCEEDED; the run SUCCEEDED);
* cache-skip: a second run skips SUMMARISE (its Summary already persisted at the
  input hash) -- no second LLM call;
* resume-from-failure: a run whose RENDER stage fails marks the run FAILED with
  INGEST + SUMMARISE already SUCCEEDED; the retry resumes -- it does NOT re-call
  the LLM (SUMMARISE replays from its persisted output) and completes SUCCEEDED.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from downlow.config.models import ModelConfig
from downlow.config.profiles import (
    DownLowConfig,
    MetadataConfig,
    NarrationConfig,
    ReportConfig,
    SummaryConfig,
)
from downlow.core.services.processing import (
    INGEST,
    NARRATE,
    RENDER,
    STORE,
    SUMMARISE,
    ProcessingService,
)
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
)
from downlow.domain.enums import RunStatus, SpeakerRole, StageStatus
from downlow.domain.schemas import (
    NarrationScript,
    OutputProfile,
    ResearchProfile,
    Turn,
    VoiceRef,
)
from tests.conftest import FrozenClock
from tests.fakes.audio import FakeAudioMixer
from tests.fakes.llm import FakeLLMClient
from tests.fakes.pdf import FakePdfExtractor
from tests.fakes.render import FakeArtifactStore, FakeReportRenderer
from tests.fakes.repository import FakeRepository, InMemoryStore
from tests.fakes.tts import FakeTTSClient


def _config() -> DownLowConfig:
    """A minimal valid config: active profiles + per-stage config for every stage."""
    model = ModelConfig(id="claude-sonnet-4-6", max_tokens=8000, effort="low")
    return DownLowConfig(
        research_profile=ResearchProfile(
            name="luke",
            research_field="ML",
            research_topic="generalisation",
            research_focus="cross-domain transfer",
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
    """A schema-valid script that clears the NARRATE quality gate."""
    turns = [
        Turn(type="speech", role=SpeakerRole.HOST, text="Welcome to the show."),
        Turn(
            type="speech",
            role=SpeakerRole.AUTHOR,
            text="Thanks. The core idea is a new training objective that improves cross-domain transfer markedly.",
        ),
        Turn(type="speech", role=SpeakerRole.HOST, text="And what surprised you?"),
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
def pdf(tmp_path: Path) -> Path:
    """A tiny fake 'PDF' file (the fakes never parse it; the stages only hash it)."""
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"%PDF-1.7\nfake pdf bytes for the orchestration test\n")
    return p


class _Harness:
    """Holds the wired service + the fakes/repos so a test can drive + assert."""

    def __init__(self, tmp_path: Path, *, render_fails: bool = False, with_narration: bool = True) -> None:
        cache_dir = tmp_path / "cache"
        self.clock = FrozenClock()
        self.shared = InMemoryStore()

        self.llm = FakeLLMClient()
        self.extractor = FakePdfExtractor()
        self.renderer = FakeReportRenderer(fail=render_fails)
        self.artifacts = FakeArtifactStore()
        self.tts = FakeTTSClient()
        self.mixer = FakeAudioMixer()

        narrate_llm = FakeLLMClient(result=_narration_script())
        narrate: NarrateStage | None = None
        if with_narration:
            narrate = NarrateStage(
                narrate_llm,
                self.tts,
                self.mixer,
                cache_dir=cache_dir,
                assets_dir=tmp_path / "assets",
                extractor=self.extractor,
            )

        self.store_stage = StoreStage(
            papers=FakeRepository(Paper, self.shared, clock=self.clock),
            summaries=FakeRepository(Summary, self.shared, clock=self.clock),
            reports=FakeRepository(ReportAsset, self.shared, clock=self.clock),
            episodes=FakeRepository(Episode, self.shared, clock=self.clock),
            episode_papers=FakeRepository(EpisodePaper, self.shared, clock=self.clock),
            podcasts=FakeRepository(PodcastAsset, self.shared, clock=self.clock),
        )
        self.runs: FakeRepository[PipelineRun] = FakeRepository(PipelineRun, self.shared, clock=self.clock)
        self.stage_runs: FakeRepository[StageRun] = FakeRepository(StageRun, self.shared, clock=self.clock)

        self.service = ProcessingService(
            ingest=IngestStage(self.extractor, cache_dir=cache_dir),
            summarise=SummariseStage(self.llm, cache_dir=cache_dir, extractor=self.extractor),
            render=RenderStage(self.renderer, self.artifacts, cache_dir=cache_dir),
            narrate=narrate,
            store=self.store_stage,
            papers=FakeRepository(Paper, self.shared, clock=self.clock),
            runs=self.runs,
            stage_runs=self.stage_runs,
            summaries=FakeRepository(Summary, self.shared, clock=self.clock),
            clock=self.clock,
        )

    def stages_of(self, run_id: int) -> dict[str, StageStatus]:
        """Map stage name -> status for one run (one StageRun per stage here)."""
        return {sr.stage_name: sr.status for sr in self.stage_runs.list(run_id=run_id)}


# --------------------------------------------------------------------------- #
# Happy path: run + stage lifecycle                                             #
# --------------------------------------------------------------------------- #


def test_process_paper_records_run_and_stage_lifecycle(pdf: Path, tmp_path: Path) -> None:
    h = _Harness(tmp_path)
    result = h.service.process_paper(pdf, _config(), user_id=1)

    assert result.run.status is RunStatus.SUCCEEDED
    assert result.run.started_at is not None
    assert result.run.finished_at is not None
    assert result.summary is not None

    assert result.run.id is not None
    statuses = h.stages_of(result.run.id)
    # Every stage ran and succeeded (one StageRun per stage on a clean first run).
    for name in (INGEST, SUMMARISE, RENDER, NARRATE, STORE):
        assert statuses[name] is StageStatus.SUCCEEDED, name


def test_process_paper_persists_every_artifact(pdf: Path, tmp_path: Path) -> None:
    h = _Harness(tmp_path)
    result = h.service.process_paper(pdf, _config(), user_id=1)

    papers = FakeRepository(Paper, h.shared).list()
    assert len(papers) == 1
    assert papers[0].id == result.paper_id
    assert len(FakeRepository(Summary, h.shared).list()) == 1
    assert len(FakeRepository(ReportAsset, h.shared).list()) == 1
    assert len(FakeRepository(PodcastAsset, h.shared).list()) == 1


def test_narration_skipped_when_not_wired(pdf: Path, tmp_path: Path) -> None:
    h = _Harness(tmp_path, with_narration=False)
    result = h.service.process_paper(pdf, _config(), user_id=1)

    assert result.run.status is RunStatus.SUCCEEDED
    assert result.run.id is not None
    assert h.stages_of(result.run.id)[NARRATE] is StageStatus.SKIPPED
    # No podcast asset when narration is not wired (graceful degradation).
    assert FakeRepository(PodcastAsset, h.shared).list() == []


# --------------------------------------------------------------------------- #
# Cache-skip                                                                    #
# --------------------------------------------------------------------------- #


def test_second_run_cache_skips_summarise(pdf: Path, tmp_path: Path) -> None:
    h = _Harness(tmp_path)
    first = h.service.process_paper(pdf, _config(), user_id=1)
    assert first.run.status is RunStatus.SUCCEEDED
    calls_after_first = h.llm.call_count
    assert calls_after_first >= 1

    second = h.service.process_paper(pdf, _config(), user_id=1)
    assert second.run.status is RunStatus.SUCCEEDED
    assert second.run.id is not None
    # SUMMARISE was cache-skipped: its persisted Summary satisfied the input hash,
    # so no second LLM call was made for it.
    assert h.llm.call_count == calls_after_first
    assert h.stages_of(second.run.id)[SUMMARISE] is StageStatus.SKIPPED
    # No duplicate library rows after the second run.
    assert len(FakeRepository(Summary, h.shared).list()) == 1
    assert len(FakeRepository(Paper, h.shared).list()) == 1


# --------------------------------------------------------------------------- #
# Resume-from-failure                                                           #
# --------------------------------------------------------------------------- #


def test_failed_render_marks_run_failed_with_prior_stages_succeeded(pdf: Path, tmp_path: Path) -> None:
    h = _Harness(tmp_path, render_fails=True)
    result = h.service.process_paper(pdf, _config(), user_id=1)

    assert result.run.status is RunStatus.FAILED
    assert result.run.error
    assert result.run.id is not None
    statuses = h.stages_of(result.run.id)
    assert statuses[INGEST] is StageStatus.SUCCEEDED
    assert statuses[SUMMARISE] is StageStatus.SUCCEEDED
    assert statuses[RENDER] is StageStatus.FAILED
    # RENDER failed, so NARRATE + STORE never ran.
    assert NARRATE not in statuses
    assert STORE not in statuses


def test_rerun_resumes_after_a_render_failure_without_recalling_the_llm(pdf: Path, tmp_path: Path) -> None:
    # First run: SUMMARISE succeeds (LLM called) but RENDER fails.
    h = _Harness(tmp_path, render_fails=True)
    failed = h.service.process_paper(pdf, _config(), user_id=1)
    assert failed.run.status is RunStatus.FAILED
    llm_calls_after_failure = h.llm.call_count
    assert llm_calls_after_failure >= 1
    summary_rows = len(FakeRepository(Summary, h.shared).list())
    assert summary_rows == 1  # SUMMARISE persisted its output before RENDER failed

    # Repair the renderer (the transient failure cleared) and re-run on the same
    # shared store + caches. The retry must resume: SUMMARISE replays from its
    # persisted Summary (no new LLM call), and the run completes.
    h.renderer.fail = False
    retry = h.service.process_paper(pdf, _config(), user_id=1)

    assert retry.run.status is RunStatus.SUCCEEDED
    assert retry.run.id is not None
    statuses = h.stages_of(retry.run.id)
    assert statuses[SUMMARISE] is StageStatus.SKIPPED  # replayed from the DB, not redone
    assert statuses[RENDER] is StageStatus.SUCCEEDED
    assert statuses[STORE] is StageStatus.SUCCEEDED
    # The LLM was NOT called again for the summary on the resume.
    assert h.llm.call_count == llm_calls_after_failure
    # Still exactly one summary row (the resume reused it, did not duplicate).
    assert len(FakeRepository(Summary, h.shared).list()) == 1
