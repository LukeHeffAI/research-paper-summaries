"""Tests for the legacy backfill service (Phase 2.3).

Driven against the REAL :class:`SqlModelRepository` over a per-test temp SQLite DB
(the ``db_session`` fixture) -- so the import is exercised through the same FK-enforced
schema + entity<->row mapping ``dl backfill`` uses in production (the lesson from the
Phase 2.1 store tests: prefer the real repo for the persistence-shaped path). The
headline assertion is **idempotency**: running the import twice produces no duplicate
rows and reports everything as already-present on the second pass.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session

from downlow.adapters.db.repositories import SqlModelRepository
from downlow.core.services.backfill import (
    BackfillService,
    LegacyImport,
    LegacyOrphanAudio,
    LegacyOutputProfile,
    LegacyResearchProfile,
)
from downlow.domain.entities import OutputProfileRecord, ResearchProfileRecord, User
from tests.conftest import FrozenClock


def _service(session: Session) -> BackfillService:
    clock = FrozenClock()
    return BackfillService(
        users=SqlModelRepository(session, User, clock=clock),
        research_profiles=SqlModelRepository(session, ResearchProfileRecord, clock=clock),
        output_profiles=SqlModelRepository(session, OutputProfileRecord, clock=clock),
    )


def _luke_profile() -> LegacyResearchProfile:
    return LegacyResearchProfile(
        username="luke",
        research_field="Machine Learning",
        research_topic="generalisation of large pretrained models",
        research_interests=("Multimodal models", "Zero-shot classification"),
        research_focus="developing models that can generalise to new tasks and domains",
    )


def _mehrnia_profile() -> LegacyResearchProfile:
    return LegacyResearchProfile(
        username="mehrnia",
        research_field="Machine Learning",
        research_topic="out-of-distribution generalisation",
        research_interests=("Large language models", "Diffusion"),
        research_focus="robustness to distributional shifts",
    )


def _output_profile() -> LegacyOutputProfile:
    return LegacyOutputProfile(
        document_type="Literature Review",
        return_details=("A summary of roughly 300 words", "Key findings"),
    )


def _full_import() -> LegacyImport:
    return LegacyImport(
        users=("luke", "mehrnia"),
        research_profiles=(_luke_profile(), _mehrnia_profile()),
        output_profile=_output_profile(),
        orphan_audio=(LegacyOrphanAudio(owner="luke", path="/abs/legacy/users/luke/audio/orphan.pdf.mp3"),),
    )


def test_import_creates_profile_rows(db_session: Session) -> None:
    report = _service(db_session).run(_full_import())

    users = SqlModelRepository(db_session, User, clock=FrozenClock()).list()
    usernames = {u.username for u in users}
    assert {"luke", "mehrnia"} <= usernames

    research = SqlModelRepository(db_session, ResearchProfileRecord, clock=FrozenClock()).list()
    assert len(research) == 2
    luke_id = next(u.id for u in users if u.username == "luke")
    luke_research = next(r for r in research if r.user_id == luke_id)
    assert luke_research.research_field == "Machine Learning"
    assert luke_research.research_interests == ["Multimodal models", "Zero-shot classification"]

    outputs = SqlModelRepository(db_session, OutputProfileRecord, clock=FrozenClock()).list()
    # One global output profile per imported user.
    assert len(outputs) == 2
    assert all(o.name == "default" and o.document_type == "Literature Review" for o in outputs)

    assert report.research_profiles_imported == 2
    assert report.output_profiles_imported == 2
    assert len(report.skipped_orphan_audio) == 1


def test_dedupes_against_seeded_default_user(db_session: Session) -> None:
    """A pre-seeded id-1 ``luke`` (the processing seed) is reused, not duplicated."""
    users_repo = SqlModelRepository(db_session, User, clock=FrozenClock())
    users_repo.add(User(id=1, username="luke", display_name="Luke"))

    report = _service(db_session).run(_full_import())

    all_lukes = [u for u in users_repo.list() if u.username == "luke"]
    assert len(all_lukes) == 1  # the seeded owner was reused
    assert report.users_already_present >= 1  # luke counted as already-present
    assert report.users_imported == 1  # only mehrnia was new


def test_idempotent_second_run_adds_nothing(db_session: Session) -> None:
    service = _service(db_session)
    service.run(_full_import())

    users_before = len(SqlModelRepository(db_session, User, clock=FrozenClock()).list())
    research_before = len(SqlModelRepository(db_session, ResearchProfileRecord, clock=FrozenClock()).list())
    output_before = len(SqlModelRepository(db_session, OutputProfileRecord, clock=FrozenClock()).list())

    second = service.run(_full_import())

    users_after = len(SqlModelRepository(db_session, User, clock=FrozenClock()).list())
    research_after = len(SqlModelRepository(db_session, ResearchProfileRecord, clock=FrozenClock()).list())
    output_after = len(SqlModelRepository(db_session, OutputProfileRecord, clock=FrozenClock()).list())

    assert (users_after, research_after, output_after) == (users_before, research_before, output_before)
    assert second.users_imported == 0
    assert second.research_profiles_imported == 0
    assert second.output_profiles_imported == 0
    assert second.users_already_present == 2
    assert second.research_profiles_already_present == 2
    assert second.output_profiles_already_present == 2


def test_research_profile_not_overwritten_when_user_already_has_one(db_session: Session) -> None:
    """A user already carrying a research profile is left untouched (dedupe by user_id)."""
    users_repo = SqlModelRepository(db_session, User, clock=FrozenClock())
    research_repo = SqlModelRepository(db_session, ResearchProfileRecord, clock=FrozenClock())
    luke = users_repo.add(User(username="luke", display_name="Luke"))
    assert luke.id is not None
    research_repo.add(ResearchProfileRecord(user_id=luke.id, research_field="Pre-existing"))

    report = _service(db_session).run(LegacyImport(users=("luke",), research_profiles=(_luke_profile(),)))

    profiles = [r for r in research_repo.list() if r.user_id == luke.id]
    assert len(profiles) == 1
    assert profiles[0].research_field == "Pre-existing"  # not overwritten
    assert report.research_profiles_already_present == 1
    assert report.research_profiles_imported == 0


def test_user_in_tree_only_is_imported(db_session: Session) -> None:
    """A user present in the users/ tree but absent from the JSON still gets a row."""
    report = _service(db_session).run(LegacyImport(users=("harriet",)))

    users = SqlModelRepository(db_session, User, clock=FrozenClock()).list()
    assert any(u.username == "harriet" for u in users)
    assert report.users_imported == 1
    # No research profile for a tree-only user (no JSON profile supplied).
    assert report.research_profiles_imported == 0


def test_orphan_audio_is_reported_not_imported(db_session: Session) -> None:
    orphan = LegacyOrphanAudio(owner="luke", path="/abs/audio/orphan.mp3")
    report = _service(db_session).run(LegacyImport(users=("luke",), orphan_audio=(orphan,)))

    assert report.skipped_orphan_audio == [orphan]
    # No Paper / Episode tables touched -- the service has no such repos by design.


def test_empty_import_is_a_no_op(db_session: Session) -> None:
    report = _service(db_session).run(LegacyImport())

    assert report.users_imported == 0
    assert report.research_profiles_imported == 0
    assert report.output_profiles_imported == 0
    assert report.skipped_orphan_audio == []


@pytest.mark.parametrize("missing_user_in_set", [True])
def test_research_profile_for_user_not_in_set_still_imports(db_session: Session, missing_user_in_set: bool) -> None:
    """A research profile whose username is not in ``users`` still resolves a user.

    Defensive path: the loader always unions profile usernames into ``users``, but the
    service must not drop a profile whose username slipped the set.
    """
    report = _service(db_session).run(LegacyImport(users=(), research_profiles=(_luke_profile(),)))

    users = SqlModelRepository(db_session, User, clock=FrozenClock()).list()
    assert any(u.username == "luke" for u in users)
    assert report.research_profiles_imported == 1
