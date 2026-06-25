"""Unit tests for F5's pure naming utilities (``downlow.core.naming``).

Two concerns, both pure (no I/O, no LLM): the relocated path-safe ``slugify`` (now
the single source of truth shared by RENDER F3 and F5 -- the F3 render tests still
import it from ``core.stages.render`` and pass unchanged), and
``build_paper_filename`` -- the deterministic PaperMetadata -> filename builder
(convention, fallbacks, path-safety, length cap, unicode, idempotency).
"""

from __future__ import annotations

import pytest

from downlow.core.naming import build_paper_filename, slugify
from downlow.core.stages.render import slugify as render_slugify
from downlow.domain.schemas import PaperMetadata

# Fixed so the year-plausibility window is reproducible regardless of the real date.
_YEAR = 2026


def _meta(*, title: str = "", authors: list[str] | None = None, year: int | None = None) -> PaperMetadata:
    return PaperMetadata(title=title, authors=authors or [], year=year)


# --------------------------------------------------------------------------- #
# slugify relocation: the render module re-export is the SAME function.        #
# --------------------------------------------------------------------------- #


def test_render_reexports_the_shared_slugify() -> None:
    # The F3 render tests import slugify from core.stages.render; after the move it
    # must be the very same callable as core.naming.slugify (no duplicate logic).
    assert render_slugify is slugify


def test_slugify_default_behaviour_unchanged() -> None:
    # The report defaults (80-char cap, "report" fallback) are preserved so F3 keeps
    # working without a code change.
    assert slugify("Hello World") == "hello-world"
    assert slugify("") == "report"
    assert slugify("..//../etc/passwd") == "etc-passwd"
    assert len(slugify("word " * 50)) <= 80


def test_slugify_accepts_custom_cap_and_fallback() -> None:
    assert slugify("", fallback="") == ""
    # Hard char cap at 8 -> "a-very-l"; the cap is a char cap (rstrip only removes a
    # trailing hyphen), not a word-boundary cut.
    assert slugify("a very long title indeed", max_len=8) == "a-very-l"
    # When the cap lands exactly after a word, the trailing hyphen is stripped.
    assert slugify("aaa bbb ccc", max_len=4) == "aaa"


# --------------------------------------------------------------------------- #
# build_paper_filename: the convention (surname-year-titleslug.pdf).          #
# --------------------------------------------------------------------------- #


def test_full_metadata_builds_surname_year_titleslug() -> None:
    meta = _meta(title="Contrastive Learning", authors=["Jane Smith", "Bob Jones"], year=2021)
    assert build_paper_filename(meta, current_year=_YEAR) == "smith-2021-contrastive-learning.pdf"


def test_first_author_surname_is_used_not_alphabetical() -> None:
    # authors[0] is the first author; order is preserved by the extractor, and the
    # builder must take the FIRST listed surname, not a sorted one.
    meta = _meta(title="A Paper", authors=["Zoe Aaronson", "Adam Zylberberg"], year=2020)
    assert build_paper_filename(meta, current_year=_YEAR).startswith("aaronson-")


def test_missing_year_omits_the_year_segment() -> None:
    meta = _meta(title="Robustness", authors=["Jane Smith"], year=None)
    assert build_paper_filename(meta, current_year=_YEAR) == "smith-robustness.pdf"


def test_missing_authors_omits_the_surname_segment() -> None:
    meta = _meta(title="Robustness", authors=[], year=2021)
    assert build_paper_filename(meta, current_year=_YEAR) == "2021-robustness.pdf"


def test_title_only() -> None:
    meta = _meta(title="Zero Shot Transfer")
    assert build_paper_filename(meta, current_year=_YEAR) == "zero-shot-transfer.pdf"


def test_author_only() -> None:
    meta = _meta(authors=["Jane Smith"])
    assert build_paper_filename(meta, current_year=_YEAR) == "smith.pdf"


def test_no_etal_for_many_authors() -> None:
    # Multi-author papers do NOT get an "-etal" segment; just the first surname.
    authors = ["Jane Smith", "Bob Jones", "Carol White", "Dan Black", "Eve Green"]
    meta = _meta(title="Big Collab", authors=authors, year=2022)
    name = build_paper_filename(meta, current_year=_YEAR)
    assert "etal" not in name
    assert name == "smith-2022-big-collab.pdf"  # only the first author's surname


# --------------------------------------------------------------------------- #
# Surname extraction: particles, multi-part, single-token, unicode.           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("author", "expected_surname"),
    [
        ("Jane Smith", "smith"),
        ("Jane Q. Smith", "smith"),
        ("Jane van der Berg", "vanderberg"),
        ("Ludwig von Mises", "vonmises"),
        ("Maria de los Santos", "delossantos"),
        ("The BERT Team", "team"),  # multi-token group author -> trailing token (no leading particle)
        ("Madonna", "madonna"),  # single-token author taken whole
    ],
)
def test_surname_extraction(author: str, expected_surname: str) -> None:
    meta = _meta(title="T", authors=[author], year=2020)
    assert build_paper_filename(meta, current_year=_YEAR) == f"{expected_surname}-2020-t.pdf"


