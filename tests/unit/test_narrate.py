"""Unit tests for F4 -- the NARRATE stage, prompt, config, and helpers.

Everything runs on fakes (FakeLLMClient / FakeTTSClient / FakeAudioMixer): no
network, no key, no ffmpeg. Covers the interview prompt's persona/craft, schema
validation, tone->preset, consecutive-same-speaker merge, script_source paper vs
summary, the two caches (script + per-segment, hit/miss/force), truncation->retry,
the quality gate, and missing-asset handling.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from downlow.config.models import ModelConfig
from downlow.config.profiles import MixConfig, NarrationConfig, load_config
from downlow.core.prompts.narration import (
    NARRATION_PROMPT_VERSION,
    NARRATION_SYSTEM_PROMPT,
    PERSONA_VERSION,
    build_narration_instruction,
    summary_to_document_text,
)
from downlow.core.stages.narrate import (
    NarrateStage,
    merge_consecutive_turns,
    tone_to_preset,
)
from downlow.domain.enums import SpeakerRole
from downlow.domain.errors import LLMError, NarrationQualityError, TruncatedResponseError
from downlow.domain.ports import LLMClient, LLMDocument, TTSClient
from downlow.domain.schemas import KeyFinding, NarrationScript, PaperSummary, Turn, VoiceRef
from tests.fakes.audio import FakeAudioMixer
from tests.fakes.llm import FakeLLMClient
from tests.fakes.tts import FakeTTSClient

CONFIG_TOML = Path(__file__).parent.parent.parent / "config" / "downlow.toml"


# --------------------------------------------------------------------------- #
# Fixtures / helpers.
# --------------------------------------------------------------------------- #


def _voices() -> list[VoiceRef]:
    return [
        VoiceRef(role=SpeakerRole.HOST, voice_id="host-voice"),
        VoiceRef(role=SpeakerRole.AUTHOR, voice_id="author-voice"),
    ]


def _good_script() -> NarrationScript:
    """A schema-valid script that clears the quality gate (host = minority of words)."""
    return NarrationScript(
        episode_title="The snow, not the dog",
        voices=_voices(),
        turns=[
            Turn(type="speech", role=SpeakerRole.HOST, text="Wait, the snow decided?", tone="hooked, fast"),
            Turn(type="music", cue="intro"),
            Turn(type="speech", role=SpeakerRole.HOST, text="Welcome back.", tone="warm, welcoming"),
            Turn(
                type="speech",
                role=SpeakerRole.AUTHOR,
                text=(
                    "We wanted models to keep working when the test data drifts away from what they were "
                    "trained on, without retraining them, and we found the background can dominate the signal."
                ),
                tone="measured",
            ),
            Turn(type="speech", role=SpeakerRole.HOST, text="Huh, back up.", tone="naive-but-sharp"),
            Turn(
                type="speech",
                role=SpeakerRole.AUTHOR,
                text=(
                    "Great question. Imagine a classifier that only ever saw huskies in snow; it can learn the "
                    "snow instead of the animal, and that is exactly the failure mode we measured and quantified."
                ),
                tone="building, vivid",
            ),
            Turn(type="pause", duration_ms=600),
            Turn(type="speech", role=SpeakerRole.HOST, text="So next time my phone is dumb.", tone="landing"),
            Turn(type="music", cue="outro"),
        ],
    )


def _config(**overrides: object) -> NarrationConfig:
    base: dict[str, object] = {
        "model": ModelConfig(id="claude-sonnet-4-6", max_tokens=32000, effort="medium"),
        "prompt_version": "narration-v1",
        "persona_version": "persona-v1",
        "script_source": "paper",
        "target_minutes": 8,
        "voices": _voices(),
        "tone_presets": {
            "excited": "excited",
            "hooked": "excited",
            "curious": "curious",
            "naive-but-sharp": "curious",
            "warm": "warm",
            "welcoming": "warm",
            "serious": "serious",
            "landing": "serious",
            "measured": "measured",
            "building": "measured",
        },
        "default_preset": "measured",
        "music_assets": {"intro": "intro.wav", "outro": "outro.wav"},
        "mix": MixConfig(),
    }
    base.update(overrides)
    return NarrationConfig(**base)  # type: ignore[arg-type]


def _write_pdf(tmp_path: Path, raw: bytes = b"%PDF-fake-bytes") -> Path:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(raw)
    return pdf


def _stage(tmp_path: Path, llm: LLMClient, tts: TTSClient, mixer: FakeAudioMixer, **kwargs: object) -> NarrateStage:
    return NarrateStage(
        llm,
        tts,
        mixer,
        cache_dir=tmp_path / "cache",
        assets_dir=tmp_path / "assets",
        **kwargs,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------- #
# The interview prompt: persona + craft + fidelity, frozen + versioned.
# --------------------------------------------------------------------------- #


def test_system_prompt_encodes_everyperson_host_and_asymmetry() -> None:
    prompt = NARRATION_SYSTEM_PROMPT.lower()
    assert "everyperson" in prompt
    assert "not an expert" in prompt
    # depth-asymmetry in turn length / vocabulary, host the minority of words
    assert "asymmetry" in prompt
    assert "vocabulary and turn-length" in prompt
    assert "minority" in prompt


def test_system_prompt_encodes_craft_and_antipatterns() -> None:
    prompt = NARRATION_SYSTEM_PROMPT.lower()
    assert "cold-open" in prompt or "cold open" in prompt
    assert "wait, back up" in prompt
    assert "promo" in prompt  # promo-piece anti-pattern
    assert "host-too-smart" in prompt
    assert "limitations beat" in prompt
    # fidelity: claims trace to the source, hedging preserved, speculation flagged
    assert "trace" in prompt
    assert "speculation" in prompt


def test_system_prompt_is_frozen_and_versioned() -> None:
    # cache-stable: no per-paper or per-reader text interpolated
    assert "{" not in NARRATION_SYSTEM_PROMPT  # no stray format placeholders
    # names the schema fields it must fill
    assert "episode_title" in NARRATION_SYSTEM_PROMPT
    assert "turns" in NARRATION_SYSTEM_PROMPT
    # the depth-asymmetry craft principle (host = minority of words) lives in the frozen system prompt
    assert "minority" in NARRATION_SYSTEM_PROMPT.lower()
    assert NARRATION_PROMPT_VERSION == "narration-v1"
    assert PERSONA_VERSION == "persona-v1"


def test_system_prompt_is_pure_ascii() -> None:
    NARRATION_SYSTEM_PROMPT.encode("ascii")  # raises if any non-ASCII slipped in


def test_instruction_paper_vs_summary_and_length_budget() -> None:
    paper = build_narration_instruction(target_minutes=8, script_source="paper")
    assert "attached as a document" in paper
    assert "about 8 minutes" in paper
    assert "1200 words" in paper  # 8 * 150

    summary = build_narration_instruction(target_minutes=10, script_source="summary")
    assert "structured summary" in summary
    assert "complete and only" in summary
    assert "1500 words" in summary  # 10 * 150


# --------------------------------------------------------------------------- #
# Schema validation + the fake satisfies the port.
# --------------------------------------------------------------------------- #


def test_narration_script_round_trips() -> None:
    script = _good_script()
    reloaded = NarrationScript.model_validate_json(script.model_dump_json())
    assert reloaded == script
    assert reloaded.turns[0].type == "speech"
    assert reloaded.turns[1].cue == "intro"


def test_fake_tts_satisfies_port() -> None:
    assert isinstance(FakeTTSClient(), TTSClient)


def test_fake_llm_returns_validated_narration_script() -> None:
    fake = FakeLLMClient(result=_good_script())
    result = fake.complete_structured(
        document=LLMDocument.from_text("body"),
        system="sys",
        instruction="go",
        schema=NarrationScript,
        max_tokens=32000,
        effort="medium",
    )
    assert isinstance(result, NarrationScript)
    assert result.episode_title


# --------------------------------------------------------------------------- #
# tone -> preset.
# --------------------------------------------------------------------------- #


def test_tone_to_preset_maps_substring_first_match() -> None:
    presets = {"excited": "excited", "warm": "warm", "measured": "measured"}
    assert tone_to_preset("warm, welcoming", presets, "measured") == "warm"
    assert tone_to_preset("hooked and excited", presets, "measured") == "excited"


def test_tone_to_preset_falls_back_to_default() -> None:
    assert tone_to_preset(None, {"warm": "warm"}, "measured") == "measured"
    assert tone_to_preset("inscrutable", {"warm": "warm"}, "measured") == "measured"


def test_tone_to_preset_high_energy_first_in_merged_tone() -> None:
    # ordered dict: high-energy cue listed first wins on a merged "calm shifting to excited"
    presets = {"excited": "excited", "measured": "measured"}
    assert tone_to_preset("measured shifting to excited", presets, "measured") == "excited"


# --------------------------------------------------------------------------- #
# Consecutive-same-speaker merge.
# --------------------------------------------------------------------------- #


def test_merge_consecutive_same_speaker_turns() -> None:
    turns = [
        Turn(type="speech", role=SpeakerRole.AUTHOR, text="First part.", tone="measured"),
        Turn(type="speech", role=SpeakerRole.AUTHOR, text="Second part.", tone="building"),
        Turn(type="speech", role=SpeakerRole.HOST, text="Huh."),
    ]
    merged = merge_consecutive_turns(turns)
    assert len(merged) == 2
    assert merged[0].text == "First part. Second part."
    assert merged[0].role == SpeakerRole.AUTHOR
    # differing tones recorded as a shift
    assert "shifting to" in (merged[0].tone or "")
    assert merged[1].role == SpeakerRole.HOST


def test_merge_does_not_cross_non_speech_or_speaker() -> None:
    turns = [
        Turn(type="speech", role=SpeakerRole.HOST, text="A."),
        Turn(type="pause", duration_ms=400),
        Turn(type="speech", role=SpeakerRole.HOST, text="B."),
    ]
    merged = merge_consecutive_turns(turns)
    # the pause breaks the run -> three turns preserved
    assert [t.type for t in merged] == ["speech", "pause", "speech"]


# --------------------------------------------------------------------------- #
# Stage: script_source paper vs summary.
# --------------------------------------------------------------------------- #


def test_paper_source_uses_native_pdf(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    llm = FakeLLMClient(result=_good_script())
    tts, mixer = FakeTTSClient(), FakeAudioMixer()
    stage = _stage(tmp_path, llm, tts, mixer)

    stage.run(pdf, _config())
    assert llm.call_count == 1
    assert llm.calls[0].document.is_pdf
    assert llm.calls[0].system == NARRATION_SYSTEM_PROMPT


def test_summary_source_uses_summary_text(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    llm = FakeLLMClient(result=_good_script())
    tts, mixer = FakeTTSClient(), FakeAudioMixer()
    stage = _stage(tmp_path, llm, tts, mixer)
    summary = PaperSummary(
        title="A Paper",
        overall_summary="An overall summary of the paper " * 10,
        key_findings=[KeyFinding(statement="X improves Y.", evidence="+4 pts")],
        contributions=["A method."],
        methods="Controlled comparison.",
        gaps_and_limitations=["Single modality."],
        relevance_to_profile="Bears on your focus.",
    )

    stage.run(pdf, _config(script_source="summary"), summary=summary)
    assert llm.call_count == 1
    call = llm.calls[0]
    assert not call.document.is_pdf  # text path
    assert "Key findings" in (call.document.text or "")


def test_summary_source_without_summary_raises(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    stage = _stage(tmp_path, FakeLLMClient(result=_good_script()), FakeTTSClient(), FakeAudioMixer())
    with pytest.raises(LLMError, match="no PaperSummary"):
        stage.run(pdf, _config(script_source="summary"))


def test_summary_to_document_text_renders_sections() -> None:
    summary = PaperSummary(
        title="T",
        overall_summary="Overall.",
        key_findings=[KeyFinding(statement="F1", evidence="e1"), KeyFinding(statement="F2")],
        contributions=["C1"],
        methods="M",
        gaps_and_limitations=["G1"],
        relevance_to_profile="R",
    )
    text = summary_to_document_text(summary)
    assert "Title: T" in text
    assert "- F1 (evidence: e1)" in text
    assert "- F2" in text and "evidence" not in text.split("- F2")[1].split("\n")[0]
    assert "Relevance to the reader:" in text


# --------------------------------------------------------------------------- #
# Stage: script cache (miss -> hit -> force) via the LLM spy.
# --------------------------------------------------------------------------- #


def test_script_cache_miss_then_hit(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    llm = FakeLLMClient(result=_good_script())
    stage = _stage(tmp_path, llm, FakeTTSClient(), FakeAudioMixer())

    first = stage.generate_script(pdf, _config())
    assert llm.call_count == 1
    second = stage.generate_script(pdf, _config())
    assert llm.call_count == 1  # hit -> no second LLM call
    assert second == first
    # provenance stamped
    assert first.model == "claude-sonnet-4-6"
    assert first.prompt_version == "narration-v1"
    assert first.paper_content_hashes == [hashlib.sha256(pdf.read_bytes()).hexdigest()]


def test_script_force_bypasses_cache(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    llm = FakeLLMClient(result=_good_script())
    stage = _stage(tmp_path, llm, FakeTTSClient(), FakeAudioMixer())
    stage.generate_script(pdf, _config())
    stage.generate_script(pdf, _config(), force=True)
    assert llm.call_count == 2


def test_script_cache_key_changes_with_script_source(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    llm = FakeLLMClient(result=_good_script())
    summary = PaperSummary(
        title="A",
        overall_summary="o " * 50,
        key_findings=[KeyFinding(statement="s")],
        contributions=["c"],
        methods="m",
        gaps_and_limitations=["g"],
        relevance_to_profile="r",
    )
    stage = _stage(tmp_path, llm, FakeTTSClient(), FakeAudioMixer())
    stage.generate_script(pdf, _config(script_source="paper"))
    stage.generate_script(pdf, _config(script_source="summary"), summary=summary)
    assert llm.call_count == 2  # different source -> different key -> miss


def test_corrupt_script_cache_treated_as_miss(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    llm = FakeLLMClient(result=_good_script())
    stage = _stage(tmp_path, llm, FakeTTSClient(), FakeAudioMixer())
    stage.generate_script(pdf, _config())
    sidecar = next((tmp_path / "cache" / "narration").glob("*.json"))
    sidecar.write_text("{ not valid", encoding="utf-8")
    stage.generate_script(pdf, _config())
    assert llm.call_count == 2


# --------------------------------------------------------------------------- #
# Stage: per-segment TTS cache (miss -> hit -> force) via the TTS spy.
# --------------------------------------------------------------------------- #


def test_segment_cache_miss_then_hit(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    tts = FakeTTSClient()
    stage = _stage(tmp_path, FakeLLMClient(result=_good_script()), tts, FakeAudioMixer())

    stage.run(pdf, _config())
    first_synths = tts.call_count
    assert first_synths > 0
    # second run: script is cached AND segments are cached -> no new synth
    stage.run(pdf, _config())
    assert tts.call_count == first_synths


def test_segment_cache_force_resynthesises(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    tts = FakeTTSClient()
    stage = _stage(tmp_path, FakeLLMClient(result=_good_script()), tts, FakeAudioMixer())
    stage.run(pdf, _config())
    n = tts.call_count
    stage.run(pdf, _config(), force=True)
    assert tts.call_count == 2 * n  # every segment re-synthesised


def test_segment_synth_count_matches_merged_speech_turns(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    tts = FakeTTSClient()
    stage = _stage(tmp_path, FakeLLMClient(result=_good_script()), tts, FakeAudioMixer())
    stage.run(pdf, _config())
    # _good_script has 6 speech turns, none consecutive-same-speaker -> 6 synths
    assert tts.call_count == 6


# --------------------------------------------------------------------------- #
# Stage: rendered turns handed to the mixer (audio, asset resolution).
# --------------------------------------------------------------------------- #


def test_rendered_turns_carry_audio_and_resolved_assets(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    # ship the intro asset; leave outro missing -> graceful skip (asset_path None)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "intro.wav").write_bytes(b"RIFFfake")
    mixer = FakeAudioMixer()
    stage = _stage(tmp_path, FakeLLMClient(result=_good_script()), FakeTTSClient(), mixer)

    audio = stage.run(pdf, _config())
    assert audio.startswith(b"FAKEMIX")
    rendered = mixer.last
    speech = [r for r in rendered if r.turn.type == "speech"]
    assert speech and all(r.audio is not None for r in speech)
    music = {r.turn.cue: r for r in rendered if r.turn.type == "music"}
    assert music["intro"].asset_path is not None  # resolved
    assert music["outro"].asset_path is None  # missing -> skipped gracefully


def test_unmapped_voice_role_raises(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    stage = _stage(tmp_path, FakeLLMClient(result=_good_script()), FakeTTSClient(), FakeAudioMixer())
    # config with only a host voice -> author turn has no voice
    cfg = _config(voices=[VoiceRef(role=SpeakerRole.HOST, voice_id="h")])
    with pytest.raises(LLMError, match="no voice configured for role 'author'"):
        stage.run(pdf, cfg)


# --------------------------------------------------------------------------- #
# Long-input: text fallback + section-split + truncation retry (reuses textsplit).
# --------------------------------------------------------------------------- #


class _FakeExtractor:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract(self, pdf_path: Path):  # type: ignore[no-untyped-def]
        from downlow.domain.schemas import ExtractedText

        return ExtractedText(
            full_text=self._text,
            pages=[self._text],
            page_count=1,
            is_scanned=False,
            source_hash=hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            content_hash=hashlib.sha256(self._text.encode("utf-8")).hexdigest(),
        )


def _midsize_pdf(tmp_path: Path) -> Path:
    from downlow.core.stages.narrate import _SMALL_PDF_FAST_PATH_BYTES

    pdf = tmp_path / "mid.pdf"
    pdf.write_bytes(b"%PDF-" + b"x" * (_SMALL_PDF_FAST_PATH_BYTES + 4096))
    return pdf


def test_over_budget_pdf_falls_back_to_text(tmp_path: Path) -> None:
    pdf = _midsize_pdf(tmp_path)
    long_text = "Section A.\n\nSection B with content."

    def tokens(doc: LLMDocument) -> int:
        return 500_000 if doc.is_pdf else 100

    llm = FakeLLMClient(result=_good_script(), token_count=tokens)
    stage = _stage(tmp_path, llm, FakeTTSClient(), FakeAudioMixer(), extractor=_FakeExtractor(long_text))
    script = stage.generate_script(pdf, _config())
    assert llm.call_count == 1
    assert not llm.calls[0].document.is_pdf
    assert script.paper_content_hashes == [hashlib.sha256(long_text.encode("utf-8")).hexdigest()]


def test_over_budget_pdf_without_extractor_raises(tmp_path: Path) -> None:
    pdf = _midsize_pdf(tmp_path)
    llm = FakeLLMClient(result=_good_script(), token_count=500_000)
    stage = _stage(tmp_path, llm, FakeTTSClient(), FakeAudioMixer(), extractor=None)
    with pytest.raises(LLMError, match="native-PDF input budget"):
        stage.generate_script(pdf, _config())


def test_truncation_then_retry_on_text(tmp_path: Path) -> None:
    pdf = _midsize_pdf(tmp_path)
    splittable = "Part one of the document.\n\nPart two of the document."
    llm = FakeLLMClient(result=_good_script(), truncate_first_n=1)
    stage = _stage(
        tmp_path,
        llm,
        FakeTTSClient(),
        FakeAudioMixer(),
        extractor=_FakeExtractor(splittable),
        input_budget_tokens=1,  # force the text/section path
    )
    script = stage.generate_script(pdf, _config())
    assert isinstance(script, NarrationScript)
    assert llm.call_count >= 3  # truncate(1) + two halves (+ concat reduce)


def test_truncation_on_native_pdf_raises(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    llm = FakeLLMClient(result=_good_script(), truncate_first_n=1, token_count=100)
    stage = _stage(tmp_path, llm, FakeTTSClient(), FakeAudioMixer())
    with pytest.raises(TruncatedResponseError):
        stage.generate_script(pdf, _config())


# --------------------------------------------------------------------------- #
# Quality gate: schema-valid but degenerate scripts are rejected.
# --------------------------------------------------------------------------- #


def test_quality_gate_rejects_too_few_speech_turns(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    bad = NarrationScript(
        episode_title="t",
        voices=_voices(),
        turns=[Turn(type="speech", role=SpeakerRole.HOST, text="Hi.")],
    )
    stage = _stage(tmp_path, FakeLLMClient(result=bad), FakeTTSClient(), FakeAudioMixer())
    with pytest.raises(NarrationQualityError, match="speech turns"):
        stage.generate_script(pdf, _config())


def test_quality_gate_rejects_host_monologue(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    # host speaks the vast majority of words -> asymmetry collapsed
    bad = NarrationScript(
        episode_title="t",
        voices=_voices(),
        turns=[
            Turn(type="speech", role=SpeakerRole.HOST, text="word " * 100),
            Turn(type="speech", role=SpeakerRole.AUTHOR, text="brief."),
            Turn(type="speech", role=SpeakerRole.HOST, text="more " * 50),
            Turn(type="speech", role=SpeakerRole.AUTHOR, text="ok."),
        ],
    )
    stage = _stage(tmp_path, FakeLLMClient(result=bad), FakeTTSClient(), FakeAudioMixer())
    with pytest.raises(NarrationQualityError, match="depth-asymmetry"):
        stage.generate_script(pdf, _config())


def test_quality_gate_rejects_empty_speech_text(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    bad = NarrationScript(
        episode_title="t",
        voices=_voices(),
        turns=[
            Turn(type="speech", role=SpeakerRole.HOST, text="Q?"),
            Turn(type="speech", role=SpeakerRole.AUTHOR, text="   "),
            Turn(type="speech", role=SpeakerRole.HOST, text="ok"),
            Turn(type="speech", role=SpeakerRole.AUTHOR, text="A long enough answer here friend."),
        ],
    )
    stage = _stage(tmp_path, FakeLLMClient(result=bad), FakeTTSClient(), FakeAudioMixer())
    with pytest.raises(NarrationQualityError, match="empty text"):
        stage.generate_script(pdf, _config())


def test_good_script_passes_the_gate(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path)
    stage = _stage(tmp_path, FakeLLMClient(result=_good_script()), FakeTTSClient(), FakeAudioMixer())
    script = stage.generate_script(pdf, _config())
    assert script.episode_title == "The snow, not the dog"


# --------------------------------------------------------------------------- #
# Config-file layer: the [podcast]/[voices]/[tone_presets]/[mix]/[music] sections.
# --------------------------------------------------------------------------- #


def test_load_config_parses_narration_section() -> None:
    cfg = load_config(CONFIG_TOML)
    nar = cfg.narration
    assert nar.script_source == "paper"
    assert nar.target_minutes == 8
    assert nar.model.id == "claude-sonnet-4-6"
    assert nar.model.max_tokens == 32000
    assert nar.voice_for(SpeakerRole.HOST)
    assert nar.voice_for(SpeakerRole.AUTHOR)
    assert nar.tone_presets["warm"] == "warm"
    assert nar.music_assets["intro"] == "intro.wav"
    assert nar.mix.crossfade_ms == 120
    assert nar.mix.target_loudness_dbfs == -16.0
