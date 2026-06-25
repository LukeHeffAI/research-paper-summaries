"""The ``dl backfill`` command (Phase 2.3): import the legacy data into the DB.

A thin Typer driver -- it parses the on-disk ``legacy/`` tree (the file-reading
``legacy_loader``), opens the backfill composition root, runs the idempotent import,
and prints an imported / already-present / skipped summary. No business logic lives
here; the upsert logic is in ``core.services.backfill``.

The import is safe to re-run: every row is upserted on its dedupe key, so a second
``dl backfill`` reports everything as already-present and writes nothing new.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from downlow.cli.deps import backfill_session
from downlow.cli.legacy_loader import LegacyDataError, load_legacy_import

# The ``--user`` option is accepted for forward-compatibility / parity with the other
# commands, but the legacy import is driven by the data it finds (every legacy user is
# imported, not just one); a value scopes nothing today and is reported if given.


def backfill(
    source: Annotated[Path, typer.Option(help="Root of the legacy tree to import from.")] = Path("legacy"),
    user: Annotated[
        str | None,
        typer.Option(help="(Reserved) the owning user; the import covers every legacy user it finds."),
    ] = None,
) -> None:
    """Import the legacy ``data/`` profiles + ``users/`` tree into the DB (idempotent)."""
    if not source.is_dir():
        typer.echo(f"Legacy source directory not found: {source}", err=True)
        raise typer.Exit(code=2)

    try:
        data = load_legacy_import(source)
    except LegacyDataError as exc:
        typer.echo(f"Backfill aborted: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    with backfill_session() as service:
        report = service.run(data)

    typer.echo("Backfill complete.")
    typer.echo(f"  users:            {report.users_imported} imported, {report.users_already_present} already present")
    typer.echo(
        f"  research profiles: {report.research_profiles_imported} imported, "
        f"{report.research_profiles_already_present} already present"
    )
    typer.echo(
        f"  output profiles:   {report.output_profiles_imported} imported, "
        f"{report.output_profiles_already_present} already present"
    )

    if report.skipped_orphan_audio:
        typer.echo(f"  skipped {len(report.skipped_orphan_audio)} orphan audio file(s) (no source PDF/summary):")
        for orphan in report.skipped_orphan_audio:
            typer.echo(f"    - [{orphan.owner}] {orphan.path}")
        typer.echo("    Re-ingest the source PDF with `dl process` to rebuild the podcast.")

    if user is not None:
        typer.echo(f"  note: --user {user!r} is reserved; every legacy user found was imported.")
