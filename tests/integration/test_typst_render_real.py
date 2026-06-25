"""Integration test for the real ``typst`` binary (F3, the RENDER adapter).

Marked ``integration`` -- needs the system ``typst`` binary (report compilation).
Compiles a fixture :class:`ReportData` through the deterministic ``report.typ``
template and asserts a non-empty, valid PDF (``%PDF`` header). Skipped when
``typst`` is not installed (mirrors the F4 ffmpeg guard) so a local run without the
binary stays green -- CI installs typst. No network, no keys.
"""

from __future__ import annotations

import shutil

import pytest

from downlow.adapters.render.typst_renderer import TypstRenderer
from downlow.domain.schemas import KeyFinding, PaperSummary, ReportData, ReportMeta

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("typst") is None, reason="typst binary not installed (report rendering needs it)"),
]


def _report_data(*titles: str) -> ReportData:
    summaries = [
        PaperSummary(
            title=title,
            overall_summary=(
                "A real-prose overall summary with arbitrary characters that Typst must escape: "
                "a backslash \\, a hash #, a dollar $, quotes \" and ', and brackets [ ] { }."
            ),
            key_findings=[
                KeyFinding(statement="A finding with evidence.", evidence="+4.2 points (Table 2)"),
                KeyFinding(statement="A qualitative finding.", evidence=None),
            ],
            contributions=["A new objective.", "A released suite."],
            methods="A controlled comparison against three baselines.",
            gaps_and_limitations=["Single modality.", "Small sample."],
            relevance_to_profile="Bears on cross-domain generalisation.",
            input_hash=f"hash-{i}",
        )
        for i, title in enumerate(titles)
    ]
    return ReportData(meta=ReportMeta(title="Research Summaries", template_version="report-v1"), summaries=summaries)


def test_compiles_a_single_paper_to_a_valid_pdf() -> None:
    out = TypstRenderer().render(_report_data("A Paper on Generalisation"))
    assert isinstance(out, bytes)
    assert out.startswith(b"%PDF")
    assert len(out) > 1000  # a real, non-trivial PDF


def test_compiles_multiple_papers_into_one_report() -> None:
    out = TypstRenderer().render(_report_data("First Paper", "Second Paper", "Third Paper"))
    assert out.startswith(b"%PDF")
    assert len(out) > 1000


def test_arbitrary_strings_are_escaped_not_injected() -> None:
    # A title full of Typst-significant characters must not break compilation
    # (the template loads strings as DATA, so Typst escapes them).
    out = TypstRenderer().render(_report_data('# $ \\ [weird] {title} with "quotes"'))
    assert out.startswith(b"%PDF")
