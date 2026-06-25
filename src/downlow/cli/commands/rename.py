"""The ``dl rename`` command (F5): suggest (and optionally apply) a clean PDF name.

A thin Typer driver -- it wires the filename heuristic at the composition root,
extracts the paper's metadata via the LLM, builds the deterministic filename, prints
the suggestion, and (only with ``--apply``) renames the file. No business logic lives
here; the suggest/apply split lives in ``core.services.filename``.

The legacy ``update_pdf_filenames`` renamed in place after a ``y``/``n`` prompt. The
rebuild defaults to *suggest-only* (print the name, change nothing) so the heuristic
is safe to run over a folder; ``--apply`` opts in to the rename.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from downlow.cli.deps import build_filename_heuristic
from downlow.config.profiles import load_config
from downlow.config.settings import Settings
from downlow.domain.errors import EmptyExtractionError, LLMError, TruncatedResponseError


def rename(
    pdf: Annotated[Path, typer.Argument(help="Path to the source PDF to name.")],
    apply: Annotated[
        bool, typer.Option(help="Rename the file to the suggested name (default: suggest only, change nothing).")
    ] = False,
) -> None:
    """Suggest a clean filename for a research PDF from its title/authors/year."""
    if not pdf.exists():
        typer.echo(f"PDF not found: {pdf}", err=True)
        raise typer.Exit(code=2)

    try:
        settings = Settings()
        config = load_config(settings.config_file)
        heuristic = build_filename_heuristic(settings=settings, config=config)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    try:
        suggestion = heuristic.suggest_for_pdf(pdf, config.metadata)
    except TruncatedResponseError as exc:
        typer.echo(f"Metadata extraction truncated (try a larger metadata max_tokens): {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except (EmptyExtractionError, LLMError) as exc:
        typer.echo(f"Metadata extraction failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not apply:
        typer.echo(f"Suggested name for {pdf.name}: {suggestion.filename}")
        return

    try:
        new_path = heuristic.apply(pdf, suggestion.filename)
    except FileExistsError as exc:
        typer.echo(f"Not renamed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if new_path == pdf:
        typer.echo(f"Already named {suggestion.filename}; nothing to do.")
    else:
        typer.echo(f"Renamed {pdf.name} -> {new_path.name}")
