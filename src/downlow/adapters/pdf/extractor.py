"""PdfExtractor implementation backed by ``pdfplumber`` (F1, the INGEST adapter).

This is the ONLY module allowed to import ``pdfplumber``. Swapping the backend
(PyMuPDF / pypdfium2) is a one-class change behind the :class:`PdfExtractor`
port; nothing in ``core``/``domain`` changes.

Responsibilities (per PROJECT_PLAN.md -> Stage 1 INGEST):

* read raw bytes -> ``source_hash`` (sha256 of the PDF bytes);
* extract per-page text;
* normalise (the pure, separately-testable :func:`normalize_text`) -> ``content_hash``;
* scanned/empty detection: raise :class:`EmptyExtractionError` when there is
  effectively no text; set ``is_scanned=True`` when text is suspiciously sparse
  relative to ``page_count`` but non-empty. Never feed garbage downstream, never
  silently truncate.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import pdfplumber

from downlow.domain.errors import EmptyExtractionError
from downlow.domain.schemas import ExtractedText

# A non-empty page with fewer than this many characters of real text is
# "suspiciously sparse" — typical of an image-only page with stray text. If the
# *whole document* averages below this per page (while not being empty overall),
# we flag ``is_scanned`` so downstream can decide (this phase: surface it).
_MIN_CHARS_PER_PAGE = 100

# Below this total, after stripping, we treat the extraction as empty and refuse.
_MIN_TOTAL_CHARS = 1

# Control chars to strip, excluding the whitespace we normalise separately
# (\t \n \r). Matches C0/C1 controls plus the Unicode line/paragraph
# separators (U+2028 / U+2029) that pdfplumber can emit.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u2028\u2029]")

# A word split across a line break by hyphenation, e.g. ``exam-\nple``. We join
# only when both sides are alphabetic so we don't merge genuine compounds or
# numbers (``2019-\n2020`` stays split).
_HYPHEN_WRAP = re.compile(r"([A-Za-z])-\n([A-Za-z])")

# Runs of horizontal whitespace (spaces / tabs) that should collapse to one space.
_HORIZONTAL_WS = re.compile(r"[ \t]+")

# Three-or-more newlines collapse to a paragraph break (two newlines).
_BLANK_LINES = re.compile(r"\n{3,}")

# Spaces hugging a newline are redundant after horizontal-ws collapse.
_WS_AROUND_NEWLINE = re.compile(r"[ \t]*\n[ \t]*")

# The page separator used to join per-page text before normalisation; a single
# newline is enough because normalisation then collapses runs.
_PAGE_JOIN = "\n"


def normalize_text(text: str) -> str:
    """Normalise extracted PDF text to a stable, hash-friendly form.

    Pure (no I/O) and deliberately separate so it is unit-tested in isolation and
    so ``content_hash`` is stable across cosmetically-different extractions of the
    same paper. Steps, in order:

    1. Unicode NFC normalisation (canonical form).
    2. Strip control characters (excluding tab/newline).
    3. Normalise line endings (``\\r\\n`` / ``\\r`` -> ``\\n``).
    4. De-hyphenate line-wrapped words (``exam-\\nple`` -> ``example``).
    5. Collapse runs of horizontal whitespace to a single space.
    6. Trim whitespace around newlines and collapse 3+ blank lines to one break.
    7. Strip leading/trailing whitespace.
    """
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL_CHARS.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_WRAP.sub(r"\1\2", text)
    text = _HORIZONTAL_WS.sub(" ", text)
    text = _WS_AROUND_NEWLINE.sub("\n", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def _sha256(data: bytes) -> str:
    """Return the hex sha256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


class PdfPlumberExtractor:
    """``PdfExtractor`` implementation using ``pdfplumber``."""

    def extract(self, pdf_path: Path) -> ExtractedText:
        """Read, extract, and normalise the text of ``pdf_path``.

        Raises:
            EmptyExtractionError: when the PDF yields effectively no text.
            FileNotFoundError: when ``pdf_path`` does not exist (from ``read_bytes``).
        """
        raw = pdf_path.read_bytes()
        source_hash = _sha256(raw)

        raw_pages = self._extract_pages(pdf_path)
        page_count = len(raw_pages)

        pages = [normalize_text(p) for p in raw_pages]
        full_text = normalize_text(_PAGE_JOIN.join(raw_pages))

        if len(full_text) < _MIN_TOTAL_CHARS:
            raise EmptyExtractionError(
                f"PDF '{pdf_path.name}' yielded no extractable text ({page_count} page(s)); likely scanned/image-only",
                page_count=page_count,
            )

        is_scanned = self._looks_scanned(full_text, page_count)

        return ExtractedText(
            full_text=full_text,
            pages=pages,
            page_count=page_count,
            is_scanned=is_scanned,
            source_hash=source_hash,
            content_hash=_sha256(full_text.encode("utf-8")),
        )

    @staticmethod
    def _extract_pages(pdf_path: Path) -> list[str]:
        """Return the raw (un-normalised) text of each page, in document order."""
        with pdfplumber.open(pdf_path) as doc:
            return [(page.extract_text() or "") for page in doc.pages]

    @staticmethod
    def _looks_scanned(full_text: str, page_count: int) -> bool:
        """Heuristic: non-empty but too sparse to be a real text layer.

        Averaging fewer than ``_MIN_CHARS_PER_PAGE`` characters per page (while
        non-empty overall) is the signature of a mostly-image PDF with only stray
        text (page numbers, watermarks). ``page_count == 0`` cannot be sparse.
        """
        if page_count <= 0:
            return False
        return len(full_text) < _MIN_CHARS_PER_PAGE * page_count
