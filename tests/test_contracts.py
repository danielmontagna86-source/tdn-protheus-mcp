from __future__ import annotations

import sys
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tdn_protheus_mcp.contracts import ContextBundle, SearchQuery, SearchResult, SnapshotStatus  # noqa: E402


class ContractsTests(unittest.TestCase):
    def test_public_contracts_are_immutable_and_keep_citation_metadata(self) -> None:
        query = SearchQuery(query="FWRest", root_id="235312129", max_results=8, max_chars=12000)
        result = SearchResult(
            root_id="235312129",
            page_id="42",
            chunk_id="42:0",
            title="FWRest",
            source_url="https://tdn.totvs.com/page/42",
            content="Referência externa.",
            collected_at="2026-08-15T00:00:00+00:00",
        )
        context = ContextBundle(question="Como usar FWRest?", results=(result,), safety_notice="external_reference")
        status = SnapshotStatus(root_id="235312129", active_pages=1, removed_pages=0, cache_bytes=100)

        self.assertEqual(query.max_results, 8)
        self.assertEqual(context.results[0].source_url, "https://tdn.totvs.com/page/42")
        self.assertEqual(status.active_pages, 1)
        with self.assertRaises(FrozenInstanceError):
            result.title = "não permitido"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
