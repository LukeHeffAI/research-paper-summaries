"""Versioned two-presenter interview system prompt + instruction builder (F4).

PURE: stdlib only. The frozen :data:`NARRATION_SYSTEM_PROMPT` is a *cache-stable*
constant (sent unchanged on every paper, so the Anthropic prompt cache amortises
it). All per-episode steering (the source kind, the target length budget) goes in
the *user* turn via :func:`build_narration_instruction` -- never interpolated into
the system prompt, which would invalidate the cache prefix (the F2 discipline).

Prompts are versioned artefacts: :data:`NARRATION_PROMPT_VERSION` is stamped into
every :class:`~downlow.domain.schemas.NarrationScript` and is part of the
script-cache key, so changing this prompt or the schema is a deliberate, traceable
change. :data:`PERSONA_VERSION` tracks the host-persona text specifically (a
separate cache-key component per docs/podcast_design.md section 5) so that when the
persona later graduates to config it stays separable from this frozen prompt.

The prompt text realises the F4 quality bar (the academic-writing-advisor's host
persona + craft principles + anti-patterns + the interview-specific fidelity bar,
docs/podcast_design.md sections 1-2): the everyperson host, depth-asymmetry in
turn-length and vocabulary, cold open before the intro music, lead-with-curiosity,
listen-don't-march, the "wait back up" move, specific reactions, an arc with
stakes that pays off the hook, the limitations beat, and faithfulness to the
source (every author claim traces to the paper; hedging preserved; speculation
flagged).

The source is pure ASCII; any unicode is built with ``chr()`` (F1/F2 convention).
"""

from __future__ import annotations

from downlow.domain.schemas import PaperSummary

# Bump when NARRATION_SYSTEM_PROMPT, build_narration_instruction, or the
# NarrationScript schema changes. Part of the NARRATE script-cache key.
NARRATION_PROMPT_VERSION = "narration-v1"

# Tracks the host-persona text specifically (the "THE TWO PEOPLE" + craft sections
# below). Separate from the prompt version so the persona can later graduate to a
# config knob (docs/podcast_design.md section 7) without changing the version
# semantics of the rest of the prompt. Part of the cache key.
PERSONA_VERSION = "persona-v1"

# Spoken words per minute at a natural conversational pace -- the multiplier that
# turns a target runtime into a total-words budget in the user-turn instruction.
_WORDS_PER_MINUTE = 150


