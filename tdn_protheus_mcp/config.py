"""Strict, local-only configuration loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MAX_RESULTS = 20
DEFAULT_MAX_CHARS = 24000
DEFAULT_TDN_API_BASE = "https://tdn.totvs.com/rest/api"
DEFAULT_REFRESH_TIMEOUT_SECONDS = 900
_ALLOWED_FIELDS = {
    "cache_root",
    "allowed_root_ids",
    "offline",
    "allow_mutations",
    "max_results",
    "max_chars",
    "tdn_api_base",
    "refresh_timeout_seconds",
}


class ConfigError(ValueError):
    """A configuration error with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class McpConfig:
    cache_root: Path
    allowed_root_ids: frozenset[str]
    offline: bool = True
    allow_mutations: bool = False
    max_results: int = DEFAULT_MAX_RESULTS
    max_chars: int = DEFAULT_MAX_CHARS
    tdn_api_base: str = DEFAULT_TDN_API_BASE
    refresh_timeout_seconds: int = DEFAULT_REFRESH_TIMEOUT_SECONDS


def _required_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError("CONFIG_REQUIRED_FIELD", f"'{field}' deve ser uma string não vazia")
    return value


def _bounded_int(data: dict[str, Any], field: str, default: int, upper_bound: int) -> int:
    value = data.get(field, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > upper_bound:
        raise ConfigError("CONFIG_INVALID_LIMIT", f"'{field}' deve estar entre 1 e {upper_bound}")
    return value


def load_config(path: str | Path) -> McpConfig:
    """Load a single explicit JSON configuration file without side effects."""
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigError("CONFIG_NOT_FOUND", f"arquivo não encontrado: {config_path}")
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ConfigError("CONFIG_INVALID_JSON", "JSON inválido") from error
    if not isinstance(data, dict):
        raise ConfigError("CONFIG_INVALID_FORMAT", "a raiz do JSON deve ser um objeto")
    unknown_fields = set(data) - _ALLOWED_FIELDS
    if unknown_fields:
        raise ConfigError("CONFIG_UNKNOWN_FIELD", f"campo não permitido: {sorted(unknown_fields)[0]}")

    cache_root = Path(_required_string(data, "cache_root")).expanduser().resolve()
    root_ids = data.get("allowed_root_ids")
    if not isinstance(root_ids, list) or not root_ids or any(not isinstance(item, (str, int)) or not str(item).strip() for item in root_ids):
        raise ConfigError("CONFIG_INVALID_ROOTS", "'allowed_root_ids' deve ser uma lista não vazia de identificadores")
    offline = data.get("offline", True)
    allow_mutations = data.get("allow_mutations", False)
    if not isinstance(offline, bool) or not isinstance(allow_mutations, bool):
        raise ConfigError("CONFIG_INVALID_FLAG", "'offline' e 'allow_mutations' devem ser booleanos")
    tdn_api_base = data.get("tdn_api_base", DEFAULT_TDN_API_BASE)
    if not isinstance(tdn_api_base, str) or not tdn_api_base.startswith("https://"):
        raise ConfigError("CONFIG_INVALID_ENDPOINT", "'tdn_api_base' deve usar https://")
    return McpConfig(
        cache_root=cache_root,
        allowed_root_ids=frozenset(str(item) for item in root_ids),
        offline=offline,
        allow_mutations=allow_mutations,
        max_results=_bounded_int(data, "max_results", DEFAULT_MAX_RESULTS, DEFAULT_MAX_RESULTS),
        max_chars=_bounded_int(data, "max_chars", DEFAULT_MAX_CHARS, DEFAULT_MAX_CHARS),
        tdn_api_base=tdn_api_base.rstrip("/"),
        refresh_timeout_seconds=_bounded_int(data, "refresh_timeout_seconds", DEFAULT_REFRESH_TIMEOUT_SECONDS, 3600),
    )
