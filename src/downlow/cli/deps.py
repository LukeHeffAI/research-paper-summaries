"""Composition root: build the adapter/stage container from Settings + config.

This is one of the only layers allowed to instantiate concrete adapters and wire
them into ``core`` stages. It reads ``Settings`` (the env) and the typed config
file, validates secrets at point of use, and hands ``core`` typed values only --
keeping ``core`` pure and provider-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from downlow.adapters.llm.anthropic_client import AnthropicLLMClient
from downlow.adapters.pdf.extractor import PdfPlumberExtractor
from downlow.config.profiles import DownLowConfig, load_config
from downlow.config.settings import Settings
from downlow.core.stages.ingest import IngestStage
from downlow.core.stages.summarise import SummariseStage


@dataclass
class Container:
    """The wired application container for a single CLI invocation."""

    settings: Settings
    config: DownLowConfig
    ingest: IngestStage
    summarise: SummariseStage


def build_container(
    settings: Settings | None = None,
    *,
    research_profile: str | None = None,
    output_profile: str | None = None,
) -> Container:
    """Wire adapters + stages from ``Settings`` and the config file.

    Args:
        settings: the application settings (constructed from the env if omitted).
        research_profile: select this named research profile instead of the
            config file's active one.
        output_profile: select this named output profile instead of the active one.

    Raises:
        ValueError: if ``ANTHROPIC_API_KEY`` is unset (validated at point of use).
    """
    settings = settings or Settings()
    config = load_config(
        settings.config_file,
        research_override=research_profile,
        output_override=output_profile,
    )

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set; summarisation needs an Anthropic API key")

    cache_dir = settings.data_dir / "cache"
    extractor = PdfPlumberExtractor()
    llm = AnthropicLLMClient(api_key=settings.anthropic_api_key, model=config.summary.model.id)

    return Container(
        settings=settings,
        config=config,
        ingest=IngestStage(extractor, cache_dir=cache_dir),
        summarise=SummariseStage(llm, cache_dir=cache_dir, extractor=extractor),
    )


def cache_dir_for(settings: Settings) -> Path:
    """The cache root under ``DATA_DIR`` (exposed for tests / inspection)."""
    return settings.data_dir / "cache"
