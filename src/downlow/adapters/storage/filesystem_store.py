"""FilesystemArtifactStore implements :class:`ArtifactStore` (F3+).

The only place the on-disk artifact layout under ``DATA_DIR`` is owned. Binaries
(report PDFs, episode mp3s) are written here behind a logical ``key`` and the
returned reference (the resolved path string) is what the DB records -- so a later
move to object storage for multi-user is an adapter swap, nothing in ``core``
changes.

``pathlib`` only (the legacy backslash-path bug is gone); writes are atomic via a
unique temp file + ``replace`` (mirrors the stage caches), so a concurrent or
re-run write cannot leave a torn file and re-putting a key overwrites in place.
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
        self._base_dir = base_dir

    def put(self, key: str, data: bytes) -> str:
        """Store ``data`` under ``key`` (relative to the base dir); return its path.

        The write is atomic (unique temp file + ``replace``) and idempotent
        (re-putting the same key overwrites in place). Returns the resolved
        absolute path as the artifact reference.
        """
        target = (self._base_dir / key).resolve()
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
