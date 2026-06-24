"""INGEST stage: source PDF -> normalised text + content hashes, with a cache.

PURE orchestration: stdlib + ``domain`` only. No ``pdfplumber`` here — the stage
depends on the :class:`PdfExtractor` *port*, which an adapter implements.

Flow (PROJECT_PLAN.md -> Stage 1 INGEST):

1. compute ``source_hash = sha256(pdf_bytes)`` (available before extraction);
2. check a file-backed extraction cache at
   ``<cache_dir>/extracted/<source_hash>.json`` — on a hit, load and return the
   stored :class:`ExtractedText` with no extractor call;
3. on a miss, call the :class:`PdfExtractor` port, write the cache sidecar
   atomically, and return.

The sidecar cache replaces the legacy ``pdf_texts.json`` blob and is the
content-hash cache layer (plan task 1.2b). It is intentionally simple and
file-backed for now; the artifact references move into the DB later (1.1e) — see
the "DB-backed later" note below.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from downlow.domain.ports import PdfExtractor
from downlow.domain.schemas import ExtractedText

_EXTRACTED_SUBDIR = "extracted"


class IngestStage:
    """Orchestrates PDF extraction behind a source-hash-keyed file cache."""

    name = "ingest"

    def __init__(self, extractor: PdfExtractor, cache_dir: Path) -> None:
        """Wire the stage.

        Args:
            extractor: the injected :class:`PdfExtractor` port (an adapter).
            cache_dir: the cache root (``<settings.data_dir>/cache``); the stage
                owns the ``extracted/`` subdirectory beneath it.
        """
        self._extractor = extractor
        self._cache_dir = cache_dir / _EXTRACTED_SUBDIR

    def run(self, pdf_path: Path, *, force: bool = False) -> ExtractedText:
        """Extract ``pdf_path``, using the cache unless ``force`` is set.

        Args:
            pdf_path: the source PDF to ingest.
            force: bypass the cache (re-extract and overwrite the sidecar),
                preserving the legacy overwrite behaviour.

        Returns:
            The :class:`ExtractedText` for the PDF (cached or freshly extracted).
        """
        source_hash = self._source_hash(pdf_path)
        cache_path = self._cache_path(source_hash)

        if not force:
            cached = self._load_cache(cache_path)
            if cached is not None:
                return cached

        extracted = self._extractor.extract(pdf_path)
        self._write_cache(cache_path, extracted)
        return extracted

    # --- caching (DB-backed later: artifact refs move into the DB at 1.1e) ---

    def _cache_path(self, source_hash: str) -> Path:
        return self._cache_dir / f"{source_hash}.json"

    @staticmethod
    def _load_cache(cache_path: Path) -> ExtractedText | None:
        """Load a cached :class:`ExtractedText`, or ``None`` on miss/corruption.

        A corrupt or schema-stale sidecar is treated as a miss (and will be
        overwritten on the subsequent extraction) rather than crashing the run.
        """
        if not cache_path.exists():
            return None
        try:
            return ExtractedText.model_validate_json(cache_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None

    @staticmethod
    def _write_cache(cache_path: Path, extracted: ExtractedText) -> None:
        """Write the sidecar atomically (temp file + replace) to avoid partial reads."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        tmp_path.write_text(extracted.model_dump_json(), encoding="utf-8")
        tmp_path.replace(cache_path)

    @staticmethod
    def _source_hash(pdf_path: Path) -> str:
        """sha256 of the raw PDF bytes — the cache key, known before extraction."""
        return hashlib.sha256(pdf_path.read_bytes()).hexdigest()
