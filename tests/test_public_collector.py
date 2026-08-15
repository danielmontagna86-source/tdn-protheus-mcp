from __future__ import annotations

import unittest
import tempfile
import json
from pathlib import Path

from tdn_protheus_mcp.contracts import PolicyRefusal
from tdn_protheus_mcp.mutations import RefreshPlan
from tdn_protheus_mcp.public_collector import AtomicSnapshotWriter, PublicSnapshotCollector, PublicSnapshotRefresher, TdnHttpFetcher


class PublicSnapshotCollectorTests(unittest.TestCase):
    def test_atomic_writer_does_not_publish_manifest_until_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "cache" / "1"
            writer = AtomicSnapshotWriter(root)
            writer.write_page({"id": 10, "title": "FWRest", "url": "https://tdn/10", "text": "conteúdo"})
            self.assertFalse((root / "manifest.json").exists())

            writer.commit({"root_id": 1, "pages": {"10": {"status": "active"}}})

            self.assertEqual(json.loads((root / "manifest.json").read_text(encoding="utf-8"))["root_id"], 1)
            self.assertTrue((root / "pages" / "10.json").is_file())

    def test_atomic_writer_abort_removes_staging_without_touching_published_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "cache" / "1"
            root.mkdir(parents=True)
            (root / "manifest.json").write_text('{"root_id": 1, "stable": true}', encoding="utf-8")
            writer = AtomicSnapshotWriter(root)
            writer.write_page({"id": 11, "title": "Nova", "url": "https://tdn/11", "text": "novo"})

            writer.abort()

            self.assertEqual(json.loads((root / "manifest.json").read_text(encoding="utf-8"))["stable"], True)
            self.assertFalse((root / "pages" / "11.json").exists())
    def test_http_fetcher_uses_explicit_timeout_and_validates_json_response(self) -> None:
        calls = []

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"id": "10"}

        fetcher = TdnHttpFetcher("https://example.test/rest/api", timeout_seconds=7, get=lambda url, timeout: calls.append((url, timeout)) or Response())

        self.assertEqual(fetcher("10"), {"id": "10"})
        self.assertEqual(calls, [("https://example.test/rest/api/content/10?expand=version,body.storage", 7)])

    def test_http_fetcher_requests_child_pages_with_the_same_timeout(self) -> None:
        calls = []

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"results": [{"id": "11"}]}

        fetcher = TdnHttpFetcher(
            "https://example.test/rest/api", timeout_seconds=9,
            get=lambda url, timeout: calls.append((url, timeout)) or Response(),
        )

        self.assertEqual(fetcher.fetch_children("10"), {"results": [{"id": "11"}]})
        self.assertEqual(calls, [("https://example.test/rest/api/content/10/child/page?limit=50&start=0", 9)])

    def test_collector_converts_a_page_to_snapshot_record_without_html(self) -> None:
        collector = PublicSnapshotCollector(lambda _url: {
            "id": "10", "title": "FWRest", "body": {"storage": {"value": "<h1>FWRest</h1><p>Use HTTP.</p>"}},
            "version": {"number": 3, "when": "2026-08-15"}, "_links": {"webui": "/pages/10"},
        })

        record = collector.fetch_page("10")

        self.assertEqual(record["id"], 10)
        self.assertEqual(record["url"], "https://tdn.totvs.com/pages/10")
        self.assertEqual(record["text"], "FWRest\nUse HTTP.")
        self.assertNotIn("html", record)

    def test_collector_discovers_children_breadth_first_with_a_depth_limit(self) -> None:
        children = {
            "1": {"results": [{"id": "2"}, {"id": "3"}]},
            "2": {"results": [{"id": "4"}]},
            "3": {"results": [{"id": "5"}]},
        }
        collector = PublicSnapshotCollector(
            lambda _page_id: {"id": "unused"},
            fetch_children=lambda page_id: children.get(page_id, {"results": []}),
        )

        self.assertEqual(collector.discover_tree("1", max_depth=1, max_pages=10), ["1", "2", "3"])

    def test_collector_refuses_a_tree_that_exceeds_the_page_limit(self) -> None:
        collector = PublicSnapshotCollector(
            lambda _page_id: {"id": "unused"},
            fetch_children=lambda _page_id: {"results": [{"id": "2"}]},
        )

        with self.assertRaisesRegex(RuntimeError, "limite de 1 páginas"):
            collector.discover_tree("1", max_depth=1, max_pages=1)

    def test_collector_checks_cancellation_before_discovering_any_page(self) -> None:
        calls = []
        collector = PublicSnapshotCollector(
            lambda _page_id: {"id": "unused"},
            fetch_children=lambda page_id: calls.append(page_id) or {"results": []},
        )

        with self.assertRaisesRegex(PolicyRefusal, "POLICY_REFRESH_CANCELLED"):
            collector.discover_tree("1", max_depth=1, max_pages=10, cancelled=lambda: True)

        self.assertEqual(calls, [])

    def test_refresher_publishes_a_complete_discovered_tree(self) -> None:
        pages = {
            "1": {"id": "1", "title": "Raiz", "body": {"storage": {"value": "<p>raiz</p>"}}, "version": {"number": 1}, "_links": {"webui": "/1"}},
            "2": {"id": "2", "title": "Filha", "body": {"storage": {"value": "<p>filha</p>"}}, "version": {"number": 1}, "_links": {"webui": "/2"}},
        }
        collector = PublicSnapshotCollector(
            lambda page_id: pages[page_id],
            fetch_children=lambda page_id: {"results": [{"id": "2"}]} if page_id == "1" else {"results": []},
        )
        plan = RefreshPlan("1", max_depth=1, estimated_pages=2, estimated_disk_bytes=1, minimum_duration_seconds=0)

        with tempfile.TemporaryDirectory() as temp_dir:
            result = PublicSnapshotRefresher(collector, Path(temp_dir))(plan)
            manifest = json.loads((Path(temp_dir) / "1" / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(result, {"root_id": 1, "pages_saved": 2})
        self.assertEqual(manifest["pages"]["2"]["status"], "active")

    def test_refresher_cancellation_preserves_the_previous_manifest_and_cleans_staging(self) -> None:
        collector = PublicSnapshotCollector(
            lambda _page_id: self.fail("não deve buscar página após cancelamento"),
            fetch_children=lambda _page_id: {"results": []},
        )
        plan = RefreshPlan("1", max_depth=0, estimated_pages=1, estimated_disk_bytes=1, minimum_duration_seconds=0)
        cancellations = iter([False, True])

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "1"
            root.mkdir()
            (root / "manifest.json").write_text('{"root_id": 1, "stable": true}', encoding="utf-8")
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_REFRESH_CANCELLED"):
                PublicSnapshotRefresher(collector, Path(temp_dir))(plan, cancelled=lambda: next(cancellations))

            self.assertEqual(json.loads((root / "manifest.json").read_text(encoding="utf-8"))["stable"], True)
            self.assertEqual(list(Path(temp_dir).glob("tdn-refresh-*")), [])


if __name__ == "__main__":
    unittest.main()
