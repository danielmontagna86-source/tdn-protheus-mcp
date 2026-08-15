"""Explicit, bounded maintenance operations for a local TDN snapshot."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Callable, Protocol

from .config import McpConfig
from .contracts import PolicyRefusal
from .audit import AuditLog
from .policy import SnapshotPolicy
from .snapshot_repository import SnapshotRepository


MAX_REFRESH_DEPTH = 12
MAX_REFRESH_PAGES = 5_000
ESTIMATED_BYTES_PER_PAGE = 50_000
MINIMUM_SECONDS_PER_PAGE = 0.35
_EXPORT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.jsonl\Z")


@dataclass(frozen=True)
class RefreshPlan:
    root_id: str
    max_depth: int
    estimated_pages: int
    estimated_disk_bytes: int
    minimum_duration_seconds: float


class SnapshotRefreshRunner(Protocol):
    """Explicit refresh boundary so collector failures are never reinterpreted."""

    def __call__(
        self, plan: RefreshPlan, *, cancelled: Callable[[], bool] | None = None
    ) -> dict[str, int]: ...


class RefreshOperations:
    """Plans maintenance locally; applying it is intentionally a separate operation."""

    def __init__(self, config: McpConfig, refresh_runner: SnapshotRefreshRunner | None = None) -> None:
        self._config = config
        self._policy = SnapshotPolicy(config)
        self._refresh_runner = refresh_runner

    def plan_snapshot_refresh(self, root_id: str, *, max_depth: int, max_pages: int) -> RefreshPlan:
        if max_depth < 0 or max_depth > MAX_REFRESH_DEPTH:
            raise ValueError(f"max_depth deve estar entre 0 e {MAX_REFRESH_DEPTH}")
        if max_pages < 1 or max_pages > MAX_REFRESH_PAGES:
            raise ValueError(f"max_pages deve estar entre 1 e {MAX_REFRESH_PAGES}")
        normalized_root = self._policy.require_root(root_id)
        return RefreshPlan(
            root_id=normalized_root,
            max_depth=max_depth,
            estimated_pages=max_pages,
            estimated_disk_bytes=max_pages * ESTIMATED_BYTES_PER_PAGE,
            minimum_duration_seconds=round(max_pages * MINIMUM_SECONDS_PER_PAGE, 2),
        )

    def apply_snapshot_refresh(
        self, root_id: str, *, max_depth: int, max_pages: int, confirmation: str, cancelled: Callable[[], bool] | None = None
    ) -> dict[str, int]:
        """Run a separately supplied collector only after policy authorization."""
        plan = self.plan_snapshot_refresh(root_id, max_depth=max_depth, max_pages=max_pages)
        if self._config.offline:
            raise PolicyRefusal("POLICY_OFFLINE", "atualização requer offline=false")
        if not self._config.allow_mutations:
            raise PolicyRefusal("POLICY_MUTATIONS_DISABLED", "atualização requer allow_mutations=true")
        if confirmation != "APPLY":
            raise PolicyRefusal("POLICY_CONFIRMATION_REQUIRED", "confirme a atualização com APPLY")
        if self._refresh_runner is None:
            raise PolicyRefusal("POLICY_REFRESH_RUNNER_UNAVAILABLE", "nenhum adaptador de atualização foi configurado")
        started = time.perf_counter()
        try:
            if cancelled and cancelled():
                raise PolicyRefusal("POLICY_REFRESH_CANCELLED", "atualização cancelada antes de iniciar")
            result = self._refresh_runner(plan, cancelled=cancelled)
        except Exception:
            AuditLog(self._config).record(
                "apply_snapshot_refresh", root_id=plan.root_id,
                limits={"max_depth": plan.max_depth, "max_pages": plan.estimated_pages},
                duration_seconds=time.perf_counter() - started, outcome="failed",
            )
            raise
        AuditLog(self._config).record(
            "apply_snapshot_refresh", root_id=plan.root_id,
            limits={"max_depth": plan.max_depth, "max_pages": plan.estimated_pages},
            duration_seconds=time.perf_counter() - started, outcome="success",
        )
        return result

    def export_hermes_context(self, root_id: str, filename: str) -> Path:
        """Export active local pages to a bounded cache-owned JSONL file."""
        if not self._config.allow_mutations:
            raise PolicyRefusal("POLICY_MUTATIONS_DISABLED", "exportação requer allow_mutations=true")
        if not _EXPORT_NAME.fullmatch(filename):
            raise PolicyRefusal("POLICY_EXPORT_NAME", "o nome deve ser um arquivo .jsonl simples")
        normalized_root = self._policy.require_root(root_id)
        exports = self._policy.require_path(self._config.cache_root / "exports")
        exports.mkdir(parents=True, exist_ok=True)
        target = self._policy.require_path(exports / filename)
        started = time.perf_counter()
        repository = SnapshotRepository(self._policy)
        records = (
            {
                "root_id": normalized_root,
                "page_id": str(page["id"]),
                "title": str(page.get("title", "")),
                "source_url": str(page.get("url", "")),
                "content": str(page.get("text", "")),
                "content_classification": "external_reference",
            }
            for page in repository.active_pages(normalized_root)
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=exports, suffix=".tmp") as file:
            temporary = Path(file.name)
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        try:
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        AuditLog(self._config).record(
            "export_hermes_context",
            root_id=normalized_root,
            limits={"filename_length": len(filename)},
            duration_seconds=time.perf_counter() - started,
            outcome="success",
        )
        return target
