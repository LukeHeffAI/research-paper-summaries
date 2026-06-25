"""Unit tests for the library use-case service (Phase 2.1).

In-memory fake repository: asserts ``add_paper`` / ``get_paper`` /
``get_by_source_hash`` / ``list_papers`` over the Repository port, including the
multi-user-ready ``user_id`` narrowing and the dedupe lookup miss.
"""

from __future__ import annotations

from downlow.core.services.library import LibraryService
from downlow.domain.entities import Paper
from tests.conftest import FrozenClock
from tests.fakes.repository import FakeRepository


def _service() -> LibraryService:
    return LibraryService(FakeRepository(Paper, clock=FrozenClock()))


def test_add_and_get_round_trip() -> None:
    svc = _service()
    saved = svc.add_paper(Paper(user_id=1, title="A paper", source_hash="src-1"))
    assert saved.id is not None
    fetched = svc.get_paper(saved.id)
    assert fetched is not None
    assert fetched.title == "A paper"


def test_get_paper_returns_none_for_a_miss() -> None:
    assert _service().get_paper(404) is None


def test_get_by_source_hash_finds_and_misses() -> None:
    svc = _service()
    svc.add_paper(Paper(user_id=1, title="A", source_hash="src-1"))
    found = svc.get_by_source_hash("src-1")
    assert found is not None
    assert found.title == "A"
    assert svc.get_by_source_hash("nope") is None


def test_list_papers_narrows_by_user() -> None:
    svc = _service()
    svc.add_paper(Paper(user_id=1, title="mine-1", source_hash="a"))
    svc.add_paper(Paper(user_id=1, title="mine-2", source_hash="b"))
    svc.add_paper(Paper(user_id=2, title="theirs", source_hash="c"))

    assert {p.title for p in svc.list_papers()} == {"mine-1", "mine-2", "theirs"}
    assert {p.title for p in svc.list_papers(user_id=1)} == {"mine-1", "mine-2"}
    assert [p.title for p in svc.list_papers(user_id=2)] == ["theirs"]
