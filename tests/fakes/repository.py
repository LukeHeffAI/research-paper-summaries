"""An in-memory :class:`~downlow.domain.ports.Repository` for ``core`` tests.

Implements the same port the real ``SqlModelRepository`` does, so ``core``
services + the STORE stage run with no DB, no session, and deterministic ids.
This is the seam that lets the orchestration tests inject persistence as a fake.

Contract parity with the SQL repo:

* :meth:`add` clears any caller-supplied id, assigns a fresh monotonic id, stamps
  ``created_at`` / ``updated_at`` from an injected clock when the entity has them
  and they are unset, and returns the populated *entity* (never a row);
* :meth:`get` returns the entity by id or ``None`` (never raises on a miss);
* :meth:`list` returns entities in id order, narrowed by equality ``filters``
  (rejecting an unknown field, like the SQL repo);
* :meth:`delete` removes by id, returning whether a row was removed (idempotent).

A shared :class:`InMemoryStore` lets several entity-typed repos see one another's
writes (mirroring several SQL repos over one session), so e.g. an Episode repo and
its EpisodePaper repo agree.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, TypeVar, cast

from pydantic import BaseModel

from downlow.domain.ports import Clock

EntityT = TypeVar("EntityT", bound=BaseModel)

_CREATED_FIELD = "created_at"
_UPDATED_FIELD = "updated_at"


class _SystemClock:
    """A real UTC clock fallback when no clock is injected (test convenience)."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class InMemoryStore:
    """The shared backing store: per-entity-type rows keyed by id, one id sequence.

    One store backs many :class:`FakeRepository` instances (one per entity type), so
    they see each other's writes exactly as several SQL repos over one session do.
    """

    def __init__(self) -> None:
        self._tables: dict[type[BaseModel], dict[int, BaseModel]] = {}
        self._next_id = 1

    def table(self, entity_type: type[BaseModel]) -> dict[int, BaseModel]:
        return self._tables.setdefault(entity_type, {})

    def allocate_id(self) -> int:
        assigned = self._next_id
        self._next_id += 1
        return assigned


class FakeRepository(Generic[EntityT]):
    """An in-memory ``Repository`` for one entity type, over a shared store."""

    def __init__(
        self,
        entity_type: type[EntityT],
        store: InMemoryStore | None = None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._entity_type = entity_type
        self._store = store or InMemoryStore()
        self._clock = clock or _SystemClock()

    @property
    def store(self) -> InMemoryStore:
        """The shared backing store (so a test can build sibling repos over it)."""
        return self._store

    def add(self, entity: EntityT) -> EntityT:
        """Insert ``entity`` with a fresh id + stamped timestamps; return it."""
        now = self._clock.now()
        fields = set(self._entity_type.model_fields)
        updates: dict[str, object] = {}
        existing_id = getattr(entity, "id", None)
        # An add with an existing id is an update-in-place (the SQL repo overwrites
        # the row via the PK); otherwise allocate a new id.
        table = self._store.table(self._entity_type)
        if existing_id is not None and existing_id in table:
            assigned = cast(int, existing_id)
        else:
            assigned = self._store.allocate_id()
        updates["id"] = assigned
        if _CREATED_FIELD in fields and getattr(entity, _CREATED_FIELD, None) is None:
            updates[_CREATED_FIELD] = now
        if _UPDATED_FIELD in fields and getattr(entity, _UPDATED_FIELD, None) is None:
            updates[_UPDATED_FIELD] = now
        saved = entity.model_copy(update=updates)
        table[assigned] = saved
        return saved

    def get(self, entity_id: int) -> EntityT | None:
        """Return the entity by id, or ``None`` on a miss."""
        row = self._store.table(self._entity_type).get(entity_id)
        return cast("EntityT | None", row)

    def list(self, **filters: object) -> list[EntityT]:
        """Return entities in id order, narrowed by equality ``filters``."""
        fields = set(self._entity_type.model_fields)
        for field in filters:
            if field not in fields:
                raise ValueError(f"unknown filter field {field!r} for {self._entity_type.__name__}")
        rows = self._store.table(self._entity_type)
        result: list[EntityT] = []
        for entity_id in sorted(rows):
            entity = cast(EntityT, rows[entity_id])
            if all(getattr(entity, field) == value for field, value in filters.items()):
                result.append(entity)
        return result

    def delete(self, entity_id: int) -> bool:
        """Delete by id; return whether a row was removed (idempotent)."""
        return self._store.table(self._entity_type).pop(entity_id, None) is not None
