from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tdn_protheus_mcp.context_assembler import ContextAssembler  # noqa: E402
from tdn_protheus_mcp.contracts import SearchResult  # noqa: E402


class ContextAssemblerTests(unittest.TestCase):
    def test_assembler_deduplicates_pages_and_respects_total_character_budget(self) -> None:
        first = SearchResult("1", "10", "10:0", "Primeira", "https://tdn/10", "12345678", "2026-08-15")
        duplicate = SearchResult("1", "10", "10:1", "Primeira", "https://tdn/10", "não deve entrar", "2026-08-15")
        second = SearchResult("1", "20", "20:0", "Segunda", "https://tdn/20", "abcdefgh", "2026-08-15")

        bundle = ContextAssembler().assemble("Como usar?", (first, duplicate, second), max_chunks=2, max_chars=12)

        self.assertEqual([result.page_id for result in bundle.results], ["10", "20"])
        self.assertEqual(sum(len(result.content) for result in bundle.results), 12)
        self.assertEqual(bundle.safety_notice, "external_reference")


if __name__ == "__main__":
    unittest.main()
