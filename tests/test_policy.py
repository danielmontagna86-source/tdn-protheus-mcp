from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tdn_protheus_mcp.config import McpConfig  # noqa: E402
from tdn_protheus_mcp.contracts import PolicyRefusal  # noqa: E402
from tdn_protheus_mcp.policy import SnapshotPolicy  # noqa: E402


class SnapshotPolicyTests(unittest.TestCase):
    def test_policy_refuses_unknown_roots_and_paths_outside_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            cache_root.mkdir()
            policy = SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"})))

            with self.assertRaisesRegex(PolicyRefusal, "POLICY_ROOT_NOT_ALLOWED"):
                policy.require_root("2")
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_PATH_OUTSIDE_CACHE"):
                policy.require_path(Path(temp_dir) / "outside.json")

    def test_policy_creates_only_bounded_nonempty_search_queries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy = SnapshotPolicy(McpConfig(cache_root=Path(temp_dir), allowed_root_ids=frozenset({"1"}), max_results=20, max_chars=24000))

            query = policy.search_query(" FWRest ", "1", 8, 12000)

            self.assertEqual(query.query, "FWRest")
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_LIMIT_EXCEEDED"):
                policy.search_query("FWRest", "1", 21, 12000)
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_EMPTY_QUERY"):
                policy.search_query("   ", "1", 8, 12000)

    def test_policy_accepts_a_cache_path_when_config_uses_an_equivalent_unresolved_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            cache_root.mkdir()
            equivalent_root = cache_root / ".." / "cache"
            policy = SnapshotPolicy(McpConfig(cache_root=equivalent_root, allowed_root_ids=frozenset({"1"})))

            accepted = policy.require_path(cache_root / "1" / "index.sqlite3")

            self.assertEqual(accepted, (cache_root / "1" / "index.sqlite3").resolve())


if __name__ == "__main__":
    unittest.main()
