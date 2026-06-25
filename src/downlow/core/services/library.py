"""Library use-case service: papers CRUD over the :class:`Repository` port.

PURE: stdlib + ``domain`` only. This is the application-seam layer the CLI (now)
and a future FastAPI route (later) call unchanged -- it depends on the
:class:`~downlow.domain.ports.Repository` *port*, never on ``sqlmodel`` / a
``Session`` / the engine. Persistence concretes are injected at the composition
root (``cli/deps.py``), so the SQLite-now / Postgres-later switch never reaches
here.

Scope (Phase 2.1): the read/write operations the ``process`` and ``library``
CLIs need -- ``add_paper`` / ``get_paper`` / ``get_by_source_hash`` /
``list_papers``. The STORE stage (``core/stages/store.py``) owns the
content-hash *upsert* of a paper during a pipeline run; this service owns the
plain library CRUD a caller drives directly.
"""

from __future__ import annotations

from downlow.domain.entities import Paper
from downlow.domain.ports import Repository


class LibraryService:
    """Papers CRUD over the injected :class:`Repository` port."""

    def __init__(self, papers: Repository[Paper]) -> None:
        """Wire the service.

        Args:
            papers: the :class:`Repository` for :class:`Paper` entities (the
                SQLModel-backed repo in production, a fake in tests).
        """
        self._papers = papers

    def add_paper(self, paper: Paper) -> Paper:
        """Persist ``paper``; return it with its store-assigned id + timestamps.

        A thin pass-through to the repository's ``add`` (insert). Content-level
        idempotency (dedupe by ``source_hash``) is the STORE stage's concern, not
        a plain ``add`` -- a caller wanting upsert-by-hash semantics uses
        :meth:`get_by_source_hash` first (or drives the STORE stage).
        """
        return self._papers.add(paper)

    def get_paper(self, paper_id: int) -> Paper | None:
        """Return the paper with this id, or ``None`` if absent (never raises)."""
        return self._papers.get(paper_id)

    def get_by_source_hash(self, source_hash: str) -> Paper | None:
        """Return the paper with this ``source_hash``, or ``None`` if none matches.

        The dedupe lookup: ``source_hash`` = ``sha256(pdf_bytes)`` is stable before
        extraction, so re-adding an identical PDF resolves to the existing paper
        rather than a duplicate row. Returns the first match (the column is the
        de-facto dedupe key; a future unique constraint makes it exactly one).
        """
        matches = self._papers.list(source_hash=source_hash)
        return matches[0] if matches else None

    def list_papers(self, *, user_id: int | None = None) -> list[Paper]:
        """List papers, optionally narrowed to one owner (stable id order).

        Args:
            user_id: when given, return only that user's papers (multi-user-ready);
                ``None`` returns every paper (single-user today).
        """
        if user_id is None:
            return self._papers.list()
        return self._papers.list(user_id=user_id)
