"""Unit tests for the FilesystemArtifactStore (F3+).

Real filesystem (a tmp dir), no network: asserts the store writes bytes under a
logical key beneath its base dir, returns a resolvable reference, overwrites in
place on a re-put (idempotent), and creates nested key directories.
"""

from __future__ import annotations

from pathlib import Path

from downlow.adapters.storage.filesystem_store import FilesystemArtifactStore


def test_put_writes_under_the_key_and_returns_the_path(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    ref = store.put("reports/my-report.pdf", b"%PDF-bytes")

    target = tmp_path / "reports" / "my-report.pdf"
    assert target.exists()
    assert target.read_bytes() == b"%PDF-bytes"
    assert ref == str(target.resolve())


def test_put_creates_nested_directories(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    store.put("audio/episode-1/asset.mp3", b"mp3")
    assert (tmp_path / "audio" / "episode-1" / "asset.mp3").read_bytes() == b"mp3"


def test_put_is_idempotent_overwrite(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    store.put("reports/r.pdf", b"first")
    ref2 = store.put("reports/r.pdf", b"second")  # re-put same key overwrites
    assert (tmp_path / "reports" / "r.pdf").read_bytes() == b"second"
    assert ref2 == str((tmp_path / "reports" / "r.pdf").resolve())
    # No leftover temp files from the atomic write.
    assert sorted(p.name for p in (tmp_path / "reports").iterdir()) == ["r.pdf"]
