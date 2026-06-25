"""Persisted domain entities -- the pure pydantic view of every DB row.

PURE: pydantic + stdlib + ``domain`` only. No SQLModel ``table=True``, no
``sqlalchemy``, no engine. These are the objects ``core`` works with through the
:class:`~downlow.domain.ports.Repository` port; the SQLModel rows that actually
persist them live in ``adapters/db/tables.py`` and never leak past that adapter,
which maps row <-> entity.

Why a separate module from ``schemas.py``? ``schemas.py`` holds the *stage I/O*
DTOs (``ExtractedText``, ``PaperSummary``, ``NarrationScript`` ...) -- the wire
objects that flow between pipeline stages and are Claude structured-output
targets. The entities here are the *persistence* model -- the library's durable
nouns (Paper, the run/stage provenance, the stored Summary/asset rows, voices,
profiles, settings). DB rows are deliberately not the same objects as the
wire/domain DTOs (see PROJECT_PLAN -> Data Model), so they live apart.

Provider-agnostic ids: every entity carries an ``id: int | None`` (``None`` before
insert, assigned by the store on ``add``). Timestamps are timezone-aware UTC and
are stamped by the adapter from an injected :class:`~downlow.domain.ports.Clock`,
not read from the wall clock inside ``core`` -- so snapshot tests and cache keys
stay deterministic. JSON-shaped columns (author lists, structured summary fields,
the narration-script blob) are modelled here as plain Python ``list``/``dict``;
the adapter maps them onto portable JSON columns that work on SQLite and Postgres
alike.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from downlow.domain.enums import RunStatus, SpeakerRole, StageStatus, VoiceSource

# --------------------------------------------------------------------------- #
# Identity / profiles                                                          #
# --------------------------------------------------------------------------- #


class User(BaseModel):
    """The library owner. Single-user now; the columns let multi-user + auth slot
    in without a foreign-key migration (no password/JWT this phase).
    """

    id: int | None = None
    username: str = Field(description="Unique login handle.")
    display_name: str = Field(default="", description="Human-friendly name for the UI.")
    host_voice_id: int | None = Field(default=None, description="The user's designated consistent host Voice (FK).")
    created_at: datetime | None = None


class ResearchProfileRecord(BaseModel):
    """Persisted research identity (replaces ``data/research_data.json``).

    Distinct from the pure steering DTO ``schemas.ResearchProfile``: this is the
    durable row (ids, ``user_id``, timestamps); the DTO is what the SUMMARISE
    prompt assembler consumes. One active profile per user steers summarisation.
    """

    id: int | None = None
    user_id: int = Field(description="Owning user (FK).")
    research_field: str = ""
    research_topic: str = ""
    research_interests: list[str] = Field(default_factory=list)
    research_focus: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OutputProfileRecord(BaseModel):
    """Persisted output-shape steering (replaces ``data/document_data.json``).

    Kept apart from :class:`ResearchProfileRecord` because document shape and
    researcher identity vary independently (one researcher, many output formats).
    """

    id: int | None = None
    user_id: int = Field(description="Owning user (FK).")
    name: str = ""
    document_type: str = ""
    return_details: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Library: papers + their derived assets                                        #
# --------------------------------------------------------------------------- #


class Paper(BaseModel):
    """A paper in the library. Per-stage lifecycle is NOT inferred from nullable
    columns here -- it lives on :class:`PipelineRun` / :class:`StageRun`, so
    ``failed`` is distinguishable from ``not-yet-run``.
    """

    id: int | None = None
    user_id: int = Field(description="Owning user (FK).")
    title: str = ""
    source_pdf_ref: str = Field(default="", description="ArtifactStore reference to the ingested source PDF.")
    source_hash: str = Field(default="", description="sha256 of the raw PDF bytes (dedupe / extraction cache key).")
    extracted_text_ref: str | None = Field(default=None, description="ArtifactStore reference to the extracted text.")
    page_count: int | None = None
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    author_voice_id: int | None = Field(default=None, description="Per-paper author Voice (FK).")
    chosen_profile_id: int | None = Field(default=None, description="ResearchProfile used to steer this paper (FK).")
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Summary(BaseModel):
    """The persisted SUMMARISE output (the DB row for a ``schemas.PaperSummary``).

    Structured fields (not one text blob) so RENDER/NARRATE consume typed data.
    ``model_id`` + ``prompt_version`` + the two hashes make regeneration and cache
    invalidation explicit.
    """

    id: int | None = None
    paper_id: int = Field(description="The summarised paper (FK).")
    overall_summary: str = ""
    key_findings: list[dict[str, object]] = Field(default_factory=list, description="Serialised KeyFinding objects.")
    contributions: list[str] = Field(default_factory=list)
    gaps_and_limitations: list[str] = Field(default_factory=list)
    methods: str = ""
    relevance_to_profile: str = ""
    model_id: str = ""
    prompt_version: str = ""
    content_hash: str = ""
    profile_hash: str = ""
    created_at: datetime | None = None


class ReportAsset(BaseModel):
    """A Typst-rendered report PDF. Separate table because one paper may have
    several renders over time (different templates / summaries).
    """

    id: int | None = None
    paper_id: int = Field(description="The paper this report renders (FK).")
    run_id: int | None = Field(default=None, description="The PipelineRun that produced it (FK), if any.")
    pdf_ref: str = Field(default="", description="ArtifactStore reference to the compiled PDF.")
    filename: str = ""
    template_version: str = ""
    created_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Episodes + podcast assets (multi-paper-ready)                                  #
# --------------------------------------------------------------------------- #


class Episode(BaseModel):
    """A podcast episode. Owns the script + audio and references 1..N papers via
    :class:`EpisodePaper`. Single-paper ships now (one ``EpisodePaper`` row);
    themed multi-paper episodes are a population change, not a schema rewrite.
    """

    id: int | None = None
    user_id: int = Field(description="Owning user (FK).")
    title: str = ""
    status: RunStatus = RunStatus.PENDING
    created_at: datetime | None = None


class EpisodePaper(BaseModel):
    """The ordered join between an :class:`Episode` and its source :class:`Paper`(s)."""

    id: int | None = None
    episode_id: int = Field(description="The episode (FK).")
    paper_id: int = Field(description="A source paper of the episode (FK).")
    order: int = Field(default=0, description="Position of this paper within the episode.")


class PodcastAsset(BaseModel):
    """The stitched episode mp3 + its regenerable :class:`NarrationScript` blob.

    On ``episode_id`` (not paper) so a multi-paper episode resolves multiple author
    voices. The host voice is one consistent stock voice; each author voice is
    per-paper on :class:`Paper`. Storing the script makes the mp3 reproducible and
    the per-turn transcript inspectable.
    """

    id: int | None = None
    episode_id: int = Field(description="The episode this audio belongs to (FK).")
    mp3_ref: str = Field(default="", description="ArtifactStore reference to the stitched mp3.")
    narration_script: dict[str, object] = Field(
        default_factory=dict,
        description="The serialised NarrationScript (ordered turns + voices + cues).",
    )
    host_voice_id: int | None = Field(default=None, description="The host Voice used (FK).")
    model_id: str = ""
    duration_seconds: float | None = None
    created_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Pipeline provenance (the Job abstraction)                                      #
# --------------------------------------------------------------------------- #


class PipelineRun(BaseModel):
    """One processing invocation over a paper (the Job abstraction). The
    sync-now / async-later boundary: today the CLI runs it inline; tomorrow a
    FastAPI route enqueues ``status=pending`` and a worker advances it.
    """

    id: int | None = None
    paper_id: int = Field(description="The paper being processed (FK).")
    status: RunStatus = RunStatus.PENDING
    requested_stages: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class StageRun(BaseModel):
    """Per-stage status of a :class:`PipelineRun`. A child table (not columns on
    Paper) so it keeps history, supports re-processing, and is the async-later
    boundary where a worker claims / advances individual stages.
    """

    id: int | None = None
    run_id: int = Field(description="The owning PipelineRun (FK).")
    stage_name: str = ""
    status: StageStatus = StageStatus.PENDING
    cache_hit: bool = False
    model_id: str | None = None
    output_ref: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Voices                                                                         #
# --------------------------------------------------------------------------- #


class Voice(BaseModel):
    """A voice in the pool: stock (used now for host + author roles) or cloned
    (FUTURE). One table -- a cloned voice is just a Voice with ``source=cloned`` and
    populated sample/consent fields, no parallel hierarchy.
    """

    id: int | None = None
    user_id: int | None = Field(default=None, description="Owner; None for shared stock voices.")
    provider: str = Field(default="elevenlabs", description="The TTS provider this voice id belongs to.")
    provider_voice_id: str = ""
    source: VoiceSource = VoiceSource.STOCK
    display_name: str = ""
    role_hint: SpeakerRole | None = Field(
        default=None, description="The role this voice is intended for (host|author)."
    )
    # --- cloning / consent (FUTURE-populated) ---
    sample_recording_ref: str | None = None
    consent_granted: bool = False
    consent_owner: str | None = None
    consent_recorded_at: datetime | None = None
    created_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Settings registry                                                             #
# --------------------------------------------------------------------------- #


class Setting(BaseModel):
    """A DB-backed tunable (key/value). Seeded from the config file later; the
    config file stays the fallback/default. The graduation path for a knob is
    config default -> DB override -> UI control, no code change.
    """

    id: int | None = None
    key: str = Field(description="The setting key (unique).")
    value: str = Field(default="", description="The serialised setting value.")
    created_at: datetime | None = None
    updated_at: datetime | None = None
