from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tdn_protheus_mcp.config import McpConfig  # noqa: E402
from tdn_protheus_mcp.policy import SnapshotPolicy  # noqa: E402
from tdn_protheus_mcp.snapshot_repository import SnapshotRepository  # noqa: E402


class SnapshotRepositoryTests(unittest.TestCase):
    def test_repository_reads_only_active_pages_and_reports_snapshot_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages_dir = cache_root / "1" / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "10.json").write_text(json.dumps({"id": 10, "title": "Ativa", "url": "https://tdn.totvs.com/10", "text": "texto ativo", "fetched_at": "2026-08-15"}), encoding="utf-8")
            (pages_dir / "20.json").write_text(json.dumps({"id": 20, "title": "Removida", "url": "https://tdn.totvs.com/20", "text": "texto removido"}), encoding="utf-8")
            (cache_root / "1" / "manifest.json").write_text(
                json.dumps({"root_id": 1, "last_complete_at": "2026-08-15", "pages": {"10": {"status": "active"}, "20": {"status": "removed"}}}),
                encoding="utf-8",
            )
            repository = SnapshotRepository(SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"}))))

            pages = list(repository.active_pages("1"))
            status = repository.status("1")

            self.assertEqual([page["id"] for page in pages], [10])
            self.assertEqual(status.active_pages, 1)
            self.assertEqual(status.removed_pages, 1)
            self.assertGreater(status.cache_bytes, 0)


if __name__ == "__main__":
    unittest.main()
