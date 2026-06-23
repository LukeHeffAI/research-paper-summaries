# `legacy/` — reference-only snapshot (delete after Phase 1)

The original pre-rebuild scripts, kept **only** as a behavioural reference while
F1–F5 are ported into `src/downlow/`. They are **broken on Linux** (Windows
backslash paths with `\a`/`\d` escapes), use the **legacy pre-1.0 OpenAI SDK**, and
depend on an **external LaTeX watcher + `sleep(20)`**.

Also quarantined here: `legacy/data/` (the old `research_data.json` / `document_data.json`
profiles) and `legacy/users/` (the old per-user tree + a sample mp3) — kept as the
**Phase 2 migration source** (backfilled into the DB), then deleted with the rest of `legacy/`.

- Not linted, type-checked, or tested (excluded from ruff/mypy/CI).
- Do **not** import from `legacy/` in new code.
- **Delete this directory once Phase 1 is complete** and the F1–F5 traceability
  tests pass. See `PROJECT_PLAN.md` → Requirements Traceability.
