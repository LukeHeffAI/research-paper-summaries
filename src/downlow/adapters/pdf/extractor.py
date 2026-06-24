"""PdfExtractor implementation backed by ``pdfplumber`` (F1, the INGEST adapter).

This is the ONLY module allowed to import ``pdfplumber``. Swapping the backend
(PyMuPDF / pypdfium2) is a one-class change behind the :class:`PdfExtractor`
port; nothing in ``core``/``domain`` changes.

Responsibilities (per PROJECT_PLAN.md, Stage 1 INGEST):

* read raw bytes into ``source_hash`` (sha256 of the PDF bytes);
* extract per-page text;
* normalise (the pure, separately-testable :func:`normalize_text`) into ``content_hash``;
* scanned/empty detection: raise :class:`EmptyExtractionError` when there is
  effectively no text; set ``is_scanned=True`` when text is suspiciously sparse
  relative to ``page_count`` but non-empty. Never feed garbage downstream, never
  silently truncate.

Unicode codepoints are built with ``chr()`` rather than ``\\u`` escapes or literal
glyphs so the source stays pure ASCII (unambiguous, ruff-clean).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import pdfplumber

from downlow.domain.errors import EmptyExtractionError
from downlow.domain.schemas import ExtractedText

# Conservative "near-empty page" floor: the average characters of real text per
# page below which we flag ``is_scanned`` (likely image-only / needs OCR). Kept
# low on purpose so a genuinely short note (e.g. a one-page memo) is NOT flagged;
# this is a small absolute floor, not the plan's illustrative
# 0.1 * expected_chars_per_page (which over-flags short documents). The flag is
# informational this phase (it never raises).
_MIN_CHARS_PER_PAGE = 10

# Below this total (after normalisation) we treat the extraction as empty and refuse.
_MIN_TOTAL_CHARS = 1

# Unicode line / paragraph separators (U+2028 / U+2029) that pdfplumber can emit
# at line breaks. We TRANSLATE these to newline (not delete) so the words on
# either side are not fused (which would corrupt the text and content_hash).
_LINE_SEP = chr(0x2028)
_PARA_SEP = chr(0x2029)

# Soft hyphen (U+00AD): a discretionary hyphen. At a line wrap it is removed and
# the word joined; anywhere else it is invisible and dropped.
_SOFT_HYPHEN = chr(0x00AD)

# C0/C1 control chars to strip, keeping the whitespace handled elsewhere (tab,
# newline) and the line separators handled above.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# A word split across a line break by ASCII hyphenation (an "exam-" / "ple" wrap).
# Join only when both sides are alphabetic so genuine compounds / number ranges
# (a "2019-" / "2020" wrap) stay split.
_HYPHEN_WRAP = re.compile(r"([A-Za-z])-\n([A-Za-z])")

# Runs of horizontal whitespace that collapse to a single space, including the
# common Unicode spaces (NBSP U+00A0, U+2000-U+200A, NNBSP U+202F, U+205F,
# ideographic U+3000) so content_hash is stable when one extraction emits an NBSP
# where another emits a regular space.
_HORIZONTAL_WS = re.compile(
    "[ \t" + chr(0x00A0) + chr(0x2000) + "-" + chr(0x200A) + chr(0x202F) + chr(0x205F) + chr(0x3000) + "]+"
)

# Three-or-more newlines collapse to a single paragraph break (two newlines).
_BLANK_LINES = re.compile(r"\n{3,}")

# Spaces hugging a newline are redundant after the horizontal-ws collapse.
_WS_AROUND_NEWLINE = re.compile(r"[ \t]*\n[ \t]*")

# Page separator used to join per-page text before normalisation; a single
# newline suffices because normalisation then collapses runs.
_PAGE_JOIN = "\n"


def normalize_text(text: str) -> str:
    """Normalise extracted PDF text to a stable, hash-friendly form.

    Pure (no I/O) and deliberately separate so it is unit-tested in isolation and
    so ``content_hash`` is stable across cosmetically-different extractions of the
    same paper. Steps, in order:

    1. Unicode NFC normalisation (canonical form).
    2. Translate line / paragraph separators (CRLF, CR, U+2028, U+2029) to newline
       (translated, not deleted, so words on either side are not fused).
    3. Strip remaining C0/C1 control characters (keeping tab and newline).
    4. Resolve soft hyphens (U+00AD): join discretionary line-wraps, drop the rest.
    5. De-hyphenate ASCII line-wrapped words (an "exam-" / "ple" wrap -> "example").
    6. Collapse runs of horizontal whitespace (incl. NBSP / Unicode spaces) to one space.
    7. Trim whitespace around newlines and collapse 3+ blank lines to one break.
    8. Strip leading/trailing whitespace.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(_LINE_SEP, "\n").replace(_PARA_SEP, "\n")
    text = _CONTROL_CHARS.sub("", text)
    text = text.replace(_SOFT_HYPHEN + "\n", "").replace(_SOFT_HYPHEN, "")
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
        text (page numbers, watermarks). ``page_count <= 0`` cannot be sparse.
        """
        if page_count <= 0:
            return False
        return len(full_text) < _MIN_CHARS_PER_PAGE * page_count
