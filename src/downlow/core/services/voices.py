"""Voices use-case service: the host + default-author stock voice pool.

PURE: stdlib + ``domain`` only. Depends on the
:class:`~downlow.domain.ports.Repository` *port* for :class:`Voice` entities; the
concrete SQLModel repo is injected at the composition root. Cloning (a
``source=cloned`` voice with sample/consent fields) is Phase 7 -- this phase ships
only the two stock voices the two-presenter NARRATE stage needs (a consistent
host, a default author).

Seeding is idempotent: :meth:`seed_stock_voices` is keyed on
``(provider, provider_voice_id)`` so re-running it (every ``dl process``, a future
bootstrap) does not duplicate the stock pool -- an existing voice is returned
unchanged, a missing one is inserted. This mirrors the STORE stage's upsert-by-key
discipline so the voice pool stays a no-op on re-run.
"""

from __future__ import annotations

from dataclasses import dataclass

from downlow.domain.entities import Voice
from downlow.domain.enums import SpeakerRole, VoiceSource
from downlow.domain.ports import Repository


@dataclass(frozen=True)
class StockVoiceSpec:
    """A stock voice to seed: its provider identity + role + display name.

    Pure value object so the composition root can pass the configured
    provider/voice ids (from the config file's ``[voices]`` host/author) without
    this service reading the config -- it stays a pure CRUD seam.
    """

    provider: str
    provider_voice_id: str
    role_hint: SpeakerRole
    display_name: str


class VoicesService:
    """The stock host + author voice pool over the :class:`Repository` port."""

    def __init__(self, voices: Repository[Voice]) -> None:
        """Wire the service.

        Args:
            voices: the :class:`Repository` for :class:`Voice` entities.
        """
        self._voices = voices

    def seed_stock_voices(self, specs: list[StockVoiceSpec], *, user_id: int | None = None) -> list[Voice]:
        """Ensure each stock voice in ``specs`` exists; return the resolved pool.

        Idempotent upsert keyed on ``(provider, provider_voice_id)``: an existing
        stock voice is returned as-is (no duplicate, no overwrite), a missing one is
        inserted. ``user_id`` is ``None`` for shared stock voices today (the schema
        allows an owner so multi-user can scope them later).
        """
        resolved: list[Voice] = []
        for spec in specs:
            resolved.append(self._upsert_stock(spec, user_id=user_id))
        return resolved

    def get_by_role(self, role: SpeakerRole, *, user_id: int | None = None) -> Voice | None:
        """Return the first stock voice hinted for ``role``, or ``None`` if unseeded.

        Used to resolve the host / default-author voice for a NARRATE run from the
        seeded pool. Narrows by ``user_id`` when given (shared stock voices use
        ``None``).
        """
        for voice in self._stock_voices(user_id=user_id):
            if voice.role_hint == role:
                return voice
        return None

    def list_stock_voices(self, *, user_id: int | None = None) -> list[Voice]:
        """Return every stock voice (optionally one owner's), in stable id order."""
        return self._stock_voices(user_id=user_id)

    # --- internals ----------------------------------------------------------- #

    def _upsert_stock(self, spec: StockVoiceSpec, *, user_id: int | None) -> Voice:
        """Return the existing matching stock voice, or insert a new one."""
        existing = self._find(spec.provider, spec.provider_voice_id)
        if existing is not None:
            return existing
        return self._voices.add(
            Voice(
                user_id=user_id,
                provider=spec.provider,
                provider_voice_id=spec.provider_voice_id,
                source=VoiceSource.STOCK,
                display_name=spec.display_name,
                role_hint=spec.role_hint,
            )
        )

    def _find(self, provider: str, provider_voice_id: str) -> Voice | None:
        """Find a voice by its provider identity (the idempotency key)."""
        matches = self._voices.list(provider=provider, provider_voice_id=provider_voice_id)
        return matches[0] if matches else None

    def _stock_voices(self, *, user_id: int | None) -> list[Voice]:
        """All stock-source voices, optionally narrowed to one owner."""
        if user_id is None:
            voices = self._voices.list(source=VoiceSource.STOCK)
        else:
            voices = self._voices.list(source=VoiceSource.STOCK, user_id=user_id)
        return voices
