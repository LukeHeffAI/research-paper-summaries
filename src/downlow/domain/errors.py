"""Typed domain errors.

Pure: stdlib only. Adapters and core raise these so callers can distinguish a
recoverable, well-understood failure (e.g. a scanned PDF with no text layer)
from an unexpected crash. Keeping them in ``domain`` means every layer can
``except`` them without importing a third-party SDK.
"""

from __future__ import annotations


class DownLowError(Exception):
    """Base class for all DownLow domain errors.

    Catch this to handle any *expected*, modelled failure of the pipeline while
    letting genuinely unexpected exceptions propagate.
    """


class EmptyExtractionError(DownLowError):
    """Raised by INGEST when a PDF yields effectively no extractable text.

    Typically a scanned / image-only PDF with no text layer. The stage raises
    this rather than feeding empty or garbage text to SUMMARISE. OCR is a future
    INGEST sub-stage; for now the paper should be flagged ``needs_ocr`` upstream.
    """

    def __init__(self, message: str = "PDF yielded no extractable text", *, page_count: int | None = None) -> None:
        self.page_count = page_count
        super().__init__(message)
