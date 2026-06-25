"""Shared pure naming utilities: the path-safe ``slugify`` + the F5 filename builder.

PURE: stdlib + ``domain`` only. No I/O, no third-party SDK -- every function here
is deterministic and unit-testable in isolation, and is the single source of truth
for turning an arbitrary string (or a :class:`PaperMetadata`) into a filesystem-safe
name.

Two concerns live here:

* :func:`slugify` -- the deterministic, path-safe slug used by RENDER (F3) for the
  report's on-disk filename and by F5 for the title segment of a paper filename. It
  was factored out of ``core/stages/render.py`` so both features share one
  implementation rather than duplicating the path-safe slug logic; ``render.py``
  re-exports it for backward compatibility.
* :func:`build_paper_filename` -- the F5 heuristic: a :class:`PaperMetadata`
  (model-extracted title/authors/year) -> a clean, deterministic, path-traversal-proof
  ``surname-year-title-slug.pdf`` filename, with graceful fallbacks when metadata is
  missing. It NEVER trusts the model for the on-disk name -- the model supplies the
  faithful metadata; this code owns the filename (so it is reproducible across runs
  and the model can never escape the target directory).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

from downlow.domain.schemas import PaperMetadata

# --------------------------------------------------------------------------- #
# slugify -- the canonical path-safe slug (shared by RENDER F3 + F5).          #
# --------------------------------------------------------------------------- #

# Slug safety bounds: lowercase ASCII alnum + single hyphens, no leading/trailing
# hyphen, capped so a pathological title cannot produce an unwieldy filename.
_MAX_SLUG_LEN = 80
_FALLBACK_SLUG = "report"

# Non-[a-z0-9] runs collapse to a single hyphen during slugify.
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def slugify(title: str, *, max_len: int = _MAX_SLUG_LEN, fallback: str = _FALLBACK_SLUG) -> str:
    """Derive a lowercase, hyphen-separated, filesystem-safe slug from ``title``.

    Deterministic and path-safe by construction: only ``[a-z0-9-]`` survive, so the
    result can never contain a path separator (``/`` / ``\\``), ``..``, a leading
    dot, a space, or any shell-significant character -- the model (or a paper title)
    can never escape the target directory. An empty result (a title of only
    punctuation / non-ASCII) falls back to ``fallback``. Length is capped at
    ``max_len`` so a pathological title cannot produce an unwieldy filename.

    ``max_len`` / ``fallback`` are parameters so F5 can ask for a shorter title
    segment and a different fallback while RENDER keeps the report defaults; the
    bare two-argument call is unchanged, so :data:`downlow.core.stages.render.slugify`
    (the re-export) behaves exactly as before.

    Pure and module-level so it is unit-tested in isolation. Same title in => same
    slug out (idempotent re-renders/re-names overwrite in place rather than
    duplicating).
    """
    lowered = title.strip().lower()
    slug = _NON_SLUG_CHARS.sub("-", lowered).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or fallback


# --------------------------------------------------------------------------- #
# F5 -- the deterministic paper-filename builder.                              #
# --------------------------------------------------------------------------- #

# The minimum year a faithful publication year can sensibly take. Anything below
# this (or above current_year + 1) is treated as noise and dropped. The upper
# bound is supplied by the caller (so this module stays free of `datetime.now`,
# keeping it pure and its output reproducible in tests / cache keys).
_MIN_PLAUSIBLE_YEAR = 1900

# Title segment of a paper filename is capped shorter than a report slug: a paper
# filename already carries the surname + year, so the title only needs to be
# recognisable, not exhaustive (the academic-writing advisor's ~50-char guidance).
_MAX_TITLE_SLUG_LEN = 50

# Name particles that are part of a surname rather than a separate given/middle
# name. Lowercased; the first-author surname keeps these joined (e.g. "van der
# Berg" -> "vanderberg") so the surname segment is stable and recognisable.
_SURNAME_PARTICLES = frozenset(
    {
        "van",
        "von",
        "der",
        "den",
        "de",
        "del",
        "della",
        "di",
        "da",
        "dos",
        "du",
        "la",
        "las",
        "le",
        "lo",
        "los",
        "el",
        "al",
        "bin",
        "ibn",
    }
)

# The all-metadata-missing fallback: a deterministic, unique name from the PDF
# bytes so re-ingesting the same PDF yields the same name (idempotency) and two
# different no-metadata PDFs never collide. Prefixed so these sort together and are
# a visible "extraction produced nothing" signal.
_NO_METADATA_PREFIX = "paper"
_NO_METADATA_HASH_LEN = 8


def build_paper_filename(metadata: PaperMetadata, *, current_year: int, pdf_bytes: bytes | None = None) -> str:
    """Build a clean, deterministic, path-safe PDF filename from ``metadata``.

    The F5 convention (academic-writing advisor): ``surname-year-title-slug.pdf``
    leading with the first author's surname (how researchers recall and scan a
    paper folder), then the year, then a short title slug. Missing segments are
    *omitted* rather than filled with placeholders, so partial metadata still yields
    a clean name:

    * all three -> ``smith-2021-contrastive-learning.pdf``
    * no year   -> ``smith-contrastive-learning.pdf``
    * no author -> ``2021-contrastive-learning.pdf``
    * title only -> ``contrastive-learning.pdf``
    * author only -> ``smith.pdf``
    * nothing usable -> ``paper-<8-char-hash>.pdf`` (from ``pdf_bytes`` if given,
      else the literal ``paper.pdf``) -- deterministic and unique, never a
      collision-guaranteed ``untitled.pdf``.

    Deterministic and path-traversal-proof: every segment is run through
    :func:`slugify` (surname) or built from it (title), so no segment can contain a
    path separator, ``..``, or a leading dot. ``current_year`` is injected (not read
    from the clock) so the year-plausibility bound is reproducible in tests and the
    builder stays pure.

    Args:
        metadata: the model-extracted :class:`PaperMetadata` (faithful; may be empty).
        current_year: today's year, used only as the upper year-plausibility bound.
        pdf_bytes: the source PDF bytes, used ONLY to build the unique all-missing
            fallback name; ``None`` falls back to the literal ``paper.pdf``.

    Returns:
        A path-safe filename ending in ``.pdf``.
    """
    segments: list[str] = []

    surname = _first_author_surname(metadata.authors)
    if surname:
        segments.append(surname)

    year = _plausible_year(metadata.year, current_year=current_year)
    if year is not None:
        segments.append(str(year))

    title_slug = _title_slug(metadata.title)
    if title_slug:
        segments.append(title_slug)

    if not segments:
        return f"{_no_metadata_stem(pdf_bytes)}.pdf"
    return "-".join(segments) + ".pdf"


def _first_author_surname(authors: list[str]) -> str:
    """The first author's surname, ASCII-folded and slugified, or ``""``.

    ``authors[0]`` is the first listed author (the extractor preserves order). The
    surname is the trailing run of name tokens including any leading particles
    ("van der Berg" -> ``vanderberg``); a single-token name is taken whole (a group
    / consortium author like "The BERT Team" -> ``thebertteam`` -- weak but stable).
    The model never picks the on-disk name, so an adversarial author string still
    cannot escape the directory: the result is slugified with internal hyphens
    stripped (a surname is one path-safe token).
    """
    if not authors:
        return ""
    first = authors[0].strip()
    if not first:
        return ""

    tokens = _ascii_fold(first).split()
    if not tokens:
        return ""
    if len(tokens) == 1:
        surname_tokens = tokens
    else:
        # Walk left from the last token, absorbing surname particles, so
        # "Jane van der Berg" -> ["van", "der", "berg"].
        idx = len(tokens) - 1
        while idx > 0 and tokens[idx - 1].lower() in _SURNAME_PARTICLES:
            idx -= 1
        surname_tokens = tokens[idx:]

    # Join the surname tokens into one slug token (no internal hyphens) so the
    # surname is a single recognisable segment of the filename.
    joined = "".join(surname_tokens)
    return slugify(joined, max_len=_MAX_TITLE_SLUG_LEN, fallback="").replace("-", "")


def _plausible_year(year: int | None, *, current_year: int) -> int | None:
    """Return ``year`` only when it is a plausible publication year, else ``None``.

    Faithfulness guard: an out-of-range value (a parsing artefact, a body-text year
    the model wrongly picked up, a future date) is dropped rather than baked into a
    filename. The window is ``[1900, current_year + 1]`` (the ``+1`` admits papers
    dated to next year's venue, common near year boundaries).
    """
    if year is None:
        return None
    if _MIN_PLAUSIBLE_YEAR <= year <= current_year + 1:
        return year
    return None


def _title_slug(title: str) -> str:
    """A short, recognisable title slug, or ``""`` when the title yields nothing.

    Drops a subtitle after the first colon (subtitles carry the length and noise),
    then slugifies and caps shorter than a report slug -- the filename already leads
    with surname + year, so the title only needs to be recognisable. An empty /
    punctuation-only / non-ASCII-only title yields ``""`` (the segment is omitted),
    NOT the report fallback.
    """
    stripped = title.strip()
    if not stripped:
        return ""
    main = stripped.split(":", 1)[0].strip() or stripped
    return slugify(main, max_len=_MAX_TITLE_SLUG_LEN, fallback="")


def _no_metadata_stem(pdf_bytes: bytes | None) -> str:
    """The deterministic stem for a PDF with no usable metadata.

    ``paper-<8-char sha256 of the PDF bytes>`` so re-ingesting the same PDF yields
    the same name (idempotent) and two distinct no-metadata PDFs never collide. With
    no bytes available, the literal ``paper`` (the only non-unique case, acceptable
    only when the caller has no PDF to hash).
    """
    if pdf_bytes is None:
        return _NO_METADATA_PREFIX
    digest = hashlib.sha256(pdf_bytes).hexdigest()[:_NO_METADATA_HASH_LEN]
    return f"{_NO_METADATA_PREFIX}-{digest}"


def _ascii_fold(text: str) -> str:
    """Fold ``text`` to ASCII (drop diacritics) so non-Latin names slug cleanly.

    NFKD-decomposes then strips combining marks, so e.g. ``M`` + combining-umlaut
    -> ``Mu``-style folding upstream of :func:`slugify`. Characters with no ASCII
    decomposition (e.g. CJK) are left for :func:`slugify` to drop.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))
