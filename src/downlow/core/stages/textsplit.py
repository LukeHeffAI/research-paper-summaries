"""Shared long-input text splitting for SUMMARISE (F2) and NARRATE (F4).

PURE: stdlib only. Both stages reuse the same section-boundary splitter for the
over-budget / truncation-retry paths (the machinery is built cleanly here so a
single behaviour -- "never cut a section mid-paragraph" -- is shared and tested
once). It rarely fires (Sonnet 4.6 has a 1M context), but when it does, both the
summary reduce and the narration reduce walk the same halves.
"""

from __future__ import annotations

import re

# Paragraph/section boundary for the splitter: a blank line.
_SECTION_BOUNDARY = re.compile(r"\n\s*\n")


def split_text(text: str) -> list[str]:
    """Split ``text`` into two roughly-equal halves on a section boundary.

    Splits at the blank-line boundary nearest the midpoint so a section is not cut
    mid-paragraph; falls back to a hard midpoint split if there is no boundary.
    Returns ``[text]`` unchanged when it cannot be split (so callers can detect a
    no-progress split and stop recursing).
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
