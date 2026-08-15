"""Deterministic SQLite FTS5 index derived from the local snapshot."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .policy import SnapshotPolicy
from .snapshot_repository import SnapshotRepository


SCHEMA_VERSION = 1
CHUNK_SIZE = 2_000


@dataclass(frozen=True)
class IndexBuild:
    root_id: str
    index_path: Path
    chunks_indexed: int


def _chunks(text: str) -> Iterator[str]:
    text = text.strip()
    for start in range(0, len(text), CHUNK_SIZE):
        chunk = text[start : start + CHUNK_SIZE].strip()
        if chunk:
            yield chunk


def _metadata(record: dict[str, Any], field: str) -> str:
    value = record.get(field, [])
    return json.dumps(value if isinstance(value, list) else [], ensure_ascii=False, sort_keys=True)


class SnapshotIndexer:
    def __init__(self, repository: SnapshotRepository, policy: SnapshotPolicy) -> None:
        self._repository = repository
        self._policy = policy

    def _index_path(self, root_id: str) -> Path:
        normalized = self._policy.require_root(root_id)
        return self._policy.require_path(self._policy.cache_root / normalized / "index.sqlite3")

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE chunks (
                chunk_id TEXT PRIMARY KEY,
                root_id TEXT NOT NULL,
                page_id TEXT NOT NULL,
                title TEXT NOT NULL,
                source_url TEXT NOT NULL,
                version_number INTEGER,
                collected_at TEXT,
                modules_json TEXT NOT NULL,
                tables_json TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                routines_json TEXT NOT NULL,
                entry_points_json TEXT NOT NULL,
                target_audience TEXT,
                content TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE chunks_fts USING fts5(title, content);
            """
        )
        connection.execute("INSERT INTO schema_metadata(key, value) VALUES (?, ?)", ("schema_version", str(SCHEMA_VERSION)))

    def build(self, root_id: str) -> IndexBuild:
        normalized = self._policy.require_root(root_id)
        index_path = self._index_path(normalized)
        temporary_path = index_path.with_suffix(".sqlite3.tmp")
        if temporary_path.exists():
            temporary_path.unlink()
        chunk_count = 0
        try:
            connection = sqlite3.connect(temporary_path)
            try:
                self._create_schema(connection)
                for record in self._repository.active_pages(normalized):
                    page_id = str(record["id"])
                    for chunk_index, content in enumerate(_chunks(str(record.get("text", "")))):
                        chunk_id = f"{page_id}:{chunk_index}"
                        connection.execute(
                            """
                            INSERT INTO chunks(
                                chunk_id, root_id, page_id, title, source_url, version_number, collected_at,
                                modules_json, tables_json, parameters_json, routines_json, entry_points_json,
                                target_audience, content
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                chunk_id,
                                normalized,
                                page_id,
                                str(record.get("title", f"page-{page_id}")),
                                str(record.get("url", "")),
                                record.get("version_number"),
                                record.get("fetched_at"),
                                _metadata(record, "modules"),
                                _metadata(record, "tables"),
                                _metadata(record, "parameters"),
                                _metadata(record, "routines"),
                                _metadata(record, "entry_points"),
                                record.get("target_audience"),
                                content,
                            ),
                        )
                        connection.execute("INSERT INTO chunks_fts(rowid, title, content) VALUES (last_insert_rowid(), ?, ?)", (str(record.get("title", "")), content))
                        chunk_count += 1
                connection.commit()
            finally:
                connection.close()
            os.replace(temporary_path, index_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        return IndexBuild(root_id=normalized, index_path=index_path, chunks_indexed=chunk_count)
