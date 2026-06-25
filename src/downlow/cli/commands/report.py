"""The ``dl report`` command (F3): PDF(s) -> summary -> compiled Typst report PDF.

A thin Typer driver -- it wires the container at the composition root, summarises
each PDF via the SUMMARISE stage (which ingests internally), renders the merged
report via the RENDER stage (the typst subprocess lives in the adapter), and
writes the report PDF. No business logic lives here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from downlow.cli.deps import build_container
from downlow.domain.errors import LLMError, TruncatedResponseError, TypstCompileError
from downlow.domain.schemas import PaperSummary


def report(
    pdfs: Annotated[list[Path], typer.Argument(help="One or more source PDFs to compile into one report.")],
    out: Annotated[
        Path | None, typer.Option(help="Write the report PDF here (defaults to <DATA_DIR>/reports/).")
    ] = None,
    title: Annotated[
        str | None, typer.Option(help="Explicit report title (overrides the templated/LLM title).")
    ] = None,
    profile: Annotated[
        str | None, typer.Option(help="Research profile name (defaults to the config's active one).")
    ] = None,
    output_profile: Annotated[
        str | None, typer.Option(help="Output profile name (defaults to the config's active one).")
    ] = None,
    force: Annotated[bool, typer.Option(help="Bypass the summary + render caches and rebuild.")] = False,
) -> None:
    """Compile one or more research PDFs into a single Typst summary report."""
    missing = [p for p in pdfs if not p.exists()]
    if missing:
        typer.echo(f"PDF(s) not found: {', '.join(str(p) for p in missing)}", err=True)
        raise typer.Exit(code=2)

    try:
        container = build_container(research_profile=profile, output_profile=output_profile)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    cfg = container.config
    summaries: list[PaperSummary] = []
    try:
        for pdf in pdfs:
            summaries.append(
                container.summarise.run(pdf, cfg.research_profile, cfg.output_profile, cfg.summary, force=force)
            )
    except TruncatedResponseError as exc:
        typer.echo(f"Summarisation truncated (try a larger max_tokens): {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except LLMError as exc:
        typer.echo(f"Summarisation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        result = container.render.run(summaries, cfg.report, title=title, force=force)
    except TypstCompileError as exc:
        detail = f": {exc.stderr.strip()}" if exc.stderr else ""
        typer.echo(f"Report rendering failed{detail}", err=True)
        raise typer.Exit(code=1) from exc
    except LLMError as exc:
        typer.echo(f"Report title generation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(result.pdf_bytes)
        typer.echo(f"Wrote report '{result.title}' to {out}")
    else:
        typer.echo(f"Wrote report '{result.title}' to {result.ref}")
