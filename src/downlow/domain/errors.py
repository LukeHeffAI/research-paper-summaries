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


class LLMError(DownLowError):
    """Raised when an LLM call fails in a modelled, expected way.

    The :class:`LLMClient` port maps a provider's structured-output, refusal, or
    transport failures onto this provider-agnostic error so ``core`` can ``except``
    it without importing the ``anthropic`` SDK. The adapter is the only layer that
    knows about ``RateLimitError`` / ``APIStatusError`` and friends; everything it
    cannot recover from surfaces here.
    """

    def __init__(self, message: str, *, request_id: str | None = None, stop_reason: str | None = None) -> None:
        self.request_id = request_id
        self.stop_reason = stop_reason
        super().__init__(message)


class TruncatedResponseError(LLMError):
    """Raised when the model stopped because it hit ``max_tokens``.

    A truncated response cannot be trusted even when the structured-output schema
    parses (the JSON may be cut off mid-value, or whole required sections missing).
    SUMMARISE's long-input machinery catches this to recursively split-and-retry;
    a single-call path surfaces it so the caller can raise ``max_tokens``. Mirrors
    the legacy "never silently accept a cut-off response" guard.
    """

    def __init__(
        self, message: str = "model response truncated at max_tokens", *, request_id: str | None = None
    ) -> None:
        super().__init__(message, request_id=request_id, stop_reason="max_tokens")
