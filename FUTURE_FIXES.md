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
