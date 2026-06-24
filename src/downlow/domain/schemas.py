"""Pydantic DTOs that flow between pipeline stages.

PURE: pydantic only — no third-party SDK imports, no SQLModel ``table=True``.
DB rows live in ``adapters/db/tables.py``; these are the wire/domain objects.

Phase 1 (F1) defines ``ExtractedText``. Later phases add ``PaperSummary``,
``NarrationScript`` (turns), ``RenderedReport``, ``PodcastAsset``.
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
