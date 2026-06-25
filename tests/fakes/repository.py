"""An in-memory :class:`~downlow.domain.ports.Repository` for ``core`` tests.

Implements the same port the real ``SqlModelRepository`` does, so ``core``
services + the STORE stage run with no DB, no session, and deterministic ids.
This is the seam that lets the orchestration tests inject persistence as a fake.

Contract parity with the SQL repo (load-bearing -- a divergence here masks real
insert-vs-update bugs in ``core``):

* :meth:`add` is INSERT-ONLY -- it ALWAYS clears any caller-supplied id and inserts
  a fresh row (matching ``SqlModelRepository.add`` /
  ``test_add_ignores_caller_supplied_id``). It never updates in place; a re-save
  with an id still inserts a new row.
* :meth:`update` UPDATEs the row identified by ``entity.id`` in place, re-stamping
  ``updated_at`` -- raising ``ValueError`` if the id is ``None`` and ``KeyError`` if
  no such row exists (update never inserts).
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
        """INSERT ``entity`` with a fresh id + stamped timestamps; return it.

        Insert-only, exactly like ``SqlModelRepository.add``: any caller-supplied id
        is discarded and a fresh monotonic id allocated, so a re-save NEVER silently
        updates in place (that is :meth:`update`'s job). This parity is what lets the
        orchestration tests catch a service that wrongly relied on ``add`` to update.
        """
        now = self._clock.now()
        fields = set(self._entity_type.model_fields)
        updates: dict[str, object] = {}
        assigned = self._store.allocate_id()
        updates["id"] = assigned
        if _CREATED_FIELD in fields and getattr(entity, _CREATED_FIELD, None) is None:
            updates[_CREATED_FIELD] = now
        if _UPDATED_FIELD in fields and getattr(entity, _UPDATED_FIELD, None) is None:
            updates[_UPDATED_FIELD] = now
        saved = entity.model_copy(update=updates)
        self._store.table(self._entity_type)[assigned] = saved
        return saved

    def update(self, entity: EntityT) -> EntityT:
        """UPDATE the row identified by ``entity.id`` in place; re-stamp ``updated_at``.

        Mirrors ``SqlModelRepository.update``: never inserts. Raises ``ValueError``
        if the id is ``None`` and ``KeyError`` if no such row exists. ``created_at``
        is preserved (the entity's value wins); ``updated_at`` is re-stamped.
        """
        entity_id = getattr(entity, "id", None)
        if entity_id is None:
            raise ValueError(f"cannot update a {self._entity_type.__name__} with no id (use add to insert)")
        table = self._store.table(self._entity_type)
        if entity_id not in table:
            raise KeyError(f"no {self._entity_type.__name__} with id {entity_id} to update")
        updates: dict[str, object] = {}
        if _UPDATED_FIELD in set(self._entity_type.model_fields):
            updates[_UPDATED_FIELD] = self._clock.now()
        saved = entity.model_copy(update=updates) if updates else entity
        table[cast(int, entity_id)] = saved
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
