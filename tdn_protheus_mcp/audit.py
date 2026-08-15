"""Privacy-preserving local audit events for explicit maintenance operations."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .config import McpConfig


class AuditLog:
    def __init__(self, config: McpConfig) -> None:
        self._config = config

    def _config_sha256(self) -> str:
        public = {
            "allowed_root_ids": sorted(self._config.allowed_root_ids),
            "offline": self._config.offline,
            "allow_mutations": self._config.allow_mutations,
            "max_results": self._config.max_results,
            "max_chars": self._config.max_chars,
        }
        encoded = json.dumps(public, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def record(
        self, operation: str, *, root_id: str, limits: dict[str, int], duration_seconds: float, outcome: str
    ) -> Path:
        event = {
            "at": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "root_id": root_id,
            "limits": dict(sorted(limits.items())),
            "duration_seconds": round(duration_seconds, 3),
            "outcome": outcome,
            "config_sha256": self._config_sha256(),
        }
        audit_path = Path(self._config.cache_root) / "audit.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        return audit_path
