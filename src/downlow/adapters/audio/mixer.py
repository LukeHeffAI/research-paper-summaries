"""``PydubAudioMixer`` -- the :class:`AudioMixer` port via ``pydub`` + ffmpeg.

This is the ONLY module allowed to import ``pydub`` / shell out to ``ffmpeg``.
Everything it knows about audio rendering is confined here; ``core``/``domain`` see
only the provider-agnostic :class:`~downlow.domain.ports.AudioMixer` contract and
the :class:`~downlow.domain.ports.RenderedTurn` value object.

A near-wholesale rip of VTTD's ``audio_mixer.py`` (pure ``pydub``), retargeted from
the horror NARRATION/DIALOGUE/SFX/AMBIENT/PAUSE segment model to our multi-speaker
``Turn`` model with music. The 3-layer timeline (docs/podcast_design.md section 6):

* **Voice track** (foundation): ``speech`` + ``pause`` turns advance the playhead;
  consecutive speech turns are crossfaded (``crossfade_ms``).
* **Music/ambient bed** (underneath, low dB): ``under=True`` cues are looped to fill
  their span and fade between sections; they do not advance the playhead.
* **SFX / sting layer** (overlay): non-``under`` cues are placed at their timeline
  position with brief in/out fades; they occupy their own time.

Then intro fade-in, outro fade-out, and a peak-based loudness normalise to a target
dBFS. A missing asset is already resolved to ``asset_path=None`` upstream, so the
mixer simply skips that cue -- the episode still renders. The mix constants come
from :class:`~downlow.config.profiles.MixConfig`.

The source is pure ASCII.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field

from pydub import AudioSegment

from downlow.config.profiles import MixConfig
from downlow.domain.ports import RenderedTurn

logger = logging.getLogger(__name__)

# Per-section bed fade-ins/outs and sfx edge fades (fixed; the tunable dB/fade
# values live in MixConfig). These cap the fade at half the span so a short clip
# is not all-fade.
_BED_FADE_IN_MS = 1500
_BED_FADE_OUT_MS = 1000
_SFX_FADE_IN_MS = 50
_SFX_FADE_OUT_MS = 200

# Clamp on the loudness adjustment so a near-silent mix is not amplified to noise.
_MAX_GAIN_DB = 12.0


@dataclass
class _Entry:
    """A positioned piece of audio on the mix timeline."""

    audio: AudioSegment
    position_ms: int
    is_speech: bool = False


@dataclass
class _Timeline:
    """The three layers collected before rendering."""

    voice: list[_Entry] = field(default_factory=list)
    beds: list[_Entry] = field(default_factory=list)
    stings: list[_Entry] = field(default_factory=list)
    duration_ms: int = 0


class PydubAudioMixer:
    """``AudioMixer`` backed by ``pydub`` (needs the system ``ffmpeg`` binary)."""

    def __init__(self, mix: MixConfig | None = None) -> None:
        """Build the mixer with the given mix constants (defaults if omitted)."""
        self._mix = mix or MixConfig()

    def mix(self, rendered: list[RenderedTurn]) -> bytes:
        """Mix ``rendered`` turns into one finished episode (mp3 bytes)."""
        if not rendered:
            return _export(AudioSegment.silent(duration=1000))

        decoded = [(item, _decode(item)) for item in rendered]
        timeline = self._build_timeline(decoded)
        mixed = self._render(timeline)
        mixed = self._apply_fades(mixed)
        mixed = self._normalize(mixed)
        logger.info(
            "mix complete: %dms, %d voice, %d sting, %d bed",
            len(mixed),
            len(timeline.voice),
            len(timeline.stings),
            len(timeline.beds),
        )
        return _export(mixed)

    # --- timeline construction ---------------------------------------------- #

    def _build_timeline(self, decoded: list[tuple[RenderedTurn, AudioSegment | None]]) -> _Timeline:
        """Walk decoded turns in order, placing each on the right layer.

        Takes ``(turn, segment)`` pairs (decoding is done up front in :meth:`mix`,
        so the timeline logic itself is pure ``pydub`` and unit-testable with silent
        segments). Speech and pause advance the playhead. Non-``under`` cues
        (stings) occupy their own time and advance it; ``under`` cues (beds) layer
        underneath and do not advance it. A turn whose segment is ``None`` (a missing
        asset, or speech with no audio) is skipped.

        A configured ``inter_turn_gap_ms`` of silence is inserted between two
        *consecutive* speech turns (a natural turn-taking beat). Because the gap
        makes the turns non-adjacent, the crossfade in :meth:`_render_voice` simply
        will not trigger across a gapped boundary -- the two compose cleanly.
        """
        timeline = _Timeline()
        playhead = 0
        prev_was_speech = False
        for item, segment in decoded:
            turn = item.turn
            if turn.type == "speech":
                if segment is None:
                    continue
                if prev_was_speech and self._mix.inter_turn_gap_ms > 0:
                    playhead += self._mix.inter_turn_gap_ms
                timeline.voice.append(_Entry(audio=segment, position_ms=playhead, is_speech=True))
                playhead += len(segment)
                prev_was_speech = True
            elif turn.type == "pause":
                duration = turn.duration_ms or 500
                silence = AudioSegment.silent(duration=duration)
                timeline.voice.append(_Entry(audio=silence, position_ms=playhead, is_speech=False))
                playhead += duration
                prev_was_speech = False
            elif turn.type in ("music", "sfx"):
                if segment is None:
                    continue
                if turn.under:
                    timeline.beds.append(_Entry(audio=segment, position_ms=playhead))
                else:
                    timeline.stings.append(_Entry(audio=segment, position_ms=playhead))
                    playhead += len(segment)
                    prev_was_speech = False
        timeline.duration_ms = max(playhead, 1)
        return timeline

    # --- rendering ----------------------------------------------------------- #

    def _render(self, timeline: _Timeline) -> AudioSegment:
        """Render the three layers into one segment: bed under voice, stings over."""
        duration = timeline.duration_ms
        voice = self._render_voice(timeline.voice, duration)
        bed = self._render_bed(timeline.beds, duration)
        stings = self._render_stings(timeline.stings, duration)
        mixed = bed.overlay(voice)
        mixed = mixed.overlay(stings)
        return mixed

    def _render_voice(self, entries: list[_Entry], duration_ms: int) -> AudioSegment:
        """Lay voice + pause onto a silent canvas, crossfading consecutive speech."""
        canvas = AudioSegment.silent(duration=duration_ms)
        prev_end: int | None = None
        prev_speech = False
        for entry in entries:
            pos = entry.position_ms
            if entry.is_speech and prev_speech and prev_end is not None and pos == prev_end:
                fade = min(self._mix.crossfade_ms, len(entry.audio) // 2)
                if fade > 0:
                    pos = max(0, pos - fade)
            canvas = canvas.overlay(entry.audio, position=pos)
            prev_end = pos + len(entry.audio)
            prev_speech = entry.is_speech
        return canvas

    def _render_bed(self, entries: list[_Entry], duration_ms: int) -> AudioSegment:
        """Build a continuous bed: each cue runs until the next bed (or the end).

        Looped to fill its span, attenuated to ``bed_volume_db``, faded in (and out
        if a later bed supersedes it). Beds do not advance the playhead, so they
        layer beneath the voice track.
        """
        bed = AudioSegment.silent(duration=duration_ms)
        if not entries:
            return bed
        for i, entry in enumerate(entries):
            start = entry.position_ms
            end = entries[i + 1].position_ms if i + 1 < len(entries) else duration_ms
            span = end - start
            if span <= 0:
                continue
            clip = entry.audio
            if len(clip) < span:
                repeats = (span // len(clip)) + 1
                clip = clip * repeats
            clip = clip[:span] + self._mix.bed_volume_db
            clip = clip.fade_in(min(_BED_FADE_IN_MS, span // 2))
            if i + 1 < len(entries):
                clip = clip.fade_out(min(_BED_FADE_OUT_MS, span // 2))
            bed = bed.overlay(clip, position=start)
        return bed

    def _render_stings(self, entries: list[_Entry], duration_ms: int) -> AudioSegment:
        """Place sting/sfx cues at their positions with brief edge fades."""
        layer = AudioSegment.silent(duration=duration_ms)
        for entry in entries:
            sting = entry.audio + self._mix.sting_volume_db
            sting = sting.fade_in(min(_SFX_FADE_IN_MS, len(sting) // 4))
            sting = sting.fade_out(min(_SFX_FADE_OUT_MS, len(sting) // 4))
            layer = layer.overlay(sting, position=entry.position_ms)
        return layer

    # --- post-processing ----------------------------------------------------- #

    def _apply_fades(self, mixed: AudioSegment) -> AudioSegment:
        """Apply the intro fade-in and outro fade-out to the whole mix."""
        intro = min(self._mix.intro_fade_ms, len(mixed) // 4)
        if intro > 0:
            mixed = mixed.fade_in(intro)
        outro = min(self._mix.outro_fade_ms, len(mixed) // 4)
        if outro > 0:
            mixed = mixed.fade_out(outro)
        return mixed

    def _normalize(self, mixed: AudioSegment) -> AudioSegment:
        """Peak-based loudness normalise toward the target dBFS (clamped gain)."""
        if mixed.dBFS == float("-inf"):
            return mixed
        delta = self._mix.target_loudness_dbfs - mixed.dBFS
        delta = max(-_MAX_GAIN_DB, min(_MAX_GAIN_DB, delta))
        return mixed + delta


def _decode(item: RenderedTurn) -> AudioSegment | None:
    """Decode a rendered turn's audio into an ``AudioSegment``, or ``None``.

    Speech turns carry mp3 ``bytes``; music/sfx turns carry an on-disk
    ``asset_path`` (format inferred from the suffix). A turn with neither (a pause,
    or a missing/unmapped cue) returns ``None`` -- the timeline handles silence /
    skipping. Decoding here keeps :meth:`PydubAudioMixer._build_timeline` free of IO
    so the timeline logic is unit-testable with silent segments.
    """
    if item.audio is not None:
        return AudioSegment.from_file(io.BytesIO(item.audio), format="mp3")
    if item.asset_path is not None:
        return AudioSegment.from_file(str(item.asset_path))
    return None


def _export(segment: AudioSegment) -> bytes:
    """Encode an ``AudioSegment`` to mp3 ``bytes``."""
    buffer = io.BytesIO()
    segment.export(buffer, format="mp3")
    return buffer.getvalue()
