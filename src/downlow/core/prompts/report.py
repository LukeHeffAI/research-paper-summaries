"""Versioned report-title prompt (F3, the optional LLM title-override path).

PURE: stdlib + ``domain`` only. Used only when ``ReportConfig.title_mode == "llm"``
-- a tiny structured-output call that proposes a concise document title for the
assembled report. The model's proposed slug is advisory: the RENDER stage ALWAYS
re-slugifies deterministically (path-safety -- the model never picks the on-disk
filename). The default ``templated`` path uses no LLM and no prompt at all.

:data:`REPORT_TITLE_PROMPT_VERSION` is part of the (optional) render-title cache
key; bump it whenever this prompt changes.
"""

from __future__ import annotations

# Bump when REPORT_TITLE_SYSTEM_PROMPT or the ReportTitleSuggestion schema changes.
REPORT_TITLE_PROMPT_VERSION = "report-title-v1"


# The frozen, cache-stable system prompt for the title-suggestion call. It names
# the target schema's fields by their stable names and never mentions a specific
# paper, so the prefix is byte-identical across reports.
REPORT_TITLE_SYSTEM_PROMPT = """\
You name a short research-summary report. You are given the titles (and brief \
summaries) of one or more papers that have been compiled into a single report \
document, and you propose a concise, human-readable document title.

Rules:
- The title is for a *collection* of paper summaries, not one paper. When several \
papers share a theme, name the theme; for a single paper, a lightly-edited version \
of its title is fine.
- Keep it under about ten words. No trailing punctuation. No quotation marks. No \
"A report on" / "Summary of" filler.
- The slug is a lowercase, hyphen-separated, filesystem-safe rendering of the \
title; it is advisory only (the system re-derives the on-disk filename itself).
"""


def build_report_title_instruction(titles: list[str]) -> str:
    """Compose the user-turn instruction listing the report's paper titles.

    The volatile per-report content (the paper titles) goes in the user turn, never
    the frozen system prefix, so the prompt cache prefix stays stable.
    """
    listed = "\n".join(f"- {t}" for t in titles) if titles else "- (no titles available)"
    return f"Propose a title for a report compiling these papers:\n{listed}"
