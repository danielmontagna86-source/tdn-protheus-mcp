from __future__ import annotations
import tomllib
import unittest
from pathlib import Path
from tdn_protheus_mcp import __version__

ROOT = Path(__file__).parents[1]


class PackageMetadataTests(unittest.TestCase):
    def test_project_declares_read_only_mcp_package(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]
        self.assertEqual(project["name"], "tdn-protheus-mcp")
        self.assertEqual(__version__, project["version"])
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["scripts"]["tdn-protheus-mcp"], "tdn_protheus_mcp.cli:main")
        self.assertNotIn("optional-dependencies", project)
        self.assertEqual(project["dependencies"], ["mcp>=1.0,<2"])


if __name__ == "__main__":
    unittest.main()
