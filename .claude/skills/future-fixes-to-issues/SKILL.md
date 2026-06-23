---
name: future-fixes-to-issues
description: >
  Convert FUTURE_FIXES.md (the project's running tech-debt scratchpad) into individual,
  scored, labelled GitHub issues — one issue per top-level entry, with C1-C5 (criticality)
  and L1-L5 (length) labels. Verifies each entry against the current codebase via parallel
  specialist sub-agents, deletes resolved/stale entries, replaces FUTURE_FIXES.md prose
  with one-line GH issue pointers, and ships via a PR (never direct to protected `main`).
  Triggered by "review FUTURE_FIXES", "convert FUTURE_FIXES to issues",
  "/future-fixes-to-issues", or any request to turn the scratchpad into tracked issues.
allowed-tools: Bash(gh *), Bash(git *), Bash(python3 *), Bash(grep *), Bash(wc *), Bash(ls *), Read, Edit, Write, Grep, Glob, Agent, AskUserQuestion, TaskCreate, TaskUpdate, TaskList
argument-hint: "[optional: 'verify-light' | 'verify-deep' | path/to/alt-scratchpad.md]"
---

# FUTURE_FIXES → GitHub issues

Each scratchpad entry becomes one GH issue with `## Summary / Why it matters /
Affected code / Proposed fix / References` sections, one `C{1-5}` label, one `L{1-5}`
label, sub-bullets preserved as `## Sub-items` checklists for bundles.

PROJECT_PLAN.md §Work Style applies. `main` is protected — every change ships via PR.

## Workflow

### 1. Clarify scope (one `AskUserQuestion`, three Qs)

(a) Post-creation entry handling: one-line pointer (recommended) / delete entirely /
leave in place. (b) Verification depth: spot-check / verify-each / per-entry sub-agent
(recommended for >10). (c) Resolved entries: delete (recommended) / keep as history.
If invoked with `verify-light`/`verify-deep`, use that for (b) and skip it.

### 2. Inventory + clean

```bash
wc -l FUTURE_FIXES.md && grep -n "^## \|^### " FUTURE_FIXES.md
```

Treat both `##` and `###` as candidate top-levels. Build numbered inventory (line range,
gist, target specialist).

**Delete resolved/stale entries first** (`^## ~~`, `^## Resolved`, `Action: None
required`). Before deleting a resolved block, re-grep it for `Open follow-ups` /
`Remaining` / `TODO` and extract any unresolved bullets as new top-level entries — don't
lose buried items.

### 3. Create C1-C5 + L1-L5 labels

```bash
for c in 1 2 3 4 5; do
  gh label create "C$c" --color "<gradient>" --description "Criticality $c — ..." --force
done  # same for L1-L5
```

C1 `BFDBFE` → C5 `DC2626` (blue→red); L1 `DCFCE7` → L5 `16A34A` (green). `--force`
makes it idempotent.

### 4. Dispatch specialists in parallel

Group entries into 6–8 batches (8–16 each) by domain; dispatch all in **one message** as
parallel `Agent` calls with `run_in_background: true`. Typical: pipeline-orchestration
(core/services), ingest-pdf, summarise-claude, render-typst, narrate-elevenlabs,
adapters/storage-db, cli, test-coverage.

Each brief uses `agent-brief-template.md`, pre-loading: working dir + branch; table of
`id | line range | topic`; per-entry targeted verification command (`grep -n` /
`Read offset+limit`, never whole files); the rubric from `rubric.md`; output format with
`=== ISSUE <id> === ... === END ISSUE <id> ===` delimiters and `BODY: <<<EOF / EOF`
heredoc body for parsing; "read-only, no edits, no tests/lints" directive; response cap.

### 5. Save outputs as agents return

Save each background agent's output to `/tmp/issue-batch-<letter>.md` immediately on
return — protects against context compaction before issue creation.

### 6. Bulk-create via `create_issues.py`

The bundled script parses each batch file, skips `SKIP: yes` blocks, runs `gh issue
create --title ... --body ... --label "C{n},L{n}"`, sleeps 0.4s between calls, writes
`/tmp/issue-mapping.txt` keyed by in-batch id. ~90s for 50–70 issues.

### 7. Rewrite FUTURE_FIXES.md as an index

Replace with a domain-grouped index. Each line:

```
- [#N](https://github.com/LukeHeffAI/research-paper-summaries/issues/N) `C{n} L{n}` — short title
```

Lead with one paragraph explaining the index→GH contract and label semantics.
Cross-link paired issues (`paired with #Y`, `blocked on #X`).

### 8. Ship via PR

```bash
git add FUTURE_FIXES.md && git commit -m "<conventional message>"
git checkout -b docs/future-fixes-to-gh-issues && git push -u origin <branch>
gh pr create --base main --title "..." --body "..."  # heredoc: summary, dropped entries,
                                                      # C4+ priority list, test plan
```

Don't merge.

## Constraints & gotchas

- **Never push direct to `main`** — branch protection rejects.
- **Don't lose buried unresolved items** when deleting resolved blocks (step 2).
- **Default to one issue per top-level `##`.** Splitting "Misc nits" bundles is OK if
  sub-items are wholly unrelated; keep total count manageable (~50–70).
- **Verification budget.** Per-entry sub-agent on 50+ items ≈ 300–500k tokens. Under
  budget pressure dispatch sequentially.
- **No worktree isolation** — agents are read-only investigation.
- **`SKIP: yes` reasons:** file/symbol gone, fix shipped in later PR, stale env var
  removed. Agents should mark these explicitly.
- **Idempotency.** Script doesn't dedupe vs existing issues. Re-running on the same
  scratchpad: clear `/tmp/issue-batch-*.md` and confirm no prior-run issues exist.

## Files in this skill

- `SKILL.md` — this file.
- `rubric.md` — full C1-C5 + L1-L5 rubric (paste into agent briefs).
- `agent-brief-template.md` — canonical specialist-batch dispatch template.
- `create_issues.py` — bulk issue-creation script.
