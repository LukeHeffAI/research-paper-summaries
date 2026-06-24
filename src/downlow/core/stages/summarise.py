"""SUMMARISE stage: source PDF + steering profiles -> validated PaperSummary.

PURE orchestration: stdlib + ``domain`` (+ the config-file *types* and the
prompts module, both pure) only. No ``anthropic``, no ``pdfplumber`` here -- the
stage depends on the :class:`~downlow.domain.ports.LLMClient` and
:class:`~downlow.domain.ports.PdfExtractor` *ports*, which adapters implement and
tests fake.

Flow (PROJECT_PLAN.md -> Stage 2 SUMMARISE):

1. compute the result-cache key ``(input_hash, profile_hash, model, prompt_version)``
   -- ``input_hash`` is the PDF ``source_hash`` on the native path (or the text
   ``content_hash`` on the fallback path);
2. on a cache hit (and not ``force``), load and return the stored summary with no
   LLM call;
3. otherwise build the steering instruction (``build_context_prompt``) and call
   the ``LLMClient`` with the native PDF (the default) -- *single-call path first*;
4. if the native PDF is over the input budget (measured with the client's
   ``count_tokens``, never ``len()``), fall back to F1's extracted text, and if
   *that* is still over budget, run the section-split + carried-context + recursive
   truncation-retry machinery;
5. stamp provenance (``input_hash``, ``profile_hash``, ``model``,
   ``prompt_version``) onto the validated summary and write the cache sidecar.

The long-input machinery is built cleanly here so NARRATE can reuse it; it rarely
fires (Sonnet 4.6 has a 1M context, so most papers summarise in one call).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from downlow.config.profiles import SummaryConfig
from downlow.core.prompts.summary import SUMMARY_SYSTEM_PROMPT, build_context_prompt
from downlow.domain.errors import LLMError, TruncatedResponseError
from downlow.domain.ports import LLMClient, LLMDocument, PdfExtractor
from downlow.domain.schemas import OutputProfile, PaperSummary, ResearchProfile

_SUMMARIES_SUBDIR = "summaries"

# Default token budget for a single native-PDF call. Above this the stage falls
# back to extracted text (and then section-split). Generous because Sonnet 4.6
# has a 1M-token context; the budget exists so a pathological PDF cannot blow the
# context window or the per-paper cost silently. Override per call if needed.
_DEFAULT_INPUT_BUDGET_TOKENS = 180_000

# Maximum recursive split iterations before giving up on a stubborn section
# (guards the truncation-retry work queue against an infinite loop).
_MAX_SPLIT_ITERATIONS = 8

# Paragraph/section boundary for the long-input splitter: a blank line.
_SECTION_BOUNDARY = re.compile(r"\n\s*\n")


class SummariseStage:
    """Orchestrates context-steered summarisation behind a result cache."""

    name = "summarise"

    def __init__(
        self,
        llm: LLMClient,
        cache_dir: Path,
        *,
        extractor: PdfExtractor | None = None,
        input_budget_tokens: int = _DEFAULT_INPUT_BUDGET_TOKENS,
    ) -> None:
        """Wire the stage.

        Args:
            llm: the injected :class:`LLMClient` port (an adapter, or the fake).
            cache_dir: the cache root (``<settings.data_dir>/cache``); the stage
                owns the ``summaries/`` subdirectory beneath it.
            extractor: the :class:`PdfExtractor` port, used only on the
                over-budget fallback path. ``None`` disables the fallback (a
                native-PDF-only deployment); an over-budget PDF then raises rather
                than silently truncating.
            input_budget_tokens: the native-PDF token budget above which the stage
                falls back to extracted text.
        """
        self._llm = llm
        self._cache_dir = cache_dir / _SUMMARIES_SUBDIR
        self._extractor = extractor
        self._input_budget = input_budget_tokens

    def run(
        self,
        pdf_path: Path,
        research_profile: ResearchProfile,
        output_profile: OutputProfile,
        summary_config: SummaryConfig,
        *,
        force: bool = False,
    ) -> PaperSummary:
        """Summarise ``pdf_path`` under the steering profiles, using the cache.

        Args:
            pdf_path: the source PDF to summarise.
            research_profile: the reader's research identity (steers emphasis).
            output_profile: what the summary should surface (document shape).
            summary_config: the resolved model + prompt-version config.
            force: bypass the result cache (re-summarise and overwrite), preserving
                the legacy overwrite behaviour.

        Returns:
            The validated :class:`PaperSummary` (cached or freshly generated).

        Raises:
            TruncatedResponseError: if the response is truncated and the long-input
                retry machinery cannot recover it.
            LLMError: for refusals / other modelled provider failures.
        """
        instruction = build_context_prompt(research_profile, output_profile)
        profile_hash = self._profile_hash(research_profile, output_profile)
        source_hash = self._source_hash(pdf_path)

        cache_key = self._cache_key(
            input_hash=source_hash,
            profile_hash=profile_hash,
            model=summary_config.model.id,
            prompt_version=summary_config.prompt_version,
        )
        cache_path = self._cache_path(cache_key)

        if not force:
            cached = self._load_cache(cache_path)
            if cached is not None:
                return cached

        summary, input_hash = self._summarise(pdf_path, instruction, summary_config)

        summary.input_hash = input_hash
        summary.profile_hash = profile_hash
        summary.model = summary_config.model.id
        summary.prompt_version = summary_config.prompt_version

        self._write_cache(cache_path, summary)
        return summary

    # --- summarisation (single-call path first, then fallbacks) -------------- #

    def _summarise(self, pdf_path: Path, instruction: str, cfg: SummaryConfig) -> tuple[PaperSummary, str]:
        """Produce a PaperSummary; return it with the chosen ``input_hash``.

        Single-call native-PDF path first; falls back to extracted text + (if
        still over budget) section-split. Never silently truncates input.
        """
        pdf_bytes = pdf_path.read_bytes()
        native_doc = LLMDocument.from_pdf(pdf_bytes)

        if self._fits_budget(native_doc, instruction):
            summary = self._complete(native_doc, instruction, cfg)
            return summary, self._source_hash(pdf_path)

        # Over the native-PDF budget -> fall back to F1 extracted text.
        if self._extractor is None:
            raise LLMError(
                f"PDF '{pdf_path.name}' exceeds the native-PDF input budget and no extractor "
                "is configured for the text fallback; refusing to truncate the input"
            )
        extracted = self._extractor.extract(pdf_path)
        text_doc = LLMDocument.from_text(extracted.full_text)

        if self._fits_budget(text_doc, instruction):
            summary = self._complete(text_doc, instruction, cfg)
            return summary, extracted.content_hash

        # Still over budget even as text -> section-split + carried-context reduce.
        summary = self._summarise_sectioned(extracted.full_text, instruction, cfg)
        return summary, extracted.content_hash

    def _complete(self, document: LLMDocument, instruction: str, cfg: SummaryConfig) -> PaperSummary:
        """One structured-output call, with a recursive truncation-retry guard."""
        return self._complete_with_retry(document, instruction, cfg, iteration=0)

    def _complete_with_retry(
        self, document: LLMDocument, instruction: str, cfg: SummaryConfig, *, iteration: int
    ) -> PaperSummary:
        """Call the LLM; on truncation, split a text document in half and re-queue.

        A native-PDF document cannot be split locally, so a truncation there
        surfaces immediately (raise ``max_tokens``). A text document is split on a
        section boundary and the two halves summarised then merged -- the same
        machinery NARRATE will reuse. ``iteration`` caps the recursion.
        """
        try:
            return self._llm.complete_structured(
                document=document,
                system=SUMMARY_SYSTEM_PROMPT,
                instruction=instruction,
                schema=PaperSummary,
                max_tokens=cfg.model.max_tokens,
                effort=cfg.model.effort,
            )
        except TruncatedResponseError:
            if document.is_pdf or document.text is None or iteration >= _MAX_SPLIT_ITERATIONS:
                raise
            halves = self._split_text(document.text)
            if len(halves) < 2:
                raise
            partials = [
                self._complete_with_retry(LLMDocument.from_text(half), instruction, cfg, iteration=iteration + 1)
                for half in halves
            ]
            return self._reduce(partials, instruction, cfg, iteration=iteration + 1)

    def _summarise_sectioned(self, text: str, instruction: str, cfg: SummaryConfig) -> PaperSummary:
        """Split a too-large document into ordered sections and reduce them.

        Sections are processed sequentially carrying forward the running summary
        (title/abstract + prior overall_summary) so later sections stay consistent,
        then merged via a final reduce call. Truncated sections recurse via
        :meth:`_complete_with_retry`.
        """
        sections = self._split_text(text)
        partials: list[PaperSummary] = []
        carried = ""
        for section in sections:
            section_instruction = instruction if not carried else f"{instruction}\n\nContext so far:\n{carried}"
            partial = self._complete_with_retry(LLMDocument.from_text(section), section_instruction, cfg, iteration=0)
            partials.append(partial)
            carried = f"{partial.title}\n\n{partial.overall_summary}"
        return self._reduce(partials, instruction, cfg, iteration=0)

    def _reduce(
        self, partials: list[PaperSummary], instruction: str, cfg: SummaryConfig, *, iteration: int
    ) -> PaperSummary:
        """Merge per-section partial summaries into one via a final reduce call.

        The partials are serialised into a text document and re-summarised against
        the same steering, so the merged result still clears the quality bar.
        """
        if len(partials) == 1:
            return partials[0]
        merged_text = "\n\n".join(p.model_dump_json() for p in partials)
        reduce_instruction = (
            f"{instruction}\n\nThe attached content is a set of partial summaries of sections of one "
            "paper. Synthesise them into a single faithful summary of the whole paper."
        )
        return self._complete_with_retry(
            LLMDocument.from_text(merged_text), reduce_instruction, cfg, iteration=iteration
        )

    # --- budgets + splitting ------------------------------------------------- #

    def _fits_budget(self, document: LLMDocument, instruction: str) -> bool:
        """True when the document + steering fit the input budget (count_tokens)."""
        tokens = self._llm.count_tokens(document=document, system=SUMMARY_SYSTEM_PROMPT, instruction=instruction)
        return tokens <= self._input_budget

    @staticmethod
    def _split_text(text: str) -> list[str]:
        """Split ``text`` into two roughly-equal halves on a section boundary.

        Used both for the section-split path and for recursive truncation-retry.
        Splits at the blank-line boundary nearest the midpoint so a section is not
        cut mid-paragraph; falls back to a hard midpoint split if there is no
        boundary. Returns ``[text]`` unchanged when it cannot be split.
        """
        boundaries = [m.start() for m in _SECTION_BOUNDARY.finditer(text)]
        if not boundaries:
            mid = len(text) // 2
            if mid == 0:
                return [text]
            return [text[:mid], text[mid:]]
        target = len(text) // 2
        split_at = min(boundaries, key=lambda b: abs(b - target))
        left = text[:split_at].strip()
        right = text[split_at:].strip()
        if not left or not right:
            return [text]
        return [left, right]

    # --- cache keys + provenance hashes -------------------------------------- #

    def _cache_key(self, *, input_hash: str, profile_hash: str, model: str, prompt_version: str) -> str:
        """The result-cache key: a hash of the four invalidating inputs."""
        material = f"{input_hash}|{profile_hash}|{model}|{prompt_version}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _profile_hash(research: ResearchProfile, output: OutputProfile) -> str:
        """Stable hash of the steering profiles (sorted-key JSON for determinism)."""
        material = json.dumps(
            {"research": research.model_dump(), "output": output.model_dump()},
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _source_hash(pdf_path: Path) -> str:
        """sha256 of the raw PDF bytes -- the native-path input_hash."""
        return hashlib.sha256(pdf_path.read_bytes()).hexdigest()

    # --- caching (DB-backed later: artifact refs move into the DB at STORE) --- #

    def _cache_path(self, cache_key: str) -> Path:
        return self._cache_dir / f"{cache_key}.json"

    @staticmethod
    def _load_cache(cache_path: Path) -> PaperSummary | None:
        """Load a cached summary, or ``None`` on miss / corruption / schema drift."""
        if not cache_path.exists():
            return None
        try:
            return PaperSummary.model_validate_json(cache_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return None

    @staticmethod
    def _write_cache(cache_path: Path, summary: PaperSummary) -> None:
        """Write the sidecar atomically via a unique temp file + replace."""
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=cache_path.parent, prefix=f"{cache_path.name}.", suffix=".tmp")
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(summary.model_dump_json())
            tmp_path.replace(cache_path)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
