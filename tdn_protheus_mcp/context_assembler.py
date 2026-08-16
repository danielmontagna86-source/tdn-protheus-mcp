"""Bounded context assembly for MCP tool responses."""
from __future__ import annotations

from collections import Counter
from dataclasses import replace

from .contracts import ContextBundle, SearchResult

MAX_CHUNKS_PER_PAGE = 2


class ContextAssembler:
    def assemble(
        self,
        question: str,
        results: tuple[SearchResult, ...],
        *,
        max_chunks: int,
        max_chars: int,
    ) -> ContextBundle:
        selected: list[SearchResult] = []
        seen_chunks: set[tuple[str, str, str]] = set()
        per_page: Counter[tuple[str, str]] = Counter()
        remaining = max_chars
        for result in results:
            page_key = (result.root_id, result.page_id)
            chunk_key = (result.root_id, result.page_id, result.chunk_id)
            if (
                chunk_key in seen_chunks
                or per_page[page_key] >= MAX_CHUNKS_PER_PAGE
                or len(selected) >= max_chunks
                or remaining <= 0
            ):
                continue
            content = result.content[:remaining]
            if not content:
                continue
            selected.append(replace(result, content=content))
            seen_chunks.add(chunk_key)
            per_page[page_key] += 1
            remaining -= len(content)
        return ContextBundle(question=question, results=tuple(selected), safety_notice="external_reference")
