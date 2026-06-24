"""A spy fake for the :class:`PdfExtractor` port.

Used by the INGEST cache tests to assert *whether* the extractor was invoked
(cache miss) or skipped (cache hit), without touching ``pdfplumber`` or a real
file. It implements the port's contract and records its call count.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from downlow.domain.schemas import ExtractedText


class FakePdfExtractor:
    """Deterministic in-memory ``PdfExtractor`` that counts its invocations."""

    def __init__(self, result: ExtractedText | None = None) -> None:
        self._result = result
        self.calls: list[Path] = []

    @property
    def call_count(self) -> int:
        """How many times :meth:`extract` has been called."""
        return len(self.calls)

    def extract(self, pdf_path: Path) -> ExtractedText:
        """Record the call and return a canned (or hash-derived) result."""
        self.calls.append(pdf_path)
        if self._result is not None:
            return self._result
        # Derive a deterministic result from the path so distinct PDFs differ.
        raw = pdf_path.read_bytes()
        source_hash = hashlib.sha256(raw).hexdigest()
        text = f"fake text for {pdf_path.name}"
        return ExtractedText(
            full_text=text,
            pages=[text],
            page_count=1,
            is_scanned=False,
            source_hash=source_hash,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
