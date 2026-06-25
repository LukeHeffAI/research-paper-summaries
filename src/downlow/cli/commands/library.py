"""The ``dl library`` command group (Phase 2.1): read the library from the DB.

Thin Typer drivers -- they open a read session over the Paper repository and print
the persisted library. No business logic lives here; the queries are in
``core.services.library``.

* ``dl library list``      -- list the papers in the library.
* ``dl library show <id>`` -- show one paper's stored detail.
"""

from __future__ import annotations

from typing import Annotated

import typer

from downlow.cli.deps import library_session

library_app = typer.Typer(help="Inspect the DownLow library (papers persisted by `dl process`).")


@library_app.command("list")
def list_papers() -> None:
    """List every paper in the library (id, title, source hash prefix)."""
    with library_session() as library:
        papers = library.list_papers()

    if not papers:
        typer.echo("The library is empty. Run `dl process <pdf>` to add a paper.")
        return

    for paper in papers:
        short_hash = paper.source_hash[:12] if paper.source_hash else "(no hash)"
        title = paper.title or "(untitled)"
        typer.echo(f"{paper.id}\t{title}\t{short_hash}")


@library_app.command("show")
def show_paper(
    paper_id: Annotated[int, typer.Argument(help="The id of the paper to show.")],
) -> None:
    """Show one paper's stored detail by id."""
    with library_session() as library:
        paper = library.get_paper(paper_id)

    if paper is None:
        typer.echo(f"No paper with id {paper_id} in the library.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"id:          {paper.id}")
    typer.echo(f"title:       {paper.title or '(untitled)'}")
    typer.echo(f"authors:     {', '.join(paper.authors) if paper.authors else '(none)'}")
    typer.echo(f"pages:       {paper.page_count if paper.page_count is not None else '(unknown)'}")
    typer.echo(f"source hash: {paper.source_hash or '(none)'}")
    typer.echo(f"created:     {paper.created_at.isoformat() if paper.created_at else '(unknown)'}")
