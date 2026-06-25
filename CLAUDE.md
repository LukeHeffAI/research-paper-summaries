# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DownLow** (repo dir `research-paper-summaries`, import root `downlow`, CLI `dl`) is a local-network "Spotify for research papers": a library of papers where, per paper, you read the source PDF in-app, read a context-steered text summary, and play a **two-presenter (host + author) interview podcast** — served from the owner's machine over the LAN. Single-user (Luke) now; multi-user is a possible later goal.

**This repo is in its foundation phase.** The clean package + tooling are in place; the five existing features (F1–F5) have **not been re-implemented yet** — most modules under `src/downlow/` are intentional docstring stubs that Phase 1 fills in. **Read `PROJECT_PLAN.md` before doing feature work** — it is the authoritative scope, architecture, data model, phased roadmap, and the record of locked decisions and open questions.

## Source of Truth

- **`PROJECT_PLAN.md`** — the living plan: vision, target architecture, data model, the rebuilt pipeline, phased roadmap (with the F1–F5 traceability table), tech choices, risks, scope-of-this-phase, and open questions. Authoritative for *what* to build and *why*.
- **`docs/podcast_design.md`** — authoritative NARRATE/F4 design: the everyperson-host persona, podcast craft principles (with sources), the multi-speaker script schema, the audio mixer (ripped from VTTD), the config-file→Settings strategy, and the multi-paper-ready Episode model.
- **`README.md`** — quickstart commands.
- **`legacy/`** — the original pre-rebuild scripts, kept **only** as a behavioural reference for the F1–F5 rebuild. Broken on Linux (Windows backslash paths), legacy OpenAI SDK, external-LaTeX hack. Excluded from ruff/mypy/CI. **Do not import from `legacy/`; delete it once Phase 1 is complete and the traceability tests pass.**
- **`FUTURE_FIXES.md`** — running scratchpad for known issues / tech debt (create it on first use). Append rather than fixing unrelated issues opportunistically; convert to GitHub issues via the `future-fixes-to-issues` skill.

## General Principles

- **Best practices first.** If a request conflicts with best practice, surface the trade-off and recommend the better path; defer to the user if they choose otherwise.
- **Mind the architecture.** Avoid quick fixes that violate the dependency rule below. Note medium/high-priority debt in `FUTURE_FIXES.md` rather than fixing unrelated things opportunistically.
- **Functions do one thing.** Avoid `x_and_y()` naming that bundles two concerns.
- **Ask when ambiguous.** The user provides context readily — don't guess on scope or design.
- **Hold the phase boundary.** This phase rebuilds F1–F5 and scaffolds the future; it ships no new user-facing features (no web UI, no API endpoints, no auth, no voice cloning). New ideas → `FUTURE_FIXES.md` / issues, not commits.

## Specialist Invocation Rules (MANDATORY)

Before planning, designing, or implementing in a matching domain, invoke the relevant specialist first. Pass all relevant context in the prompt (they run in a separate context). Line/file count is not the measure — a 3-line change to a summarisation prompt still warrants `ml-engineer` + `academic-writing-advisor`.

| Trigger | Specialist | Type |
|---|---|---|
| Backend / core work: FastAPI, SQLModel, services, pipeline stages, adapters, CLI | `backend-engineer` | Agent |
| LLM / ML work: Claude integration, prompts, summary/narration schemas, evaluation, the TTS/mix pipeline logic | `ml-engineer` | Agent |
| Significant refactor, architecture migration, or restructuring across modules | `systems-architect` | Agent |
| Any tool / framework / library selection or architecture decision | `modern-stack-advisor` | Agent |
| Summarisation quality, research framing, lit-review structure, summary or podcast **content** | `academic-writing-advisor` | Agent |
| Frontend code: React 19 / Vite / TS / Tailwind components, hooks, routing, the persistent player, wiring the UI to the API | `frontend-engineer` | Agent |
| UX / interaction / usability / information architecture / user flows / onboarding copy | `ux-design-advisor` | Agent |
| Visual identity / design system / brand / palette / typography / motion / landing page | `deeptech-brand-architect` | Agent |
| PR review requested | `pr-reviewer` | Skill |
| A GitHub issue to solve | `issue-solver` | Skill |
| Git history search beyond a simple `git log` | `git-detective` | Skill |
| Convert `FUTURE_FIXES.md` entries to GitHub issues | `future-fixes-to-issues` | Skill |
| Blocked on an inaccessible external resource (DB, API, running service) | `ask-for-help` | Skill |
| Authoring or optimising a multi-agent workflow | `workflow-optimizer` | Skill |

Exceptions: pure research/explanation with no code changes, meta questions about tooling, and git/shell operations with no code edits.

