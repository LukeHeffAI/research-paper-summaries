# Scoring rubric — paste verbatim into agent briefs

## CRITICALITY (C1=lowest, C5=highest)

- **C1** — Cosmetic / informational only. No functional impact. (e.g. log wording, doc nit, dead code with no consumers.)
- **C2** — Low priority. Code smell, minor performance hint, or low-blast-radius nit.
- **C3** — Medium. Real bug or material gap, but workarounds exist or impact is bounded.
- **C4** — High. Significant correctness bug, performance hit affecting users, or production-relevant gap. Should be picked up soon.
- **C5** — Critical. Data loss, silent fail-closed bypass, security, active production breakage.

## LENGTH (L1=trivial, L5=epic)

- **L1** — <30 min, single-file mechanical edit.
- **L2** — 1-2 hours, single-module change with a test.
- **L3** — Half-day to one day, 2-3 modules, tests, possibly migration.
- **L4** — Multi-day, frontend+backend, design discussion, multiple PRs.
- **L5** — Week+, new pipeline stage / new architecture / multi-PR plan.

## Anchor examples (calibrate against these)

| Example | C | L |
|---|---|---|
| Stale docstring on a pipeline service | 1 | 1 |
| Missing fakes for a port Protocol in 3 unit tests | 2 | 2 |
| Operator decision: rotate expired ElevenLabs/Anthropic API key | 2 | 1 |
| Cap summary input token budget instead of sending whole PDF | 3 | 2 |
| Test coverage gap on SUMMARISE + RENDER stages | 3 | 2 |
| Sync DB writes in the STORE adapter block the pipeline thread | 3 | 3 |
| Bundle of 12 frontend follow-ups (React 19 + Vite, mixed P1/P2) | 3 | 4 |
| Summary generated with wrong context-steer prompt, off-topic output | 4 | 1 |
| Pipeline service swallows a NARRATE adapter failure silently | 4 | 1 |
| `ci.yml` triggers on wrong branch — most PRs skip CI | 4 | 1 |
| Typst template breaks on multi-author papers; needs schema rework | 4 | 4 |
| New stage: two-presenter podcast diarisation + chaptering pipeline | 3 | 5 |
