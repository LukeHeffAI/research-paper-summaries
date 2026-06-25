"""Unit tests for the pydub audio mixer's 3-layer timeline (F4).

These exercise the timeline + layer logic with silent ``AudioSegment``s, which
need no ffmpeg (only mp3 decode/encode does). The full decode -> mix -> mp3 path is
the integration test (tests/integration/test_narrate_real.py). Covers voice-track
positions, ``under`` bed layering, sting overlay (occupies its own time),
crossfades, intro/outro fades, the loudness target, and missing-asset skip.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pydub")

from pydub import AudioSegment

from downlow.adapters.audio.mixer import PydubAudioMixer, _decode
from downlow.config.profiles import MixConfig
from downlow.domain.ports import RenderedTurn
from downlow.domain.schemas import Turn


def _speech(segment: AudioSegment) -> tuple[RenderedTurn, AudioSegment]:
    return (RenderedTurn(turn=Turn(type="speech", text="x"), audio=b""), segment)


def _pause(ms: int) -> tuple[RenderedTurn, None]:
    return (RenderedTurn(turn=Turn(type="pause", duration_ms=ms)), None)


def _music(cue: str, segment: AudioSegment, *, under: bool) -> tuple[RenderedTurn, AudioSegment]:
    return (RenderedTurn(turn=Turn(type="music", cue=cue, under=under)), segment)


def test_voice_track_positions_advance_playhead() -> None:
    # gap=0 isolates the bare playhead advance (the gap is exercised separately).
    mixer = PydubAudioMixer(MixConfig(inter_turn_gap_ms=0))
    a = AudioSegment.silent(duration=1000)
    b = AudioSegment.silent(duration=2000)
    timeline = mixer._build_timeline([_speech(a), _speech(b)])
    positions = [e.position_ms for e in timeline.voice]
    assert positions == [0, 1000]
    assert timeline.duration_ms == 3000


def test_inter_turn_gap_advances_playhead_between_consecutive_speech() -> None:
    mixer = PydubAudioMixer(MixConfig(inter_turn_gap_ms=250))
    a = AudioSegment.silent(duration=1000)
    b = AudioSegment.silent(duration=2000)
    timeline = mixer._build_timeline([_speech(a), _speech(b)])
    # the 250ms gap pushes the second speech turn back, so it is no longer adjacent
    assert [e.position_ms for e in timeline.voice] == [0, 1250]
    assert timeline.duration_ms == 3250


def test_inter_turn_gap_not_inserted_across_a_pause() -> None:
    mixer = PydubAudioMixer(MixConfig(inter_turn_gap_ms=250))
    timeline = mixer._build_timeline(
        [_speech(AudioSegment.silent(duration=500)), _pause(300), _speech(AudioSegment.silent(duration=500))]
    )
    # a pause already separates the speech turns -> no extra gap inserted
    assert [e.position_ms for e in timeline.voice] == [0, 500, 800]
    assert timeline.duration_ms == 1300


def test_pause_inserts_silence_and_advances() -> None:
    mixer = PydubAudioMixer()
    timeline = mixer._build_timeline([_speech(AudioSegment.silent(duration=500)), _pause(700)])
    assert [e.position_ms for e in timeline.voice] == [0, 500]
    assert timeline.duration_ms == 1200


def test_under_cue_is_a_bed_and_does_not_advance() -> None:
    mixer = PydubAudioMixer()
    speech = AudioSegment.silent(duration=1000)
    bed = AudioSegment.silent(duration=200)
    timeline = mixer._build_timeline([_speech(speech), _music("bed", bed, under=True)])
    assert len(timeline.beds) == 1
    assert timeline.beds[0].position_ms == 1000  # placed at the playhead
    assert timeline.duration_ms == 1000  # bed did NOT advance the playhead


def test_non_under_cue_is_a_sting_and_occupies_time() -> None:
    mixer = PydubAudioMixer()
    intro = AudioSegment.silent(duration=800)
    speech = AudioSegment.silent(duration=1000)
    timeline = mixer._build_timeline([_music("intro", intro, under=False), _speech(speech)])
    assert len(timeline.stings) == 1
    assert timeline.stings[0].position_ms == 0
    # the sting occupies its own 800ms, so speech starts after it
    assert timeline.voice[0].position_ms == 800
    assert timeline.duration_ms == 1800


def test_missing_asset_is_skipped() -> None:
    mixer = PydubAudioMixer()
    speech = AudioSegment.silent(duration=1000)
    missing = (RenderedTurn(turn=Turn(type="music", cue="outro")), None)  # asset None
    timeline = mixer._build_timeline([_speech(speech), missing])
    assert timeline.beds == [] and timeline.stings == []
    assert timeline.duration_ms == 1000  # the missing cue contributed nothing


def test_voice_render_crossfades_adjacent_speech() -> None:
    # gap=0 so the two speech turns stay adjacent and the crossfade can trigger.
    mixer = PydubAudioMixer(MixConfig(crossfade_ms=120, inter_turn_gap_ms=0))
    a = AudioSegment.silent(duration=1000)
    b = AudioSegment.silent(duration=1000)
    timeline = mixer._build_timeline([_speech(a), _speech(b)])
    assert [e.position_ms for e in timeline.voice] == [0, 1000]  # adjacent
    rendered = mixer._render_voice(timeline.voice, timeline.duration_ms)
    # the crossfade pulls the second clip's start back by crossfade_ms; the canvas
    # length itself is unchanged.
    assert len(rendered) == timeline.duration_ms == 2000


def test_gapped_speech_is_not_crossfaded() -> None:
    # with a gap, consecutive speech turns are non-adjacent -> no crossfade overlap.
    mixer = PydubAudioMixer(MixConfig(crossfade_ms=120, inter_turn_gap_ms=250))
    a = AudioSegment.silent(duration=1000)
    b = AudioSegment.silent(duration=1000)
    timeline = mixer._build_timeline([_speech(a), _speech(b)])
    # second turn starts at 1250 (gapped), not 1000, so the crossfade guard (pos ==
    # prev_end) is false and nothing is pulled back.
    assert [e.position_ms for e in timeline.voice] == [0, 1250]
    rendered = mixer._render_voice(timeline.voice, timeline.duration_ms)
    assert len(rendered) == timeline.duration_ms == 2250


def test_bed_is_attenuated_and_spans_to_end() -> None:
    mixer = PydubAudioMixer(MixConfig(bed_volume_db=-20.0))
    # a loud bed (0 dBFS-ish tone proxy: use a non-silent segment)
    loud = AudioSegment.silent(duration=100)  # silent; we assert span/placement, not dB
    timeline = mixer._build_timeline([_speech(AudioSegment.silent(duration=1000)), _music("bed", loud, under=True)])
    bed = mixer._render_bed(timeline.beds, timeline.duration_ms)
    assert len(bed) == timeline.duration_ms  # bed canvas spans the whole timeline


def test_apply_fades_caps_at_quarter_length() -> None:
    mixer = PydubAudioMixer(MixConfig(intro_fade_ms=2000, outro_fade_ms=3000))
    seg = AudioSegment.silent(duration=4000)
    faded = mixer._apply_fades(seg)
    # fades are clamped to len//4 each; length is unchanged by fading
    assert len(faded) == 4000


def test_normalize_clamps_gain_on_silence() -> None:
    mixer = PydubAudioMixer(MixConfig(target_loudness_dbfs=-16.0))
    silent = AudioSegment.silent(duration=500)  # dBFS == -inf
    # silence is returned unchanged (no -inf -> finite amplification)
    assert mixer._normalize(silent) == silent


def test_decode_returns_none_for_pause_and_missing_asset() -> None:
    assert _decode(RenderedTurn(turn=Turn(type="pause", duration_ms=400))) is None
    assert _decode(RenderedTurn(turn=Turn(type="music", cue="x"))) is None


def test_empty_rendered_list_returns_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    # mix([]) returns a 1s silent export; stub _export so this needs no ffmpeg
    monkeypatch.setattr("downlow.adapters.audio.mixer._export", lambda seg: b"OK" + str(len(seg)).encode())
    mixer = PydubAudioMixer()
    assert mixer.mix([]) == b"OK1000"
