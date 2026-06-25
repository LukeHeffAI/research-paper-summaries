"""The ``dl process`` command (Phase 2.1): run the full persisted pipeline.

A thin Typer driver -- it opens the persisted-pipeline composition root, runs
INGEST -> SUMMARISE -> RENDER -> NARRATE -> STORE over the PDF (persisting the
PipelineRun + per-stage status + every artifact reference to the DB), and reports
the outcome. No business logic lives here; the orchestration is in
``core.services.processing``.

This is the orchestrated + persisted path. The standalone ``summarise`` / ``report``
/ ``narrate`` / ``rename`` commands stay file-only for quick one-shot use; ``process``
is the one that builds the library.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from downlow.cli.deps import processing_session
from downlow.domain.enums import RunStatus
from downlow.domain.errors import DownLowError


def process(
    pdf: Annotated[Path, typer.Argument(help="Path to the source PDF to process through the full pipeline.")],
    profile: Annotated[
        str | None, typer.Option(help="Research profile name (defaults to the config's active one).")
    ] = None,
    output_profile: Annotated[
        str | None, typer.Option(help="Output profile name (defaults to the config's active one).")
    ] = None,
    no_audio: Annotated[
        bool, typer.Option(help="Skip the NARRATE stage (summary + report only; no ElevenLabs needed).")
    ] = False,
    force: Annotated[bool, typer.Option(help="Rebuild every stage (bypass caches + resume-from-failure).")] = False,
) -> None:
    """Process a research PDF through the full persisted pipeline into the library."""
    if not pdf.exists():
        typer.echo(f"PDF not found: {pdf}", err=True)
        raise typer.Exit(code=2)

    try:
        with processing_session(
            research_profile=profile,
            output_profile=output_profile,
            with_narration=not no_audio,
        ) as container:
            result = container.processing.process_paper(pdf, container.config, user_id=container.user_id, force=force)
    except ValueError as exc:
        # Missing API key (validated at the composition root).
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    except DownLowError as exc:
        # A modelled pipeline failure that escaped the run record (defensive).
        typer.echo(f"Processing failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    run = result.run
    if run.status is RunStatus.SUCCEEDED:
        typer.echo(f"Processed '{pdf.name}' as paper {result.paper_id} (run {run.id}: {run.status.value}).")
    else:
        typer.echo(
            f"Processing of '{pdf.name}' did not complete (run {run.id}: {run.status.value}): {run.error}",
            err=True,
        )
        raise typer.Exit(code=1)
