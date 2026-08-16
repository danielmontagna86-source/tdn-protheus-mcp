from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tdn_protheus_mcp.config import McpConfig
from tdn_protheus_mcp.indexer import SCHEMA_VERSION, SnapshotIndexer
from tdn_protheus_mcp.policy import SnapshotPolicy
from tdn_protheus_mcp.snapshot_repository import SnapshotRepository


class SnapshotIndexerTests(unittest.TestCase):
    def test_build_binds_index_to_snapshot_and_indexes_only_active_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir) / "cache"
            pages = cache / "1" / "pages"
            pages.mkdir(parents=True)
            (pages / "10.json").write_text(json.dumps({"id": 10, "title": "FWRest", "url": "https://tdn.totvs.com/10", "text": "Use FWRest e MATA103 na SD1 com MV_TESTE.", "fetched_at": "2026-08-15"}), encoding="utf-8")
            (pages / "20.json").write_text(json.dumps({"id": 20, "title": "Removida", "url": "https://tdn/20", "text": "não indexar"}), encoding="utf-8")
            (cache / "1" / "manifest.json").write_text(json.dumps({"schema_version": 1, "root_id": 1, "pages": {"10": {"status": "active"}, "20": {"status": "removed"}}}), encoding="utf-8")
            policy = SnapshotPolicy(McpConfig(cache_root=cache, allowed_root_ids=frozenset({"1"})))
            repo = SnapshotRepository(policy)
            build = SnapshotIndexer(repo, policy).build("1")
            connection = sqlite3.connect(build.index_path)
            try:
                metadata = dict(connection.execute("SELECT key, value FROM schema_metadata").fetchall())
                tags = set(connection.execute("SELECT kind, value FROM chunk_tags").fetchall())
            finally:
                connection.close()
            self.assertEqual(metadata["schema_version"], str(SCHEMA_VERSION))
            self.assertEqual(metadata["snapshot_fingerprint"], repo.snapshot_fingerprint("1"))
            self.assertIn(("routine", "MATA103"), tags)
            self.assertIn(("table", "SD1"), tags)
            self.assertIn(("parameter", "MV_TESTE"), tags)


if __name__ == "__main__":
    unittest.main()
