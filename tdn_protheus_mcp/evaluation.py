"""Offline synthetic evaluation for citation and no-evidence regressions."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .policy import SnapshotPolicy
from .search import SnapshotSearch


@dataclass(frozen=True)
class EvaluationCase:
    question: str
    expected_source_urls: frozenset[str]


@dataclass(frozen=True)
class EvaluationReport:
    cases: int
    evidence_cases: int
    no_evidence_cases: int
    citation_recall: float
    exact_source_rate: float
    no_evidence_accuracy: float


def evaluate(
    cases: tuple[EvaluationCase, ...],
    search: Callable[[str], tuple[str, ...]],
) -> EvaluationReport:
    evidence_cases = 0
    citation_hits = 0
    no_evidence_cases = 0
    no_evidence_hits = 0
    exact = 0
    for case in cases:
        actual = frozenset(search(case.question))
        expected = case.expected_source_urls
        if expected:
            evidence_cases += 1
            if expected <= actual:
                citation_hits += 1
        else:
            no_evidence_cases += 1
            if not actual:
                no_evidence_hits += 1
        if actual == expected:
            exact += 1
    total = len(cases)
    return EvaluationReport(
        cases=total,
        evidence_cases=evidence_cases,
        no_evidence_cases=no_evidence_cases,
        citation_recall=citation_hits / evidence_cases if evidence_cases else 1.0,
        exact_source_rate=exact / total if total else 1.0,
        no_evidence_accuracy=(
            no_evidence_hits / no_evidence_cases if no_evidence_cases else 1.0
        ),
    )


def evaluate_snapshot(
    cases: tuple[EvaluationCase, ...],
    *,
    search: SnapshotSearch,
    policy: SnapshotPolicy,
    root_id: str,
    max_results: int = 8,
    max_chars: int = 12000,
) -> EvaluationReport:
    """Exercise cases through the same bounded local search path used by MCP."""

    def source_urls(question: str) -> tuple[str, ...]:
        request = policy.search_query(question, root_id, max_results, max_chars)
        return tuple(result.source_url for result in search.search(request))

    return evaluate(cases, source_urls)
