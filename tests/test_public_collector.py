from __future__ import annotations

import unittest
import tempfile
import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

from tdn_protheus_mcp.contracts import PolicyRefusal, UpstreamError
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

            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["root_id"], 1)
            self.assertTrue((root / manifest["page_directory"] / "10.json").is_file())
            self.assertFalse((root / "pages" / "10.json").exists())

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

    def test_atomic_writers_can_publish_concurrently_without_sharing_a_manifest_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "cache" / "1"
            writers = [AtomicSnapshotWriter(root), AtomicSnapshotWriter(root)]
            self.assertNotEqual(writers[0].manifest_temp_path, writers[1].manifest_temp_path)
            for index, writer in enumerate(writers, start=10):
                writer.write_page({"id": index, "title": str(index), "url": f"https://tdn/{index}", "text": "conteúdo"})
            errors = []

            def commit(writer):
                try:
                    writer.commit({"root_id": 1, "pages": {"10": {"status": "active"}}})
                except Exception as error:
                    errors.append(error)

            threads = [threading.Thread(target=commit, args=(writer,)) for writer in writers]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

            self.assertEqual(errors, [])
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue((root / manifest["page_directory"]).is_dir())

    def test_atomic_writer_retains_only_the_current_and_previous_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "cache" / "1"
            for page_id in (10, 11, 12):
                writer = AtomicSnapshotWriter(root)
                writer.write_page({"id": page_id, "title": str(page_id), "url": f"https://tdn/{page_id}", "text": "conteúdo"})
                writer.commit({"root_id": 1, "pages": {str(page_id): {"status": "active"}}})

            generations = sorted(path.name for path in (root / "generations").iterdir() if path.is_dir())
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(generations), 2)
            self.assertIn(Path(manifest["page_directory"]).parts[1], generations)
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

    def test_default_http_fetcher_disables_redirects(self) -> None:
        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"id": "10"}

        with patch("requests.get", return_value=Response()) as get:
            fetcher = TdnHttpFetcher("https://example.test/rest/api")
            self.assertEqual(fetcher("10"), {"id": "10"})

        get.assert_called_once_with(
            "https://example.test/rest/api/content/10?expand=version,body.storage",
            timeout=20,
            allow_redirects=False,
        )

    def test_http_fetcher_converts_transport_failures_to_a_stable_upstream_error(self) -> None:
        def unavailable(_url, *, timeout):
            raise TimeoutError(f"timed out after {timeout}")

        fetcher = TdnHttpFetcher("https://example.test/rest/api", get=unavailable)

        with self.assertRaisesRegex(UpstreamError, "UPSTREAM_TDN_REQUEST_FAILED"):
            fetcher("10")

    def test_http_fetcher_returns_when_the_total_request_budget_expires(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"id": "10"}

        def slow_get(_url, *, timeout):
            entered.set()
            release.wait(timeout=1)
            return Response()

        fetcher = TdnHttpFetcher("https://example.test/rest/api", timeout_seconds=20, get=slow_get)
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_REFRESH_TIMEOUT"):
                fetcher("10", remaining_timeout=lambda: 0.05)
        finally:
            release.set()

        self.assertTrue(entered.is_set())
        self.assertLess(time.monotonic() - started, 0.5)

    def test_http_fetcher_does_not_accumulate_blocked_requests_after_timeout(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def slow_get(_url, *, timeout):
            calls.append(timeout)
            entered.set()
            release.wait(timeout=1)
            return None

        fetcher = TdnHttpFetcher("https://example.test/rest/api", timeout_seconds=20, get=slow_get)
        try:
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_REFRESH_TIMEOUT"):
                fetcher("10", remaining_timeout=lambda: 0.05)
            self.assertTrue(entered.is_set())
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_REFRESH_TIMEOUT"):
                fetcher("11", remaining_timeout=lambda: 0.05)
        finally:
            release.set()

        self.assertEqual(calls, [0.05])

    def test_http_fetcher_recalculates_the_budget_after_waiting_for_a_request_slot(self) -> None:
        calls = []

        class Slot:
            def __init__(self) -> None:
                self.timeouts = []

            def acquire(self, *, timeout):
                self.timeouts.append(timeout)
                return True

            def release(self) -> None:
                return None

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"id": "10"}

        fetcher = TdnHttpFetcher(
            "https://example.test/rest/api", timeout_seconds=20,
            get=lambda _url, timeout: calls.append(timeout) or Response(),
        )
        slot = Slot()
        fetcher._request_slot = slot
        remaining = iter([0.1, 0.08])

        self.assertEqual(fetcher("10", remaining_timeout=lambda: next(remaining)), {"id": "10"})

        self.assertEqual(slot.timeouts, [0.1])
        self.assertEqual(calls, [0.08])

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

    def test_http_fetcher_collects_all_paginated_children(self) -> None:
        calls = []

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return self.payload

        payloads = [
            {"results": [{"id": "11"}], "_links": {"next": "/rest/api/content/10/child/page?limit=50&start=1"}},
            {"results": [{"id": "12"}], "_links": {}},
        ]
        fetcher = TdnHttpFetcher("https://example.test/rest/api", get=lambda url, timeout: calls.append((url, timeout)) or Response(payloads.pop(0)))

        self.assertEqual(fetcher.list_children("10"), [{"id": "11"}, {"id": "12"}])
        self.assertEqual(len(calls), 2)

    def test_http_fetcher_resolves_a_query_only_pagination_link_against_the_current_page(self) -> None:
        calls = []

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return self.payload

        payloads = [
            {"results": [{"id": "11"}], "_links": {"next": "?limit=50&start=1"}},
            {"results": [{"id": "12"}], "_links": {}},
        ]
        fetcher = TdnHttpFetcher(
            "https://example.test/rest/api",
            get=lambda url, timeout: calls.append(url) or Response(payloads.pop(0)),
        )

        self.assertEqual(fetcher.list_children("10"), [{"id": "11"}, {"id": "12"}])
        self.assertEqual(
            calls[1], "https://example.test/rest/api/content/10/child/page?limit=50&start=1"
        )

    def test_http_fetcher_refuses_pagination_links_outside_the_configured_api_origin(self) -> None:
        calls = []

        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"results": [], "_links": {"next": "https://example.invalid/private"}}

        def get(url, *, timeout):
            calls.append(url)
            if len(calls) > 1:
                raise AssertionError("não deve solicitar a origem externa")
            return Response()

        fetcher = TdnHttpFetcher("https://example.test/rest/api", get=get)

        with self.assertRaisesRegex(UpstreamError, "UPSTREAM_TDN_INVALID_RESPONSE"):
            fetcher.list_children("10")
        self.assertEqual(calls, ["https://example.test/rest/api/content/10/child/page?limit=50&start=0"])

    def test_http_fetcher_refuses_a_malformed_child_list(self) -> None:
        class Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return {"results": "não é lista", "_links": {}}

        fetcher = TdnHttpFetcher("https://example.test/rest/api", get=lambda _url, timeout: Response())

        with self.assertRaisesRegex(UpstreamError, "UPSTREAM_TDN_INVALID_RESPONSE"):
            fetcher.list_children("10")

    def test_http_fetcher_uses_the_remaining_global_budget_for_each_paginated_request(self) -> None:
        calls = []

        class Response:
            def __init__(self, payload):
                self.payload = payload

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                return self.payload

        payloads = [
            {"results": [{"id": "11"}], "_links": {"next": "/rest/api/content/10/child/page?limit=50&start=1"}},
            {"results": [{"id": "12"}], "_links": {}},
        ]
        remaining = iter([8.0, 8.0, 3.0, 3.0])
        fetcher = TdnHttpFetcher(
            "https://example.test/rest/api", timeout_seconds=20,
            get=lambda url, timeout: calls.append((url, timeout)) or Response(payloads.pop(0)),
        )

        self.assertEqual(
            fetcher.list_children("10", remaining_timeout=lambda: next(remaining)),
            [{"id": "11"}, {"id": "12"}],
        )
        self.assertEqual([timeout for _url, timeout in calls], [8.0, 3.0])

    def test_collector_converts_a_page_to_snapshot_record_without_html(self) -> None:
        collector = PublicSnapshotCollector(lambda _url: {
            "id": "10", "title": "FWRest", "body": {"storage": {"value": "<h1>FWRest</h1><p>Use HTTP.</p>"}},
            "version": {"number": 3, "when": "2026-08-15"}, "_links": {"webui": "/pages/10"},
        })

        record = collector.fetch_page("10")

        self.assertEqual(record["id"], 10)
        self.assertEqual(record["url"], "https://tdn.totvs.com/pages/10")
        self.assertEqual(record["text"], "FWRest\nUse HTTP.")
        self.assertTrue(record["fetched_at"].endswith("+00:00"))
        self.assertNotIn("html", record)

    def test_collector_converts_a_malformed_page_body_to_a_stable_upstream_error(self) -> None:
        collector = PublicSnapshotCollector(lambda _url: {"id": "10", "body": "malformed"})

        with self.assertRaisesRegex(UpstreamError, "UPSTREAM_TDN_INVALID_RESPONSE"):
            collector.fetch_page("10")

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
            index_path = Path(temp_dir) / "1" / "index.sqlite3"
            index_path.parent.mkdir()
            index_path.write_text("stale", encoding="utf-8")
            result = PublicSnapshotRefresher(collector, Path(temp_dir))(plan)
            manifest = json.loads((Path(temp_dir) / "1" / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(index_path.exists())

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
