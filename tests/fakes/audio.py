"""A fake :class:`AudioMixer` for ``core`` NARRATE tests.

Implements the same port Protocol the real ``PydubAudioMixer`` does, so the
NARRATE stage runs with no ``pydub`` / ffmpeg. Records the rendered turns it was
handed (so tests can assert on speech audio, resolved asset paths, and turn order)
and returns deterministic dummy mp3 bytes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from downlow.domain.ports import RenderedTurn


@dataclass
class FakeAudioMixer:
    """Deterministic in-memory ``AudioMixer`` that records what it mixed."""

    received: list[list[RenderedTurn]] = field(default_factory=list)

    @property
    def last(self) -> list[RenderedTurn]:
        """The most recently mixed rendered-turn list (for assertions)."""
        return self.received[-1]

    def mix(self, rendered: list[RenderedTurn]) -> bytes:
        """Record the rendered turns and return dummy mixed bytes."""
        self.received.append(rendered)
        return b"FAKEMIX" + str(len(rendered)).encode()
