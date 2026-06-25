"""F5: the paper-filename heuristic -- metadata extraction + suggest()/apply().

PURE orchestration: stdlib + ``domain`` (the ports + DTOs) + the config-file
*types* and the pure prompts/naming modules only. No ``anthropic``, no
``pdfplumber`` here -- the service depends on the
:class:`~downlow.domain.ports.LLMClient` (and optional
:class:`~downlow.domain.ports.PdfExtractor`) *ports*, which adapters implement and
tests fake.

The legacy ``file_processing.update_pdf_filenames`` was a single interactive
function that read the PDF's first text line, stripped punctuation, and renamed the
file in place after a ``y``/``n`` prompt. The rebuild splits that into three clean,
non-interactive, separately-testable steps (roadmap 1.6a):

1. :meth:`FilenameHeuristic.extract` -- a tiny structured-output LLM call extracting
   the faithful :class:`PaperMetadata` (title / authors / year) from the paper
   (native-PDF by default, extracted-text fallback);
2. :meth:`FilenameHeuristic.suggest` -- the pure, deterministic
   :class:`PaperMetadata` -> path-safe filename builder
   (:func:`downlow.core.naming.build_paper_filename`), no I/O;
3. :meth:`FilenameHeuristic.apply` -- the *only* I/O step: rename a PDF to a
   suggested filename, non-interactively (the CLI owns any confirmation), refusing
   to clobber an existing different file.

A caller wanting "look at this PDF and tell me the clean name" uses
:meth:`suggest_for_pdf` (extract -> suggest); a caller wanting "rename it too" then
calls :meth:`apply`. Keeping ``apply`` separate means ``suggest`` is pure and the
rename is an opt-in, reviewable action -- no surprise filesystem mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from downlow.config.profiles import MetadataConfig
from downlow.core.naming import build_paper_filename
from downlow.core.prompts.metadata import METADATA_SYSTEM_PROMPT, build_metadata_instruction
from downlow.domain.errors import LLMError
from downlow.domain.ports import LLMClient, LLMDocument, PdfExtractor
from downlow.domain.schemas import PaperMetadata

# Raw-bytes cap for inlining a native PDF as base64 (mirrors SummariseStage): a PDF
# over this would inflate past the ~32 MB request limit once base64-encoded, so it
# takes the extracted-text fallback instead of being inlined (which would 413).
_MAX_INLINE_PDF_BYTES = 20 * 1024 * 1024

# Metadata lives in the front matter, so for the text fallback we only need the
# first slice of the document -- sending the whole text is wasteful and can blow the
# budget for a long paper. The first ~6000 characters comfortably cover a title
# block, author line, and the copyright / arXiv stamp.
_FRONT_MATTER_CHARS = 6000


@dataclass
class FilenameSuggestion:
    """The outcome of suggesting a filename for a PDF.

    Carries both the extracted :class:`PaperMetadata` (the faithful provenance -- a
    caller / future DB can store the title/authors/year) and the deterministic
    ``filename`` derived from it, so a caller need not re-derive either.
    """

    metadata: PaperMetadata
    filename: str


class FilenameHeuristic:
    """Extract a paper's metadata and build / apply a clean filename (F5)."""

    name = "filename"

    def __init__(
        self,
        llm: LLMClient,
        *,
        extractor: PdfExtractor | None = None,
        current_year: int,
    ) -> None:
        """Wire the heuristic.

        Args:
            llm: the injected :class:`LLMClient` port (an adapter, or the fake) --
                the only thing that talks to the model.
            extractor: the :class:`PdfExtractor` port, used only on the
                over-inline-limit fallback path. ``None`` disables the fallback (a
                native-PDF-only deployment); an over-limit PDF then raises rather
                than silently sending no document.
            current_year: today's year, passed to the pure filename builder as the
                upper year-plausibility bound. Injected (not read from the clock) so
                the service stays pure and its output is reproducible in tests.
        """
        self._llm = llm
        self._extractor = extractor
        self._current_year = current_year

    # --- 1. extract (the only LLM call) -------------------------------------- #

    def extract(self, pdf_path: Path, cfg: MetadataConfig) -> PaperMetadata:
        """Extract the faithful :class:`PaperMetadata` from ``pdf_path``.

        Native-PDF path by default (the model reads the front matter directly); on a
        PDF too large to inline safely, falls back to the extractor's front-matter
        text. Metadata extraction is a tiny call with a small ``max_tokens``, so
        there is no section-split machinery -- the front matter always fits.

        Raises:
            LLMError: if the PDF is over the inline limit and no extractor is
                configured for the text fallback, or on a modelled provider failure.
        """
        return self._extract_from_bytes(pdf_path, pdf_path.read_bytes(), cfg)

    def _extract_from_bytes(self, pdf_path: Path, pdf_bytes: bytes, cfg: MetadataConfig) -> PaperMetadata:
        """Extract metadata from already-read ``pdf_bytes`` (so the caller reads once).

        The shared core of :meth:`extract` and :meth:`suggest_for_pdf`: both pass the
        bytes they have already read, so a large PDF is read from disk exactly once
        per invocation. ``pdf_path`` is still needed for the extractor (which reads
        per its own contract) and for error messages.
        """
        document = self._document_for(pdf_path, pdf_bytes)
        return self._llm.complete_structured(
            document=document,
            system=METADATA_SYSTEM_PROMPT,
            instruction=build_metadata_instruction(),
            schema=PaperMetadata,
            max_tokens=cfg.model.max_tokens,
            effort=cfg.model.effort,
        )

    def _document_for(self, pdf_path: Path, pdf_bytes: bytes) -> LLMDocument:
        """Build the LLM input from ``pdf_bytes``: native PDF, or front-matter text when too large."""
        if len(pdf_bytes) <= _MAX_INLINE_PDF_BYTES:
            return LLMDocument.from_pdf(pdf_bytes)

        if self._extractor is None:
            raise LLMError(
                f"PDF '{pdf_path.name}' is too large to inline for metadata extraction and no extractor "
                "is configured for the text fallback"
            )
        extracted = self._extractor.extract(pdf_path)
        return LLMDocument.from_text(extracted.full_text[:_FRONT_MATTER_CHARS])

    # --- 2. suggest (pure) --------------------------------------------------- #

    def suggest(self, metadata: PaperMetadata, *, pdf_bytes: bytes | None = None) -> str:
        """Build the deterministic, path-safe filename from ``metadata`` (pure).

        Delegates to :func:`downlow.core.naming.build_paper_filename`; ``pdf_bytes``
        is used only to seed the unique all-metadata-missing fallback name.
        """
        return build_paper_filename(metadata, current_year=self._current_year, pdf_bytes=pdf_bytes)

    def suggest_for_pdf(self, pdf_path: Path, cfg: MetadataConfig) -> FilenameSuggestion:
        """Extract metadata for ``pdf_path`` and build its suggested filename.

        The convenience composition of :meth:`extract` + :meth:`suggest`. The PDF is
        read from disk exactly once here and the bytes are threaded into both the
        extraction document and the missing-metadata fallback hash, so a large PDF is
        never read twice and the suggestion is unique even when extraction yields
        nothing.
        """
        pdf_bytes = pdf_path.read_bytes()
        metadata = self._extract_from_bytes(pdf_path, pdf_bytes, cfg)
        filename = self.suggest(metadata, pdf_bytes=pdf_bytes)
        return FilenameSuggestion(metadata=metadata, filename=filename)

    # --- 3. apply (the only filesystem mutation) ----------------------------- #

    @staticmethod
    def apply(pdf_path: Path, filename: str) -> Path:
        """Rename ``pdf_path`` to ``filename`` in the same directory; return the new path.

        Non-interactive (the CLI owns any confirmation) and safe:

        * a no-op when ``pdf_path`` already has ``filename`` (idempotent re-run);
        * refuses to overwrite a *different* existing file at the target (raises
          ``FileExistsError`` rather than silently clobbering an unrelated paper) --
          the legacy ``os.rename`` would have overwritten it;
        * ``filename`` is the output of :func:`build_paper_filename`, which is
          path-safe by construction, but as defence in depth this rejects a
          ``filename`` that contains a path separator (it must be a bare name in
          ``pdf_path``'s directory, never an escape).

        Raises:
            FileNotFoundError: if ``pdf_path`` does not exist.
            ValueError: if ``filename`` is not a bare filename (contains a separator).
            FileExistsError: if a different file already occupies the target name.
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"cannot rename a PDF that does not exist: {pdf_path}")
        if Path(filename).name != filename or not filename:
            raise ValueError(f"filename must be a bare name with no path separator, got {filename!r}")

        target = pdf_path.with_name(filename)
        if target == pdf_path:
            return pdf_path
        if target.exists():
            raise FileExistsError(f"refusing to overwrite an existing file: {target}")
        pdf_path.rename(target)
        return target
