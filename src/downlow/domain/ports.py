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
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

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


# --------------------------------------------------------------------------- #
# LLMClient (F2) — the structured-output completion port.                      #
# --------------------------------------------------------------------------- #

# The validated schema the model fills. Bound to BaseModel so the port returns a
# concrete, validated pydantic instance — no provider types leak to ``core``.
SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMDocument(BaseModel):
    """A provider-agnostic LLM input: either a native PDF document or plain text.

    This is the value object the :class:`LLMClient` accepts so neither ``core`` nor
    ``domain`` ever names an ``anthropic`` content-block shape. Exactly one of
    ``pdf_bytes`` or ``text`` is set:

    * ``pdf_bytes`` set -> the native-PDF path (the default): the adapter sends the
      bytes to Claude as a base64 ``document`` block (or via the Files API for
      large PDFs). ``media_type`` defaults to ``application/pdf``.
    * ``text`` set -> the provider-agnostic fallback path (F1's extracted text),
      used when the PDF exceeds the native-PDF limit or a non-PDF source is summarised.

    Construct via :meth:`from_pdf` / :meth:`from_text` so the invariant holds.
    """

    pdf_bytes: bytes | None = None
    text: str | None = None
    media_type: str = "application/pdf"

    @classmethod
    def from_pdf(cls, pdf_bytes: bytes, *, media_type: str = "application/pdf") -> LLMDocument:
        """A native-PDF input (the default summarise path)."""
        return cls(pdf_bytes=pdf_bytes, text=None, media_type=media_type)

    @classmethod
    def from_text(cls, text: str) -> LLMDocument:
        """A plain-text input (the provider-agnostic fallback path)."""
        return cls(pdf_bytes=None, text=text)

    @property
    def is_pdf(self) -> bool:
        """True for the native-PDF path."""
        return self.pdf_bytes is not None


@runtime_checkable
class LLMClient(Protocol):
    """A structured-output LLM completion, provider-agnostic.

    The default backend is ``adapters.llm.anthropic_client.AnthropicLLMClient`` (the
    only place ``anthropic`` is imported); ``tests.fakes.llm.FakeLLMClient`` is what
    every ``core`` test uses. No provider types appear in this contract.

    Contract for :meth:`complete_structured`:

    * accepts a single :class:`LLMDocument` (native PDF by default, or text) placed
      before the instruction, a stable ``system`` prompt, the target pydantic
      ``schema`` class, and ``max_tokens``/``effort`` budgets;
    * returns a *validated* instance of ``schema`` (the model's structured output);
    * streams internally when the output may be large (large ``max_tokens``), using
      the SDK's stream + final-message helper so it never trips the non-streaming
      timeout guard;
    * raises :class:`downlow.domain.errors.TruncatedResponseError` when the model
      stops at ``max_tokens`` (the schema parsing cannot save a cut-off response);
    * raises :class:`downlow.domain.errors.LLMError` for refusals and other
      modelled provider failures, after the SDK's own retry/backoff is exhausted.

    The implementation owns prompt caching of the frozen ``system`` + schema prefix.
    """

    def complete_structured(
        self,
        *,
        document: LLMDocument,
        system: str,
        instruction: str,
        schema: type[SchemaT],
        max_tokens: int,
        effort: str,
    ) -> SchemaT:
        """Complete ``document`` into a validated ``schema`` instance."""
        ...

    def count_tokens(self, *, document: LLMDocument, system: str, instruction: str) -> int:
        """Estimate the input-token count for a would-be request (budget check).

        Uses the provider's token counter (never ``len()``/``tiktoken``). The count
        is model-specific, so the implementation pins its own model — callers
        recompute if the model flips (e.g. Sonnet <-> Opus).
        """
        ...
