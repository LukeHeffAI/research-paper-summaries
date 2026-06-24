# DownLow Podcast Design (NARRATE / F4)

> The audio summary is the centrepiece of DownLow. It is **not** an academic promo piece — it is a warm, genuinely curious **two-presenter interview** between a science-enamoured everyperson host and the paper's author, produced (voices + music + timing) into one mixed episode.

This document is the authoritative design for the **NARRATE** stage. `PROJECT_PLAN.md` references it. The script schema, mixer, and config below are designed now even though only single-paper ships first; multi-paper is architected in (§8).

---

## 1. The show & the host persona

A science-interview podcast. Each episode, the guest is the **author** of a research paper.

**The host** is a *science-enamoured everyperson*: reads widely, genuinely curious, clearly intelligent — but **not** an expert in this field. They love their job: chatting to scientists about topics that touch their life and the lives of people around them. This week, the author's paper happens to feed something the host is especially engrossed in.

**The dynamic (load-bearing):**
- **Obvious depth-asymmetry.** The host asks the simple, naive-but-sharp questions a fascinated listener would ask; the author answers with real expert depth, nuance, and caveats. The asymmetry shows in **turn length and vocabulary**, never in the host being foolish or the author condescending.
- **Curiosity-driven wandering.** Both may wander onto adjacent topics out of curiosity — bounded tangents that reveal the author's range and build the narrative that they are a deep expert — then return.
- **It must feel human and exciting**, not a lecture or a press release.

---

## 2. Craft principles (what makes it engaging)

Synthesised from interview-craft and science-comms research (Terry Gross / Fresh Air, Radiolab, Ologies, Hidden Brain, The Open Notebook, ASCB; see §9). These are the rules the script-generation prompt encodes.

**Principles**
1. **Lead with curiosity, not coverage** — the seeking is the entertainment; one answer opens the next question (Radiolab).
2. **The host is a proxy for the listener** — assume the audience knows nothing of the field; the host asks what they'd ask. The naivety is a feature: it gives the expert room to shine.
3. **"Smart people, simple questions"** (Ologies) — the naive-but-sharp question forces vivid, plain explanation.
4. **Translate, don't dumb down** — rigour + accessibility; make the research a story about human experience (Hidden Brain).
5. **Make it matter** — every thread answers the unspoken "why does this matter to me and people around me?"
6. **Listen, don't march** — questions visibly grow out of the previous answer (Terry Gross). A reacting script feels alive; a prepared-list script feels dead.
7. **Build an arc, not a list** — beginning (scene + stakes) -> middle (a shift / surprise / twist) -> end (an insight that closes the loop opened in the cold open).
8. **Warmth is the retention mechanism** — laughter early, specific reactions, rapport. Listeners forgive imperfect info; they don't forgive flatness.

**Techniques the script deploys**
- **Cold open**: drop the listener into the single most arresting moment (a startling fact, a "wait, *what?*" exchange, the human stake) *before* the intro music; then pull back to introduce.
- **Question patterns**: open & non-leading ("What did you find?" not "Did you find X?"); the naive-but-smart question ("wait, how does that even work?"); the simplify prompt ("explain it like I've never heard of it", "is there an analogy?", "a specific example?"); the "tell me more / why is that?" follow-up that pushes past the rehearsed answer; escalation (each question builds on the last).
- **Reaction / back-channel beats**: scattered, specific micro-reactions ("huh", "wow", "no way", laughter) — the audible signature of real listening. Always to a *specific* thing just said.
- **The "wait, back up" move** (Radiolab): when a concept gets dense, the host surfaces — "whoa, back up" — and asks the clarifying question the listener needs. The immersion-then-distance rhythm is the source of tension.
- **Analogy co-construction**: the author reaches for everyday analogies; the host tests/riffs ("so it's like...?"), confirming understanding.
- **Depth-asymmetry done well**: host = short turns, plain language, questions + reactions, occasional vulnerable "I always thought X — is that wrong?"; author = longer turns, nuance, caveats, gentle "great question — most people assume..." builds, never condescension.
- **Pacing**: alternate immersion (deep science) with surfacing (reaction, a joke, reflection); vary turn length — follow a dense explanation with a short, light host beat.
- **The close**: pay off the cold-open hook; land one resonant takeaway that changes how the listener sees their world. Not "thanks for coming on."

**Anti-patterns the script must avoid**
- Promo-piece tells: "your groundbreaking paper", reciting the abstract, listing credentials, the author pitching uninterrupted.
- Jargon dumps; the host nodding along to terms a layperson wouldn't get (if a term appears, the host stops it: "okay, what does that actually mean?").
- Flat / scripted Q&A with no link between topics and no reaction to answers.
- Fake, generic enthusiasm ("wow, amazing!") not tied to a specific thing.
- Host-too-smart: supplying the expert's answers, insider vocabulary, finishing their thoughts (collapses the asymmetry, steals the author's moment).
- Host monologuing: the host should be the *minority* of words.
- Expert condescension; rehearsed FAQ answers; no stakes / no arc.

