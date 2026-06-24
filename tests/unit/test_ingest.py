"""Unit tests for F1 — the INGEST stage.

Covers the pure normalisation logic, the ``pdfplumber``-backed extractor (with
the library mocked so no real file is needed), and the file-backed cache in the
core stage (with a spy fake asserting hit/miss behaviour).
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from downlow.adapters.pdf.extractor import PdfPlumberExtractor, normalize_text
from downlow.core.stages.ingest import IngestStage
from downlow.domain.errors import DownLowError, EmptyExtractionError
from downlow.domain.schemas import ExtractedText
from tests.fakes.pdf import FakePdfExtractor

if TYPE_CHECKING:
    from collections.abc import Iterator


# --------------------------------------------------------------------------- #
# Helpers: a stand-in for pdfplumber.open() returning fake pages.
# --------------------------------------------------------------------------- #


class _FakePage:
    def __init__(self, text: str | None) -> None:
        self._text = text

    def extract_text(self) -> str | None:
        return self._text


class _FakeDoc:
    def __init__(self, page_texts: list[str | None]) -> None:
        self.pages = [_FakePage(t) for t in page_texts]


@contextmanager
def _fake_open(page_texts: list[str | None]) -> Iterator[_FakeDoc]:
    yield _FakeDoc(page_texts)


def _extract_with_pages(tmp_path: Path, page_texts: list[str | None], raw: bytes = b"%PDF-fake") -> ExtractedText:
    """Run the real extractor with ``pdfplumber.open`` patched to yield ``page_texts``."""
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(raw)
    with patch(
        "downlow.adapters.pdf.extractor.pdfplumber.open",
        return_value=_fake_open(page_texts),
    ):
        return PdfPlumberExtractor().extract(pdf)


# --------------------------------------------------------------------------- #
# normalize_text — pure logic, table-driven.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # hyphen-wrapped word join
        ("exam-\nple", "example"),
        # do NOT join across a non-alpha boundary (year ranges stay split)
        ("2019-\n2020", "2019-\n2020"),
        # collapse runs of horizontal whitespace
        ("a    b\t\tc", "a b c"),
        # collapse 3+ blank lines to a single paragraph break
        ("para1\n\n\n\npara2", "para1\n\npara2"),
        # trim whitespace around newlines
        ("line1   \n   line2", "line1\nline2"),
        # normalise CRLF / CR line endings
        ("a\r\nb\rc", "a\nb\nc"),
        # strip surrounding whitespace
        ("   hello   ", "hello"),
        # strip control characters
        ("ab\x00\x07cd", "abcd"),
        # Unicode line/paragraph separators are TRANSLATED to newline, not deleted
        (f"a{chr(0x2028)}b", "a\nb"),
        (f"a{chr(0x2029)}b", "a\nb"),
        # non-breaking / Unicode spaces collapse like regular whitespace
        (f"a{chr(0xA0)}{chr(0xA0)}b", "a b"),
        (f"a{chr(0x2003)}b", "a b"),
        # soft-hyphen line-wrap joins; a standalone soft hyphen is dropped
        (f"exam{chr(0xAD)}\nple", "example"),
        (f"a{chr(0xAD)}b", "ab"),
    ],
)
def test_normalize_text_cases(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


def test_normalize_text_is_idempotent() -> None:
    once = normalize_text("exam-\nple   text\n\n\n\nmore")
    assert normalize_text(once) == once


# --------------------------------------------------------------------------- #
# Per-page extraction + assembly.
# --------------------------------------------------------------------------- #


def test_per_page_extraction_assembled(tmp_path: Path) -> None:
    result = _extract_with_pages(tmp_path, ["Page one text.", "Page two text."])
    assert result.page_count == 2
    assert result.pages == ["Page one text.", "Page two text."]
    assert "Page one text." in result.full_text
    assert "Page two text." in result.full_text


def test_none_pages_are_treated_as_empty_strings(tmp_path: Path) -> None:
    # pdfplumber returns None for a page with no text layer; we coerce to "".
    result = _extract_with_pages(tmp_path, ["Real content on a page here.", None])
    assert result.page_count == 2
    assert result.pages[1] == ""


def test_hyphen_wrap_joined_across_pages_full_text(tmp_path: Path) -> None:
    # A word split by hyphenation at a line break is rejoined in full_text.
    result = _extract_with_pages(tmp_path, ["some long exam-\nple sentence to give it bulk and weight here"])
    assert "example" in result.full_text


# --------------------------------------------------------------------------- #
# Hashes: source vs content, distinct and stable.
# --------------------------------------------------------------------------- #


def test_source_and_content_hash_distinct(tmp_path: Path) -> None:
    result = _extract_with_pages(tmp_path, ["Hello world, this is the body text of a paper."], raw=b"%PDF-distinct")
    assert result.source_hash != result.content_hash
    # source_hash is over raw bytes; content_hash over the normalised text.
    assert result.source_hash == hashlib.sha256(b"%PDF-distinct").hexdigest()
    assert result.content_hash == hashlib.sha256(result.full_text.encode("utf-8")).hexdigest()


def test_content_hash_stable_across_cosmetic_differences(tmp_path: Path) -> None:
    a = _extract_with_pages(tmp_path, ["The   quick brown   fox jumps over the lazy dog repeatedly."])
    b = _extract_with_pages(tmp_path, ["The quick brown fox jumps over the lazy dog repeatedly."])
    assert a.content_hash == b.content_hash


def test_source_hash_differs_for_different_bytes(tmp_path: Path) -> None:
    a = _extract_with_pages(tmp_path, ["same text body here for both documents"], raw=b"%PDF-A")
    b = _extract_with_pages(tmp_path, ["same text body here for both documents"], raw=b"%PDF-B")
    assert a.source_hash != b.source_hash
    assert a.content_hash == b.content_hash  # identical normalised text


# --------------------------------------------------------------------------- #
# Empty / scanned handling.
# --------------------------------------------------------------------------- #


def test_empty_extraction_raises(tmp_path: Path) -> None:
    with pytest.raises(EmptyExtractionError) as exc:
        _extract_with_pages(tmp_path, [None, "   ", ""])
    assert exc.value.page_count == 3


def test_empty_extraction_error_is_a_downlow_error(tmp_path: Path) -> None:
    with pytest.raises(DownLowError):
        _extract_with_pages(tmp_path, [""])


def test_sparse_text_flagged_scanned(tmp_path: Path) -> None:
    # Non-empty but well under 100 chars/page across 2 pages -> is_scanned.
    result = _extract_with_pages(tmp_path, ["Fig 1", "p. 2"])
    assert result.is_scanned is True
    assert result.full_text  # not empty


def test_dense_text_not_flagged_scanned(tmp_path: Path) -> None:
    body = "This is a properly extracted page with plenty of real text content on it. " * 3
    result = _extract_with_pages(tmp_path, [body])
    assert result.is_scanned is False


def test_short_single_page_not_flagged_scanned(tmp_path: Path) -> None:
    # A genuinely short one-page note must NOT be mistaken for a scan.
    result = _extract_with_pages(tmp_path, ["See appendix A for the full derivation and the proof."])
    assert result.is_scanned is False


def test_zero_page_pdf_raises_empty(tmp_path: Path) -> None:
    with pytest.raises(EmptyExtractionError) as exc:
        _extract_with_pages(tmp_path, [])
    assert exc.value.page_count == 0


# --------------------------------------------------------------------------- #
# IngestStage cache: miss then hit, force bypass.
# --------------------------------------------------------------------------- #


def test_cache_miss_then_hit(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-cache-test")
    extractor = FakePdfExtractor()
    stage = IngestStage(extractor, cache_dir=tmp_path / "cache")

    first = stage.run(pdf)
    assert extractor.call_count == 1  # miss -> extracted

    second = stage.run(pdf)
    assert extractor.call_count == 1  # hit -> NOT re-extracted
    assert second == first


def test_cache_sidecar_written_at_source_hash_path(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    raw = b"%PDF-sidecar"
    pdf.write_bytes(raw)
    stage = IngestStage(FakePdfExtractor(), cache_dir=tmp_path / "cache")
    stage.run(pdf)

    source_hash = hashlib.sha256(raw).hexdigest()
    sidecar = tmp_path / "cache" / "extracted" / f"{source_hash}.json"
    assert sidecar.exists()
    # round-trips back into an ExtractedText
    loaded = ExtractedText.model_validate_json(sidecar.read_text(encoding="utf-8"))
    assert loaded.source_hash == source_hash


def test_force_bypasses_cache(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-force")
    extractor = FakePdfExtractor()
    stage = IngestStage(extractor, cache_dir=tmp_path / "cache")

    stage.run(pdf)
    assert extractor.call_count == 1
    stage.run(pdf, force=True)
    assert extractor.call_count == 2  # re-extracted despite the sidecar


def test_corrupt_cache_treated_as_miss(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    raw = b"%PDF-corrupt"
    pdf.write_bytes(raw)
    cache_dir = tmp_path / "cache"
    source_hash = hashlib.sha256(raw).hexdigest()
    sidecar = cache_dir / "extracted" / f"{source_hash}.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("{ not valid json", encoding="utf-8")

    extractor = FakePdfExtractor()
    stage = IngestStage(extractor, cache_dir=cache_dir)
    stage.run(pdf)
    assert extractor.call_count == 1  # corrupt sidecar -> miss -> extracted
    # and the sidecar is overwritten with a valid payload
    ExtractedText.model_validate_json(sidecar.read_text(encoding="utf-8"))


def test_distinct_pdfs_get_distinct_cache_entries(tmp_path: Path) -> None:
    pdf_a = tmp_path / "a.pdf"
    pdf_b = tmp_path / "b.pdf"
    pdf_a.write_bytes(b"%PDF-A-bytes")
    pdf_b.write_bytes(b"%PDF-B-bytes")
    extractor = FakePdfExtractor()
    stage = IngestStage(extractor, cache_dir=tmp_path / "cache")

    stage.run(pdf_a)
    stage.run(pdf_b)
    assert extractor.call_count == 2  # different source_hash -> two misses