## Architecture

**The cardinal rule — inward-only dependencies.** The package is layered and dependencies point inward only:

```
domain/  →  (nothing but stdlib + pydantic)        # entities, enums, DTOs, PORT Protocols
core/    →  domain/ only                            # pure pipeline orchestration + use-case services
adapters/→  domain/ (+ external libs)              # the ONLY place third-party SDKs may be imported
cli/     →  core/services + adapters/ + config/    # thin Typer driver (composition root)
api/     →  (reserved, empty)                       # future FastAPI layer; will call core/services UNCHANGED
```

- **`core/` must stay pure**: no `print`, no `sys.argv`, no third-party SDK imports, no filesystem assumptions. It depends on ports (Protocols in `domain/ports.py`), which adapters implement. This is what lets the future FastAPI layer call `core` services unchanged — and lets tests run entirely on **fakes** (`tests/fakes/`) with no network. The `T20` ruff rule (no `print`) helps enforce IO-purity in `core`.
- **Never leak a third-party SDK type past `adapters/`.** Introduce/extend a port before swapping or adding a backend.
- **Pipeline (5 stages):** `INGEST → SUMMARISE → RENDER → NARRATE → STORE`. Each stage is idempotent, content-hash-cached, and retryable-from-failure (status tracked on a `PipelineRun`/`StageRun`). `RENDER` and `NARRATE` both consume the summary and are independent. See `PROJECT_PLAN.md` → "The Rebuilt Pipeline".

**Locked decisions** (do not re-litigate; see `PROJECT_PLAN.md`): Anthropic **Claude** (default summarise input = the PDF sent **natively** to Claude; text extraction kept for the reader/search/cache/fallback) · **Typst** report via a deterministic data-driven template (not LLM-emitted markup) · **SQLite via SQLModel + Alembic now**, Postgres-ready later · two-presenter podcast = Claude interview script → per-turn ElevenLabs TTS → `pydub` mix · React 19 + Vite frontend (future).

## Working on the LLM layer

When touching anything Claude/Anthropic-related (the `anthropic` SDK, `messages.parse` structured output, native-PDF input, thinking/effort, streaming, prompt caching, `count_tokens`, model IDs/pricing), **consult the `claude-api` skill first — do not answer from memory.** Defaults: `claude-sonnet-4-6` for summarisation/narration, `claude-opus-4-8` for the hardest reasoning; adaptive thinking only (never `budget_tokens`); stream large outputs (non-streaming large `max_tokens` raises `ValueError`); measure long-input budgets with `count_tokens`, never `len()`/tiktoken.

## Code Conventions

- **Python 3.11+**, line length 120. **ruff** for lint+format (select `E,W,F,I,N,UP,B,SIM,T20,RUF`; ignore `E501,N815,RUF012`; first-party = `downlow`). **mypy strict** on `src/downlow/`.
- **Imports:** `src/` is on the path; import as `from downlow.core... import ...`. First-party isort group is `downlow`.
- **Config:** the only place the environment is read is `downlow.config.settings.Settings` (pydantic-settings). Never scatter `os.getenv`. Secrets are optional at load time and validated where used.
- **Paths:** always `pathlib`, never string concatenation (the legacy bug was Windows backslash paths). A test guards POSIX-safe construction.
- **Tests:** mock every external API (Claude, ElevenLabs) via fakes behind the ports; the real `typst`/`ffmpeg` binaries are exercised only in `tests/integration/`. Coverage `fail_under` is **0 during the foundation phase** and ratchets up (60 → 70 → 80) as F1–F5 land.

## Commands

```bash
uv sync --extra dev                       # create the venv + install (dev tools included)
uv run dl version                         # run the CLI (`dl info` for orientation)
uv run ruff check src/ tests/             # lint
uv run ruff format src/ tests/            # format (CI runs `ruff format --check`)
uv run mypy src/downlow/                  # type-check (strict)
uv run pytest                             # all tests
uv run pytest tests/unit/test_smoke.py    # a single file
uv run pytest -k test_cli_version         # a single test by name
uv run pytest --cov=downlow --cov-report=term-missing   # with coverage (gate from pyproject)
git config core.hooksPath .githooks       # one-time per clone: enable the ruff-format pre-commit hook
```

**System dependencies (needed once Phase 1 lands):** the `typst` binary (report rendering) and `ffmpeg` (`pydub` audio mixing).

CI (`.github/workflows/ci.yml`) runs three jobs on `astral-sh/setup-uv`: **lint** (ruff check + format --check), **typecheck** (mypy), **test** (pytest + coverage). Work lands via PR on `main`.
