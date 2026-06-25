# DownLow — UI Design System (Phase 4)

Authoritative visual identity, design tokens, motion language, and key-surface layout specs for DownLow's frontend. This is the `deeptech-brand-architect` deliverable that turns `docs/ui_plan.md` (the components/interaction plan) into a concrete, Tailwind-friendly system for `frontend-engineer` to implement.

**Chosen direction: "Late Show" — deep-tech tuned.** A warm-dark radio-studio spine for the library and player, with **ember = host / teal = author** functional voice-coding, the **player as protagonist**, and **warm-light reading discipline** on the summary/PDF surfaces. The original Late Show sketch has been pulled materially closer to the deep-tech benchmark guides (`.claude/website_design_examples/design_notes.md`) so DownLow reads as a *credible deep-tech instrument*, not a consumer media app — without losing the broadcast warmth that makes it "a show about your paper."

> **The governing tension, resolved.** Linear-grade restraint applies to **everything by default**: one accent per surface, flat-over-glassy, no gradients-as-decoration, near-monochrome chrome, type does the work. The warm broadcast personality is **earned, scoped, and functional** — it lives in exactly three places: (1) the **player** (the protagonist), (2) the **ember/teal voice system** (information, not decoration — you can *see* the conversation), and (3) the **first-play "cold open" moment** (the one signature flourish). Everywhere else, DownLow behaves like Supabase or Linear: quiet, dense, confident.

---

## 0. Design principles (the non-negotiables)

1. **Restraint is the default; warmth is earned.** One accent does one job per surface (Linear, Supabase, Cloudflare). The page is near-monochrome until the player or the voice system needs to speak.
2. **The product is the marketing and the marketing is the product.** No stock art, no illustration, no decorative gradient. The library grid, the player, and the transcript ARE the visual identity (Linear, Observable, Palantir).
3. **Two reading temperatures, one system.** The *library + player* are warm-dark (the studio). The *summary + PDF* are warm-light editorial reading surfaces (Anthropic). Same tokens, same type, swapped canvas — one decision, not two designs.
4. **Colour is information.** Ember and teal are *never* decorative. They mean host and author, consistently, everywhere — waveform, scrubber, transcript, live indicator, speaker label. Status colour is always paired with an icon + word (never colour-only).
5. **Flat over glassy.** No glassmorphism, no drop-shadow stacks, no neumorphism. Surfaces are separated by a single hairline and a 1-step elevation in background tone (Linear, Supabase, Vercel).
6. **Type does the work.** A serif/sans editorial split (Anthropic, W&B) plus mono for every number and label. Three families, each with a defined register.
7. **Tabular numerics, always.** Every timestamp, duration, page count, percentage, star count is `tabular-nums`. This single discipline is the cheapest credibility signal there is (Linear).
8. **Motion explains or it's cut.** 200ms expo-out for micro-interactions; one shared-layout morph for the player; one cold-open flourish. Everything respects `prefers-reduced-motion` first.

---

## 1. Palette

DownLow runs **two canvases from one token set**. The "studio" (dark) is primary for the library and player; the "page" (light) is primary for reading. Both ship at full fidelity. All colours are warm — there is **no blue-black, no cool grey** anywhere in the system. That is the deliberate escape from the infra-SaaS cliché.

### 1.1 Studio (dark) — library, player, app shell

| Token | Hex | Role |
|---|---|---|
| `--canvas` | `#16130D` | App background. Warm charcoal with brown in it — "on air at midnight," never blue-black. |
| `--surface` | `#1E1A12` | Cards, the player bar, panels. One step up from canvas. |
| `--surface-raised` | `#272117` | Hover/active card, expanded player, popovers. Two steps up. |
| `--hairline` | `#352D20` | The *only* border. 1px, warm. Separates surfaces — no shadows do this job. |
| `--ink` | `#F2ECDD` | Primary text. Warm bone, not pure white (pure white is harsh on warm-dark — cf. Scale, Raycast). |
| `--ink-muted` | `#A99E86` | Secondary text, metadata, inactive labels. |
| `--ink-faint` | `#6E654F` | Tertiary — captions, disabled, ticks, axis marks. |

### 1.2 Page (light) — summary reader, PDF frame, settings prose

