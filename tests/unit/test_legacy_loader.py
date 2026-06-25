"""Tests for the legacy-tree parser (Phase 2.3).

Builds a temp ``legacy/`` tree mirroring the real layout (``data/research_data.json``,
``data/document_data.json``, ``users/<name>/audio/*.mp3``) and asserts the loader
produces the expected pure :class:`LegacyImport`, detects the sourceless orphan mp3,
and handles missing / malformed JSON gracefully.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from downlow.cli.legacy_loader import LegacyDataError, load_legacy_import


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _research_payload() -> dict[str, object]:
    return {
        "users": {
            "luke": {
                "research_field": "Machine Learning",
                "research_topic": "generalisation",
                "research_interests": ["Multimodal models", "Zero-shot classification"],
                "research_focus": "transfer to new domains",
            },
            "harriet": {
                "research_field": "Anthropology",
                "research_topic": "Indigenous studies",
                "research_interests": ["Land education"],
                "research_focus": "land based education",
            },
        }
    }


def _document_payload() -> dict[str, object]:
    return {
        "document_type": "Literature Review",
        "document_return_details": ["A summary of roughly 300 words", "Key findings"],
    }


def _legacy_tree(root: Path, *, with_orphan_audio: bool = True) -> Path:
    _write(root / "data" / "research_data.json", _research_payload())
    _write(root / "data" / "document_data.json", _document_payload())
    if with_orphan_audio:
        audio_dir = root / "users" / "luke" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        (audio_dir / "research_summaries_x.pdf.mp3").write_bytes(b"ID3fake-mp3")
    return root


def test_loads_research_and_output_profiles(tmp_path: Path) -> None:
    data = load_legacy_import(_legacy_tree(tmp_path))

    names = {p.username for p in data.research_profiles}
    assert names == {"luke", "harriet"}
    luke = next(p for p in data.research_profiles if p.username == "luke")
    assert luke.research_field == "Machine Learning"
    assert luke.research_interests == ("Multimodal models", "Zero-shot classification")

    assert data.output_profile is not None
    assert data.output_profile.document_type == "Literature Review"
    assert data.output_profile.return_details == ("A summary of roughly 300 words", "Key findings")


def test_users_union_of_json_and_tree(tmp_path: Path) -> None:
    data = load_legacy_import(_legacy_tree(tmp_path))
    # luke + harriet from JSON; luke also has a users/ dir -- union, no duplicates.
    assert sorted(data.users) == ["harriet", "luke"]
    assert len(data.users) == len(set(data.users))


def test_detects_orphan_audio(tmp_path: Path) -> None:
    data = load_legacy_import(_legacy_tree(tmp_path, with_orphan_audio=True))

    assert len(data.orphan_audio) == 1
    orphan = data.orphan_audio[0]
    assert orphan.owner == "luke"
    assert orphan.path.endswith("research_summaries_x.pdf.mp3")
    assert Path(orphan.path).is_absolute()


def test_audio_with_source_pdf_is_not_orphan(tmp_path: Path) -> None:
    root = _legacy_tree(tmp_path, with_orphan_audio=True)
    # Give luke a documents/ source so the audio is no longer an orphan.
    docs = root / "users" / "luke" / "documents"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "paper.pdf").write_bytes(b"%PDF-1.7")

    data = load_legacy_import(root)
    assert data.orphan_audio == ()


def test_missing_json_files_yield_empty_sections(tmp_path: Path) -> None:
    # An empty legacy root: data/ and users/ both absent.
    data = load_legacy_import(tmp_path)
    assert data.research_profiles == ()
    assert data.output_profile is None
    assert data.users == ()
    assert data.orphan_audio == ()


def test_malformed_research_json_raises(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "research_data.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(LegacyDataError) as excinfo:
        load_legacy_import(tmp_path)
    assert excinfo.value.path.name == "research_data.json"


def test_malformed_document_json_raises(tmp_path: Path) -> None:
    _write(tmp_path / "data" / "research_data.json", _research_payload())
    (tmp_path / "data" / "document_data.json").write_text("[1, 2, 3", encoding="utf-8")

    with pytest.raises(LegacyDataError):
        load_legacy_import(tmp_path)


def test_research_users_not_an_object_raises(tmp_path: Path) -> None:
    _write(tmp_path / "data" / "research_data.json", {"users": ["luke"]})

    with pytest.raises(LegacyDataError):
        load_legacy_import(tmp_path)


def test_document_not_an_object_raises(tmp_path: Path) -> None:
    _write(tmp_path / "data" / "document_data.json", ["nope"])

    with pytest.raises(LegacyDataError):
        load_legacy_import(tmp_path)


def test_partial_research_blob_defaults_missing_fields(tmp_path: Path) -> None:
    _write(tmp_path / "data" / "research_data.json", {"users": {"luke": {"research_field": "ML"}}})

    data = load_legacy_import(tmp_path)
    luke = data.research_profiles[0]
    assert luke.research_field == "ML"
    assert luke.research_topic == ""
    assert luke.research_interests == ()
    assert luke.research_focus == ""
