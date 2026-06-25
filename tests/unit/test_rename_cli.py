"""Unit tests for the ``dl rename`` CLI command (F5) with the heuristic faked.

Drives the Typer app via ``CliRunner`` with ``build_filename_heuristic`` and
``load_config`` monkeypatched: no Anthropic key, no network, no pdfplumber. Covers
suggest-only (the default, changes nothing), ``--apply`` (rename), the already-named
no-op, the missing-PDF exit, and the clobber-refusal exit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from downlow.cli.app import app
from downlow.config.models import ModelConfig
from downlow.config.profiles import MetadataConfig
from downlow.core.services.filename import FilenameHeuristic
from downlow.domain.schemas import PaperMetadata
from tests.fakes.llm import FakeLLMClient

runner = CliRunner()


def _config() -> Any:
    # A minimal stand-in carrying just .metadata (the rename command reads only that).
    class _Cfg:
        metadata = MetadataConfig(model=ModelConfig(id="claude-sonnet-4-6", max_tokens=512, effort="low"))

    return _Cfg()


def _install(monkeypatch: pytest.MonkeyPatch, *, metadata: PaperMetadata) -> None:
    heuristic = FilenameHeuristic(FakeLLMClient(result=metadata), extractor=None, current_year=2026)

    def fake_build_heuristic(*args: Any, **kwargs: Any) -> FilenameHeuristic:
        return heuristic

    def fake_load_config(*args: Any, **kwargs: Any) -> Any:
        return _config()

    monkeypatch.setattr("downlow.cli.commands.rename.build_filename_heuristic", fake_build_heuristic)
    monkeypatch.setattr("downlow.cli.commands.rename.load_config", fake_load_config)


def test_rename_suggest_only_does_not_change_the_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch, metadata=PaperMetadata(title="Contrastive Learning", authors=["Jane Smith"], year=2021))
    pdf = tmp_path / "1234.pdf"
    pdf.write_bytes(b"%PDF-fake")

    result = runner.invoke(app, ["rename", str(pdf)])

    assert result.exit_code == 0, result.output
    assert "smith-2021-contrastive-learning.pdf" in result.output
    assert pdf.exists()  # suggest-only: nothing renamed
    assert not (tmp_path / "smith-2021-contrastive-learning.pdf").exists()


def test_rename_apply_renames_the_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch, metadata=PaperMetadata(title="Zero Shot Transfer", authors=["Ada Lovelace"], year=2020))
    pdf = tmp_path / "raw.pdf"
    pdf.write_bytes(b"%PDF-fake")

    result = runner.invoke(app, ["rename", str(pdf), "--apply"])

    assert result.exit_code == 0, result.output
    assert "Renamed" in result.output
    assert (tmp_path / "lovelace-2020-zero-shot-transfer.pdf").exists()
    assert not pdf.exists()


def test_rename_apply_already_named_is_a_noop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch, metadata=PaperMetadata(title="Paper", authors=["Jane Smith"], year=2021))
    pdf = tmp_path / "smith-2021-paper.pdf"
    pdf.write_bytes(b"%PDF-fake")

    result = runner.invoke(app, ["rename", str(pdf), "--apply"])

    assert result.exit_code == 0, result.output
    assert "nothing to do" in result.output
    assert pdf.exists()


def test_rename_apply_clobber_refusal_exits_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch, metadata=PaperMetadata(title="Paper", authors=["Jane Smith"], year=2021))
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"%PDF-source")
    (tmp_path / "smith-2021-paper.pdf").write_bytes(b"%PDF-other")  # target occupied

    result = runner.invoke(app, ["rename", str(pdf), "--apply"])

    assert result.exit_code == 1
    assert "Not renamed" in result.output
    assert pdf.exists()  # source untouched


def test_rename_missing_pdf_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch, metadata=PaperMetadata())
    result = runner.invoke(app, ["rename", str(tmp_path / "nope.pdf")])
    assert result.exit_code == 2
    assert "not found" in result.output
