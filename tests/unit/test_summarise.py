"""Unit tests for F2 -- the SUMMARISE stage, prompts, config layer, and fake.

Everything runs on the FakeLLMClient: no network, no key, deterministic output.
Covers prompt composition (profile steering), structured-output validation, the
result cache (hit/miss + force), the section-split path, the truncation -> retry
path, profile loading from the config file, and the FakeLLMClient port contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from downlow.config.models import ModelConfig
from downlow.config.profiles import ConfigError, SummaryConfig, load_config
from downlow.core.prompts.summary import (
    PROMPT_VERSION,
    SUMMARY_SYSTEM_PROMPT,
    build_context_prompt,
)
from downlow.core.stages.summarise import (
    _MAX_INLINE_PDF_BYTES,
    _SMALL_PDF_FAST_PATH_BYTES,
    SummariseStage,
)
from downlow.domain.errors import LLMError, SummaryQualityError, TruncatedResponseError
from downlow.domain.ports import LLMClient, LLMDocument
from downlow.domain.schemas import KeyFinding, OutputProfile, PaperSummary, ResearchProfile
from tests.fakes.llm import FakeLLMClient

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
CONFIG_TOML = Path(__file__).parent.parent.parent / "config" / "downlow.toml"


# --------------------------------------------------------------------------- #
# Fixtures / helpers.
# --------------------------------------------------------------------------- #


@pytest.fixture
def research_profile() -> ResearchProfile:
    return ResearchProfile(
        name="luke",
        research_field="Machine Learning",
        research_topic="generalisation of large pretrained models",
        research_interests=["Zero-shot classification", "Model interpretability"],
        research_focus="developing models that generalise to new tasks and domains",
    )


@pytest.fixture
def output_profile() -> OutputProfile:
    return OutputProfile(
        name="literature_review",
        document_type="Literature Review",
        return_details=["Key findings", "Contributions to the field", "Gaps remaining"],
    )


@pytest.fixture
def summary_config() -> SummaryConfig:
    return SummaryConfig(model=ModelConfig(id="claude-sonnet-4-6", max_tokens=8000, effort="low"))


def _write_pdf(tmp_path: Path, raw: bytes = b"%PDF-fake-bytes") -> Path:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(raw)
    return pdf


def _write_midsize_pdf(tmp_path: Path, name: str = "paper.pdf") -> Path:
    """A PDF above the small-PDF fast-path but under the inline cap.

    Forces the token-budget gate (count_tokens) to actually run -- the fast path
    skips it for trivially small PDFs.
    """
    pdf = tmp_path / name
    size = _SMALL_PDF_FAST_PATH_BYTES + 4096
    pdf.write_bytes(b"%PDF-" + b"x" * size)
    return pdf


# --------------------------------------------------------------------------- #
# Prompt composition: the steering profile shows up in the user turn.
# --------------------------------------------------------------------------- #


def test_context_prompt_carries_research_steering(
    research_profile: ResearchProfile, output_profile: OutputProfile
) -> None:
    prompt = build_context_prompt(research_profile, output_profile)
    # field / document type / topic / focus all present
    assert "a machine learning researcher" in prompt  # lower-cased in the article clause
    assert "from outside Machine Learning" in prompt  # original case in the framing clause
    assert "a literature review" in prompt
    assert research_profile.research_topic in prompt
    assert research_profile.research_focus in prompt
    # interests + return details rendered as bullets
    assert "- Zero-shot classification" in prompt
    assert "- Key findings" in prompt
    # ends pointing at the document
    assert prompt.rstrip().endswith("The paper is attached below.")


def test_context_prompt_uses_an_for_vowel_field(output_profile: OutputProfile) -> None:
    anth = ResearchProfile(
        name="harriet",
        research_field="Anthropology",
        research_topic="Indigenous studies",
        research_interests=[],
        research_focus="land-based education",
    )
    prompt = build_context_prompt(anth, output_profile)
    assert "an anthropology researcher" in prompt


def test_context_prompt_drops_empty_lists(research_profile: ResearchProfile) -> None:
    op = OutputProfile(name="bare", document_type="Report", return_details=[])
    rp = research_profile.model_copy(update={"research_interests": []})
    prompt = build_context_prompt(rp, op)
    # no stray bullets, no "topics I care about" / "especially looking for" blocks
    assert "The topics I care about most are:" not in prompt
    assert "I am especially looking for:" not in prompt
    assert "\n- " not in prompt


def test_system_prompt_is_frozen_and_versioned() -> None:
    # The system prompt must not be parameterised by any reader (cache stability).
    assert "luke" not in SUMMARY_SYSTEM_PROMPT.lower()
    assert "relevance_to_profile" in SUMMARY_SYSTEM_PROMPT  # names the schema field
    assert PROMPT_VERSION == "summary-v1"


# --------------------------------------------------------------------------- #
# The fake satisfies the LLMClient port contract.
# --------------------------------------------------------------------------- #


def test_fake_satisfies_llmclient_protocol() -> None:
    fake = FakeLLMClient()
    assert isinstance(fake, LLMClient)


def test_fake_returns_validated_schema_instance() -> None:
    fake = FakeLLMClient()
    result = fake.complete_structured(
        document=LLMDocument.from_text("body"),
        system="sys",
        instruction="do it",
        schema=PaperSummary,
        max_tokens=8000,
        effort="low",
    )
    assert isinstance(result, PaperSummary)
    assert result.key_findings  # at least one


# --------------------------------------------------------------------------- #
# Structured-output validation: provenance is stamped, content is validated.
# --------------------------------------------------------------------------- #


def test_summary_is_validated_and_provenance_stamped(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_pdf(tmp_path)
    fake = FakeLLMClient()
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")

    summary = stage.run(pdf, research_profile, output_profile, summary_config)

    assert isinstance(summary, PaperSummary)
    # provenance set by the pipeline (not the model)
    assert summary.model == "claude-sonnet-4-6"
    assert summary.prompt_version == summary_config.prompt_version
    assert summary.input_hash == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert summary.profile_hash  # non-empty


def test_native_pdf_is_the_default_path(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_pdf(tmp_path)
    fake = FakeLLMClient()  # token_count=100, comfortably under budget
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")
    stage.run(pdf, research_profile, output_profile, summary_config)

    assert fake.call_count == 1
    call = fake.calls[0]
    assert call.document.is_pdf  # native PDF, not text
    assert call.system == SUMMARY_SYSTEM_PROMPT
    # steering carried into the instruction
    assert research_profile.research_focus in call.instruction


# --------------------------------------------------------------------------- #
# Result cache: miss then hit, force bypass, key sensitivity.
# --------------------------------------------------------------------------- #


def test_cache_miss_then_hit(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_pdf(tmp_path)
    fake = FakeLLMClient()
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")

    first = stage.run(pdf, research_profile, output_profile, summary_config)
    assert fake.call_count == 1
    second = stage.run(pdf, research_profile, output_profile, summary_config)
    assert fake.call_count == 1  # hit -> no second LLM call
    assert second == first


def test_force_bypasses_cache(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_pdf(tmp_path)
    fake = FakeLLMClient()
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")

    stage.run(pdf, research_profile, output_profile, summary_config)
    stage.run(pdf, research_profile, output_profile, summary_config, force=True)
    assert fake.call_count == 2  # re-summarised despite the sidecar


def test_cache_key_changes_with_profile(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_pdf(tmp_path)
    fake = FakeLLMClient()
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")

    stage.run(pdf, research_profile, output_profile, summary_config)
    other = research_profile.model_copy(update={"research_focus": "a completely different focus"})
    stage.run(pdf, other, output_profile, summary_config)
    assert fake.call_count == 2  # different profile_hash -> different key -> miss


def test_cache_key_changes_with_prompt_version(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_pdf(tmp_path)
    fake = FakeLLMClient()
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")

    stage.run(pdf, research_profile, output_profile, summary_config)
    bumped = summary_config.model_copy(update={"prompt_version": "summary-v2"})
    stage.run(pdf, research_profile, output_profile, bumped)
    assert fake.call_count == 2


def test_corrupt_cache_treated_as_miss(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_pdf(tmp_path)
    fake = FakeLLMClient()
    cache_dir = tmp_path / "cache"
    stage = SummariseStage(fake, cache_dir=cache_dir)
    # warm the cache, then corrupt the sidecar
    stage.run(pdf, research_profile, output_profile, summary_config)
    sidecar = next((cache_dir / "summaries").glob("*.json"))
    sidecar.write_text("{ not valid json", encoding="utf-8")
    stage.run(pdf, research_profile, output_profile, summary_config)
    assert fake.call_count == 2  # corrupt -> miss -> re-summarised


# --------------------------------------------------------------------------- #
# Long-input machinery: text fallback + section-split + truncation retry.
# --------------------------------------------------------------------------- #


class _FakeExtractor:
    """A minimal PdfExtractor fake returning canned long text."""

    def __init__(self, text: str) -> None:
        self._text = text

    def extract(self, pdf_path: Path):  # type: ignore[no-untyped-def]
        from downlow.domain.schemas import ExtractedText

        return ExtractedText(
            full_text=self._text,
            pages=[self._text],
            page_count=1,
            is_scanned=False,
            source_hash=hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            content_hash=hashlib.sha256(self._text.encode("utf-8")).hexdigest(),
        )


def test_over_budget_pdf_falls_back_to_text(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_midsize_pdf(tmp_path)
    long_text = "Section A.\n\nSection B with content."

    # PDF over budget, extracted text under budget.
    def tokens(doc: LLMDocument) -> int:
        return 500_000 if doc.is_pdf else 100

    fake = FakeLLMClient(token_count=tokens)
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache", extractor=_FakeExtractor(long_text))

    summary = stage.run(pdf, research_profile, output_profile, summary_config)
    # one completion, on the TEXT document (fallback)
    assert fake.call_count == 1
    assert not fake.calls[0].document.is_pdf
    # input_hash is the text content_hash on the fallback path
    assert summary.input_hash == hashlib.sha256(long_text.encode("utf-8")).hexdigest()


def test_over_budget_pdf_without_extractor_raises(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_midsize_pdf(tmp_path)
    fake = FakeLLMClient(token_count=500_000)  # always over budget
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache", extractor=None)

    with pytest.raises(LLMError, match="native-PDF input budget"):
        stage.run(pdf, research_profile, output_profile, summary_config)


def test_section_split_when_text_also_over_budget(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_midsize_pdf(tmp_path)
    long_text = "First section of the paper.\n\nSecond section of the paper.\n\nThird section here."
    fake = FakeLLMClient(token_count=500_000)  # PDF and full text both over budget
    stage = SummariseStage(
        fake,
        cache_dir=tmp_path / "cache",
        extractor=_FakeExtractor(long_text),
        input_budget_tokens=1000,
    )

    summary = stage.run(pdf, research_profile, output_profile, summary_config)
    # sections summarised + a reduce call -> more than one completion
    assert fake.call_count >= 2
    # all section calls are on text documents
    assert all(not c.document.is_pdf for c in fake.calls)
    assert isinstance(summary, PaperSummary)


def test_truncation_then_retry_on_text(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_midsize_pdf(tmp_path)
    splittable = "Part one of the document.\n\nPart two of the document."
    # First call truncates; the text splits in half and both halves succeed, then reduce.
    fake = FakeLLMClient(truncate_first_n=1)
    stage = SummariseStage(
        fake,
        cache_dir=tmp_path / "cache",
        extractor=_FakeExtractor(splittable),
        input_budget_tokens=1,  # force the text/section path so we have a text doc to split
    )
    # token_count default 100 > budget 1 -> text fallback path, on a splittable doc
    summary = stage.run(pdf, research_profile, output_profile, summary_config)
    assert isinstance(summary, PaperSummary)
    # truncate(1) + two halves + reduce = at least 4 calls
    assert fake.call_count >= 3


def test_truncation_on_native_pdf_raises(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_pdf(tmp_path)
    # PDF under budget (single native call) but the model truncates -> cannot split a PDF.
    fake = FakeLLMClient(truncate_first_n=1, token_count=100)
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")
    with pytest.raises(TruncatedResponseError):
        stage.run(pdf, research_profile, output_profile, summary_config)


# --------------------------------------------------------------------------- #
# Config-file layer: profiles loaded from config; overrides; errors.
# --------------------------------------------------------------------------- #


def test_load_config_seeds_default_profile() -> None:
    cfg = load_config(CONFIG_TOML)
    assert cfg.research_profile.name == "luke"
    assert cfg.research_profile.research_field == "Machine Learning"
    assert "Multimodal models" in cfg.research_profile.research_interests
    assert cfg.output_profile.document_type == "Literature Review"
    assert cfg.summary.model.id == "claude-sonnet-4-6"
    assert cfg.summary.model.effort == "low"
    assert cfg.summary.prompt_version == PROMPT_VERSION


def test_load_config_research_override() -> None:
    cfg = load_config(CONFIG_TOML, research_override="harriet")
    assert cfg.research_profile.name == "harriet"
    assert cfg.research_profile.research_field == "Anthropology"


def test_load_config_unknown_profile_raises() -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(CONFIG_TOML, research_override="nobody")


def test_load_config_exposes_all_profiles() -> None:
    cfg = load_config(CONFIG_TOML)
    assert set(cfg.research_profiles) >= {"luke", "mehrnia", "harriet"}


# --------------------------------------------------------------------------- #
# Golden snapshot: a recorded PaperSummary fixture round-trips + drives the stage.
# --------------------------------------------------------------------------- #


def test_recorded_fixture_is_a_valid_paper_summary() -> None:
    raw = (FIXTURES_DIR / "paper_summary.json").read_text(encoding="utf-8")
    summary = PaperSummary.model_validate_json(raw)
    assert summary.title.startswith("Contrastive Pretraining")
    assert len(summary.key_findings) == 3
    assert summary.key_findings[2].evidence is None  # qualitative finding -> None


def test_golden_summary_through_stage(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    recorded = PaperSummary.model_validate_json((FIXTURES_DIR / "paper_summary.json").read_text(encoding="utf-8"))
    fake = FakeLLMClient(result=recorded)
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")
    pdf = _write_pdf(tmp_path)

    summary = stage.run(pdf, research_profile, output_profile, summary_config)
    # content carried through verbatim
    assert summary.title == recorded.title
    assert [f.statement for f in summary.key_findings] == [f.statement for f in recorded.key_findings]
    # provenance stamped on top of the recorded content
    assert summary.model == "claude-sonnet-4-6"
    assert summary.prompt_version == PROMPT_VERSION

    # the sidecar JSON is a stable, re-loadable snapshot
    sidecar = next((tmp_path / "cache" / "summaries").glob("*.json"))
    reloaded = PaperSummary.model_validate_json(sidecar.read_text(encoding="utf-8"))
    assert reloaded == summary
    # deterministic JSON serialisation (sorted nothing, but stable structure)
    assert json.loads(sidecar.read_text(encoding="utf-8"))["title"] == recorded.title


# --------------------------------------------------------------------------- #
# Quality-band gate: schema-valid but degenerate summaries are rejected.
# --------------------------------------------------------------------------- #


def _degenerate(*, findings: list[KeyFinding], overall: str) -> PaperSummary:
    return PaperSummary(
        title="A Paper",
        overall_summary=overall,
        key_findings=findings,
        contributions=["x"],
        methods="m",
        gaps_and_limitations=["g"],
        relevance_to_profile="r",
    )


def test_quality_gate_rejects_empty_findings(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    bad = _degenerate(findings=[], overall="word " * 60)
    fake = FakeLLMClient(result=bad)
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")
    with pytest.raises(SummaryQualityError, match="no key findings"):
        stage.run(_write_pdf(tmp_path), research_profile, output_profile, summary_config)
    # a degenerate summary is never cached
    assert not list((tmp_path / "cache" / "summaries").glob("*.json"))


def test_quality_gate_rejects_too_short_overall(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    bad = _degenerate(findings=[KeyFinding(statement="s")], overall="just three words")
    fake = FakeLLMClient(result=bad)
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")
    with pytest.raises(SummaryQualityError, match="overall_summary is only"):
        stage.run(_write_pdf(tmp_path), research_profile, output_profile, summary_config)


def test_quality_gate_passes_default_summary(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    # the default fake summary clears the bar (>=1 finding, long overall_summary)
    fake = FakeLLMClient()
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")
    summary = stage.run(_write_pdf(tmp_path), research_profile, output_profile, summary_config)
    assert summary.key_findings
    assert len(summary.overall_summary.split()) >= 40


# --------------------------------------------------------------------------- #
# Inline-size guard + small-PDF fast path.
# --------------------------------------------------------------------------- #


def test_small_pdf_skips_token_count_and_inlines(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = _write_pdf(tmp_path)  # tiny, under the fast-path threshold
    fake = FakeLLMClient()
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache")
    stage.run(pdf, research_profile, output_profile, summary_config)
    # fast path: native PDF used, count_tokens NOT called
    assert fake.calls[0].document.is_pdf
    assert fake.count_token_calls == []


def test_oversize_pdf_never_inlined_falls_back_to_text(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    # A PDF over the inline cap must take the text fallback regardless of tokens.
    pdf = tmp_path / "huge.pdf"
    pdf.write_bytes(b"%PDF-" + b"x" * (_MAX_INLINE_PDF_BYTES + 1))
    long_text = "Body of the paper that is small once extracted."
    fake = FakeLLMClient()  # token_count default 100, well under budget
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache", extractor=_FakeExtractor(long_text))

    summary = stage.run(pdf, research_profile, output_profile, summary_config)
    # text fallback, never a native PDF call; count_tokens not needed to decide
    # (size guard short-circuits before the budget check)
    assert not fake.calls[0].document.is_pdf
    assert summary.input_hash == hashlib.sha256(long_text.encode("utf-8")).hexdigest()


def test_oversize_pdf_without_extractor_raises(
    tmp_path: Path,
    research_profile: ResearchProfile,
    output_profile: OutputProfile,
    summary_config: SummaryConfig,
) -> None:
    pdf = tmp_path / "huge.pdf"
    pdf.write_bytes(b"%PDF-" + b"x" * (_MAX_INLINE_PDF_BYTES + 1))
    fake = FakeLLMClient()
    stage = SummariseStage(fake, cache_dir=tmp_path / "cache", extractor=None)
    with pytest.raises(LLMError, match="native-PDF input budget"):
        stage.run(pdf, research_profile, output_profile, summary_config)


# --------------------------------------------------------------------------- #
# Adapter: Opus reasoning-leak guard (no network; inspects the thinking param).
# --------------------------------------------------------------------------- #


def test_adapter_forces_thinking_on_opus() -> None:
    from downlow.adapters.llm.anthropic_client import AnthropicLLMClient

    opus = AnthropicLLMClient(api_key="test-key", model="claude-opus-4-8")
    sonnet = AnthropicLLMClient(api_key="test-key", model="claude-sonnet-4-6")
    assert opus._thinking_param() == {"type": "adaptive"}
    assert sonnet._thinking_param() is None
