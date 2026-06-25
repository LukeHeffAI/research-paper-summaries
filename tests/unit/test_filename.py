"""Unit tests for F5's FilenameHeuristic service (extract / suggest / apply).

Runs on the FakeLLMClient (and the fake extractor where the text fallback fires):
no Anthropic key, no network, no pdfplumber. Covers the LLM metadata extraction
(native-PDF default + large-PDF text fallback), the pure suggest() composition, and
the non-interactive apply() rename (idempotency, clobber-refusal, path-safety).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from downlow.config.models import ModelConfig
from downlow.config.profiles import MetadataConfig
from downlow.core.prompts.metadata import METADATA_SYSTEM_PROMPT
from downlow.core.services.filename import FilenameHeuristic
from downlow.domain.errors import LLMError
from downlow.domain.schemas import ExtractedText, PaperMetadata
from tests.fakes.llm import FakeLLMClient
from tests.fakes.pdf import FakePdfExtractor

_YEAR = 2026


def _cfg() -> MetadataConfig:
    return MetadataConfig(model=ModelConfig(id="claude-sonnet-4-6", max_tokens=512, effort="low"))


def _heuristic(
    *, llm: FakeLLMClient | None = None, extractor: FakePdfExtractor | None = None
) -> tuple[FilenameHeuristic, FakeLLMClient]:
    llm = llm or FakeLLMClient(result=PaperMetadata(title="A Paper", authors=["Jane Smith"], year=2021))
    return FilenameHeuristic(llm, extractor=extractor, current_year=_YEAR), llm


def _write_pdf(path: Path, data: bytes = b"%PDF-fake") -> Path:
    path.write_bytes(data)
    return path


# --------------------------------------------------------------------------- #
# extract: native-PDF default path + the metadata schema/prompt.              #
# --------------------------------------------------------------------------- #


def test_extract_sends_native_pdf_with_metadata_prompt(tmp_path: Path) -> None:
    heuristic, llm = _heuristic()
    pdf = _write_pdf(tmp_path / "paper.pdf")

    meta = heuristic.extract(pdf, _cfg())

    assert isinstance(meta, PaperMetadata)
    assert meta.authors == ["Jane Smith"]
    assert llm.call_count == 1
    call = llm.calls[0]
    assert call.document.is_pdf  # native-PDF path by default
    assert call.system == METADATA_SYSTEM_PROMPT  # the frozen, cache-stable prompt
    assert call.max_tokens == 512  # the cheap metadata budget


def test_extract_passes_through_empty_metadata_faithfully(tmp_path: Path) -> None:
    # The model found nothing -> empty fields flow through unchanged (no fabrication).
    llm = FakeLLMClient(result=PaperMetadata())
    heuristic, _ = _heuristic(llm=llm)
    pdf = _write_pdf(tmp_path / "paper.pdf")

    meta = heuristic.extract(pdf, _cfg())
    assert meta.title == ""
    assert meta.authors == []
    assert meta.year is None


# --------------------------------------------------------------------------- #
# extract: the large-PDF text fallback.                                       #
# --------------------------------------------------------------------------- #


def test_large_pdf_falls_back_to_front_matter_text(tmp_path: Path) -> None:
    big = b"%PDF" + b"x" * (21 * 1024 * 1024)  # over the 20 MB inline cap
    long_text = "Title Line\nJane Smith\n" + "body " * 5000  # well over the 6000-char front-matter slice
    extracted = ExtractedText(
        full_text=long_text,
        pages=[long_text],
        page_count=1,
        is_scanned=False,
        source_hash="src",
        content_hash="cnt",
    )
    extractor = FakePdfExtractor(result=extracted)
    heuristic, llm = _heuristic(extractor=extractor)
    pdf = _write_pdf(tmp_path / "big.pdf", big)

    heuristic.extract(pdf, _cfg())

    call = llm.calls[0]
    assert not call.document.is_pdf  # fell back to text
    assert call.document.text is not None
    assert len(call.document.text) <= 6000  # only the front matter slice, not the whole body


def test_large_pdf_without_extractor_raises(tmp_path: Path) -> None:
    big = b"%PDF" + b"x" * (21 * 1024 * 1024)
    heuristic, _ = _heuristic(extractor=None)  # no fallback wired
    pdf = _write_pdf(tmp_path / "big.pdf", big)

    with pytest.raises(LLMError, match="too large to inline"):
        heuristic.extract(pdf, _cfg())


# --------------------------------------------------------------------------- #
# suggest / suggest_for_pdf: the pure builder composition.                    #
# --------------------------------------------------------------------------- #


def test_suggest_builds_the_deterministic_filename() -> None:
    heuristic, _ = _heuristic()
    meta = PaperMetadata(title="Contrastive Learning", authors=["Jane Smith"], year=2021)
    assert heuristic.suggest(meta) == "smith-2021-contrastive-learning.pdf"


def test_suggest_for_pdf_extracts_then_builds(tmp_path: Path) -> None:
    llm = FakeLLMClient(result=PaperMetadata(title="Zero Shot Transfer", authors=["Ada Lovelace"], year=2020))
    heuristic, _ = _heuristic(llm=llm)
    pdf = _write_pdf(tmp_path / "raw.pdf")

    suggestion = heuristic.suggest_for_pdf(pdf, _cfg())
    assert suggestion.filename == "lovelace-2020-zero-shot-transfer.pdf"
    assert suggestion.metadata.title == "Zero Shot Transfer"


def test_suggest_for_pdf_no_metadata_uses_pdf_hash_fallback(tmp_path: Path) -> None:
    llm = FakeLLMClient(result=PaperMetadata())  # nothing extracted
    heuristic, _ = _heuristic(llm=llm)
    pdf = _write_pdf(tmp_path / "mystery.pdf", b"%PDF-unique-bytes")

    suggestion = heuristic.suggest_for_pdf(pdf, _cfg())
    assert suggestion.filename.startswith("paper-")  # unique, deterministic from bytes
    assert suggestion.filename.endswith(".pdf")


# --------------------------------------------------------------------------- #
# apply: the only filesystem mutation -- non-interactive + safe.              #
# --------------------------------------------------------------------------- #


def test_apply_renames_in_place(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "1706.03762.pdf", b"%PDF-attention")
    new = FilenameHeuristic.apply(pdf, "vaswani-2017-attention-is-all-you-need.pdf")

    assert new == tmp_path / "vaswani-2017-attention-is-all-you-need.pdf"
    assert new.exists()
    assert not pdf.exists()
    assert new.read_bytes() == b"%PDF-attention"


def test_apply_is_a_noop_when_already_named(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "smith-2021-paper.pdf")
    result = FilenameHeuristic.apply(pdf, "smith-2021-paper.pdf")
    assert result == pdf
    assert pdf.exists()


def test_apply_refuses_to_clobber_a_different_file(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "source.pdf", b"%PDF-source")
    _write_pdf(tmp_path / "target.pdf", b"%PDF-other")  # already occupied by a different paper

    with pytest.raises(FileExistsError):
        FilenameHeuristic.apply(pdf, "target.pdf")
    # both files survive untouched
    assert pdf.read_bytes() == b"%PDF-source"
    assert (tmp_path / "target.pdf").read_bytes() == b"%PDF-other"


def test_apply_rejects_a_filename_with_a_separator(tmp_path: Path) -> None:
    pdf = _write_pdf(tmp_path / "source.pdf")
    with pytest.raises(ValueError, match="bare name"):
        FilenameHeuristic.apply(pdf, "../escape.pdf")


def test_apply_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        FilenameHeuristic.apply(tmp_path / "nope.pdf", "new.pdf")
