"""Composition root: build the adapter/stage container from Settings + config.

This is one of the only layers allowed to instantiate concrete adapters and wire
them into ``core`` stages. It reads ``Settings`` (the env) and the typed config
file, validates secrets at point of use, and hands ``core`` typed values only --
keeping ``core`` pure and provider-agnostic.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session

from downlow.adapters.audio.mixer import PydubAudioMixer
from downlow.adapters.db.engine import SystemClock, create_all, create_db_engine
from downlow.adapters.db.repositories import SqlModelRepository
from downlow.adapters.llm.anthropic_client import AnthropicLLMClient
from downlow.adapters.pdf.extractor import PdfPlumberExtractor
from downlow.adapters.render.typst_renderer import TypstRenderer
from downlow.adapters.storage.filesystem_store import FilesystemArtifactStore
from downlow.adapters.tts.elevenlabs_client import ElevenLabsTTSClient
from downlow.config.profiles import DownLowConfig, load_config
from downlow.config.settings import Settings
from downlow.core.services.filename import FilenameHeuristic
from downlow.core.services.library import LibraryService
from downlow.core.services.processing import ProcessingService
from downlow.core.services.voices import StockVoiceSpec, VoicesService
from downlow.core.stages.ingest import IngestStage
from downlow.core.stages.narrate import NarrateStage
from downlow.core.stages.render import RenderStage
from downlow.core.stages.store import StoreStage
from downlow.core.stages.summarise import SummariseStage
from downlow.domain.entities import (
    Episode,
    EpisodePaper,
    Paper,
    PipelineRun,
    PodcastAsset,
    ReportAsset,
    StageRun,
    Summary,
    Voice,
)
from downlow.domain.enums import SpeakerRole


@dataclass
class Container:
    """The wired application container for a single CLI invocation."""

    settings: Settings
    config: DownLowConfig
    ingest: IngestStage
    summarise: SummariseStage
    render: RenderStage


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
    llm = AnthropicLLMClient(
        api_key=settings.anthropic_api_key,
        model=config.summary.model.id,
        max_retries=settings.max_retries,
        timeout=settings.request_timeout,
    )

    # RENDER (F3): the typst renderer + the filesystem artifact store. The LLM is
    # passed only so the optional ``title_mode = "llm"`` override path works; the
    # default ``templated`` mode never calls it.
    renderer = TypstRenderer(binary=settings.typst_binary)
    store = FilesystemArtifactStore(settings.data_dir)
    render = RenderStage(renderer, store, llm=llm, cache_dir=cache_dir)

    return Container(
        settings=settings,
        config=config,
        ingest=IngestStage(extractor, cache_dir=cache_dir),
        summarise=SummariseStage(llm, cache_dir=cache_dir, extractor=extractor),
        render=render,
    )


def build_narrate_stage(
    settings: Settings | None = None,
    *,
    config: DownLowConfig | None = None,
    research_profile: str | None = None,
    output_profile: str | None = None,
) -> NarrateStage:
    """Wire the NARRATE stage (F4) -- needs both Anthropic and ElevenLabs keys.

    Built separately from :func:`build_container` so the summarise/ingest commands
    do not require an ElevenLabs key. Uses the *narration* model config (distinct
    from the summary model) and the repo/``$DATA_DIR`` assets dir.

    Raises:
        ValueError: if ``ANTHROPIC_API_KEY`` or ``ELEVENLABS_API_KEY`` is unset.
    """
    settings = settings or Settings()
    config = config or load_config(
        settings.config_file,
        research_override=research_profile,
        output_override=output_profile,
    )

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set; narration needs an Anthropic API key")
    if not settings.elevenlabs_api_key:
        raise ValueError("ELEVENLABS_API_KEY is not set; narration needs an ElevenLabs API key")

    cache_dir = settings.data_dir / "cache"
    extractor = PdfPlumberExtractor()
    llm = AnthropicLLMClient(
        api_key=settings.anthropic_api_key,
        model=config.narration.model.id,
        max_retries=settings.max_retries,
        timeout=settings.request_timeout,
    )
    tts = ElevenLabsTTSClient(api_key=settings.elevenlabs_api_key)
    mixer = PydubAudioMixer(config.narration.mix)

    return NarrateStage(
        llm,
        tts,
        mixer,
        cache_dir=cache_dir,
        assets_dir=settings.assets_dir,
        extractor=extractor,
    )


def build_filename_heuristic(
    settings: Settings | None = None,
    *,
    config: DownLowConfig | None = None,
) -> FilenameHeuristic:
    """Wire the F5 filename heuristic -- needs only the Anthropic key.

    Built separately from :func:`build_container` so ``dl name`` does not require an
    ElevenLabs key (or the typst binary). Uses the *metadata* model config (a tiny,
    cheap call distinct from the summary model) and injects today's UTC year as the
    year-plausibility bound, keeping ``core`` free of any clock dependency.

    Raises:
        ValueError: if ``ANTHROPIC_API_KEY`` is unset.
    """
    settings = settings or Settings()
    config = config or load_config(settings.config_file)

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set; metadata extraction needs an Anthropic API key")

    llm = AnthropicLLMClient(
        api_key=settings.anthropic_api_key,
        model=config.metadata.model.id,
        max_retries=settings.max_retries,
        timeout=settings.request_timeout,
    )
    return FilenameHeuristic(
        llm,
        extractor=PdfPlumberExtractor(),
        current_year=datetime.now(UTC).year,
    )


def cache_dir_for(settings: Settings) -> Path:
    """The cache root under ``DATA_DIR`` (exposed for tests / inspection)."""
    return settings.data_dir / "cache"


# --------------------------------------------------------------------------- #
# Phase 2.1 -- the persisted pipeline composition root (engine + session +     #
# repositories + the STORE stage + the orchestration/library services).        #
# --------------------------------------------------------------------------- #


# The single owning user for the single-user phase. The schema carries a user FK
# throughout so multi-user slots in later; today every paper/run belongs to id 1.
_DEFAULT_USER_ID = 1


@dataclass
class ProcessingContainer:
    """A fully-wired persisted-pipeline container, bound to one open DB session.

    Yielded by :func:`processing_session` for the lifetime of a CLI invocation
    (the session must stay open while the repositories are used). Holds the
    orchestration + library services and the resolved config.
    """

    settings: Settings
    config: DownLowConfig
    processing: ProcessingService
    library: LibraryService
    user_id: int


@contextmanager
def processing_session(
    settings: Settings | None = None,
    *,
    research_profile: str | None = None,
    output_profile: str | None = None,
    with_narration: bool = True,
) -> Iterator[ProcessingContainer]:
    """Open a DB session and yield the wired persisted-pipeline container.

    The composition root for ``dl process``: builds the engine, ensures the schema
    exists, opens one short-lived session, wires one :class:`SqlModelRepository`
    per entity type onto it, assembles the stages (INGEST/SUMMARISE/RENDER, and
    NARRATE when ``with_narration`` and the ElevenLabs key are present), the STORE
    stage, and the orchestration service. Seeds the stock host/author voices.

    Args:
        settings: the application settings (constructed from the env if omitted).
        research_profile/output_profile: select named profiles (CLI overrides).
        with_narration: include the NARRATE stage (needs the ElevenLabs key). When
            the key is absent, narration is skipped (recorded SKIPPED) and the run
            still succeeds with the report (graceful degradation).

    Raises:
        ValueError: if ``ANTHROPIC_API_KEY`` is unset.
    """
    settings = settings or Settings()
    config = load_config(settings.config_file, research_override=research_profile, output_override=output_profile)

    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is not set; processing needs an Anthropic API key")

    cache_dir = settings.data_dir / "cache"
    extractor = PdfPlumberExtractor()
    llm = AnthropicLLMClient(
        api_key=settings.anthropic_api_key,
        model=config.summary.model.id,
        max_retries=settings.max_retries,
        timeout=settings.request_timeout,
    )
    store_fs = FilesystemArtifactStore(settings.data_dir)
    renderer = TypstRenderer(binary=settings.typst_binary)

    ingest = IngestStage(extractor, cache_dir=cache_dir)
    summarise = SummariseStage(llm, cache_dir=cache_dir, extractor=extractor)
    render = RenderStage(renderer, store_fs, llm=llm, cache_dir=cache_dir)

    narrate: NarrateStage | None = None
    if with_narration and settings.elevenlabs_api_key:
        narrate = build_narrate_stage(settings=settings, config=config)

    engine = create_db_engine(settings.database_url)
    create_all(engine)  # idempotent; a real deployment runs Alembic, this is the dev bootstrap
    clock = SystemClock()
    with Session(engine) as session:
        try:
            store_stage = StoreStage(
                papers=SqlModelRepository(session, Paper, clock=clock),
                summaries=SqlModelRepository(session, Summary, clock=clock),
                reports=SqlModelRepository(session, ReportAsset, clock=clock),
                episodes=SqlModelRepository(session, Episode, clock=clock),
                episode_papers=SqlModelRepository(session, EpisodePaper, clock=clock),
                podcasts=SqlModelRepository(session, PodcastAsset, clock=clock),
            )
            processing = ProcessingService(
                ingest=ingest,
                summarise=summarise,
                render=render,
                narrate=narrate,
                store=store_stage,
                papers=SqlModelRepository(session, Paper, clock=clock),
                runs=SqlModelRepository(session, PipelineRun, clock=clock),
                stage_runs=SqlModelRepository(session, StageRun, clock=clock),
                summaries=SqlModelRepository(session, Summary, clock=clock),
                clock=clock,
            )
            voices = VoicesService(SqlModelRepository(session, Voice, clock=clock))
            voices.seed_stock_voices(_stock_voice_specs(config))
            library = LibraryService(SqlModelRepository(session, Paper, clock=clock))
            yield ProcessingContainer(
                settings=settings,
                config=config,
                processing=processing,
                library=library,
                user_id=_DEFAULT_USER_ID,
            )
        finally:
            engine.dispose()


@contextmanager
def library_session(settings: Settings | None = None) -> Iterator[LibraryService]:
    """Open a DB session and yield a read-only-friendly :class:`LibraryService`.

    The composition root for ``dl library list`` / ``dl library show`` -- a thin
    session over the Paper repository, with no LLM/TTS adapters (so the library
    commands work without any API key). Ensures the schema exists for a fresh DB.
    """
    settings = settings or Settings()
    engine = create_db_engine(settings.database_url)
    create_all(engine)
    try:
        with Session(engine) as session:
            yield LibraryService(SqlModelRepository(session, Paper, clock=SystemClock()))
    finally:
        engine.dispose()


def _stock_voice_specs(config: DownLowConfig) -> list[StockVoiceSpec]:
    """The host + author stock voices to seed, from the config's [voices] mapping.

    Reads the configured provider voice ids (host/author) so the seeded pool matches
    what NARRATE resolves. A role with no configured voice is omitted (it is seeded
    once the owner sets it in the config file).
    """
    specs: list[StockVoiceSpec] = []
    host = config.narration.voice_for(SpeakerRole.HOST)
    if host:
        specs.append(
            StockVoiceSpec(
                provider="elevenlabs",
                provider_voice_id=host,
                role_hint=SpeakerRole.HOST,
                display_name="Host (stock)",
            )
        )
    author = config.narration.voice_for(SpeakerRole.AUTHOR)
    if author:
        specs.append(
            StockVoiceSpec(
                provider="elevenlabs",
                provider_voice_id=author,
                role_hint=SpeakerRole.AUTHOR,
                display_name="Author (stock)",
            )
        )
    return specs
