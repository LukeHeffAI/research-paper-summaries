"""Unit tests for the TypstRenderer adapter (F3) with ``subprocess.run`` mocked.

No real ``typst`` binary needed: we patch ``subprocess.run`` to assert the adapter
serialises ``summaries.json`` beside the template, builds the ``typst compile``
command in an isolated cwd, returns the produced PDF bytes on success, and raises
:class:`TypstCompileError` (with captured stderr) on a non-zero exit or a missing
binary. The real-binary path is covered by the (skip-if-absent) integration test.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from downlow.adapters.render.typst_renderer import TypstRenderer
from downlow.domain.errors import TypstCompileError
from downlow.domain.schemas import KeyFinding, PaperSummary, ReportData, ReportMeta


def _report_data() -> ReportData:
    summary = PaperSummary(
        title="A Paper",
        overall_summary="A real-prose overall summary used in the report.",
        key_findings=[KeyFinding(statement="X improves Y.", evidence="+3 points")],
        contributions=["A contribution."],
        methods="A controlled comparison.",
        gaps_and_limitations=["A limitation."],
        relevance_to_profile="Relevant to the reader.",
        input_hash="h1",
    )
    return ReportData(meta=ReportMeta(title="My Report", template_version="report-v1"), summaries=[summary])


def test_render_writes_data_json_and_runs_typst_compile(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        # Record the command + cwd, and assert the inputs are written before compile.
        captured["cmd"] = cmd
        captured["cwd"] = kwargs["cwd"]
        workdir = Path(kwargs["cwd"])
        data_file = workdir / "summaries.json"
        template_file = workdir / "report.typ"
        assert data_file.exists(), "summaries.json must be written before compile"
        assert template_file.exists(), "report.typ template must be copied before compile"
        captured["data"] = json.loads(data_file.read_text(encoding="utf-8"))
        # Simulate the compiler producing the output PDF.
        (workdir / "out.pdf").write_bytes(b"%PDF-1.7\nrendered\n")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("downlow.adapters.render.typst_renderer.subprocess.run", fake_run)

    renderer = TypstRenderer(binary="typst")
    out = renderer.render(_report_data())

    assert out == b"%PDF-1.7\nrendered\n"
    assert out.startswith(b"%PDF")
    assert captured["cmd"] == ["typst", "compile", "report.typ", "out.pdf"]
    # The data the template will load is the serialised ReportData.
    assert captured["data"]["meta"]["title"] == "My Report"
    assert captured["data"]["summaries"][0]["title"] == "A Paper"


def test_render_honours_a_custom_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        seen["binary"] = cmd[0]
        (Path(kwargs["cwd"]) / "out.pdf").write_bytes(b"%PDF-x")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("downlow.adapters.render.typst_renderer.subprocess.run", fake_run)
    TypstRenderer(binary="/opt/typst/typst").render(_report_data())
    assert seen["binary"] == "/opt/typst/typst"


def test_render_raises_on_nonzero_exit_with_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.CalledProcessError(returncode=1, cmd=cmd, stderr=b"error: unknown function")

    monkeypatch.setattr("downlow.adapters.render.typst_renderer.subprocess.run", fake_run)

    with pytest.raises(TypstCompileError) as exc_info:
        TypstRenderer().render(_report_data())
    err = exc_info.value
    assert err.returncode == 1
    assert err.stderr is not None and "unknown function" in err.stderr


def test_render_raises_when_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError(2, "No such file or directory", cmd[0])

    monkeypatch.setattr("downlow.adapters.render.typst_renderer.subprocess.run", fake_run)

    with pytest.raises(TypstCompileError, match="not found"):
        TypstRenderer(binary="definitely-not-a-real-binary").render(_report_data())


def test_render_uses_an_isolated_temp_dir_that_is_cleaned_up(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_cwd: dict[str, str] = {}

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        seen_cwd["cwd"] = kwargs["cwd"]
        (Path(kwargs["cwd"]) / "out.pdf").write_bytes(b"%PDF")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr("downlow.adapters.render.typst_renderer.subprocess.run", fake_run)
    TypstRenderer().render(_report_data())
    # The temp compile dir is removed on exit (TemporaryDirectory context manager).
    assert not Path(seen_cwd["cwd"]).exists()
