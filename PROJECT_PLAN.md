# DownLow — Project Plan

*Working title **DownLow** (the low-down on a paper); import root `downlow`, CLI `dl`. Repo dir stays `research-paper-summaries`.*

> **A local-network "Spotify for research papers": maintain a library of papers and, per paper, read the source PDF, read a context-steered text summary, and play a two-presenter interview podcast — all served from your own machine over the LAN.**

This plan rebuilds the existing run-once script into a clean, typed, tested Python `core` package with a thin CLI, and lays the architectural foundations (env, CI/CD, agent culture, directory seams) that make every later phase additive rather than a rewrite. It is modelled on the planning-doc format used in the proven VTTD project: a one-line pitch, a current-state audit, an ASCII pipeline, checkbox phases with sub-IDs, a technology-choices table, and a recommended build order.

**Phase boundary up front:** this phase rebuilds the five existing features (F1–F5) at expert quality and scaffolds the future. It builds **no** new user-facing features — no web UI, no API endpoints, no library/search/dashboard, no auth. (The two-presenter host+author podcast itself *is* rebuilt this phase; only *voice cloning* of a real author's voice — and its consent-onboarding flow — is designed-but-not-built.) Everything else above is designed and planned here, not implemented.

---

## Vision & End State

A local-network web app where the owner (Luke, an ML researcher at the University of Adelaide) maintains a **library** of research papers and, for each one, can:

1. **Read** the source PDF in-app,
2. **Read** a context-steered text summary, and
3. **Play** a podcast/audio summary — the centrepiece.

The backend and UI are served from the owner's host machine over the local network. Single-user for now; opening to other users is a possible later goal, so the data model and config keep a `user`/profile boundary throughout (the difference between single-user-today and multi-user-later is scope, not a schema rewrite).

The product is explicitly modelled on the owner's proven MVP, **Voice-To-The-Dark (VTTD)** — a FastAPI app that turns Reddit r/nosleep stories into dramatic multi-voice audio. VTTD already ships every primitive this product needs (library, recently-viewed, folders, resume-playback, in-app reading, multi-voice script → mixed audio, a persistent PWA player), so most of the future work is adaptation, not invention.

### The audio is a two-presenter interview podcast

The audio summary is the heart of the product and must feel like a natural **two-presenter interview**, not a flat single-voice read:

- A **consistent host/interviewer** — the same recognisable "show host" voice on every episode — interviews the **paper's author**, whose voice varies per paper. They go back and forth (question → answer → follow-up), naturally surfacing the summary, key findings, contributions, and gaps.
- **Killer feature — voice cloning:** a real researcher can supply their own voice for the "author" role by reading a short standard template script; that recording is run through ElevenLabs voice cloning to create a custom author voice for their paper's podcast.

**This phase ships the full two-presenter (host + author) interview podcast** — Claude generates a host↔author interview script, each turn is synthesised with its role's stock voice, and the segments are mixed into one track (VTTD's *script → segments → per-segment TTS → mix* pattern). Only *voice cloning* of a real author's own voice (and its consent-onboarding flow) is deferred; the multi-speaker turn schema + `Voice`/`TTSClient` ports make it additive.

---

## Current State Audit

### What exists today

A single-user, run-once CLI script (`python main.py`, hardcoded user) with one linear pipeline in `main()`:

1. **Bootstrap user dirs** — creates `users/{user}/{documents,summaries,audio}` + an empty `pdf_texts.json`.
2. **Discover PDFs** — `file_processing.get_pdf_filepaths` walks `users/{user}/documents` for `.pdf`.
3. **Extract text** — `file_processing.read_pdf` uses `pdfplumber`, caches to `pdf_texts.json`.
4. **Build context prompt** — `research_details.py` holds `ResearchContext` + `DocumentContext` dataclasses, loaded from `data/research_data.json` (per-user research profile: `research_field`, `research_topic`, `research_interests[]`, `research_focus`) and `data/document_data.json` (`document_type`, `document_return_details[]`); `build_context_prompt()` composes the steering prompt.
5. **Summarise** — `text_processing.ResearchSummariser` calls OpenAI (legacy `openai.ChatCompletion`, `gpt-4o-mini`), per-PDF, caches to `summaries/{title}.txt`; has an overwrite flag.
6. **To LaTeX** — `text_processing.LaTeXConverter` (LLM) merges all summaries into a LaTeX doc; `CustomLLMCall` (LLM) generates a filename.
7. **Build PDF** — writes `Research-Summaries/main.tex`, `sleep(20)`, then `os.rename Research-Summaries/main.pdf → users/{user}/summaries/{filename}.pdf` (relies on an **external** latex compiler/watcher — fragile, non-reproducible).
8. **Optional audio** — `text_processing.TechnicalPodcastGenerator` (LLM) writes a single-voice podcast script; `audio_processing.VoiceGenerator_ElevenLabs` POSTs to ElevenLabs and streams an mp3 to `users/{user}/audio/{filename}.mp3`.

Also `file_processing.update_pdf_filenames`: an interactive heuristic that renames PDFs from their first text line (not in the main flow).

### Existing features to rebuild (and nothing more)

| ID | Feature |
|----|---------|
| **F1** | PDF text extraction |
| **F2** | Per-user research-context-steered summarisation via LLM |
| **F3** | Compiled summary **report** document (was LaTeX→PDF, now Typst→PDF) with auto-generated title/filename |
| **F4** | Optional single-voice "podcast" audio summary via ElevenLabs |
| **F5** | The PDF-filename-from-first-line heuristic utility |

### Known problems the rebuild must fix

- **Windows-only backslash paths that are broken on Linux** — e.g. `f"users\{user}\audio"` contains a `\a` (bell) and `\d` escape; `os.rename("Research-Summaries\main.pdf")`.
- **The external-LaTeX-watcher + `sleep(20)` hack** — non-reproducible; depends on an Overleaf/latexmk process the code doesn't control.
- **Legacy pre-1.0 OpenAI SDK** — `openai.ChatCompletion`.
- **No package / venv / tests / typing / lint.**
- **Config-vs-data overlap** — per-user profiles live both in `data/research_data.json` and implicitly in the `users/` tree; the owner's journal wants this unified into a DB.
- **No error handling, retries, or parallelism.**
- **Mixed concerns in `main()`** — IO, business logic, and orchestration tangled together; hardcoded model/token globals.

### Owner's stated trajectory (from `app_planning.md` + `progress_journal.md`)

- **Near:** summaries + audio.
- **Mid:** user profiles, dashboard, search, feedback.
- **Long:** Zotero integration, visualisation.
- The journal explicitly wants: a DB instead of JSON, a user-creation class, parallelised PDF reading + summarisation + podcast generation, removal of the Overleaf dependency, and better podcasts (per-section generation referencing neighbours, stitching, music/SFX).

---

## Aims, Goals & Desired Outcomes

### Overarching aim

Transform `research-paper-summaries` from a fragile single-run script into a local-network "Spotify for research papers." The aim of **this phase specifically** is narrower and load-bearing for everything above: **rebuild the existing capability to expert quality as a clean, typed, tested Python `core` package callable unchanged by a future FastAPI layer, and lay the architectural foundations that make every later phase additive rather than a rewrite.**

### Strategic goals

1. **G1 — Preserve every existing capability, lose nothing.** All five current features (F1–F5) survive the rebuild with equal or better behaviour, with regression coverage proving it.
2. **G2 — Engineer for the future, not just the rebuild.** The `core` package is provider-agnostic (port/adapter), DB-ready, and shaped so the multi-speaker podcast + voice-cloning vision and the FastAPI `api/` layer drop in without reworking `core`.
3. **G3 — Eliminate the known defects.** Cross-platform paths, deterministic Typst PDF generation (no Overleaf watcher / `sleep(20)`), modern Anthropic SDK, error handling/retries, and separation of concerns.
4. **G4 — Establish an engineering culture.** uv + pyproject, ruff + mypy strict, pytest + coverage gate, CI/CD, `.claude` agents/skills, and a `CLAUDE.md` adapted from the `tipping-tools` reference repo.
5. **G5 — Boost research productivity.** Cut the per-paper time-to-comprehension (extract → steered summary → report → optional audio) and make the pipeline repeatable, parallelisable, and trustworthy.
6. **G6 — Keep the door open to multi-user later** without building it now: the data model and config keep a `user`/profile boundary, so single-user today and multi-user later differ by scope, not by schema rewrite.

### Desired outcomes / success criteria

- **DO1** — `uv run dl <command>` runs the full existing pipeline end-to-end on Linux with zero Windows-path or external-compiler dependencies. *(G1, G3)*
- **DO2** — `from downlow.core import …` exposes every feature as a typed, side-effect-isolated callable that a FastAPI route could invoke unchanged (no `print`, no `sys.argv`, no hardcoded user). *(G2)*
- **DO3** — Typst renders the compiled summary report PDF in-process, deterministically, in a single bundled-binary call — no watcher, no sleep. *(G3)*
- **DO4** — LLM calls go through a single `LLMClient` port backed by an Anthropic adapter (`claude-sonnet-4-6` default for summarisation; `claude-opus-4-8` available for hardest reasoning), with retries and truncation handling. *(G2, G3)*
- **DO5** — The podcast ships as a **two-presenter host+author interview**: a multi-speaker turn schema, a Claude-generated interview script, per-turn TTS with distinct stock host/author voices, mixed into one mp3 via `pydub`. Only author voice *cloning* (consent onboarding) is deferred. *(G2)*
- **DO6** — CI is green: `ruff check` + `ruff format --check`, `mypy` (strict), `pytest --cov` above the coverage gate, on every push/PR. *(G4)*
- **DO7** — The requirements-traceability table maps every F1–F5 capability current-location → new-module → covering test, with all tests passing. *(G1)*
- **DO8** — `.claude/` agents + skills and `CLAUDE.md` are present and adapted from `tipping-tools` (greyhound-domain agent replaced by a research/academic-writing advisor). *(G4)*
- **DO9** — The directory layout contains empty-but-real seams (`api/`, `frontend/`) so later phases add files, not restructure. *(G2)*
- **DO10** — No new user-facing feature ships this phase (explicit non-goal); the phase boundary holds. *(scope discipline)*

---

## Target Architecture

A single src-layout package, **`downlow`** (`src/downlow/`), with strict **inward-only** dependencies. The dependency rule is one-directional: **`domain/` depends on nothing but stdlib, pydantic, and its own port Protocols; `core/` depends only on `domain/`; everything else depends inward.** Adapters implement ports. The CLI (now) and API (later) are thin drivers that wire concrete adapters into the core and invoke use-cases.

### Directory tree

```
research-paper-summaries/
├── pyproject.toml              # uv + hatchling; packages = ["src/downlow"]
├── uv.lock
├── .env.example
├── .python-version             # pin 3.11 (matches reference repo target)
├── CLAUDE.md
├── README.md
├── ruff.toml / [tool.ruff]     # line-length 120, py311, E,W,F,I,N,UP,B,SIM,T20,RUF
├── .githooks/pre-commit        # ruff-format-fix staged .py (adapted from tipping-tools)
├── .github/workflows/ci.yml    # lint / typecheck / test (scan job deferred until Docker)
├── .claude/
│   ├── agents/                 # backend-engineer, ml-engineer, systems-architect,
│   │                           #   modern-stack-advisor + NEW academic-writing-advisor
│   │                           #   (replaces greyhound-racing-expert) + deeptech-brand-
│   │                           #   architect (frontend aesthetic; adapted from augur)
│   └── skills/                 # ask-for-help, future-fixes-to-issues, git-detective,
│                               #   issue-solver, pr-reviewer, workflow-optimizer
├── src/downlow/
│   ├── __init__.py
│   ├── config/
│   │   ├── settings.py         # pydantic-settings BaseSettings (the ONLY env reader)
│   │   └── models.py           # ModelConfig: model-id + max_tokens + effort per stage (typed)
│   │
│   ├── domain/                 # PURE: entities, enums, value objects, port Protocols.
│   │   ├── enums.py            # StageStatus, RunStatus, SpeakerRole, VoiceSource, ...
│   │   ├── schemas.py          # Pydantic DTOs: ExtractedText, PaperSummary,
│   │   │                       #   NarrationScript (turns), RenderedReport, PodcastAsset
│   │   └── ports.py            # Protocols: LLMClient, TTSClient, PdfExtractor,
│   │                           #   ReportRenderer, ArtifactStore, Clock, Repository[...]
│   │                           #   (Clock: injectable now()/UTC so timestamps in
│   │                           #    snapshot tests + cache keys are deterministic)
│   │
│   ├── core/                   # PURE orchestration: depends only on domain.
│   │   ├── pipeline.py         # PipelineRun orchestrator: runs stages, records status
│   │   ├── stages/
│   │   │   ├── base.py         # Stage Protocol + StageResult + cache-key helpers
│   │   │   ├── ingest.py       # IngestStage(PdfExtractor, ArtifactStore)
│   │   │   ├── summarise.py    # SummariseStage(LLMClient)
│   │   │   ├── render.py       # RenderStage(ReportRenderer, ArtifactStore)
│   │   │   └── narrate.py      # NarrateStage(LLMClient, TTSClient, ArtifactStore)
│   │   ├── prompts/            # frozen system prompts as module constants (cache-stable)
│   │   │   ├── summary.py
│   │   │   └── narration.py
│   │   ├── eval/               # RESERVED — scaffold for the prompt-version eval harness
│   │   └── services/           # USE-CASE layer — the API/CLI seam
│   │       ├── library.py      # add_paper, list_papers, get_paper (CRUD over Repository)
│   │       ├── processing.py   # process_paper(paper_id, stages=...) -> PipelineRun
│   │       ├── filename.py     # F5 filename-from-first-line heuristic (pure)
│   │       └── voices.py       # host-voice config, voice pool, (FUTURE) clone onboarding
│   │
│   ├── adapters/               # IMPURE: implement domain.ports. Swappable, faked in tests.
│   │   ├── llm/anthropic_client.py     # AnthropicLLMClient implements LLMClient
│   │   ├── pdf/extractor.py            # PdfExtractor impl (pdfplumber now; pymupdf later)
│   │   ├── render/typst_renderer.py    # TypstRenderer implements ReportRenderer
│   │   ├── tts/elevenlabs_client.py    # ElevenLabsTTSClient implements TTSClient
│   │   ├── storage/filesystem_store.py # FilesystemArtifactStore implements ArtifactStore
│   │   └── db/                          # SQLModel persistence
│   │       ├── engine.py                # create_engine, session factory, get_session
│   │       ├── tables.py                # SQLModel table=True entities (the DB schema)
│   │       └── repositories.py          # SqlModelRepository[...] implements Repository
│   │
│   ├── cli/                    # THIN driver: typer app. Wires adapters -> services.
│   │   ├── app.py              # `dl` entrypoint
│   │   ├── deps.py             # composition root: build container from Settings
│   │   └── commands/          # add, process, summarise, report, narrate, rename, run
│   │
│   ├── api/                    # RESERVED — EMPTY this phase. __init__.py + README only.
│   │                          #   Future FastAPI app calls core/services unchanged.
│   └── frontend/              # RESERVED — EMPTY. README records the React-vs-Jinja/PWA
│                              #   OPEN QUESTION for the owner. No build this phase.
├── tests/
│   ├── conftest.py            # fixtures: settings, tmp_data_dir, db_session,
│   │                          #   fake_llm, fake_tts, fake_renderer, fake_store, sample_pdf
│   ├── fakes/                 # in-memory port impls (FakeLLMClient, FakeTTSClient, ...)
│   ├── fixtures/              # committed sample PDFs + recorded LLM JSON
│   ├── unit/                  # stages + services against fakes (no network, no binaries)
│   └── integration/          # adapters against real SQLite tmpfile / real typst binary
└── typst/
    └── report.typ            # Typst template the renderer fills (data-driven, no LLM LaTeX)
```

