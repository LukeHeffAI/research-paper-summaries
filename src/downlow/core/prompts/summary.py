"""Versioned summary system prompt + ``build_context_prompt`` (F2).

PURE: stdlib + ``domain`` only. The frozen :data:`SUMMARY_SYSTEM_PROMPT` is a
*cache-stable* constant (it is sent unchanged on every paper, so the Anthropic
prompt cache can amortise it). All per-paper / per-profile steering goes in the
*user* turn via :func:`build_context_prompt` -- never interpolated into the
system prompt, which would invalidate the cache prefix.

Prompts are versioned artefacts: :data:`PROMPT_VERSION` is stamped into every
:class:`~downlow.domain.schemas.PaperSummary` and is part of the result-cache
key, so changing this prompt or the schema is a deliberate, traceable ablation.
Bump it whenever the system prompt or the composed steering changes.

The prompt text realises the F2 quality bar (the academic-writing-advisor's
summary structure + fidelity bar): faithful emphasis, preserved hedging, no
fabrication, scope discipline, and summariser-voice separation in
``relevance_to_profile`` and reviewer-raised limitations.
"""

from __future__ import annotations

from downlow.domain.schemas import OutputProfile, ResearchProfile

# Bump when SUMMARY_SYSTEM_PROMPT, build_context_prompt, or the PaperSummary
# schema changes. Part of the SUMMARISE result-cache key.
PROMPT_VERSION = "summary-v1"


# The frozen, cache-stable system prompt. It deliberately names PaperSummary's
# fields by their stable schema names and never mentions a specific reader, so the
# cache prefix is byte-identical across every paper and profile. No JSON/schema
# formatting instructions: native structured output enforces the shape.
SUMMARY_SYSTEM_PROMPT = """\
You summarise research papers for an active researcher doing fast, accurate triage. \
The reader wants to decide, in under a minute, whether this paper deserves their full \
attention and why. They are domain-literate but time-poor, often reading outside their \
exact subfield, and they trust a summary only as far as it is faithful to the source. \
A summary that distorts the paper is worse than no summary at all.

You are given the paper itself (a PDF, or extracted text on a fallback path) and, in the \
user turn, a description of the reader's research and what they need from this summary. \
Read the whole paper before writing. Base every statement only on what this paper contains.

Write each field for its specific job, and spend words in proportion to the paper's real \
contribution - lead with the headline result, not a minor ablation that happens to sound \
exciting.

title: The paper's actual title, taken from the source. Do not paraphrase or invent it.

overall_summary: About 300 words of prose a domain-literate reader could repeat to a \
colleague: the problem, the approach, the main result, and why it matters. Open with the \
substance. Do not write "this paper presents" or similar filler, and do not hedge with \
empty throat-clearing. Keep the authors' own level of certainty.

key_findings: The concrete, falsifiable results the authors actually showed - numbers, \
effect sizes, directions, and the conditions under which they hold. A finding is what the \
authors demonstrated, not what they assert is important. Put the supporting metric or \
condition in the finding's evidence field when the paper reports one (an accuracy delta, \
an effect size, a sample size, the regime it holds in). Leave evidence empty when the \
finding is genuinely qualitative. Never invent a number, a metric, or a confidence \
interval the paper does not report. Where you can, anchor a finding to its location in \
the paper (a section, table, or figure) so the reader can verify it.

contributions: What is genuinely new relative to prior work. Distinguish the kind of \
contribution - a new method, a new dataset, a new theoretical result, a new empirical \
observation - because each is worth something different to a different reader. Report the \
contribution the paper claims, not an inflated version of it.

methods: Enough of the study design, data, baselines, evaluation metric, and sample size \
for the reader to judge whether the findings are credible and whether they would transfer \
to a different setting. Name the single most load-bearing assumption the results rest on. \
Report what the paper studied - its population, setting, and regime - and do not \
generalise beyond it.

gaps_and_limitations: Both the limitations the authors state and the ones a sharp peer \
reviewer would raise. This section earns the reader's trust, so be honest: a list that \
only flatters the paper is a fidelity failure. When a limitation is your own critical \
reading rather than the authors' admission, phrase it as the reviewer's observation \
("a reviewer might note...") so it is unmistakably your framing and not attributed to \
the authors.

relevance_to_profile: Why this paper matters to THIS reader, given the research focus \
described in the user turn - or an honest statement that it does not connect, if that is \
the truth. Write this in your own voice as the summariser; never put this framing in the \
authors' mouths. Name the specific, reusable thing where you can: a transferable method, \
a usable dataset, a metric or experimental control they could borrow, a competing claim, \
or a failure mode that bears on their work. Where an unfamiliar technique maps onto \
something in the reader's toolkit, say so, and flag where the analogy breaks down. Do not \
overstate the connection to seem useful; a precise small overlap beats a vague large one.

Fidelity rules that govern every field:
- No fabrication. Every claim must trace to this paper. If the paper does not report \
something, do not supply it.
- Preserve the authors' certainty. "Suggests" is not "proves"; a correlation is not a \
cause; an in-vitro or simulated result is not a real-world one. Keep the qualifiers the \
authors used.
- Stay inside the paper's scope. Report the population, setting, and regime studied; do \
not silently extend the conclusions past them.
- Keep paper-voice and your voice separate. Reported findings and contributions are the \
authors'. Critique, reviewer-raised limitations, and relevance are yours, and must read \
as yours.
- Note evidentiary weight when it is material: preprint versus peer-reviewed versus \
workshop versus journal; the paper's own results versus results it merely cites; released \
code or data versus none. Do not credit this paper with a finding it only referenced."""


