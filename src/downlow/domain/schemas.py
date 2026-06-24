"""Pydantic DTOs that flow between pipeline stages.

PURE: pydantic only — no third-party SDK imports, no SQLModel ``table=True``.
DB rows live in ``adapters/db/tables.py``; these are the wire/domain objects.

Phase 1 (F1) defines ``ExtractedText``; F2 adds ``PaperSummary`` (+ ``KeyFinding``)
and the steering context (``ResearchProfile`` + ``OutputProfile``). Later phases
add ``NarrationScript`` (turns), ``RenderedReport``, ``PodcastAsset``.

**Structured-output note (F2).** ``KeyFinding`` / ``PaperSummary`` are the target
schema for Claude's native structured output (``messages.parse``). The Claude
structured-output JSON-schema subset forbids numeric/length constraints and
requires ``additionalProperties: false`` (the SDK strips unsupported keywords and
re-validates client-side, but we keep the *model* free of ``min_length`` /
``ge`` / ``le`` on model-populated fields so the generated schema is accepted
unchanged). Quality bands (word count, >=1 finding) are asserted as a *gate*
in the SUMMARISE stage, not encoded as schema constraints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedText(BaseModel):
    """The output of the INGEST stage: normalised text + per-page text + hashes.

    Paper-agnostic by design — extraction does not know which ``Paper`` it
    belongs to. The Paper linkage happens later at the STORE stage, which records
    ``source_hash`` on the Paper row and the artifact reference.

    Two hashes, two jobs:

    * ``source_hash`` = ``sha256(raw_pdf_bytes)`` — known *before* extraction, so
      a re-added identical PDF skips re-extraction (the extraction cache key).
    * ``content_hash`` = ``sha256(normalised_text)`` — known only *after*
      extraction + normalisation, and stable across cosmetically-different
      extractions of the same paper; everything downstream is keyed by it.
    """

    full_text: str = Field(description="The normalised, whole-document text (pages joined).")
    pages: list[str] = Field(description="Per-page normalised text, in document order.")
    page_count: int = Field(ge=0, description="Number of pages in the source PDF.")
    is_scanned: bool = Field(
        default=False,
        description="True when text is suspiciously sparse relative to page_count (likely image-only / needs OCR).",
    )
    source_hash: str = Field(description="sha256 hex digest of the raw PDF bytes (extraction-cache key).")
    content_hash: str = Field(description="sha256 hex digest of the normalised full_text (downstream-cache key).")


# --------------------------------------------------------------------------- #
# Steering context (F2) — replaces legacy data/research_data.json +            #
# data/document_data.json. Pure pydantic; loaded from the config file for now  #
# (DB-backed ResearchProfile/OutputProfile tables are a later phase).          #
# --------------------------------------------------------------------------- #


class ResearchProfile(BaseModel):
    """The reader's research identity — steers *emphasis* and *relevance*.

    Composed into the cacheable steering prompt (``build_context_prompt``). One
    active profile per user steers summarisation. The fields mirror the legacy
    ``ResearchContext`` (``data/research_data.json``) so existing profiles port
    over verbatim.
    """

    name: str = Field(description="A short identifier for this profile (e.g. the user's name).")
    research_field: str = Field(description="The reader's discipline, e.g. 'Machine Learning'.")
    research_topic: str = Field(description="The general subject of the reader's research.")
    research_interests: list[str] = Field(
        default_factory=list,
        description="Specific topics the reader cares about; used to focus emphasis.",
    )
    research_focus: str = Field(description="The reader's specific aim; what 'relevance' should connect to.")


class OutputProfile(BaseModel):
    """What the summary should surface — the document-shape steering (DocumentContext).

    Kept separate from :class:`ResearchProfile` because the output format and the
    researcher identity vary independently (one researcher, many output formats).
    Mirrors the legacy ``DocumentContext`` (``data/document_data.json``).
    """

    name: str = Field(description="A short identifier for this output profile.")
    document_type: str = Field(description="The kind of document being written, e.g. 'Literature Review'.")
    return_details: list[str] = Field(
        default_factory=list,
        description="The specific things the summary should surface (the legacy document_return_details).",
    )


# --------------------------------------------------------------------------- #
# SUMMARISE output (F2).                                                       #
# --------------------------------------------------------------------------- #


class KeyFinding(BaseModel):
    """A single concrete, falsifiable result the paper *showed*.

    ``evidence`` carries the supporting metric / detail when the paper reports one
    (an effect size, an accuracy delta, the regime it holds in); ``None`` when the
    finding is qualitative. Per the advisor's fidelity bar, ``evidence`` must trace
    to the source — it is never invented.
    """

    statement: str = Field(description="The finding itself: what the authors showed, with hedging preserved.")
    evidence: str | None = Field(
        default=None,
        description="Supporting metric/detail from the paper (number, effect size, condition); None if qualitative.",
    )


class PaperSummary(BaseModel):
    """The validated output of the SUMMARISE stage (F2).

    The model populates the *content* fields; the SUMMARISE pipeline stamps the
    *provenance* fields (it never trusts the model for those). Structured so RENDER
    (Typst) and NARRATE (interview script) consume typed data, not a text blob.

    The content fields and their ordering encode the advisor's summary structure
    (overall -> key findings -> contributions -> methods -> gaps -> relevance) and
    fidelity bar (faithful emphasis, preserved hedging, no fabrication).
    """

    # --- model-populated content ---
    title: str = Field(description="The paper's actual title, as extracted from the source.")
    overall_summary: str = Field(
        description="~300 words of prose: problem, approach, result, why it matters. No 'this paper presents' filler.",
    )
    key_findings: list[KeyFinding] = Field(
        default_factory=list,
        description="The concrete, falsifiable results the authors showed (at least one).",
    )
    contributions: list[str] = Field(
        default_factory=list,
        description="What is genuinely new vs prior work (a method, dataset, theoretical result, or observation).",
    )
    methods: str = Field(
        description="Enough of the study design/data/baselines/metric to judge credibility and transfer.",
    )
    gaps_and_limitations: list[str] = Field(
        default_factory=list,
        description="Honest limitations the authors state AND those a sharp reviewer would raise.",
    )
    relevance_to_profile: str = Field(
        description="Why this paper matters to THIS reader's stated focus (or an honest disconnect). Summariser-voice.",
    )

    # --- provenance (set by the SUMMARISE pipeline, never by the model) ---
    input_hash: str = Field(
        default="",
        description="source_hash (native-PDF path) or content_hash (text fallback) of the summarised input.",
    )
    profile_hash: str = Field(default="", description="Stable hash of the (research, output) steering profiles.")
    model: str = Field(default="", description="The Claude model id that produced this summary.")
    prompt_version: str = Field(default="", description="The PROMPT_VERSION of the system+steering prompt used.")
