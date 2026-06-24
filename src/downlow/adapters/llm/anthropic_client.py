"""``AnthropicLLMClient`` -- the :class:`LLMClient` port via the official SDK.

This is the ONLY module allowed to import ``anthropic``. Everything it knows about
the Claude API is confined here; ``core``/``domain`` see only the provider-agnostic
:class:`~downlow.domain.ports.LLMClient` contract and the
:class:`~downlow.domain.errors.LLMError` / ``TruncatedResponseError`` exceptions.

Confirmed against the ``claude-api`` skill (Anthropic SDK):

* **Structured output** -- ``client.messages.parse(output_format=Schema, ...)`` ->
  ``.parsed_output`` is a validated pydantic instance; the streaming path uses
  ``output_config={"format": {"type": "json_schema", "schema": ...}}`` and
  validates the final text.
* **Native PDF** -- a base64 ``document`` content block placed *before* the text
  block; base64 with no newlines; 32 MB / 600-page limit (100 on 200K-context
  models). For PDFs over a size threshold we upload via the Files API
  (``files-api-2025-04-14``) and reference by ``file_id`` so repeated stages reuse
  one upload.
* **Streaming** -- large ``max_tokens`` non-streaming raises ``ValueError`` (the
  SDK's >~10-min guard), so we stream via ``messages.stream().get_final_message()``
  above a threshold.
* **Truncation** -- ``stop_reason == "max_tokens"`` -> ``TruncatedResponseError``.
* **Thinking/effort** -- adaptive thinking only (``{"type": "adaptive"}``) +
  ``output_config.effort``; never ``budget_tokens`` / ``temperature`` (400 on
  current models). For straightforward summarisation, thinking is omitted (cheaper).
* **Prompt caching** -- ``cache_control={"type": "ephemeral"}`` on the frozen
  ``system`` block so the stable prefix amortises; min cacheable prefix is 2048
  tokens for Sonnet 4.6 (caching silently no-ops below it).
* **Token counting** -- ``client.messages.count_tokens(model=...)`` (never
  ``len()`` / ``tiktoken``); model-specific.
* **Errors** -- typed-exception chain (``RateLimitError`` -> ``APIStatusError`` ->
  ``APIConnectionError``), most-specific first; the SDK's own retry/backoff runs
  underneath (``max_retries``). ``_request_id`` is logged onto the raised error.

Unicode is built with ``chr()`` where needed so the source stays pure ASCII.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any, TypeVar, cast

import anthropic
from pydantic import BaseModel

from downlow.domain.errors import LLMError, TruncatedResponseError
from downlow.domain.ports import LLMDocument

if TYPE_CHECKING:
    from anthropic.types import MessageParam

SchemaT = TypeVar("SchemaT", bound=BaseModel)

# Above this max_tokens we must stream: a non-streaming request the SDK estimates
# will exceed ~10 min raises ValueError at call time. 16000 is the skill's
# non-streaming ceiling.
_STREAM_THRESHOLD_TOKENS = 16_000

# PDFs at or above this size are uploaded via the Files API and referenced by
# file_id (so summarise + narrate reuse one upload) rather than inlined as base64.
# Comfortably under the 32 MB request limit; small PDFs stay inline (one fewer
# round trip).
_FILES_API_THRESHOLD_BYTES = 4 * 1024 * 1024

_FILES_API_BETA = "files-api-2025-04-14"


class AnthropicLLMClient:
    """``LLMClient`` backed by the official ``anthropic`` SDK."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        max_retries: int = 2,
        timeout: float = 600.0,
    ) -> None:
        """Build the client.

        Args:
            api_key: the Anthropic API key (validated at the composition root).
            model: the default Claude model id (bare, no date suffix).
            max_retries: SDK retry count (retries 408/409/429/5xx + connection
                errors + timeouts with exponential backoff). Bump for batch runs.
            timeout: per-request timeout in seconds.
        """
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=max_retries, timeout=timeout)
        self._model = model

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
        content, file_id = self._build_user_content(document, instruction)
        system_blocks = self._cacheable_system(system)
        try:
            if max_tokens > _STREAM_THRESHOLD_TOKENS:
                return self._complete_streaming(
                    content=content,
                    system_blocks=system_blocks,
                    schema=schema,
                    max_tokens=max_tokens,
                    effort=effort,
                    uses_files_api=file_id is not None,
                )
            return self._complete_nonstreaming(
                content=content,
                system_blocks=system_blocks,
                schema=schema,
                max_tokens=max_tokens,
                effort=effort,
                uses_files_api=file_id is not None,
            )
        except anthropic.RateLimitError as exc:
            raise LLMError("rate limited by the Anthropic API", request_id=_req_id(exc)) from exc
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Anthropic API error ({exc.status_code})", request_id=_req_id(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("could not reach the Anthropic API", request_id=_req_id(exc)) from exc

    def count_tokens(self, *, document: LLMDocument, system: str, instruction: str) -> int:
        """Estimate the input-token count for a would-be request (budget check)."""
        content, _ = self._build_user_content(document, instruction)
        messages: list[MessageParam] = [{"role": "user", "content": cast(Any, content)}]
        try:
            resp = self._client.messages.count_tokens(
                model=self._model,
                system=cast(Any, self._cacheable_system(system)),
                messages=messages,
            )
        except anthropic.APIStatusError as exc:
            raise LLMError(f"token counting failed ({exc.status_code})", request_id=_req_id(exc)) from exc
        return resp.input_tokens

    # --- request construction ------------------------------------------------ #

    def _cacheable_system(self, system: str) -> list[dict[str, Any]]:
        """The frozen system prompt as a single cache-controlled text block.

        The breakpoint on the last (only) system block caches the stable prefix so
        it amortises across papers; below the per-model minimum (2048 tokens for
        Sonnet 4.6) caching silently no-ops -- a test asserts a real hit.
        """
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    def _build_user_content(self, document: LLMDocument, instruction: str) -> tuple[list[dict[str, Any]], str | None]:
        """Build the user-turn content blocks: document first, then instruction.

        Returns the content list and the Files API ``file_id`` if one was created
        (so the caller knows the request needs the Files beta header).
        """
        if not document.is_pdf:
            text = document.text or ""
            return [{"type": "text", "text": f"{instruction}\n\n{text}"}], None

        assert document.pdf_bytes is not None  # is_pdf guarantees this
        if len(document.pdf_bytes) >= _FILES_API_THRESHOLD_BYTES:
            file_id = self._upload_pdf(document.pdf_bytes)
            doc_block: dict[str, Any] = {"type": "document", "source": {"type": "file", "file_id": file_id}}
            return [doc_block, {"type": "text", "text": instruction}], file_id

        b64 = base64.standard_b64encode(document.pdf_bytes).decode("ascii")  # no newlines
        inline_block: dict[str, Any] = {
            "type": "document",
            "source": {"type": "base64", "media_type": document.media_type, "data": b64},
        }
        return [inline_block, {"type": "text", "text": instruction}], None

    def _upload_pdf(self, pdf_bytes: bytes) -> str:
        """Upload a large PDF via the Files API; return the file_id."""
        uploaded = self._client.beta.files.upload(
            file=("paper.pdf", pdf_bytes, "application/pdf"),
        )
        return uploaded.id

    # --- completion paths ---------------------------------------------------- #

    def _complete_nonstreaming(
        self,
        *,
        content: list[dict[str, Any]],
        system_blocks: list[dict[str, Any]],
        schema: type[SchemaT],
        max_tokens: int,
        effort: str,
        uses_files_api: bool,
    ) -> SchemaT:
        """Small-output path: ``messages.parse`` -> validated ``parsed_output``."""
        messages: list[MessageParam] = [{"role": "user", "content": cast(Any, content)}]
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system_blocks,
            "messages": messages,
            "output_format": schema,
            "output_config": {"effort": effort},
        }
        if uses_files_api:
            kwargs["betas"] = [_FILES_API_BETA]
        response = self._client.messages.parse(**kwargs)
        self._guard_stop_reason(response)
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError("Anthropic returned no parsed output", request_id=_req_id_msg(response))
        return cast(SchemaT, parsed)

    def _complete_streaming(
        self,
        *,
        content: list[dict[str, Any]],
        system_blocks: list[dict[str, Any]],
        schema: type[SchemaT],
        max_tokens: int,
        effort: str,
        uses_files_api: bool,
    ) -> SchemaT:
        """Large-output path: stream + ``get_final_message()``, then validate JSON.

        Streaming avoids the SDK's non-streaming >~10-min ValueError guard. The
        ``output_config.format`` schema constrains the output; we validate the
        final text against ``schema`` ourselves (the streaming helper does not
        expose ``parsed_output``).
        """
        messages: list[MessageParam] = [{"role": "user", "content": cast(Any, content)}]
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system_blocks,
            "messages": messages,
            "output_config": {"effort": effort, "format": _json_schema_format(schema)},
        }
        if uses_files_api:
            kwargs["betas"] = [_FILES_API_BETA]
        with self._client.messages.stream(**kwargs) as stream:
            response = stream.get_final_message()
        self._guard_stop_reason(response)
        text = _first_text(response)
        return schema.model_validate_json(text)

    @staticmethod
    def _guard_stop_reason(response: Any) -> None:
        """Raise on a truncated or refused response before reading content."""
        stop = getattr(response, "stop_reason", None)
        if stop == "max_tokens":
            raise TruncatedResponseError(request_id=_req_id_msg(response))
        if stop == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None)
            raise LLMError(
                f"Anthropic refused the request (category: {category})",
                request_id=_req_id_msg(response),
                stop_reason="refusal",
            )


def _json_schema_format(schema: type[BaseModel]) -> dict[str, Any]:
    """Build the ``output_config.format`` json_schema block from a pydantic model."""
    return {"type": "json_schema", "schema": schema.model_json_schema()}


def _first_text(response: Any) -> str:
    """Return the first text block's text from a Message (structured-output JSON)."""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            return str(block.text)
    raise LLMError("Anthropic response contained no text block", request_id=_req_id_msg(response))


def _req_id(exc: Any) -> str | None:
    """Best-effort request id from an SDK exception."""
    return getattr(exc, "request_id", None)


def _req_id_msg(response: Any) -> str | None:
    """Best-effort request id from a Message response (the public ``_request_id``)."""
    return getattr(response, "_request_id", None)
