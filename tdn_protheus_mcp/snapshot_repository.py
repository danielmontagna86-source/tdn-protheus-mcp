"""Read-only access to the public local snapshot format."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from .contracts import PolicyRefusal, SnapshotStatus
from .policy import SnapshotPolicy


class SnapshotRepository:
    def __init__(self, policy: SnapshotPolicy) -> None:
        self._policy = policy

    def _root(self, root_id: str) -> tuple[str, Path]:
        normalized = self._policy.require_root(root_id)
        cache_root = self._policy.require_path(self._policy.cache_root)
        return normalized, self._policy.require_path(cache_root / normalized)

    def _manifest(self, root_id: str) -> tuple[str, Path, dict[str, Any]]:
        normalized, root = self._root(root_id)
        path = self._policy.require_path(root / "manifest.json")
        if not path.is_file():
            raise PolicyRefusal("POLICY_SNAPSHOT_NOT_FOUND", f"manifest inexistente para root_id={normalized}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PolicyRefusal("POLICY_SNAPSHOT_INVALID", f"manifest inválido para root_id={normalized}") from error
        if not isinstance(data, dict) or not isinstance(data.get("pages"), dict):
            raise PolicyRefusal("POLICY_SNAPSHOT_INVALID", f"manifest sem páginas para root_id={normalized}")
        return normalized, root, data

    @staticmethod
    def _page_id(page_id: str | int) -> str:
        try:
            normalized = str(int(str(page_id)))
        except ValueError as error:
            raise PolicyRefusal("POLICY_PAGE_NOT_ALLOWED", "page_id deve ser numérico") from error
        if int(normalized) < 0:
            raise PolicyRefusal("POLICY_PAGE_NOT_ALLOWED", "page_id deve ser positivo")
        return normalized

    def read_active_page(self, root_id: str, page_id: str | int) -> dict[str, Any]:
        normalized_root, root, manifest = self._manifest(root_id)
        normalized_page = self._page_id(page_id)
        summary = manifest["pages"].get(normalized_page)
        if not isinstance(summary, dict) or summary.get("status") != "active":
            raise PolicyRefusal("POLICY_PAGE_NOT_ALLOWED", f"página ativa não encontrada: {normalized_page}")
        path = self._policy.require_path(root / "pages" / f"{normalized_page}.json")
        if not path.is_file():
            raise PolicyRefusal("POLICY_PAGE_NOT_FOUND", f"arquivo ausente para página {normalized_page} em root_id={normalized_root}")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PolicyRefusal("POLICY_PAGE_INVALID", f"arquivo inválido para página {normalized_page}") from error
        if not isinstance(record, dict) or str(record.get("id")) != normalized_page:
            raise PolicyRefusal("POLICY_PAGE_INVALID", f"identificador inválido para página {normalized_page}")
        return record

    def active_pages(self, root_id: str) -> Iterator[dict[str, Any]]:
        _, _, manifest = self._manifest(root_id)
        for page_id, summary in sorted(manifest["pages"].items(), key=lambda item: int(item[0])):
            if isinstance(summary, dict) and summary.get("status") == "active":
                yield self.read_active_page(root_id, page_id)

    def status(self, root_id: str) -> SnapshotStatus:
        normalized, root, manifest = self._manifest(root_id)
        summaries = list(manifest["pages"].values())
        pages_dir = self._policy.require_path(root / "pages")
        cache_bytes = sum(path.stat().st_size for path in pages_dir.glob("*.json")) if pages_dir.is_dir() else 0
        return SnapshotStatus(
            root_id=normalized,
            active_pages=sum(isinstance(item, dict) and item.get("status") == "active" for item in summaries),
            removed_pages=sum(isinstance(item, dict) and item.get("status") == "removed" for item in summaries),
            cache_bytes=cache_bytes,
            last_complete_at=manifest.get("last_complete_at"),
        )