---

## 3. The script schema (turns)

A direct generalisation of VTTD's `ScriptSegment` model (NARRATION/DIALOGUE/SFX/AMBIENT/PAUSE), retargeted to a multi-speaker interview with music. Stored as JSON on the `Episode` (the regenerable, inspectable source of the mp3 and the in-app transcript).

```python
SpeakerRole = Literal["host", "author"]   # future multi-paper: "author" generalises to a speaker id (see Sec 8)
TurnType    = Literal["speech", "pause", "music", "sfx"]

class Turn(BaseModel):
    type: TurnType
    # speech:
    role: SpeakerRole | None = None
    text: str | None = None
    tone: str | None = None          # delivery direction -> voice preset (e.g. "warm, curious", "measured")
    # pause:
    duration_ms: int | None = None   # beat for emphasis / breath
    # music | sfx:
    cue: str | None = None           # music: "intro" | "outro" | "sting" | "bed"; sfx: a description
    under: bool = False              # if true, layers UNDER following speech (a bed); else occupies its own time

class VoiceRef(BaseModel):
    role: SpeakerRole
    voice_id: str                    # FK into the Voice pool (stock now; cloned author voice in Phase 7)

class NarrationScript(BaseModel):
    episode_title: str
    voices: list[VoiceRef]
    turns: list[Turn]
    paper_content_hashes: list[str]  # the source paper(s) this was generated from (list for multi-paper)
    model: str
    prompt_version: str
```

Mapping from VTTD: `NARRATION`/`DIALOGUE` -> `speech` with `role`; `AMBIENT` -> `music`/`sfx` with `under=True`; `SFX` -> `sfx`; `PAUSE` -> `pause`; **new** `music` cue for intro/outro/transition stings (interview podcasts use a fixed theme, not generated horror ambience).

---

## 4. Example (abbreviated — shows the craft)

```
[speech host  | tone: hooked, fast]      "Okay so apparently the thing that decides whether your photo app
                                          knows it's a husky and not a wolf might be... the snow behind it.
                                          Not the animal. The snow."
[music intro  | cue: intro]              (theme stings, settles to a low bed)
[speech host  | tone: warm, welcoming]   "Welcome back. I'm here with the author of a paper I have not been
                                          able to stop thinking about all week. Thanks for coming on."
[speech author| tone: relaxed]           "Happy to be here."
[speech host  | tone: curious]           "Give me the one-sentence version - what were you chasing?"
[speech author| tone: measured]          "We wanted models to keep working when the test data drifts from
                                          what they trained on - without retraining them."
[speech host  | tone: naive-but-sharp]   "Wait, back up - 'drifts'. What does that actually mean for, like,
                                          my photo app?"
[speech author| tone: building, vivid]   "Great question. Imagine it only ever saw huskies in snow..."
[pause        | 600ms]
[speech host  | tone: delighted]         "Huh - so it learned the *background*, not the dog."
...
[speech host  | tone: landing]           "So next time my phone does something dumb, it might just be...
                                          looking at the snow."
[music outro  | cue: outro]
```

Note the cold open *before* the intro music, the "wait, back up", the specific reaction ("huh -"), the depth-asymmetry in turn length, and the close paying off the hook.

---

## 5. Script generation

