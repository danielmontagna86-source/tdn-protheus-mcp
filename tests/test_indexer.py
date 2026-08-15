from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tdn_protheus_mcp.config import McpConfig  # noqa: E402
from tdn_protheus_mcp.indexer import SnapshotIndexer  # noqa: E402
from tdn_protheus_mcp.policy import SnapshotPolicy  # noqa: E402
from tdn_protheus_mcp.snapshot_repository import SnapshotRepository  # noqa: E402


class SnapshotIndexerTests(unittest.TestCase):
    def test_build_is_idempotent_and_indexes_only_active_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages_dir = cache_root / "1" / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "10.json").write_text(json.dumps({"id": 10, "title": "FWRest", "url": "https://tdn.totvs.com/10", "text": "Use FWRest para chamar serviços REST.", "fetched_at": "2026-08-15", "version_number": 3}), encoding="utf-8")
            (pages_dir / "20.json").write_text(json.dumps({"id": 20, "title": "Removida", "url": "https://tdn.totvs.com/20", "text": "não indexar"}), encoding="utf-8")
            (cache_root / "1" / "manifest.json").write_text(json.dumps({"root_id": 1, "pages": {"10": {"status": "active"}, "20": {"status": "removed"}}}), encoding="utf-8")
            policy = SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"})))
            indexer = SnapshotIndexer(SnapshotRepository(policy), policy)

            first = indexer.build("1")
            second = indexer.build("1")
            connection = sqlite3.connect(first.index_path)
            try:
                rows = connection.execute("SELECT page_id, title, source_url, version_number FROM chunks").fetchall()
            finally:
                connection.close()

            self.assertEqual(first.chunks_indexed, 1)
            self.assertEqual(second.chunks_indexed, 1)
            self.assertEqual(rows, [("10", "FWRest", "https://tdn.totvs.com/10", 3)])


if __name__ == "__main__":
    unittest.main()
