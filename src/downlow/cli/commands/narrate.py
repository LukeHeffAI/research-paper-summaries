"""The ``dl narrate`` command (F4): PDF -> two-presenter interview podcast mp3.

A thin Typer driver -- it wires the container at the composition root, runs the
NARRATE stage (script generation -> per-turn TTS -> mix), writes the episode mp3,
and (optionally) the generated :class:`NarrationScript` JSON alongside it. No
business logic lives here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from downlow.cli.deps import build_container, build_narrate_stage
from downlow.domain.errors import LLMError, NarrationQualityError, TruncatedResponseError, TTSError
from downlow.domain.schemas import PaperSummary


def narrate(
    pdf: Annotated[Path, typer.Argument(help="Path to the source PDF to turn into a podcast episode.")],
    out: Annotated[Path | None, typer.Option(help="Write the episode mp3 here (defaults to <pdf>.mp3).")] = None,
    script_out: Annotated[Path | None, typer.Option(help="Also write the generated NarrationScript JSON here.")] = None,
    profile: Annotated[
        str | None, typer.Option(help="Research profile name (only used on the summary script_source).")
    ] = None,
    output_profile: Annotated[
        str | None, typer.Option(help="Output profile name (only used on the summary script_source).")
    ] = None,
    force: Annotated[bool, typer.Option(help="Bypass the script and per-segment TTS caches.")] = False,
) -> None:
    """Generate the two-presenter interview podcast for a research PDF."""
    if not pdf.exists():
        typer.echo(f"PDF not found: {pdf}", err=True)
        raise typer.Exit(code=2)

    try:
        stage = build_narrate_stage(research_profile=profile, output_profile=output_profile)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    # On the summary script_source, the LLM is fed the prior summary, so produce it
    # first via the summarise stage (which needs only the Anthropic key).
    summary: PaperSummary | None = None
    container = build_container(research_profile=profile, output_profile=output_profile)
    cfg = container.config
    if cfg.narration.script_source == "summary":
        try:
            summary = container.summarise.run(pdf, cfg.research_profile, cfg.output_profile, cfg.summary, force=force)
        except (TruncatedResponseError, LLMError) as exc:
            typer.echo(f"Summarisation (for the summary script source) failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    try:
        if script_out is not None:
            script = stage.generate_script(pdf, cfg.narration, summary=summary, force=force)
            script_out.parent.mkdir(parents=True, exist_ok=True)
            script_out.write_text(script.model_dump_json(indent=2), encoding="utf-8")
            typer.echo(f"Wrote script to {script_out}")
        audio = stage.run(pdf, cfg.narration, summary=summary, force=force)
    except TruncatedResponseError as exc:
        typer.echo(f"Narration truncated (try a larger podcast max_tokens): {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except NarrationQualityError as exc:
        typer.echo(f"Narration script failed the quality gate: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except (LLMError, TTSError) as exc:
        typer.echo(f"Narration failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    destination = out if out is not None else pdf.with_suffix(".mp3")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(audio)
    typer.echo(f"Wrote episode to {destination}")
