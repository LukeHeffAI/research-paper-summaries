"""Unit tests for the ``dl process`` + ``dl library`` CLI commands (Phase 2.1).

Drives the Typer app via ``CliRunner`` with ``processing_session`` /
``library_session`` monkeypatched to yield fake-wired containers (real stages +
the F1-F4 fakes + in-memory repositories) -- no network, no DB file, no binaries.
Covers the happy ``process`` path, the missing-PDF exit, and ``library list`` /
``library show`` reading the persisted papers.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from downlow.cli.app import app
from downlow.cli.deps import ProcessingContainer
from downlow.config.models import ModelConfig
from downlow.config.profiles import (
    DownLowConfig,
    MetadataConfig,
    NarrationConfig,
    ReportConfig,
    SummaryConfig,
)
from downlow.config.settings import Settings
from downlow.core.services.library import LibraryService
from downlow.core.services.processing import ProcessingService
from downlow.core.stages.ingest import IngestStage
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
from downlow.domain.schemas import OutputProfile, ResearchProfile
from tests.conftest import FrozenClock
from tests.fakes.llm import FakeLLMClient
from tests.fakes.pdf import FakePdfExtractor
from tests.fakes.render import FakeArtifactStore, FakeReportRenderer
from tests.fakes.repository import FakeRepository, InMemoryStore

runner = CliRunner()


def _config() -> DownLowConfig:
    model = ModelConfig(id="claude-sonnet-4-6", max_tokens=8000, effort="low")
    return DownLowConfig(
        research_profile=ResearchProfile(
            name="luke", research_field="ML", research_topic="generalisation", research_focus="transfer"
        ),
        output_profile=OutputProfile(name="lit", document_type="Literature Review"),
        summary=SummaryConfig(model=model),
        report=ReportConfig(),
        narration=NarrationConfig(model=model),
        metadata=MetadataConfig(),
    )


def _build(shared: InMemoryStore) -> tuple[ProcessingService, LibraryService]:
    """Wire a summary-only (no NARRATE) processing service over the shared store."""
    clock = FrozenClock()
    store_stage = StoreStage(
        papers=FakeRepository(Paper, shared, clock=clock),
        summaries=FakeRepository(Summary, shared, clock=clock),
        reports=FakeRepository(ReportAsset, shared, clock=clock),
        episodes=FakeRepository(Episode, shared, clock=clock),
        episode_papers=FakeRepository(EpisodePaper, shared, clock=clock),
        podcasts=FakeRepository(PodcastAsset, shared, clock=clock),
    )
    extractor = FakePdfExtractor()
    service = ProcessingService(
        ingest=IngestStage(extractor, cache_dir=Path("/tmp/downlow-cli-test-cache")),
        summarise=SummariseStage(FakeLLMClient(), cache_dir=Path("/tmp/downlow-cli-test-cache"), extractor=extractor),
        render=RenderStage(FakeReportRenderer(), FakeArtifactStore(), cache_dir=Path("/tmp/downlow-cli-test-cache")),
        narrate=None,
        store=store_stage,
        papers=FakeRepository(Paper, shared, clock=clock),
        runs=FakeRepository(PipelineRun, shared, clock=clock),
        stage_runs=FakeRepository(StageRun, shared, clock=clock),
        summaries=FakeRepository(Summary, shared, clock=clock),
        clock=clock,
    )
    library = LibraryService(FakeRepository(Paper, shared, clock=clock))
    return service, library


def _install(monkeypatch: pytest.MonkeyPatch, shared: InMemoryStore) -> None:
    service, library = _build(shared)

    @contextmanager
    def fake_processing_session(*args: Any, **kwargs: Any) -> Iterator[ProcessingContainer]:
        yield ProcessingContainer(
            settings=Settings(anthropic_api_key="x"),
            config=_config(),
            processing=service,
            library=library,
            user_id=1,
        )

    @contextmanager
    def fake_library_session(*args: Any, **kwargs: Any) -> Iterator[LibraryService]:
        yield library

    monkeypatch.setattr("downlow.cli.commands.process.processing_session", fake_processing_session)
    monkeypatch.setattr("downlow.cli.commands.library.library_session", fake_library_session)


def _pdf(tmp_path: Path) -> Path:
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"%PDF-1.7\nfake\n")
    return p


def test_process_succeeds_and_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    shared = InMemoryStore()
    _install(monkeypatch, shared)
    result = runner.invoke(app, ["process", str(_pdf(tmp_path)), "--no-audio"])

    assert result.exit_code == 0, result.output
    assert "Processed" in result.output
    assert len(FakeRepository(Paper, shared).list()) == 1


def test_process_missing_pdf_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch, InMemoryStore())
    result = runner.invoke(app, ["process", str(tmp_path / "nope.pdf")])
    assert result.exit_code == 2
    assert "not found" in result.output


def test_library_list_shows_processed_paper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    shared = InMemoryStore()
    _install(monkeypatch, shared)
    runner.invoke(app, ["process", str(_pdf(tmp_path)), "--no-audio"])

    result = runner.invoke(app, ["library", "list"])
    assert result.exit_code == 0, result.output
    # The processed paper appears (titled from the fake summary).
    assert "A Fake Paper on Generalisation" in result.output or "paper" in result.output.lower()


def test_library_list_empty_message(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, InMemoryStore())
    result = runner.invoke(app, ["library", "list"])
    assert result.exit_code == 0, result.output
    assert "empty" in result.output


def test_library_show_renders_detail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    shared = InMemoryStore()
    _install(monkeypatch, shared)
    proc = runner.invoke(app, ["process", str(_pdf(tmp_path)), "--no-audio"])
    assert proc.exit_code == 0, proc.output
    paper_id = FakeRepository(Paper, shared).list()[0].id
    assert paper_id is not None

    result = runner.invoke(app, ["library", "show", str(paper_id)])
    assert result.exit_code == 0, result.output
    assert "title:" in result.output


def test_library_show_missing_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, InMemoryStore())
    result = runner.invoke(app, ["library", "show", "999"])
    assert result.exit_code == 1
    assert "No paper" in result.output
