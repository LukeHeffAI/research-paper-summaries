"""Unit tests for the ElevenLabs TTS adapter (F4).

No network, no key: the SDK client is replaced with a fake that records calls and
can be told to fail. Covers per-turn synth (bytes out), the preset -> voice_settings
mapping, and the retry/backoff (retryable vs non-retryable, Retry-After honoured).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from downlow.adapters.tts.elevenlabs_client import (
    _VOICE_PRESETS,
    ElevenLabsTTSClient,
    _is_retryable,
    _retry_after,
)
from downlow.domain.errors import TTSError
from downlow.domain.ports import TTSClient


@dataclass
class _Convert:
    voice_id: str
    text: str
    model_id: str
    output_format: str
    voice_settings: dict[str, float]


class _FakeTextToSpeech:
    def __init__(self, fail_times: int = 0, exc: Exception | None = None) -> None:
        self.calls: list[_Convert] = []
        self._fail_times = fail_times
        self._exc = exc or _http_error(429)

    def convert(self, **kwargs: Any) -> Iterator[bytes]:
        self.calls.append(_Convert(**kwargs))
        if self._fail_times > 0:
            self._fail_times -= 1
            raise self._exc
        return iter([b"chunk1", b"chunk2"])


@dataclass
class _FakeSdk:
    text_to_speech: _FakeTextToSpeech = field(default_factory=_FakeTextToSpeech)


def _http_error(status: int, retry_after: str | None = None) -> Exception:
    exc = RuntimeError(f"http {status}")
    exc.status_code = status  # type: ignore[attr-defined]
    if retry_after is not None:
        exc.headers = {"Retry-After": retry_after}  # type: ignore[attr-defined]
    return exc


def _client(sdk: _FakeSdk, **kwargs: Any) -> ElevenLabsTTSClient:
    client = ElevenLabsTTSClient(api_key="test-key", **kwargs)
    client._client = sdk  # type: ignore[assignment]
    return client


def test_adapter_satisfies_port() -> None:
    assert isinstance(ElevenLabsTTSClient(api_key="k"), TTSClient)


def test_synthesize_returns_joined_bytes() -> None:
    sdk = _FakeSdk()
    client = _client(sdk)
    audio = client.synthesize(text="hello", voice_id="v1", preset="warm")
    assert audio == b"chunk1chunk2"
    assert len(sdk.text_to_speech.calls) == 1
    call = sdk.text_to_speech.calls[0]
    assert call.voice_id == "v1"
    assert call.text == "hello"


def test_preset_maps_to_voice_settings() -> None:
    sdk = _FakeSdk()
    client = _client(sdk)
    client.synthesize(text="hi", voice_id="v", preset="excited")
    assert sdk.text_to_speech.calls[0].voice_settings == _VOICE_PRESETS["excited"]


def test_unknown_preset_falls_back_to_measured() -> None:
    sdk = _FakeSdk()
    client = _client(sdk)
    client.synthesize(text="hi", voice_id="v", preset="nonsense")
    assert sdk.text_to_speech.calls[0].voice_settings == _VOICE_PRESETS["measured"]


def test_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("downlow.adapters.tts.elevenlabs_client.time.sleep", lambda _s: None)
    sdk = _FakeSdk(text_to_speech=_FakeTextToSpeech(fail_times=2, exc=_http_error(429)))
    client = _client(sdk, max_retries=3)
    audio = client.synthesize(text="hi", voice_id="v", preset="warm")
    assert audio == b"chunk1chunk2"
    assert len(sdk.text_to_speech.calls) == 3  # 2 failures + 1 success


def test_retries_exhausted_raises_tts_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("downlow.adapters.tts.elevenlabs_client.time.sleep", lambda _s: None)
    sdk = _FakeSdk(text_to_speech=_FakeTextToSpeech(fail_times=99, exc=_http_error(429)))
    client = _client(sdk, max_retries=2)
    with pytest.raises(TTSError) as exc_info:
        client.synthesize(text="hi", voice_id="v", preset="warm")
    assert exc_info.value.status_code == 429
    assert len(sdk.text_to_speech.calls) == 3  # initial + 2 retries


def test_non_retryable_error_raises_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("downlow.adapters.tts.elevenlabs_client.time.sleep", lambda _s: None)
    sdk = _FakeSdk(text_to_speech=_FakeTextToSpeech(fail_times=99, exc=_http_error(400)))
    client = _client(sdk, max_retries=3)
    with pytest.raises(TTSError):
        client.synthesize(text="hi", voice_id="v", preset="warm")
    assert len(sdk.text_to_speech.calls) == 1  # 400 is not retried


def test_is_retryable_classifies_status() -> None:
    assert _is_retryable(_http_error(429)) is True
    assert _is_retryable(_http_error(503)) is True
    assert _is_retryable(_http_error(400)) is False
    assert _is_retryable(RuntimeError("no status")) is False


def test_retry_after_parsed_from_headers() -> None:
    assert _retry_after(_http_error(429, retry_after="7")) == 7.0
    assert _retry_after(_http_error(429)) is None
    assert _retry_after(RuntimeError("plain")) is None