| Token | Hex | Role |
|---|---|---|
| `--canvas` | `#FAF7EF` | Reading background. Warm parchment (Anthropic cream lineage), not white. |
| `--surface` | `#FFFFFFEE` | Reading cards, callouts, sticky TOC. |
| `--surface-raised` | `#F2ECDD` | Active/hover, code blocks, the relevance callout fill. |
| `--hairline` | `#E4DCC9` | The single border, warm. |
| `--ink` | `#1B1710` | Body text — contrast 13:1 on `--canvas` (AAA; reading is the job). |
| `--ink-muted` | `#6B6453` | Secondary. Contrast ≥ 4.5:1. |
| `--ink-faint` | `#9A917A` | Captions, provenance line, ticks. |

### 1.3 The voice system (functional — host vs author)

These are the **only chromatic colours in the entire product**, and they carry meaning. They are tuned to read on both canvases.

| Token | Studio hex | Page hex | Role |
|---|---|---|---|
| `--host` (ember) | `#F2792B` | `#C2570F` | **Host.** Now-playing crest, host scrubber bands, host transcript rule, "on air" pulse, primary CTAs, progress bars, active nav. The brand ember. |
| `--host-weak` | `#F2792B22` | `#C2570F1A` | Host band fill, hover wash, focus ring backing. |
| `--author` (teal) | `#52C6BA` | `#0E7C73` | **Author.** Author scrubber bands, author transcript rule, author live indicator. *Only* appears where the two-speaker distinction is live. |
| `--author-weak` | `#52C6BA22` | `#0E7C731A` | Author band fill. |

> **Discipline rule (this is what keeps it deep-tech, not consumer).** Ember is the single brand accent and does the Linear/Supabase "one accent, one job" work across the whole app — CTAs, progress, active states. **Teal is not a second brand colour.** It appears *only* alongside ember in a two-speaker context (scrubber, transcript, live indicator). You will never see teal on a button, a link, or a generic active state. This keeps the page near-monochrome+ember everywhere except where the conversation itself is being shown — exactly the restraint of Supabase's single green, with one principled exception for the product's core idea.

### 1.4 Semantic status (pipeline honesty)

Always rendered with **icon + word + colour** — never colour alone (WCAG; `ui_plan.md` "failed ≠ not-yet-run"). Desaturated to sit on warm canvases.

| Token | Studio | Page | Meaning |
|---|---|---|---|
| `--ok` | `#6BBF77` | `#2F7A45` | succeeded / ready / cache-hit |
| `--warn` | `#E0A92E` | `#9A6B12` | running / buffering / re-summarise nudge |
| `--crit` | `#E2603F` | `#B23A24` | failed (with retry affordance) |
| `--idle` | `--ink-faint` | `--ink-faint` | not-yet-run / skipped |

### 1.5 Grey ramp (warm neutrals)

A single warm ramp underlies both canvases (stone, never slate). Implementation: define studio + page sets as CSS variables on `:root` / `[data-theme]`; never reference raw hex in components.

```
stone-950 #16130D  stone-900 #1E1A12  stone-800 #272117  stone-700 #352D20
stone-600 #4A4030  stone-500 #6E654F  stone-400 #A99E86  stone-300 #C9BFA6
stone-200 #E4DCC9  stone-100 #F2ECDD  stone-50  #FAF7EF
```

### 1.6 What is banned

