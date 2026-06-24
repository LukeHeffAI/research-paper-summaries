"""Port Protocols — the contracts every adapter implements.

PURE: stdlib + pydantic + ``domain`` only. Core depends on these Protocols and
never on a concrete adapter or third-party SDK; adapters implement them; tests
inject fakes. This is the seam that keeps ``core`` provider-agnostic and lets a
future FastAPI layer call core services unchanged.

Phase 1 (F1) defines ``PdfExtractor``. The remaining ports named in the plan
(``LLMClient``, ``TTSClient``, ``ReportRenderer``, ``AudioMixer``,
``ArtifactStore``, ``Repository``, ``Clock``) are defined alongside the features
that introduce them (F2-F5 / STORE).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from downlow.domain.schemas import ExtractedText


@runtime_checkable
class PdfExtractor(Protocol):
    """Extracts normalised text + content hashes from a source PDF.

    Implemented by ``adapters.pdf.extractor.PdfPlumberExtractor`` (the only place
    ``pdfplumber`` is imported); a swap to PyMuPDF / pypdfium2 later is a
    one-class change behind this port.

    Contract:

    * ``extract`` reads ``pdf_path`` and returns a populated :class:`ExtractedText`
      with both ``source_hash`` (of the raw bytes) and ``content_hash`` (of the
      normalised text) set.
    * It raises :class:`downlow.domain.errors.EmptyExtractionError` when the PDF
      yields effectively no extractable text (scanned / image-only). It never
      returns empty or garbage text and never silently truncates.
    """

    def extract(self, pdf_path: Path) -> ExtractedText:
        """Extract and normalise the text of ``pdf_path``."""
        ...
