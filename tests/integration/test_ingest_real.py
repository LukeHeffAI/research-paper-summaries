"""Integration test for F1 — extract a real PDF with the real ``pdfplumber``.

Uses the committed tiny one-page fixture (``tests/fixtures/sample.pdf``) with
known text. Marked ``integration`` so it can be deselected when running the pure
unit suite (it still needs no network or external binary, only ``pdfplumber``).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from downlow.adapters.pdf.extractor import PdfPlumberExtractor
from downlow.core.stages.ingest import IngestStage

pytestmark = pytest.mark.integration


def test_extract_real_sample_pdf(sample_pdf: Path) -> None:
    result = PdfPlumberExtractor().extract(sample_pdf)

    assert result.page_count == 1
    assert "DownLow ingest fixture" in result.full_text
    assert "XYZZY-42" in result.full_text  # known unique marker
    assert result.is_scanned is False
    assert result.source_hash == hashlib.sha256(sample_pdf.read_bytes()).hexdigest()
    assert result.content_hash != result.source_hash


def test_ingest_stage_caches_real_pdf(sample_pdf: Path, tmp_path: Path) -> None:
    stage = IngestStage(PdfPlumberExtractor(), cache_dir=tmp_path / "cache")
    first = stage.run(sample_pdf)

    source_hash = hashlib.sha256(sample_pdf.read_bytes()).hexdigest()
    sidecar = tmp_path / "cache" / "extracted" / f"{source_hash}.json"
    assert sidecar.exists()

    second = stage.run(sample_pdf)  # cache hit
    assert second == first