### Module boundaries and the dependency rule

- **`domain/` → nothing.** Entities, enums, DTOs, and the port Protocols. No SQLModel `table=True`, no SDK imports, no FastAPI. This is the contract every other layer agrees on.
- **`core/` → `domain/` only.** Stages and services accept ports via constructor injection; they never import `adapters/`, `anthropic`, `pdfplumber`, the Typst binary, or `sqlmodel`. This is what makes the future FastAPI layer free: `process_paper(...)` is identical whether called from a Typer command or a FastAPI route. (The `T20` ruff rule — no `print`/`pprint` — helps enforce IO-purity here.)
- **`adapters/` → `domain/` (+ external libs).** Each adapter is the *only* place a given third-party dependency appears. Swapping ElevenLabs for another TTS, or pdfplumber for PyMuPDF, is a one-file change behind a stable port.
- **`cli/` and (future) `api/` → `core/services` + `adapters/` + `config/`.** These are the composition roots — the only layers allowed to instantiate concrete adapters and hand them to services. They contain no business logic; a Typer command is ~5 lines wrapping a service, and a FastAPI route will be the same ~5 lines.

### The seams that let FastAPI + workers slot in without rework

1. **Use-case/service layer (`core/services/`).** Every meaningful operation is a plain function/method with typed inputs and a typed return — `add_paper`, `process_paper`, `list_papers`. No logic migrates when the caller changes from CLI to HTTP.
2. **`PipelineRun` / `Job` abstraction.** `process_paper` produces and persists a `PipelineRun` row with per-stage status. This is the sync-now/async-later boundary: today the CLI runs it inline and returns the finished run; tomorrow a FastAPI route enqueues a `PipelineRun(status=pending)` and a worker picks it up. The core call (`pipeline.run(run, stages)`) is identical in both worlds.
3. **Repository port + session-factory injection.** Services depend on `Repository[T]`, not a global engine. The CLI builds a short-lived session per command; FastAPI will use a `get_session` dependency; a worker will own its own session. SQLite-now/Postgres-later is purely a `DATABASE_URL` change because nothing above `adapters/db/` knows the dialect.
4. **`ArtifactStore` port.** Binary artifacts (PDFs, mp3s, reports) flow through a storage port that returns logical references stored in the DB, not raw filesystem paths baked into core. A future move to object storage for multi-user is an adapter swap.
5. **Stage Protocol with idempotent, content-hash-keyed execution.** Each stage is independently invokable and re-runnable, so a worker can retry a single failed stage without re-running the pipeline — the foundation for the journal's "parallelise reading/summarisation/narration" goal.

### Pipeline stage interfaces

Five stages mirror VTTD's FETCH → ADAPT → GENERATE → MIX → DELIVER, retargeted to PDFs. Every stage is **(a) idempotent** (same input ⇒ same output, safe to re-run), **(b) cache-aware** (keyed by a content hash of its inputs + the model/version that produced it; a cache hit returns the stored artifact with no API call), and **(c) retryable-from-failure** (the `PipelineRun` records per-stage status, so execution resumes at the first non-`succeeded` stage). `RENDER` and `NARRATE` both consume the `PaperSummary` and are independent of each other (parallelisable).

**Stage Protocol (`core/stages/base.py`):**

```python
class StageResult(BaseModel):
    status: StageStatus            # succeeded | failed | skipped
    output_ref: str | None        # artifact reference or DB id of the produced entity
    cache_hit: bool
    model_id: str | None          # which Claude model produced it (None for non-LLM stages)
    error: str | None

class Stage(Protocol):
    name: ClassVar[str]
    def cache_key(self, ctx: StageContext) -> str: ...     # hash(inputs + model_id + prompt_version)
    def run(self, ctx: StageContext) -> StageResult: ...    # idempotent; checks cache first
```

The ports faked in tests are `LLMClient`, `TTSClient`, `PdfExtractor`, `ReportRenderer`, `ArtifactStore`, `Repository[T]`, and `Clock`. `tests/fakes/` supplies deterministic in-memory implementations; all external APIs and the Typst binary are mocked in `unit/` and exercised for real only in `integration/`. (Per-stage contracts are detailed in **The Rebuilt Pipeline** below.)

### Configuration strategy

One `Settings(BaseSettings)` in `config/settings.py` is the **single** place the environment is read — replacing the scattered `os.getenv` calls and module-level model/token globals. Built on `pydantic-settings` (the reference repo's stated upgrade path for VTTD's ad-hoc `config.py`).

**Secrets and infra (from env / `.env`):**

- `ANTHROPIC_API_KEY` — Claude (full switch off OpenAI; the SDK also auto-reads this, but Settings validates presence and fails fast).
- `ELEVENLABS_API_KEY` — TTS.
- `DATABASE_URL` — default `sqlite:///${DATA_DIR}/downlow.db`; set to a `postgresql+psycopg://…` URL later with no code change.
- `DATA_DIR` — root for all binary artifacts and caches (default `./data` or an XDG path).

**Typed application settings (defaults in code, overridable by env, NOT secrets):**

- `summary_model: str = "claude-sonnet-4-6"`, plus `report_title_model` / `narration_model` (default `claude-sonnet-4-6`; allow `claude-opus-4-8` for the hardest reasoning).
- `summary_max_tokens` (default ~8000 — structured summaries are small, safely non-streaming) and `narration_max_tokens` (larger; **must be streamed** — see below). Never lowball — truncation forces a retry.
- `request_timeout`, `max_retries` (default 2; bump to ~5 for batch runs). **Note:** the SDK retries not only 408/409/429/5xx but also connection errors **and timeouts**, so a slow call's worst-case wall-clock is `request_timeout × (max_retries + 1)` — keep `request_timeout` modest when `max_retries` is high for batch runs.
- **Streaming is mandatory above the SDK's output-size guard:** a non-streaming `messages.create()` whose *estimated* time exceeds ~10 min (driven by large `max_tokens`) **raises `ValueError` at call time** — this is a hard refusal, not a soft timeout. NARRATE (and any large-output call) must use `messages.stream()` + `.get_final_message()`. Concrete defaults: non-streaming ≤ ~16000; stream anything larger (e.g. ~64000).
- `typst_binary: str = "typst"`, `report_template: Path`.
- `max_workers` (thread-pool fan-out cap; default small, e.g. 4).

Nested config is grouped where it clarifies — a `ModelConfig { id, max_tokens, effort }` per stage in `config/models.py` — so a stage receives a typed `ModelConfig` rather than loose strings/ints. **`effort` is a real cost lever:** Sonnet 4.6 defaults to `effort="high"` (more latency/tokens); summarisation/narration should run at `effort="low"` or `"medium"` with thinking off, while the future eval LLM-judge runs at `effort="high"`. `Settings` is constructed once at the composition root (`cli/deps.py`) and injected downward; **core never imports `Settings`**, only the typed values it is handed (keeping `core/` pure and unit-testable with arbitrary config). A `.env.example` (no real keys) documents every variable.

**Config file → Settings UI (the tunables layer).** Beyond secrets (`.env`) and the typed `Settings`, the owner-tunable knobs — podcast `script_source` (`paper`|`summary`), host-persona text, `tone_presets`, the mix constants, default host/author voices, episode-length targets — live in a non-secret **config file** (`config/downlow.toml`) loaded via pydantic-settings, providing the **initial values**. Later these graduate to a DB-backed `Setting` registry (the tipping-tools `SystemSetting` pattern: key/value, read-through cache, write-through) seeded from the config file and surfaced in a **Settings tab** in the UI — the config file stays the fallback/defaults. A knob's lifecycle: config default → DB override → UI control, no code change. See `docs/podcast_design.md` §7.

**On-disk artifact layout** under a configurable `DATA_DIR` (structured data in SQLite, binaries on the filesystem per the locked decision):

```
$DATA_DIR/
├── downlow.db          # SQLite (→ Postgres later via DATABASE_URL)
├── sources/<paper_id>/source.pdf  # ingested source PDFs
├── reports/<paper_id>/<filename>.pdf   # Typst-rendered reports
├── audio/<paper_id>/<asset_id>.mp3     # stitched podcast mp3s
├── voices/samples/<voice_id>.<ext>     # uploaded clone samples (FUTURE)
└── cache/
    ├── extracted/<source_hash>.json    # ingest cache (replaces pdf_texts.json)
    ├── summaries/<cache_key>.json      # summarise cache
    └── narration/<cache_key>.json      # narration-script cache (pre-TTS)
```

The `ArtifactStore` adapter owns this layout and returns logical references stored in the DB — so the path scheme is an implementation detail behind a port, and a later move to object storage (multi-user) is an adapter swap, not a schema or core change. All paths are built with `pathlib`, fixing the Windows-backslash `\a`/`\d` bugs and the `os.rename` hack in the legacy code.

---

## Data Model

SQLModel `table=True` entities live in `adapters/db/tables.py`; the pure DTOs in `domain/schemas.py` are separate (DB rows ≠ wire/domain objects). **SQLite now, Postgres-ready:** use `int`/`str` (or UUID) ids, timezone-aware `datetime`, JSON columns via `sqlalchemy.JSON` / SQLModel `Field(sa_column=Column(JSON))` (works on both backends), and **explicit status enums** rather than VTTD's implicit "which nullable column is populated" convention. **Migrations via Alembic** — not VTTD's runtime auto-add-missing-columns hack, which silently diverges schema from code and can't express backfills or drops. Alembic gives reviewable, reversible, CI-checkable migrations from day one.

Status enums (`domain/enums.py`):

- `StageStatus = pending | running | succeeded | failed | skipped`
- `RunStatus = pending | running | succeeded | failed`
- `SpeakerRole = host | author`
- `VoiceSource = stock | cloned`

### Core entities (built and used this phase)

**User** — `id, username (unique), display_name, host_voice_id (FK→Voice, nullable), created_at`. No password/JWT this phase (single-user); the columns exist so multi-user + auth slot in without a foreign-key migration. Owns profiles, papers, voices.

**ResearchProfile** — replaces `data/research_data.json`. `id, user_id (FK, unique per user), research_field, research_topic, research_interests (JSON list[str]), research_focus, created_at, updated_at`. One active profile per user steers summarisation. *Why:* unifies the config-vs-data overlap the journal wants moved into the DB.

**OutputProfile** (≙ DocumentContext) — replaces `data/document_data.json`. `id, user_id (FK), name, document_type, return_details (JSON list[str]), created_at`. Drives what the summary should surface. Kept separate from `ResearchProfile` because document-shape and researcher-identity vary independently (one researcher, many output formats).

**Paper** (≙ VTTD `Story`) — `id, user_id (FK), title, source_pdf_ref, source_hash (for dedupe/cache), extracted_text_ref, page_count, authors (JSON), doi (nullable), author_voice_id (FK→Voice, nullable), chosen_profile_id, created_at, updated_at`. Per-stage lifecycle is **not** inferred from nullable columns — it lives on `PipelineRun`/`StageRun` (below), so `failed` is distinguishable from `not-yet-run`.

**Summary** (≙ `PaperSummary` DTO) — `id, paper_id (FK), overall_summary, key_findings (JSON), contributions (JSON), gaps_and_limitations (JSON), relevance_to_profile, methods, model_id, prompt_version, content_hash, profile_hash, created_at`. Structured fields (not one text blob) so Render/Narrate consume typed data and the report template is data-driven. `model_id` + `prompt_version` make regeneration and cache invalidation explicit.

