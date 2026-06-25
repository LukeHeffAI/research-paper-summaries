"""Typed config-file layer: profiles + per-stage summary config (F2).

The config file (``config/downlow.toml`` by default) holds the *typed application*
configuration that is not a secret: the steering profiles (which replace the
legacy ``data/research_data.json`` + ``data/document_data.json``) and the
SUMMARISE model/summary config. Secrets and infra stay in the environment and are
read by :class:`~downlow.config.settings.Settings`.

This module owns parsing the TOML into pure domain models. ``core`` is handed the
resulting :class:`ResearchProfile` / :class:`OutputProfile` /
:class:`SummaryConfig` -- it never reads the file (keeping it pure and testable
with arbitrary config).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal, TypeVar

from pydantic import BaseModel, Field

from downlow.config.models import ModelConfig
from downlow.domain.enums import SpeakerRole
from downlow.domain.schemas import OutputProfile, ResearchProfile, VoiceRef

TitleMode = Literal["templated", "llm"]

_ProfileT = TypeVar("_ProfileT", ResearchProfile, OutputProfile)


class SummaryConfig(BaseModel):
    """The SUMMARISE stage's resolved model + prompt configuration.

    Composes a :class:`ModelConfig` (model id, ``max_tokens``, ``effort``) with
    the ``prompt_version`` so the stage receives one typed bundle and the cache
    key has every input it needs.
    """

    model: ModelConfig
    prompt_version: str = "summary-v1"


# --------------------------------------------------------------------------- #
# RENDER config (F3) -- the Typst report's title/template knobs.               #
# `core` receives the typed values; it never reads the config file.            #
# --------------------------------------------------------------------------- #


class ReportConfig(BaseModel):
    """The RENDER stage's resolved template + title configuration.

    ``template_version`` is stamped into the report's :class:`ReportMeta` and is an
    optional render-cache-key input. ``title_mode`` selects how the document title
    is chosen: ``templated`` (a deterministic default from the paper title(s), no
    API call) or ``llm`` (a tiny LLM call proposes a title; the on-disk slug is
    still derived deterministically -- the model never picks the filename). The
    :class:`ModelConfig` is used only on the ``llm`` path.
    """

    template_version: str = "report-v1"
    title_mode: TitleMode = "templated"
    model: ModelConfig = Field(
        default_factory=lambda: ModelConfig(id="claude-sonnet-4-6", max_tokens=200, effort="low")
    )
    prompt_version: str = "report-title-v1"


# --------------------------------------------------------------------------- #
# F5 config -- the paper-filename metadata extractor's model + prompt knobs.    #
# `core` receives the typed values; it never reads the config file.            #
# --------------------------------------------------------------------------- #


class MetadataConfig(BaseModel):
    """The F5 metadata-extractor's resolved model + prompt configuration.

    Metadata extraction is a tiny, cheap structured-output call (title / authors /
    year), so the defaults are a small ``max_tokens`` and ``effort = "low"``. The
    ``prompt_version`` is the metadata cache-key input (matches
    :data:`downlow.core.prompts.metadata.METADATA_PROMPT_VERSION`).
    """

    model: ModelConfig = Field(
        default_factory=lambda: ModelConfig(id="claude-sonnet-4-6", max_tokens=512, effort="low")
    )
    prompt_version: str = "metadata-v1"


# --------------------------------------------------------------------------- #
# NARRATE config (F4) -- podcast / voices / tone-presets / mix / music.        #
# These are the owner-tunable knobs from docs/podcast_design.md section 7.     #
# `core` receives the typed values; it never reads the config file.            #
# --------------------------------------------------------------------------- #


class MixConfig(BaseModel):
    """The audio-mixer constants (docs/podcast_design.md section 6).

    VTTD defaults as starting points. Negative dB values attenuate; ms values are
    fade / gap durations. The PydubAudioMixer adapter receives this typed bundle.
    """

    bed_volume_db: float = -22.0
    sting_volume_db: float = -3.0
    crossfade_ms: int = 120
    intro_fade_ms: int = 2000
    outro_fade_ms: int = 3000
    inter_turn_gap_ms: int = 250
    target_loudness_dbfs: float = -16.0


class NarrationConfig(BaseModel):
    """The NARRATE stage's resolved model + prompt + production configuration.

    One typed bundle for the stage and the adapters: the LLM model config and
    prompt/persona versions (the script-cache key), the ``script_source``
    (paper|summary) and ``target_minutes`` budget, the role->voice mapping, the
    tone->preset map, the music-asset cue->filename map, and the mix constants.
    """

    model: ModelConfig
    prompt_version: str = "narration-v1"
    persona_version: str = "persona-v1"
    script_source: str = "paper"
    target_minutes: int = 8
    voices: list[VoiceRef] = Field(default_factory=list)
    tone_presets: dict[str, str] = Field(default_factory=dict)
    default_preset: str = "measured"
    music_assets: dict[str, str] = Field(default_factory=dict)
    mix: MixConfig = Field(default_factory=MixConfig)

    def voice_for(self, role: SpeakerRole) -> str | None:
        """The configured voice id for ``role``, or ``None`` if unmapped."""
        for ref in self.voices:
            if ref.role == role:
                return ref.voice_id
        return None


class DownLowConfig(BaseModel):
    """The fully-resolved config-file contents the composition root hands down.

    Holds the *active* steering profiles (already selected by name from the file's
    profile tables) plus the per-stage summary config.
    """

    research_profile: ResearchProfile
    output_profile: OutputProfile
    summary: SummaryConfig
    report: ReportConfig
    narration: NarrationConfig
    metadata: MetadataConfig = Field(default_factory=MetadataConfig)

    # All defined profiles, kept so the CLI can select a non-default one by name.
    research_profiles: dict[str, ResearchProfile] = Field(default_factory=dict)
    output_profiles: dict[str, OutputProfile] = Field(default_factory=dict)


class ConfigError(Exception):
    """Raised when the config file is missing a referenced profile or section."""


def load_config(
    config_path: Path,
    *,
    research_override: str | None = None,
    output_override: str | None = None,
) -> DownLowConfig:
    """Parse ``config_path`` into a typed :class:`DownLowConfig`.

    Args:
        config_path: the TOML file to read.
        research_override: select this named research profile instead of the
            file's ``[profile].active_research`` (the CLI ``--profile`` hook).
        output_override: select this named output profile instead of the file's
            ``[profile].active_output``.

    Raises:
        FileNotFoundError: if ``config_path`` does not exist.
        ConfigError: if a referenced profile name is absent from the file.
    """
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))

    research_profiles = {name: ResearchProfile(name=name, **body) for name, body in raw.get("research", {}).items()}
    output_profiles = {name: OutputProfile(name=name, **body) for name, body in raw.get("output", {}).items()}

    profile_section = raw.get("profile", {})
    research_name = research_override or profile_section.get("active_research")
    output_name = output_override or profile_section.get("active_output")

    research = _select(research_profiles, research_name, "research")
    output = _select(output_profiles, output_name, "output")

    summary_section = raw.get("summary", {})
    summary = SummaryConfig(
        model=ModelConfig(
            id=summary_section.get("model", "claude-sonnet-4-6"),
            max_tokens=int(summary_section.get("max_tokens", 8000)),
            effort=summary_section.get("effort", "low"),
        ),
        prompt_version=summary_section.get("prompt_version", "summary-v1"),
    )

    report = _load_report(raw)
    narration = _load_narration(raw)
    metadata = _load_metadata(raw)

    return DownLowConfig(
        research_profile=research,
        output_profile=output,
        summary=summary,
        report=report,
        narration=narration,
        metadata=metadata,
        research_profiles=research_profiles,
        output_profiles=output_profiles,
    )


def _load_report(raw: dict[str, object]) -> ReportConfig:
    """Parse the [report] section into a typed :class:`ReportConfig`.

    Tolerant of an absent section: every field has a default, so a config file
    without a ``[report]`` table still yields a usable :class:`ReportConfig` (the
    safe ``templated`` title mode, the shipped template version).
    """
    report = _section(raw, "report")
    return ReportConfig(
        template_version=_as_str(report.get("template_version"), "report-v1"),
        title_mode=_as_title_mode(report.get("title_mode")),
        model=ModelConfig(
            id=_as_str(report.get("model"), "claude-sonnet-4-6"),
            max_tokens=_as_int(report, "max_tokens", 200),
            effort=_as_str(report.get("effort"), "low"),
        ),
        prompt_version=_as_str(report.get("prompt_version"), "report-title-v1"),
    )


def _as_title_mode(value: object) -> TitleMode:
    """Validate the [report].title_mode literal at config-parse time.

    A typo (e.g. ``templatd``) raises :class:`ConfigError` here rather than
    silently falling through to the templated branch at render time. An absent
    value defaults to ``templated``.
    """
    if value is None:
        return "templated"
    if value == "templated" or value == "llm":
        return value
    raise ConfigError(f"[report].title_mode must be 'templated' or 'llm', got {value!r}")


def _load_metadata(raw: dict[str, object]) -> MetadataConfig:
    """Parse the [metadata] section into a typed :class:`MetadataConfig` (F5).

    Tolerant of an absent section: every field has a default, so a config file
    without a ``[metadata]`` table still yields a usable :class:`MetadataConfig`
    (the cheap default model + the shipped prompt version).
    """
    metadata = _section(raw, "metadata")
    return MetadataConfig(
        model=ModelConfig(
            id=_as_str(metadata.get("model"), "claude-sonnet-4-6"),
            max_tokens=_as_int(metadata, "max_tokens", 512),
            effort=_as_str(metadata.get("effort"), "low"),
        ),
        prompt_version=_as_str(metadata.get("prompt_version"), "metadata-v1"),
    )


def _load_narration(raw: dict[str, object]) -> NarrationConfig:
    """Parse the [podcast]/[voices]/[tone_presets]/[mix]/[music] sections.

    Tolerant of missing sections: every field has a default, so a config file
    without a podcast section still yields a usable :class:`NarrationConfig` (the
    NARRATE stage then fails clearly only if it actually needs an absent voice id).
    """
    podcast = _section(raw, "podcast")
    voices_section = _section(raw, "voices")
    tone_section = _section(raw, "tone_presets")
    mix_section = _section(raw, "mix")
    music_section = _section(raw, "music")

    voices: list[VoiceRef] = []
    host_id = voices_section.get("host")
    if isinstance(host_id, str) and host_id:
        voices.append(VoiceRef(role=SpeakerRole.HOST, voice_id=host_id))
    author_id = voices_section.get("author")
    if isinstance(author_id, str) and author_id:
        voices.append(VoiceRef(role=SpeakerRole.AUTHOR, voice_id=author_id))

    tone_presets = {str(k): _as_str(v, "") for k, v in tone_section.items()}
    music_assets = {str(k): _as_str(v, "") for k, v in music_section.items()}

    mix = MixConfig(
        bed_volume_db=_as_float(mix_section, "bed_volume_db", -22.0),
        sting_volume_db=_as_float(mix_section, "sting_volume_db", -3.0),
        crossfade_ms=_as_int(mix_section, "crossfade_ms", 120),
        intro_fade_ms=_as_int(mix_section, "intro_fade_ms", 2000),
        outro_fade_ms=_as_int(mix_section, "outro_fade_ms", 3000),
        inter_turn_gap_ms=_as_int(mix_section, "inter_turn_gap_ms", 250),
        target_loudness_dbfs=_as_float(mix_section, "target_loudness_dbfs", -16.0),
    )

    return NarrationConfig(
        model=ModelConfig(
            id=_as_str(podcast.get("model"), "claude-sonnet-4-6"),
            max_tokens=_as_int(podcast, "max_tokens", 32000),
            effort=_as_str(podcast.get("effort"), "medium"),
        ),
        prompt_version=_as_str(podcast.get("prompt_version"), "narration-v1"),
        persona_version=_as_str(podcast.get("persona_version"), "persona-v1"),
        script_source=_as_str(podcast.get("script_source"), "paper"),
        target_minutes=_as_int(podcast, "target_minutes", 8),
        voices=voices,
        tone_presets=tone_presets,
        default_preset=_as_str(voices_section.get("default_preset"), "measured"),
        music_assets=music_assets,
        mix=mix,
    )


def _section(raw: dict[str, object], name: str) -> dict[str, object]:
    """Return the named table from the parsed TOML, or an empty dict."""
    value = raw.get(name, {})
    return value if isinstance(value, dict) else {}


def _as_str(value: object, default: str) -> str:
    """Coerce a TOML scalar to ``str`` (so mypy sees a typed result), else default."""
    return value if isinstance(value, str) else default


def _as_int(section: dict[str, object], key: str, default: int) -> int:
    """Read ``key`` from ``section`` as an ``int`` (bools rejected), else default."""
    value = section.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _as_float(section: dict[str, object], key: str, default: float) -> float:
    """Read ``key`` from ``section`` as a ``float`` (ints accepted), else default."""
    value = section.get(key)
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    return default


def _select(profiles: dict[str, _ProfileT], name: str | None, kind: str) -> _ProfileT:
    if not name:
        raise ConfigError(f"no active {kind} profile selected (set [profile].active_{kind} or pass an override)")
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none defined)"
        raise ConfigError(f"{kind} profile {name!r} not found in config; available: {available}")
    return profiles[name]
