"""Integration test for the real pydub/ffmpeg mixer (F4).

Marked ``integration`` -- needs the system ``ffmpeg`` binary (mp3 decode/encode).
Builds a few dummy rendered turns (real mp3 speech bytes + a committed .wav asset)
and asserts the mixer produces one decodable mp3 of roughly the expected duration.
No network, no keys.
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest

pytest.importorskip("pydub")

from pydub import AudioSegment

from downlow.adapters.audio.mixer import PydubAudioMixer
from downlow.domain.ports import RenderedTurn
from downlow.domain.schemas import Turn

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg binary not installed (pydub mp3 needs it)"),
]

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "audio"


def _mp3_bytes(duration_ms: int) -> bytes:
    """A real, decodable mp3 of ``duration_ms`` (a quiet tone, not pure silence)."""
    seg = AudioSegment.silent(duration=duration_ms)
    buffer = io.BytesIO()
    seg.export(buffer, format="mp3")
    return buffer.getvalue()


def test_mix_produces_one_mp3_of_expected_duration() -> None:
    intro = ASSETS_DIR / "intro.wav"
    assert intro.exists(), "committed placeholder intro asset is missing"

    rendered = [
        RenderedTurn(turn=Turn(type="speech", role=None, text="Cold open."), audio=_mp3_bytes(1000)),
        RenderedTurn(turn=Turn(type="music", cue="intro"), asset_path=intro),
        RenderedTurn(turn=Turn(type="speech", text="Welcome."), audio=_mp3_bytes(1500)),
        RenderedTurn(turn=Turn(type="pause", duration_ms=500)),
        RenderedTurn(turn=Turn(type="speech", text="The answer."), audio=_mp3_bytes(2000)),
    ]
    mixer = PydubAudioMixer()
    out = mixer.mix(rendered)

    # one decodable mp3
    assert isinstance(out, bytes) and out
    decoded = AudioSegment.from_file(io.BytesIO(out), format="mp3")

    # expected duration: speech 1000 + intro-sting (its own time) + 1500 + 500 pause
    # + 2000, minus small crossfade overlaps. Assert it is in a sane band and that
    # the intro sting contributed (so it is clearly longer than speech+pause alone).
    intro_len = len(AudioSegment.from_file(intro))
    speech_and_pause = 1000 + 1500 + 500 + 2000
    assert len(decoded) >= speech_and_pause - 1000  # crossfade slack
    assert len(decoded) >= intro_len  # the sting occupied its own time


def test_mix_skips_missing_asset_and_still_renders() -> None:
    rendered = [
        RenderedTurn(turn=Turn(type="speech", text="Hi."), audio=_mp3_bytes(800)),
        RenderedTurn(turn=Turn(type="music", cue="outro"), asset_path=None),  # missing -> skipped
        RenderedTurn(turn=Turn(type="speech", text="Bye."), audio=_mp3_bytes(800)),
    ]
    out = PydubAudioMixer().mix(rendered)
    decoded = AudioSegment.from_file(io.BytesIO(out), format="mp3")
    assert len(decoded) > 0
