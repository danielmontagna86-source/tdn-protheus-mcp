from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tdn_protheus_mcp.config import McpConfig
from tdn_protheus_mcp.evaluation import EvaluationCase, evaluate, evaluate_snapshot
from tdn_protheus_mcp.indexer import SnapshotIndexer
from tdn_protheus_mcp.policy import SnapshotPolicy
from tdn_protheus_mcp.search import SnapshotSearch
from tdn_protheus_mcp.snapshot_repository import SnapshotRepository


class EvaluationTests(unittest.TestCase):
    def test_evaluation_separates_citation_recall_from_no_evidence_accuracy(self) -> None:
        cases = (
            EvaluationCase(question="FWRest", expected_source_urls=frozenset({"https://tdn/10"})),
            EvaluationCase(question="MVC", expected_source_urls=frozenset({"https://tdn/20"})),
            EvaluationCase(question="INVENTADO", expected_source_urls=frozenset()),
        )
        results = {
            "FWRest": ("https://tdn/10",),
            "MVC": ("https://tdn/20", "https://tdn/30"),
            "INVENTADO": (),
        }

        report = evaluate(cases, lambda question: results[question])

        self.assertEqual(report.cases, 3)
        self.assertEqual(report.evidence_cases, 2)
        self.assertEqual(report.no_evidence_cases, 1)
        self.assertEqual(report.citation_recall, 1.0)
        self.assertEqual(report.no_evidence_accuracy, 1.0)
        self.assertEqual(report.exact_source_rate, 2 / 3)

    def test_evaluation_penalizes_false_evidence_for_no_evidence_case(self) -> None:
        report = evaluate(
            (EvaluationCase(question="MT103VALIDAITENSXYZ", expected_source_urls=frozenset()),),
            lambda _question: ("https://tdn/falso",),
        )
        self.assertEqual(report.no_evidence_accuracy, 0.0)
        self.assertEqual(report.exact_source_rate, 0.0)

    def test_critical_snapshot_gate_has_perfect_recall_and_no_evidence_accuracy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages = cache_root / "1" / "pages"
            pages.mkdir(parents=True)
            fixtures = [
                {"id": 10, "title": "MATA103 Documento de Entrada", "url": "https://fixture/mata103", "text": "MATA103 processa Documento de Entrada e usa SD1.", "fetched_at": "2026-08-15"},
                {"id": 20, "title": "Ponto de Entrada PLRSTPR1", "url": "https://fixture/plrstpr1", "text": "PLRSTPR1 recebe PARAMIXB para a API de procedimentos.", "fetched_at": "2026-08-15"},
            ]
            manifest_pages = {}
            for page in fixtures:
                (pages / f"{page['id']}.json").write_text(json.dumps(page), encoding="utf-8")
                manifest_pages[str(page["id"])] = {"status": "active"}
            (cache_root / "1" / "manifest.json").write_text(
                json.dumps({"schema_version": 1, "root_id": 1, "pages": manifest_pages}), encoding="utf-8"
            )
            policy = SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"})))
            SnapshotIndexer(SnapshotRepository(policy), policy).build("1")

            report = evaluate_snapshot(
                (
                    EvaluationCase(question="MATA103", expected_source_urls=frozenset({"https://fixture/mata103"})),
                    EvaluationCase(question="PLRSTPR1", expected_source_urls=frozenset({"https://fixture/plrstpr1"})),
                    EvaluationCase(question="MT103VALIDAITENSXYZ", expected_source_urls=frozenset()),
                ),
                search=SnapshotSearch(policy), policy=policy, root_id="1",
            )

        self.assertEqual(report.citation_recall, 1.0)
        self.assertEqual(report.no_evidence_accuracy, 1.0)
        self.assertEqual(report.exact_source_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
