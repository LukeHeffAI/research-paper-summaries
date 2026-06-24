"""A fake :class:`LLMClient` for ``core`` pipeline tests.

Implements the same port Protocol the real ``AnthropicLLMClient`` does, so the
whole SUMMARISE stage runs with no network, no key, and deterministic output.
This is the seam that makes the pipeline testable.

Capabilities:

* returns a canned, schema-valid model instance (default a sensible
  :class:`PaperSummary`), or one supplied per construction;
* spies: records every ``complete_structured`` call's document / system /
  instruction and every ``count_tokens`` call, so tests can assert that the
  steering prompt carried the profile and that the cache skipped the call;
* truncation mode: raise :class:`TruncatedResponseError` for the first N calls
  (to exercise the recursive split-and-retry path), then succeed;
* token mode: a fixed ``token_count`` (or a callable) drives the input-budget
  gate, so the section-split / text-fallback paths are reachable deterministically.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

from downlow.domain.errors import TruncatedResponseError
from downlow.domain.ports import LLMDocument
from downlow.domain.schemas import KeyFinding, PaperSummary

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _default_summary() -> PaperSummary:
    """A canned, schema-valid PaperSummary (content fields only; provenance blank)."""
    return PaperSummary(
        title="A Fake Paper on Generalisation",
        overall_summary=("A canned overall summary used by the fake LLM client. " * 12).strip(),
        key_findings=[
            KeyFinding(statement="Method X improves zero-shot accuracy.", evidence="+4.2 points on the benchmark"),
            KeyFinding(statement="The gain is robust across two domains.", evidence=None),
        ],
        contributions=["A new training objective.", "A released evaluation suite."],
        methods="Controlled comparison against three baselines on a public benchmark.",
        gaps_and_limitations=["Evaluated on a single modality.", "A reviewer might note the small sample."],
        relevance_to_profile="Directly bears on your focus on cross-domain generalisation.",
    )


@dataclass
class _Call:
    document: LLMDocument
    system: str
    instruction: str
    max_tokens: int
    effort: str


@dataclass
class FakeLLMClient:
    """Deterministic in-memory ``LLMClient`` with spying + failure-injection."""

    result: BaseModel = field(default_factory=_default_summary)
    truncate_first_n: int = 0
    token_count: int | Callable[[LLMDocument], int] = 100
    calls: list[_Call] = field(default_factory=list)
    count_token_calls: list[LLMDocument] = field(default_factory=list)
    _truncations_left: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._truncations_left = self.truncate_first_n

    @property
    def call_count(self) -> int:
        """How many ``complete_structured`` calls have been made."""
        return len(self.calls)

    def complete_structured(
        self,
        *,
        document: LLMDocument,
        system: str,
        instruction: str,
        schema: type[SchemaT],
        max_tokens: int,
        effort: str,
    ) -> SchemaT:
        """Record the call and return the canned result (or simulate truncation)."""
        self.calls.append(
            _Call(document=document, system=system, instruction=instruction, max_tokens=max_tokens, effort=effort)
        )
        if self._truncations_left > 0:
            self._truncations_left -= 1
            raise TruncatedResponseError(request_id="fake-req")
        if not isinstance(self.result, schema):
            # Validate the canned result against the requested schema so the fake
            # honours the same contract as the real adapter.
            return schema.model_validate(self.result.model_dump())
        return self.result

    def count_tokens(self, *, document: LLMDocument, system: str, instruction: str) -> int:
        """Record the call and return the configured token count."""
        self.count_token_calls.append(document)
        if callable(self.token_count):
            return self.token_count(document)
        return self.token_count
