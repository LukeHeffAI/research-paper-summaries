"""Domain enums: the pipeline + voice status/role vocabularies."""

from __future__ import annotations

from enum import StrEnum


class StageStatus(StrEnum):
    """Lifecycle of a single pipeline stage run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(StrEnum):
    """Lifecycle of a whole pipeline run (a Job)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SpeakerRole(StrEnum):
    """A turn's speaker in the two-presenter interview podcast."""

    HOST = "host"
    AUTHOR = "author"


class VoiceSource(StrEnum):
    """Where a voice came from."""

    STOCK = "stock"
    CLONED = "cloned"
