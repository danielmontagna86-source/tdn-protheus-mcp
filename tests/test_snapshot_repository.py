from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tdn_protheus_mcp.config import McpConfig
from tdn_protheus_mcp.policy import SnapshotPolicy
from tdn_protheus_mcp.snapshot_repository import SnapshotRepository


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

    def test_repository_reads_the_generation_selected_by_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages_dir = cache_root / "1" / "generations" / "run-a" / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "10.json").write_text(json.dumps({"id": 10, "title": "Atualizada", "url": "https://tdn/10", "text": "nova", "fetched_at": "2026-08-15"}), encoding="utf-8")
            (cache_root / "1" / "manifest.json").write_text(json.dumps({"pages": {"10": {"status": "active"}}, "page_directory": "generations/run-a/pages"}), encoding="utf-8")
            repository = SnapshotRepository(SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"}))))

            self.assertEqual(repository.read_active_page("1", "10")["title"], "Atualizada")

    def test_repository_reads_a_schema_v1_portable_companion_skill_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages_dir = cache_root / "235312129" / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "42.json").write_text(
                json.dumps(
                    {
                        "id": 42,
                        "title": "Referência AdvPL",
                        "url": "https://tdn.totvs.com/pages/viewpage.action?pageId=42",
                        "text": "Conteúdo coletado pela skill portátil.",
                        "body_len": 41,
                        "version_number": 3,
                        "version_when": "2026-08-15T00:00:00Z",
                        "text_sha256": "a" * 64,
                        "status": "active",
                        "fetched_at": "2026-08-15T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            (cache_root / "235312129" / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "root_id": 235312129,
                        "last_complete_at": "2026-08-15T00:00:00Z",
                        "pages": {"42": {"status": "active"}},
                    }
                ),
                encoding="utf-8",
            )
            repository = SnapshotRepository(
                SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"235312129"})))
            )

            page = repository.read_active_page("235312129", "42")

            self.assertEqual(page["title"], "Referência AdvPL")
            self.assertEqual(page["url"], "https://tdn.totvs.com/pages/viewpage.action?pageId=42")


if __name__ == "__main__":
    unittest.main()