**ReportAsset** — `id, paper_id (FK) | run_id, pdf_ref, filename, template_version, created_at`. The Typst output. A separate table because one paper may have several report renders over time (different templates/summaries).

**Episode** (multi-paper-ready) — `id, user_id (FK), title, status, created_at`. An episode owns the podcast script + audio and references **1..N papers** via **EpisodePaper** (`episode_id, paper_id, order`). Single-paper ships now (one `EpisodePaper` row); themed multi-paper episodes become a population change, not a schema rewrite (see `docs/podcast_design.md` §8).

**PodcastAsset** (≙ VTTD audio fields) — `id, episode_id (FK), mp3_ref, narration_script (JSON: the ordered multi-speaker `Turn[]` + per-turn music/SFX cues), host_voice_id (FK→Voice), model_id, duration_seconds (nullable), created_at`. The host voice is one consistent stock voice now; each author voice is per-paper (`Paper.author_voice_id`), so a multi-paper episode resolves multiple author voices. *Why store the script:* it is the regenerable, inspectable source of the mp3 and the per-turn transcript.

**PipelineRun** (the Job abstraction) — `id, paper_id (FK), status (RunStatus), requested_stages (JSON list[str]), created_at, started_at, finished_at, error`. One row per processing invocation.

**StageRun** — `id, run_id (FK), stage_name, status (StageStatus), cache_hit (bool), model_id (nullable), output_ref (nullable), error, started_at, finished_at`. Per-stage status enables retry-from-failure and, later, a worker claiming/advancing individual stages. *Why a child table not columns-on-Paper:* keeps history, supports re-processing, and is the async-later boundary.

### Voice entities (built + used now: stock host + author voices; only cloning/consent fields are FUTURE-populated)

**Voice** (voice pool; ≙ VTTD `voice_pool`) — `id, user_id (FK, nullable for shared stock voices), provider (e.g. "elevenlabs"), provider_voice_id, source (VoiceSource: stock|cloned), display_name, role_hint (SpeakerRole, nullable), sample_recording_ref (nullable; the template-script reading, FUTURE), consent_granted (bool, default False, FUTURE), consent_owner (str, nullable, FUTURE), consent_recorded_at (nullable, FUTURE), created_at`. This single table holds both stock voices (used now for the host and author roles) and cloned author voices (FUTURE). *Why one table:* a cloned voice is just a `Voice` with `source=cloned` + populated sample/consent fields — no parallel hierarchy.

**Host voice** — modelled as the user's one designated `Voice` (the consistent interviewer) via `User.host_voice_id` (default) and referenced from `PodcastAsset.host_voice_id`, so every episode uses the **same** host. This phase: a single stock voice. *Why a pointer not a flag:* "the host" is a selection over the voice pool, swappable without a schema change.

**Per-Paper author voice** — `Paper.author_voice_id` (FK→Voice, nullable). Populated now with a default stock author voice and read by the two-presenter NARRATE stage; voice-clone onboarding later overwrites it with the author's cloned voice.

### Library entities — FUTURE / scaffold only (defined, not wired this phase)

Marked clearly as scaffold; tables may be created by Alembic but no service touches them yet. Adapted from VTTD:

- **PlaybackState** (FUTURE) — `user_id + paper_id (unique together), position_seconds, updated_at`. Spotify-style resume. Zero cost to reserve, and central to the "Spotify for papers" vision.
- **View / RecentlyViewed** (FUTURE) — `id, user_id, paper_id, viewed_at, hidden (bool)`. Recently-viewed + hide.
- **Folder + FolderMembership** (FUTURE) — `Folder {id, user_id, name}` and `FolderMembership {folder_id, paper_id}`. User-created organisation.

Auth (JWT/bcrypt, rate limiting) and these library tables are explicitly **out of scope this phase** — reserved so the later FastAPI layer adds routers, not migrations-of-everything.

---

## The Rebuilt Pipeline

```
  ┌─────────┐   ┌───────────┐   ┌────────┐   ┌─────────┐   ┌───────┐
  │ INGEST  │──▶│ SUMMARISE │──▶│ RENDER │──▶│ NARRATE │──▶│ STORE │
  │ (PDF→   │   │ (Claude → │   │(struct │   │(Claude  │   │(DB +  │
  │  text + │   │ structured│   │ → .typ │   │ script →│   │ FS    │
  │  hash)  │   │ summary)  │   │ → PDF) │   │ TTS→mp3)│   │ refs) │
  └─────────┘   └───────────┘   └────────┘   └─────────┘   └───────┘
       │              │              │             │            │
   content_hash   (hash,profile,  deterministic  script_hash  Paper row +
   caches text    model,prompt_v) Typst template  caches mp3  artifact paths
```

`RENDER` and `NARRATE` both consume the `PaperSummary` and are independent (parallelisable). The whole pipeline is callable as `core.pipeline.run_paper(paper_id, *, force_stages=...)` so the future FastAPI layer drives it unchanged. The orchestrator is **sync** (`def`, not `async def`) this phase — see Concurrency & Performance for why and where the async seam lives. A failure in stage N leaves stages < N intact, so the run resumes from the failed stage (VTTD's retry-from-failed-stage pattern).

### Stage 1 — INGEST (PDF → text + content hash)

**Port:** `PdfExtractor.extract(pdf_ref) -> ExtractedText`.
**Input:** a `Paper` with a source-PDF reference.
**Output:** `ExtractedText { paper_id, full_text, pages, page_count, is_scanned, content_hash }`; persisted, source hash stored on `Paper`.

- **Two hashes, two jobs (resolves the chicken-and-egg):** the **extraction cache** is keyed by `source_hash = sha256(pdf_bytes)` — available *before* extraction, so a re-added identical PDF skips re-extraction; everything **downstream** is keyed by `content_hash = sha256(normalised_text)` — only available *after* extraction. A small **text-normalisation step** (de-hyphenate line-wraps, join across page breaks, collapse whitespace, strip PDF artefacts) runs **before** `content_hash` so the hash is stable across cosmetically-different extractions of the same paper. This **replaces the legacy `pdf_texts.json` blob**; if `content_hash` already exists, skip straight to whatever downstream stages are already cached.
- **This phase keeps `pdfplumber`** for parity with the legacy behaviour, behind the `PdfExtractor` port. **Library recommendation to surface (open question):** PyMuPDF (`fitz`) is ~5–20× faster, has best reading-order text via `page.get_text("blocks")`, and can render page images (needed later for the in-app PDF reader) — but it is **AGPL-3.0**. For a single-user local-network tool that is fine; if "open to others" ever means distributing/SaaS, either buy the commercial licence or fall back to **pypdfium2** (Apache/BSD, nearly as fast). The port makes swapping a one-class change; record the AGPL decision in `CLAUDE.md`. **Note (native-PDF default):** with SUMMARISE sending the PDF to Claude directly (see Stage 2), extraction is no longer the *summariser's* default input — INGEST still runs to compute `source_hash` + `ExtractedText` for dedupe/caching, the future in-app reader and search, and as the provider-agnostic fallback summarise path.
- **Scanned/empty handling:** after extraction, if the text is mostly empty (e.g. `len(full_text.strip()) < 0.1 × N_chars_per_page × page_count`), set `is_scanned=True` and raise a typed `EmptyExtractionError` / flag the paper `needs_ocr` rather than feeding garbage to Claude. **OCR is out of scope this phase** (note it as a future INGEST sub-stage: PyMuPDF page render → Tesseract/`ocrmypdf`). Never silently truncate; never pass empty text to SUMMARISE.

### Stage 2 — SUMMARISE (Claude → structured summary)

**Port:** `LLMClient` (one method, e.g. `complete_structured(*, system, user, schema, max_tokens) -> validated model`). `AnthropicLLMClient` is the default backend; `FakeLLMClient` (canned/recorded JSON) is what every test uses.
**Input:** the **source PDF (sent to Claude natively, the default)** or `ExtractedText` (the alt/fallback path) + the resolved `ResearchProfile` + the `OutputProfile`.
**Output:** a validated `PaperSummary`:

```python
class KeyFinding(BaseModel):
    statement: str
    evidence: str | None = None          # supporting detail / metric from the paper

class PaperSummary(BaseModel):
    title: str                           # paper's actual title (model-extracted)
    overall_summary: str                 # ~300 words, prose
    key_findings: list[KeyFinding]
    contributions: list[str]
    gaps_and_limitations: list[str]
    relevance_to_profile: str            # WHY this matters to THIS researcher
    # provenance (set by the pipeline, not the model):
    content_hash: str
    profile_hash: str
    model: str
    prompt_version: str
```

**Claude integration — mirrors VTTD's `script_adapter` pattern (confirmed against the claude-api skill):**

0. **Input mode (default = native PDF).** Claude reads the source PDF directly — a base64 `document` content block (or the Files API for large / over-~100-page PDFs) — because it handles figures, tables, and awkward layouts better than local extraction. The `LLMClient` accepts either a PDF document block (default) or text; the extracted-text path is the provider-agnostic fallback. *(Native-PDF specifics — exact page/size limits, Files API usage, and whether `document` blocks are prompt-cacheable — to be confirmed against the `claude-api` skill at build time.)*

1. **Models & params.** Default summariser **`claude-sonnet-4-6`** ($3 / $15 per MTok, 1M context, 64K max output) — the cost/speed sweet spot. Hardest-reasoning escalation **`claude-opus-4-8`** ($5 / $25 per MTok, 1M context, 128K max output). Pin **bare model-ID strings, no date suffix** (`claude-sonnet-4-6`, not `…-20251114`); make the model a config field so the owner can flip it without code changes. *Pricing above is current as of the skill cache (2026-06); treat as to-confirm and do not hard-code dollar values into business logic.* These are 4.6/4.8-family models: **adaptive thinking only** (`thinking={"type":"adaptive"}` + `output_config={"effort":...}`) — never `budget_tokens` (returns 400). For straightforward summarisation, thinking-off (omit the param) is fine and cheaper. **Caveat on Opus 4.8 escalation:** with thinking omitted, Opus 4.8 can leak reasoning into the visible output, which would corrupt the prose fields (`overall_summary`) even though the structured-output path protects the JSON; when escalating to Opus, either set `thinking={"type":"adaptive"}` or add a final-answer-only instruction.
2. **Structured/JSON output + validation.** Use the SDK's native structured outputs — `client.messages.parse(model=…, output_format=PaperSummary, …)` → `response.parsed_output` is a validated `PaperSummary` (equivalent lower-level form: `output_config={"format":{"type":"json_schema","schema":…}}`). Supported on both default models. **API caveat:** `output_format=` is the `messages.parse()` *helper* kwarg only; on raw `messages.create()` the field is `output_config.format` — the bare top-level `output_format` on `create()` is deprecated and will misbehave. This replaces VTTD's manual "strip markdown fences → `json.loads` → validate" dance — but **keep VTTD's truncation guard:** check `response.stop_reason == "max_tokens"` and raise `TruncatedResponseError` (the schema can't save you from a cut-off response).
3. **System prompt strategy.** A stable, versioned `SYSTEM_PROMPT` constant demanding the exact `PaperSummary` shape and the analytical stance ("you are summarising for an active researcher; surface findings, contributions, and gaps; `relevance_to_profile` must connect the paper to the researcher's stated focus"). The per-user steering and the `OutputProfile` go in the **user** turn or a cacheable system block — **not** interpolated into the frozen system prefix (keeps the prompt cache valid). Bump `prompt_version` whenever the system prompt or schema changes — it is part of the cache key.
4. **Long-PDF strategy (VTTD's section-split, verbatim).** Sonnet 4.6 has 1M context, so most papers fit in one call — **do the single-call path first.** For papers over a configured input budget (**measured with `client.messages.count_tokens(model=…)` — never `len()` or tiktoken, which are wrong for Claude; the budget is model-specific, so it recomputes if the model flips Sonnet↔Opus**): split on paragraph/section boundaries into ordered sections, process **sequentially carrying forward context** (a running summary + title/abstract) so later sections stay consistent, then merge via a final reduce call. Truncated sections (`stop_reason == "max_tokens"`) are **recursively split in half and re-queued** via a work queue with an iteration cap. Build this machinery now even though it rarely fires — NARRATE reuses it.
5. **Caching (two layers).** *App-level result cache* keyed by `(input_hash, profile_hash, model, prompt_version)` — where `input_hash` is the PDF's `source_hash` on the native path (or the text `content_hash` on the fallback path) — same paper + profile + model + prompt ⇒ stored `PaperSummary`, zero API calls (an `overwrite`/`force` flag bypasses it, preserving the old script's overwrite behaviour). *Anthropic prompt caching* for the within-run shared prefix: put the frozen `SYSTEM_PROMPT` + schema before the volatile per-paper text with `cache_control={"type":"ephemeral"}`; verify via `usage.cache_read_input_tokens`. **Gotcha:** caching *silently no-ops* below the minimum cacheable prefix — **2048 tokens for Sonnet 4.6** (4096 for Opus 4.8); a frozen summary prompt + schema may fall under that, so a test must assert `usage.cache_read_input_tokens > 0` on the second call (zero ⇒ the prefix is too short to cache, the usual cause).

### Stage 3 — RENDER (structured summary → report PDF via Typst)

