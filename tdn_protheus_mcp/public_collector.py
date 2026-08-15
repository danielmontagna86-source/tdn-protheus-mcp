"""Public, package-owned snapshot page collector primitives."""

from __future__ import annotations

from collections import deque
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from queue import Empty, Queue
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlsplit

from .contracts import PolicyRefusal, UpstreamError
from .mutations import RefreshPlan


TDN_WEB = "https://tdn.totvs.com"
GENERATIONS_TO_RETAIN = 2


class _ManifestLock(AbstractContextManager["_ManifestLock"]):
    """Small cross-process lock for the short manifest replacement critical section."""

    def __init__(self, path: Path, *, timeout_seconds: float = 30, stale_seconds: float = 120) -> None:
        self._path = path
        self._timeout_seconds = timeout_seconds
        self._stale_seconds = stale_seconds
        self._descriptor: int | None = None

    def __enter__(self) -> "_ManifestLock":
        deadline = time.monotonic() + self._timeout_seconds
        while True:
            try:
                self._descriptor = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self._descriptor, str(os.getpid()).encode("ascii"))
                return self
            except FileExistsError:
                try:
                    stale = time.time() - self._path.stat().st_mtime >= self._stale_seconds
                except FileNotFoundError:
                    continue
                if stale:
                    try:
                        self._path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise PolicyRefusal("POLICY_REFRESH_BUSY", "outra atualização está publicando este snapshot")
                time.sleep(0.05)

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        if self._descriptor is not None:
            os.close(self._descriptor)
            self._descriptor = None
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass


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

    @property
    def manifest_temp_path(self) -> Path:
        return self._root / f".manifest-{self._staging.name}.tmp"

    @staticmethod
    def _prune_generations(generations: Path, current: Path) -> None:
        candidates = [path for path in generations.iterdir() if path.is_dir()]
        previous = sorted(
            (path for path in candidates if path != current), key=lambda path: path.stat().st_mtime, reverse=True
        )[: GENERATIONS_TO_RETAIN - 1]
        retained = {current, *previous}
        for generation in candidates:
            if generation in retained:
                continue
            try:
                shutil.rmtree(generation)
            except OSError:
                # A concurrent reader may still have a generation open (notably on Windows).
                # Retaining it is safe; the next successful refresh will try again.
                pass

    def commit(self, manifest: dict[str, Any]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        generations = self._root / "generations"
        generations.mkdir(exist_ok=True)
        current_generation = generations / self._staging.name
        os.replace(self._staging, current_generation)
        published_manifest = {**manifest, "page_directory": self.page_directory}
        with _ManifestLock(self._root / ".manifest.lock"):
            temporary = self.manifest_temp_path
            temporary.write_text(json.dumps(published_manifest, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, self._root / "manifest.json")
            self._prune_generations(generations, current_generation)

    def abort(self) -> None:
        if self._staging.exists():
            shutil.rmtree(self._staging)


class TdnHttpFetcher:
    """Small injectable HTTP boundary; requests is needed only for live refreshes."""

    def __init__(self, api_base: str, *, timeout_seconds: float = 20, get: Callable[..., Any] | None = None) -> None:
        self._api_base = api_base.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._request_slot = threading.BoundedSemaphore(value=1)
        parsed_base = urlsplit(self._api_base)
        self._api_origin = (parsed_base.scheme.lower(), parsed_base.netloc.lower())
        self._api_path = parsed_base.path.rstrip("/")
        if get is None:
            try:
                import requests
            except ImportError as error:
                raise RuntimeError("instale tdn-protheus-mcp[snapshot] para atualização HTTP") from error

            def get(url: str, *, timeout: float) -> Any:
                return requests.get(url, timeout=timeout, allow_redirects=False)
        self._get = get

    def _request_json(
        self, url: str, *, remaining_timeout: Callable[[], float | None] | None = None
    ) -> dict[str, Any]:
        timeout = self._request_budget(remaining_timeout)
        outcome: Queue[tuple[dict[str, Any] | None, Exception | None]] = Queue(maxsize=1)
        if not self._request_slot.acquire(timeout=timeout):
            raise PolicyRefusal("POLICY_REFRESH_TIMEOUT", "o prazo de atualização expirou durante a coleta")
        try:
            timeout = self._request_budget(remaining_timeout)
        except Exception:
            self._request_slot.release()
            raise

        def request() -> None:
            try:
                response = self._get(url, timeout=timeout)
                response.raise_for_status()
                data = response.json()
            except Exception as error:
                outcome.put((None, error))
            else:
                outcome.put((data, None))
            finally:
                self._request_slot.release()

        try:
            threading.Thread(target=request, daemon=True).start()
        except Exception:
            self._request_slot.release()
            raise
        try:
            data, error = outcome.get(timeout=timeout)
        except Empty as error:
            raise PolicyRefusal("POLICY_REFRESH_TIMEOUT", "o prazo de atualização expirou durante a coleta") from error
        if error is not None:
            raise UpstreamError(
                "UPSTREAM_TDN_REQUEST_FAILED", "não foi possível consultar o endpoint TDN configurado"
            ) from error
        if not isinstance(data, dict):
            raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", "o endpoint TDN retornou uma resposta inválida")
        return data

    def _request_budget(self, remaining_timeout: Callable[[], float | None] | None) -> float:
        timeout = self._timeout_seconds
        if remaining_timeout is not None:
            remaining = remaining_timeout()
            if remaining is not None:
                if remaining <= 0:
                    raise PolicyRefusal("POLICY_REFRESH_TIMEOUT", "o prazo de atualização expirou durante a coleta")
                timeout = min(timeout, remaining)
        return timeout

    def __call__(
        self, page_id: str, *, remaining_timeout: Callable[[], float | None] | None = None
    ) -> dict[str, Any] | None:
        return self._request_json(
            f"{self._api_base}/content/{page_id}?expand=version,body.storage",
            remaining_timeout=remaining_timeout,
        )

    def fetch_children(
        self,
        page_id: str,
        *,
        limit: int = 50,
        start: int = 0,
        remaining_timeout: Callable[[], float | None] | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            f"{self._api_base}/content/{page_id}/child/page?limit={limit}&start={start}",
            remaining_timeout=remaining_timeout,
        )

    def list_children(
        self,
        page_id: str,
        *,
        limit: int = 50,
        remaining_timeout: Callable[[], float | None] | None = None,
    ) -> list[dict[str, Any]]:
        """Return every child page advertised by the public TDN pagination links."""
        url = f"{self._api_base}/content/{page_id}/child/page?limit={limit}&start=0"
        expected_path = f"{self._api_path}/content/{page_id}/child/page"
        children: list[dict[str, Any]] = []
        while True:
            response = self._request_json(url, remaining_timeout=remaining_timeout)
            results = response.get("results", [])
            if not isinstance(results, list):
                raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", "o endpoint TDN retornou uma lista de filhos inválida")
            children.extend(item for item in results if isinstance(item, dict))
            links = response.get("_links", {})
            if not isinstance(links, dict):
                raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", "o endpoint TDN retornou links inválidos")
            next_link = links.get("next")
            if next_link is None or next_link == "":
                return children
            if not isinstance(next_link, str):
                raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", "o endpoint TDN retornou paginação inválida")
            url = urljoin(url, next_link)
            parsed_next = urlsplit(url)
            if (parsed_next.scheme.lower(), parsed_next.netloc.lower()) != self._api_origin or parsed_next.path != expected_path:
                raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", "o endpoint TDN retornou paginação fora da origem configurada")


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
        fetch_json: Callable[..., dict[str, Any] | None],
        *,
        fetch_children: Callable[..., dict[str, Any] | list[dict[str, Any]] | None] | None = None,
    ) -> None:
        self._fetch_json = fetch_json
        self._fetch_children = fetch_children

    @staticmethod
    def _fetch_with_remaining_timeout(
        fetch: Callable[..., Any], page_id: str, remaining_timeout: Callable[[], float | None] | None
    ) -> Any:
        if remaining_timeout is None:
            return fetch(page_id)
        return fetch(page_id, remaining_timeout=remaining_timeout)

    def discover_tree(
        self,
        root_id: str | int,
        *,
        max_depth: int,
        max_pages: int,
        cancelled: Callable[[], bool] | None = None,
        remaining_timeout: Callable[[], float | None] | None = None,
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
            response = self._fetch_with_remaining_timeout(self._fetch_children, page_id, remaining_timeout)
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

    def fetch_page(
        self, page_id: str | int, *, remaining_timeout: Callable[[], float | None] | None = None
    ) -> dict[str, Any]:
        normalized = str(int(page_id))
        data = self._fetch_with_remaining_timeout(self._fetch_json, normalized, remaining_timeout)
        if not isinstance(data, dict):
            raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", f"página inválida: {normalized}")
        body = data.get("body", {})
        if not isinstance(body, dict):
            raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", f"corpo inválido para página {normalized}")
        storage = body.get("storage", {})
        if not isinstance(storage, dict):
            raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", f"armazenamento inválido para página {normalized}")
        value = storage.get("value", "")
        if not isinstance(value, str):
            raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", f"conteúdo inválido para página {normalized}")
        html = value
        version = data.get("version", {})
        if not isinstance(version, dict):
            raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", f"versão inválida para página {normalized}")
        links = data.get("_links", {})
        if not isinstance(links, dict):
            raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", f"links inválidos para página {normalized}")
        webui = links.get("webui", f"/pages/viewpage.action?pageId={normalized}")
        if not isinstance(webui, str):
            raise UpstreamError("UPSTREAM_TDN_INVALID_RESPONSE", f"link inválido para página {normalized}")
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
        self,
        plan: RefreshPlan,
        *,
        cancelled: Callable[[], bool] | None = None,
        remaining_timeout: Callable[[], float | None] | None = None,
    ) -> dict[str, int]:
        writer = AtomicSnapshotWriter(self._cache_root / plan.root_id)
        try:
            page_ids = self._collector.discover_tree(
                plan.root_id,
                max_depth=plan.max_depth,
                max_pages=plan.estimated_pages,
                cancelled=cancelled,
                remaining_timeout=remaining_timeout,
            )
            pages: dict[str, dict[str, Any]] = {}
            for page_id in page_ids:
                if cancelled and cancelled():
                    raise PolicyRefusal("POLICY_REFRESH_CANCELLED", "atualização cancelada durante coleta")
                record = self._collector.fetch_page(page_id, remaining_timeout=remaining_timeout)
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
