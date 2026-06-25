"""Unit tests for the STORE stage (Phase 2.1, Stage 5).

In-memory fake repositories (no DB, no network): assert STORE upserts each
artifact type (Paper, Summary, ReportAsset, Episode + EpisodePaper + PodcastAsset)
keyed on its content hash / deterministic ref, and that re-running STORE on
unchanged input is a true no-op (no duplicate rows).
"""

from __future__ import annotations

import pytest

from downlow.core.stages.store import StoreStage
from downlow.domain.entities import (
    Episode,
    EpisodePaper,
    Paper,
    PodcastAsset,
    ReportAsset,
    Summary,
)
from downlow.domain.enums import SpeakerRole
from downlow.domain.schemas import KeyFinding, NarrationScript, PaperSummary, Turn, VoiceRef
from tests.conftest import FrozenClock
from tests.fakes.repository import FakeRepository, InMemoryStore


@pytest.fixture
def store() -> StoreStage:
    """A STORE stage wired with fresh in-memory repos over one shared store."""
    shared = InMemoryStore()
    clock = FrozenClock()
    return StoreStage(
        papers=FakeRepository(Paper, shared, clock=clock),
        summaries=FakeRepository(Summary, shared, clock=clock),
        reports=FakeRepository(ReportAsset, shared, clock=clock),
        episodes=FakeRepository(Episode, shared, clock=clock),
        episode_papers=FakeRepository(EpisodePaper, shared, clock=clock),
        podcasts=FakeRepository(PodcastAsset, shared, clock=clock),
    )


def _summary(*, input_hash: str = "content-abc", title: str = "A Paper") -> PaperSummary:
    return PaperSummary(
        title=title,
        overall_summary="It works, robustly, across two domains, with a clear method and honest gaps.",
        key_findings=[KeyFinding(statement="X improves Y", evidence="+3%")],
        contributions=["a method"],
        methods="ablation",
        gaps_and_limitations=["small N"],
        relevance_to_profile="bears on your focus",
        input_hash=input_hash,
        profile_hash="prof-1",
        model="claude-sonnet-4-6",
        prompt_version="summary-v1",
    )


def _script() -> NarrationScript:
    return NarrationScript(
        episode_title="The Hook",
        voices=[VoiceRef(role=SpeakerRole.HOST, voice_id="h"), VoiceRef(role=SpeakerRole.AUTHOR, voice_id="a")],
        turns=[Turn(type="speech", role=SpeakerRole.HOST, text="Welcome.")],
        model="claude-sonnet-4-6",
    )


# --------------------------------------------------------------------------- #
# Paper upsert (dedupe by source_hash)                                          #
# --------------------------------------------------------------------------- #


def test_upsert_paper_inserts_then_dedupes_by_source_hash(store: StoreStage) -> None:
    first = store.upsert_paper(user_id=1, source_hash="src-1", title="A")
    assert first.id is not None

    again = store.upsert_paper(user_id=1, source_hash="src-1", title="A")
    assert again.id == first.id  # same paper, not a duplicate
    assert len(store._papers.list()) == 1


def test_upsert_paper_backfills_title_without_clobbering(store: StoreStage) -> None:
    blank = store.upsert_paper(user_id=1, source_hash="src-1", title="")
    learned = store.upsert_paper(user_id=1, source_hash="src-1", title="The Real Title", page_count=12)
    assert learned.id == blank.id
    assert learned.title == "The Real Title"
    assert learned.page_count == 12
    # A later blank title must NOT erase the learned one.
    kept = store.upsert_paper(user_id=1, source_hash="src-1", title="")
    assert kept.title == "The Real Title"
    assert len(store._papers.list()) == 1


def test_upsert_paper_unchanged_is_a_noop(store: StoreStage) -> None:
    first = store.upsert_paper(user_id=1, source_hash="src-1", title="A", page_count=3)
    second = store.upsert_paper(user_id=1, source_hash="src-1", title="A", page_count=3)
    assert second == first  # identical entity returned, nothing rewritten


# --------------------------------------------------------------------------- #
# Summary upsert (dedupe by paper + content_hash)                               #
# --------------------------------------------------------------------------- #


def test_upsert_summary_persists_structured_fields(store: StoreStage) -> None:
    paper = store.upsert_paper(user_id=1, source_hash="src-1", title="A")
    assert paper.id is not None
    saved = store.upsert_summary(paper.id, _summary(input_hash="c-1"))

    assert saved.id is not None
    assert saved.content_hash == "c-1"
    assert saved.key_findings == [{"statement": "X improves Y", "evidence": "+3%"}]
    assert saved.contributions == ["a method"]
    assert saved.model_id == "claude-sonnet-4-6"
    assert saved.prompt_version == "summary-v1"


def test_upsert_summary_is_idempotent_by_content_hash(store: StoreStage) -> None:
    paper = store.upsert_paper(user_id=1, source_hash="src-1", title="A")
    assert paper.id is not None
    one = store.upsert_summary(paper.id, _summary(input_hash="c-1"))
    two = store.upsert_summary(paper.id, _summary(input_hash="c-1"))
    assert two.id == one.id
    assert len(store._summaries.list()) == 1

    # A different content hash IS a new summary row (re-summarised input).
    store.upsert_summary(paper.id, _summary(input_hash="c-2"))
    assert len(store._summaries.list()) == 2


# --------------------------------------------------------------------------- #
# ReportAsset upsert (dedupe by paper + deterministic pdf_ref)                  #
# --------------------------------------------------------------------------- #


def test_upsert_report_is_idempotent_by_ref(store: StoreStage) -> None:
    paper = store.upsert_paper(user_id=1, source_hash="src-1", title="A")
    assert paper.id is not None
    one = store.upsert_report(paper.id, pdf_ref="/data/reports/a.pdf", filename="a.pdf", template_version="report-v1")
    two = store.upsert_report(paper.id, pdf_ref="/data/reports/a.pdf", filename="a.pdf", template_version="report-v1")
    assert two.id == one.id
    assert len(store._reports.list()) == 1


# --------------------------------------------------------------------------- #
# Episode + EpisodePaper + PodcastAsset upsert                                  #
# --------------------------------------------------------------------------- #


def test_upsert_episode_podcast_creates_join_and_asset(store: StoreStage) -> None:
    paper = store.upsert_paper(user_id=1, source_hash="src-1", title="A")
    assert paper.id is not None
    episode, podcast = store.upsert_episode_podcast(paper.id, user_id=1, mp3_ref="audio/x.mp3", script=_script())

    assert episode.id is not None
    assert podcast.id is not None
    assert podcast.mp3_ref == "audio/x.mp3"
    assert podcast.model_id == "claude-sonnet-4-6"
    # The multi-paper-ready join links the episode to the paper.
    joins = store._episode_papers.list(episode_id=episode.id)
    assert [(j.paper_id, j.order) for j in joins] == [(paper.id, 0)]


def test_upsert_episode_podcast_is_idempotent(store: StoreStage) -> None:
    paper = store.upsert_paper(user_id=1, source_hash="src-1", title="A")
    assert paper.id is not None
    ep1, pod1 = store.upsert_episode_podcast(paper.id, user_id=1, mp3_ref="audio/x.mp3", script=_script())
    ep2, pod2 = store.upsert_episode_podcast(paper.id, user_id=1, mp3_ref="audio/x.mp3", script=_script())

    assert ep2.id == ep1.id  # one episode per paper
    assert pod2.id == pod1.id  # one asset per (episode, ref)
    assert len(store._episodes.list()) == 1
    assert len(store._episode_papers.list()) == 1
    assert len(store._podcasts.list()) == 1
