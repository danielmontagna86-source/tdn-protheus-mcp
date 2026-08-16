from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tdn_protheus_mcp.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_defaults_to_read_only_and_limits_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mcp.json"
            path.write_text(json.dumps({"cache_root": temp_dir, "allowed_root_ids": ["235312129"]}), encoding="utf-8")
            config = load_config(path)
            self.assertEqual(config.allowed_root_ids, frozenset({"235312129"}))
            self.assertEqual(config.max_results, 20)

    def test_load_config_accepts_explicit_read_only_legacy_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mcp.json"
            path.write_text(json.dumps({"cache_root": temp_dir, "allowed_root_ids": [1], "offline": True, "allow_mutations": False}), encoding="utf-8")
            self.assertEqual(load_config(path).allowed_root_ids, frozenset({"1"}))

    def test_load_config_rejects_mutable_or_online_mode(self) -> None:
        for extra in ({"offline": False}, {"allow_mutations": True}):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "mcp.json"
                path.write_text(json.dumps({"cache_root": temp_dir, "allowed_root_ids": ["1"], **extra}), encoding="utf-8")
                with self.assertRaisesRegex(ConfigError, "CONFIG_READ_ONLY_REQUIRED"):
                    load_config(path)

    def test_load_config_rejects_unknown_and_non_numeric_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "mcp.json"
            path.write_text(json.dumps({"cache_root": temp_dir, "allowed_root_ids": ["../escape"]}), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "CONFIG_INVALID_ROOTS"):
                load_config(path)
            path.write_text(json.dumps({"cache_root": temp_dir, "allowed_root_ids": ["1"], "tdn_api_base": "https://example"}), encoding="utf-8")
            with self.assertRaisesRegex(ConfigError, "CONFIG_UNKNOWN_FIELD"):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
