"""``ElevenLabsTTSClient`` -- the :class:`TTSClient` port via the official SDK.

This is the ONLY module allowed to import ``elevenlabs``. Everything it knows
about the ElevenLabs API is confined here; ``core``/``domain`` see only the
provider-agnostic :class:`~downlow.domain.ports.TTSClient` contract and the
:class:`~downlow.domain.errors.TTSError` exception.

Modernises VTTD's raw ``requests`` POST to the official ``elevenlabs`` Python SDK
(typed, streaming, and the voice-cloning API for Phase 7). Per-turn synthesis:

* ``synthesize`` converts one turn's text in one voice with one preset and returns
  the mp3 ``bytes`` (the SDK ``convert`` returns a byte-chunk iterator; we join it);
* the ``tone -> preset`` mapping is done in ``core`` (config-driven); this adapter
  owns only the ``preset -> ElevenLabs voice_settings`` table (``stability`` /
  ``similarity_boost`` / ``style``);
* retry/backoff: on a rate-limit / transient error we sleep with exponential
  backoff + jitter, honouring a ``Retry-After`` header when present, then re-raise
  as :class:`TTSError` once retries are exhausted.

Unicode is built with ``chr()`` where needed so the source stays pure ASCII.
"""

from __future__ import annotations

import random
import time
from typing import Any

from elevenlabs.client import ElevenLabs

from downlow.domain.errors import TTSError

# ElevenLabs model id for TTS. Multilingual v2 is the broad-quality default; a
# future config knob can flip this without touching ``core``.
_MODEL_ID = "eleven_multilingual_v2"
_OUTPUT_FORMAT = "mp3_44100_128"

# Our preset names -> ElevenLabs voice settings. Lower stability = more emotional
# range; higher style = more pronounced delivery. These map the docs/podcast_design
# presets (warm/curious/measured/excited/serious) to concrete knobs; the unknown
# fallback is the neutral "measured" profile.
_VOICE_PRESETS: dict[str, dict[str, float]] = {
    "warm": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.35},
    "curious": {"stability": 0.45, "similarity_boost": 0.75, "style": 0.45},
    "measured": {"stability": 0.65, "similarity_boost": 0.75, "style": 0.20},
    "excited": {"stability": 0.40, "similarity_boost": 0.70, "style": 0.55},
    "serious": {"stability": 0.70, "similarity_boost": 0.75, "style": 0.25},
}
_DEFAULT_PRESET = "measured"


class ElevenLabsTTSClient:
    """``TTSClient`` backed by the official ``elevenlabs`` SDK."""

    def __init__(
        self,
        *,
        api_key: str,
        model_id: str = _MODEL_ID,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ) -> None:
        """Build the client.

        Args:
            api_key: the ElevenLabs API key (validated at the composition root).
            model_id: the ElevenLabs TTS model id.
            max_retries: retries for rate-limit / transient failures.
            base_delay: initial backoff (seconds); doubled each retry.
            max_delay: backoff ceiling (seconds).
        """
        self._client = ElevenLabs(api_key=api_key)
        self._model_id = model_id
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay

    def synthesize(self, *, text: str, voice_id: str, preset: str) -> bytes:
        """Synthesise ``text`` in ``voice_id`` with ``preset`` -> mp3 bytes."""
        settings = _VOICE_PRESETS.get(preset, _VOICE_PRESETS[_DEFAULT_PRESET])
        attempt = 0
        while True:
            try:
                stream = self._client.text_to_speech.convert(
                    voice_id=voice_id,
                    text=text,
                    model_id=self._model_id,
                    output_format=_OUTPUT_FORMAT,
                    voice_settings=settings,
                )
                return b"".join(stream)
            except Exception as exc:
                attempt += 1
                if attempt > self._max_retries or not _is_retryable(exc):
                    raise TTSError(
                        f"ElevenLabs synthesis failed for voice {voice_id}: {exc}",
                        status_code=_status_code(exc),
                    ) from exc
                time.sleep(self._backoff(attempt, exc))

    def _backoff(self, attempt: int, exc: Exception) -> float:
        """Backoff for ``attempt``: honour Retry-After, else exponential + jitter."""
        retry_after = _retry_after(exc)
        if retry_after is not None:
            return min(retry_after, self._max_delay)
        delay: float = min(self._base_delay * (2.0 ** (attempt - 1)), self._max_delay)
        return delay + random.uniform(0, self._base_delay)


def _status_code(exc: Exception) -> int | None:
    """Best-effort HTTP status from an SDK exception."""
    code = getattr(exc, "status_code", None)
    return code if isinstance(code, int) else None


def _is_retryable(exc: Exception) -> bool:
    """True for rate-limit (429) and server (>=500) errors -- the retryable class."""
    code = _status_code(exc)
    if code is None:
        return False
    return code == 429 or code >= 500


def _retry_after(exc: Exception) -> float | None:
    """Parse a ``Retry-After`` seconds value from the exception's headers, if any."""
    headers = getattr(exc, "headers", None) or _response_headers(exc)
    if not headers:
        return None
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _response_headers(exc: Exception) -> Any:
    """Best-effort headers off a nested response object on the exception."""
    response = getattr(exc, "response", None)
    return getattr(response, "headers", None)
