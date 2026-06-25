"""A fake :class:`TTSClient` for ``core`` NARRATE tests.

Implements the same port Protocol the real ``ElevenLabsTTSClient`` does, so the
NARRATE stage runs with no network, no key, and deterministic output. Returns
dummy bytes derived from ``(text, voice_id, preset)`` so a cache hit (same key)
returns identical bytes and a spy can assert which turns actually hit the provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256


@dataclass
class _SynthCall:
    text: str
    voice_id: str
    preset: str


@dataclass
class FakeTTSClient:
    """Deterministic in-memory ``TTSClient`` with spying + optional failure."""

    calls: list[_SynthCall] = field(default_factory=list)
    fail_with: Exception | None = None

    @property
    def call_count(self) -> int:
        """How many ``synthesize`` calls reached the provider (cache misses)."""
        return len(self.calls)

    def synthesize(self, *, text: str, voice_id: str, preset: str) -> bytes:
        """Record the call and return deterministic dummy 'mp3' bytes for the key."""
        self.calls.append(_SynthCall(text=text, voice_id=voice_id, preset=preset))
        if self.fail_with is not None:
            raise self.fail_with
        digest = sha256(f"{text}|{voice_id}|{preset}".encode()).digest()
        # A stable, key-dependent payload; not a real mp3 (the mixer is faked too).
        return b"FAKEMP3" + digest
