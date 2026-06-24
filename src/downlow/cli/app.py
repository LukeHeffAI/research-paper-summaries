"""DownLow CLI (``dl``) — a thin Typer driver over core services.

Phase 0 ships only ``version``/``info``. The feature commands
(``add``, ``summarise``, ``report``, ``narrate``, ``rename``, ``run``) arrive in
Phase 1 and will orchestrate ``core`` services only — no business logic here.
"""

from __future__ import annotations

import typer

from downlow import __version__

app = typer.Typer(
    help="DownLow — the low-down on a research paper.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def version() -> None:
    """Print the installed DownLow version."""
    typer.echo(__version__)


@app.command()
def info() -> None:
    """Show a short orientation message."""
    typer.echo("DownLow scaffold (Phase 0). Pipeline commands land in Phase 1 — see PROJECT_PLAN.md.")
