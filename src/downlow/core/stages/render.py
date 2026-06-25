"""RENDER stage (F3): one or more PaperSummary -> a compiled report PDF.

PURE orchestration: stdlib + ``domain`` (the ports + DTOs) + the config-file
*types* and the pure prompts module only. No ``typst`` / ``subprocess`` here -- the
stage depends on the :class:`~downlow.domain.ports.ReportRenderer` (and optional
:class:`~downlow.domain.ports.LLMClient` for the title override and
:class:`~downlow.domain.ports.ArtifactStore` for the PDF) *ports*, which adapters
implement and tests fake.

Flow (PROJECT_PLAN.md -> Stage 3 RENDER; roadmap 1.4a-1.4d):

1. assemble the ordered ``list[PaperSummary]`` (the legacy merge-into-one-document
   behaviour) + a title into a :class:`ReportData` (1.4a);
2. choose the title: a deterministic *templated* default derived from the paper
   title(s), or an optional LLM override behind ``ReportConfig.title_mode == "llm"``;
   derive a deterministic, path-safe ``slug`` for the on-disk filename -- the model
   NEVER picks the filename directly (1.4b);
3. (optional) on a render-cache hit, return the stored PDF bytes with no compile;
4. render the :class:`ReportData` via the :class:`ReportRenderer` port (the typst
   subprocess lives in the adapter -- 1.4c);
5. write the PDF to ``<DATA_DIR>/reports/<slug>.pdf`` via the
   :class:`ArtifactStore` (1.4d) and return the result.

Deterministic and idempotent: identical summaries + title + template version yield
a byte-stable PDF and the same slug, so a re-run overwrites in place rather than
duplicating.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from downlow.config.profiles import ReportConfig
from downlow.core.prompts.report import REPORT_TITLE_SYSTEM_PROMPT, build_report_title_instruction
from downlow.domain.errors import LLMError
from downlow.domain.ports import ArtifactStore, LLMClient, LLMDocument, ReportRenderer
from downlow.domain.schemas import PaperSummary, ReportData, ReportMeta, ReportTitleSuggestion

_REPORTS_SUBDIR = "reports"

# The fallback document title when no usable paper title is available, or for a
# multi-paper report with no LLM override. Mirrors the legacy report's heading.
_DEFAULT_MULTI_TITLE = "Research Summaries"

# Slug safety bounds: lowercase ASCII alnum + single hyphens, no leading/trailing
# hyphen, capped so a pathological title cannot produce an unwieldy filename.
_MAX_SLUG_LEN = 80
_FALLBACK_SLUG = "report"

# Non-[a-z0-9] runs collapse to a single hyphen during slugify.
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


@dataclass
class RenderResult:
    """The outcome of a RENDER run: the PDF bytes, its slug, and where it landed.

    ``ref`` is the :class:`ArtifactStore` reference (a logical path string) the DB
    records; ``pdf_bytes`` is returned so a caller (or test) can inspect the
    artifact without re-reading it.
    """

    pdf_bytes: bytes
    slug: str
    title: str
    ref: str


class RenderStage:
    """Assembles summaries into a report, renders it, and stores the PDF.

    Also known as the ``ReportComposer`` (PROJECT_PLAN.md 1.4a): the composition of
    "assemble + title + slug + render + store".
    """

    name = "render"

    def __init__(
        self,
        renderer: ReportRenderer,
        store: ArtifactStore,
        *,
        llm: LLMClient | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        """Wire the stage.

        Args:
            renderer: the :class:`ReportRenderer` port (the typst adapter, or the
                fake) -- the only thing that knows about Typst.
            store: the :class:`ArtifactStore` port; the stage writes the report PDF
                under ``reports/<slug>.pdf`` through it.
            llm: the :class:`LLMClient` port, used only on the
                ``title_mode == "llm"`` override path. ``None`` forces the
                deterministic templated title (a non-LLM deployment).
            cache_dir: the cache root (``<DATA_DIR>/cache``); when given, compiled
                PDFs are cached under ``reports/`` keyed by the summaries' content +
                template version + title (compilation is sub-second, so this is
                optional). ``None`` disables the render cache.
        """
        self._renderer = renderer
        self._store = store
        self._llm = llm
        self._cache_dir = cache_dir / _REPORTS_SUBDIR if cache_dir is not None else None

    def run(
        self,
        summaries: list[PaperSummary],
        cfg: ReportConfig,
        *,
        title: str | None = None,
        force: bool = False,
    ) -> RenderResult:
        """Render ``summaries`` into one report PDF and store it.

        Args:
            summaries: one or more validated :class:`PaperSummary` objects, in
                document order (the legacy merge-all-into-one-document behaviour).
            cfg: the resolved :class:`ReportConfig` (template version, title mode).
            title: an explicit document title; overrides both the templated default
                and the LLM path when given (the CLI ``--title`` hook).
            force: bypass the render cache (recompile and overwrite).

        Returns:
            The :class:`RenderResult` (PDF bytes, slug, resolved title, store ref).

        Raises:
            ValueError: if ``summaries`` is empty (nothing to render).
            LLMError: on the LLM title path when no client is configured.
            TypstCompileError: when the renderer's compile fails.
        """
        if not summaries:
            raise ValueError("RENDER needs at least one PaperSummary; none were provided")

        resolved_title = title if title is not None else self._resolve_title(summaries, cfg)
        slug = self._slugify(resolved_title)
        data = self.assemble(summaries, resolved_title, cfg)

        cache_key = self._cache_key(summaries, resolved_title, cfg.template_version)
        if not force:
            cached = self._load_cache(cache_key)
            if cached is not None:
                ref = self._store.put(self._artifact_key(slug), cached)
                return RenderResult(pdf_bytes=cached, slug=slug, title=resolved_title, ref=ref)

        pdf_bytes = self._renderer.render(data)
        self._write_cache(cache_key, pdf_bytes)
        ref = self._store.put(self._artifact_key(slug), pdf_bytes)
        return RenderResult(pdf_bytes=pdf_bytes, slug=slug, title=resolved_title, ref=ref)

    @staticmethod
    def assemble(summaries: list[PaperSummary], title: str, cfg: ReportConfig) -> ReportData:
        """Assemble the ordered summaries + title into a :class:`ReportData` (1.4a).

        Pure and deterministic: no LLM markup, no I/O. The adapter serialises this
        to the data file the Typst template loads.
        """
        return ReportData(
            meta=ReportMeta(title=title, template_version=cfg.template_version),
            summaries=summaries,
        )

    # --- title resolution (templated default + optional LLM override) -------- #

    def _resolve_title(self, summaries: list[PaperSummary], cfg: ReportConfig) -> str:
        """Choose the document title per ``cfg.title_mode``.

        ``templated`` (the default) derives a deterministic title from the paper
        title(s) with no API call. ``llm`` asks the model for a title (only its
        *title* is used; the slug is always re-derived deterministically).
        """
        if cfg.title_mode == "llm":
            return self._llm_title(summaries, cfg)
        return self._templated_title(summaries)

    @staticmethod
    def _templated_title(summaries: list[PaperSummary]) -> str:
        """A deterministic default title from the paper title(s).

        One paper -> that paper's title. Multiple papers -> the fixed collection
        title (mirrors the legacy "Research Summaries" report heading). An empty /
        whitespace title falls back to the collection title.
        """
        if len(summaries) == 1:
            single = summaries[0].title.strip()
            return single or _DEFAULT_MULTI_TITLE
        return _DEFAULT_MULTI_TITLE

    def _llm_title(self, summaries: list[PaperSummary], cfg: ReportConfig) -> str:
        """Ask the LLM for a report title (the override path).

        Only the model's ``title`` is used; the on-disk slug is always re-derived by
        :meth:`_slugify` (the model never picks the filename -- path-safety). Falls
        back to the templated title if the model returns an empty title.
        """
        if self._llm is None:
            raise LLMError("title_mode is 'llm' but no LLMClient was configured for the RENDER stage")
        titles = [s.title for s in summaries]
        instruction = build_report_title_instruction(titles)
        suggestion = self._llm.complete_structured(
            document=LLMDocument.from_text("\n\n".join(titles)),
            system=REPORT_TITLE_SYSTEM_PROMPT,
            instruction=instruction,
            schema=ReportTitleSuggestion,
            max_tokens=cfg.model.max_tokens,
            effort=cfg.model.effort,
        )
        return suggestion.title.strip() or self._templated_title(summaries)

    # --- deterministic, path-safe slugify ------------------------------------ #

    @staticmethod
    def _slugify(title: str) -> str:
        """Derive a deterministic, path-safe slug from ``title`` (module :func:`slugify`)."""
        return slugify(title)

    @staticmethod
    def _artifact_key(slug: str) -> str:
        """The logical ArtifactStore key for the report PDF (``reports/<slug>.pdf``)."""
        return f"{_REPORTS_SUBDIR}/{slug}.pdf"

    # --- optional render cache ----------------------------------------------- #

    def _cache_key(self, summaries: list[PaperSummary], title: str, template_version: str) -> str:
        """The render-cache key: hash(sorted content hashes + template version + title).

        Sorted so the order summaries are passed in does not change the key when the
        *set* of papers is the same; the title and template version invalidate on a
        re-title or a template change.
        """
        content_hashes = sorted(s.input_hash for s in summaries)
        material = "|".join([*content_hashes, template_version, title])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _cache_path(self, cache_key: str) -> Path | None:
        if self._cache_dir is None:
            return None
        return self._cache_dir / f"{cache_key}.pdf"

    def _load_cache(self, cache_key: str) -> bytes | None:
        """Load a cached compiled PDF, or ``None`` on a miss / disabled cache."""
        cache_path = self._cache_path(cache_key)
        if cache_path is None or not cache_path.exists():
            return None
        try:
            return cache_path.read_bytes()
        except OSError:
            return None

    def _write_cache(self, cache_key: str, pdf_bytes: bytes) -> None:
        """Write the compiled PDF to the render cache (atomic; no-op if disabled)."""
        cache_path = self._cache_path(cache_key)
        if cache_path is None:
            return
        _atomic_write(cache_path, pdf_bytes)


def slugify(title: str) -> str:
    """Derive a lowercase, hyphen-separated, filesystem-safe slug from ``title``.

    Deterministic and path-safe by construction: only ``[a-z0-9-]`` survive, so the
    result can never contain a path separator (``/`` / ``\\``), ``..``, a leading
    dot, a space, or any shell-significant character -- the model (or a paper title)
    can never escape the reports directory. An empty result (a title of only
    punctuation / non-ASCII) falls back to :data:`_FALLBACK_SLUG`. Length is capped
    so a pathological title cannot produce an unwieldy filename.

    Pure and module-level so it is unit-tested in isolation. Same title in => same
    slug out (idempotent re-renders overwrite in place rather than duplicating).
    """
    lowered = title.strip().lower()
    slug = _NON_SLUG_CHARS.sub("-", lowered).strip("-")
    if len(slug) > _MAX_SLUG_LEN:
        slug = slug[:_MAX_SLUG_LEN].rstrip("-")
    return slug or _FALLBACK_SLUG


def disambiguate_slug(slug: str, taken: set[str]) -> str:
    """Return ``slug`` or, if it collides with a ``taken`` one, a suffixed variant.

    Two different titles can slugify to the same string (e.g. "OOD Generalisation!"
    and "OOD generalisation"); when several reports land in the same directory, this
    avoids one clobbering another by appending ``-2``, ``-3``, ... until the name is
    free. Deterministic given the iteration order of ``taken`` checks. The base
    ``slug`` is returned unchanged when there is no collision (the common case).
    """
    if slug not in taken:
        return slug
    n = 2
    while f"{slug}-{n}" in taken:
        n += 1
    return f"{slug}-{n}"


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically via a unique temp file + replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
