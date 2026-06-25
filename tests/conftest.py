"""Shared test fixtures.

Includes the F1-F4 fakes (``fake_llm``, ``fake_tts``, ``fake_renderer``,
``fake_mixer``) and the Phase 2.0 persistence fixtures: a temp-file SQLite engine
with the schema created (``db_engine``), a session bound to it (``db_session``),
and a frozen :class:`~downlow.domain.ports.Clock` so timestamps are deterministic.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session

from downlow.adapters.db.engine import create_all, create_db_engine
from downlow.config.settings import Settings

FIXTURES_DIR = Path(__file__).parent / "fixtures"


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
def db_engine(tmp_path: Path) -> Iterator[Engine]:
    """A temp-file SQLite engine with the full schema created (no Alembic needed)."""
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
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
