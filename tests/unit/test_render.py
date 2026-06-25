"""Unit tests for F3 -- the RENDER stage, its composer, slugify, and the cache.

Everything runs on fakes (FakeReportRenderer / FakeArtifactStore / FakeLLMClient):
no ``typst`` binary, no subprocess, no real filesystem layout. Covers the
PaperSummary[] -> ReportData assembly, the templated default + optional LLM title,
deterministic path-safe slugify (incl. collision), the multi-summary merge into
one report, the render cache (hit/miss/force), and the stage orchestration writing
the PDF to ``reports/<slug>.pdf`` via the ArtifactStore.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from downlow.config.models import ModelConfig
from downlow.config.profiles import ReportConfig
from downlow.core.stages.render import RenderStage, disambiguate_slug, slugify
from downlow.domain.errors import LLMError, TypstCompileError
from downlow.domain.schemas import KeyFinding, PaperSummary, ReportData, ReportTitleSuggestion
from tests.fakes.llm import FakeLLMClient
from tests.fakes.render import FakeArtifactStore, FakeReportRenderer

# --------------------------------------------------------------------------- #
# Fixtures / helpers.
# --------------------------------------------------------------------------- #


def _summary(title: str = "A Paper on Generalisation", *, input_hash: str = "hash-1") -> PaperSummary:
    """A schema-valid PaperSummary with a content hash set (the render-cache key input)."""
    return PaperSummary(
        title=title,
        overall_summary="An overall summary of the paper, long enough to be real prose for the report.",
        key_findings=[
            KeyFinding(statement="Method X improves accuracy.", evidence="+4.2 points"),
            KeyFinding(statement="The gain is robust.", evidence=None),
        ],
        contributions=["A new objective.", "A released suite."],
        methods="Controlled comparison against three baselines.",
        gaps_and_limitations=["Single modality.", "Small sample."],
        relevance_to_profile="Bears on cross-domain generalisation.",
        input_hash=input_hash,
    )


def _report_cfg(**overrides: object) -> ReportConfig:
    base: dict[str, object] = {
        "template_version": "report-v1",
        "title_mode": "templated",
        "model": ModelConfig(id="claude-sonnet-4-6", max_tokens=200, effort="low"),
        "prompt_version": "report-title-v1",
    }
    base.update(overrides)
    return ReportConfig(**base)  # type: ignore[arg-type]


def _stage(
    *,
    renderer: FakeReportRenderer | None = None,
    store: FakeArtifactStore | None = None,
    llm: FakeLLMClient | None = None,
    cache_dir: Path | None = None,
) -> tuple[RenderStage, FakeReportRenderer, FakeArtifactStore]:
    renderer = renderer or FakeReportRenderer()
    store = store or FakeArtifactStore()
    stage = RenderStage(renderer, store, llm=llm, cache_dir=cache_dir)
    return stage, renderer, store


# --------------------------------------------------------------------------- #
# Assembly: PaperSummary[] -> ReportData.
# --------------------------------------------------------------------------- #


def test_assemble_builds_report_data_with_title_and_template_version() -> None:
    summaries = [_summary("First Paper", input_hash="h1"), _summary("Second Paper", input_hash="h2")]
    data = RenderStage.assemble(summaries, "My Report", _report_cfg(template_version="report-v9"))

    assert isinstance(data, ReportData)
    assert data.meta.title == "My Report"
    assert data.meta.template_version == "report-v9"
    assert [s.title for s in data.summaries] == ["First Paper", "Second Paper"]


def test_assembled_data_serialises_to_template_loadable_json() -> None:
    # The adapter serialises ReportData via model_dump_json; assert the shape the
    # Typst template loads (meta + summaries with the six content fields).
    data = RenderStage.assemble([_summary("Paper")], "T", _report_cfg())
    payload = json.loads(data.model_dump_json())

    assert set(payload) == {"meta", "summaries"}
    assert set(payload["meta"]) == {"title", "template_version"}
    paper = payload["summaries"][0]
    for field in ("title", "overall_summary", "key_findings", "contributions", "methods", "gaps_and_limitations"):
        assert field in paper
    assert payload["summaries"][0]["key_findings"][0]["statement"]


# --------------------------------------------------------------------------- #
# Title: templated default + optional LLM override.
# --------------------------------------------------------------------------- #


def test_single_paper_templated_title_is_the_paper_title() -> None:
    stage, _, _ = _stage()
    result = stage.run([_summary("Contrastive Pretraining Wins")], _report_cfg())
    assert result.title == "Contrastive Pretraining Wins"


def test_multi_paper_templated_title_is_the_collection_default() -> None:
    stage, _, _ = _stage()
    result = stage.run([_summary("A", input_hash="a"), _summary("B", input_hash="b")], _report_cfg())
    assert result.title == "Research Summaries"


def test_blank_paper_title_falls_back_to_collection_default() -> None:
    stage, _, _ = _stage()
    result = stage.run([_summary("   ")], _report_cfg())
    assert result.title == "Research Summaries"


def test_explicit_title_overrides_both_templated_and_llm() -> None:
    llm = FakeLLMClient(result=ReportTitleSuggestion(title="LLM title", slug="llm-title"))
    stage, _, _ = _stage(llm=llm)
    result = stage.run([_summary("Paper")], _report_cfg(title_mode="llm"), title="Explicit")
    assert result.title == "Explicit"
    assert llm.call_count == 0  # explicit title short-circuits the LLM


def test_llm_title_mode_uses_the_model_title_but_reslugifies() -> None:
    # The model proposes a path-UNSAFE slug; the stage must ignore it and derive a
    # safe slug from the title itself (the model never picks the filename).
    llm = FakeLLMClient(result=ReportTitleSuggestion(title="Robustness Under Shift", slug="../etc/passwd"))
    stage, _, store = _stage(llm=llm)
    result = stage.run([_summary("Paper")], _report_cfg(title_mode="llm"))

    assert result.title == "Robustness Under Shift"
    assert result.slug == "robustness-under-shift"
    assert "reports/robustness-under-shift.pdf" in store.stored
    assert llm.call_count == 1


def test_llm_title_mode_without_a_client_raises() -> None:
    stage, _, _ = _stage(llm=None)  # no LLM wired
    with pytest.raises(LLMError):
        stage.run([_summary("Paper")], _report_cfg(title_mode="llm"))


def test_llm_empty_title_falls_back_to_templated() -> None:
    llm = FakeLLMClient(result=ReportTitleSuggestion(title="   ", slug="x"))
    stage, _, _ = _stage(llm=llm)
    result = stage.run([_summary("Fallback Paper")], _report_cfg(title_mode="llm"))
    assert result.title == "Fallback Paper"


# --------------------------------------------------------------------------- #
# Slugify: deterministic, path-safe, collision.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Hello World", "hello-world"),
        ("  Trim  Me  ", "trim-me"),
        ("Mixed CASE Title", "mixed-case-title"),
        ("Lots___of   separators!!!", "lots-of-separators"),
        ("a/b/c", "a-b-c"),
        ("..//../etc/passwd", "etc-passwd"),
        ("C:\\Windows\\system32", "c-windows-system32"),
        ("---leading-and-trailing---", "leading-and-trailing"),
    ],
)
def test_slugify_is_path_safe_and_deterministic(title: str, expected: str) -> None:
    slug = slugify(title)
    assert slug == expected
    assert slugify(title) == slug  # deterministic
    # path-safety: no separators, no parent refs, no leading dot, no spaces
    for bad in ("/", "\\", "..", " "):
        assert bad not in slug
    assert not slug.startswith(".")


def test_slugify_empty_or_punctuation_only_falls_back() -> None:
    assert slugify("") == "report"
    assert slugify("!!!") == "report"
    assert slugify("   ") == "report"


def test_slugify_non_ascii_is_stripped_to_fallback() -> None:
    # chr(0x00E9) is e-acute, chr(0x4E2D) a CJK char -- neither is [a-z0-9].
    assert slugify(chr(0x00E9) + chr(0x4E2D)) == "report"


def test_slugify_caps_length() -> None:
    slug = slugify("word " * 50)
    assert len(slug) <= 80
    assert not slug.endswith("-")


def test_disambiguate_slug_handles_collisions() -> None:
    taken: set[str] = {"ood-generalisation"}
    assert disambiguate_slug("fresh", taken) == "fresh"
    assert disambiguate_slug("ood-generalisation", taken) == "ood-generalisation-2"
    taken.add("ood-generalisation-2")
    assert disambiguate_slug("ood-generalisation", taken) == "ood-generalisation-3"


def test_two_titles_can_collide_then_disambiguate() -> None:
    # Two different titles that slugify identically -> collision handling avoids a clobber.
    a = slugify("OOD Generalisation!")
    b = slugify("ood   generalisation")
    assert a == b == "ood-generalisation"
    assert disambiguate_slug(b, {a}) == "ood-generalisation-2"


# --------------------------------------------------------------------------- #
# Orchestration: render via the port + write via the ArtifactStore.
# --------------------------------------------------------------------------- #


def test_run_renders_and_stores_the_pdf_under_reports_slug() -> None:
    stage, renderer, store = _stage()
    result = stage.run([_summary("Zero Shot Transfer")], _report_cfg())

    assert renderer.call_count == 1
    assert result.pdf_bytes.startswith(b"%PDF")
    assert result.slug == "zero-shot-transfer"
    key = "reports/zero-shot-transfer.pdf"
    assert store.stored[key] == result.pdf_bytes
    assert result.ref == f"fake://{key}"


def test_run_passes_assembled_data_to_the_renderer() -> None:
    stage, renderer, _ = _stage()
    summaries = [_summary("P1", input_hash="h1"), _summary("P2", input_hash="h2")]
    stage.run(summaries, _report_cfg(template_version="report-v3"), title="Merged")

    data = renderer.last_data
    assert data is not None
    assert data.meta.title == "Merged"
    assert data.meta.template_version == "report-v3"
    assert [s.title for s in data.summaries] == ["P1", "P2"]  # multi-summary merge, in order


def test_run_with_no_summaries_raises() -> None:
    stage, _, _ = _stage()
    with pytest.raises(ValueError, match="at least one"):
        stage.run([], _report_cfg())


def test_renderer_failure_propagates_as_typst_compile_error() -> None:
    renderer = FakeReportRenderer(fail=True)
    stage, _, _ = _stage(renderer=renderer)
    with pytest.raises(TypstCompileError):
        stage.run([_summary("Paper")], _report_cfg())


# --------------------------------------------------------------------------- #
# Render cache: hit / miss / force.
# --------------------------------------------------------------------------- #


def test_cache_miss_then_hit_skips_recompile(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    renderer = FakeReportRenderer(pdf_bytes=b"%PDF-cached-bytes")
    stage, _, store = _stage(renderer=renderer, cache_dir=cache_dir)

    first = stage.run([_summary("Cached Paper")], _report_cfg())
    assert renderer.call_count == 1  # miss -> compiled

    second = stage.run([_summary("Cached Paper")], _report_cfg())
    assert renderer.call_count == 1  # hit -> NOT recompiled
    assert second.pdf_bytes == first.pdf_bytes
    assert store.stored["reports/cached-paper.pdf"] == first.pdf_bytes


def test_force_bypasses_the_cache(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    renderer = FakeReportRenderer()
    stage, _, _ = _stage(renderer=renderer, cache_dir=cache_dir)

    stage.run([_summary("Paper")], _report_cfg())
    assert renderer.call_count == 1
    stage.run([_summary("Paper")], _report_cfg(), force=True)
    assert renderer.call_count == 2  # force recompiled despite the cache


def test_cache_invalidates_on_template_version_change(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    renderer = FakeReportRenderer()
    stage, _, _ = _stage(renderer=renderer, cache_dir=cache_dir)

    stage.run([_summary("Paper", input_hash="h")], _report_cfg(template_version="report-v1"))
    stage.run([_summary("Paper", input_hash="h")], _report_cfg(template_version="report-v2"))
    assert renderer.call_count == 2  # a different template version is a different cache key


def test_no_cache_dir_always_recompiles() -> None:
    renderer = FakeReportRenderer()
    stage, _, _ = _stage(renderer=renderer, cache_dir=None)
    stage.run([_summary("Paper")], _report_cfg())
    stage.run([_summary("Paper")], _report_cfg())
    assert renderer.call_count == 2  # no cache -> every run compiles


def test_cache_key_is_order_independent_for_the_same_set(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    renderer = FakeReportRenderer()
    stage, _, _ = _stage(renderer=renderer, cache_dir=cache_dir)

    a = _summary("A", input_hash="aaa")
    b = _summary("B", input_hash="bbb")
    stage.run([a, b], _report_cfg(), title="Same")
    stage.run([b, a], _report_cfg(), title="Same")  # same set, reversed order
    assert renderer.call_count == 1  # order does not change the cache key
