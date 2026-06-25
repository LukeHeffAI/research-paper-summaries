"""FilesystemArtifactStore implements :class:`ArtifactStore` (F3+).

The only place the on-disk artifact layout under ``DATA_DIR`` is owned. Binaries
(report PDFs, episode mp3s) are written here behind a logical ``key`` and the
returned reference (the resolved path string) is what the DB records -- so a later
move to object storage for multi-user is an adapter swap, nothing in ``core``
changes.

``pathlib`` only (the legacy backslash-path bug is gone); writes are atomic via a
unique temp file + ``replace`` (mirrors the stage caches), so a concurrent or
re-run write cannot leave a torn file and re-putting a key overwrites in place.

Path-containment defense-in-depth: every ``key`` is resolved and asserted to live
*under* the base dir, so a ``../``-escape (or an absolute key) raises rather than
writing outside the artifact tree -- RENDER passes a sanitised slug today, but
mp3s / future callers reuse this store.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


class FilesystemArtifactStore:
    """``ArtifactStore`` implementation rooted at a ``DATA_DIR`` base directory."""

    def __init__(self, base_dir: Path) -> None:
        """Wire the store.

        Args:
            base_dir: the artifact root (typically ``settings.data_dir``); every
                ``key`` is resolved beneath it.
        """
        self._base_dir = base_dir.resolve()

    def put(self, key: str, data: bytes) -> str:
        """Store ``data`` under ``key`` (relative to the base dir); return its path.

        The write is atomic (unique temp file + ``replace``) and idempotent
        (re-putting the same key overwrites in place). Returns the resolved
        absolute path as the artifact reference.

        Raises:
            ValueError: if ``key`` resolves outside the base directory.
        """
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f"{target.name}.", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            tmp_path.replace(target)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        return str(target)

    def exists(self, key: str) -> bool:
        """True when an artifact is already stored under ``key``.

        Lets a stage skip a redundant re-write when the artifact is already present
        (e.g. RENDER on a cache hit). Same containment guard as :meth:`put`.

        Raises:
            ValueError: if ``key`` resolves outside the base directory.
        """
        return self._resolve(key).is_file()

    def ref_for(self, key: str) -> str:
        """The reference (resolved path string) for ``key`` without writing.

        Matches what :meth:`put` returns, so a stage that skipped the write on a
        cache hit reports the same reference. Same containment guard as :meth:`put`.

        Raises:
            ValueError: if ``key`` resolves outside the base directory.
        """
        return str(self._resolve(key))

    def _resolve(self, key: str) -> Path:
        """Resolve ``key`` under the base dir, rejecting any ``../``-escape.

        ``resolve()`` collapses ``..`` segments and symlinks; the result must be the
        base dir itself or a descendant of it (defense-in-depth for the reusable
        store), else a malicious / buggy key could write outside the artifact tree.
        """
        target = (self._base_dir / key).resolve()
        if target != self._base_dir and self._base_dir not in target.parents:
            raise ValueError(f"artifact key {key!r} escapes the artifact root {self._base_dir}")
        return target
