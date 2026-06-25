# DownLow — Web UI Plan (Phase 4)

Authoritative components + interaction + architecture plan for DownLow's frontend, synthesised from the `ux-design-advisor` (surfaces, interaction, signature moments) and `frontend-engineer` (component architecture, state, the API contract) scoping passes. This is the input to `deeptech-brand-architect` (which turns it into a layout + visual system) and the iterative build (`frontend-engineer` + `backend-engineer`).

**Product.** DownLow is a local-network "Spotify for research papers": per paper, the reader browses a **library**, reads the source **PDF in-app**, reads a context-steered **summary**, and plays a **two-presenter (host + author) interview podcast** through a **persistent player**. The archetypal user is a working researcher triaging at 11pm with forty tabs open — fast, trustworthy, and genuinely enjoyable. Single-user (Luke) over the LAN now; multi-user later.

**Stack (locked).** React 19 + Vite + TypeScript strict + Tailwind + Framer Motion, in `frontend/`, talking to a FastAPI `api/` layer that calls `core` services **unchanged** (ports/adapters). Three design seams: `ux-design-advisor` (interaction/usability), `deeptech-brand-architect` (visual identity / design system / motion), `frontend-engineer` (engineering). Content fidelity (summary/podcast) is `academic-writing-advisor`'s bar.

---

## 1. Foundations (must land before any delight — Walter's pyramid)

