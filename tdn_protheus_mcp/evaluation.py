"""Offline synthetic evaluation for citation regressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .policy import SnapshotPolicy
from .search import SnapshotSearch


@dataclass(frozen=True)
class EvaluationCase:
    question: str
    expected_source_urls: frozenset[str]


@dataclass(frozen=True)
class EvaluationReport:
    cases: int
    citation_recall: float
    exact_source_rate: float


def evaluate(cases: tuple[EvaluationCase, ...], search: Callable[[str], tuple[str, ...]]) -> EvaluationReport:
    hits = 0
    exact = 0
    for case in cases:
        actual = frozenset(search(case.question))
        if case.expected_source_urls <= actual:
            hits += 1
        if actual == case.expected_source_urls:
            exact += 1
    total = len(cases)
    return EvaluationReport(total, hits / total if total else 1.0, exact / total if total else 1.0)


def evaluate_snapshot(
    cases: tuple[EvaluationCase, ...], *, search: SnapshotSearch, policy: SnapshotPolicy,
    root_id: str, max_results: int = 8, max_chars: int = 12000,
) -> EvaluationReport:
    """Exercise evaluation cases through the same bounded local search path used by MCP."""

    def source_urls(question: str) -> tuple[str, ...]:
        request = policy.search_query(question, root_id, max_results, max_chars)
        return tuple(result.source_url for result in search.search(request))

    return evaluate(cases, source_urls)