def _article(text: str) -> str:
    """Return ``text`` with the right indefinite article ('a'/'an').

    Preserves the legacy ``vowel_check`` grammar helper so the composed prompt
    reads like a person wrote it (the advisor's "11pm reader trusts prose that
    is not visibly machine-stamped"). Crude but correct for the common cases.
    """
    if text and text[0].lower() in "aeiou":
        return "an " + text
    return "a " + text


def _bullets(items: list[str]) -> str:
    """Render ``items`` as flat ``- item`` lines (one per line)."""
    return "\n".join(f"- {item}" for item in items)


def build_context_prompt(research_profile: ResearchProfile, output_profile: OutputProfile) -> str:
    """Compose the user-turn steering instruction from the two profiles.

    A faithful upgrade of the legacy ``research_details.build_context_prompt``,
    grounded in the advisor's framing-across-fields guidance (translate-then-map,
    surface the transfer, explicit relevance steering). Returns the *instruction*
    text only; the SUMMARISE stage places it after the document content block.

    Empty interest / return-detail lists drop their block entirely rather than
    emitting a stray bullet (which reads as noise to the model).
    """
    field = research_profile.research_field
    topic = research_profile.research_topic
    focus = research_profile.research_focus

    parts: list[str] = [
        f"I am {_article(field.lower())} researcher, and I am summarising this paper to help me "
        f"write {_article(output_profile.document_type.lower())}. My research is in {topic}, "
        f"focused specifically on {focus}.",
    ]

    if research_profile.research_interests:
        parts.append("The topics I care about most are:\n" + _bullets(research_profile.research_interests))

    ask = (
        "Please summarise the attached paper for me. Read it the way a busy peer would, and "
        "surface what I need to make a fast, accurate decision about whether to read it in full."
    )
    if output_profile.return_details:
        ask += " I am especially looking for:\n" + _bullets(output_profile.return_details)
    parts.append(ask)

    parts.append(
        f"When you reach relevance, connect the paper to my focus on {focus} in concrete terms: "
        "name the specific method, dataset, metric, control, result, or failure mode I could "
        "actually use, or tell me plainly if it does not connect. Where the paper uses techniques "
        f"or vocabulary from outside {field}, introduce the term as its own field uses it and then "
        "map it onto what I already work with, flagging where that mapping is loose. Keep the "
        "paper's own level of certainty, and stay within what it actually shows."
    )

    parts.append("The paper is attached below.")

    return "\n\n".join(parts)
