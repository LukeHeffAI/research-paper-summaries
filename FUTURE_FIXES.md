# FUTURE_FIXES

Running scratchpad for known issues / tech debt. Append rather than fixing
unrelated issues opportunistically; convert to GitHub issues via the
`future-fixes-to-issues` skill. See `CLAUDE.md`.

---

## S1 -- Summary system prompt is below Sonnet's min cacheable prefix

`SUMMARY_SYSTEM_PROMPT` (core/prompts/summary.py) is ~1k tokens, below Sonnet
4.6's 2048-token minimum cacheable prefix. The `cache_control={"type":
"ephemeral"}` breakpoint the adapter sets on the system block therefore *silently
no-ops* -- the prompt cache never fires, so the steering prefix is re-billed at
full input price on every paper.

Options:
- grow the frozen prefix past 2048 tokens (e.g. fold a fuller, stable rubric /
  worked field-by-field example into the system prompt);
- move the cache breakpoint to cover system + the (stable) schema together if
  that clears 2048;
- accept it (single-user, low volume) and document the cost.

Acceptance: a cache-hit **integration** test asserting `usage.cache_read_input_
tokens > 0` on the second call with the same prefix (today nothing verifies the
cache actually fires; the unit suite uses the fake, which has no usage data).

Source: claude-api skill (min cacheable prefix 2048 Sonnet / 4096 Opus);
PROJECT_PLAN.md Stage 2 step 5 "Gotcha".

---

## S4 -- `_reduce` can split a partial-summary JSON mid-token

`SummariseStage._reduce` (core/stages/summarise.py) joins `model_dump_json()` of
the partial summaries into one text blob and re-summarises it. On a genuinely huge
paper that reduce input can itself exceed `max_tokens`, hit the recursive
truncation path, and `_split_text` can hard-midpoint-split the concatenated JSON
**mid-token** (the midpoint fallback when there is no blank-line boundary),
producing invalid JSON fragments fed back to the model.

Fix: reduce **pairwise** (tree-reduce partials two at a time) and/or budget the
reduce input with `count_tokens` so it never needs splitting; never midpoint-split
serialised JSON. NARRATE will reuse this long-input machinery, so fix the latent
bug here before it is copied.

Rarely fires today (Sonnet 4.6 has 1M context; the section-split path is itself
rare), hence deferred rather than blocking.

---

## Files-API native-large-PDF (deferred from F2)

F2 inlines native PDFs as base64 only; PDFs over the safe inline cap
(`_MAX_INLINE_PDF_BYTES`, ~20 MB raw) fall back to extracted text + section-split.
The original F2 attempt at a Files-API path was removed because it was wired
wrong: `betas=` was passed to the **non-beta** `client.messages.parse/stream`
(beta features live on `client.beta.messages.*`), and the upload omitted the beta
header -- so the large-native-PDF route never worked.

Re-add correctly:
- upload via `client.beta.files.upload(...)` with the `files-api-2025-04-14` beta;
- send the message via `client.beta.messages.parse/stream(..., betas=[
  "files-api-2025-04-14"])` referencing the `document` block by `file_id`;
- reuse one upload across summarise + narrate stages (the win over re-inlining);
- boundary test at the >=4 MB threshold (native-Files path vs inline base64).

Source: claude-api skill (Files API beta `files-api-2025-04-14`; beta messages on
`client.beta.messages.*`).

---

## Generated podcast theme + richer SFX via ElevenLabs (deferred from F4)

F4 ships placeholder/curated music assets (committed `assets/audio/*.wav`:
intro/outro/sting/bed) resolved by cue, with a graceful missing-asset skip in the
mixer. The two follow-ups:

- **Generated theme music** via ElevenLabs (the music/sound-generation API) to
  replace the placeholder stings -- a generation path behind the audio/tts ports
  so the theme and the rare SFX cue can be synthesised, cached, and reused.
- **Richer SFX beds** -- the 3-layer mixer already supports `under` beds and
  non-`under` stings; populate a small curated/generated SFX library and let the
  narration prompt emit sparse `sfx` cues.

The schema (`Turn.type == "sfx"`, `cue`, `under`) and the mixer layers already
exist, so this is a population + generation-adapter change, not a rewrite.

Source: docs/podcast_design.md section 6 (Music & SFX) + the F4 brief.

---

## Sectioned-narration `_reduce` duplicates structural music turns

`NarrateStage._reduce` (core/stages/narrate.py) merges per-section partial scripts
by concatenating their `turns`. The required structure (cold-open host turn,
`music intro`, ... `music outro`) appears in *each* section's partial, so a
multi-section paper produces an episode with duplicated intro/outro/cold-open
`music` turns mid-timeline. Rarely fires (Sonnet 4.6 has a 1M context, so almost
every paper scripts in one call), but the reduce path is wrong when it does.

Fix options:
- dedupe structural `music` cues in `_reduce` -- keep the first section's cold-open
  + intro and the last section's outro, drop interior intro/outro turns; or
- budget/instruct the reduce so only the first section emits the cold open + intro
  and only the last emits the outro (a per-section prompt variant); or
- run a final reduce LLM pass that re-stitches the concatenated turns into one
  coherent arc (mirrors SUMMARISE's reduce, at a token cost).

Sibling to the S4 summarise reduce entry. Source: F4 PR #6 review.

---

## Repository `add`/`delete` commit without rollback (unit-of-work)

`SqlModelRepository.add` / `.delete` (adapters/db/repositories.py) call
`session.commit()` but have **no** `try/except -> session.rollback()`. This is a
deliberate "the composition root owns the session" design (the CLI now / a FastAPI
`get_session` dependency / a worker later opens and disposes the session and is
responsible for rolling back a failed unit of work), and it is documented on both
methods. But there is currently no enforcing wrapper, so a caller that does several
`add`s and crashes mid-way leaves the session in a partially-committed, undefined
state unless it rolls back itself.

Fix when the STORE stage / services land (Phase 2.1):
- add a unit-of-work context manager at the composition root that `commit`s on
  success and `rollback`s on any exception, and have services run their writes
  inside it; or
- make the repository methods flush (not commit) and let the unit-of-work own the
  single commit/rollback for the whole operation.

Source: Phase 2.0 PR #9 review.

---

## JSON columns are `sqlalchemy.JSON` (Postgres `json`, not `jsonb`)

The list/dict columns in adapters/db/tables.py (`authors`, the structured
`Summary` fields, `requested_stages`, `narration_script`, ...) use the portable
`sqlalchemy.JSON` type. On SQLite it is fine; on Postgres it maps to `json` (text
storage), **not** `jsonb` -- so it cannot be GIN-indexed and containment / path
queries on it are slow. Acceptable now (single-user SQLite; these columns are
read/written whole, never queried by their contents).

Switch the relevant column(s) to `postgresql.JSONB` (e.g. via a
`JSON().with_variant(JSONB(), "postgresql")` type) **when** any JSON column needs
indexed querying on Postgres -- ships as an Alembic migration (`ALTER ... TYPE
jsonb USING column::jsonb`), reviewed.

Source: Phase 2.0 PR #9 review.

---

## Phase 2.2 Postgres-readiness audit -- result (no blocking gaps)

The 2.1a audit of `adapters/db/{engine,tables}.py` + `migrations/env.py` found the
hot path already portable: timestamps are `DateTime(timezone=True)` with a
read-path UTC re-attach (`_utc_aware`); enums are `Enum(native_enum=False)` portable
VARCHARs; PKs are SQLAlchemy `Integer` (-> Postgres identity); there are **no**
server-side defaults (all defaults Python-side / via the injected `Clock`, no
`func.now()`); `render_as_batch` + the FK `PRAGMA` are gated on `_is_sqlite` only;
the user<->voice FK cycle is a post-create `use_alter` ALTER (works on both
backends); `compare_type=True` is set so cross-backend drift is caught. The single
known non-blocking gap remains the `json`-vs-`jsonb` entry above (acceptable: these
columns are read/written whole, never queried by content). Driver: `psycopg[binary]`
under the `postgres` extra; the same `create_db_engine` serves both backends. Proof
is the CI `test-postgres` job (no local Postgres).

## research_profile / output_profile lack a DB uniqueness backstop (Phase 2.3)

The backfill (and the data-model docstrings) treat `research_profile.user_id` as
unique-per-user and `output_profile.(user_id, name)` as unique, but
`adapters/db/tables.py` declares no `UniqueConstraint` for them (unlike
`user.username` / `episode_paper`). Dedupe is enforced only by the service's
find-then-`add`. Safe for the single-process CLI, but two concurrent backfills (or a
future API racing the CLI) could double-insert. **Fix when concurrency / the API
lands:** add `UniqueConstraint("user_id")` to `research_profile` and
`UniqueConstraint("user_id", "name")` to `output_profile`, plus an Alembic migration,
and verify the drift gate on both backends.
