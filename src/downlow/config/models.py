"""Typed per-stage model configuration."""

from __future__ import annotations

from pydantic import BaseModel


class ModelConfig(BaseModel):
    """Per-stage Claude model configuration.

    ``effort`` is a real cost lever — Sonnet defaults to ``"high"``; summarisation
    and narration usually want ``"low"`` or ``"medium"`` with thinking off.
    """

    id: str
    max_tokens: int = 8000
    effort: str = "medium"
