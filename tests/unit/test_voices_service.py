"""Unit tests for the voices use-case service (Phase 2.1).

In-memory fake repository: asserts the stock host/author voice pool is seeded,
idempotently (re-seeding does not duplicate), and resolvable by role.
"""

from __future__ import annotations

from downlow.core.services.voices import StockVoiceSpec, VoicesService
from downlow.domain.entities import Voice
from downlow.domain.enums import SpeakerRole, VoiceSource
from tests.conftest import FrozenClock
from tests.fakes.repository import FakeRepository


def _service() -> VoicesService:
    return VoicesService(FakeRepository(Voice, clock=FrozenClock()))


def _specs() -> list[StockVoiceSpec]:
    return [
        StockVoiceSpec(
            provider="elevenlabs", provider_voice_id="host-v", role_hint=SpeakerRole.HOST, display_name="Host"
        ),
        StockVoiceSpec(
            provider="elevenlabs", provider_voice_id="author-v", role_hint=SpeakerRole.AUTHOR, display_name="Author"
        ),
    ]


def test_seed_stock_voices_creates_the_pool() -> None:
    svc = _service()
    seeded = svc.seed_stock_voices(_specs())
    assert {v.role_hint for v in seeded} == {SpeakerRole.HOST, SpeakerRole.AUTHOR}
    assert all(v.source is VoiceSource.STOCK for v in seeded)
    assert len(svc.list_stock_voices()) == 2


def test_seed_is_idempotent() -> None:
    svc = _service()
    first = svc.seed_stock_voices(_specs())
    second = svc.seed_stock_voices(_specs())
    assert [v.id for v in second] == [v.id for v in first]  # same rows, not duplicates
    assert len(svc.list_stock_voices()) == 2


def test_get_by_role_resolves_the_seeded_voice() -> None:
    svc = _service()
    svc.seed_stock_voices(_specs())
    host = svc.get_by_role(SpeakerRole.HOST)
    assert host is not None
    assert host.provider_voice_id == "host-v"
    assert svc.get_by_role(SpeakerRole.AUTHOR) is not None
