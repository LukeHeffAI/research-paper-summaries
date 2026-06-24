"""Shared test fixtures.

Phase 0 keeps this minimal; Phase 1 adds fakes (``fake_llm``, ``fake_tts``,
``fake_renderer``, ``fake_mixer``), a ``sample_pdf`` fixture, and an in-memory
``db_session``.
"""

from __future__ import annotations

import pytest

from downlow.config.settings import Settings


@pytest.fixture
def settings() -> Settings:
    """A Settings instance with defaults and no real credentials."""
    return Settings(anthropic_api_key=None, elevenlabs_api_key=None)
