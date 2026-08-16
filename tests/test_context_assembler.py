from __future__ import annotations

import unittest

from tdn_protheus_mcp.context_assembler import ContextAssembler
from tdn_protheus_mcp.contracts import SearchResult


class ContextAssemblerTests(unittest.TestCase):
    def test_assembler_keeps_up_to_two_chunks_per_page_and_respects_budget(self) -> None:
        first = SearchResult("1", "10", "10:0", "Primeira", "https://tdn/10", "123456", "2026-08-15")
        adjacent = SearchResult("1", "10", "10:1", "Primeira", "https://tdn/10", "abcdef", "2026-08-15")
        third_same_page = SearchResult("1", "10", "10:2", "Primeira", "https://tdn/10", "não deve entrar", "2026-08-15")
        second_page = SearchResult("1", "20", "20:0", "Segunda", "https://tdn/20", "XYZXYZ", "2026-08-15")

        bundle = ContextAssembler().assemble(
            "Como usar?",
            (first, adjacent, third_same_page, second_page),
            max_chunks=3,
            max_chars=15,
        )

        self.assertEqual([result.chunk_id for result in bundle.results], ["10:0", "10:1", "20:0"])
        self.assertEqual(sum(len(result.content) for result in bundle.results), 15)
        self.assertEqual(bundle.results[-1].content, "XYZ")
        self.assertEqual(bundle.safety_notice, "external_reference")

    def test_assembler_deduplicates_exact_chunk(self) -> None:
        result = SearchResult("1", "10", "10:0", "Primeira", "https://tdn/10", "abc", "2026-08-15")
        bundle = ContextAssembler().assemble("Q", (result, result), max_chunks=4, max_chars=100)
        self.assertEqual(len(bundle.results), 1)


if __name__ == "__main__":
    unittest.main()