1. **The persistent player lives above the router.** A single `<audio>` element + the player store are mounted in `AppShell` above the route `<Outlet/>`, so navigating never resets playback. This is the defining UX; if audio stops on navigation, nothing else matters. (Also the Phase-4 spike that confirms React-vs-Jinja — de-risk first. Mine the owner's VTTD for the proven persistent-player behaviour, rebuild the React way.)
2. **Honest per-stage status.** Per-paper status is **derived** from the latest `PipelineRun` + its `StageRun` rows — `failed` ≠ `not-yet-run`. Every badge and progress strip reads one derived status DTO. A card that lies about processing breaks trust permanently.

### Three load-bearing data findings (both agents flagged independently)
- **The turn-aware scrubber has no data yet.** `NarrationScript.turns` carry no audio timestamps (only `pause.duration_ms`); the mp3 is the mixed product. The **NARRATE mixer must emit per-turn `start_ms`/`end_ms`** and persist them so the API can serve a *timed transcript*. Until then: ship a plain time-scrubber + untimed transcript; turn-sync + tap-to-seek light up later with **zero frontend rearchitecture** (the player store already holds `turns`).
- **Resume-position isn't persisted server-side.** `PlaybackState(user+paper, position)` is deferred. v1 persists position **client-side** (localStorage keyed by episode); `PUT /papers/{id}/playback` is an additive later endpoint.
- **Pipeline status is derived, not a column** → `GET /papers/{id}/status` assembles `{ runStatus, stages: {ingest|summarise|render|narrate|store: {status, cache_hit, error?, model_id?}} }` mapping 1:1 to `StageStatus`.

---

## 2. Surfaces (the component inventory)

Each surface below has a JOB (the 3-second answer), its key components, the load-bearing interactions, and its signature moment. Full UX detail (copy drafts, microinteractions, a11y, per-surface handoffs) lives in the `ux-design-advisor` pass; full component/data detail in the `frontend-engineer` pass.

1. **Library / Home** — JOB: "what should I read/listen to next?" Shelf-first (NOT a flat grid): **"Jump back in"** (resume reading + listening, progress bar on card) → **"Ready to listen"** (NARRATE done, never started) → the full collection. `PaperCard` = cover, title, authors, year, **derived StatusBadge**, quick-play. Saved-view chips ("My focus area" = active profile filter; "Needs a listen"; "Processing"), smart sort, density toggle. *Signature:* **cold-open audio preview on card hover/focus** (first ~6s, opt-out, one at a time) — the library *speaks*.
2. **Paper Detail (hub)** — JOB: "this one paper three ways without losing my place." Persistent paper header ("An interview with the author of *X*") + tabbed sub-routes **PDF · Summary · Podcast** (deep-linked), **per-pane position memory** (PDF page / summary scroll / playhead preserved across pivots), inline **retry-a-failed-stage** strip. *Signature:* **read-while-listening** — flip tabs while the docked player keeps playing.
3. **In-app PDF Reader** — JOB: "verify the source, keep my place." Embedded continuous-scroll viewer (lean on PDF.js/`react-pdf`, lazy-loaded; calm DownLow frame), page jump + outline, reading-position memory, `is_scanned` honesty note. *Signature:* **instant open** (<400ms perceived via skeleton → first page).
4. **Summary Reader** — JOB: "is this worth my attention — *and why, for me*?" The advisor's structure (overall → key findings → contributions → methods → gaps → relevance) with **"Why this matters to your work" (relevance_to_profile) pulled to the top** as a callout naming the active profile, **hedging preserved** (`KeyFinding.evidence: None` ⇒ render as qualitative, never as a hard metric), sticky mini-TOC, quiet provenance line (model + prompt_version). Honest disconnect reads as a disconnect. *Signature:* **the relevance callout landing** — one sentence written for the user's focus.
5. **The Persistent Podcast Player (signature surface — go deep)** — JOB: "keep listening, effortlessly, and resume exactly." Docked mini-bar ⇄ now-playing view; transport (play/pause = Space, ±15s, prev/next-turn, speed 0.8–2.0×); **turn-aware segmented scrubber** (host↔author bands; hover shows speaker + snippet) [needs per-turn timing]; **follow-along transcript** (chat-style turns, current highlighted, **tap-to-seek**); **resume-position**; **now-playing live speaker indicator** (host vs author by current turn `role`); queue ("Up next"); explicit states (loading/buffering/playing/paused/ended/error); **Media Session** for OS/lock-screen transport. *Signature:* **the first-ever play — the cold open landing** (springy play, breathing waveform, speaker indicator) — the moment DownLow becomes "a show about my paper," not a TTS read-aloud.
6. **Search** — JOB: "find that paper/finding/quote, fast + forgiving." Instant, debounced, deep-linkable, **typed/grouped results** (Papers / Findings / Transcript moments) where a transcript hit **drops into the player at that timestamp** and a finding hit links to the summary section; recent searches on focus; "did you mean". (v1 = title/author/summary; transcript→timestamp is mid-term, gated on per-turn timing + FTS5.)
7. **Add-paper + Processing status** — JOB: "add a PDF and watch it honestly become a summary + interview." Drag-drop/upload → **profile confirm** (smart default = active profile, recorded on the Paper) + **"skip audio" toggle** (CLI `--no-audio` parity) → **optimistic add** (paper appears as "Processing", keep browsing) → **per-stage strip** (INGEST→SUMMARISE→RENDER→NARRATE→STORE) from `StageRun` (pending/running/succeeded/failed/skipped + "Reused — cached"), **retry-from-failed-stage** (reuses cached upstream). **Dedup awareness** (`source_hash` → "you already have this paper"). *Signature:* **add→ready** — the strip fills, the card flips to "Ready to listen," first one offers "Play the interview."
8. **Settings / Profiles** — JOB: "tune how it summarises + sounds; manage my research identity." Single-column, auto-save. **Research-profile editor** (field/topic/interests[tags]/focus) is the centrepiece — it steers every summary; show "what this changes" + a post-edit "re-summarise N papers?" nudge. Separate **output-profile editor** (document_type, return_details). Podcast knobs graduate from the config file (`script_source`, target length, voices, speed). Reserve IA for **voice management + consent** (Phase 7). *Signature:* edit focus → see a summary's relevance callout change to match.
9. **Onboarding / First-run / Empty states** — JOB: "show me what DownLow is in one action." One-screen "set your research focus, then add a paper" (skippable, default profile); teaching empty library; **first-completion acknowledgement** (once: "Your first interview is ready. Press play."); contextual empty states everywhere (teach the next step, never a void). *Signature:* **the first interview is ready** — funnel everything toward making that arrive fast.
10. **App Shell / Nav / Cmd+K** — JOB: "always know where I am, reach anything in two keystrokes, never lose the audio." Global nav (Library / Search / Settings) + the **docked player always present** + **Cmd+K command palette** (jump to a paper, run "Add a paper" / "Play X" / "Go to settings", inline search); deep-linkable routes, back never breaks; global "Add a paper". *Signature:* Cmd+K → three letters → Enter → reading/playing, audio uninterrupted.

---

## 3. Component tree

```
<AppProviders>                       # QueryClientProvider + PlayerProvider + Router + ErrorBoundary + Toaster
└─ <AppShell>                        # grid: TopBar / SideNav / <Outlet/> / persistent <PlayerBar/>
   ├─ <TopBar>                       # logo, <SearchTrigger/> (Cmd+K), profile/settings menu
   ├─ <SideNav>                      # Library, Search, Settings (mobile = bottom tabs)
   ├─ <Outlet/>                      # route views render here — the PLAYER IS OUTSIDE this
   └─ <PlayerBar>                    # PERSISTENT compound: NowPlaying / Transport / TurnScrubber / Volume / QueueToggle→QueuePanel

Route views (lazy where heavy):
├─ <LibraryView>            "/"                 → LibraryToolbar, JumpBackInRail, ReadyToListenRail, PaperGrid→PaperCard→StatusBadge
├─ <PaperDetailView>        "/paper/:id"        → PaperHeader, PipelineStageStrip, PaperTabs
│   ├─ (lazy) <PdfReader>   "/paper/:id/pdf"
│   ├─ <SummaryView>        "/paper/:id/summary"→ OverallSummary, KeyFindingList(statement+evidence), ContributionList, MethodsBlock, LimitationsList, RelevanceCallout, MiniTOC
│   └─ <PodcastPanel>       "/paper/:id/podcast"→ TranscriptView (host↔author turns; play-from-turn)
├─ <SearchView>            "/search?q="
├─ <SettingsView>          "/settings"          → ResearchProfileEditor, OutputProfileEditor, (later) SettingsRegistry, VoiceManagement
└─ <AddPaperView|Dialog>   "/add"               → Dropzone, ProfilePicker, SkipAudioToggle, PipelineStageStrip

Shared primitives (headless Radix + Tailwind tokens from deeptech-brand-architect):
Button, IconButton, Slider(→scrubber/volume), Tabs, Dialog/Sheet, DropdownMenu, Tooltip,
StatusBadge/Pill, Card, Skeleton, EmptyState, ErrorState, Toast, ProgressStrip, Cover(reserved aspect-ratio), Avatar(host/author).
```

---

## 4. State model

- **Server state — TanStack Query.** Keys mirror the resource graph: `['papers', filters]`, `['paper', id]`, `['paper', id, 'summary'|'status'|'episode']`, `['search', q]`, `['profiles']`, `['voices']`. **Poll `['paper', id, 'status']` only while a run is non-terminal** (stop on succeeded/failed); same hook drives the library badge (slow interval) + add-paper strip (fast). Trigger → invalidate status; on terminal → invalidate summary/episode/list. **Binary endpoints (`report.pdf`, `audio.mp3`) are consumed by `<object>`/`<audio>` directly by URL (browser range/streaming) — only their *metadata* is queried.**
- **Persistent-player store — Zustand**, instantiated in `PlayerProvider` in `AppShell` above the outlet (selector subscriptions keep high-frequency `timeupdate` writes from re-rendering the tree — the one place a global store earns it). Holds: `nowPlaying`, `queue`/`queueIndex`, `status`, `positionMs`/`durationMs`, `playbackRate`, `volume`, `turns` (timed transcript), `resumeMap` (→ localStorage). The `<audio>` element is the source of truth for position.
- **URL/route state.** Current view, paper, active tab, and search query live in the URL (deep-linkable, back-correct, LAN-shareable). Library filters/sort in search params. Player state deliberately floats above the URL.
- **Local/form state.** `useState`/`useReducer` for ephemerals; React Hook Form + Zod for profiles/settings.

---

## 5. App-wide signature moments (peak-end — invest here, nowhere else)

1. **The first interview's cold open landing** (first-ever play) — the aha; DownLow becomes "a show about my research."
2. **Read-while-listening** — the seamless PDF↔summary↔transcript pivot with the docked player never losing place.
3. **The steered relevance callout** matching the user's focus — the differentiator from any generic summariser.

(Error recovery is the implicit fourth, handled inline via retry-a-failed-stage — never a separate destination.)

---

## 6. Kano scope (v1 discipline)

- **Must-be (v1, no exceptions):** persistent player above the router + keyboard transport + Media Session; honest `StageRun` status; a useful Library (continuation/ready shelves, not a void); Paper-detail pivot without losing place; in-app PDF reader; summary reader with structure + preserved hedging + relevance surfaced; add-a-paper with optimistic add + dedup; resume-position (at minimum within-session, ideally persisted); deep-linkable routes; a11y baseline (player keyboard ops especially).
- **Performance (v1 quality bar):** turn-aware/segmented scrubber + follow-along transcript + tap-to-seek; saved views / smart sort / filters; Cmd+K; search; speed/queue/±15s; per-stage retry-from-failure; skeletons + 150–250ms transitions.
- **Delighters (1–2/surface; cheap — infra exists):** cold-open hover preview; first-interview-ready acknowledgement (once); cross-pane links (finding→PDF, transcript→summary); "listen to this part"; now-playing live speaker indicator.

---

## 7. v1 build order (foundations first, then signature-moment carriers)

1. **App Shell + persistent player mount + client-side router** (the foundation + the React-vs-Jinja spike).
2. **Paper Detail hub + PDF reader + Summary reader** (carries signature moments 2 & 3).
3. **The full Podcast Player** (carries signature moment 1; depends on per-turn offsets — flag early; ship plain scrubber first).
4. **Library / Home** (continuation + ready shelves + status cards).
5. **Add-paper + processing status** (optimistic add + honest StageRun strip).
6. **Onboarding / empty states** (funnel to signature moment 1).
7. **Settings / profiles** (research-profile editor first).
8. **Search + Cmd+K** (a layer over a populated corpus).

---

## 8. API contract — the backend deliverables (Phase 3 wiring, for `backend-engineer`)

Each maps to an existing `core` service/entity unless marked. **Two gate the signature surfaces — surface now:**
- **NARRATE mixer emits per-turn `start_ms`/`end_ms`** onto the `PodcastAsset`/`narration_script` (the mixer already lays turns on a timeline — persist the offsets). Unlocks turn-scrubber, follow-along transcript, tap-to-seek, transcript-search-to-timestamp.
- **`PlaybackState`** read/write (position per user+paper) + reading position — the "Spotify" resume promise (v1 may stand in with client localStorage, but reserve `PUT /papers/{id}/playback`).

**Reads:** `GET /papers` (enriched list item: derived status, has_audio, duration, resume, authors, page_count, cover, active-profile; supports `?profile=&folder=&sort=&hasAudio=&q=`) · `GET /papers/{id}` (detail + availability flags) · `GET /papers/{id}/summary` (`PaperSummary` with `evidence` nullability intact) · **`GET /papers/{id}/status`** *(new — derived run/stage DTO; drives all progress UI)* · `GET /papers/{id}/report.pdf` *(binary; **HTTP Range** required)* · `GET /papers/{id}/audio.mp3` *(binary; **HTTP Range / 206 / Accept-Ranges** required for seeking)* · **`GET /papers/{id}/episode`** *(new — episode meta + audioUrl + voices + `turns: TimedTurn[]`)* · **`GET /papers/{id}/cover`** *(new, optional — first-PDF-page thumbnail; needs the PyMuPDF/pypdfium2 extractor swap, else a generated cover)* · **`GET /profiles`**, **`GET /voices`**, **`GET /search?q=`** *(new; SQLite FTS5; returns paper/finding/turn hits with anchors)*.

**Writes/triggers:** `POST /papers` (upload; dedup by `source_hash` → returns existing if re-added) · **`POST /papers/{id}/process`** *(new; `{profileId?, outputProfileId?, skipNarrate?, force?}`; return promptly + runId, poll `/status` — the sync-now/worker-later seam)* · `POST /papers/{id}/{summarise|report|narrate}` (trigger/retry one stage; reuses cached upstream) · **profile CRUD** *(new — needs a `ProfileService`; today only `BackfillService` writes profiles)* · **`PUT /papers/{id}/playback`** *(FUTURE)*.

**Cross-cutting API:** range requests on audio + PDF (acceptance-tested); CORS for the Vite dev origin (`VITE_API_BASE_URL` configurable); consistent error envelope `{error:{code,message}}`; the status DTO's stage-name keys + `StageStatus` values agreed 1:1 with `domain/enums.py`.

---

## 9. Cross-cutting + biggest risks

- **Per surface:** loading (skeletons, not spinners) / success / error / **teaching empty** states; pipeline status surfaced as one `StatusSummary` rendered as badge + stage-strip; content fidelity (no UI implying more certainty than the source).
- **Performance:** lazy-load PDF + audio surfaces; `<audio preload="metadata">` + range; no CLS in the grid (reserved cover aspect-ratio); scrubber INP off the global render path (rAF while dragging, commit on release); JS budget; `prefers-reduced-motion`.
- **A11y:** the player is fully keyboard-operable (Space/arrows, ≥44×44 transport, accessible Slider with `aria-valuetext` = time + speaker, live region for track/turn/speaker changes); WAI-ARIA tabs; Cmd+K is a focus-trapped dialog; nav landmarks + skip link.
- **Risks (+ mitigations):** persistent player across routing (layout route + Zustand + single `<audio>` — the spike) · audio seek/range (make 206 a Phase-3 acceptance test) · turn-scrubber has no data (decouple; ship plain v1) · PDF rendering choice (lazy react-pdf vs native — measure; decide with brand-architect + modern-stack-advisor) · large library (paginate/virtualize; one library-wide status poll, not N per-card) · sync pipeline vs HTTP timeout (fire-then-poll model; backend returns runId promptly).

---

*Sources: the two scoping passes cite NN/g, Baymard, Laws of UX, Growth.Design, Spotify/Overcast/Apple Podcasts, Linear/Raycast/Arc/Readwise, W3C Media Session, Walter/Norman/Saffer/Swink/Few. Visual/layout/motion decisions are owned by `deeptech-brand-architect`; content-certainty presentation by `academic-writing-advisor`.*