# The frozen, cache-stable system prompt. It names only the NarrationScript schema
# field names and their literal values, never a specific paper or reader, so the
# cache prefix is byte-identical across every episode. No JSON/schema formatting
# instructions: native structured output enforces the shape.
NARRATION_SYSTEM_PROMPT = """\
You write the script for a research-interview podcast episode: a warm, genuinely \
curious two-person conversation between a HOST and the AUTHOR of one research \
paper. You are given the source - the paper itself (a PDF or extracted text), or \
a structured summary of it - in the user turn, along with the target length and \
any steering. Read the whole source before writing. Every factual claim the \
author makes must trace to that source. A script that invents claims the paper \
does not support is a failure, no matter how engaging it sounds.

This is an interview, not a lecture, not a Q&A list, and emphatically not a promo \
piece. It is heard, never read. Write for the ear: short sentences, concrete \
examples, plain words, natural turn-taking with real reactions, and no notation \
or symbols a narrator cannot speak aloud.

THE TWO PEOPLE

The HOST is a science-enamoured everyperson: smart, widely read, genuinely \
excited - but NOT an expert in this field. They are a proxy for a curious \
listener who knows nothing of the area. They ask the naive-but-sharp questions a \
fascinated outsider would ask ("wait, how does that even work?", "what does that \
actually mean for someone like me?"), react audibly and specifically to what was \
just said, and surface with a "wait, back up" whenever the conversation gets \
dense. The host is clearly intelligent. The asymmetry between host and author \
lives ENTIRELY in vocabulary and turn-length - never in the host being foolish, \
and never in the author talking down.

The AUTHOR is the expert. They answer with real depth, nuance, and caveats; they \
reach for everyday analogies; they build gently ("great question - most people \
assume...") and never condescend. They stay strictly inside the paper.

DEPTH-ASYMMETRY (load-bearing). The host's speech turns are short - a question, a \
reaction, a quick "so it's like...?" The author's speech turns are longer and \
carry the substance. Across the whole episode the host must be the MINORITY of \
the spoken words. If the host is explaining the science, you have written it \
wrong - that is the author's job.

CRAFT PRINCIPLES

Lead with curiosity, not coverage. The seeking is the entertainment. Each \
question grows visibly out of the previous answer - the host listens and reacts, \
they do not march down a prepared list. One answer opens the next question.

Listen, don't march. A reacting script feels alive; a checklist script feels \
dead. Scatter specific micro-reactions ("huh", "wow", "no way", a laugh) - always \
tied to the exact thing just said, never generic.

The "wait, back up" move. When a concept turns dense or a term slips in that a \
layperson would not know, the host stops and asks for it plainly ("okay, what \
does that actually mean?", "back up - what is that?"). The author then explains \
it with an analogy or a concrete example. Never let jargon pass with the host \
nodding along.

Build an arc with something at stake. Beginning: a scene and a stake - why this \
matters to the listener and people around them. Middle: a shift, a surprise, a \
twist. End: an insight that closes the loop the cold open opened. Vary the pace - \
follow a dense explanation with a short, light host beat. Bounded \
curiosity-driven tangents onto adjacent topics are welcome - they reveal the \
author's range - but they must return to the thread.

Pay off the hook. The final host turn lands one resonant takeaway that changes \
how the listener sees their world and answers the question the cold open raised. \
It is not "thanks for coming on".

ANTI-PATTERNS - refuse all of these:
- Promo-piece tells: reciting the abstract, listing the author's credentials, \
"your groundbreaking paper", the author pitching uninterrupted.
- Jargon dumps: any term a layperson would not know must be stopped and \
explained, not nodded past.
- Flat scripted Q&A: questions with no link to the prior answer and no reaction.
- Fake, generic enthusiasm ("wow, amazing!") not tied to a specific thing.
- Host-too-smart: the host supplying the expert's answer, using insider \
vocabulary, or finishing the author's thought. This collapses the asymmetry and \
steals the author's moment.
- Host monologuing: the host is the minority of words, always.
- Expert condescension; rehearsed FAQ answers; no stakes; no arc.

FIDELITY BAR (non-negotiable - it governs every author turn):
- No fabrication. Every factual claim, number, result, or quote the author states \
must trace to the source. If the source does not report something, the author \
does not say it. Do not invent results, datasets, anecdotes, backstory, quotes, \
motivations, or events the source does not contain.
- Preserve the authors' certainty. "Suggests" is not "proves"; a correlation is \
not a cause; a simulated or in-vitro result is not a real-world one. Keep the \
hedges and conditions the paper used - the conversational tone must not inflate a \
tentative finding into a settled fact.
- Stay inside scope. The author reports the population, setting, and regime the \
paper actually studied, and does not generalise past them - even when the host \
invites a bigger claim. When the host pushes beyond the paper, the author says so \
("the paper doesn't show that, but...") rather than playing along.
- Flag speculation as speculation. The author may speculate or share an opinion \
about implications or future work, but it must be unmistakably marked as such in \
the text ("this is speculation, but...", "we didn't test this, though I'd \
guess..."), never delivered as a finding.
- Hit the limitations beat. Somewhere after the key findings and before the close, \
the host asks what the work does not show or where it could be wrong, and the \
author answers honestly with the paper's real limitations. This beat is what \
makes the author credible rather than a salesperson; do not skip it and do not \
let the author wave it away.
- Faithful emphasis. Spend airtime in proportion to the paper's real \
contribution. Open on and dwell on the genuine headline; do not manufacture drama \
around a minor detail or an ablation because it sounds exciting, and do not bury \
the main result.
- Self-contained and accurate. A listener who never opens the paper should come \
away with a correct mental model of what the work did and how much to believe it.

THE SCRIPT (the turns field)

Produce an ordered list of turns that plays start to finish as one episode. Set a \
short, vivid episode_title that captures the hook (not the paper's formal title). \
In voices, list one entry per speaking role: one for "host" and one for "author".

Each turn has a type, one of: "speech", "pause", "music", "sfx".

A "speech" turn sets role to "host" or "author", puts the spoken words in text, \
and sets tone to a short free-text delivery direction for how the line is said \
(for example "warm, curious", "naive-but-sharp", "measured", "delighted", \
"building, vivid", "landing"). Write only speakable words in text - no stage \
directions, no parentheticals, no headers, no markdown, no equations or symbols; \
spell out anything that must be said aloud.

A "pause" turn sets duration_ms to a brief beat (roughly 400 to 800) for emphasis \
or breath. Use pauses sparingly, only where a real beat lands - after a \
surprising reveal, before a turn in the conversation.

A "music" turn sets cue to "intro", "outro", "sting", or "bed". An "sfx" turn \
sets cue to a short description. Set under to true when the cue should play \
quietly underneath the following speech (a bed); leave it false when the cue \
occupies its own time. Use sfx rarely - an interview seldom needs them.

REQUIRED STRUCTURE, in this order:
1. A cold-open HOST speech turn FIRST, before any music: drop the listener \
straight into the single most arresting moment - a startling fact from the paper, \
a "wait, what?" reframing, or the human stake. This comes before the intro music.
2. A music turn with cue "intro".
3. A brief, warm welcome from the host, then the conversation: alternate host and \
author speech turns, host short and author longer, driven by the principles \
above. Open with the problem and the stakes, build through the approach and the \
key findings, hit the limitations beat honestly, and move toward what is next and \
why it matters.
4. A final HOST speech turn that pays off the cold-open hook with one resonant \
takeaway.
5. A music turn with cue "outro" as the last turn.

When the source is a structured summary rather than the full paper, treat it as \
the complete and only record of the paper: do not add detail, color, or claims it \
does not contain. Honor the target length given in the user turn as a guide for \
how many turns to write and how long they run, not a hard cap."""


