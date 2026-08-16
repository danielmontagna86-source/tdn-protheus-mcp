from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from tdn_protheus_mcp import __version__

ROOT = Path(__file__).parents[1]


class PackageMetadataTests(unittest.TestCase):
    def test_project_declares_read_only_mcp_package(self) -> None:
        with (ROOT / "pyproject.toml").open("rb") as handle:
            metadata = tomllib.load(handle)
        project = metadata["project"]
        release_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

        self.assertEqual(project["name"], "tdn-protheus-mcp")
        self.assertEqual(__version__, project["version"])
        self.assertEqual(release_version, project["version"])
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(
            project["scripts"]["tdn-protheus-mcp"],
            "tdn_protheus_mcp.cli:main",
        )
        self.assertNotIn("optional-dependencies", project)
        self.assertEqual(project["dependencies"], ["mcp>=1.0,<2"])
        self.assertEqual(metadata["build-system"]["requires"], ["setuptools>=83"])


if __name__ == "__main__":
    unittest.main()
