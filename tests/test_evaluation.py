from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from tdn_protheus_mcp.config import McpConfig
from tdn_protheus_mcp.evaluation import EvaluationCase, evaluate, evaluate_snapshot
from tdn_protheus_mcp.indexer import SnapshotIndexer
from tdn_protheus_mcp.policy import SnapshotPolicy
from tdn_protheus_mcp.search import SnapshotSearch
from tdn_protheus_mcp.snapshot_repository import SnapshotRepository


class EvaluationTests(unittest.TestCase):
    def test_evaluation_reports_citation_recall_for_synthetic_results(self) -> None:
        cases = (
            EvaluationCase(question="FWRest", expected_source_urls=frozenset({"https://tdn/10"})),
            EvaluationCase(question="MVC", expected_source_urls=frozenset({"https://tdn/20"})),
        )
        results = {"FWRest": ("https://tdn/10",), "MVC": ("https://tdn/20", "https://tdn/30")}

        report = evaluate(cases, lambda question: results[question])

        self.assertEqual(report.cases, 2)
        self.assertEqual(report.citation_recall, 1.0)
        self.assertEqual(report.exact_source_rate, 0.5)

    def test_evaluation_runs_against_a_real_synthetic_snapshot_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages = cache_root / "1" / "pages"
            pages.mkdir(parents=True)
            (pages / "10.json").write_text(json.dumps({"id": 10, "title": "FWRest", "url": "https://fixture/10", "text": "FWRest chama serviços REST.", "fetched_at": "2026-08-15"}), encoding="utf-8")
            (pages / "20.json").write_text(json.dumps({"id": 20, "title": "MVC", "url": "https://fixture/20", "text": "MVC organiza telas Protheus.", "fetched_at": "2026-08-15"}), encoding="utf-8")
            (cache_root / "1" / "manifest.json").write_text(json.dumps({"root_id": 1, "pages": {"10": {"status": "active"}, "20": {"status": "active"}}}), encoding="utf-8")
            policy = SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"})))
            SnapshotIndexer(SnapshotRepository(policy), policy).build("1")

            report = evaluate_snapshot(
                (EvaluationCase(question="FWRest", expected_source_urls=frozenset({"https://fixture/10"})),),
                search=SnapshotSearch(policy), policy=policy, root_id="1",
            )

        self.assertEqual(report.citation_recall, 1.0)
        self.assertEqual(report.exact_source_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