**Port:** `ReportRenderer.render(summaries, meta) -> bytes`.
**Input:** one or more `PaperSummary` objects (the legacy "merge all summaries into one doc" behaviour) + an auto-generated `title`/`filename`.
**Output:** a compiled report PDF on the FS + a `ReportAsset` row.

**Feed the structured summary into a deterministic Typst template — do NOT ask the LLM to emit Typst markup.** The old `LaTeXConverter` had the LLM author LaTeX, the source of half the fragility (escaping, unbalanced braces, hallucinated packages, non-reproducible output). Instead:

- Ship a versioned `typst/report.typ`. Serialise the `list[PaperSummary]` to JSON next to the template; the template does `#let data = json("summaries.json")` and loops — a contents page (`#outline()`), one section per paper (`#heading`), sub-sections for Summary / Key Findings / Contributions / Gaps. Identical input ⇒ byte-identical PDF, fully unit-testable, trivially restyleable. (The trade-off is less freeform layout creativity, which is exactly what you want for a report; LLM-emits-Typst is rejected for the report path — it reintroduces validation/retry/escaping burden and non-determinism. Because the JSON is loaded *as data*, Typst handles escaping of arbitrary user strings.)
- **Title/filename generation:** recommend a **templated default, optional LLM override behind a flag** (a tiny `complete_structured` returning `{title, slug}` if the owner wants auto-titles). Slugify deterministically; never let the model pick the on-disk filename directly (path-safety).
- **Compilation: shell out to the `typst` binary via `subprocess`** — the canonical, self-contained, pinned-version artifact, trivially installed in CI/Docker: `subprocess.run(["typst","compile","report.typ","out.pdf"], check=True, capture_output=True)`. Fully in-process and deterministic — **no `sleep(20)`, no external Overleaf/latexmk watcher.** Render the data file + template into a temp dir (the scratchpad), compile, move the PDF to the artifact store. On non-zero exit, raise `TypstCompileError` with captured stderr (real error handling, unlike the old "rename and hope"). Pin the Typst version in `pyproject`/CI and record it in `CLAUDE.md`. (If the owner later wants zero external binaries, the `typst` Python package — bundled compiler — is the fallback behind the same port.)
- **Caching:** optional — compilation is sub-second; key on `hash(sorted(summary.content_hash) + template_version + title)` if you want to skip recompiles.

### Stage 4 — NARRATE (summary → script → mp3)

The centrepiece. The **two-presenter (host + author) interview ships this phase** — whole-paper → Claude interview script → per-turn TTS (distinct stock voices) → **full VTTD-style mix** (intro/outro music, optional SFX, crossfades, loudness-normalised) → one mp3. Default script input is the **whole paper** (the summary is a configurable, cheaper alternative). Only author voice *cloning* is deferred (Phase 7). **Full design — host persona, craft principles, the mixer rip, config strategy, and the multi-paper-ready Episode model — lives in `docs/podcast_design.md`.**

