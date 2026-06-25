"""SQLModel engine + session factory + ``get_session``.

The only place a SQLAlchemy ``Engine`` / ``Session`` is constructed. Driven by a
``DATABASE_URL`` (SQLite now, e.g. ``sqlite:///./data/downlow.db``; Postgres-ready
-- flip the URL to ``postgresql+psycopg://...`` with no code change).

SQLite gets two dialect-specific touches applied *only* when the URL is SQLite, so
nothing here is a SQLite-only assumption that would break on Postgres:

* ``connect_args={"check_same_thread": False}`` -- the ``ThreadPoolExecutor``
  fan-out (Concurrency & Performance) shares a connection pool across threads;
* a ``PRAGMA foreign_keys=ON`` per-connection -- SQLite does not enforce foreign
  keys unless asked, so the FKs the schema declares are actually checked (Postgres
  enforces them natively, so the pragma is scoped to SQLite).

Postgres needs no special-casing here: a ``postgresql+psycopg://...`` URL (psycopg3,
the ``postgres`` optional-dependency extra) is created with default ``connect_args``
and the stdlib connection pool, so the same ``create_db_engine`` call serves both
backends after a ``DATABASE_URL`` flip. ``psycopg`` enforces FKs and stores tz-aware
timestamps natively, so neither SQLite tweak applies.

Importing this module pulls in :mod:`downlow.adapters.db.tables`, registering every
``table=True`` row on ``SQLModel.metadata`` before any ``create_all`` /
autogenerate reads it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Session, create_engine

import downlow.adapters.db.tables as tables


def _is_sqlite(database_url: str) -> bool:
    """True when ``database_url`` targets SQLite (drives dialect-scoped tweaks)."""
    return make_url(database_url).get_backend_name() == "sqlite"


def create_db_engine(database_url: str, *, echo: bool = False) -> Engine:
    """Create the SQLAlchemy engine for ``database_url``.

    Applies SQLite-only connection tweaks (cross-thread sharing + FK enforcement)
    when the URL is SQLite; for any other backend (Postgres) the engine is created
    with defaults, so the same call works unchanged after a ``DATABASE_URL`` flip.

    Args:
        database_url: a SQLAlchemy URL (``sqlite:///...`` now, ``postgresql+...``
            later).
        echo: log emitted SQL (debugging only).
    """
    connect_args: dict[str, Any] = {}
    if _is_sqlite(database_url):
        connect_args["check_same_thread"] = False

    engine = create_engine(database_url, echo=echo, connect_args=connect_args)

    if _is_sqlite(database_url):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_fk(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_all(engine: Engine) -> None:
    """Create every table on the engine (test/bootstrap convenience).

    Production schema changes go through Alembic; this is for tests and a quick
    bootstrap where running migrations is unnecessary.
    """
    tables.metadata().create_all(engine)


def session_factory(engine: Engine) -> Any:
    """A ``Session``-yielding factory bound to ``engine`` (callable -> context mgr)."""

    @contextmanager
    def _factory() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    return _factory


@contextmanager
def get_session(engine: Engine) -> Iterator[Session]:
    """A short-lived transactional :class:`Session` bound to ``engine``.

    The composition root (CLI now, a FastAPI dependency later, a worker later still)
    opens one of these per unit of work and hands it to the repositories. Keeping
    sessions short matters under SQLite's single-writer lock (Concurrency notes).
    """
    with Session(engine) as session:
        yield session


class SystemClock:
    """A real UTC :class:`~downlow.domain.ports.Clock`.

    Lives in the adapter layer (where touching the wall clock is allowed) so
    ``core`` and the repositories take time through the injected port and stay
    deterministic under test.
    """

    def now(self) -> datetime:
        """The current timezone-aware UTC instant."""
        return datetime.now(UTC)
