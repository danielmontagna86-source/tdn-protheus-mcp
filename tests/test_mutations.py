from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tdn_protheus_mcp.config import McpConfig  # noqa: E402
from tdn_protheus_mcp.contracts import PolicyRefusal  # noqa: E402
from tdn_protheus_mcp.mutations import RefreshOperations  # noqa: E402
from tdn_protheus_mcp.refresh_adapter import SnapshotRefreshAdapter  # noqa: E402


class RefreshOperationsTests(unittest.TestCase):
    def test_public_refresh_adapter_honors_preflight_cancellation_without_calling_collector(self) -> None:
        calls = []
        adapter = SnapshotRefreshAdapter(lambda _plan: calls.append("called") or {"changed": 1})
        operations = RefreshOperations(McpConfig(cache_root=Path(tempfile.gettempdir()) / "cache", allowed_root_ids=frozenset({"1"}), offline=False, allow_mutations=True), refresh_runner=adapter)

        with self.assertRaisesRegex(PolicyRefusal, "POLICY_REFRESH_CANCELLED"):
            operations.apply_snapshot_refresh("1", max_depth=1, max_pages=10, confirmation="APPLY", cancelled=lambda: True)
        self.assertEqual(calls, [])

    def test_public_refresh_adapter_refuses_an_expired_timeout_before_calling_collector(self) -> None:
        calls = []
        adapter = SnapshotRefreshAdapter(lambda _plan: calls.append("called") or {"changed": 1})
        plan = RefreshOperations(McpConfig(cache_root=Path(tempfile.gettempdir()) / "cache", allowed_root_ids=frozenset({"1"}))).plan_snapshot_refresh("1", max_depth=1, max_pages=10)

        with self.assertRaisesRegex(PolicyRefusal, "POLICY_REFRESH_TIMEOUT"):
            adapter(plan, timeout_seconds=0)
        self.assertEqual(calls, [])

    def test_public_refresh_adapter_enforces_timeout_during_collection(self) -> None:
        clock = iter([0.0, 6.0])

        def collector(_plan, *, cancelled):
            cancelled()
            return {"changed": 1}

        adapter = SnapshotRefreshAdapter(collector, clock=lambda: next(clock))
        plan = RefreshOperations(McpConfig(cache_root=Path(tempfile.gettempdir()) / "cache", allowed_root_ids=frozenset({"1"}))).plan_snapshot_refresh("1", max_depth=1, max_pages=10)

        with self.assertRaisesRegex(PolicyRefusal, "POLICY_REFRESH_TIMEOUT"):
            adapter(plan, timeout_seconds=5)

    def test_plan_is_offline_read_only_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            operations = RefreshOperations(
                McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"235312129"}))
            )

            plan = operations.plan_snapshot_refresh("235312129", max_depth=3, max_pages=80)

            self.assertEqual(plan.root_id, "235312129")
            self.assertEqual(plan.max_depth, 3)
            self.assertEqual(plan.estimated_pages, 80)
            self.assertGreater(plan.estimated_disk_bytes, 0)
            self.assertGreater(plan.minimum_duration_seconds, 0)
            self.assertFalse(cache_root.exists())

    def test_apply_refuses_when_offline_or_without_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            operations = RefreshOperations(
                McpConfig(cache_root=Path(temp_dir), allowed_root_ids=frozenset({"1"}), offline=True, allow_mutations=True)
            )

            with self.assertRaisesRegex(PolicyRefusal, "POLICY_OFFLINE"):
                operations.apply_snapshot_refresh("1", max_depth=1, max_pages=10, confirmation="APPLY")

    def test_apply_runs_only_after_all_explicit_authorizations_and_audits_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            calls = []
            operations = RefreshOperations(
                McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"}), offline=False, allow_mutations=True),
                refresh_runner=lambda plan, *, cancelled=None: calls.append(plan) or {"changed": 2},
            )

            result = operations.apply_snapshot_refresh("1", max_depth=1, max_pages=10, confirmation="APPLY")

            self.assertEqual(result, {"changed": 2})
            self.assertEqual(calls[0].estimated_pages, 10)
            self.assertEqual(json.loads((cache_root / "audit.jsonl").read_text(encoding="utf-8"))["outcome"], "success")

    def test_export_hermes_writes_only_a_safe_jsonl_under_cache_exports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages = cache_root / "1" / "pages"
            pages.mkdir(parents=True)
            (pages / "10.json").write_text(json.dumps({"id": 10, "title": "FWRest", "url": "https://tdn.totvs.com/10", "text": "conteúdo"}), encoding="utf-8")
            (cache_root / "1" / "manifest.json").write_text(json.dumps({"pages": {"10": {"status": "active"}}}), encoding="utf-8")
            operations = RefreshOperations(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"}), allow_mutations=True))

            exported = operations.export_hermes_context("1", "advpl-context.jsonl")

            self.assertEqual(exported.name, "advpl-context.jsonl")
            self.assertEqual(exported.parent, cache_root / "exports")
            self.assertIn('"source_url": "https://tdn.totvs.com/10"', exported.read_text(encoding="utf-8"))
            audit_event = json.loads((cache_root / "audit.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(audit_event["operation"], "export_hermes_context")
            self.assertNotIn("content", audit_event)
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_EXPORT_NAME"):
                operations.export_hermes_context("1", "../escape.jsonl")

    def test_apply_does_not_retry_a_type_error_raised_by_the_refresh_runner(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            calls = []

            def broken_runner(_plan, **_kwargs):
                calls.append("called")
                raise TypeError("collector implementation bug")

            operations = RefreshOperations(
                McpConfig(cache_root=Path(temp_dir) / "cache", allowed_root_ids=frozenset({"1"}), offline=False, allow_mutations=True),
                refresh_runner=broken_runner,
            )

            with self.assertRaisesRegex(TypeError, "collector implementation bug"):
                operations.apply_snapshot_refresh("1", max_depth=1, max_pages=10, confirmation="APPLY")

            self.assertEqual(calls, ["called"])


if __name__ == "__main__":
    unittest.main()
