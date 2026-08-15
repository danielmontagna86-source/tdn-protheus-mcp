from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tdn_protheus_mcp.config import McpConfig  # noqa: E402
from tdn_protheus_mcp.indexer import SnapshotIndexer  # noqa: E402
from tdn_protheus_mcp.policy import SnapshotPolicy  # noqa: E402
from tdn_protheus_mcp.search import SnapshotSearch  # noqa: E402
from tdn_protheus_mcp.snapshot_repository import SnapshotRepository  # noqa: E402


class SnapshotSearchTests(unittest.TestCase):
    def test_search_returns_cited_filtered_results_and_treats_fts_syntax_as_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages_dir = cache_root / "1" / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "10.json").write_text(json.dumps({"id": 10, "title": "FWRest", "url": "https://tdn.totvs.com/10", "text": "FWRest consome serviços REST no AdvPL.", "fetched_at": "2026-08-15", "modules": ["ADVPL"], "routines": ["FWRest"]}), encoding="utf-8")
            (pages_dir / "20.json").write_text(json.dumps({"id": 20, "title": "Outro", "url": "https://tdn.totvs.com/20", "text": "FWRest também aparece aqui.", "fetched_at": "2026-08-15", "modules": ["Financeiro"]}), encoding="utf-8")
            (cache_root / "1" / "manifest.json").write_text(json.dumps({"root_id": 1, "pages": {"10": {"status": "active"}, "20": {"status": "active"}}}), encoding="utf-8")
            policy = SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"})))
            repository = SnapshotRepository(policy)
            SnapshotIndexer(repository, policy).build("1")
            search = SnapshotSearch(policy)

            results = search.search(policy.search_query("FWRest", "1", 8, 12000), module="advpl")
            hostile = search.search(policy.search_query("' OR 1=1 --", "1", 8, 12000))

            self.assertEqual([(result.page_id, result.source_url) for result in results], [("10", "https://tdn.totvs.com/10")])
            self.assertEqual(hostile, ())


if __name__ == "__main__":
    unittest.main()
