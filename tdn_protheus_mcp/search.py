"""Safe, snapshot-bound FTS5 search over the derived local index."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from .contracts import PolicyRefusal, SearchQuery, SearchResult
from .indexer import SCHEMA_VERSION
from .policy import SnapshotPolicy
from .snapshot_repository import SnapshotRepository

_FILTER_KINDS = {"module": "module", "table": "table", "routine": "routine", "parameter": "parameter"}


def _fts_expression(query: str) -> str | None:
    tokens = re.findall(r"[^\W_]+|\d+", query, flags=re.UNICODE)
    if not tokens:
        return None
    return " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


class SnapshotSearch:
    def __init__(self, policy: SnapshotPolicy) -> None:
        self._policy = policy
        self._repository = SnapshotRepository(policy)

    def _index_path(self, root_id: str) -> Path:
        return self._policy.require_path(self._policy.cache_root / self._policy.require_root(root_id) / "index.sqlite3")

    def index_status(self, root_id: str) -> str:
        index_path = self._index_path(root_id)
        if not index_path.is_file():
            return "missing"
        try:
            connection = sqlite3.connect(f"file:{index_path.as_posix()}?mode=ro", uri=True)
            try:
                metadata = dict(connection.execute("SELECT key, value FROM schema_metadata").fetchall())
            finally:
                connection.close()
        except sqlite3.Error:
            return "invalid"
        if metadata.get("schema_version") != str(SCHEMA_VERSION):
            return "stale"
        return "current" if metadata.get("snapshot_fingerprint") == self._repository.snapshot_fingerprint(root_id) else "stale"

    def _require_current_index(self, root_id: str) -> Path:
        status = self.index_status(root_id)
        if status == "missing":
            raise PolicyRefusal("POLICY_INDEX_NOT_FOUND", f"índice inexistente para root_id={root_id}; execute 'index' explicitamente")
        if status == "stale":
            raise PolicyRefusal("POLICY_INDEX_STALE", f"índice desatualizado para root_id={root_id}; execute 'index' novamente")
        if status == "invalid":
            raise PolicyRefusal("POLICY_INDEX_INVALID", f"índice inválido para root_id={root_id}")
        return self._index_path(root_id)

    def search(self, query: SearchQuery, *, module: str | None = None, table: str | None = None, routine: str | None = None, parameter: str | None = None) -> tuple[SearchResult, ...]:
        expression = _fts_expression(query.query)
        if expression is None:
            return ()
        index_path = self._require_current_index(query.root_id)
        filters = {"module": module, "table": table, "routine": routine, "parameter": parameter}
        where = ["chunks_fts MATCH ?", "c.root_id = ?"]
        params: list[object] = [expression, query.root_id]
        for name, expected in filters.items():
            if expected is None:
                continue
            where.append("EXISTS (SELECT 1 FROM chunk_tags t WHERE t.chunk_id = c.chunk_id AND t.kind = ? AND t.value = ? COLLATE NOCASE)")
            params.extend([_FILTER_KINDS[name], expected])
        params.append(query.max_results)
        connection = sqlite3.connect(f"file:{index_path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(f"""
                SELECT c.*, bm25(chunks_fts) AS rank
                FROM chunks_fts JOIN chunks AS c ON c.rowid = chunks_fts.rowid
                WHERE {' AND '.join(where)}
                ORDER BY rank, c.page_id, c.chunk_id
                LIMIT ?
            """, params).fetchall()
        except sqlite3.Error as error:
            raise PolicyRefusal("POLICY_INDEX_INVALID", f"índice inválido para root_id={query.root_id}") from error
        finally:
            connection.close()
        return tuple(SearchResult(
            root_id=str(row["root_id"]), page_id=str(row["page_id"]), chunk_id=str(row["chunk_id"]),
            title=str(row["title"]), source_url=str(row["source_url"]), content=str(row["content"])[:query.max_chars],
            collected_at=row["collected_at"], version_number=row["version_number"],
        ) for row in rows)
