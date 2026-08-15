"""Public, package-owned snapshot page collector primitives."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin

from .contracts import PolicyRefusal
from .mutations import RefreshPlan


TDN_WEB = "https://tdn.totvs.com"


class AtomicSnapshotWriter:
    """Stages pages beside a snapshot and publishes the manifest only at commit."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.parent.mkdir(parents=True, exist_ok=True)
        self._staging = Path(tempfile.mkdtemp(prefix="tdn-refresh-", dir=self._root.parent))
        (self._staging / "pages").mkdir(parents=True)

    def write_page(self, record: dict[str, Any]) -> None:
        target = self._staging / "pages" / f"{int(record['id'])}.json"
        target.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    @property
    def page_directory(self) -> str:
        return f"generations/{self._staging.name}/pages"

    def commit(self, manifest: dict[str, Any]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        generations = self._root / "generations"
        generations.mkdir(exist_ok=True)
        os.replace(self._staging, generations / self._staging.name)
        published_manifest = {**manifest, "page_directory": self.page_directory}
        temporary = self._root / "manifest.json.tmp"
        temporary.write_text(json.dumps(published_manifest, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, self._root / "manifest.json")

    def abort(self) -> None:
        if self._staging.exists():
            shutil.rmtree(self._staging)


class TdnHttpFetcher:
    """Small injectable HTTP boundary; requests is needed only for live refreshes."""

    def __init__(self, api_base: str, *, timeout_seconds: float = 20, get: Callable[..., Any] | None = None) -> None:
        self._api_base = api_base.rstrip("/")
        self._timeout_seconds = timeout_seconds
        if get is None:
            try:
                import requests
            except ImportError as error:
                raise RuntimeError("instale tdn-protheus-mcp[snapshot] para atualização HTTP") from error
            get = requests.get
        self._get = get

    def _request_json(self, url: str) -> dict[str, Any]:
        response = self._get(url, timeout=self._timeout_seconds)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("resposta TDN inválida")
        return data

    def __call__(self, page_id: str) -> dict[str, Any] | None:
        return self._request_json(f"{self._api_base}/content/{page_id}?expand=version,body.storage")

    def fetch_children(self, page_id: str, *, limit: int = 50, start: int = 0) -> dict[str, Any]:
        return self._request_json(
            f"{self._api_base}/content/{page_id}/child/page?limit={limit}&start={start}"
        )

    def list_children(self, page_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return every child page advertised by the public TDN pagination links."""
        url = f"{self._api_base}/content/{page_id}/child/page?limit={limit}&start=0"
        children: list[dict[str, Any]] = []
        while True:
            response = self._request_json(url)
            results = response.get("results", [])
            if not isinstance(results, list):
                raise RuntimeError(f"lista de filhos inválida para página {page_id}")
            children.extend(item for item in results if isinstance(item, dict))
            links = response.get("_links", {})
            next_link = links.get("next") if isinstance(links, dict) else None
            if not isinstance(next_link, str) or not next_link:
                return children
            url = urljoin(f"{self._api_base}/", next_link)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


def html_to_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    return "\n".join(parser.parts)


class PublicSnapshotCollector:
    """Converts a fetch function response into the portable snapshot record format."""

    def __init__(
        self,
        fetch_json: Callable[[str], dict[str, Any] | None],
        *,
        fetch_children: Callable[[str], dict[str, Any] | list[dict[str, Any]] | None] | None = None,
    ) -> None:
        self._fetch_json = fetch_json
        self._fetch_children = fetch_children

    def discover_tree(
        self,
        root_id: str | int,
        *,
        max_depth: int,
        max_pages: int,
        cancelled: Callable[[], bool] | None = None,
    ) -> list[str]:
        if self._fetch_children is None:
            raise RuntimeError("descoberta de árvore não foi configurada")
        queue = deque([(str(int(root_id)), 0)])
        seen: set[str] = set()
        discovered: list[str] = []
        while queue:
            if cancelled and cancelled():
                raise PolicyRefusal("POLICY_REFRESH_CANCELLED", "atualização cancelada durante descoberta")
            page_id, depth = queue.popleft()
            if page_id in seen or depth > max_depth:
                continue
            if len(discovered) >= max_pages:
                raise RuntimeError(f"limite de {max_pages} páginas atingido durante descoberta")
            seen.add(page_id)
            discovered.append(page_id)
            if depth == max_depth:
                continue
            response = self._fetch_children(page_id)
            if isinstance(response, dict):
                children = response.get("results", [])
            elif isinstance(response, list):
                children = response
            else:
                raise RuntimeError(f"resposta de filhos inválida para página {page_id}")
            if not isinstance(children, list):
                raise RuntimeError(f"lista de filhos inválida para página {page_id}")
            for child in children:
                if isinstance(child, dict) and str(child.get("id", "")).isdigit():
                    queue.append((str(int(str(child["id"]))), depth + 1))
        return discovered

    def fetch_page(self, page_id: str | int) -> dict[str, Any]:
        normalized = str(int(page_id))
        data = self._fetch_json(normalized)
        if not isinstance(data, dict):
            raise RuntimeError(f"página indisponível: {normalized}")
        html = str(data.get("body", {}).get("storage", {}).get("value", ""))
        version = data.get("version", {})
        webui = str(data.get("_links", {}).get("webui", f"/pages/viewpage.action?pageId={normalized}"))
        return {
            "id": int(normalized),
            "title": str(data.get("title", f"page-{normalized}")),
            "url": f"{TDN_WEB}{webui}",
            "text": html_to_text(html),
            "body_len": len(html),
            "version_number": version.get("number"),
            "version_when": version.get("when"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


class PublicSnapshotRefresher:
    """Builds a bounded snapshot in staging and publishes it only when complete."""

    def __init__(self, collector: PublicSnapshotCollector, cache_root: Path) -> None:
        self._collector = collector
        self._cache_root = Path(cache_root)

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _summary(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": record["id"],
            "title": record["title"],
            "url": record["url"],
            "body_len": record["body_len"],
            "version_number": record["version_number"],
            "version_when": record["version_when"],
            "status": "active",
        }

    def __call__(
        self, plan: RefreshPlan, *, cancelled: Callable[[], bool] | None = None
    ) -> dict[str, int]:
        writer = AtomicSnapshotWriter(self._cache_root / plan.root_id)
        try:
            page_ids = self._collector.discover_tree(
                plan.root_id, max_depth=plan.max_depth, max_pages=plan.estimated_pages, cancelled=cancelled
            )
            pages: dict[str, dict[str, Any]] = {}
            for page_id in page_ids:
                if cancelled and cancelled():
                    raise PolicyRefusal("POLICY_REFRESH_CANCELLED", "atualização cancelada durante coleta")
                record = self._collector.fetch_page(page_id)
                writer.write_page(record)
                pages[page_id] = self._summary(record)
            completed_at = self._timestamp()
            writer.commit(
                {
                    "schema_version": 1,
                    "root_id": int(plan.root_id),
                    "max_depth": plan.max_depth,
                    "created_at": completed_at,
                    "updated_at": completed_at,
                    "last_complete_at": completed_at,
                    "pages": pages,
                }
            )
            index_path = self._cache_root / plan.root_id / "index.sqlite3"
            if index_path.is_file():
                index_path.unlink()
            return {"root_id": int(plan.root_id), "pages_saved": len(pages)}
        except Exception:
            writer.abort()
            raise