No gradients as decoration (the only gradient permitted is the player's *amplitude-driven* waveform fill). No glassmorphism / backdrop-blur as a style. No second brand accent. No cool greys. No drop-shadow elevation stacks (hairline + tone step only). No pure black, no pure white.

---

## 2. Typography

A three-register editorial system: **serif for long-form reading**, **sans for UI and display**, **mono for every number and label**. This is the Anthropic serif/sans split + the W&B "serif headline repositions an ML tool as research-grade" move + Vercel/PlanetScale's mono-for-engineers discipline, fused.

### 2.1 Families

| Role | Family | Fallback stack | Notes |
|---|---|---|---|
| **Display + UI** | **Söhne** (or **ABC Diatype** / open: **Inter Variable**) | `'Söhne', 'Inter', system-ui, sans-serif` | The grotesque workhorse. Nav, buttons, card titles, headings. Self-hosted, subset. Inter is the no-licence fallback (Linear/Cloudflare prove it's enough). |
| **Long-form reading** | **Source Serif 4** (or **Lyon Text**) | `'Source Serif 4', Georgia, serif` | The summary body **only**. This is the W&B/Anthropic signal: the summary reads like a paper, because it is about one. |
| **Mono — numbers + labels** | **Berkeley Mono** (open: **Geist Mono** / **JetBrains Mono**) | `'Berkeley Mono', 'Geist Mono', ui-monospace, monospace` | Timestamps, durations, page numbers, percentages, status chips, shelf labels (`JUMP BACK IN`), the "on air" super, provenance lines. The PlanetScale/Observable engineer signal — used as supers, not body. |

Three families maximum. Self-host all; subset to used glyphs; load non-render-blocking with `font-display: swap` guarded against CLS (size-adjust matched fallbacks).

### 2.2 Type scale (modular, ~1.25)

Tailwind-mappable. Display uses tight tracking; body uses generous leading.

| Token | Size / line-height | Tracking | Family | Use |
|---|---|---|---|---|
| `display-xl` | 56 / 60 | -0.03em | Sans 600 | Hero / first-run only |
| `display-l` | 40 / 44 | -0.03em | Sans 600 | Section bridge headlines |
| `title-l` | 28 / 34 | -0.02em | Sans 600 | Paper detail header |
| `title-m` | 22 / 28 | -0.02em | Sans 600 | Now-playing title, panel titles |
| `title-s` | 18 / 24 | -0.01em | Sans 600 | Card titles |
| `body-l` | 18 / 30 (1.66) | 0 | **Serif** | Summary body |
| `body-m` | 16 / 26 (1.62) | 0 | Sans | UI body, descriptions |
| `body-s` | 14 / 22 | 0 | Sans | Secondary UI |
| `label` | 12 / 16 | 0.08em UPPER | **Mono** | Shelf labels, section supers, status chips |
| `meta` | 13 / 18 | 0 | **Mono** | Timestamps, durations, authors·year, counts (`tabular-nums`) |
| `caption` | 12 / 16 | 0 | Mono | Provenance, ticks, axis marks |

**Reading discipline.** Summary body capped at **66ch**, `body-l` serif at 1.66. Hedging preserved typographically (a qualitative finding is set in regular serif prose, never as a pseudo-metric). The PDF pane owns its own width (exempt).

**Tabular numerics rule.** `font-variant-numeric: tabular-nums` is set globally on `.meta`, `.caption`, `.label`, and every transport/scrubber number. No exceptions.

---

## 3. Spacing, density, radius, elevation

### 3.1 Spacing scale (4px base)

`4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 · 96 · 128`. Arbitrary values are bugs. Tailwind defaults already match; we restrict to these steps.

### 3.2 Density posture

**Medium-dense — denser than the original Late Show sketch, closer to Linear/Supabase.** The original sketch leaned consumer-large on cards; deep-tech tuning tightens it:

- Library cards: cover + 3 tight text rows + one action row. Cover aspect ratio **4:5** reserved (no CLS). Grid gap `16`.
- The list (density toggle) is a true data row — `meta` mono, scannable at 11pm with forty tabs (the PlanetScale/Linear table discipline).
- Player resting bar: **64px** tall — quiet and dense, not a consumer mega-bar.
- Reading surfaces: generous — `64`–`96` vertical rhythm, 66ch measure. Density is for browsing; space is for reading.

### 3.3 Radius

| Token | Value | Use |
|---|---|---|
| `radius-sm` | 6px | Chips, status pills, inputs |
| `radius-md` | 10px | Cards, buttons, the player bar |
| `radius-lg` | 16px | Expanded player, dialogs, sheets |
| `radius-full` | 9999px | Avatars, the live "on air" dot, scrubber thumb |

Consistent, modest radii — not pill-everything (consumer tell), not sharp-everything (defence cosplay). 10px is the DownLow default.

### 3.4 Elevation (flat-over-glassy)

There are **only three elevation levels**, expressed as background-tone steps + the single hairline. No coloured shadows, no blur.

- **0** — canvas.
- **1** — `--surface` + `--hairline` (cards, player bar).
- **2** — `--surface-raised` + `--hairline` + one soft shadow `0 8px 24px rgb(0 0 0 / 0.28)` (studio) / `0 8px 24px rgb(60 50 30 / 0.10)` (page). Reserved for the expanded player, dialogs, popovers — things that float *above* the app.

---

## 4. Motion language (Framer Motion)

The benchmark lesson is overwhelming: the best deep-tech sites use **almost no JS animation** (Linear, Vercel, Supabase, PlanetScale = CSS-only or near-it). DownLow follows suit. Framer Motion earns its place in exactly two structural jobs; everything else is CSS transitions.

### 4.1 The four primitives

| Primitive | Spec | Where |
|---|---|---|
| **`microEase`** | 180–220ms, `cubic-bezier(0.16, 1, 0.3, 1)` (expo-out) | All hover/press/focus, tab switches, chip toggles. CSS transitions, not Framer. |
| **`enter`** | opacity 0→1 + translateY(8px)→0, 240ms, expo-out, stagger 40ms | Card grids, list rows, panel mounts. Framer `whileInView` once; never on every scroll. |
| **`playerMorph`** | shared-layout (`layoutId`) spring, `stiffness 320, damping 34` | **The one signature motion.** Resting bar ⇄ expanded now-playing morph as a single continuous element (cover, title, scrubber, controls share `layoutId`s). Never a remount. |
| **`coldOpen`** | play-button press: scale 0.96→1 spring (`stiffness 500, damping 22`); waveform amplitude fade-in over 600ms; speaker indicator settles | **The one flourish.** First-ever play only emphasises; subsequent plays use a lighter version. |

### 4.2 Restraint rules (where Linear-grade discipline applies)

- **No ambient motion** anywhere in the chrome. (The original sketch allowed a 4% glow behind the expanded player — **removed**; it read consumer. The expanded player earns presence through tone + the live waveform, not a glow.)
- **No scroll-jacking, no parallax, no marquee** in the app.
- **The waveform** is the *only* continuously-animating element, and only while playing. It is amplitude-driven (real information), ember-crested, ≤ 30fps, and pauses when paused. Reduced-motion → a static segmented bar that still reflects position.
- **Status transitions** (a stage flipping pending→running→succeeded) cross-fade colour+icon over `microEase` — explanatory, not celebratory. The exception: the **first paper ever reaching "Ready to listen"** gets one acknowledgement (a single `coldOpen`-class beat), once, then never again.
- **`prefers-reduced-motion` is checked first, every time.** Every animation has a defined static end-state. The scrubber still updates; the player still works; `enter` becomes an instant opacity set.

### 4.3 What the player must do (motion-wise)

- Resting ⇄ expanded = `playerMorph` (shared layout). The user must perceive *one* object growing, not two views swapping.
- The live speaker indicator switches host↔author on turn boundaries with a 160ms colour cross-fade (ember↔teal) — no pulse-spam; a single soft pulse only on the active dot.
- Scrubber drag commits on release (rAF while dragging, off the global render path — `ui_plan.md` INP rule).

---

## 5. Iconography

- **Set:** a single thin line set (1.75px stroke, rounded joins) — Lucide is the pragmatic default (open, complete, matches the grotesque). Subset to used icons.
- **Transport is the exception:** play / pause / skip-turn / ±15s use **filled, slightly heavier glyphs** (the one broadcast cue) so the player's controls read as a console, not as generic UI. ≥ 44×44 hit targets.
- **Labels often replace icons** in the deep-tech register: a status chip says `READY` in mono, not just a checkmark — though it carries both (colour + icon + word). Shelf supers (`JUMP BACK IN`) are mono text, never iconified.
- No duotone, no filled decorative icons, no emoji as identity.

---

## 6. Light / dark stance

- **Per-surface canvas, not a global toggle.** The library, player, and shell are **studio (dark) by default**. The summary reader and PDF frame are **page (light) by default** — because reading long-form on warm-light is materially better and is the daily loop. This is the Anthropic diptych applied *across surfaces* rather than within one hero.
- A user theme override exists (Settings → studio-everywhere / page-everywhere / auto), but the *default* is the diptych: dark studio, light reading.
- The player bar is always studio-toned even when docked beneath a light reading surface — it is the constant "on air" spine. The hairline above it separates the two temperatures cleanly.
- Both temperatures meet contrast targets: body ≥ 4.5:1 (reading body ≥ 7:1, AAA-leaning), large/display ≥ 3:1, ember/teal on their canvases ≥ 4.5:1 for the text/icon uses, ≥ 3:1 for the band fills.

---

## 7. Key-surface layout specs

ASCII layouts are schematic, not pixel-exact. Studio surfaces are warm-dark; the summary reader is warm-light.

### 7.1 App shell (the constant)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  ◆ DownLow                                   ⌘K  Search          ◐  ⚙      │  TopBar  56px  studio
├────┬───────────────────────────────────────────────────────────────────────┤
│ ☰  │                                                                       │
│Libr│                                                                       │
│Srch│                      <Outlet/>  — route views                         │  SideNav 200px (icons+label)
│Set │                      (studio for library, page for reading)           │  collapses to 64px / bottom-tabs mobile
│    │                                                                       │
├────┴───────────────────────────────────────────────────────────────────────┤
│ ▓  "Out-of-distribution generalisation" — interview   ● HOST  02:14 ─●── ⤢ │  PlayerBar 64px  ALWAYS studio
└──────────────────────────────────────────────────────────────────────────┘
```
- TopBar: wordmark + mark (left), `⌘K` search trigger (centre-right, a quiet pill — Linear's ghost-nav restraint), theme + settings (right). One CTA inversion max, ember.
- SideNav: three items + the global "Add a paper" affordance. Active item marked by an **ember left-rail** (2px) + ink — single-accent active state.
- **The player lives outside `<Outlet/>`** (the foundational requirement) — it survives every navigation. Always studio-toned.

### 7.2 Library / Home (studio — the lineup)

Shelf-first, denser and more restrained than the original sketch. Mono shelf supers; near-monochrome cards; ember only on progress + the now-playing card.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ JUMP BACK IN                                                    (mono super)│
│ ┌────────────┐  ┌────────────┐  ┌────────────┐                             │
│ │  ▓ cover ▓ │  │  ▓ cover ▓ │  │  ▓ cover ▓ │   4:5 reserved, no CLS      │
│ │            │  │            │  │            │                             │
│ │ Out-of-dis…│  │ Sparse Att…│  │ Scaling La…│   title-s sans              │
│ │ MEHRNIA·24 │  │ CHEN·23    │  │ KAPLAN·20  │   meta mono                 │
│ │ ●ON AIR    │  │ paused     │  │ read 64%   │   ember dot only on now-play│
│ │ ▬▬▬▬▬░ 12:41│  │ ▬▬░░░ 04:10│  │ ▬▬▬▬░ ──   │   ember progress, tabular   │
│ └────────────┘  └────────────┘  └────────────┘                             │
│                                                                            │
│ READY TO LISTEN                                                            │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│ │ ▓cover▓  │ │ ▓cover▓  │ │ ▓cover▓  │ │ ▓cover▓  │   hover → ember         │
│ │ title……  │ │ title……  │ │ title……  │ │ title……  │   hairline lights,      │
│ │ AUTHOR·24│ │ AUTHOR·23│ │ AUTHOR·20│ │ AUTHOR·24│   cold-open ~6s,         │
│ │ ◷08:12 ▶ │ │ ◷09:03 ▶ │ │ ◷07:40 ▶ │ │ ◷08:55 ▶ │   one at a time, opt-out │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘                       │
│                                                                            │
│ YOUR LIBRARY   [Focus area][Needs a listen][Processing]   sort▾   ▦ ▤      │
│ ──┬─────────────────────────────────────────┬───────────┬──────┬─────────  │
│ # │ TITLE                                    │ AUTHOR·YR │ DUR  │ STATUS    │  density toggle → table
│ 01│ Out-of-distribution generalisation……… │ MEHRNIA·24│08:41 │ ●READY    │  mono, scannable
│ 02│ Sparse attention is all you……………………… │ CHEN·23   │ ──   │ ⟳ SUMM 60%│  icon+word+colour
└──────────────────────────────────────────────────────────────────────────┘
```
**Deep-tech shifts from the sketch:** uppercase mono shelf supers (was title-case); ember restricted to progress + the single now-playing dot (was ember edges everywhere); hover lights the *hairline* in ember rather than igniting the whole card edge (Linear's spotlight restraint, not a consumer glow); the table view is a genuine data table for triage (PlanetScale/Linear). Status is always `icon + WORD + colour`.

**Card hover (the one expensive interaction):** a Linear-style mouse-tracking radial — `--host-weak` (≈8% ember) at the cursor, fading over 180px, on `--surface` → `--surface-raised`. Plus the cold-open audio preview (first ~6s, one at a time, opt-out). The card does not lift or shadow; it warms.

### 7.3 Paper detail hub (diptych — studio header, page reading)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ← Library                                                          studio   │
│ An interview with the author of                                            │
│ "Out-of-distribution generalisation in machine learning"      title-l       │
│ M. Mehrnia · 2024 · 14 pp · ◷ 08:41                            meta mono     │
│ ┌─ stage strip (only when non-terminal / failed) ───────────────────────┐  │
│ │ INGEST ✓  SUMMARISE ✓  RENDER ⟳ 40%  NARRATE …  STORE …   [retry]     │  │  honest, derived
│ └────────────────────────────────────────────────────────────────────────┘  │
│ ┌─────────┬──────────┬──────────┐                                          │
│ │  PDF    │ SUMMARY● │ PODCAST  │   tabs (deep-linked, per-pane memory)     │  ember underline = active
│ └─────────┴──────────┴──────────┘                                          │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│          (SUMMARY tab → switches canvas to PAGE / warm-light)              │  ← the diptych moment
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘
```
The header + tabs are studio; selecting **Summary** transitions the content canvas to **page** (warm-light) with a 200ms cross-fade of the canvas variable — the reader literally warms up for reading. PDF tab keeps a calm light frame too. Podcast tab stays studio (it's player territory). The docked player keeps playing across all three (signature moment: read-while-listening).

### 7.4 The persistent player — RESTING (studio, 64px)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ▓ │ "Out-of-distribution generalisation" — interview   ● ON AIR · HOST    │
│cov│ ◀◀turn  ◀15  ⏸  15▶  turn▶   02:14 ──●──────────── 08:41   1.0×  ↕  ⤢ │
└──────────────────────────────────────────────────────────────────────────┘
        └ filled transport glyphs   └ tabular mono times   └ queue  └ expand
```
- One line. Cover (40px, `radius-md`), title (truncated, sans), the `● ON AIR · HOST` super in **mono**, with the dot **ember** (host) / **teal** (author) live-coded to the current turn.
- Transport filled glyphs; ±15s and ±turn both present; speed; a thin time-scrubber (turn-segmented when per-turn timing exists — see §7.6); queue + expand.
- Quiet by default: near-monochrome bar, ember only on the playhead + the live dot. This is the Supabase "accent does one job" rule applied to the spine.

### 7.5 The persistent player — EXPANDED (studio, the protagonist)

`playerMorph` grows the bar upward into a `radius-lg`, elevation-2 panel. The host↔author **turn scrubber** is the centrepiece and is the one place teal earns its presence.

```
┌─ NOW PLAYING ─────────────────────────────────────────────── ⤡ collapse ──┐
│                                                                            │
│  ┌────────┐   "Out-of-distribution generalisation"        title-m          │
│  │ ▓▓▓▓▓▓ │   an interview with M. Mehrnia · 08:41        meta mono         │
│  │ cover  │   ● HOST speaking                              live, ember      │
│  └────────┘                                                                │
│                                                                            │
│   ◀◀turn   ◀15   ⏸   15▶   turn▶                0.8× 1.0× 1.5× 2.0×        │
│                                                                            │
│   HOST ████░░░░░░  AUTHOR ░░░░░░██████░░  HOST ░░██  AUTHOR ░░░░████        │
│        ember           teal                 ember        teal              │  turn-aware scrubber
│   00:00          ▲02:14                                          08:41      │  tabular mono
│                  └ hover any band → speaker + first words of that turn      │
│                                                                            │
│   TRANSCRIPT  (follow-along, current turn lit; tap any turn to seek) ────── │
│   [02:01] HOST    wait, back up — what does "drifts" mean for my app?       │  host: ember rule (left)
│ ▸ [02:14] AUTHOR  Great question. Imagine it only ever saw huskies in snow… │  author: teal rule, lit
│   [03:40] HOST    huh — so it learned the *background*, not the dog.        │
└────────────────────────────────────────────────────────────────────────────┘
```
- **The scrubber as conversation map.** Host bands fill `--host-weak` with an ember top-edge; author bands `--author-weak` with a teal top-edge. You can *see* the rhythm of the interview — short host beats, long author turns — at a glance. The playhead is a single ember/teal thumb (coloured by the current speaker). This is the functional payoff of the two-colour system and the heart of "a show, not a TTS read-aloud."
- **Transcript = follow-along.** Chat-style turns; host turns carry a 2px ember left-rule, author turns a 2px teal left-rule; the current turn is lit (`--surface-raised` + full-opacity rule). Tap-to-seek. Until per-turn timing lands, transcript is untimed and the scrubber is a plain time-scrubber — **zero rearchitecture later** (the store already holds `turns`).
- **A11y:** scrubber is an ARIA slider with `aria-valuetext` = "2:14, author speaking"; a live region announces speaker/turn changes; Space/arrows operate everything; transport ≥ 44×44.

### 7.6 Turn scrubber — data gating (honest about what ships)

- **v1 (no per-turn offsets yet):** plain ember time-scrubber + untimed transcript. The player is fully functional; the conversation-map visualisation is dormant.
- **v1.1 (NARRATE mixer emits `start_ms`/`end_ms`):** the same scrubber lights up into the host/author banded map; transcript gains timestamps + tap-to-seek; hover snippets appear. No frontend rearchitecture — purely data arriving.

### 7.7 Summary reader (page — warm-light editorial)

The diptych's light half. Anthropic/W&B reading discipline: serif body, parchment canvas, 66ch, the relevance callout pulled to the top.

```
╭──────────────────────────────────────────────────────────────────────────╮   page (warm-light)
│                                                                            │
│  ┌── WHY THIS MATTERS TO YOUR WORK ─────────────────────────────────────┐ │  relevance callout
│  │ For your focus on distribution shift in deployed vision models, this   │ │  ember left-rule,
│  │ paper's snow-vs-husky failure mode is directly relevant: it…           │ │  --surface-raised fill
│  └────────────────────────────────────────────────────────────────────────┘ │  (the differentiator)
│                                                                            │
│  Overall                                                       title-m sans  │
│  The authors investigate whether models retain accuracy when the test      │  body-l SERIF, 66ch, 1.66
│  distribution drifts from training, without retraining…                    │
│                                                                            │
│  Key findings                                                              │
│  — Models latch onto spurious background cues (quantitative, with metric)  │  metric → tabular mono
│  — Performance degradation is uneven across subgroups (qualitative)        │  no metric → plain serif,
│                                                                            │     hedging preserved
│  Contributions · Methods · Gaps & limitations …                            │
│                                                                            │
│  ────────────────────────────────────────────────────────────────────────  │
│  claude-sonnet-4-6 · prompt v3 · summarised 24 Jun           caption mono   │  quiet provenance
╰──────────────────────────────────────────────────────────────────────────╯
   ┌─ player stays docked (studio) beneath — read-while-listening ──────────┐
```
- **Relevance callout first**, naming the active profile — the steering differentiator, given the strongest position (ember left-rule, raised fill, but calm).
- **Hedging is typographic:** a `KeyFinding` with `evidence: None` renders as qualitative serif prose; only findings with real evidence get a mono metric. The UI never manufactures certainty (the `academic-writing-advisor` bar).
- Sticky mini-TOC (mono labels) in the left margin on wide viewports. Provenance line quiet at the foot.

---

## 8. Component token cheat-sheet (for `frontend-engineer`)

| Component | Key tokens / behaviour |
|---|---|
| `Button` (primary) | `--host` bg, `--canvas` text, `radius-md`, `microEase` press scale 0.98. One per view. |
| `Button` (ghost) | transparent, `--hairline` border, `--ink` text. The default button. |
| `StatusBadge` | `radius-sm`, mono `label`, icon + word + semantic colour. Never colour-only. |
| `PaperCard` | `--surface`→`--surface-raised` on hover, mouse-tracked `--host-weak` radial, hairline-lights-ember, 4:5 cover reserved, ember progress bar. |
| `PlayerBar` | studio always, 64px, elevation-1, `layoutId` shared parts, ember/teal live dot. |
| `NowPlaying` | elevation-2, `radius-lg`, the banded scrubber, follow-along transcript. |
| `TurnScrubber` | ember (host) / teal (author) bands, single speaker-coloured thumb, ARIA slider. |
| `RelevanceCallout` | `--surface-raised`, ember 2px left-rule, page canvas, serif body. |
| `Tabs` | ember underline active, `microEase`, deep-linked, per-pane memory. |
| `Skeleton` | `--surface` shimmer over `--surface-raised`, never a spinner (`ui_plan.md`). |
| `EmptyState` | teaching, mono label + one sans line + one action — never a void. |

---

## 9. Deep-tech influences applied (traceable lineage)

Per-entry from `design_notes.md`, what was pulled and how Late Show shifted to absorb it.

- **Linear** — *extreme restraint + product-as-hero + one-accent-one-job.* Late Show's ember became the **single brand accent doing all CTA/progress/active work**; teal was demoted from "second brand colour" to "functional voice code only." Card hover became Linear's mouse-tracked radial spotlight (warming the hairline) instead of a consumer edge-glow. Adopted CSS-keyframe-first motion (Framer reserved for two structural jobs). Adopted `tabular-nums` everywhere.
- **Anthropic** — *warm cream editorial canvas + serif/sans diptych + zero colour accents in chrome.* Drove the **two-temperature system**: studio-dark for the library/player, warm parchment `#FAF7EF` + serif body for the reading surfaces. The Summary tab switching the canvas to page is a literal diptych-across-surfaces. Restricted chrome colour to near-monochrome+ember.
- **Raycast / Scale** — *warm/near-black body, muted-bone text not pure white.* Studio canvas is warm charcoal `#16130D`; primary text is bone `#F2ECDD` (pure white rejected as harsh on warm-dark).
- **Supabase** — *disciplined dark theme, single green doing exactly one job.* The model for ember discipline: one accent, action-forward, everything else neutral dark. Confirmed the dark-developer-tool register can be warm and credible at once.
- **W&B (Weights & Biases)** — *serif headline repositions an ML tool as research-grade; warm yellow on dark instead of cold ML-blue.* Validated the serif reading body and the warm-accent-over-cold-accent thesis — DownLow's ember/parchment is the same "serious researchers, not humourless ones" move.
- **Observable** — *the product (live notebook) IS the hero; mono section headers as cells.* The library grid, scrubber, and transcript are DownLow's visual identity — no illustration. Mono shelf supers + section labels are the "looks like a research instrument" cue.
- **PlanetScale / Vercel** — *mono-for-engineers; prose/data-table over icon-bullets.* The library density-toggle table and all metadata use mono; the engineer-credible register. Self-hosted brand-grade type as a signal (Geist lineage → Söhne/Berkeley Mono).
- **Palantir / Anduril** — *wordmark-only confidence, product-as-hero, zero decorative chrome.* Justified killing the original sketch's ambient glow and any decorative gradient; the player earns presence through tone + the amplitude waveform, not effects.
- **Cloudflare / Snowflake** — *single keyword/operator colour accent within type.* Informs the `● ON AIR · HOST` super and the ember/teal dot — colour embedded in a mono label as a brand moment, not a separate decorative element.
- **Flat-over-glassy (collective: Linear, Vercel, Supabase, Databricks — none use glassmorphism).** Elevation is tone-step + hairline + (only at level 2) one soft shadow. No backdrop-blur, no neumorphism.

---

## 10. Brand voice + logo concept (brief)

### 10.1 Voice

Calm, specific, engineer-to-engineer, with a quiet warmth borrowed from the host. No urgency, no exclamations, no AI-startup hype. Numbers are concrete. The product describes what it *does*, never what it'll "revolutionise."

- **Do:** "An interview with the author of *X*." · "Why this matters to your work." · "Ready to listen — 8:41." · "Reused — cached."
- **Don't:** "Revolutionise how you read research!" · "AI-powered insights." · "Your groundbreaking paper."

Headline pattern: a declarative noun phrase + a concrete second clause. *"A show about your paper. Played from your own machine."*

### 10.2 Logo concepts (two, for selection — neither is a literal book/mic/soundwave)

1. **The turn-glyph (recommended).** Two stacked horizontal bars of unequal length — a short one (ember) above a long one (teal) — the exact visual grammar of the host/author turn scrubber. It *is* the product's core idea (a short question, a long answer; reading distilled to a conversation) reduced to two strokes. Constructible on a whiteboard; works in pure monochrome (the colour is optional emphasis); typesets inline beside the wordmark; the favicon is just the two bars. The mark and the scrubber are the same idea — maximal coherence.

2. **The descent mark.** A "D" whose counter is cut by a downward play-triangle — encoding *DownLow* (the name, the downward motion of distilling a paper to its essence) and *play* in one geometric letterform. Pure-monochrome, single-stroke constructible, more wordmark-fused than concept 1.

Wordmark: **Söhne 600, tracking -0.03em**, "DownLow" set tight; the mark sits to the left at cap-height. Deliver (on selection): black-on-transparent, bone-on-transparent, ember-on-canvas, favicon 32×32 (mark only), app icon, and a 1200×630 social lockup.

---

## 11. Implementation notes for `frontend-engineer`

- Define **two CSS-variable sets** (`:root` = studio default, `[data-surface="page"]` and a `[data-theme]` override) so canvas swaps are a single attribute, animatable via the `--canvas`/`--ink` variables. Components reference variables only — **no raw hex in TSX**.
- Tailwind: map the scale/spacing/radius/colour tokens in `tailwind.config` to the CSS variables (e.g. `colors.host: 'var(--host)'`). Restrict spacing to the §3.1 steps.
- Set `font-variant-numeric: tabular-nums` globally on `.meta/.label/.caption` and all transport/scrubber numerics.
- Framer Motion only for `enter` (whileInView once) and `playerMorph` (shared `layoutId`). Everything else = CSS transitions on `microEase`. Wrap all motion in a `prefers-reduced-motion` guard with defined static end-states.
- The waveform is canvas/SVG, amplitude-driven, ≤30fps, paused-when-paused, reduced-motion → static segmented bar.
- Reserve the 4:5 cover aspect-ratio box to prevent CLS in the grid; lazy-load PDF + audio surfaces; `<audio preload="metadata">` with HTTP Range.

---

*Source direction: `docs/ui_plan.md` (surfaces/interaction/state). Deep-tech lineage: `.claude/website_design_examples/design_notes.md`. Content-certainty presentation deferred to `academic-writing-advisor`; engineering to `frontend-engineer`. This document is the visual source of truth; it does not scaffold the app — Luke reviews before the build begins.*
