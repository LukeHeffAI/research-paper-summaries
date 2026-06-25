"""Golden-file test for the assembled report data JSON (F3).

The Typst template loads ``summaries.json`` -- the serialised :class:`ReportData`
-- as data. This snapshots that serialised JSON against a committed fixture so a
schema change or an accidental field rename in the report path is caught
deterministically, with no ``typst`` binary and no subprocess.

Regenerate the golden file deliberately (and review the diff) when the report DTO
or its content intentionally changes:

    python -c "from tests.unit.test_render_golden import _build; \
import pathlib; pathlib.Path('tests/fixtures/report_data.golden.json').write_text(_build())"
"""

from __future__ import annotations

import json
from pathlib import Path

from downlow.config.models import ModelConfig
from downlow.config.profiles import ReportConfig
from downlow.core.stages.render import RenderStage
from downlow.domain.schemas import KeyFinding, PaperSummary

GOLDEN = Path(__file__).parent.parent / "fixtures" / "report_data.golden.json"


def _summaries() -> list[PaperSummary]:
    return [
        PaperSummary(
            title="Contrastive Pretraining Improves Zero-Shot Cross-Domain Transfer",
            overall_summary=(
                "A controlled study of whether a contrastive objective lets a model "
                "generalise to unseen domains. The gains grow with the domain shift."
            ),
            key_findings=[
                KeyFinding(
                    statement="Contrastive beats supervised on zero-shot transfer.",
                    evidence="+6.1 average accuracy points across five held-out domains",
                ),
                KeyFinding(statement="The medical-scan confidence is poorly calibrated.", evidence=None),
            ],
            contributions=["A controlled comparison of pretraining objectives.", "A released evaluation suite."],
            methods="Two equal-parameter models pretrained on the same corpus, evaluated zero-shot.",
            gaps_and_limitations=["Classification only.", "Pretraining compute is not held constant."],
            relevance_to_profile="Bears directly on cross-domain generalisation.",
            input_hash="content-hash-1",
        ),
        PaperSummary(
            title="A Second Paper To Prove The Merge",
            overall_summary="A short second summary so the golden snapshot covers the multi-paper merge.",
            key_findings=[KeyFinding(statement="Merging works.", evidence="two sections rendered")],
            contributions=["Demonstrates 1..N papers in one report."],
            methods="N/A.",
            gaps_and_limitations=["Illustrative only."],
            relevance_to_profile="Exercises the legacy merge-into-one-document behaviour.",
            input_hash="content-hash-2",
        ),
    ]


def _build() -> str:
    """Build the deterministic assembled-data JSON (pretty-printed for a readable diff)."""
    cfg = ReportConfig(
        template_version="report-v1",
        title_mode="templated",
        model=ModelConfig(id="claude-sonnet-4-6", max_tokens=200, effort="low"),
    )
    data = RenderStage.assemble(_summaries(), "Research Summaries", cfg)
    return json.dumps(json.loads(data.model_dump_json()), indent=2, ensure_ascii=True, sort_keys=True) + "\n"


def test_assembled_report_data_matches_golden() -> None:
    assert GOLDEN.exists(), f"golden file missing: {GOLDEN} (regenerate via _build())"
    expected = GOLDEN.read_text(encoding="utf-8")
    assert _build() == expected, "assembled report JSON drifted from the golden snapshot; review then regenerate"