def test_unicode_surname_is_ascii_folded() -> None:
    # chr(0x00FC) is u-umlaut; "Muller" after folding. Author full name with diacritics.
    meta = _meta(title="T", authors=["Hans M" + chr(0x00FC) + "ller"], year=2020)
    assert build_paper_filename(meta, current_year=_YEAR) == "muller-2020-t.pdf"


def test_cjk_surname_with_no_ascii_falls_through_to_other_segments() -> None:
    # A CJK-only author name has no [a-z0-9] after folding -> the surname segment is
    # dropped (empty), and the filename leans on year + title instead of crashing.
    cjk = chr(0x4E2D) + chr(0x6587)
    meta = _meta(title="A Study", authors=[cjk], year=2021)
    assert build_paper_filename(meta, current_year=_YEAR) == "2021-a-study.pdf"


# --------------------------------------------------------------------------- #
# Title handling: subtitle drop, length cap, punctuation.                     #
# --------------------------------------------------------------------------- #


def test_subtitle_after_colon_is_dropped() -> None:
    meta = _meta(title="BERT: Pre-training of Deep Bidirectional Transformers", authors=["Jacob Devlin"], year=2019)
    name = build_paper_filename(meta, current_year=_YEAR)
    assert name == "devlin-2019-bert.pdf"  # subtitle after the colon dropped


def test_title_slug_is_length_capped() -> None:
    long_title = "word " * 40
    meta = _meta(title=long_title, authors=["Jane Smith"], year=2021)
    name = build_paper_filename(meta, current_year=_YEAR)
    title_part = name.removeprefix("smith-2021-").removesuffix(".pdf")
    assert len(title_part) <= 50
    assert not title_part.endswith("-")


def test_title_only_punctuation_drops_the_title_segment() -> None:
    meta = _meta(title="!!!", authors=["Jane Smith"], year=2021)
    assert build_paper_filename(meta, current_year=_YEAR) == "smith-2021.pdf"


# --------------------------------------------------------------------------- #
# Year plausibility: out-of-range years are dropped, not baked in.            #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad_year", [0, 1899, 12, 9999, 3000])
def test_implausible_year_is_dropped(bad_year: int) -> None:
    meta = _meta(title="Paper", authors=["Jane Smith"], year=bad_year)
    assert build_paper_filename(meta, current_year=_YEAR) == "smith-paper.pdf"


def test_next_year_is_allowed() -> None:
    # Papers dated to next year's venue are common near a year boundary.
    meta = _meta(title="Paper", authors=["Jane Smith"], year=_YEAR + 1)
    assert build_paper_filename(meta, current_year=_YEAR) == f"smith-{_YEAR + 1}-paper.pdf"


def test_year_two_beyond_current_is_dropped() -> None:
    meta = _meta(title="Paper", authors=["Jane Smith"], year=_YEAR + 2)
    assert build_paper_filename(meta, current_year=_YEAR) == "smith-paper.pdf"


# --------------------------------------------------------------------------- #
# All-metadata-missing fallback: deterministic + unique from the PDF bytes.   #
# --------------------------------------------------------------------------- #


def test_no_metadata_falls_back_to_paper_hash() -> None:
    name = build_paper_filename(_meta(), current_year=_YEAR, pdf_bytes=b"%PDF-some-bytes")
    assert name.startswith("paper-")
    assert name.endswith(".pdf")
    stem = name.removeprefix("paper-").removesuffix(".pdf")
    assert len(stem) == 8 and stem.isalnum()


def test_no_metadata_fallback_is_deterministic_for_the_same_pdf() -> None:
    a = build_paper_filename(_meta(), current_year=_YEAR, pdf_bytes=b"%PDF-same")
    b = build_paper_filename(_meta(), current_year=_YEAR, pdf_bytes=b"%PDF-same")
    assert a == b  # idempotent: re-naming the same PDF yields the same name


def test_no_metadata_fallback_differs_for_different_pdfs() -> None:
    a = build_paper_filename(_meta(), current_year=_YEAR, pdf_bytes=b"%PDF-one")
    b = build_paper_filename(_meta(), current_year=_YEAR, pdf_bytes=b"%PDF-two")
    assert a != b  # two distinct no-metadata PDFs never collide


def test_no_metadata_without_bytes_is_literal_paper_pdf() -> None:
    assert build_paper_filename(_meta(), current_year=_YEAR) == "paper.pdf"


# --------------------------------------------------------------------------- #
# Path-safety: an adversarial title / author can never escape the directory.  #
# --------------------------------------------------------------------------- #


def test_adversarial_metadata_is_path_safe() -> None:
    meta = _meta(
        title="../../etc/passwd",
        authors=["../../../root"],
        year=2021,
    )
    name = build_paper_filename(meta, current_year=_YEAR)
    for bad in ("/", "\\", "..", " "):
        assert bad not in name
    assert not name.startswith(".")
    assert name.endswith(".pdf")


def test_builder_is_deterministic() -> None:
    meta = _meta(title="Contrastive Learning", authors=["Jane Smith"], year=2021)
    first = build_paper_filename(meta, current_year=_YEAR)
    second = build_paper_filename(meta, current_year=_YEAR)
    assert first == second
