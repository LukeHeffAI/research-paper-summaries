"""Unit tests for the SqlModelRepository (Phase 2.0 persistence).

Real (temp-file) SQLite, no network: asserts the generic ``Repository`` port
honours its CRUD contract against pure ``domain.entities`` objects, that a row
never leaks (callers get entities back), that timestamps are stamped from the
injected clock (deterministic), and that the row<->entity mapping is faithful for
JSON-shaped fields, enum columns, and the Episode/EpisodePaper join.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session

from downlow.adapters.db.engine import create_db_engine
from downlow.adapters.db.repositories import SqlModelRepository
from downlow.domain.entities import (
    Episode,
    EpisodePaper,
    Paper,
    PipelineRun,
    StageRun,
    Summary,
    User,
    Voice,
)
from downlow.domain.enums import RunStatus, SpeakerRole, StageStatus, VoiceSource
from downlow.domain.ports import Clock, Repository
from tests.conftest import FrozenClock


def _user(db_session: Session, clock: Clock, *, username: str = "luke") -> User:
    """Insert and return a User (most entities need an owning user FK)."""
    repo: Repository[User] = SqlModelRepository(db_session, User, clock=clock)
    return repo.add(User(username=username, display_name="Luke"))


def test_add_assigns_id_and_stamps_created_at(db_session: Session, frozen_clock: FrozenClock) -> None:
    repo: Repository[User] = SqlModelRepository(db_session, User, clock=frozen_clock)
    saved = repo.add(User(username="luke"))

    assert isinstance(saved, User)  # an entity, not a row
    assert saved.id is not None
    assert saved.created_at == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_add_stamps_updated_at_when_the_entity_has_one(db_session: Session, frozen_clock: FrozenClock) -> None:
    user = _user(db_session, frozen_clock)
    repo: Repository[Paper] = SqlModelRepository(db_session, Paper, clock=frozen_clock)
    saved = repo.add(Paper(user_id=user.id or 0, title="A paper"))

    assert saved.created_at == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert saved.updated_at == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_cold_read_returns_tz_aware_utc_timestamps(db_session: Session, db_url: str, frozen_clock: FrozenClock) -> None:
    """The load-bearing claim: a value read back from SQLite is tz-aware UTC.

    The ``add()`` return value carries the clock's tz-aware instant and never
    touches the DB, so it cannot prove the read path. Here we ``add`` through one
    session, then open a SECOND engine on the same file -- a genuine cold read that
    bypasses the first session's identity map and forces SQLAlchemy to materialise
    the stored (naive) datetime. The ``_utc_aware`` / ``_row_dump`` re-attach-UTC
    path must turn it back into a tz-aware UTC value (matching Postgres, where the
    column is tz-aware natively).
    """
    repo: Repository[User] = SqlModelRepository(db_session, User, clock=frozen_clock)
    saved = repo.add(User(username="luke"))
    assert saved.id is not None
    db_session.close()  # drop the identity map so the next read hits the DB

    cold_engine = create_db_engine(db_url)
    try:
        with Session(cold_engine) as cold_session:
            cold_repo: Repository[User] = SqlModelRepository(cold_session, User, clock=frozen_clock)
            fetched = cold_repo.get(saved.id)
    finally:
        cold_engine.dispose()

    assert fetched is not None
    assert fetched.created_at is not None
    # tz-aware (not naive) AND a true UTC offset of zero, regardless of backend.
    assert fetched.created_at.tzinfo is not None
    assert fetched.created_at.utcoffset() == timedelta(0)
    # and the instant itself survived the round-trip.
    assert fetched.created_at == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_add_ignores_caller_supplied_id(db_session: Session, frozen_clock: FrozenClock) -> None:
    repo: Repository[User] = SqlModelRepository(db_session, User, clock=frozen_clock)
    saved = repo.add(User(id=999, username="luke"))
    assert saved.id == 1  # the store assigned it, not the caller's 999


def test_get_round_trips(db_session: Session, frozen_clock: FrozenClock) -> None:
    repo: Repository[User] = SqlModelRepository(db_session, User, clock=frozen_clock)
    saved = repo.add(User(username="luke", display_name="Luke"))
    assert saved.id is not None

    fetched = repo.get(saved.id)
    assert fetched is not None
    assert fetched.username == "luke"
    assert fetched.display_name == "Luke"


def test_get_returns_none_for_a_miss(db_session: Session, frozen_clock: FrozenClock) -> None:
    repo: Repository[User] = SqlModelRepository(db_session, User, clock=frozen_clock)
    assert repo.get(404) is None


def test_list_returns_all_in_pk_order(db_session: Session, frozen_clock: FrozenClock) -> None:
    repo: Repository[User] = SqlModelRepository(db_session, User, clock=frozen_clock)
    repo.add(User(username="a"))
    repo.add(User(username="b"))
    rows = repo.list()
    assert [u.username for u in rows] == ["a", "b"]


def test_list_filters_by_equality(db_session: Session, frozen_clock: FrozenClock) -> None:
    user = _user(db_session, frozen_clock)
    other = _user(db_session, frozen_clock, username="other")
    papers: Repository[Paper] = SqlModelRepository(db_session, Paper, clock=frozen_clock)
    papers.add(Paper(user_id=user.id or 0, title="mine-1"))
    papers.add(Paper(user_id=user.id or 0, title="mine-2"))
    papers.add(Paper(user_id=other.id or 0, title="theirs"))

    mine = papers.list(user_id=user.id)
    assert {p.title for p in mine} == {"mine-1", "mine-2"}


def test_list_rejects_unknown_filter(db_session: Session, frozen_clock: FrozenClock) -> None:
    repo: Repository[User] = SqlModelRepository(db_session, User, clock=frozen_clock)
    with pytest.raises(ValueError, match="unknown filter field"):
        repo.list(nope="x")


def test_delete_removes_and_reports(db_session: Session, frozen_clock: FrozenClock) -> None:
    repo: Repository[User] = SqlModelRepository(db_session, User, clock=frozen_clock)
    saved = repo.add(User(username="luke"))
    assert saved.id is not None

    assert repo.delete(saved.id) is True
    assert repo.get(saved.id) is None
    assert repo.delete(saved.id) is False  # idempotent: nothing left to delete


# --------------------------------------------------------------------------- #
# row <-> entity mapping fidelity                                               #
# --------------------------------------------------------------------------- #


def test_json_list_fields_round_trip(db_session: Session, frozen_clock: FrozenClock) -> None:
    user = _user(db_session, frozen_clock)
    repo: Repository[Paper] = SqlModelRepository(db_session, Paper, clock=frozen_clock)
    saved = repo.add(
        Paper(
            user_id=user.id or 0,
            title="Attention",
            authors=["Ada Lovelace", "Alan Turing"],
            page_count=12,
        )
    )
    assert saved.id is not None

    fetched = repo.get(saved.id)
    assert fetched is not None
    assert fetched.authors == ["Ada Lovelace", "Alan Turing"]
    assert fetched.page_count == 12


def test_summary_structured_json_round_trips(db_session: Session, frozen_clock: FrozenClock) -> None:
    user = _user(db_session, frozen_clock)
    papers: Repository[Paper] = SqlModelRepository(db_session, Paper, clock=frozen_clock)
    paper = papers.add(Paper(user_id=user.id or 0, title="A paper"))

    repo: Repository[Summary] = SqlModelRepository(db_session, Summary, clock=frozen_clock)
    saved = repo.add(
        Summary(
            paper_id=paper.id or 0,
            overall_summary="It works.",
            key_findings=[{"statement": "X improves Y", "evidence": "+3% acc"}],
            contributions=["a method"],
            gaps_and_limitations=["small N"],
            methods="ablation",
            content_hash="abc",
        )
    )
    assert saved.id is not None

    fetched = repo.get(saved.id)
    assert fetched is not None
    assert fetched.key_findings == [{"statement": "X improves Y", "evidence": "+3% acc"}]
    assert fetched.contributions == ["a method"]
    assert fetched.content_hash == "abc"


def test_enum_column_round_trips(db_session: Session, frozen_clock: FrozenClock) -> None:
    repo: Repository[Voice] = SqlModelRepository(db_session, Voice, clock=frozen_clock)
    saved = repo.add(
        Voice(
            provider="elevenlabs",
            provider_voice_id="v-123",
            source=VoiceSource.STOCK,
            role_hint=SpeakerRole.HOST,
            display_name="The Host",
        )
    )
    assert saved.id is not None

    fetched = repo.get(saved.id)
    assert fetched is not None
    assert fetched.source is VoiceSource.STOCK
    assert fetched.role_hint is SpeakerRole.HOST


def test_run_and_stage_provenance_round_trip(db_session: Session, frozen_clock: FrozenClock) -> None:
    user = _user(db_session, frozen_clock)
    papers: Repository[Paper] = SqlModelRepository(db_session, Paper, clock=frozen_clock)
    paper = papers.add(Paper(user_id=user.id or 0, title="A paper"))

    runs: Repository[PipelineRun] = SqlModelRepository(db_session, PipelineRun, clock=frozen_clock)
    run = runs.add(
        PipelineRun(
            paper_id=paper.id or 0,
            status=RunStatus.RUNNING,
            requested_stages=["ingest", "summarise"],
        )
    )
    assert run.id is not None
    assert run.requested_stages == ["ingest", "summarise"]

    stages: Repository[StageRun] = SqlModelRepository(db_session, StageRun, clock=frozen_clock)
    stage = stages.add(
        StageRun(
            run_id=run.id,
            stage_name="ingest",
            status=StageStatus.SUCCEEDED,
            cache_hit=True,
        )
    )
    assert stage.id is not None

    fetched = stages.get(stage.id)
    assert fetched is not None
    assert fetched.status is StageStatus.SUCCEEDED
    assert fetched.cache_hit is True
    assert stages.list(run_id=run.id)[0].stage_name == "ingest"


def test_episode_episode_paper_join_round_trips(db_session: Session, frozen_clock: FrozenClock) -> None:
    """The multi-paper-ready join: one Episode, two ordered EpisodePaper rows."""
    user = _user(db_session, frozen_clock)
    papers: Repository[Paper] = SqlModelRepository(db_session, Paper, clock=frozen_clock)
    p1 = papers.add(Paper(user_id=user.id or 0, title="P1"))
    p2 = papers.add(Paper(user_id=user.id or 0, title="P2"))

    episodes: Repository[Episode] = SqlModelRepository(db_session, Episode, clock=frozen_clock)
    episode = episodes.add(Episode(user_id=user.id or 0, title="Ep 1", status=RunStatus.PENDING))
    assert episode.id is not None

    join: Repository[EpisodePaper] = SqlModelRepository(db_session, EpisodePaper, clock=frozen_clock)
    join.add(EpisodePaper(episode_id=episode.id, paper_id=p1.id or 0, order=0))
    join.add(EpisodePaper(episode_id=episode.id, paper_id=p2.id or 0, order=1))

    members = join.list(episode_id=episode.id)
    assert [(m.paper_id, m.order) for m in members] == [(p1.id, 0), (p2.id, 1)]


def test_two_repos_share_one_session(db_session: Session, frozen_clock: FrozenClock) -> None:
    """Distinct entity-typed repos over the same session see each other's writes."""
    users: Repository[User] = SqlModelRepository(db_session, User, clock=frozen_clock)
    papers: Repository[Paper] = SqlModelRepository(db_session, Paper, clock=frozen_clock)
    user = users.add(User(username="luke"))
    papers.add(Paper(user_id=user.id or 0, title="A paper"))

    assert users.list()[0].username == "luke"
    assert papers.list()[0].title == "A paper"