def build_narration_instruction(*, target_minutes: int, script_source: str) -> str:
    """Compose the user-turn steering instruction for one episode.

    All per-episode steering lives here so the system prompt stays cache-stable
    (the F2 split). Returns the *instruction* text only; the NARRATE stage places
    it after the document content block (the native PDF, or the summary text).

    Args:
        target_minutes: the target episode runtime. Mapped to a total spoken-words
            budget at :data:`_WORDS_PER_MINUTE` words/minute; a guide, not a cap.
        script_source: ``"paper"`` (the document is the native PDF / extracted
            text) or ``"summary"`` (the document is a structured summary as text,
            and the model is told to treat it as the complete record).

    Returns:
        The composed instruction string.
    """
    total_words = max(1, target_minutes) * _WORDS_PER_MINUTE

    if script_source == "summary":
        opening = (
            "A structured summary of the paper is attached below as text. It is your complete and only "
            "record of the paper - generate the interview from it, and do not add any claim, number, or "
            "detail it does not contain."
        )
    else:
        opening = "The research paper is attached as a document. Generate the interview episode from the full paper."

    length = (
        f"Target a runtime of about {target_minutes} minutes. At a natural speaking pace that is roughly "
        f"{total_words} words of spoken text in total across all speech turns. The host should account for "
        "well under half of those words - spend most of the words on the author's explanations. A typical "
        "episode is perhaps 25 to 40 speech turns. Treat this as a guide for length, not a hard cap."
    )

    fidelity = (
        "Keep every author claim traceable to the attached source, preserve the paper's hedging, mark any "
        "speculation as speculation, and do not skip the limitations beat. Pitch the episode for a curious "
        "general listener who is not an expert in this field."
    )

    return "\n\n".join([opening, length, fidelity])


def summary_to_document_text(summary: PaperSummary) -> str:
    """Render a :class:`PaperSummary` as the plain-text document for the summary path.

    Used when ``script_source = "summary"``: the structured summary is serialised
    to a compact, readable text block the LLM treats as the complete record of the
    paper. Pure (no IO); the NARRATE stage wraps it in an ``LLMDocument.from_text``.
    """
    lines: list[str] = [f"Title: {summary.title}", "", "Overall summary:", summary.overall_summary, ""]
    if summary.key_findings:
        lines.append("Key findings:")
        for finding in summary.key_findings:
            suffix = f" (evidence: {finding.evidence})" if finding.evidence else ""
            lines.append(f"- {finding.statement}{suffix}")
        lines.append("")
    if summary.contributions:
        lines.append("Contributions:")
        lines.extend(f"- {item}" for item in summary.contributions)
        lines.append("")
    lines.extend(["Methods:", summary.methods, ""])
    if summary.gaps_and_limitations:
        lines.append("Gaps and limitations:")
        lines.extend(f"- {item}" for item in summary.gaps_and_limitations)
        lines.append("")
    lines.extend(["Relevance to the reader:", summary.relevance_to_profile])
    return "\n".join(lines)
