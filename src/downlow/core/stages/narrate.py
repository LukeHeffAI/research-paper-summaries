"""NARRATE stage (F4): source -> two-presenter interview script -> mp3.

PURE orchestration: stdlib + ``domain`` (the ports + DTOs) + the config-file
*types* and the pure prompts module only. No ``anthropic`` / ``elevenlabs`` /
``pydub`` here -- the stage depends on the :class:`~downlow.domain.ports.LLMClient`,
:class:`~downlow.domain.ports.TTSClient`, :class:`~downlow.domain.ports.AudioMixer`,
and :class:`~downlow.domain.ports.PdfExtractor` *ports*, which adapters implement
and tests fake.

Flow (PROJECT_PLAN.md -> Stage 4 NARRATE; docs/podcast_design.md sections 5-6):

1. compute the script-cache key
   ``(input_hash, script_source, persona_version, prompt_version, model)`` and, on
   a hit (and not ``force``), load the stored :class:`NarrationScript`;
2. otherwise generate the script: whole paper by default (native PDF, reusing F2's
   section-split / truncation-retry), or the prior summary's text when
   ``script_source = "summary"``; gate it for substance; stamp provenance; cache;
3. merge consecutive same-speaker speech turns (VTTD ``_group_consecutive_segments``)
   for natural TTS flow;
4. synthesise each speech turn via the :class:`TTSClient` behind a per-segment cache
   keyed by ``(turn content, voice_id, preset)``; resolve music/sfx cues to assets;
5. mix the ordered rendered turns into one mp3 via the :class:`AudioMixer`.

The LLM machinery mirrors SUMMARISE so a long paper degrades the same way; it
rarely fires (Sonnet 4.6 has a 1M context).
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from downlow.config.profiles import NarrationConfig
from downlow.core.prompts.narration import (
    NARRATION_SYSTEM_PROMPT,
    build_narration_instruction,
    summary_to_document_text,
)
from downlow.core.stages.textsplit import split_text
from downlow.domain.enums import SpeakerRole
from downlow.domain.errors import LLMError, NarrationQualityError, TruncatedResponseError
from downlow.domain.ports import AudioMixer, LLMClient, LLMDocument, PdfExtractor, RenderedTurn, TTSClient
from downlow.domain.schemas import NarrationScript, PaperSummary, Turn

logger = logging.getLogger(__name__)

_SCRIPTS_SUBDIR = "narration"
_SEGMENTS_SUBDIR = "segments"

# Native-PDF token budget for the script call; mirrors SUMMARISE. Above it the
# stage falls back to extracted text + section-split. Generous (Sonnet 4.6 has a
# 1M context); the budget guards against a pathological PDF, not the common case.
_DEFAULT_INPUT_BUDGET_TOKENS = 180_000

# Raw-bytes cap for inlining a native PDF as base64 (the ~32 MB request limit minus
# the ~33% base64 inflation); a larger PDF takes the extracted-text fallback.
_MAX_INLINE_PDF_BYTES = 20 * 1024 * 1024

# Below this a native PDF is trivially under any budget, so we skip count_tokens.
_SMALL_PDF_FAST_PATH_BYTES = 2 * 1024 * 1024

# Recursive split cap for the truncation-retry path.
_MAX_SPLIT_ITERATIONS = 8

# Quality-band gate floors (deterministic, run before caching/synthesis). The
# schema guarantees shape; these guard substance. A script below these is a
# degenerate model output, not something to synthesise and serve.
_MIN_SPEECH_TURNS = 4
_MAX_HOST_WORD_SHARE = 0.5


class NarrateStage:
    """Orchestrates interview-script generation -> per-turn TTS -> one mixed mp3."""

    name = "narrate"

    def __init__(
        self,
        llm: LLMClient,
        tts: TTSClient,
        mixer: AudioMixer,
        cache_dir: Path,
        *,
        assets_dir: Path,
        extractor: PdfExtractor | None = None,
        input_budget_tokens: int = _DEFAULT_INPUT_BUDGET_TOKENS,
    ) -> None:
        """Wire the stage.

        Args:
            llm: the :class:`LLMClient` port (script generation).
            tts: the :class:`TTSClient` port (per-turn synthesis).
            mixer: the :class:`AudioMixer` port (final mix).
            cache_dir: the cache root (``<data_dir>/cache``); the stage owns the
                ``narration/`` (scripts) and ``segments/`` (per-turn TTS) subdirs.
            assets_dir: where music/sfx cue assets live
                (``<data_dir>/assets/audio``). A missing asset is skipped by the
                mixer, so the episode still renders.
            extractor: the :class:`PdfExtractor` port, used only on the over-budget
                fallback path. ``None`` disables the fallback.
            input_budget_tokens: native-PDF token budget above which the stage
                falls back to extracted text.
        """
        self._llm = llm
        self._tts = tts
        self._mixer = mixer
        self._scripts_dir = cache_dir / _SCRIPTS_SUBDIR
        self._segments_dir = cache_dir / _SEGMENTS_SUBDIR
        self._assets_dir = assets_dir
        self._extractor = extractor
        self._input_budget = input_budget_tokens

    def run(
        self,
        pdf_path: Path,
        cfg: NarrationConfig,
        *,
        summary: PaperSummary | None = None,
        force: bool = False,
    ) -> bytes:
        """Generate the episode mp3 for ``pdf_path`` under ``cfg``.

        Args:
            pdf_path: the source PDF (the script source on the default ``paper``
                path; still the input-hash anchor on the ``summary`` path).
            cfg: the resolved :class:`NarrationConfig` (model, prompt/persona
                versions, script_source, target_minutes, voices, presets, mix).
            summary: the prior :class:`PaperSummary`, required when
                ``cfg.script_source == "summary"`` (its text is the LLM input).
            force: bypass both caches (regenerate the script and re-synthesise).

        Returns:
            The finished episode as mp3 ``bytes``.

        Raises:
            LLMError: for refusals / over-budget-without-extractor / a missing
                summary on the summary path / an unmapped voice role.
            TruncatedResponseError: if the script is truncated and the long-input
                retry machinery cannot recover it.
            NarrationQualityError: if the generated script is degenerate.
        """
        script = self.generate_script(pdf_path, cfg, summary=summary, force=force)
        rendered = self._render_turns(script, cfg, force=force)
        return self._mixer.mix(rendered)

    # --- script generation (cached) ----------------------------------------- #

    def generate_script(
        self,
        pdf_path: Path,
        cfg: NarrationConfig,
        *,
        summary: PaperSummary | None = None,
        force: bool = False,
    ) -> NarrationScript:
        """Produce (or load from cache) the validated :class:`NarrationScript`.

        Separated from :meth:`run` so callers (and tests) can inspect the script
        without driving TTS + mix. Stamps provenance and writes the script sidecar.
        """
        instruction = build_narration_instruction(target_minutes=cfg.target_minutes, script_source=cfg.script_source)
        input_hash = self._source_hash(pdf_path)
        cache_path = self._script_cache_path(self._script_cache_key(input_hash=input_hash, cfg=cfg))

        if not force:
            cached = self._load_script_cache(cache_path)
            if cached is not None:
                return cached

        script, content_hash = self._generate(pdf_path, instruction, cfg, summary=summary)
        self._check_quality(script)

        script.paper_content_hashes = [content_hash]
        script.model = cfg.model.id
        script.prompt_version = cfg.prompt_version

        self._write_script_cache(cache_path, script)
        return script

    def _generate(
        self, pdf_path: Path, instruction: str, cfg: NarrationConfig, *, summary: PaperSummary | None
    ) -> tuple[NarrationScript, str]:
        """Produce a NarrationScript; return it with the chosen content hash.

        The ``summary`` path feeds the serialised summary as text. The ``paper``
        path (default) sends the native PDF when it is safe to inline and under the
        budget, else falls back to extracted text + (if still over budget) the
        section-split machinery -- the same flow SUMMARISE uses. Never silently
        truncates input.
        """
        if cfg.script_source == "summary":
            if summary is None:
                raise LLMError("script_source is 'summary' but no PaperSummary was provided to NARRATE")
            text = summary_to_document_text(summary)
            script = self._complete(LLMDocument.from_text(text), instruction, cfg)
            return script, hashlib.sha256(text.encode("utf-8")).hexdigest()

        pdf_bytes = pdf_path.read_bytes()
        if self._can_use_native_pdf(pdf_bytes, instruction, cfg):
            script = self._complete(LLMDocument.from_pdf(pdf_bytes), instruction, cfg)
            return script, self._source_hash(pdf_path)

        if self._extractor is None:
            raise LLMError(
                f"PDF '{pdf_path.name}' exceeds the native-PDF input budget and no extractor is configured "
                "for the text fallback; refusing to truncate the input"
            )
        extracted = self._extractor.extract(pdf_path)
        text_doc = LLMDocument.from_text(extracted.full_text)
        if self._fits_budget(text_doc, instruction):
            script = self._complete(text_doc, instruction, cfg)
            return script, extracted.content_hash
        script = self._generate_sectioned(extracted.full_text, instruction, cfg)
        return script, extracted.content_hash

    def _can_use_native_pdf(self, pdf_bytes: bytes, instruction: str, cfg: NarrationConfig) -> bool:
        """True when the PDF is safe to inline AND fits the token budget (cheapest first)."""
        if len(pdf_bytes) > _MAX_INLINE_PDF_BYTES:
            return False
        if len(pdf_bytes) <= _SMALL_PDF_FAST_PATH_BYTES:
            return True
        return self._fits_budget(LLMDocument.from_pdf(pdf_bytes), instruction)

    def _complete(self, document: LLMDocument, instruction: str, cfg: NarrationConfig) -> NarrationScript:
        """One structured-output call, with a recursive truncation-retry guard."""
        return self._complete_with_retry(document, instruction, cfg, iteration=0)

    def _complete_with_retry(
        self, document: LLMDocument, instruction: str, cfg: NarrationConfig, *, iteration: int
    ) -> NarrationScript:
        """Call the LLM; on truncation, split a text document and re-queue.

        A native-PDF document cannot be split locally, so a truncation there raises
        ``max_tokens`` immediately. A text document splits on a section boundary and
        the two halves' turns are concatenated (the narration ``reduce``).
        """
        try:
            return self._llm.complete_structured(
                document=document,
                system=NARRATION_SYSTEM_PROMPT,
                instruction=instruction,
                schema=NarrationScript,
                max_tokens=cfg.model.max_tokens,
                effort=cfg.model.effort,
            )
        except TruncatedResponseError:
            if document.is_pdf or document.text is None or iteration >= _MAX_SPLIT_ITERATIONS:
                raise
            halves = split_text(document.text)
            if len(halves) < 2:
                raise
            partials = [
                self._complete_with_retry(LLMDocument.from_text(half), instruction, cfg, iteration=iteration + 1)
                for half in halves
            ]
            return self._reduce(partials)

    def _generate_sectioned(self, text: str, instruction: str, cfg: NarrationConfig) -> NarrationScript:
        """Split a too-large paper into ordered sections, script each, concatenate.

        Sections are processed carrying forward the running episode title so later
        sections stay consistent, then the per-section scripts' turns are merged.
        Truncated sections recurse via :meth:`_complete_with_retry`.
        """
        sections = split_text(text)
        partials: list[NarrationScript] = []
        for section in sections:
            partial = self._complete_with_retry(LLMDocument.from_text(section), instruction, cfg, iteration=0)
            partials.append(partial)
        return self._reduce(partials)

    @staticmethod
    def _reduce(partials: list[NarrationScript]) -> NarrationScript:
        """Merge per-section partial scripts into one by concatenating their turns.

        Unlike SUMMARISE (which re-summarises), a narration script is an ordered
        timeline, so the partials' turns concatenate directly. The first partial's
        title and voices win (it covers the paper's opening, where the hook lives);
        a deduplicated voices list keeps one entry per role.
        """
        if len(partials) == 1:
            return partials[0]
        head = partials[0]
        turns: list[Turn] = []
        for partial in partials:
            turns.extend(partial.turns)
        voices = head.voices or [v for p in partials for v in p.voices]
        seen: set[SpeakerRole] = set()
        deduped = []
        for ref in voices:
            if ref.role not in seen:
                seen.add(ref.role)
                deduped.append(ref)
        return NarrationScript(episode_title=head.episode_title, voices=deduped, turns=turns)

    def _fits_budget(self, document: LLMDocument, instruction: str) -> bool:
        """True when the document + system prompt fit the input budget (count_tokens)."""
        tokens = self._llm.count_tokens(document=document, system=NARRATION_SYSTEM_PROMPT, instruction=instruction)
        return tokens <= self._input_budget

    @staticmethod
    def _check_quality(script: NarrationScript) -> None:
        """Deterministic quality-band gate, run before caching/synthesis.

        Guards substance the schema cannot: at least one speech turn for each of
        host and author, non-empty speech text, enough turns to be an episode, and
        the host as a minority of the spoken words (the depth-asymmetry).

        Raises:
            NarrationQualityError: if the script is below the quality floor.
        """
        speech = [t for t in script.turns if t.type == "speech"]
        if len(speech) < _MIN_SPEECH_TURNS:
            raise NarrationQualityError(
                f"script has only {len(speech)} speech turns (floor is {_MIN_SPEECH_TURNS}); likely degenerate"
            )
        if any(not (t.text and t.text.strip()) for t in speech):
            raise NarrationQualityError(
                "a speech turn has empty text (the schema parsed but the content is degenerate)"
            )
        roles = {t.role for t in speech}
        if SpeakerRole.HOST not in roles or SpeakerRole.AUTHOR not in roles:
            raise NarrationQualityError("script is missing a host or author speaking turn")
        host_words = sum(len((t.text or "").split()) for t in speech if t.role == SpeakerRole.HOST)
        total_words = sum(len((t.text or "").split()) for t in speech)
        if total_words and host_words / total_words >= _MAX_HOST_WORD_SHARE:
            raise NarrationQualityError(
                f"host speaks {host_words}/{total_words} words (>= {_MAX_HOST_WORD_SHARE:.0%}); "
                "the depth-asymmetry collapsed (host should be the minority)"
            )

    # --- TTS + asset resolution (per-segment cache) ------------------------- #

    def _render_turns(self, script: NarrationScript, cfg: NarrationConfig, *, force: bool) -> list[RenderedTurn]:
        """Turn the script's turns into timeline-ready :class:`RenderedTurn`s.

        Merges consecutive same-speaker speech turns first (natural TTS flow), then
        synthesises each speech turn behind the per-segment cache; music/sfx cues
        resolve to an asset path (or ``None`` if missing -> the mixer skips it);
        pauses pass through with no audio.
        """
        merged = merge_consecutive_turns(script.turns)
        rendered: list[RenderedTurn] = []
        for turn in merged:
            if turn.type == "speech":
                rendered.append(self._render_speech(turn, cfg, force=force))
            elif turn.type in ("music", "sfx"):
                rendered.append(RenderedTurn(turn=turn, asset_path=self._resolve_asset(turn, cfg)))
            else:  # pause
                rendered.append(RenderedTurn(turn=turn))
        return rendered

    def _render_speech(self, turn: Turn, cfg: NarrationConfig, *, force: bool) -> RenderedTurn:
        """Synthesise one speech turn (behind the per-segment cache)."""
        role = turn.role or SpeakerRole.HOST
        voice_id = cfg.voice_for(role)
        if not voice_id:
            raise LLMError(f"no voice configured for role '{role.value}' (set it in [voices])")
        preset = tone_to_preset(turn.tone, cfg.tone_presets, cfg.default_preset)
        text = turn.text or ""

        cache_path = self._segment_cache_path(self._segment_cache_key(text=text, voice_id=voice_id, preset=preset))
        if not force:
            cached = self._load_segment_cache(cache_path)
            if cached is not None:
                return RenderedTurn(turn=turn, audio=cached)

        audio = self._tts.synthesize(text=text, voice_id=voice_id, preset=preset)
        self._write_segment_cache(cache_path, audio)
        return RenderedTurn(turn=turn, audio=audio)

    def _resolve_asset(self, turn: Turn, cfg: NarrationConfig) -> Path | None:
        """Resolve a music/sfx cue to an on-disk asset path, or ``None`` if absent.

        For ``music`` the ``cue`` keys into ``cfg.music_assets`` (intro/outro/...).
        For ``sfx`` the ``cue`` is a free description with no curated asset in Phase
        1, so it resolves to ``None`` (the mixer skips it). A missing/unmapped asset
        returns ``None`` and is logged -- the episode still renders.
        """
        cue = turn.cue
        if not cue:
            return None
        filename = cfg.music_assets.get(cue) if turn.type == "music" else None
        if not filename:
            logger.info("narrate: no asset for %s cue %r; skipping", turn.type, cue)
            return None
        path = self._assets_dir / filename
        if not path.exists():
            logger.info("narrate: asset %s for cue %r is missing; skipping", path, cue)
            return None
        return path

    # --- cache keys + hashes ------------------------------------------------ #

    @staticmethod
    def _script_cache_key(*, input_hash: str, cfg: NarrationConfig) -> str:
        """The script-cache key: hash of the five invalidating inputs."""
        material = "|".join([input_hash, cfg.script_source, cfg.persona_version, cfg.prompt_version, cfg.model.id])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _segment_cache_key(*, text: str, voice_id: str, preset: str) -> str:
        """The per-segment TTS cache key: hash of (turn content, voice, preset)."""
        material = "|".join([text, voice_id, preset])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _source_hash(pdf_path: Path) -> str:
        """sha256 of the raw PDF bytes -- the script-cache input anchor."""
        return hashlib.sha256(pdf_path.read_bytes()).hexdigest()

    # --- caching (sidecars; DB-backed artifact refs arrive at STORE) -------- #

    def _script_cache_path(self, cache_key: str) -> Path:
        return self._scripts_dir / f"{cache_key}.json"

    def _segment_cache_path(self, cache_key: str) -> Path:
        return self._segments_dir / f"{cache_key}.mp3"

    @staticmethod
    def _load_script_cache(cache_path: Path) -> NarrationScript | None:
        """Load a cached script, or ``None`` on miss / corruption / schema drift."""
        if not cache_path.exists():
            return None
        try:
            return NarrationScript.model_validate_json(cache_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None

    @staticmethod
    def _write_script_cache(cache_path: Path, script: NarrationScript) -> None:
        _atomic_write(cache_path, script.model_dump_json().encode("utf-8"))

    @staticmethod
    def _load_segment_cache(cache_path: Path) -> bytes | None:
        """Load cached segment audio, or ``None`` on miss."""
        if not cache_path.exists():
            return None
        try:
            return cache_path.read_bytes()
        except OSError:
            return None

    @staticmethod
    def _write_segment_cache(cache_path: Path, audio: bytes) -> None:
        _atomic_write(cache_path, audio)


def merge_consecutive_turns(turns: Sequence[Turn]) -> list[Turn]:
    """Merge consecutive same-speaker speech turns into one (VTTD pattern).

    When a role has several speech turns in a row with nothing between them (no
    pause / music / sfx / a different speaker), they concatenate into one turn so
    the TTS reads the combined text with natural flow rather than as independent
    utterances. The merged turn keeps the first turn's role; if the tones differ a
    combined tone is built so the TTS has the emotional arc.
    """
    grouped: list[Turn] = []
    i = 0
    while i < len(turns):
        turn = turns[i]
        if turn.type != "speech":
            grouped.append(turn)
            i += 1
            continue
        group = [turn]
        j = i + 1
        while j < len(turns) and turns[j].type == "speech" and turns[j].role == turn.role:
            group.append(turns[j])
            j += 1
        if len(group) == 1:
            grouped.append(turn)
        else:
            merged_text = " ".join(g.text for g in group if g.text)
            tones = [g.tone for g in group if g.tone]
            unique = list(dict.fromkeys(tones))
            merged_tone = (unique[0] if unique else turn.tone) if len(unique) <= 1 else " shifting to ".join(unique)
            grouped.append(Turn(type="speech", role=turn.role, text=merged_text, tone=merged_tone))
        i = j
    return grouped


def tone_to_preset(tone: str | None, tone_presets: dict[str, str], default_preset: str) -> str:
    """Map a free-text turn ``tone`` to one of our preset names.

    First match wins over a substring scan of the (lower-cased) tone against the
    configured ``tone_presets`` keys, so high-energy cues that appear first in the
    config (e.g. ``excited``) take priority in a merged tone string like
    ``"calm shifting to excited"``. Falls back to ``default_preset`` when nothing
    matches (or ``tone`` is ``None``).
    """
    if not tone:
        return default_preset
    lowered = tone.lower()
    for needle, preset in tone_presets.items():
        if needle.lower() in lowered:
            return preset
    return default_preset


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically via a unique temp file + replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
