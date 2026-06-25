"""SQLModel ``table=True`` rows -- the DB schema, and the only place it lives.

The single layer where ``sqlmodel`` / ``sqlalchemy`` appear for persistence. Each
table maps 1:1 to a pure :mod:`downlow.domain.entities` entity; ``to_entity`` /
``from_entity`` helpers convert between the two so a row never leaks past this
adapter (``core`` and the :class:`~downlow.domain.ports.Repository` port see only
the pure pydantic entities).

SQLite now, Postgres-ready (PROJECT_PLAN -> Data Model):

* integer surrogate primary keys, timezone-aware ``datetime`` columns;
* enums stored as their ``str`` value via a portable ``String`` column (not a
  native DB ``ENUM`` type, which SQLite lacks and Postgres makes migration-heavy);
* list/dict fields stored in portable ``JSON`` columns
  (``sqlalchemy.JSON`` works on both backends), declared with ``sa_column`` so
  SQLModel does not try to map a ``list[str]`` to a scalar;
* explicit status enums on the run/stage tables rather than the legacy "which
  nullable column is populated" convention.

Alembic owns migrations; this metadata (``SQLModel.metadata``) is the autogenerate
target. ``ALL_TABLES`` is the registry the engine / migration env import so every
table is registered before ``metadata`` is read.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum as PyEnum
from typing import Any, cast

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel

from downlow.domain.entities import (
    Episode,
    EpisodePaper,
    OutputProfileRecord,
    Paper,
    PipelineRun,
    PodcastAsset,
    ReportAsset,
    ResearchProfileRecord,
    Setting,
    StageRun,
    Summary,
    User,
    Voice,
)
from downlow.domain.enums import RunStatus, SpeakerRole, StageStatus, VoiceSource

# A reusable JSON column factory. ``Column(JSON)`` is portable across SQLite and
# Postgres; a fresh ``Column`` per field avoids sharing one instance between tables.


def _json_column() -> Any:
    return Field(default_factory=list, sa_column=Column(JSON, nullable=False))


def _json_dict_column() -> Any:
    return Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


# Enum columns: SQLAlchemy ``Enum(..., native_enum=False)`` renders as a portable
# VARCHAR (not a native DB ENUM, which SQLite lacks and Postgres makes
# migration-heavy) and handles the enum <-> string conversion in both directions,
# so a row carries the real Python enum (no pydantic serialization warning) while
# the column stays portable. ``values_callable`` stores the StrEnum *value*
# ("pending"), not its name.


def _enum_column(enum_type: type[PyEnum], default: Any, *, nullable: bool = False) -> Any:
    sa_type = SAEnum(
        enum_type,
        native_enum=False,
        values_callable=lambda e: [member.value for member in e],
    )
    return Field(default=default, sa_column=Column(sa_type, nullable=nullable))


# Timestamp columns: ``DateTime(timezone=True)`` so Postgres stores tz-aware UTC.
# SQLite has no tz storage and returns naive datetimes; the row -> entity mapping
# re-attaches UTC (see ``_utc_aware``) so the value is tz-aware UTC on both
# backends -- the timestamps go in as tz-aware UTC and come back the same.


def _ts_column(*, nullable: bool = True) -> Any:
    return Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=nullable))


def _utc_aware(value: Any) -> Any:
    """Re-attach UTC to a naive datetime (SQLite returns naive; Postgres tz-aware).

    Applied to every column value in the row -> entity mapping so timestamps come
    back tz-aware UTC regardless of backend; non-datetime values pass through.
    """
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _row_dump(row: SQLModel) -> dict[str, Any]:
    """A row's field dict with naive datetimes promoted to tz-aware UTC.

    The single chokepoint the ``to_entity`` helpers use so a SQLite-naive timestamp
    is normalised once, in one place, before it validates into a pure entity.
    """
    return {field: _utc_aware(value) for field, value in row.model_dump().items()}


# --------------------------------------------------------------------------- #
# Identity / profiles                                                           #
# --------------------------------------------------------------------------- #


class UserRow(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    display_name: str = Field(default="")
    # user <-> voice is a mutual FK (a user has a host Voice; a Voice has an owning
    # user). ``use_alter=True`` adds this FK as a post-create ``ALTER`` so the two
    # tables have no circular create-order dependency (which SAWarning flags as a
    # future hard error). ``voice.user_id`` keeps its plain FK; this one defers.
    host_voice_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("voice.id", use_alter=True, name="fk_user_host_voice_id"),
            nullable=True,
        ),
    )
    created_at: datetime | None = _ts_column()

    def to_entity(self) -> User:
        return User.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: User) -> UserRow:
        return cls(**entity.model_dump())


class ResearchProfileRow(SQLModel, table=True):
    __tablename__ = "research_profile"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    research_field: str = Field(default="")
    research_topic: str = Field(default="")
    research_interests: list[str] = _json_column()
    research_focus: str = Field(default="")
    created_at: datetime | None = _ts_column()
    updated_at: datetime | None = _ts_column()

    def to_entity(self) -> ResearchProfileRecord:
        return ResearchProfileRecord.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: ResearchProfileRecord) -> ResearchProfileRow:
        return cls(**entity.model_dump())


class OutputProfileRow(SQLModel, table=True):
    __tablename__ = "output_profile"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = Field(default="")
    document_type: str = Field(default="")
    return_details: list[str] = _json_column()
    created_at: datetime | None = _ts_column()

    def to_entity(self) -> OutputProfileRecord:
        return OutputProfileRecord.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: OutputProfileRecord) -> OutputProfileRow:
        return cls(**entity.model_dump())


# --------------------------------------------------------------------------- #
# Library: papers + derived assets                                              #
# --------------------------------------------------------------------------- #


class PaperRow(SQLModel, table=True):
    __tablename__ = "paper"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(default="")
    source_pdf_ref: str = Field(default="")
    source_hash: str = Field(default="", index=True)
    extracted_text_ref: str | None = Field(default=None)
    page_count: int | None = Field(default=None)
    authors: list[str] = _json_column()
    doi: str | None = Field(default=None)
    author_voice_id: int | None = Field(default=None, foreign_key="voice.id")
    chosen_profile_id: int | None = Field(default=None, foreign_key="research_profile.id")
    created_at: datetime | None = _ts_column()
    updated_at: datetime | None = _ts_column()

    def to_entity(self) -> Paper:
        return Paper.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: Paper) -> PaperRow:
        return cls(**entity.model_dump())


class SummaryRow(SQLModel, table=True):
    __tablename__ = "summary"

    id: int | None = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    overall_summary: str = Field(default="")
    key_findings: list[dict[str, Any]] = _json_column()
    contributions: list[str] = _json_column()
    gaps_and_limitations: list[str] = _json_column()
    methods: str = Field(default="")
    relevance_to_profile: str = Field(default="")
    model_id: str = Field(default="")
    prompt_version: str = Field(default="")
    content_hash: str = Field(default="", index=True)
    profile_hash: str = Field(default="")
    created_at: datetime | None = _ts_column()

    def to_entity(self) -> Summary:
        return Summary.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: Summary) -> SummaryRow:
        return cls(**entity.model_dump())


class ReportAssetRow(SQLModel, table=True):
    __tablename__ = "report_asset"

    id: int | None = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    run_id: int | None = Field(default=None, foreign_key="pipeline_run.id")
    pdf_ref: str = Field(default="")
    filename: str = Field(default="")
    template_version: str = Field(default="")
    created_at: datetime | None = _ts_column()

    def to_entity(self) -> ReportAsset:
        return ReportAsset.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: ReportAsset) -> ReportAssetRow:
        return cls(**entity.model_dump())


# --------------------------------------------------------------------------- #
# Episodes + podcast assets                                                      #
# --------------------------------------------------------------------------- #


class EpisodeRow(SQLModel, table=True):
    __tablename__ = "episode"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(default="")
    status: RunStatus = _enum_column(RunStatus, RunStatus.PENDING)
    created_at: datetime | None = _ts_column()

    def to_entity(self) -> Episode:
        return Episode.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: Episode) -> EpisodeRow:
        return cls(**entity.model_dump())


class EpisodePaperRow(SQLModel, table=True):
    __tablename__ = "episode_paper"
    __table_args__ = (UniqueConstraint("episode_id", "paper_id", name="uq_episode_paper"),)

    id: int | None = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id", index=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    order: int = Field(default=0)

    def to_entity(self) -> EpisodePaper:
        return EpisodePaper.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: EpisodePaper) -> EpisodePaperRow:
        return cls(**entity.model_dump())


class PodcastAssetRow(SQLModel, table=True):
    __tablename__ = "podcast_asset"

    id: int | None = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id", index=True)
    mp3_ref: str = Field(default="")
    narration_script: dict[str, Any] = _json_dict_column()
    host_voice_id: int | None = Field(default=None, foreign_key="voice.id")
    model_id: str = Field(default="")
    duration_seconds: float | None = Field(default=None)
    created_at: datetime | None = _ts_column()

    def to_entity(self) -> PodcastAsset:
        return PodcastAsset.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: PodcastAsset) -> PodcastAssetRow:
        return cls(**entity.model_dump())


# --------------------------------------------------------------------------- #
# Pipeline provenance                                                            #
# --------------------------------------------------------------------------- #


class PipelineRunRow(SQLModel, table=True):
    __tablename__ = "pipeline_run"

    id: int | None = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id", index=True)
    status: RunStatus = _enum_column(RunStatus, RunStatus.PENDING)
    requested_stages: list[str] = _json_column()
    error: str | None = Field(default=None)
    created_at: datetime | None = _ts_column()
    started_at: datetime | None = _ts_column()
    finished_at: datetime | None = _ts_column()

    def to_entity(self) -> PipelineRun:
        return PipelineRun.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: PipelineRun) -> PipelineRunRow:
        return cls(**entity.model_dump())


class StageRunRow(SQLModel, table=True):
    __tablename__ = "stage_run"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="pipeline_run.id", index=True)
    stage_name: str = Field(default="")
    status: StageStatus = _enum_column(StageStatus, StageStatus.PENDING)
    cache_hit: bool = Field(default=False)
    model_id: str | None = Field(default=None)
    output_ref: str | None = Field(default=None)
    error: str | None = Field(default=None)
    started_at: datetime | None = _ts_column()
    finished_at: datetime | None = _ts_column()

    def to_entity(self) -> StageRun:
        return StageRun.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: StageRun) -> StageRunRow:
        return cls(**entity.model_dump())


# --------------------------------------------------------------------------- #
# Voices                                                                         #
# --------------------------------------------------------------------------- #


class VoiceRow(SQLModel, table=True):
    __tablename__ = "voice"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id")
    provider: str = Field(default="elevenlabs")
    provider_voice_id: str = Field(default="")
    source: VoiceSource = _enum_column(VoiceSource, VoiceSource.STOCK)
    display_name: str = Field(default="")
    role_hint: SpeakerRole | None = _enum_column(SpeakerRole, None, nullable=True)
    sample_recording_ref: str | None = Field(default=None)
    consent_granted: bool = Field(default=False)
    consent_owner: str | None = Field(default=None)
    consent_recorded_at: datetime | None = _ts_column()
    created_at: datetime | None = _ts_column()

    def to_entity(self) -> Voice:
        return Voice.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: Voice) -> VoiceRow:
        return cls(**entity.model_dump())


# --------------------------------------------------------------------------- #
# Settings registry                                                             #
# --------------------------------------------------------------------------- #


class SettingRow(SQLModel, table=True):
    __tablename__ = "setting"

    id: int | None = Field(default=None, primary_key=True)
    key: str = Field(index=True, unique=True)
    value: str = Field(default="")
    created_at: datetime | None = _ts_column()
    updated_at: datetime | None = _ts_column()

    def to_entity(self) -> Setting:
        return Setting.model_validate(_row_dump(self))

    @classmethod
    def from_entity(cls, entity: Setting) -> SettingRow:
        return cls(**entity.model_dump())


# The registry every table row class belongs to. Importing this module registers
# all tables on ``SQLModel.metadata`` (the Alembic autogenerate target). The map
# also drives :class:`~downlow.adapters.db.repositories.SqlModelRepository`'s
# entity-type -> row-type lookup.
ENTITY_TO_ROW: dict[type[Any], type[SQLModel]] = {
    User: UserRow,
    ResearchProfileRecord: ResearchProfileRow,
    OutputProfileRecord: OutputProfileRow,
    Paper: PaperRow,
    Summary: SummaryRow,
    ReportAsset: ReportAssetRow,
    Episode: EpisodeRow,
    EpisodePaper: EpisodePaperRow,
    PodcastAsset: PodcastAssetRow,
    PipelineRun: PipelineRunRow,
    StageRun: StageRunRow,
    Voice: VoiceRow,
    Setting: SettingRow,
}

ALL_TABLES: tuple[type[SQLModel], ...] = tuple(ENTITY_TO_ROW.values())


def metadata() -> Any:
    """The SQLModel metadata holding every table (Alembic's autogenerate target).

    A function (not a bare module attr) so importing it forces this module -- and
    therefore every ``table=True`` class above -- to be evaluated and registered
    first. The cast keeps mypy happy about SQLModel's loosely-typed ``metadata``.
    """
    return cast(Any, SQLModel.metadata)
