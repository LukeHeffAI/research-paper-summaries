"""TypstRenderer implements :class:`ReportRenderer` (F3, the RENDER adapter).

This is the ONLY module allowed to shell out to the ``typst`` binary. Swapping
the backend -- e.g. to the ``typst`` PyPI package's bundled in-process compiler
(the documented fallback) -- is a one-class change behind the
:class:`~downlow.domain.ports.ReportRenderer` port; nothing in ``core``/``domain``
changes.

Responsibilities (per PROJECT_PLAN.md, Stage 3 RENDER):

* serialise the assembled :class:`ReportData` to ``summaries.json`` in an isolated
  temp directory, beside a copy of the deterministic ``report.typ`` template
  (which loads the JSON *as data*, so Typst escapes arbitrary summary strings --
  the LLM never emits markup);
* compile ``typst compile report.typ out.pdf`` via ``subprocess.run(..., check=True,
  capture_output=True)`` -- fully in-process and deterministic, no Overleaf
  watcher, no ``sleep(20)``;
* on a non-zero exit (or a missing binary) raise :class:`TypstCompileError` with
  the captured ``stderr`` so a maintainer sees the real cause;
* return the compiled PDF as bytes (the artifact store, not this adapter, owns
  where it lands on disk).

``subprocess`` is imported/invoked ONLY here.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from downlow.domain.errors import TypstCompileError
from downlow.domain.schemas import ReportData

# The data file the template loads via ``json("summaries.json")``. Must match the
# filename hard-coded in ``typst/report.typ``.
_DATA_FILENAME = "summaries.json"

# The template + output filenames inside the isolated compile directory.
_TEMPLATE_FILENAME = "report.typ"
_OUTPUT_FILENAME = "out.pdf"

# The default on-disk template shipped with the repo (``<repo>/typst/report.typ``).
# Resolved relative to this file so it is found regardless of the cwd.
_DEFAULT_TEMPLATE = Path(__file__).resolve().parents[4] / "typst" / _TEMPLATE_FILENAME


class TypstRenderer:
    """``ReportRenderer`` implementation that shells out to the ``typst`` binary."""

    def __init__(self, *, binary: str = "typst", template_path: Path | None = None) -> None:
        """Wire the renderer.

        Args:
            binary: the ``typst`` executable (``settings.typst_binary``); a bare
                name is resolved on ``PATH``, or an absolute path is used directly.
            template_path: the deterministic ``report.typ`` template; defaults to
                the one shipped under ``<repo>/typst/``. Injectable so a test (or a
                future restyle) can point at an alternative template.
        """
        self._binary = binary
        self._template_path = template_path or _DEFAULT_TEMPLATE

    def render(self, data: ReportData) -> bytes:
        """Compile ``data`` into a report PDF.

        Serialises the data + template into an isolated temp directory, compiles,
        and returns the PDF bytes. The temp directory is removed on exit, so the
        render leaves nothing behind (idempotent, byte-stable for identical input).

        Raises:
            TypstCompileError: when the ``typst`` binary is missing or exits
                non-zero (with the captured ``stderr``).
        """
        with tempfile.TemporaryDirectory(prefix="downlow-typst-") as tmp:
            workdir = Path(tmp)
            self._write_inputs(workdir, data)
            self._compile(workdir)
            return (workdir / _OUTPUT_FILENAME).read_bytes()

    def _write_inputs(self, workdir: Path, data: ReportData) -> None:
        """Write the data JSON + the template into the isolated compile directory.

        The summaries are serialised via pydantic (``model_dump_json``) so the
        template loads them as data and Typst handles escaping of arbitrary
        strings -- no markup is ever emitted into the document by the model.
        """
        (workdir / _DATA_FILENAME).write_text(data.model_dump_json(), encoding="utf-8")
        template = self._template_path.read_text(encoding="utf-8")
        (workdir / _TEMPLATE_FILENAME).write_text(template, encoding="utf-8")

    def _compile(self, workdir: Path) -> None:
        """Run ``typst compile`` in ``workdir``; raise on failure.

        ``cwd=workdir`` (not absolute paths in the argv) so the template's relative
        ``json("summaries.json")`` resolves and the compile directory is fully
        isolated from the repo. ``capture_output=True`` so a compile error's
        ``stderr`` is preserved for :class:`TypstCompileError`.
        """
        try:
            subprocess.run(
                [self._binary, "compile", _TEMPLATE_FILENAME, _OUTPUT_FILENAME],
                cwd=workdir,
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as exc:
            raise TypstCompileError(
                f"the typst binary {self._binary!r} was not found on PATH; install typst to render reports",
                stderr=str(exc),
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            raise TypstCompileError(
                f"typst compile failed (exit {exc.returncode})",
                returncode=exc.returncode,
                stderr=stderr,
            ) from exc
