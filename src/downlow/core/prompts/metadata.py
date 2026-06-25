"""Versioned metadata-extraction prompt (F5).

PURE: stdlib only. A tiny structured-output prompt that extracts a paper's
:class:`~downlow.domain.schemas.PaperMetadata` (title / authors / year) FAITHFULLY
from its front matter -- the input to the deterministic filename builder. The model
supplies faithful raw metadata; ``downlow.core.naming`` owns the on-disk filename,
so this prompt's only job is to be honest and to return empty fields when a value
is genuinely absent (a wrong guess is worse than empty).

The frozen :data:`METADATA_SYSTEM_PROMPT` is a cache-stable constant (sent unchanged
on every paper). :data:`METADATA_PROMPT_VERSION` is part of any metadata cache key;
bump it whenever this prompt or the :class:`PaperMetadata` schema changes.
"""

from __future__ import annotations

# Bump when METADATA_SYSTEM_PROMPT or the PaperMetadata schema changes.
METADATA_PROMPT_VERSION = "metadata-v1"


# The frozen, cache-stable system prompt. It names PaperMetadata's fields by their
# stable schema names and never mentions a specific paper, so the prefix is
# byte-identical across every extraction. No JSON formatting instructions: native
# structured output enforces the shape.
METADATA_SYSTEM_PROMPT = """\
You extract the bibliographic metadata of a research paper -- its title, its \
authors, and its publication year -- so the file can be given a clean, recognisable \
name. You are not summarising or judging the paper; you are reading its front matter \
and reporting exactly what is printed there.

Extract every value ONLY from the document itself -- the title block and author line \
on the first page, and the copyright or arXiv stamp if present. Never infer, \
complete, normalise, or reconstruct a value from your own knowledge of the paper or \
its authors. If you recognise the paper, that changes nothing: report only what the \
text in front of you shows.

An empty field is a correct, expected answer. Returning an empty author list or a \
null year when the value is not in the document is exactly right; a wrong guess is \
worse than an empty field. Do not estimate a year from the topic or the references, \
and do not supply an author you merely associate with the work.

title: The paper's title exactly as printed, including any subtitle after a colon. \
Do not truncate it, do not drop the subtitle, do not change the capitalisation, and \
do not invent one. Join a title that wraps across two display lines into one string \
with a single space. Do not include the running header, the venue name, or banners \
like "Preprint. Under review.". If the first page has no clear title, return an empty \
title rather than guessing from the filename or the body.

authors: The authors in the exact order they appear on the paper -- the first listed \
author MUST be first in your list. Return each author as a single full display name \
("Jane Q. Smith"), not split into given and family names. Strip affiliation markers, \
footnote daggers, superscripts, email addresses, "et al.", institutions, and \
corresponding-author symbols. If authorship is a group or consortium (e.g. "The BERT \
Team"), return that group name as a single author entry. If no authors are printed, \
return an empty list.

year: The publication year, as a four-digit integer, taken from the front matter in \
this priority order: (1) an explicit publication or venue year in the header or a \
venue line ("Proceedings of NeurIPS 2021"); (2) a copyright year ("(c) 2021"); (3) \
the year from an arXiv stamp. Never take a year from the body text, the abstract, the \
references or bibliography, or a dataset name -- a year in the reference list belongs \
to some other paper. If several candidate years appear in the front matter, prefer \
the publication/venue year over the copyright year over the arXiv year; never average \
or range them. If no plausible year is printed in the front matter, return null."""


# The user-turn instruction. The volatile per-paper content (the paper itself) is the
# attached document block placed before this instruction by the LLMClient port, so the
# instruction text is constant and the cache prefix stays stable.
METADATA_INSTRUCTION = (
    "Extract the title, authors, and publication year of the attached paper, following the rules above. "
    "Return empty values for anything not printed in the document rather than guessing."
)


def build_metadata_instruction() -> str:
    """Return the (constant) metadata-extraction user-turn instruction.

    A function for symmetry with the other prompt modules' ``build_*`` helpers and so
    a future per-call steering hook has a seam; today it returns the frozen constant.
    """
    return METADATA_INSTRUCTION
