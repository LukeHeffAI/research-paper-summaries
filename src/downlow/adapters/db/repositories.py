"""``SqlModelRepository`` -- the :class:`~downlow.domain.ports.Repository` impl.

The only place a :class:`~sqlmodel.Session` is driven for CRUD. Generic over a pure
:mod:`downlow.domain.entities` entity type; it looks up the matching ``table=True``
row class, maps entity <-> row on the way in/out, and stamps ``created_at`` /
``updated_at`` from an injected :class:`~downlow.domain.ports.Clock` so ``core``
never reads the wall clock. A SQLModel row never leaves this class -- callers
receive pure pydantic entities.

Construct one per entity type per session:

    repo = SqlModelRepository(session, Paper, clock=SystemClock())

Sessions are short-lived (one per CLI unit of work / FastAPI request / worker
task); this repository does not own the session's lifecycle, only its CRUD.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from pydantic import BaseModel
from sqlmodel import Session, SQLModel, select

from downlow.adapters.db.engine import SystemClock
from downlow.adapters.db.tables import ENTITY_TO_ROW
from downlow.domain.ports import Clock

EntityT = TypeVar("EntityT", bound=BaseModel)

# Entity fields the store stamps from the clock, mapped to when they apply.
_CREATED_FIELD = "created_at"
_UPDATED_FIELD = "updated_at"


class SqlModelRepository(Generic[EntityT]):
    """A :class:`~downlow.domain.ports.Repository` over a SQLModel session."""

    def __init__(
        self,
        session: Session,
        entity_type: type[EntityT],
        *,
        clock: Clock | None = None,
    ) -> None:
        """Wire the repository for one entity type.

        Args:
            session: the active (short-lived) SQLModel session.
            entity_type: the pure ``domain.entities`` class this repo persists.
            clock: time source for ``created_at`` / ``updated_at`` (a real UTC
                clock by default; tests inject a frozen one).

        Raises:
            KeyError: if ``entity_type`` has no registered table row class.
        """
        self._session = session
        self._entity_type = entity_type
        self._row_type: type[SQLModel] = ENTITY_TO_ROW[entity_type]
        self._clock = clock or SystemClock()

    def add(self, entity: EntityT) -> EntityT:
        """Insert ``entity``; return it with ``id`` / timestamps populated.

        Stamps ``created_at`` (and ``updated_at`` when the entity has one) from the
        injected clock if unset, so callers in ``core`` never touch the wall clock.
        The entity -> row conversion goes through the row's ``from_entity`` seam
        (the mirror of ``to_entity`` on the read path), so there is a single,
        tested entity<->row mapping rather than two divergent ones.

        The caller owns the session: this commits, but does NOT roll back on
        failure -- a failed unit of work must be rolled back by the composition root
        (see FUTURE_FIXES, "repository add/delete + rollback").
        """
        prepared = self._stamp(entity)
        row = self._row_type.from_entity(prepared)  # type: ignore[attr-defined]
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_entity(row)

    def _stamp(self, entity: EntityT) -> EntityT:
        """Return a copy of ``entity`` with the id cleared and timestamps stamped.

        Clears any caller-supplied ``id`` (the store assigns it) and fills
        ``created_at`` / ``updated_at`` from the injected clock when unset, so both
        the in-path conversion and the timestamping happen before ``from_entity``.
        """
        now = self._clock.now()
        fields = set(self._entity_type.model_fields)
        updates: dict[str, Any] = {"id": None}
        if _CREATED_FIELD in fields and getattr(entity, _CREATED_FIELD, None) is None:
            updates[_CREATED_FIELD] = now
        if _UPDATED_FIELD in fields and getattr(entity, _UPDATED_FIELD, None) is None:
            updates[_UPDATED_FIELD] = now
        return entity.model_copy(update=updates)

    def update(self, entity: EntityT) -> EntityT:
        """UPDATE the existing row identified by ``entity.id`` in place; return it.

        The mirror of insert-only :meth:`add`: this never inserts. It loads the row
        by ``entity.id``, overwrites its columns from ``entity`` (preserving the
        original ``created_at`` -- the entity's create timestamp wins, not the wall
        clock), re-stamps ``updated_at`` from the injected clock, commits, and returns
        the refreshed entity. Used wherever a service modifies a persisted row in
        place (a run's terminal status, a paper's backfilled title) rather than the
        insert-then-duplicate that :meth:`add` would cause.

        The caller owns the session (commits here, no rollback -- see ``add``).

        Raises:
            ValueError: if ``entity.id`` is ``None`` (nothing to update).
            KeyError: if no row with ``entity.id`` exists (update never inserts).
        """
        entity_id = getattr(entity, "id", None)
        if entity_id is None:
            raise ValueError(f"cannot update a {self._entity_type.__name__} with no id (use add to insert)")
        row = self._session.get(self._row_type, entity_id)
        if row is None:
            raise KeyError(f"no {self._entity_type.__name__} with id {entity_id} to update")

        now = self._clock.now()
        fields = set(self._entity_type.model_fields)
        updates: dict[str, Any] = {}
        if _UPDATED_FIELD in fields:
            updates[_UPDATED_FIELD] = now
        prepared = entity.model_copy(update=updates) if updates else entity

        # Overwrite the existing row's columns from the entity (id preserved), so the
        # update mutates the loaded row rather than inserting a second one.
        for field, value in prepared.model_dump().items():
            setattr(row, field, value)
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_entity(row)

    def get(self, entity_id: int) -> EntityT | None:
        """Return the entity with this primary key, or ``None`` if absent."""
        row = self._session.get(self._row_type, entity_id)
        return self._to_entity(row) if row is not None else None

    def list(self, **filters: object) -> list[EntityT]:
        """Return entities, optionally narrowed by equality ``filters``.

        ``filters`` are plain field/value pairs (e.g. ``user_id=1``), translated to
        ``WHERE col = value`` -- provider-agnostic, never a raw SQL expression.
        Ordered by primary key for a stable result.

        Raises:
            ValueError: if a filter names a column the row does not have.
        """
        statement = select(self._row_type)
        for field, value in filters.items():
            column = getattr(self._row_type, field, None)
            if column is None:
                raise ValueError(f"unknown filter field {field!r} for {self._entity_type.__name__}")
            statement = statement.where(column == value)
        # Every row class declares an ``id`` PK; the cast keeps mypy off the
        # loosely-typed ``type[SQLModel]`` while ordering by it for a stable result.
        statement = statement.order_by(cast(Any, self._row_type).id)
        rows = self._session.exec(statement).all()
        return [self._to_entity(row) for row in rows]

    def delete(self, entity_id: int) -> bool:
        """Delete the entity with this primary key; ``True`` if one was removed.

        Commits but does not roll back on failure (the composition root owns the
        session and its rollback -- see FUTURE_FIXES).
        """
        row = self._session.get(self._row_type, entity_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.commit()
        return True

    def _to_entity(self, row: SQLModel) -> EntityT:
        """Map a row back to its pure domain entity (rows never leave this class).

        Delegates to the row's own ``to_entity`` so the tz-aware-UTC datetime
        normalisation (``tables._row_dump``) is applied in one place -- a
        SQLite-naive timestamp comes back tz-aware UTC, matching Postgres.
        """
        return cast(EntityT, row.to_entity())  # type: ignore[attr-defined]
