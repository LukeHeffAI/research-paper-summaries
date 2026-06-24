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
from typing import TypeVar

from pydantic import BaseModel, Field

from downlow.config.models import ModelConfig
from downlow.domain.schemas import OutputProfile, ResearchProfile

_ProfileT = TypeVar("_ProfileT", ResearchProfile, OutputProfile)


class SummaryConfig(BaseModel):
    """The SUMMARISE stage's resolved model + prompt configuration.

    Composes a :class:`ModelConfig` (model id, ``max_tokens``, ``effort``) with
    the ``prompt_version`` so the stage receives one typed bundle and the cache
    key has every input it needs.
    """

    model: ModelConfig
    prompt_version: str = "summary-v1"


class DownLowConfig(BaseModel):
    """The fully-resolved config-file contents the composition root hands down.

    Holds the *active* steering profiles (already selected by name from the file's
    profile tables) plus the per-stage summary config.
    """

    research_profile: ResearchProfile
    output_profile: OutputProfile
    summary: SummaryConfig

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

    return DownLowConfig(
        research_profile=research,
        output_profile=output,
        summary=summary,
        research_profiles=research_profiles,
        output_profiles=output_profiles,
    )


def _select(profiles: dict[str, _ProfileT], name: str | None, kind: str) -> _ProfileT:
    if not name:
        raise ConfigError(f"no active {kind} profile selected (set [profile].active_{kind} or pass an override)")
    if name not in profiles:
        available = ", ".join(sorted(profiles)) or "(none defined)"
        raise ConfigError(f"{kind} profile {name!r} not found in config; available: {available}")
    return profiles[name]
