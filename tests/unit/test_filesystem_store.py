"""Unit tests for the FilesystemArtifactStore (F3+).

Real filesystem (a tmp dir), no network: asserts the store writes bytes under a
logical key beneath its base dir, returns a resolvable reference, overwrites in
place on a re-put (idempotent), creates nested key directories, reports existence
+ a write-free reference, and rejects a ``../``-escape (path-containment).
"""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_exists_and_ref_for(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path)
    assert store.exists("reports/r.pdf") is False
    ref_before = store.ref_for("reports/r.pdf")  # write-free
    assert not (tmp_path / "reports" / "r.pdf").exists()  # ref_for did not write

    put_ref = store.put("reports/r.pdf", b"%PDF")
    assert store.exists("reports/r.pdf") is True
    assert store.ref_for("reports/r.pdf") == put_ref == ref_before  # ref is key-deterministic


@pytest.mark.parametrize("bad_key", ["../escape.pdf", "reports/../../escape.pdf", "a/../../b.pdf"])
def test_put_rejects_path_escape(tmp_path: Path, bad_key: str) -> None:
    store = FilesystemArtifactStore(tmp_path / "root")
    with pytest.raises(ValueError, match="escapes the artifact root"):
        store.put(bad_key, b"x")


def test_exists_rejects_path_escape(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / "root")
    with pytest.raises(ValueError, match="escapes the artifact root"):
        store.exists("../../etc/passwd")