**Multi-speaker narration-script schema (built now; generalises VTTD's character+dialogue+tone model):**

```python
Role = Literal["host", "author"]

class Turn(BaseModel):
    role: Role
    text: str
    tone: str | None = None              # delivery direction, e.g. "curious", "emphatic"

class VoiceRef(BaseModel):
    role: Role
    voice_id: str                        # FK into the Voice pool

class NarrationScript(BaseModel):
    paper_content_hash: str
    turns: list[Turn]                    # ordered host↔author interview
    voices: list[VoiceRef]               # role → voice mapping
    model: str
    prompt_version: str
```

- **Step 4a (Claude script generation):** via the same `complete_structured` port + truncation guard + section-split-for-long-input machinery as SUMMARISE. **This phase: generate the two-presenter host↔author interview script** (host asks, author answers in-character, host follows up), in the `turns` schema, generated by default from the **WHOLE PAPER** (the summary is a configurable, cheaper alternative — re-feeding the summary loses signal). A versioned interview `SYSTEM_PROMPT` encodes the everyperson-host persona + the podcast craft principles (see `docs/podcast_design.md`) and governs tone, depth-asymmetry, and turn-taking. Default model `claude-sonnet-4-6`; scripts can be long, so when `max_tokens` is large, **stream** (`client.messages.stream(...).get_final_message()`).
- **Step 4b (TTS + mix):** **Ports** `TTSClient.synthesize(*, text, voice, model) -> bytes` and `AudioMixer.mix(segments) -> bytes`; `ElevenLabsTTSClient` + a `pydub`-based mixer are the defaults, `FakeTTSClient`/`FakeMixer` (deterministic dummy mp3) for tests. **Modernise the raw `requests` POST → the official `elevenlabs` Python SDK** (typed, streaming/retries, and the voice-cloning API for later). **This phase = two stock voices:** map `host` and `author` turns to two distinct stock ElevenLabs voices, synth each turn, then **concatenate/mix the per-turn segments into one mp3** with inter-turn gaps and level normalisation (VTTD's `audio_mixer` pattern via `pydub` + ffmpeg). Cross-fades/music/SFX are later polish. Stream the final mp3 to the library audio path.
- **Output:** a `PodcastAsset` (mp3 ref, the `NarrationScript` JSON, voices used, model id). **Cache audio** by `(script_hash, voice_id, tts_model)` — re-narrating the same script with the same voice returns the cached mp3.

**Clearly marked FUTURE (zero-rework — the schema/ports above already support them):**

- **Voice-clone onboarding:** researcher reads the template script → upload sample → `ElevenLabsTTSClient.clone(sample) -> Voice(source="cloned")` → assign as a Paper's author voice (a different SDK call behind the same `TTSClient` port).
- Mix polish: cross-fades, intro/outro, music beds and SFX (the basic concatenate-with-gaps mixer ships now; richer `audio_mixer` polish later).
- The journal's per-section-with-neighbour-context generation (reuse SUMMARISE's section-split machinery).
- Host-voice selection/preview UI; consent/permissions management for cloned voices.

### Stage 5 — STORE / DELIVER

**Ports:** `Repository` + `ArtifactStore`. Persists all artifact references and flips the `PipelineRun` to `succeeded`. Structured data → SQLite via SQLModel (`Paper`, `Summary`, `ReportAsset`, `PodcastAsset`, `Voice`, plus provenance/hash columns); binaries (source PDF, report PDF, mp3) → filesystem, with **paths/hashes recorded in the DB** (never blobs in the DB). This is the unification the journal wanted (kills `pdf_texts.json` / `research_data.json` / `document_data.json` / the implicit `users/` tree). "Deliver" is a no-op CLI print this phase; the seam (artifact refs in the DB, served later by FastAPI `audio`/`player`/`stories`-equivalent routers) is reserved in `api/`.

### Concurrency & Performance

**Where the parallelism is:** INGEST and SUMMARISE are embarrassingly parallel per-PDF (each paper is independent until RENDER aggregates them); NARRATE is per-paper-parallel again. This is exactly the parallelisation the journal asked for.

**Recommendation: sync-first now, with a clean async/worker seam.** The owner is single-user/local — do not introduce `asyncio`, Celery, or a task queue this phase. Instead:

- Implement each stage as a plain sync function. Run the per-PDF fan-out with `concurrent.futures.ThreadPoolExecutor` (LLM/TTS/extraction are I/O- or subprocess-bound, so threads give real speedup without async colouring). `max_workers` is config (default ~4).
- Keep the orchestrator's public surface a single `run_paper(...)` / `run_batch(papers, *, max_workers)`, so swapping `ThreadPoolExecutor` for `asyncio.gather`/Celery later is a one-function change. *Note for the owner:* the official SDK has a first-class `AsyncAnthropic` — if/when the API layer wants async, the port grows an `acomplete_structured` and the backend uses `AsyncAnthropic`; no caller changes.
- The content-hash result caches make re-runs cheap — the bigger single-user win than raw parallelism.

**Rate-limit / backoff:** Claude — the SDK auto-retries 408/409/429/5xx with exponential backoff (bump `max_retries` for batch runs; honour `retry-after` on `RateLimitError`); cap `max_workers` so per-minute token limits aren't blown; prompt-cache the shared prefix. ElevenLabs — wrap synth in small exponential backoff (respect `Retry-After`) and use a **smaller** `max_workers` for NARRATE (ElevenLabs concurrency is plan-limited).

### Evaluation & Quality

- **Golden-file / snapshot tests with `FakeLLMClient`.** The ports mean the entire pipeline runs in tests with no network and no API key. Record one real Claude `PaperSummary` JSON per fixture paper, feed it through `FakeLLMClient`, and snapshot the validated `PaperSummary`, the generated Typst data JSON + `.typ`, and (with `FakeTTSClient`) the NARRATE turn→voice mapping. Catches template regressions, schema drift, and stitching bugs deterministically and for free.
- **Schema validation is a quality gate.** Malformed output fails loudly at parse time, not silently downstream. Assert invariants: non-empty `overall_summary`, ≥1 `key_finding`, `overall_summary` word-count within a band of ~300.
- **Prompt-version tracking.** `prompt_version` is a first-class constant, stamped into every `PaperSummary`/`NarrationScript` and part of the cache key; bumping it invalidates the result cache and is the unit of "did the prompt change." Prompts live in `core/prompts/` as versioned constants so a `git blame`/diff shows exactly what changed.
- **Small eval harness (scaffold now, build later).** Reserve `core/eval/` — a tiny harness that runs a fixed set of papers through the **real** `AnthropicLLMClient` at a chosen `prompt_version` and scores cheaply: rubric checks (does `relevance_to_profile` mention `research_focus`?), structural checks (counts/lengths), and an optional **LLM-as-judge** pass (a `claude-opus-4-8` call scoring faithfulness 1–5 against the extracted text). Gate behind a marker so it doesn't run in normal CI (costs tokens). Don't build the judge this phase — just reserve the directory and the `prompt_version` plumbing.

---

## Product & UX Vision

The whole UI is **future scope**; this section defines the target experience so the `core` package and data model laid down now expose the right seams. VTTD already proves every primitive works, so this is adaptation, not invention.

### The shape of the product

- **Library home** — the landing surface: a grid/list of papers (cover = first PDF page thumbnail or generated art), with a **recently viewed / recently played** rail ("jump back in"), user-created **folders / collections** ("Lit review: OOD generalisation", "To read"), **status badges** per paper (_summarising… / rendering… / narrating… / ready_, derived from which artifacts exist), and filter/sort by profile, folder, date added, "has audio".
- **Paper detail view** — the heart of the app: three panes over the same paper — (1) **in-app PDF reader** (read the original without leaving the app), (2) **text summary** (the LLM summary, with future inline regenerate/edit/section anchors), (3) **audio player** for the two-presenter interview, with a transcript view (the interview script) and future per-turn highlighting (the script is already a structured turn list, so turn-level sync is cheap to add).
- **Persistent mini-player** — survives navigation across the whole app (VTTD's defining feature: a client-side router keeps audio playing as you move between library and detail), with resume-from-position per paper (VTTD's `PlaybackState`). Nothing about it constrains `core`, which only needs to produce a stable `audio_ref` + a queryable position store later.
- **Ingest / submit flow** — add a PDF (drag-and-drop/upload) or point at a folder; pick/confirm the research profile that steers the summary (recorded on the paper so re-runs are reproducible); watch pipeline progress through the stages (extract → summarise → render → narrate) with a per-stage strip and retry-a-failed-stage without redoing the expensive earlier ones.
- **Settings / profiles area** — manage one or more research profiles, plus app prefs; future: pick/preview the host voice, manage cloned author voices and their consent records, set audio quality presets.

### The audio is a two-presenter interview

Frame the library/player experience around the fact that the audio is a **conversation**: a consistent host interviews the paper's (variable-voice) author, back and forth. The UI shows two speakers; the transcript is a chat-like back-and-forth; the library can market a paper as "an interview with the authors of X."

### (FUTURE) Voice-clone onboarding journey

The killer feature. A real researcher puts their own voice on their paper's podcast as the "author": from a paper (or invite link) they open **"Add your voice,"** are shown a **standard template script** and **record themselves reading it** (in-browser capture or upload), give **explicit, recorded consent**, the sample is sent to **ElevenLabs voice cloning** → a custom author voice is created and **assigned to their paper(s)** → regenerating the podcast uses it. Later: re-record, host-voice selection/preview, revoke consent (which retires the cloned voice). A direct generalisation of VTTD's `voice_pool` + per-character `voice_id`. **None of the cloning UI ships this phase** — but the data model and the Voice/TTS port support it from day one.

### Core user journeys

- **Add a paper → get a summary + podcast:** add PDF → confirm profile → pipeline runs → paper appears "ready" → open detail → read summary / read PDF / play interview.
- **Browse and resume:** open library → "Jump back in" rail → tap a half-listened paper → mini-player resumes at saved position → keep listening while browsing.
- **Organise:** select papers → add to a collection → filter library by it.
- **Read while listening:** open detail → start the interview → switch to the PDF tab → audio keeps playing via the persistent mini-player → glance at the transcript for a quoted finding.
- **Retry a failed stage:** paper shows "narrate failed" → open detail → retry narrate (summary + report already cached) → podcast completes.
- **(FUTURE) Clone my voice:** read template → record → consent → ElevenLabs clone created → assigned as author voice → regenerate → it's now in their voice.

---

## Feature Backlog (Near / Mid / Long term)

Reconciles the owner's `app_planning.md`/`progress_journal.md` trajectory with VTTD's proven feature set. **"Rebuild now"** = an existing feature (F1–F5) rebuilt at expert quality this phase. **"Scaffold now"** = no UI/endpoint this phase, but the `core` data model / port must accommodate it so it slots in later without rework. Everything else is genuinely later.

### This phase (rebuild the existing features only)

| ID | Feature | Build now? | Rationale |
|----|---------|-----------|-----------|
| F1 | PDF text extraction | Rebuild now | Stage 1 of the pipeline; foundation for everything. |
| F2 | Research-context-steered summarisation (Claude `claude-sonnet-4-6`) | Rebuild now | Core value; switch OpenAI→Claude, mirror VTTD's strict structured-output pattern. |
| F3 | Compiled summary report PDF (Typst, auto title/filename) | Rebuild now | Replaces the LaTeX/Overleaf/`sleep(20)` hack with a reproducible Typst build. |
| F4 | Two-presenter interview podcast (ElevenLabs) | Rebuild + extend now | Ships the host+author interview: Claude script → per-turn TTS (2 stock voices) → `pydub`-mixed mp3. Only author voice *cloning* is deferred. |
| F5 | PDF-filename-from-first-line heuristic | Rebuild now | Existing utility; keep as a `core` helper / CLI subcommand. |

### Foundations to scaffold now (data model / ports only — no UI)

| Area | Scaffold now | Rationale |
|------|-------------|-----------|
| Multi-speaker narration script schema | Yes | Ordered list of **turns** (`role: host\|author`, `text`, `tone`); drives the two-presenter podcast this phase. |
| Voice abstraction / port | Yes | `Voice` entity (`id, provider, provider_voice_id, source: stock\|cloned, owner, consent, sample path`); host-voice config + per-Paper author-voice ref. TTS via a port so cloning is an adapter capability later. |
| Research profiles in DB | Yes | Unify `research_data.json` + `users/` tree into DB-backed profiles. The journal explicitly wants this. |
| Paper / artifact data model | Yes | `Paper` + `Summary`/`ReportAsset`/`PodcastAsset` (adapt VTTD's `Story`); lifecycle on `PipelineRun`/`StageRun`. |
| Pipeline stage seams + content-hash caching | Yes | Typed I/O per stage, retry-from-failed-stage, expensive outputs cached by hash. `core` callable unchanged by future `api/`. |
| `api/` + `frontend/` directory seams | Yes (dirs only) | `core` written so the future FastAPI layer calls it unchanged. No endpoints built. |
| Eval harness directory + `prompt_version` plumbing | Yes (dir only) | `core/eval/` reserved; the version stamp already flows. |
| Playback-state model shape | Defer (note it) | `PlaybackState(user + paper, position_seconds)` is a later table; design `Paper` so it can be FK'd. |

### Near term (owner: summaries + audio) — first features after this phase

| Feature | Rationale |
|---------|-----------|
| FastAPI `api/` over `core` | Expose the rebuilt pipeline; precondition for any UI. |
| Library home + paper detail (PDF + summary + player) | The minimum viable "Spotify" surface. |
| Persistent mini-player + resume-playback | VTTD's defining UX; needs the playback-state table. |
| Ingest/submit flow with live pipeline progress | Turns the CLI pipeline into a product action. |
| Podcast transcript view + per-turn highlighting in the player | The interview is already structured turns (the podcast itself ships in the foundation phase); the player surfaces them. |
| In-app PDF reader | Read source without leaving the app. |

### Mid term (owner: profiles, dashboard, search, feedback + VTTD-proven extras)

| Feature | Rationale |
|---------|-----------|
| Research-profile management UI (multi-profile) | Owner's mid-term; profiles already DB-backed. |
| Folders / collections + recently-viewed | VTTD-proven organisation; high value, low cost on existing models. |
| Search across library (title, summary, transcript) | Owner's mid-term; transcript search is a natural fit given structured scripts. |
| Dashboard | Overview of library + pipeline status. |
| Summary / script editing | VTTD-proven; correct/tune before re-rendering or re-narrating. |
| Feedback capture | Owner's mid-term; thumbs/notes per paper to improve steering. |
| Voice-clone onboarding + consent management | The killer feature; unlocked by the Voice model + consent metadata scaffolded now. |
| Host-voice selection / preview | VTTD voice-pool pattern; small once the Voice abstraction exists. |
| Audio quality presets | VTTD-proven; presets over the TTS/mix ports. |

### Long term (owner: Zotero, visualisation + polish)

| Feature | Rationale |
|---------|-----------|
| Zotero integration (import library) | Owner's long-term; an ingest adapter feeding the same pipeline. |
| Visualisation (concept maps, trends across library) | Analytics over the corpus. |
| Music / SFX / cross-fades in podcasts | VTTD `audio_mixer` polish on the narrate stage. |
| Per-section podcast generation referencing neighbours | The journal wants richer podcasts; the turn schema + caching already accommodate it. |
| Multi-user / auth | Owner's "possible later"; VTTD's `User` + JWT pattern available when needed. |
| Parallelised reading/summarisation/narration | A `core` performance pass once correctness is solid. |

---

## Phased Roadmap

Legend: `[ ]` todo · `[~]` partial · `[x]` done. Sub-IDs follow VTTD's `N.Ma` style.

> **Phase numbering note:** Phase 0 and Phase 1 *together* are "this phase." Phase 0 is pure scaffolding (no behaviour); Phase 1 is the feature rebuild on that scaffold. Everything from Phase 2 onward is planned/scaffolded only.

### Phase 0 — Foundations & Scaffolding *(THIS PHASE, part 1)*

**Objective:** Stand up the package, environment, tooling, culture, and directory seams so the rebuild has somewhere clean to land. No feature behaviour yet.

- [ ] **0.1a** Initialise uv environment + `pyproject.toml` (hatchling, `packages = ["src/downlow"]`, py311 target).
- [ ] **0.1b** Pin core deps: `anthropic`, `sqlmodel`, `alembic`, `pydantic`, `pydantic-settings`, `pdfplumber`, `elevenlabs`, `pydub` (+ system `ffmpeg`), `typer`, `httpx`; dev extras: `pytest`, `pytest-cov`, `ruff`, `mypy`, `pre-commit`.
- [ ] **0.2a** Create the package skeleton: `domain/`, `core/` (stages, prompts, services, eval seam), `adapters/`, `cli/`, with `api/` + `frontend/` as documented future seams (READMEs explaining intent, no code).
- [ ] **0.3a** ruff config (line-length 120, py311, select `E,W,F,I,N,UP,B,SIM,T20,RUF`, ignore `E501,N815,RUF012`, isort first-party = `downlow`) — adapted from `tipping-tools`.
- [ ] **0.3b** mypy strict config (scoped `ignore_missing_imports` for `pdfplumber`/`typst`/`elevenlabs`, not a blanket flag).
- [ ] **0.3c** pytest + pytest-cov with a `fail_under` gate (start 60, ratchet up); `conftest.py` fixtures (tmp data dir, in-memory `db_session`, `fake_llm`, `fake_tts`, `sample_pdf`, `settings` override).
- [ ] **0.4a** CI workflow (`.github/workflows/ci.yml`): jobs `lint` (ruff check + format --check), `typecheck` (mypy), `test` (pytest --cov). (Trivy/`scan` deferred — no Docker image this phase; see Phase 9.)
- [ ] **0.4b** Versioned `.githooks/pre-commit` that ruff-format-fixes staged `.py`.
- [ ] **0.5a** Adapt `.claude/agents` from `tipping-tools`: keep backend-engineer, ml-engineer, systems-architect, modern-stack-advisor; **replace greyhound-racing-expert with a research-domain / academic-writing advisor.** Also adapt **`deeptech-brand-architect`** (from `/home/luke/Documents/GitHub/augur/.claude/agents/`) for the frontend aesthetic / visual design system — **retargeted from its Next.js default to our React 19 + Vite stack**, and reframed for an *app* (library + reader + player) as well as a future landing page (its "Scientific Diagrammatic" direction is a natural fit for a research-paper tool).
- [ ] **0.5b** Adapt `.claude/skills`: ask-for-help, future-fixes-to-issues, git-detective, issue-solver, pr-reviewer, workflow-optimizer.
- [ ] **0.6a** Author `CLAUDE.md` (base on `tipping-tools`; document the locked decisions, the port/adapter pattern, the pipeline stages, the no-new-features boundary, the PyMuPDF/AGPL note, the Typst-version pin).
- [ ] **0.6b** Commit this plan in the repo (`PROJECT_PLAN.md` / `docs/task_breakdown.md`).

**Dependencies:** none (greenfield); reference repos available locally.
**Definition of Done:** `uv sync` works; `uv run pytest` runs (even with 0 real tests); CI is green on a placeholder test; `.claude/` + `CLAUDE.md` present; layout reviewed against `tipping-tools` conventions.
**Sequencing:** first; most of 0.x can proceed in parallel after 0.1a/0.2a.

### Phase 1 — Rebuild Existing Features (F1–F5) in `core` + CLI *(THIS PHASE, part 2)*

**Objective:** Re-implement the entire existing pipeline at expert quality inside `core`, exposed through a thin CLI. Fix every known defect. Add nothing new feature-wise. Build on seams that make the podcast/voice vision additive.

*Cross-cutting ports & infra*
- [ ] **1.1a** Define ports as `Protocol`: `LLMClient`, `PdfExtractor`, `ReportRenderer`, `TTSClient`, `ArtifactStore`, `Repository[T]`, `Clock`.
- [ ] **1.1b** `AnthropicLLMClient` adapter: official `anthropic` SDK, `messages.parse` structured output, `stop_reason == "max_tokens"` → typed `TruncatedResponseError`, retries/backoff, model pinned via config (default `claude-sonnet-4-6`; `claude-opus-4-8` selectable; adaptive thinking, never `budget_tokens`). *Model IDs/pricing confirmed against the `claude-api` skill (sonnet-4-6 $3/$15; opus-4-8 $5/$25); pricing is to-confirm at release, not hard-asserted.*
- [ ] **1.1c** `pydantic-settings` config (API keys, model IDs, paths, concurrency, timeouts) — replaces hardcoded globals.
- [ ] **1.1d** Cross-platform path handling via `pathlib` throughout; **delete all `users\{user}\…` backslash strings.**
- [ ] **1.1e** Persistence wired **this phase** (locked decision: SQLite *now*): SQLModel `table=True` entities + `engine`/`get_session` + `SqlModelRepository[T]` behind the `Repository` port; **Alembic** initialised with the first migration; the SQLite file lives under `$DATA_DIR`. (Postgres-readiness + the legacy `users/` backfill are deferred to Phase 2.)

*F1 — PDF text extraction*
- [ ] **1.2a** `PdfExtractor` adapter (pdfplumber) behind the port; pure `extract(path) -> ExtractedText`.
- [ ] **1.2b** Content-hash cache layer (replaces `pdf_texts.json`): extraction cache keyed by `source_hash`, downstream caches by `content_hash`; artifact references recorded in the DB (1.1e).
- [ ] **1.2c** Graceful empty/scanned/garbled handling (`is_scanned` flag / `EmptyExtractionError`; never crash, never feed garbage to Claude).

*F2 — Context-steered summarisation*
- [ ] **1.3a** `ResearchProfile` + `OutputProfile` models (SQLModel-ready) and the `PaperSummary` schema with provenance.
- [ ] **1.3b** `build_context_prompt()` composition (faithful port of the existing steering prompt; frozen system prefix + volatile context in the user/cacheable block).
- [ ] **1.3c** `SummariseStage` / `Summariser` service: per-PDF, context-steered, via `LLMClient`; overwrite/force flag; content-hash result cache.
- [ ] **1.3d** Long-input section-split + carried-context + recursive-resplit machinery (single-call path first).
- [ ] **1.3e** Parallelise per-PDF summarisation (`ThreadPoolExecutor`, bounded `max_workers`).

*F3 — Compiled report PDF (LaTeX→Typst)*
- [ ] **1.4a** `RenderStage` / `ReportComposer`: assemble `list[PaperSummary]` → Typst data JSON (deterministic; no LLM markup).
- [ ] **1.4b** Title/filename: templated default + optional LLM override behind a flag; deterministic slugify.
- [ ] **1.4c** `TypstRenderer` adapter: subprocess to the pinned `typst` binary, in-process and deterministic; `TypstCompileError` on non-zero exit (**kills Overleaf watcher + `sleep(20)`**).
- [ ] **1.4d** Write the report PDF via `ArtifactStore`; record the `ReportAsset` row/metadata.

*F4 — Two-presenter interview podcast (host + author, per-turn TTS + mix)*
- [ ] **1.5a** Define the **multi-speaker `NarrationScript`** schema now (`Turn[]` with `role|text|tone`, `VoiceRef[]`).
- [ ] **1.5b** `NarrationScriptGenerator` (LLM) emitting that schema — **host↔author interview** this phase; versioned interview prompt; long-input section splitting; stream when `max_tokens` is large.
- [ ] **1.5c** `Voice`/voice-pool table **created** by Alembic (id, provider, provider_voice_id, source, owner + consent, sample path); **two stock voices seeded (a default host + a default author) and used by F4**. The clone/consent columns exist but stay unpopulated until Phase 7.
- [ ] **1.5d** `ElevenLabsTTSClient` adapter (official SDK) behind `TTSClient`; `NarrateStage`: per-turn TTS mapping host/author roles to two stock voices → streamed to the audio artifact path; cache by `(script_hash, voices, tts_model)`.
- [ ] **1.5e** Retry/streaming/error handling for ElevenLabs (respect `Retry-After`; smaller `max_workers`).
- [ ] **1.5f** `AudioMixer` port + `pydub`/ffmpeg adapter: concatenate the per-turn segments with inter-turn gaps and level normalisation into one mp3 (VTTD `audio_mixer` pattern); `FakeMixer` for unit tests.

*F5 — Filename-from-first-line heuristic*
- [ ] **1.6a** Port `update_pdf_filenames` to a pure, testable `FilenameHeuristic` (`suggest()` + `apply()` as separate, non-interactive steps).

*CLI & wiring*
- [ ] **1.7a** Thin CLI commands: `add`, `summarise`, `report`, `narrate`, `rename`, and `run` (full pipeline). CLI only orchestrates `core`; no business logic.
- [ ] **1.7b** Remove the mixed-concern `main()`; bootstrap the library (DB rows + artifact dirs) via a small `Library`/user-init helper (the journal's "user-creation class").

*Tests*
- [ ] **1.8a** Unit tests per service/adapter with all external APIs mocked (Anthropic, ElevenLabs), incl. a simulated `max_tokens` truncation case.
- [ ] **1.8b** Golden-file test for Typst render (deterministic `.typ`/JSON + extracted-text snapshot; no sleep, no external process).
- [ ] **1.8c** End-to-end CLI test on a fixture PDF with mocked LLM/TTS, asserting artifacts land on `tmp_path` and DB rows reach the expected state.
- [ ] **1.8d** Satisfy the Requirements Traceability table (every F has ≥1 covering test).
- [ ] **1.8e** Path-handling test asserting POSIX-safe `pathlib` construction (guards against the backslash regression).

**Dependencies:** Phase 0. Within Phase 1: ports/infra (1.1x) precede all feature work; F2 depends on F1; F3 depends on F2; F4 depends on F2 (needs summaries) + 1.5a schema; F5 is independent.
**Definition of Done:** DO1–DO7 met; CI green; `uv run dl run` achieves **functional parity on fresh inputs** — the same source PDFs produce equivalent-or-better summary/report/audio outputs and the expected SQLite rows (it does *not* reuse the old `pdf_texts.json`/`summaries/` cache files; importing Luke's existing `users/` tree is Phase 2); no `sleep`, no Overleaf, no OpenAI, no backslash paths; traceability table fully populated and passing.
**Sequencing:** ports first → F1 → F2 → (F3 ∥ F4) → F5 ∥ CLI → tests throughout.

### Phase 2 — Postgres-Readiness & Legacy Backfill

**Objective:** SQLite + SQLModel + Alembic are already live from Phase 1 (1.1e). This phase hardens persistence for the multi-user/hosted future and imports the legacy data.
- [ ] **2.1a** Postgres-readiness audit: no SQLite-only column types in the hot path; JSON columns + enums verified portable; a `DATABASE_URL` swap smoke-tested against a Postgres service.
- [ ] **2.2a** Migration hygiene: review/squash the Phase-1 Alembic baseline; add a CI check that models and migrations agree (autogenerate diff is empty).
- [ ] **2.3a** Backfill/import Luke's existing `legacy/users/` tree + the old `legacy/data/` JSON profiles into the DB.
- [ ] **2.4a** Add a `postgres` service to the CI `test` job; prove a green run against Postgres.

**Dependencies:** Phase 1 (DB live, `core` schemas stable). **DoD:** the same `core` runs unchanged against Postgres in a smoke test; legacy data imported; autogenerate diff clean. **Sequencing:** after Phase 1; precedes API.

### Phase 3 — FastAPI `api/` Layer (read-only first)

**Objective:** Expose `core` over HTTP without changing `core`.
- [ ] **3.1a** App factory + DI wiring (`core` services + `get_session`).
- [ ] **3.2a** Read endpoints: `GET /papers`, `/papers/{id}`, `/papers/{id}/summary`, `/papers/{id}/report.pdf`, `/papers/{id}/audio.mp3`.
- [ ] **3.3a** Write/trigger endpoints: `POST /papers` (ingest), `POST /papers/{id}/{summarise|report|narrate}`.
- [ ] **3.4a** Job/stage execution model (sync first; background-task seam noted).
- [ ] **3.5a** API tests (TestClient, mocked `core` boundaries).

**Dependencies:** Phase 2 — and proves DO2 (core callable unchanged). **DoD:** the whole Phase-1 pipeline is drivable via HTTP; `core` untouched; OpenAPI complete.

### Phase 4 — Frontend (OPEN QUESTION: React 19+Vite vs mirror-VTTD Jinja/JS-PWA)

**Objective:** LAN web UI — library, in-app PDF reader, summary reader, persistent audio player. Visual design system + aesthetic direction owned by the adapted **`deeptech-brand-architect`** agent (tokens, type/spacing scales, motion-as-explanation, restraint).
**Open question (surface to owner):** React 19 + Vite (owner's pick, heavier, decoupled, matches tipping-tools' `frontend-engineer` agent) vs. mirror-VTTD (Jinja2 + vanilla-JS PWA with a custom client-side router — the proven persistent-player pattern the owner already knows). **Recommendation: resolve via a short spike (4.0a) measuring persistent-player effort in each.** Either way the API (P3) stays frontend-agnostic, so the choice is reversible.
- [ ] **4.0a** Spike + decision (React vs Jinja/PWA) — *blocking.*
- [ ] **4.1a** Library/dashboard view.
- [ ] **4.2a** In-app PDF reader.
- [ ] **4.3a** Summary reader.
- [ ] **4.4a** Persistent audio player + client-side router (Spotify-like resume).

**Dependencies:** Phase 3. **DoD:** browse the library and read/listen on the LAN; audio persists across navigation.

### Phase 5 — Auth & Multi-User

**Objective:** Open beyond single-user safely.
- [ ] **5.1a** JWT auth (python-jose + bcrypt, per VTTD) + password hashing.
- [ ] **5.2a** Per-user scoping of all data (the G6 boundary becomes load-bearing).
- [ ] **5.3a** Rate limiting.

**Dependencies:** Phases 2–3. **DoD:** two users have isolated libraries; auth enforced on all endpoints.

### Phase 6 — Library Features (folders, recently-viewed, resume)

**Objective:** The "Spotify" organisation layer.
- [ ] **6.1a** Folders + membership.
- [ ] **6.2a** Recently-viewed + hide.
- [ ] **6.3a** Playback-position resume (`PlaybackState`).

**Dependencies:** Phases 4–5. **DoD:** resume-where-you-left-off works; user-organised library.

### Phase 7 — Voice Cloning & Audio Polish

**Objective:** Let a real researcher put their *own* voice on their paper's podcast as the author (the killer feature), and polish the mix. The two-presenter interview itself already shipped in Phase 1.
- [ ] **7.1a** Voice-clone onboarding: serve the template script → record/upload sample → ElevenLabs clone → store as a cloned `Voice` with **consent metadata.**
- [ ] **7.2a** Assign a cloned voice as a `Paper`'s author voice; regenerate the podcast in the author's own voice.
- [ ] **7.3a** Host-voice selection/preview UI (swap the default stock interviewer).
- [ ] **7.4a** Consent/permissions UI + storage; revocation (retire a cloned voice).
- [ ] **7.5a** Mix polish: cross-fades, intro/outro, optional music beds + SFX (extends the Phase-1 `pydub` mixer).
- [ ] **7.6a** (Optional) per-section generation referencing neighbouring sections for longer, more coherent episodes.

**Dependencies:** Phases 1 (interview podcast + Voice/TTS/mixer ports) + 4 (UI) + 5 (per-user consent ownership). **DoD:** a real researcher can clone their voice for their paper's author role with recorded consent, and the mix sounds produced.

### Phase 8 — Search, Zotero, Visualisation

**Objective:** Owner's mid/long-term discovery + integration goals.
- [ ] **8.1a** Library search (title/author/full-text of summaries/transcripts).
- [ ] **8.2a** Zotero integration (import library) — an ingest adapter feeding the same pipeline.
- [ ] **8.3a** Visualisation (topic/citation maps).

**Dependencies:** Phases 2–4. **DoD:** search returns relevant papers; Zotero import works; at least one visualisation ships.

### Phase 9 — Deployment & Ops (Docker + Cloudflare tunnel)

**Objective:** Reproducible deploy from the host over LAN, optionally exposed via tunnel.
- [ ] **9.1a** Dockerfile + compose (named volumes for the artifact tree + SQLite DB; ffmpeg once the mixer lands).
- [ ] **9.2a** Trivy `scan` CI job (deferred from 0.4a).
- [ ] **9.3a** Cloudflare-tunnel deploy scripts (`deploy.sh`, `tunnel.sh`, adapted from `tipping-tools`).
- [ ] **9.4a** Backup strategy for DB + artifacts.

**Dependencies:** Phases 3–5. **DoD:** one-command deploy; image scanned in CI; LAN + tunnel access verified.

---

## Requirements Traceability

| Feat | Capability | Current code location | New module / port that owns it | Covering test(s) |
|---|---|---|---|---|
| **F1** | PDF text extraction | `file_processing.get_pdf_filepaths`, `file_processing.read_pdf` (pdfplumber, caches to `pdf_texts.json`) | `downlow.adapters.pdf.PdfExtractor` (impl) behind `domain.ports.PdfExtractor`; content-hash cache in `core.stages.ingest` | `tests/unit/test_ingest.py` (fixture PDF → text; empty/scanned handled; cache hit/miss) |
| **F2** | Context-steered LLM summarisation | `research_details.ResearchContext`/`DocumentContext`, `build_context_prompt()`; `text_processing.ResearchSummariser` (OpenAI `gpt-4o-mini`, caches `summaries/{title}.txt`, overwrite flag) | `core` models `ResearchProfile`/`OutputProfile`, `core.prompts.summary.build_context_prompt`, `core.stages.summarise` via `domain.ports.LLMClient` (`AnthropicLLMClient`, `claude-sonnet-4-6`; **default input = native PDF**, text path as fallback) | `tests/unit/test_summarise.py` (fake LLM: prompt composition, overwrite/force flag, cache, parallel path, truncation); `tests/unit/test_prompt.py` (steering prompt golden) |
| **F3** | Compiled report PDF + auto title/filename (LaTeX→Typst) | `text_processing.LaTeXConverter`, `CustomLLMCall`; `main.py` writes `main.tex`, `sleep(20)`, `os.rename main.pdf` (external compiler) | `core.stages.render` (merge + title) ; `adapters.render.TypstRenderer` behind `domain.ports.ReportRenderer` (in-process, deterministic) | `tests/unit/test_render.py` (fake LLM: merge + filename); `tests/integration/test_typst_render.py` (golden `.typ`/PDF; deterministic, no sleep, no watcher) |
| **F4** | Two-presenter interview podcast audio | `text_processing.TechnicalPodcastGenerator` (LLM script); `audio_processing.VoiceGenerator_ElevenLabs` (POST → stream mp3 to `users/{user}/audio/{title}.mp3`) | `domain.schemas.NarrationScript` (**multi-turn host/author**); `core.stages.narrate`; `adapters.tts.ElevenLabsTTSClient` + `pydub` mixer behind `domain.ports.TTSClient`/`AudioMixer` | `tests/unit/test_narrate.py` (fake LLM: host↔author script, long-input split); `tests/unit/test_tts.py` (fake ElevenLabs: per-turn TTS, retry/stream); `tests/unit/test_mixer.py` (segments → one mp3 with gaps) |
| **F5** | PDF filename-from-first-line heuristic | `file_processing.update_pdf_filenames` (interactive) | `core.services.filename.FilenameHeuristic` (pure: `suggest()` + `apply()`, non-interactive) | `tests/unit/test_filename.py` (first-line → name; apply renames; edge cases: empty/garbled/unicode/collision) |

*Cross-cutting guarantees (must also be covered):* CLI orchestration `tests/integration/test_run.py`; config loading `tests/unit/test_config.py`; no-backslash-path assertion (`tests/unit/test_paths.py` + CI grep); `LLMClient` truncation/retry `tests/unit/test_llm_client.py` (incl. `test_prompt_cache_hit` asserting `cache_read_input_tokens > 0`, and `test_token_budget_split` asserting the long-PDF split is measured with `count_tokens`).

---

## Technology Choices

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Environment / packaging | **uv + `pyproject.toml`** (hatchling, src-layout) | One committed `uv.lock`; reproducible `uv sync --frozen`; identical local/CI envs; mirrors `tipping-tools`. |
| Backend framework (future) | **FastAPI + SQLModel** | Locked decision; `core` is written so the api/ layer calls it unchanged. |
| LLM | **Anthropic Claude** via official `anthropic` SDK | Locked decision (full switch off OpenAI). `claude-sonnet-4-6` default for summarisation/narration; `claude-opus-4-8` for hardest reasoning. Native structured outputs (`messages.parse`), truncation guard, auto-retry. |
| Summariser input | **Native PDF to Claude (default)** + text-extraction fallback | Claude parses figures/tables/awkward layouts better than local extraction; the `LLMClient` takes a PDF `document` block or text. |
| PDF extraction | **pdfplumber** now (behind a `PdfExtractor` port) | Retained for dedupe/caching, the future reader/search, and the provider-agnostic fallback summarise path; the port lets **PyMuPDF** (faster, page-render for the future reader — but AGPL) or **pypdfium2** (Apache/BSD) drop in as a one-class change. |
| Report PDF | **Typst** (standalone binary via subprocess) | Single self-contained, pinned-version binary; deterministic `data → .typ → .pdf`; replaces the fragile Overleaf-watcher + `sleep(20)` hack. Data-driven template, not LLM-emitted markup. |
| Persistence | **SQLite via SQLModel now, Postgres-ready** | Locked decision. Structured data in the DB; binaries on the filesystem with paths/hashes in the DB. JSON columns + explicit enums portable to both backends. |
| Migrations | **Alembic** | Reviewable, reversible, CI-checkable; rejects VTTD's runtime auto-add-columns hack. |
| TTS / voice | **ElevenLabs** via official `elevenlabs` SDK (behind a `TTSClient` port) | Modernises the raw `requests` POST; exposes the voice-cloning API needed for the FUTURE author-voice feature. |
| Config | **pydantic-settings** | Single typed env reader; replaces scattered `os.getenv` + module globals. |
| CLI | **Typer** | Thin driver over `core` services; ~5-line commands. |
| Concurrency | **`concurrent.futures.ThreadPoolExecutor`** (sync-first) | I/O/subprocess-bound stages; real speedup without async colouring; clean seam to `AsyncAnthropic`/workers later. |
| Audio mixing | **pydub + ffmpeg** | Concatenates/mixes the per-turn TTS segments into one track (VTTD `audio_mixer` pattern); ships this phase for the two-presenter podcast. Cross-fades/music/SFX are later polish. |
| Lint / format | **ruff** (line-length 120, py311, `E,W,F,I,N,UP,B,SIM,T20,RUF`) | Adopted from `tipping-tools`; `T20` helps keep `core` IO-pure. |
| Types | **mypy strict** | Brand-new typed code, no legacy debt to grandfather; missing-import tolerance scoped to the three un-stubbed libs. |
| Tests | **pytest + pytest-cov** | Fully-offline; all external APIs and the Typst binary mocked in `unit/`; coverage gate ratchets up. |
| CI | **GitHub Actions** (`lint` / `typecheck` / `test`) | Lean baseline on `astral-sh/setup-uv`; `scan`/Postgres jobs added when Docker/Postgres arrive. |
| Frontend (future) | **OPEN QUESTION** — React 19 + Vite vs mirror-VTTD Jinja/JS-PWA | Owner picked React; the proven persistent-player pattern is VTTD's Jinja/PWA. Resolve via spike; `core`/`api` unaffected either way. |
| Deploy (future) | **Docker + Cloudflare tunnel** | LAN-first (`docker compose up -d`); opt-in tunnel for off-LAN access; adapted from `tipping-tools`. |

---

## Engineering Standards & CI/CD

### Environment & packaging

**uv**, one committed `uv.lock`, one git-ignored `.venv`, reproducible `uv sync --frozen`. Day-to-day: `uv sync --extra dev` to set up, `uv run <cmd>` to run inside the env, `uv add <pkg>` to add a dependency. **hatchling** build, src-layout (`packages = ["src/downlow"]`); the package name is stable now because the future `api/` layer will import it. The thin CLI entrypoint is `dl = "downlow.cli.app:app"` (`uv run dl …`).

Notes / to-confirm:
- **Claude model IDs/pricing:** pin bare model strings in typed settings, finalised against the `claude-api` skill before release; do not hard-assert pricing.
- **Typst:** subprocess to the pinned standalone binary by default; the `typst` PyPI package (bundled compiler) is the documented fallback behind the same `ReportRenderer` port if the host can't install the binary.
- **pydub/ffmpeg:** a **core dependency this phase** — the two-presenter podcast synthesises per-turn segments and mixes them into one track. `pydub` needs the system **ffmpeg** binary (documented in `CLAUDE.md`/README; installed in CI + Docker).
- **Postgres driver (`psycopg`):** deliberately absent until the Phase-2 migration.
- **FastAPI/uvicorn:** an `[project.optional-dependencies] api` extra (documented seam, `uv sync --extra api` works the day work starts) — `core/` must never import from it.

### Code quality config

Adopt tipping-tools' settings where they apply, dropping Django/DRF-specific pieces.

- **ruff:** `target-version = "py311"`, `line-length = 120`, `select = ["E","W","F","I","N","UP","B","SIM","T20","RUF"]`, `ignore = ["E501","N815","RUF012"]`, isort `known-first-party = ["downlow"]`, per-file `T201` ignore on the CLI (which legitimately prints).
- **mypy:** `strict` for the package (no legacy debt to grandfather); **no blanket `--ignore-missing-imports`** in CI — scope missing-import tolerance to `pdfplumber.*`, `typst.*`, `elevenlabs.*` only, keeping strictness honest everywhere else.
- **pytest:** `pythonpath = ["src"]`, `--strict-markers`, markers `slow` and `integration` so agents can scope runs with `-m "not slow"`.
- **coverage:** `fail_under = 60` — a **ratchet, not a wall.** Start at a realistic 60 for fresh test-first code and bump (60 → 70 → 80) only when the suite already clears the next rung. Setting 80 on day one just trains everyone to ignore the gate.

### CI/CD framework

Lean baseline now, documented growth path. One workflow, `.github/workflows/ci.yml`, three jobs, all on `astral-sh/setup-uv` + `uv sync --frozen --extra dev`:

- **lint** — `ruff check src/ tests/` + `ruff format --check src/ tests/`
- **typecheck** — `mypy src/downlow/`
- **test** — `pytest --cov=src/downlow --cov-report=term-missing` — the coverage gate lives **only** in `[tool.coverage.report] fail_under` (single source of truth; no `--cov-fail-under` on the CLI, so the ratchet is bumped in exactly one place). The `test` job also installs the pinned **`typst`** binary (the `integration/` render tests shell out to it; e.g. a `typst-community/setup-typst` step) and **`ffmpeg`** (`pydub` needs it for the audio-mix tests); unit tests need neither.

No real API keys in CI — every external call (Anthropic, ElevenLabs) is mocked in tests; if a client *constructor* requires a key, inject a fake via fixture rather than a CI env var. **Branch protection:** `main` is protected; all work lands via PR; the three CI jobs must pass and the branch must be up to date before merge (single-dev means self-review, but the PR + green-CI gate keeps the rebuild honest and gives the future `pr-reviewer` skill something to hook into).

**Versioned local hook** (`.githooks/pre-commit`, adapted from tipping-tools): `ruff check --fix` + `ruff format` on staged `.py` at commit time so the blocking lint job can't trip on formatting. Enable once per clone with `git config core.hooksPath .githooks`; document in `CLAUDE.md`/README.

**Growth path (deferred — add each when its trigger fires):** (1) **Containerise** → add a `scan` job (`aquasecurity/trivy-action`, CRITICAL/HIGH, `ignore-unfixed: true`) when the FastAPI `api/` ships deployable images. (2) **Postgres** → add a `postgres` service container + `DATABASE_URL` to the `test` job when moving off SQLite. (3) **Branch fan-out** → widen `on:` to a `dev` branch if a `main`/integration split is worth it. (4) **(Much later)** scheduled bot sessions — not warranted for a single-dev rebuild.

### Testing strategy

Mirror the VTTD / tipping-tools convention: **fast, fully-offline tests with every external API mocked.** No test hits Anthropic, ElevenLabs, or the network. Layout: `tests/unit/`, `tests/integration/`, `tests/fakes/`, `tests/fixtures/`.

- **Unit (pure logic, no I/O):** text-extraction cleanup (F1: whitespace/hyphenation, page-join); summary/narration schema round-trip + reject-malformed; **multi-speaker narration schema** validates/serialises (the foundation, not just F4); Typst data assembly (the `data → .typ` population, independent of the binary); filename heuristic (table-driven: normal/empty/garbage/unicode/collision); path handling (asserts `pathlib`, POSIX-safe — guards the legacy backslash bug).
- **Integration (pipeline, all externals mocked):** `FakeLLMClient` (canned structured JSON incl. a simulated `stop_reason == "max_tokens"` truncation case); `FakeTTSClient` (deterministic dummy mp3 bytes); committed fixture PDFs; end-to-end discover → ingest → summarise → render → (two-presenter) narrate + mix, asserting artifacts land on `tmp_path` and DB rows reach the expected state; the real `typst` binary and `ffmpeg`/`pydub` exercised in `integration/` only.
- **Golden-file / snapshot:** the assembled `.typ` source and the rendered report's extracted text — checked-in golden, diff against it (skip pixel-diffing the PDF; assert structure/text). Keeps Typst-template regressions visible.
- **conftest fixtures** (adapting VTTD's `db_session`/`client`/`test_user`): `db_session` (in-memory SQLite, rolled back per test), `tmp_artifacts`, `fake_llm`, `fake_tts`, `sample_pdf`, `settings` override (no real env/keys read).
- **Convention:** sub-agents run targeted tests for files they touch; the owner runs the full suite once before merge; `-m "not slow"` scopes fast runs.

### Future deployment (marked FUTURE — not built this phase)

When the `api/` layer exists and the app needs to be reachable on the LAN (and optionally remotely), adapt VTTD's deployment trio rather than inventing one:

- **`Dockerfile`** — `python:3.11-slim`; install ffmpeg (once the multi-turn mixer lands), `uv sync --frozen` the locked env, `CMD ["uvicorn", "downlow.api.main:app", "--host", "0.0.0.0", "--port", "8010"]` (VTTD uses `pip install -r requirements.txt`; we use `uv sync --frozen` for reproducibility).
- **`docker-compose.yml`** — one app service on a fixed port, `restart: unless-stopped`, `env_file: .env`, **named volumes for the binary-artifact tree** (source PDFs, report PDFs, mp3 audio) and the SQLite DB file so data survives rebuilds; a profile-gated `cloudflared` service (`profiles: [tunnel]`) for optional remote access (`docker compose --profile tunnel up -d`).
- **`deploy.sh`** — one-time host setup: checks Docker + `docker compose` v2, bootstraps `.env` from `.env.example` (prompting for `ANTHROPIC_API_KEY` + `ELEVENLABS_API_KEY`), brings the stack up to auto-start on reboot.
- **`tunnel.sh`** — `enable | disable | status` wrapper storing `CLOUDFLARE_TUNNEL_TOKEN` and toggling the tunnel profile (free remote access, no port-forwarding) for reaching the library off-LAN or sharing with researcher friends.

Local-first is the default: the LAN deploy is just `docker compose up -d` on the host; the tunnel is strictly opt-in. The `scan`/Trivy CI job should land in the same phase as the `Dockerfile`, so images are vulnerability-scanned from their first build.

---

## Dependencies & Critical Path

### Component dependency graph

```
                 ┌─────────────── Config (pydantic-settings) ───────────────┐
                 │                                                            │
LLMClient port ──┤                                                            │
   (Anthropic)   ├─▶ Summariser (F2) ─▶ ReportComposer (F3) ─▶ TypstRenderer (F3)
PdfExtractor ────┘        │
   (F1)                   └─▶ NarrationScriptGenerator (F4, multi-turn schema)
                                        │
TTSClient port ─────────────────────────┴─▶ NarrateStage (F4) ─▶ mp3
   (ElevenLabs)
FilenameHeuristic (F5)  ── independent ──────────────────────────────────────┐
                                                                              │
core + DB/SQLModel (Phases 0–1) ─▶ Postgres-ready + backfill (P2) ─▶ FastAPI api/ (P3) ─▶ Frontend (P4) ┘
                                                   │                  │
                                                   └─▶ Auth/Multiuser (P5) ─▶ Library feats (P6)
core schema/ports (1.5a–c) ─────────────────────────────────────────▶ Enhanced podcast (P7)
DB + API (P2–3) ──────────────────────────────────────────────────▶ Search/Zotero/Viz (P8)
API + Auth (P3,P5) ───────────────────────────────────────────────▶ Deploy (P9)
```

### Critical path (longest dependent chain to the product vision)

**Phase 0 (scaffold) → `LLMClient` + `PdfExtractor` ports + DB/SQLModel → Summariser (F2) → FastAPI api/ (P3, after Postgres-readiness P2) → Frontend + persistent player (P4) → Auth/Multiuser (P5) → Enhanced two-presenter podcast + voice cloning (P7).**

- **Within this phase**, the internal critical path is **ports/infra (1.1x) → F1 → F2 → F3 (Typst)**. F3 is the riskiest internal item (Typst fidelity vs old LaTeX) and the longest internal chain; F4 branches off F2 in parallel; F5 is off the critical path.
- **Foundational chokepoints** (block the most downstream work): the **`LLMClient` port** (everything LLM-shaped depends on it) and the **`core`-callable-unchanged contract** plus the **DB** (live in Phase 1; Postgres-readiness in P2), which gate the entire API→frontend→multiuser chain.
- **The multi-turn narration schema + `Voice` port (1.5a–1.5c)** are deliberately on the critical path *now* even though P7 is far away — getting them wrong forces a P7 rework, so they are the highest-leverage foresight items in this phase.

---

## Risks & Mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Typst report fidelity** falls short of the old LaTeX output (math, layout, references) | Med | High | Golden-file tests (1.8b); build a representative report fixture early; keep the renderer input a structured model (not raw markup) so it's swappable; spike Typst on a real multi-summary doc before committing F3. |
| R2 | **LLM cost / latency / nondeterminism** | Med | Med | Default `claude-sonnet-4-6` for summarisation, reserve `claude-opus-4-8`; prompt-cache the steering context; bounded-concurrency parallelism; cache summaries by content hash; record token usage. *Model IDs/pricing confirmed against `claude-api`; adaptive thinking, not `budget_tokens`.* |
| R3 | **PDF extraction quality on scanned/garbled papers** | Med | Med | Detect low-text output and flag (1.2c); never crash; OCR documented as future (out of scope this phase). |
| R4 | **Scope creep into new features** (web UI, search, voice *cloning* slipping into Phase 1) | High | High | Hard In/Out scope table; DO10 ("no new feature ships"); PRs reviewed against the F1–F5 traceability table; new ideas → issues via `future-fixes-to-issues`, not commits. |
| R5 | **Single-dev bus factor** | High | Med | `CLAUDE.md` + `.claude` agents/skills encode context; planning doc in repo; tests + types as executable documentation; conventional commits + CI keep history legible. |
| R6 | **External API rate limits / outages** (Anthropic, ElevenLabs) | Med | Med | Retries with backoff in adapters; typed errors (`TruncatedResponseError`); SDK auto-retry (429/5xx); cache expensive outputs so reruns don't re-hit APIs; mock all external APIs in tests. |
| R7 | **SQLite → Postgres migration** surprises later | Low | Med | SQLModel idioms portable to both; avoid SQLite-only types; smoke-test against Postgres in CI before relying on it (Phase 2 DoD). |
| R8 | **Voice-cloning consent / ethics / identity misuse** | Med | **High** | Bake **consent + ownership metadata into the `Voice` entity now** (1.5c); explicit consent capture + revocation in P7 (7.6a); store provenance (sample path, owner, timestamp); never auto-clone without recorded consent; document policy in `CLAUDE.md`. |
| R9 | **Host/author voice consistency across episodes** | Med | Med | Single canonical host-voice config seeded in Phase 1 (1.5c), referenced by id, not regenerated; per-`Paper` author-voice reference; pin `provider_voice_id`; the host-vs-author role split (1.5a) makes this structural, not incidental. |
| R10 | **Frontend stack indecision** (React vs Jinja/PWA) stalls Phase 4 | Med | Med | Explicit OPEN QUESTION; resolve via spike (4.0a) measuring persistent-player effort; keep the API frontend-agnostic so the choice is reversible. |
| R11 | **`core` accidentally couples to CLI/IO** (breaks the FastAPI-callable-unchanged contract) | Med | High | Ports/adapters discipline; no `print`/`argv`/`getcwd` in `core` (T20 ruff rule helps); API-callability is a Phase-1 DoD and re-verified in Phase 3. |
| R12 | **Profile/data-model assumes single-user**, forcing a multi-user rewrite | Low | Med | Keep a `user`/profile boundary in the schema from Phase 1 (G6); scope is the only thing that changes in P5, not the schema shape. |
| R13 | **Native-PDF input cost / page limits** (the default summarise path) — `document` blocks can be token-heavy; long-context PDF support caps ~100 pages | Med | Med | Cache by `source_hash` so each paper is sent once; fall back to the text-extraction + section-split path for over-limit PDFs; measure with `count_tokens`; confirm limits/cost against the `claude-api` skill. |

---

## Scope of This Phase (In / Out)

| ✅ IN scope (this phase = Phase 0 + Phase 1) | ❌ OUT of scope (planned/scaffolded only) |
|---|---|
| Rebuild **F1** PDF extraction in `core` | Any **web UI / frontend** (React or Jinja) |
| Rebuild **F2** context-steered summarisation (Anthropic) | Any **FastAPI endpoint / HTTP API** |
| Rebuild **F3** report PDF via **Typst** (in-process) | **Postgres** + legacy `users/` backfill (SQLite/SQLModel/Alembic *is* wired this phase) |
| Rebuild + extend **F4**: **two-presenter** (host+author) podcast — per-turn TTS + `pydub` mix | **Voice *cloning*** of a real author's voice + consent onboarding |
| Rebuild **F5** filename heuristic (non-interactive) | **Voice cloning** flow / consent UI (Voice table created; clone/consent columns empty) |
| `LLMClient`/`PdfExtractor`/`ReportRenderer`/`TTSClient`/`AudioMixer`/`ArtifactStore` **ports + adapters** | **Cross-fades / music / SFX** mix polish (basic concatenate-mix ships) |
| **Multi-speaker narration schema** + `Voice` table (stock host voice seeded) | **Auth / multi-user / JWT / rate limiting** |
| Thin **CLI** orchestrating `core` | **Library features**: folders, recently-viewed, resume |
| **uv + pyproject**, ruff, mypy strict, pytest+cov, CI; **SQLite + SQLModel + Alembic** wired | **Search / Zotero / visualisation** |
| **`.claude` agents/skills** + **`CLAUDE.md`** (from `tipping-tools`) | **Docker / Cloudflare tunnel / Trivy scan** deployment |
| **Directory seams** for `api/` and `frontend/` (documented, empty) | **OCR** for scanned PDFs |
| Fix **all known defects** (paths, sleep/Overleaf, OpenAI→Anthropic, errors/retries, parallelism, concerns) | New steering/model features beyond porting existing behaviour |
| Full **regression tests** + traceability for F1–F5 | Background job queue / async stage execution |

**Drift guard:** if a task isn't a rebuild of F1–F5 or a Phase-0 foundation, it belongs in an issue, not this phase.

---

## Open Questions for the Owner

Consolidated "to-confirm" items. None block the `core` rebuild this phase, but several shape the future and should be settled before the work they gate.

**Confirmed by the owner (2026-06-24):** brand **DownLow** / import `downlow` / CLI `dl` (Q7); the **two-presenter host+author interview podcast ships this phase** with per-turn TTS + `pydub` mix — only author voice-cloning is deferred (Q4); **default summarise input = native PDF to Claude**, with text extraction retained as fallback + for the reader/search (Q11); **Typst deterministic data-driven template** (Q3). These four are marked ✅ below.

1. **Frontend architecture — React 19 + Vite vs. mirror VTTD's Jinja2 + vanilla-JS PWA.** *The single most consequential decision.* The owner selected React 19 + Vite, but the proven template (VTTD) uses Jinja2 + a vanilla-JS PWA with a custom client-side router — which is precisely what makes the persistent audio player keep playing across navigation.

   | | React 19 + Vite (SPA) | Mirror VTTD (Jinja2 + vanilla-JS PWA) |
   |---|---|---|
   | Richness / ecosystem | Strong | Lean — more by hand |
   | Matches tipping-tools | Yes (the `frontend-engineer` agent's React conventions) | No |
   | Proven for *this* product | Unproven here | Proven — VTTD ships the exact persistent-player UX |
   | Time-to-ship | Slower setup, faster for complex views | Faster to first UI; owner knows the pattern |
   | Persistent audio player | Doable (shared audio context above the route tree) but re-solves what VTTD already solved | Already solved |
   | Owner familiarity | Less | More |

   Recommendation: resolve via a short spike (Phase 4.0a) measuring persistent-player effort in each. The `core` package is unaffected either way.

2. **Exact Claude model pinning.** Default `claude-sonnet-4-6` for summarisation/narration, `claude-opus-4-8` for hardest reasoning — **confirmed against the `claude-api` skill** (sonnet-4-6 $3/$15 per MTok, 1M ctx, 64K out; opus-4-8 $5/$25 per MTok, 1M ctx, 128K out; both adaptive-thinking only, never `budget_tokens`). Confirm before release whether these remain the chosen defaults; pricing is current-as-of the skill cache and should not be hard-coded into business logic. (Final pinning is a config value, trivially changed.)

3. ✅ **RESOLVED — Typst.** Deterministic **data-driven `report.typ`** (structured summary → template); LLM-emits-markup rejected for reproducibility. (Remaining sub-point: title/filename is templated-by-default with an optional LLM override.)

4. ✅ **RESOLVED — Audio scope.** Ship the **two-presenter host+author interview podcast** this phase: Claude interview script → per-turn TTS with two stock voices → `pydub`-mixed mp3 (VTTD's segment-mix pattern). Only author voice *cloning* (with consent onboarding) and mix polish (cross-fades/music/SFX) are deferred to Phase 7.

5. **Host/author stock voices + voice-clone onboarding/consent.** This phase seeds *sensible default* stock ElevenLabs voices for the **host** (consistent interviewer) and the **author** — confirm your preferred picks (changeable in config). Still needed before Phase 7: the exact **template-script** wording researchers read for cloning, and the **consent model** (how consent is captured, stored, revoked, and who "owns" a cloned voice). The data model reserves `consent_granted/owner/recorded_at` + `sample_recording_ref` now.

6. **Research profiles persistence.** Confirm the unification of `data/research_data.json` + the implicit `users/` tree into DB-backed `ResearchProfile`/`OutputProfile` (the journal wants this). This phase models them DB-ready; Phase 2 wires the DB and backfills the existing `users/` tree.

7. ✅ **RESOLVED — Package name.** Brand **DownLow**: import root **`downlow`**, CLI entrypoint **`dl`**. (Repo dir stays `research-paper-summaries`.)

8. **PyMuPDF AGPL decision.** pdfplumber ships this phase behind the `PdfExtractor` port. If the future in-app PDF reader or speed wants PyMuPDF, confirm the **AGPL-3.0** licence is acceptable for the single-user local-network case (it is) — and note that a move to distributing/SaaS would require the commercial licence or a swap to **pypdfium2**. Recorded in `CLAUDE.md`.

9. **In-app PDF reader delivery (future).** Native browser viewer (`<embed>`/`<iframe>` — zero bundle cost, inconsistent, hard to overlay) vs. **pdf.js** (full control, theming, deep-linking from the summary into a page/section, future annotation — costs bundle size). Affects whether the summary can link into the PDF. Confirm before any reader UI.

10. **Installable PWA + lock-screen / Media Session controls (future).** VTTD is an installable PWA with a service worker and OS-level media controls. Confirm whether this product needs add-to-home-screen + offline shell and lock-screen play/pause/seek (valuable for phone listening on the same Wi-Fi) — this materially favours the VTTD-mirror in Q1, or requires re-implementing the service worker + Media Session in the React SPA.

11. ✅ **RESOLVED — PDF input.** Support **both**, defaulting to **sending the PDF natively to Claude** (better on figures/tables/awkward layouts); text extraction is retained for the reader/search/caching and as the provider-agnostic fallback. Native-PDF specifics (page/size limits, Files API, document prompt-caching) to be confirmed against the `claude-api` skill at build time.

12. **ElevenLabs voice-cloning + SFX API surface (to-confirm).** The plan assumes the official `elevenlabs` SDK exposes voice cloning (FUTURE author voices) and SFX (FUTURE mixing). Unlike the Claude specifics (verified against the `claude-api` skill), these third-party capabilities are **not yet verified** against the SDK — confirm the exact cloning method, input requirements, and plan limits before Phase 7.

---

## Assumptions & Glossary

### Key assumptions

- **A1** — Locked decisions hold (FastAPI+SQLModel, Anthropic, Typst, SQLite-now/Postgres-later, React-or-VTTD-mirror as open question). Not re-litigated.
- **A2** — Single user (Luke) for this phase and the near term; multi-user is later, but the schema keeps the boundary (G6).
- **A3** — Model pinning confirmed against the `claude-api` skill: `claude-sonnet-4-6` default (cost/speed), `claude-opus-4-8` for hardest reasoning; both adaptive-thinking only. Final pinning is a config value.
- **A4** — Typst can reproduce the report layout the old LaTeX produced; verified by spike + golden tests before F3 is done (R1).
- **A5** — ElevenLabs remains the TTS/voice-clone provider; the `TTSClient` port keeps this swappable.
- **A6** — Binary artifacts (source PDFs, report PDFs, mp3s) live on the filesystem; structured data is in SQLite via SQLModel from **Phase 1** (Postgres-readiness + the legacy `users/` backfill come in Phase 2).
- **A7** — `tipping-tools` conventions are the culture template to **adapt** (not copy verbatim); the greyhound-domain agent is replaced.
- **A8** — No production users depend on the current script, so the rebuild can change behaviour/paths freely (only Luke's local `legacy/users/` tree needs import later).
- **A9** — The frontend stack decision (React vs Jinja/PWA) is deferred and does **not** block Phases 0–3; the API is built frontend-agnostic.

### Glossary

- **core** — The provider-agnostic, IO-isolated Python package (`downlow.core` over `domain`) holding all business logic (stages, services, prompts). The deliverable contract: a future `api/` layer calls it unchanged.
- **domain** — The purest layer: entities, enums, DTOs, and port Protocols. Depends on nothing but stdlib + pydantic.
- **port / adapter** — *Port* = an abstract interface (`Protocol`) `core` depends on (`LLMClient`, `TTSClient`, `PdfExtractor`, `ReportRenderer`, `ArtifactStore`, `Repository`). *Adapter* = a concrete implementation (`AnthropicLLMClient`, `ElevenLabsTTSClient`). Lets the same `core` logic swap providers and be tested with fakes.
- **stage** — One pipeline step with defined typed input/output, recoverable independently (VTTD's FETCH→ADAPT→GENERATE→MIX→DELIVER; here INGEST→SUMMARISE→RENDER→NARRATE→STORE).
- **profile** — A user's research context (`ResearchProfile`: field, topic, interests, focus) that steers summarisation, plus `OutputProfile` (document type, requested return details).
- **artifact** — A produced binary kept on the filesystem: the source PDF, the generated report PDF, or the mp3 audio (vs. *structured data*, which goes in the DB).
- **job** — A requested unit of pipeline work (`PipelineRun`); synchronous this phase, with a background-execution seam noted for later.
- **turn** — One entry in the multi-speaker narration schema: `{role: host|author, text, tone}`. An ordered list of turns is the narration script; the host+author interview ships now, author voice *cloning* later.
- **Voice / cloned voice** — A TTS voice entity: id, provider, provider_voice_id, source (stock|cloned), owner + consent metadata, sample-recording path. A cloned voice is a `Voice` with `source=cloned` created from an uploaded author sample via ElevenLabs cloning (Phase 7).
- **prompt_version** — A first-class constant stamped into every summary/narration script and part of the cache key; the unit of "did the prompt change."
