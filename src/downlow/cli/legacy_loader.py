"""Parse the on-disk ``legacy/`` tree into a pure :class:`LegacyImport` (Phase 2.3).

The file-reading half of the legacy backfill -- it lives in the CLI/composition-root
layer (which is allowed to touch the filesystem and parse JSON) so the
:class:`~downlow.core.services.backfill.BackfillService` stays pure ``core`` over the
:class:`~downlow.domain.ports.Repository` port and unit-testable without the real
``legacy/`` directory.

What it reads under a ``--source`` root (default ``legacy/``):

* ``data/research_data.json`` -- the per-user research identities (keyed by the
  legacy ``users.<name>`` map), one :class:`LegacyResearchProfile` each.
* ``data/document_data.json`` -- the single global output profile (no per-user key),
  one :class:`LegacyOutputProfile`.
* ``users/<name>/`` -- the per-user artifact tree; each directory contributes its
  ``<name>`` to the discovered-users set. An ``audio/*.mp3`` for which no source PDF
  / summary is present in that user's tree is collected as a
  :class:`LegacyOrphanAudio` (reported, never imported -- see the service docstring).

``pathlib`` only (the legacy backslash-path bug is gone). Missing / malformed files
are handled gracefully: a missing JSON file is treated as "nothing to import from it"
(an empty section), and a malformed JSON file raises :class:`LegacyDataError` with the
offending path so the CLI can report it rather than crash opaquely.
"""

from __future__ import annotations

import json
from pathlib import Path

from downlow.core.services.backfill import (
    LegacyImport,
    LegacyOrphanAudio,
    LegacyOutputProfile,
    LegacyResearchProfile,
)
from downlow.domain.errors import DownLowError

_RESEARCH_JSON = Path("data") / "research_data.json"
_DOCUMENT_JSON = Path("data") / "document_data.json"
_USERS_DIR = Path("users")
_AUDIO_SUBDIR = "audio"
# Source/summary subdirectories whose presence makes a paper non-orphan (legacy
# layout: documents/ held the source PDFs, summaries/ the per-paper summaries).
_SOURCE_SUBDIRS = ("documents", "summaries")


class LegacyDataError(DownLowError):
    """Raised when a legacy JSON file exists but is malformed / unreadable.

    Carries the offending path so the CLI can tell the owner *which* file is broken
    rather than surfacing an opaque ``json`` decode error.
    """

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        super().__init__(f"could not parse legacy data file {path}: {reason}")


def load_legacy_import(source: Path) -> LegacyImport:
    """Parse the ``legacy/`` tree under ``source`` into a :class:`LegacyImport`.

    Args:
        source: the legacy root (default ``legacy/``); ``data/`` and ``users/`` are
            read beneath it.

    Returns:
        the assembled, pure :class:`LegacyImport` ready for
        :meth:`~downlow.core.services.backfill.BackfillService.run`.

    Raises:
        LegacyDataError: if a present JSON file cannot be parsed.
    """
    research = _load_research_profiles(source / _RESEARCH_JSON)
    output_profile = _load_output_profile(source / _DOCUMENT_JSON)
    tree_users, orphan_audio = _scan_users_tree(source / _USERS_DIR)

    # The user set is the union of the JSON keys and the on-disk directories, in a
    # stable order: JSON-declared users first (their profiles drive the import),
    # then any extra directory-only users.
    json_users = [profile.username for profile in research]
    users = tuple(_ordered_union(json_users, tree_users))

    return LegacyImport(
        users=users,
        research_profiles=tuple(research),
        output_profile=output_profile,
        orphan_audio=tuple(orphan_audio),
    )


def _load_research_profiles(path: Path) -> list[LegacyResearchProfile]:
    """Parse ``research_data.json`` -> a per-user :class:`LegacyResearchProfile` list.

    A missing file yields ``[]`` (nothing to import). The legacy shape is
    ``{"users": {"<name>": {research_field, research_topic, research_interests,
    research_focus}}}``; a missing key defaults to empty.
    """
    payload = _read_json(path)
    if payload is None:
        return []
    if not isinstance(payload, dict):
        raise LegacyDataError(path, "expected a JSON object at the top level")
    users_blob = payload.get("users", {})
    if not isinstance(users_blob, dict):
        raise LegacyDataError(path, "'users' must be a JSON object keyed by username")

    profiles: list[LegacyResearchProfile] = []
    for username, blob in users_blob.items():
        if not isinstance(blob, dict):
            raise LegacyDataError(path, f"user {username!r} must map to a JSON object")
        profiles.append(
            LegacyResearchProfile(
                username=str(username),
                research_field=_as_str(blob.get("research_field")),
                research_topic=_as_str(blob.get("research_topic")),
                research_interests=_as_str_tuple(blob.get("research_interests")),
                research_focus=_as_str(blob.get("research_focus")),
            )
        )
    return profiles


def _load_output_profile(path: Path) -> LegacyOutputProfile | None:
    """Parse ``document_data.json`` -> the single global :class:`LegacyOutputProfile`.

    A missing file yields ``None`` (no output profile to import). The legacy shape is
    ``{document_type, document_return_details}`` (note the legacy ``document_`` prefix
    on the details key).
    """
    payload = _read_json(path)
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise LegacyDataError(path, "expected a JSON object at the top level")
    return LegacyOutputProfile(
        document_type=_as_str(payload.get("document_type")),
        return_details=_as_str_tuple(payload.get("document_return_details")),
    )


def _scan_users_tree(users_dir: Path) -> tuple[list[str], list[LegacyOrphanAudio]]:
    """Discover ``users/<name>`` directories and their orphan audio.

    Returns ``(usernames, orphan_audio)``. A missing ``users/`` directory yields
    ``([], [])``. An ``audio/*.mp3`` is an orphan when that user's tree has no
    ``documents/`` or ``summaries/`` content for it to derive from -- the conservative
    rule for this phase, where the only legacy artifact is a sourceless mp3.
    """
    if not users_dir.is_dir():
        return [], []

    usernames: list[str] = []
    orphans: list[LegacyOrphanAudio] = []
    for child in sorted(users_dir.iterdir()):
        if not child.is_dir():
            continue
        username = child.name
        usernames.append(username)
        has_source = any((child / sub).is_dir() and any((child / sub).iterdir()) for sub in _SOURCE_SUBDIRS)
        audio_dir = child / _AUDIO_SUBDIR
        if audio_dir.is_dir() and not has_source:
            for mp3 in sorted(audio_dir.glob("*.mp3")):
                orphans.append(LegacyOrphanAudio(owner=username, path=str(mp3.resolve())))
    return usernames, orphans


def _read_json(path: Path) -> object | None:
    """Read + JSON-decode ``path``; ``None`` if absent; raise on malformed content."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LegacyDataError(path, f"could not read file: {exc}") from exc
    try:
        parsed: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LegacyDataError(path, str(exc)) from exc
    return parsed


def _as_str(value: object) -> str:
    """Coerce a JSON value to a string field (``None`` -> empty)."""
    return "" if value is None else str(value)


def _as_str_tuple(value: object) -> tuple[str, ...]:
    """Coerce a JSON list to a tuple of strings (non-list -> empty)."""
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _ordered_union(first: list[str], second: list[str]) -> list[str]:
    """The order-preserving union of two username lists (first list wins ordering)."""
    seen: set[str] = set()
    result: list[str] = []
    for item in (*first, *second):
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
