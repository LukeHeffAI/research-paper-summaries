"""Shared test fixtures.

Includes the F1-F4 fakes (``fake_llm``, ``fake_tts``, ``fake_renderer``,
``fake_mixer``) and the Phase 2.0 persistence fixtures: a DB engine with the schema
created (``db_engine``), a session bound to it (``db_session``), and a frozen
:class:`~downlow.domain.ports.Clock` so timestamps are deterministic.

**Backend-agnostic (Phase 2.2 — Postgres-readiness).** The DB fixtures are driven
by the ``DATABASE_URL`` environment variable so the *same* tests run on both
backends, proving ``core`` + the schema + the migrations are portable:

* unset / SQLite ``DATABASE_URL`` -> a per-test temp-file SQLite DB (the local
  default; no Postgres needed, so a developer with no Postgres stays green);
* a ``postgresql+psycopg://...`` ``DATABASE_URL`` -> that Postgres server, with a
  clean (all-tables-dropped) schema per test for isolation (CI's Postgres job).

The Postgres proof is the CI ``test-postgres`` job; locally these run on SQLite.
See :func:`_clean_postgres_schema` for how per-test isolation is achieved on a
shared Postgres server.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session

from downlow.adapters.db.engine import create_all, create_db_engine
from downlow.config.settings import Settings

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _env_database_url() -> str | None:
    """The ``DATABASE_URL`` override, or ``None`` to use a per-test temp SQLite DB.

    An empty / unset value (or an explicit SQLite URL) means "use the default
    temp-file SQLite path", so a developer with no Postgres stays on SQLite.
    """
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return None
    return url


def _is_postgres(url: str) -> bool:
    """True when ``url`` targets a PostgreSQL backend."""
    return make_url(url).get_backend_name() == "postgresql"


def _clean_postgres_schema(engine: Engine) -> None:
    """Drop everything in the ``public`` schema so each Postgres test starts clean.

    Postgres (unlike a per-test temp SQLite file) is a single shared server, so
    isolation is achieved by recreating an empty ``public`` schema before the test
    builds its tables. ``DROP SCHEMA ... CASCADE`` also clears any leftover
    ``alembic_version`` row so a migration-driven test re-applies from base.
    """
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="session", autouse=True)
def _require_postgres_when_ci_demands_it() -> None:
    """Fail loudly if the CI Postgres job is not actually running on Postgres (S2).

    The ``test-postgres`` CI job sets ``DOWNLOW_REQUIRE_POSTGRES=1``. When that flag
    is present this guard asserts ``DATABASE_URL`` genuinely resolves to a
    ``postgresql`` backend, so a future env regression (a dropped/typo'd
    ``DATABASE_URL``) cannot let the job silently fall back to SQLite and pass a
    hollow "Postgres" proof. The flag is unset locally, so this never trips a
    developer's SQLite run.
    """
    if os.environ.get("DOWNLOW_REQUIRE_POSTGRES", "").strip() not in {"", "0", "false"}:
        url = _env_database_url()
        assert url is not None and _is_postgres(url), (
            "DOWNLOW_REQUIRE_POSTGRES is set (CI Postgres job) but DATABASE_URL does not "
            f"resolve to postgresql (got {url!r}); refusing to pass a hollow Postgres proof."
        )


@pytest.fixture
def settings() -> Settings:
    """A Settings instance with defaults and no real credentials."""
    return Settings(anthropic_api_key=None, elevenlabs_api_key=None)


@pytest.fixture
def sample_pdf() -> Path:
    """Path to the committed tiny one-page PDF with known text (F1 integration)."""
    return FIXTURES_DIR / "sample.pdf"


class FrozenClock:
    """A :class:`~downlow.domain.ports.Clock` pinned to one instant (deterministic)."""

    def __init__(self, instant: datetime | None = None) -> None:
        self._instant = instant or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._instant


@pytest.fixture
def frozen_clock() -> FrozenClock:
    """A clock fixed at 2026-01-01T12:00:00Z for deterministic timestamp asserts."""
    return FrozenClock()


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    """The DB URL for this test (backend-agnostic; see module docstring).

    ``DATABASE_URL`` (a ``postgresql+psycopg://...`` URL) wins so the same tests run
    on Postgres in CI; otherwise a per-test *file* SQLite DB (not ``:memory:``) so a
    second engine -- a genuine cold read -- sees the same data and bypasses the first
    session's identity map. Both backends honour the "open a second engine on the
    same URL" pattern the cold-read test relies on.
    """
    return _env_database_url() or f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def db_engine(db_url: str) -> Iterator[Engine]:
    """An engine with the full schema created (no Alembic), on SQLite or Postgres.

    On Postgres the ``public`` schema is dropped + recreated first so each test
    starts from an empty DB (the per-test temp file gives SQLite that for free).
    """
    engine = create_db_engine(db_url)
    if _is_postgres(db_url):
        _clean_postgres_schema(engine)
    create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """A SQLModel session bound to the temp DB engine."""
    with Session(db_engine) as session:
        yield session
