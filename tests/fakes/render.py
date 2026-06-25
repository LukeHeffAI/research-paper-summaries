"""Fakes for the RENDER stage (F3): a :class:`ReportRenderer` + an :class:`ArtifactStore`.

Implement the same port Protocols the real ``TypstRenderer`` /
``FilesystemArtifactStore`` do, so the whole RENDER stage runs with no ``typst``
binary, no subprocess, and no filesystem layout -- deterministically.

Capabilities:

* :class:`FakeReportRenderer` returns canned PDF bytes (a real ``%PDF`` header so
  callers asserting validity pass) and spies the last :class:`ReportData` it was
  handed, so a test can assert the assembled summaries + title + template version;
  a ``fail`` flag raises :class:`TypstCompileError` to exercise the error path.
* :class:`FakeArtifactStore` records every ``put(key, data)`` in an in-memory dict
  and returns a logical reference, so a test can assert the report landed under
  ``reports/<slug>.pdf`` with the expected bytes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from downlow.domain.errors import TypstCompileError
from downlow.domain.schemas import ReportData

# A minimal but valid PDF preamble so callers that assert a ``%PDF`` header pass.
_FAKE_PDF = b"%PDF-1.7\n%fake-downlow-report\n"


@dataclass
class FakeReportRenderer:
    """Deterministic in-memory ``ReportRenderer`` with spying + failure-injection."""

    pdf_bytes: bytes = _FAKE_PDF
    fail: bool = False
    calls: list[ReportData] = field(default_factory=list)

    @property
    def call_count(self) -> int:
        """How many ``render`` calls have been made (cache-hit tests assert 0/1)."""
        return len(self.calls)

    @property
    def last_data(self) -> ReportData | None:
        """The most recent :class:`ReportData` rendered, or ``None`` if never called."""
        return self.calls[-1] if self.calls else None

    def render(self, data: ReportData) -> bytes:
        """Record the assembled data and return canned PDF bytes (or raise)."""
        self.calls.append(data)
        if self.fail:
            raise TypstCompileError("fake renderer forced failure", returncode=1, stderr="boom")
        return self.pdf_bytes


@dataclass
class FakeArtifactStore:
    """In-memory ``ArtifactStore``: records puts and returns a logical reference."""

    stored: dict[str, bytes] = field(default_factory=dict)

    def put(self, key: str, data: bytes) -> str:
        """Record ``data`` under ``key`` and return a ``fake://`` reference."""
        self.stored[key] = data
        return f"fake://{key}"
