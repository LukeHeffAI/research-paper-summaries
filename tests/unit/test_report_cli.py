"""Unit tests for the ``dl report`` CLI command (F3) with the stages faked.

Drives the Typer app via ``CliRunner`` with ``build_container`` monkeypatched to a
fake container (a fake summarise + a real RenderStage over fakes): no Anthropic
key, no ``typst`` binary, no network. Covers the happy path (summarise -> render ->
write PDF), the multi-PDF merge, the ``--title`` override, missing-PDF + render-
failure exits, and the default ArtifactStore destination.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from downlow.cli.app import app
from downlow.config.models import ModelConfig
from downlow.config.profiles import (
    DownLowConfig,
    NarrationConfig,
    ReportConfig,
    SummaryConfig,
)
from downlow.core.stages.render import RenderStage
from downlow.domain.errors import TypstCompileError
from downlow.domain.schemas import KeyFinding, OutputProfile, PaperSummary, ResearchProfile
from tests.fakes.render import FakeArtifactStore, FakeReportRenderer

runner = CliRunner()


def _summary(title: str) -> PaperSummary:
    return PaperSummary(
        title=title,
        overall_summary="An overall summary that is real prose for the report body.",
        key_findings=[KeyFinding(statement="A finding.", evidence="+1 point")],
        contributions=["A contribution."],
        methods="A method.",
        gaps_and_limitations=["A gap."],
        relevance_to_profile="Relevant.",
        input_hash="h-cli",
    )


class _FakeSummarise:
    """A stand-in for the SUMMARISE stage that returns a canned summary per PDF."""

    def __init__(self) -> None:
        self.calls: list[Path] = []

    def run(self, pdf: Path, *args: Any, **kwargs: Any) -> PaperSummary:
        self.calls.append(pdf)
        return _summary(f"Paper {pdf.stem}")


def _config() -> DownLowConfig:
    model = ModelConfig(id="claude-sonnet-4-6", max_tokens=200, effort="low")
    return DownLowConfig(
        research_profile=ResearchProfile(name="luke", research_field="ML", research_topic="t", research_focus="f"),
        output_profile=OutputProfile(name="lit", document_type="Literature Review"),
        summary=SummaryConfig(model=model),
        report=ReportConfig(model=model),
        narration=NarrationConfig(model=model),
    )


@dataclass
class _FakeContainer:
    config: DownLowConfig
    summarise: _FakeSummarise
    render: RenderStage


def _install_container(
    monkeypatch: pytest.MonkeyPatch, *, renderer: FakeReportRenderer | None = None
) -> tuple[_FakeContainer, FakeArtifactStore]:
    renderer = renderer or FakeReportRenderer()
    store = FakeArtifactStore()
    container = _FakeContainer(
        config=_config(),
        summarise=_FakeSummarise(),
        render=RenderStage(renderer, store),
    )

    def fake_build_container(**kwargs: Any) -> _FakeContainer:
        return container

    monkeypatch.setattr("downlow.cli.commands.report.build_container", fake_build_container)
    return container, store


def test_report_happy_path_writes_pdf_to_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_container(monkeypatch)
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-fake")
    out = tmp_path / "report.pdf"

    result = runner.invoke(app, ["report", str(pdf), "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF")
    assert "Wrote report" in result.output


def test_report_default_destination_is_the_artifact_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _container, store = _install_container(monkeypatch)
    pdf = tmp_path / "zero-shot.pdf"
    pdf.write_bytes(b"%PDF-fake")

    result = runner.invoke(app, ["report", str(pdf)])  # no --out

    assert result.exit_code == 0, result.output
    # Single paper -> the paper title -> slug; landed in the store under reports/.
    assert "reports/paper-zero-shot.pdf" in store.stored


def test_report_merges_multiple_pdfs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    container, _ = _install_container(monkeypatch)
    pdfs = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
    for p in pdfs:
        p.write_bytes(b"%PDF-fake")

    result = runner.invoke(app, ["report", str(pdfs[0]), str(pdfs[1])])

    assert result.exit_code == 0, result.output
    assert len(container.summarise.calls) == 2  # one summary per PDF, merged into one report


def test_report_title_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_container(monkeypatch)
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-fake")

    result = runner.invoke(app, ["report", str(pdf), "--title", "My Custom Title"])

    assert result.exit_code == 0, result.output
    assert "My Custom Title" in result.output


def test_report_missing_pdf_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_container(monkeypatch)
    result = runner.invoke(app, ["report", str(tmp_path / "nope.pdf")])
    assert result.exit_code == 2
    assert "not found" in result.output


def test_report_render_failure_exits_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_container(monkeypatch, renderer=FakeReportRenderer(fail=True))
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-fake")

    result = runner.invoke(app, ["report", str(pdf)])
    assert result.exit_code == 1
    assert "rendering failed" in result.output


def test_typst_compile_error_carries_stderr() -> None:
    # Sanity check on the error type the CLI surfaces.
    err = TypstCompileError("boom", returncode=2, stderr="error: bad template")
    assert err.returncode == 2
    assert err.stderr == "error: bad template"
