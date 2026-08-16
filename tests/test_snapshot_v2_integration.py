from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tdn_protheus_mcp.config import McpConfig
from tdn_protheus_mcp.contracts import PolicyRefusal
from tdn_protheus_mcp.indexer import SnapshotIndexer
from tdn_protheus_mcp.policy import SnapshotPolicy
from tdn_protheus_mcp.search import SnapshotSearch
from tdn_protheus_mcp.snapshot_repository import SnapshotRepository


class SnapshotV2IntegrationTests(unittest.TestCase):
    def test_generation_snapshot_indexes_searches_and_detects_manifest_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            root = cache_root / "1"
            generation1 = root / "generations" / "g1" / "pages"
            generation1.mkdir(parents=True)
            (generation1 / "10.json").write_text(
                json.dumps({
                    "id": 10,
                    "title": "MATA103 Documento de Entrada",
                    "url": "https://tdn.totvs.com/10",
                    "text": "MATA103 usa SD1 no Documento de Entrada.",
                    "fetched_at": "2026-08-16T20:00:00+00:00",
                }),
                encoding="utf-8",
            )
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps({
                    "schema_version": 2,
                    "root_id": 1,
                    "generation_id": "g1",
                    "page_directory": "generations/g1/pages",
                    "updated_at": "2026-08-16T20:00:00+00:00",
                    "pages": {"10": {"status": "active"}},
                }),
                encoding="utf-8",
            )
            policy = SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"})))
            repository = SnapshotRepository(policy)
            indexer = SnapshotIndexer(repository, policy)
            search = SnapshotSearch(policy)

            indexer.build("1")
            results = search.search(policy.search_query("MATA103", "1", 8, 12000), routine="MATA103")
            self.assertEqual([(item.page_id, item.source_url) for item in results], [("10", "https://tdn.totvs.com/10")])

            generation2 = root / "generations" / "g2" / "pages"
            generation2.mkdir(parents=True)
            (generation2 / "20.json").write_text(
                json.dumps({
                    "id": 20,
                    "title": "PLRSTPR1",
                    "url": "https://tdn.totvs.com/20",
                    "text": "PLRSTPR1 recebe PARAMIXB.",
                    "fetched_at": "2026-08-16T21:00:00+00:00",
                }),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps({
                    "schema_version": 2,
                    "root_id": 1,
                    "generation_id": "g2",
                    "page_directory": "generations/g2/pages",
                    "updated_at": "2026-08-16T21:00:00+00:00",
                    "pages": {"20": {"status": "active"}},
                }),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PolicyRefusal, "POLICY_INDEX_STALE"):
                search.search(policy.search_query("MATA103", "1", 8, 12000))

            indexer.build("1")
            updated = search.search(policy.search_query("PLRSTPR1", "1", 8, 12000), routine="PLRSTPR1")
            self.assertEqual([item.page_id for item in updated], ["20"])

    def test_page_directory_cannot_escape_cache_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            root = cache_root / "1"
            root.mkdir(parents=True)
            (root / "manifest.json").write_text(
                json.dumps({
                    "schema_version": 2,
                    "root_id": 1,
                    "page_directory": "../../outside",
                    "pages": {"10": {"status": "active"}},
                }),
                encoding="utf-8",
            )
            policy = SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"})))
            repository = SnapshotRepository(policy)
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_PATH_OUTSIDE_CACHE"):
                repository.read_active_page("1", "10")

    def test_page_directory_cannot_cross_to_sibling_root_inside_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            root1 = cache_root / "1"
            root2_pages = cache_root / "2" / "pages"
            root1.mkdir(parents=True)
            root2_pages.mkdir(parents=True)
            (root2_pages / "10.json").write_text(
                json.dumps({"id": 10, "title": "Outra raiz", "url": "https://tdn/10", "text": "segredo lógico"}),
                encoding="utf-8",
            )
            (root1 / "manifest.json").write_text(
                json.dumps({
                    "schema_version": 2,
                    "root_id": 1,
                    "page_directory": "../2/pages",
                    "pages": {"10": {"status": "active"}},
                }),
                encoding="utf-8",
            )
            policy = SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"})))
            repository = SnapshotRepository(policy)
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_SNAPSHOT_INVALID"):
                repository.read_active_page("1", "10")


if __name__ == "__main__":
    unittest.main()
