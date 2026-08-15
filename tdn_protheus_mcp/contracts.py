"""Immutable public contracts shared by the CLI and MCP transport."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchQuery:
    query: str
    root_id: str
    max_results: int
    max_chars: int


@dataclass(frozen=True)
class SearchResult:
    root_id: str
    page_id: str
    chunk_id: str
    title: str
    source_url: str
    content: str
    collected_at: str | None
    version_number: int | None = None


@dataclass(frozen=True)
class ContextBundle:
    question: str
    results: tuple[SearchResult, ...]
    safety_notice: str


@dataclass(frozen=True)
class SnapshotStatus:
    root_id: str
    active_pages: int
    removed_pages: int
    cache_bytes: int
    last_complete_at: str | None = None


@dataclass(frozen=True)
class PolicyRefusal(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
