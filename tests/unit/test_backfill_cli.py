"""Unit tests for the ``dl backfill`` CLI command (Phase 2.3).

Drives the Typer app via ``CliRunner`` with ``backfill_session`` monkeypatched to
yield a real :class:`BackfillService` over in-memory fake repositories (no DB file,
no network). The legacy-tree loader runs for real against a temp ``legacy/`` fixture,
so the command's parse -> import -> report path is covered end to end, including the
idempotent second run and the missing-source / malformed-data exits.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from downlow.cli.app import app
from downlow.core.services.backfill import BackfillService
from downlow.domain.entities import OutputProfileRecord, ResearchProfileRecord, User
from tests.conftest import FrozenClock
from tests.fakes.repository import FakeRepository, InMemoryStore

runner = CliRunner()


def _legacy_tree(root: Path) -> Path:
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "research_data.json").write_text(
        json.dumps(
            {
                "users": {
                    "luke": {
                        "research_field": "Machine Learning",
                        "research_topic": "generalisation",
                        "research_interests": ["Multimodal models"],
                        "research_focus": "transfer",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (data / "document_data.json").write_text(
        json.dumps({"document_type": "Literature Review", "document_return_details": ["Key findings"]}),
        encoding="utf-8",
    )
    audio = root / "users" / "luke" / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    (audio / "orphan.pdf.mp3").write_bytes(b"ID3fake")
    return root


def _install(monkeypatch: pytest.MonkeyPatch, shared: InMemoryStore) -> None:
    clock = FrozenClock()

    @contextmanager
    def fake_backfill_session(*args: Any, **kwargs: Any) -> Iterator[BackfillService]:
        yield BackfillService(
            users=FakeRepository(User, shared, clock=clock),
            research_profiles=FakeRepository(ResearchProfileRecord, shared, clock=clock),
            output_profiles=FakeRepository(OutputProfileRecord, shared, clock=clock),
        )

    monkeypatch.setattr("downlow.cli.commands.backfill.backfill_session", fake_backfill_session)


def test_backfill_imports_and_reports(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    shared = InMemoryStore()
    _install(monkeypatch, shared)
    source = _legacy_tree(tmp_path / "legacy")

    result = runner.invoke(app, ["backfill", "--source", str(source)])

    assert result.exit_code == 0, result.output
    assert "Backfill complete." in result.output
    assert "imported" in result.output
    assert "orphan audio" in result.output
    assert "orphan.pdf.mp3" in result.output
    # One user, one research profile, one output profile written.
    assert len(FakeRepository(User, shared).list()) == 1
    assert len(FakeRepository(ResearchProfileRecord, shared).list()) == 1
    assert len(FakeRepository(OutputProfileRecord, shared).list()) == 1


def test_backfill_idempotent_via_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    shared = InMemoryStore()
    _install(monkeypatch, shared)
    source = _legacy_tree(tmp_path / "legacy")

    first = runner.invoke(app, ["backfill", "--source", str(source)])
    assert first.exit_code == 0, first.output

    counts_before = (
        len(FakeRepository(User, shared).list()),
        len(FakeRepository(ResearchProfileRecord, shared).list()),
        len(FakeRepository(OutputProfileRecord, shared).list()),
    )

    second = runner.invoke(app, ["backfill", "--source", str(source)])
    assert second.exit_code == 0, second.output
    assert "already present" in second.output

    counts_after = (
        len(FakeRepository(User, shared).list()),
        len(FakeRepository(ResearchProfileRecord, shared).list()),
        len(FakeRepository(OutputProfileRecord, shared).list()),
    )
    assert counts_before == counts_after == (1, 1, 1)


def test_backfill_missing_source_exits_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch, InMemoryStore())
    result = runner.invoke(app, ["backfill", "--source", str(tmp_path / "nope")])
    assert result.exit_code == 2
    assert "not found" in result.output


def test_backfill_malformed_json_exits_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install(monkeypatch, InMemoryStore())
    source = tmp_path / "legacy"
    (source / "data").mkdir(parents=True, exist_ok=True)
    (source / "data" / "research_data.json").write_text("{broken", encoding="utf-8")

    result = runner.invoke(app, ["backfill", "--source", str(source)])
    assert result.exit_code == 1
    assert "aborted" in result.output.lower()
