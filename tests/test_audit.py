from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tdn_protheus_mcp.audit import AuditLog  # noqa: E402
from tdn_protheus_mcp.config import McpConfig  # noqa: E402


class AuditLogTests(unittest.TestCase):
    def test_records_only_operational_metadata_and_config_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = McpConfig(cache_root=Path(temp_dir) / "cache", allowed_root_ids=frozenset({"1"}), offline=False, allow_mutations=True)

            AuditLog(config).record("apply_snapshot_refresh", root_id="1", limits={"max_pages": 10}, duration_seconds=1.25, outcome="success")

            event = json.loads((config.cache_root / "audit.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(event["operation"], "apply_snapshot_refresh")
            self.assertEqual(event["limits"], {"max_pages": 10})
            self.assertEqual(event["outcome"], "success")
            self.assertIn("config_sha256", event)
            self.assertNotIn("cache_root", event)
            self.assertNotIn("content", event)


if __name__ == "__main__":
    unittest.main()