- **Input (configurable; default = the WHOLE PAPER).** Generate the interview from the *full paper* by default — feeding the summary (which was itself made from the paper) loses signal. The summary path is built as a **configurable alternative** (cheaper) via `podcast.script_source = "paper" | "summary"`. The paper is sent to Claude **natively** (the `LLMClient` PDF-document path) by default.
- **Structured output + craft prompt.** A versioned `SYSTEM_PROMPT` encodes the host persona (§1) + the principles/techniques/anti-patterns (§2) and demands the `NarrationScript` JSON via `messages.parse` (mirrors VTTD's `script_adapter`). The one-paragraph distillation for the system framing: *write a warm, genuinely curious conversation - not a Q&A and not a promo; the host is a smart, widely-read everyperson who does not know this field and asks naive-but-sharp questions, reacts audibly, and uses "wait, back up" when it gets dense; the author answers with real depth, nuance, and everyday analogies, never condescending; the asymmetry lives in turn-length and vocabulary; open cold on the most arresting moment, build an arc with something at stake, allow curiosity-driven tangents that reveal the author's range, and close by paying off the hook with one insight that changes how the listener sees their world.*
- **Long papers.** Reuse SUMMARISE's section-split + carried-context + truncation-retry machinery; stream large outputs (`messages.stream`).
- **Cache** the generated script by `(input_hash, script_source, persona_version, prompt_version, model)`.

---

## 6. Audio production (the mixer, ripped from VTTD)

VTTD's `audio_mixer.py` ports almost wholesale (pure `pydub`). Pipeline: per-turn TTS -> mix -> one mp3.

- **Voices.** Map `host`/`author` turns to distinct stock ElevenLabs voices (Phase 1); the author voice becomes a cloned voice in Phase 7. `tone -> voice-preset` map (our own presets: e.g. `warm`, `curious`, `measured`, `excited`, `serious`) tunes ElevenLabs `stability`/`similarity`/`style` per turn. Merge consecutive same-speaker turns before TTS for natural flow (VTTD `_group_consecutive_segments`).
- **Music & SFX.** A small library of fixed assets (`intro` theme, `outro`, transition `sting`, optional low `bed`) under `$DATA_DIR/assets/audio/`, referenced by `cue`. SFX are optional and sparse (an interview rarely needs them). Music/bed assets are curated files, not generated; an ElevenLabs-SFX path remains available behind the TTS port for the rare cue.
- **The 3-layer mix (from VTTD):**
  - **Voice track** (foundation): speech + pause advance the playhead; **crossfade** consecutive voice turns (`CROSSFADE_MS`).
  - **Music/ambient bed** (underneath, low dB): `under=True` cues are looped to fill their span and fade between sections; they do not advance the playhead.
  - **SFX / sting layer** (overlay): placed at timeline positions with brief in/out fades; non-`under` stings occupy their own time.
  - Then **intro fade-in**, **outro fade-out**, **loudness normalise** to a target dBFS.
- **Mix constants (config-tunable; VTTD defaults as starting points):** `bed_volume_db = -22`, `sting_volume_db = -3`, `crossfade_ms = 120`, `intro_fade_ms = 2000`, `outro_fade_ms = 3000`, `inter_turn_gap_ms = 250`, `target_loudness_dbfs = -16`.
- **Per-segment cache** keyed by `(turn content, voice_id, preset)` so re-mixes skip unchanged TTS (VTTD `segment_cache`).
- **Ports:** `TTSClient.synthesize(text, voice, preset) -> bytes` and `AudioMixer.mix(rendered_turns, music_assets) -> bytes`; `pydub` + `ffmpeg` live only in the audio adapter. Fakes for tests.

---

## 7. Configuration (config file now, Settings UI later)

All the tunables above are **configurable**, per the owner's directive:
- **Now:** a non-secret **config file** (`config/downlow.toml`) provides initial values, loaded via `pydantic-settings`. Sections: `[podcast]` (`script_source`, target length / turn budget, persona text, `prompt_version`), `[voices]` (host + default author voice ids, `tone_presets`), `[mix]` (the constants in §6), `[music]` (asset paths). `core` receives typed config; never reads the file directly.
- **Later:** a DB-backed settings registry (a `Setting` table, the tipping-tools `SystemSetting` pattern: key/value, read-through cache, write-through) **seeded from the config-file defaults**, edited from a **Settings tab** in the UI. The config file remains the source of initial values / fallback.

This means a knob's lifecycle is: config-file default -> (later) DB override -> (later) UI control, with no code change when it graduates.

---

## 8. Multi-paper (architected now, single-paper ships first)

Single-paper is the only mode built now, but the schema must not assume it (multi-paper themed episodes are a certainty later):
- An **`Episode`** owns the script + audio and references **1..N papers** via an `EpisodePaper` join (with order). Single-paper = one join row.
- `NarrationScript.paper_content_hashes` is a list; `SpeakerRole`'s `"author"` generalises to a per-paper speaker id (each paper's author has their own voice). The mixer and turn model already handle N speakers.
- `PodcastAsset` belongs to the `Episode`, not directly to a `Paper`.

So enabling multi-paper later is a population + prompt change, not a schema rewrite.

---

## 9. Sources (podcast craft research)

- The Open Notebook — crafting effective interview questions (open/neutral questions, follow-ups, analogies).
- Writer's Digest & National Press Club — Terry Gross on curiosity, listening, arc, audience awareness.
- Wikipedia — *Ologies* ("smart people, stupid questions"; avoiding expert soundbites).
- WashU Ampersand — Radiolab (Abumrad/Krulwich) on the "whoa, wait" immersion/distance rhythm.
- ASCB — best practices in science communication (jargon, everyday analogies, relevance).
- Baird Media — "why most interview podcasts suck" (anti-patterns).
- Castos / The Podcast Host — 3-act structure, cold opens, tension/payoff.
