"""Bounded context assembly for MCP tool responses."""

from __future__ import annotations

from dataclasses import replace

from .contracts import ContextBundle, SearchResult


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
        seen_pages: set[tuple[str, str]] = set()
        remaining = max_chars
        for result in results:
            page_key = (result.root_id, result.page_id)
            if page_key in seen_pages or len(selected) >= max_chunks or remaining <= 0:
                continue
            content = result.content[:remaining]
            if not content:
                continue
            selected.append(replace(result, content=content))
            seen_pages.add(page_key)
            remaining -= len(content)
        return ContextBundle(question=question, results=tuple(selected), safety_notice="external_reference")
