"""Safe FTS5 search over a derived local index."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from .contracts import PolicyRefusal, SearchQuery, SearchResult
from .policy import SnapshotPolicy


_FILTER_COLUMNS = {
    "module": "modules_json",
    "table": "tables_json",
    "routine": "routines_json",
    "parameter": "parameters_json",
}


def _fts_expression(query: str) -> str | None:
    tokens = re.findall(r"[^\W_]+|\d+", query, flags=re.UNICODE)
    if not tokens:
        return None
    return " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def _metadata_has(value: str, expected: str | None) -> bool:
    if expected is None:
        return True
    try:
        entries = json.loads(value)
    except json.JSONDecodeError:
        return False
    return isinstance(entries, list) and any(str(entry).casefold() == expected.casefold() for entry in entries)


class SnapshotSearch:
    def __init__(self, policy: SnapshotPolicy) -> None:
        self._policy = policy

    def _index_path(self, root_id: str) -> Path:
        return self._policy.require_path(self._policy.cache_root / self._policy.require_root(root_id) / "index.sqlite3")

    def search(
        self,
        query: SearchQuery,
        *,
        module: str | None = None,
        table: str | None = None,
        routine: str | None = None,
        parameter: str | None = None,
    ) -> tuple[SearchResult, ...]:
        expression = _fts_expression(query.query)
        if expression is None:
            return ()
        index_path = self._index_path(query.root_id)
        if not index_path.is_file():
            raise PolicyRefusal("POLICY_INDEX_NOT_FOUND", f"índice inexistente para root_id={query.root_id}; execute 'index' explicitamente")
        filters = {"module": module, "table": table, "routine": routine, "parameter": parameter}
        candidate_limit = query.max_results * 20
        connection = sqlite3.connect(index_path)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                """
                SELECT c.*, bm25(chunks_fts) AS rank
                FROM chunks_fts
                JOIN chunks AS c ON c.rowid = chunks_fts.rowid
                WHERE chunks_fts MATCH ? AND c.root_id = ?
                ORDER BY rank, c.page_id, c.chunk_id
                LIMIT ?
                """,
                (expression, query.root_id, candidate_limit),
            ).fetchall()
        except sqlite3.Error as error:
            raise PolicyRefusal("POLICY_INDEX_INVALID", f"índice inválido para root_id={query.root_id}") from error
        finally:
            connection.close()
        results: list[SearchResult] = []
        for row in rows:
            if not all(_metadata_has(row[_FILTER_COLUMNS[name]], expected) for name, expected in filters.items()):
                continue
            content = str(row["content"])
            if len(content) > query.max_chars:
                content = content[: query.max_chars]
            result = SearchResult(
                root_id=str(row["root_id"]),
                page_id=str(row["page_id"]),
                chunk_id=str(row["chunk_id"]),
                title=str(row["title"]),
                source_url=str(row["source_url"]),
                content=content,
                collected_at=row["collected_at"],
                version_number=row["version_number"],
            )
            results.append(result)
            if len(results) >= query.max_results:
                break
        return tuple(results)
