"""The ``dl summarise`` command (F2): PDF -> context-steered PaperSummary JSON.

A thin Typer driver -- it wires the container at the composition root, runs the
SUMMARISE stage, and prints/saves the validated :class:`PaperSummary` as JSON. No
business logic lives here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from downlow.cli.deps import build_container
from downlow.domain.errors import LLMError, TruncatedResponseError


def summarise(
    pdf: Annotated[Path, typer.Argument(help="Path to the source PDF to summarise.")],
    profile: Annotated[
        str | None, typer.Option(help="Research profile name (defaults to the config's active one).")
    ] = None,
    output_profile: Annotated[
        str | None, typer.Option(help="Output profile name (defaults to the config's active one).")
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Write the summary JSON here instead of stdout.")] = None,
    force: Annotated[bool, typer.Option(help="Bypass the result cache and re-summarise.")] = False,
) -> None:
    """Summarise a research PDF, steered by the active research/output profile."""
    if not pdf.exists():
        typer.echo(f"PDF not found: {pdf}", err=True)
        raise typer.Exit(code=2)

    try:
        container = build_container(research_profile=profile, output_profile=output_profile)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    cfg = container.config
    try:
        summary = container.summarise.run(
            pdf,
            cfg.research_profile,
            cfg.output_profile,
            cfg.summary,
            force=force,
        )
    except TruncatedResponseError as exc:
        typer.echo(f"Summarisation truncated (try a larger max_tokens): {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except LLMError as exc:
        typer.echo(f"Summarisation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    payload = summary.model_dump_json(indent=2)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        typer.echo(f"Wrote summary to {out}")
    else:
        typer.echo(payload)
