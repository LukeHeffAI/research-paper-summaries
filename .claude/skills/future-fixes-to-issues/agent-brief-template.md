# Specialist batch dispatch template

Copy this file per batch, fill in `{{...}}` placeholders, and pass as the `prompt` to
the `Agent` tool. Always set `run_in_background: true`. Always set `subagent_type` to
match the domain (`backend-engineer` for core/adapters/CLI, `ml-engineer` for the
Claude summarisation pipeline, etc.).

---

You are investigating items from `{{ABSOLUTE_PATH_TO_SCRATCHPAD}}` and producing
structured output that the dispatcher will paste directly into `gh issue create`.
**Do not edit any files. Do not run tests/lints. Do not commit. Read-only investigation.**

Working dir: `{{REPO_ROOT}}`. Branch: `{{BRANCH}}`. Stack: {{ONE_LINE_STACK_DESCRIPTION}}.

## Items assigned to you (Batch {{LETTER}}: {{DOMAIN}})

| # | Lines | Topic |
|---|---|---|
| {{LETTER}}1 | {{a-b}} | {{topic}} |
| {{LETTER}}2 | {{a-b}} | {{topic}} |
{{...}}

## Verification policy (one targeted check per item)

For each item, do ONE quick check (skip if obviously still relevant):

- {{LETTER}}1: `grep -n "{{symbol}}" {{file}} | head -10`
- {{LETTER}}2: `Read {{path}} offset~{{N}} limit 30`
- {{...}}

If verification shows the issue is already fixed (file gone, fix shipped in later PR,
stale env var removed), mark `SKIP: yes` with a one-sentence reason. If line numbers
shifted but the bug is still present, note the new line numbers in the issue body.

## Scoring rubric

{{PASTE_FULL_CONTENTS_OF_rubric.md_HERE}}

## Output format — exactly this structure per item, separated by `=== ISSUE ===`

```
=== ISSUE {{LETTER}}1 ===
SKIP: no
TITLE: <60-90 char specific, grep-friendly title>
LABELS: C<n>,L<n>
BODY: <<<EOF
## Summary
<1-3 sentences>

## Why it matters
<concrete impact>

## Affected code
- `src/downlow/path:line` — <what>

## Proposed fix
<recipe — concrete steps>

## References
- FUTURE_FIXES.md entry dated YYYY-MM-DD
- (PR/commit refs if mentioned in original)
EOF
=== END ISSUE {{LETTER}}1 ===
```

If `SKIP: yes`:

```
=== ISSUE {{LETTER}}1 ===
SKIP: yes
SKIP_REASON: <one sentence>
=== END ISSUE {{LETTER}}1 ===
```

## Constraints

- Body 150-300 words for L1-L2 items, up to 500 for L3+, up to 600 for L4+ bundles.
- Bundles (entries with `### Ingest / ### Summarise` sub-sections, or numbered sub-items)
  → keep as ONE issue with `## Sub-items` checklist using `- [ ]` markdown checkboxes.
- Don't narrate your investigation in the issue body — write it as if it's a fresh issue.
- If the fix is partially applied, add a one-line `## Status (YYYY-MM-DD)` section noting
  what's still outstanding.
- For pure research/UX/pipeline proposals (no live bug), skip verification and produce
  the issue from the FUTURE_FIXES.md text directly.
- **Don't read whole files.** `Read offset+limit` (max 60 lines) or `Grep`. Never
  `Read` a file >100 lines without `offset+limit`.
- **Do not invoke other agents.**
- Output cap: total response under {{TOKEN_CAP}} tokens. Be terse and direct.
