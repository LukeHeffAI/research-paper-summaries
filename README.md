# DownLow

*The low-down on a research paper.*

A local-network "Spotify for research papers": maintain a library of papers and,
per paper, read the source PDF, read a context-steered text summary, and play a
**two-presenter interview podcast** — all served from your own machine.

> **Status:** foundation phase. The full plan, architecture, and phased roadmap
> live in [`PROJECT_PLAN.md`](./PROJECT_PLAN.md). The pre-rebuild scripts are kept
> under [`legacy/`](./legacy) for reference until the rebuild (F1–F5) lands.

## Stack

Python 3.11+ · FastAPI + SQLModel (web layer is future) · Anthropic Claude ·
Typst (reports) · ElevenLabs + pydub (podcast) · SQLite → Postgres-ready.

## Develop

```bash
uv sync --extra dev          # create the venv + install (dev tools included)
uv run dl version            # run the CLI
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/downlow/
uv run pytest
git config core.hooksPath .githooks   # one-time: enable the ruff-format pre-commit hook
```

**System dependencies (Phase 1):** the `typst` binary (report rendering) and
`ffmpeg` (pydub audio mixing).
