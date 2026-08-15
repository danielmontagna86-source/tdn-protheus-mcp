"""Policy checks shared by every local transport."""

from __future__ import annotations

from pathlib import Path

from .config import McpConfig
from .contracts import PolicyRefusal, SearchQuery


class SnapshotPolicy:
    def __init__(self, config: McpConfig) -> None:
        self._config = config

    @property
    def cache_root(self) -> Path:
        return self._config.cache_root

    def require_root(self, root_id: str) -> str:
        normalized = str(root_id).strip()
        if normalized not in self._config.allowed_root_ids:
            raise PolicyRefusal("POLICY_ROOT_NOT_ALLOWED", f"root_id não permitido: {normalized}")
        return normalized

    def require_path(self, path: str | Path) -> Path:
        candidate = Path(path).expanduser().resolve()
        cache_root = self._config.cache_root.expanduser().resolve()
        try:
            candidate.relative_to(cache_root)
        except ValueError as error:
            raise PolicyRefusal("POLICY_PATH_OUTSIDE_CACHE", "o caminho deve estar dentro de cache_root") from error
        return candidate

    def search_query(self, query: str, root_id: str, max_results: int, max_chars: int) -> SearchQuery:
        normalized_query = query.strip()
        if not normalized_query:
            raise PolicyRefusal("POLICY_EMPTY_QUERY", "a consulta não pode ser vazia")
        if max_results < 1 or max_results > self._config.max_results:
            raise PolicyRefusal("POLICY_LIMIT_EXCEEDED", f"max_results deve estar entre 1 e {self._config.max_results}")
        if max_chars < 1 or max_chars > self._config.max_chars:
            raise PolicyRefusal("POLICY_LIMIT_EXCEEDED", f"max_chars deve estar entre 1 e {self._config.max_chars}")
        return SearchQuery(
            query=normalized_query,
            root_id=self.require_root(root_id),
            max_results=max_results,
            max_chars=max_chars,
        )
