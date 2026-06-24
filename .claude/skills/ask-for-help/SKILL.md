---
name: ask-for-help
description: >
  Behavioral guardrail that stops Claude from guessing when it lacks access to external resources
  (DBs, APIs, remote services, schedulers, logs, running processes, deployed environments).
  Trigger on permission errors, network errors, connection refused, timeouts, speculative output
  about what a system "probably" contains, or debugging that depends on runtime state Claude
  cannot observe (the SQLite DB, Anthropic/ElevenLabs API responses, ffmpeg/Typst subprocess output,
  env vars / API keys on the local machine). Overrides the instinct to guess.
---

# Ask For Help — Stop Guessing, Start Asking

**Work Style.** `CLAUDE.md` §Work Style applies — batch up to 3 questions per ask (one round-trip beats three), structured input over prose, terse output, trust the dispatcher's stated facts.

## The Problem This Solves

When Claude can't access a resource (DB, API, scheduler, remote service, log file, deployed environment), its defaults are:

1. Guess what the resource contains and proceed on assumptions
2. Retry the same failing command with minor variations
3. Write speculative code based on imagined state
4. Generate plausible-sounding but fabricated error analyses
5. Spiral through multiple failed attempts without pausing

**This wastes the user's time and produces unreliable output.** The user is sitting right there and can get the information in seconds.

## Core Rules

### The 2-Strike Rule

If you attempt to access a resource and fail:

- **Strike 1**: try ONE reasonable alternative (different path, different command, check for a local copy).
- **Strike 2**: if that fails, **STOP IMMEDIATELY** and ask the user.

Do NOT try a third approach. Do NOT speculate about contents.

### UX-First Help Requests

**The #1 rule: make it effortless for the user to respond.** The user should answer with a tap wherever possible — not by typing prose.

#### Use structured input (multi-choice) when the answer can be a choice

Use `ask_user_input_v0` (or equivalent) for:

- **Diagnosing environment**: "Where is this running?" → `Local dev` / `uv venv` / `CI` / `Other`
- **Choosing next steps**: "Can't reach the SQLite DB. How proceed?" → `I'll paste output` / `Skip DB for now` / `Use a fake adapter` / `Let me fix it`
- **Confirming assumptions**: "Anthropic API key set in env?" → `Yes` / `No` / `Not sure`
- **Gathering context**: "Which external service is failing?" → `Anthropic Claude` / `ElevenLabs` / `Typst` / `ffmpeg`

Ask up to 3 questions at once — batching is encouraged. One interaction beats slow back-and-forth.

**Example — proactive context gathering:**

```
Q1: "Where is the pipeline running?"        [Local CLI (dl), uv venv, CI, Other]
Q2: "Are the API keys configured?"          [Yes, No, Not sure]
Q3: "Is the SQLite library DB present/seeded?"  [Yes, No, Not sure]
```

#### When free-text is needed (logs, query results, errors, config contents)

1. **Triage with a structured question first**: "I need the pipeline output. Can you access it?" → `Yes, I'll paste` / `I can run a command` / `No access`
2. **Then provide a specific, copy-pasteable command** if they say yes:
   > Paste the output of:
   > ```
   > dl summarise <paper-id> --verbose
   > ```
3. **Always provide the exact command.** Never say "check the logs" without specifying which logs and how.

### Never Do These

- **Never fabricate resource contents.** No "the DB probably has a papers table with id, title, authors…" without evidence.
- **Never silently assume.** If you must assume to proceed, flag it explicitly: "⚠️ ASSUMPTION: the Claude response is JSON with a `summary` key. Please confirm."
- **Never retry more than once.** Two attempts max, then ask.
- **Never diagnose without data.** "The issue is probably X" → replace with "I'd need to see X to diagnose — could you run [specific command]?"
- **Never ask open-ended questions when closed ones will do.** "What service is failing?" is worse than `Anthropic` / `ElevenLabs` / `Typst` / `ffmpeg` / `Other`.
- **Never dump a wall of questions in prose.** Convert to structured input.

## Recognising When You're Spinning

These patterns in your own behaviour mean **stop immediately and ask**:

**Self-correction / second-guessing (the #1 missed trigger):**

- You write "No, wait..." / "Hmm, actually..." / "On second thought..."
- You re-interpret user intent: "Maybe the user meant..." / "Perhaps they wanted..."
- You argue with yourself: "Well, it could be X, but it might also be Y..."
- You hedge mid-action: "Let me reconsider..." / "That doesn't seem right..."
- You narrate uncertainty: "I'm not sure if..." / "This might not be..."

If any of these appear, that is the signal. Ask the user — they resolve the ambiguity in seconds.

**Speculation and fabrication:**

- Paragraphs starting with "likely", "probably", "presumably", "I would expect"
- Generating mock / example data to "illustrate" what a system might return
- Writing error handling for errors you haven't seen
- Reverse-engineering system state from code alone instead of observing it

**Looping and retrying:**

- 2+ different approaches to the same resource
- "Let me try another approach" for the third time
- Tweaking a command slightly and re-running, hoping for a different result

**Rule: the moment you feel uncertain about what the user wants or what a system contains, ask.**

## Proactive Asking

Don't wait until you fail. If a task **will obviously require** access you don't have (a live Anthropic/ElevenLabs call, a populated SQLite DB, a real source PDF), ask upfront before writing any code. Use structured input to gather everything in one round-trip:

```
Q1: "Needs a real Claude call. Run it live?"  [Yes, I'll run | Yes, via tool | No, use a fake | No access]
Q2: "API keys / env config — where?"          [I'll paste | .env I can share | Not set yet | Not sure]
Q3: "Source PDF / sample paper available?"     [Yes, I'll provide path | In the repo already | No | Not sure]
```

## Batching

If you need multiple pieces of information, ask for all of them at once. 3 tappable questions in 5 seconds beats 3 separate free-text questions across 3 messages.

## How to Format Your Ask

### Preferred: structured input

Use `ask_user_input_v0` with 1–3 questions, 2–4 options each. Precede it with 1–2 sentences explaining what you hit and why you need help.

### Fallback: when you need raw output

```
🔍 **I need your help to proceed.**

I can't access [specific resource] from here because [brief reason].

Could you please run the following and paste the output?

```bash
[exact command(s)]
```

[Optional: "While waiting, I'll continue working on [other part that doesn't need this info]."]
```

The "while waiting" note matters — if other work doesn't block on the missing info, do it in parallel.

### Anti-pattern: the wall of questions

**DON'T:**
> I need some information. Which service is failing? Are the API keys set? Is this in a uv venv or system Python? Do you have ffmpeg installed? Can you run the pipeline? What's the schema for the papers table? Also, which Claude model?

**DO:** Structured input for the categorical questions (service, environment, access level). Based on answers, follow up with one targeted command if still needed.
