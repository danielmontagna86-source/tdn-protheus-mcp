from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class CliTests(unittest.TestCase):
    def _config(self, temp_dir: str, roots=("1",)) -> Path:
        path = Path(temp_dir) / "mcp.json"
        path.write_text(json.dumps({"cache_root": str(Path(temp_dir) / "cache"), "allowed_root_ids": list(roots)}), encoding="utf-8")
        return path

    def test_cli_exposes_only_read_only_commands(self) -> None:
        result = subprocess.run([sys.executable, "-m", "tdn_protheus_mcp", "--help"], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0)
        for command in ("doctor", "index", "search", "status", "serve"):
            self.assertIn(command, result.stdout)
        for forbidden in ("apply-refresh", "plan-refresh", "export-hermes"):
            self.assertNotIn(forbidden, result.stdout)

    def test_doctor_reports_missing_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            (Path(temp_dir) / "cache").mkdir()
            result = subprocess.run([sys.executable, "-m", "tdn_protheus_mcp", "doctor", "--config", str(self._config(temp_dir)), "--json"], cwd=ROOT, capture_output=True, text=True, check=False)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["diagnostics"][0]["code"], "SNAPSHOT_NOT_FOUND")

    def test_index_missing_snapshot_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run([sys.executable, "-m", "tdn_protheus_mcp", "index", "--config", str(self._config(temp_dir)), "--root-id", "1", "--json"], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "POLICY_SNAPSHOT_NOT_FOUND")

    def test_index_search_status_and_stale_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages = cache_root / "1" / "pages"
            pages.mkdir(parents=True)
            (pages / "10.json").write_text(json.dumps({"id": 10, "title": "FWRest", "url": "https://tdn.totvs.com/10", "text": "FWRest usa HTTP.", "fetched_at": "2026-08-15"}), encoding="utf-8")
            manifest = cache_root / "1" / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1, "root_id": 1, "pages": {"10": {"status": "active"}}}), encoding="utf-8")
            config = self._config(temp_dir)
            index = subprocess.run([sys.executable, "-m", "tdn_protheus_mcp", "index", "--config", str(config), "--root-id", "1", "--json"], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(index.returncode, 0, index.stderr)
            search = subprocess.run([sys.executable, "-m", "tdn_protheus_mcp", "search", "--config", str(config), "--root-id", "1", "--query", "FWRest", "--json"], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(search.returncode, 0, search.stderr)
            manifest.write_text(json.dumps({"schema_version": 1, "root_id": 1, "updated_at": "new", "pages": {"10": {"status": "active"}}}), encoding="utf-8")
            stale = subprocess.run([sys.executable, "-m", "tdn_protheus_mcp", "search", "--config", str(config), "--root-id", "1", "--query", "FWRest", "--json"], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(stale.returncode, 2)
            self.assertEqual(json.loads(stale.stdout)["error"]["code"], "POLICY_INDEX_STALE")


if __name__ == "__main__":
    unittest.main()
