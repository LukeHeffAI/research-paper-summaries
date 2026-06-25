"""Persistence: SQLModel engine/session + repositories.

The only package where ``sqlmodel`` / ``sqlalchemy`` / a ``Session`` / the engine
appear. ``core`` depends on the :class:`~downlow.domain.ports.Repository` and
:class:`~downlow.domain.ports.Clock` ports; this adapter implements them.
"""

from __future__ import annotations

from downlow.adapters.db.engine import (
    SystemClock,
    create_all,
    create_db_engine,
    get_session,
    session_factory,
)
from downlow.adapters.db.repositories import SqlModelRepository
from downlow.adapters.db.tables import ALL_TABLES, ENTITY_TO_ROW, metadata

__all__ = [
    "ALL_TABLES",
    "ENTITY_TO_ROW",
    "SqlModelRepository",
    "SystemClock",
    "create_all",
    "create_db_engine",
    "get_session",
    "metadata",
    "session_factory",
]
