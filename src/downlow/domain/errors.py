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


class TTSError(DownLowError):
    """Raised when a text-to-speech synthesis call fails in a modelled way.

    The :class:`~downlow.domain.ports.TTSClient` port maps a provider's
    rate-limit / transport / quota failures onto this provider-agnostic error so
    ``core`` can ``except`` it without importing the ``elevenlabs`` SDK. The adapter
    is the only layer that knows the provider's exception types; everything it
    cannot recover from after its own retry/backoff surfaces here.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class NarrationQualityError(DownLowError):
    """Raised when a structurally-valid narration script fails the quality gate.

    The structured-output schema guarantees *shape* (the right turn fields) but not
    *substance*: a model can return an empty ``turns`` list, speech turns with no
    text, or a host that monologues (the asymmetry collapsed). NARRATE runs cheap
    deterministic checks (>=1 speech turn per role, non-empty speech text, the host
    a minority of the spoken words) and raises this rather than synthesising and
    caching a degenerate episode.
    """


class SummaryQualityError(DownLowError):
    """Raised when a structurally-valid summary fails the quality-band gate.

    The structured-output schema guarantees *shape* (the right fields, right
    types) but not *substance*: a model can return an empty ``key_findings`` list
    or a one-sentence ``overall_summary`` that parses cleanly yet fails the F2
    quality bar. SUMMARISE runs cheap deterministic checks (>=1 finding, a sensible
    word floor on the overall summary) and raises this rather than caching and
    serving a degenerate summary downstream.
    """
