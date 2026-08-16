"""Strict configuration for the local read-only MCP."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MAX_RESULTS = 20
DEFAULT_MAX_CHARS = 24000
_ALLOWED_FIELDS = {
    "cache_root",
    "allowed_root_ids",
    "max_results",
    "max_chars",
    "offline",
    "allow_mutations",
}


class ConfigError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class McpConfig:
    cache_root: Path
    allowed_root_ids: frozenset[str]
    max_results: int = DEFAULT_MAX_RESULTS
    max_chars: int = DEFAULT_MAX_CHARS


def _required_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(
            "CONFIG_REQUIRED_FIELD",
            f"'{field}' deve ser uma string não vazia",
        )
    return value


def _bounded_int(
    data: dict[str, Any],
    field: str,
    default: int,
    upper_bound: int,
) -> int:
    value = data.get(field, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(
            "CONFIG_INVALID_LIMIT",
            f"'{field}' deve estar entre 1 e {upper_bound}",
        )
    if not 1 <= value <= upper_bound:
        raise ConfigError(
            "CONFIG_INVALID_LIMIT",
            f"'{field}' deve estar entre 1 e {upper_bound}",
        )
    return value


def load_config(path: str | Path) -> McpConfig:
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigError(
            "CONFIG_NOT_FOUND",
            f"arquivo não encontrado: {config_path}",
        )
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ConfigError("CONFIG_INVALID_JSON", "JSON inválido") from error
    if not isinstance(data, dict):
        raise ConfigError(
            "CONFIG_INVALID_FORMAT",
            "a raiz do JSON deve ser um objeto",
        )
    unknown_fields = set(data) - _ALLOWED_FIELDS
    if unknown_fields:
        raise ConfigError(
            "CONFIG_UNKNOWN_FIELD",
            f"campo não permitido: {sorted(unknown_fields)[0]}",
        )
    if (
        data.get("offline", True) is not True
        or data.get("allow_mutations", False) is not False
    ):
        raise ConfigError(
            "CONFIG_READ_ONLY_REQUIRED",
            "o MCP é somente leitura; use offline=true e allow_mutations=false",
        )

    cache_root = Path(_required_string(data, "cache_root")).expanduser().resolve()
    root_ids = data.get("allowed_root_ids")
    if not isinstance(root_ids, list) or not root_ids:
        raise ConfigError(
            "CONFIG_INVALID_ROOTS",
            "'allowed_root_ids' deve ser uma lista não vazia de identificadores",
        )
    for item in root_ids:
        normalized = str(item).strip()
        if (
            not isinstance(item, (str, int))
            or not normalized.isdigit()
            or int(normalized) <= 0
        ):
            raise ConfigError(
                "CONFIG_INVALID_ROOTS",
                "'allowed_root_ids' deve ser uma lista não vazia de identificadores",
            )
    return McpConfig(
        cache_root=cache_root,
        allowed_root_ids=frozenset(
            str(int(str(item).strip()))
            for item in root_ids
        ),
        max_results=_bounded_int(
            data,
            "max_results",
            DEFAULT_MAX_RESULTS,
            DEFAULT_MAX_RESULTS,
        ),
        max_chars=_bounded_int(
            data,
            "max_chars",
            DEFAULT_MAX_CHARS,
            DEFAULT_MAX_CHARS,
        ),
    )
