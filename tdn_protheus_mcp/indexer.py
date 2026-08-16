"""Deterministic SQLite FTS5 index derived from the local snapshot."""
from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .policy import SnapshotPolicy
from .snapshot_repository import SnapshotRepository

SCHEMA_VERSION = 2
CHUNK_SIZE = 1800
CHUNK_OVERLAP = 200
_PARAMETER = re.compile(r"\bMV_[A-Z0-9_]{3,}\b", re.I)
_TABLE = re.compile(r"\b(?:S[A-Z0-9]{2}|F0[A-Z0-9]|CN[A-Z0-9]|CT[A-Z0-9]|SN[1-5])\b", re.I)
_ROUTINE = re.compile(r"\b(?=[A-Z0-9]{6,20}\b)(?=[A-Z0-9]*\d)[A-Z][A-Z0-9]+\b", re.I)
_EXPLICIT_ENTRY = re.compile(r"\b(?:ADV[0-9]+_PE_[A-Z0-9_]+|[A-Z0-9]{3,}_PE(?:_[A-Z0-9_]+)?)\b", re.I)
_PROGRAM_PREFIXES = ("MATA", "FINA", "CTBA", "FISA", "ATFA", "CNTA", "SPED")
_MODULE_PATTERNS = {
    "ADVPL": r"\b(ADVPL|TLPP|MSEXECAUTO|EXEC_AUTO|USER\s*FUNCTION)\b",
    "SIGACOM": r"\b(SIGACOM|COMPRAS|MATA103|MATA110|MATA120|SC1|SC7|SF1|SD1)\b",
    "SIGAFAT": r"\b(SIGAFAT|FATURAMENTO|MATA410|MATA460|MATA461|SC5|SC6|SF2|SD2)\b",
    "SIGAEST": r"\b(SIGAEST|ESTOQUE|MATA240|MATA330|SB1|SB2|SD3)\b",
    "SIGAFIN": r"\b(SIGAFIN|FINANCEIRO|FINA040|FINA050|SE1|SE2|SE5)\b",
    "SIGACTB": r"\b(SIGACTB|CONTABILIDADE|CTBA102|CTBA105|CT1|CT2)\b",
    "SIGAFIS": r"\b(SIGAFIS|FISCAL|FISA170|SPED|SF3|SFT|SF4)\b",
    "SIGAATF": r"\b(SIGAATF|ATIVO\s*FIXO|ATFA012|ATFA050|SN1|SN3)\b",
    "SIGAGCT": r"\b(SIGAGCT|CONTRATOS|CNTA300|CNTA120|CN9|CNC|CND)\b",
}


@dataclass(frozen=True)
class IndexBuild:
    root_id: str
    index_path: Path
    chunks_indexed: int
    snapshot_fingerprint: str


def _chunks(text: str) -> Iterator[str]:
    text = text.strip()
    if not text:
        return
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        if end < len(text):
            boundary = max(text.rfind("\n\n", start + CHUNK_SIZE // 2, end), text.rfind("\n", start + CHUNK_SIZE // 2, end))
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            yield chunk
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)


def _existing(record: dict[str, Any], field: str) -> set[str]:
    value = record.get(field, [])
    return {str(item).upper() for item in value} if isinstance(value, list) else set()


def _metadata(record: dict[str, Any]) -> dict[str, list[str]]:
    title = str(record.get("title", ""))
    text = str(record.get("text", ""))
    source = f"{title}\n{text}"
    upper = source.upper()
    routines = _existing(record, "routines") | {item.upper() for item in _ROUTINE.findall(source)}
    tables = _existing(record, "tables") | {item.upper() for item in _TABLE.findall(source)}
    parameters = _existing(record, "parameters") | {item.upper() for item in _PARAMETER.findall(source)}
    entry_points = _existing(record, "entry_points") | {item.upper() for item in _EXPLICIT_ENTRY.findall(source)}
    if "PONTO DE ENTRADA" in title.upper():
        entry_points |= {item for item in {token.upper() for token in _ROUTINE.findall(title)} if not item.startswith(_PROGRAM_PREFIXES)}
    modules = _existing(record, "modules") | {name for name, pattern in _MODULE_PATTERNS.items() if re.search(pattern, source, re.I)}
    return {
        "modules": sorted(modules), "tables": sorted(tables), "parameters": sorted(parameters),
        "routines": sorted(routines), "entry_points": sorted(entry_points),
    }


class SnapshotIndexer:
    def __init__(self, repository: SnapshotRepository, policy: SnapshotPolicy) -> None:
        self._repository = repository
        self._policy = policy

    def _index_path(self, root_id: str) -> Path:
        normalized = self._policy.require_root(root_id)
        return self._policy.require_path(self._policy.cache_root / normalized / "index.sqlite3")

    @staticmethod
    def _create_schema(connection: sqlite3.Connection, snapshot_fingerprint: str) -> None:
        connection.executescript("""
            CREATE TABLE schema_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE chunks (
                chunk_id TEXT PRIMARY KEY, root_id TEXT NOT NULL, page_id TEXT NOT NULL,
                title TEXT NOT NULL, source_url TEXT NOT NULL, version_number INTEGER,
                collected_at TEXT, modules_json TEXT NOT NULL, tables_json TEXT NOT NULL,
                parameters_json TEXT NOT NULL, routines_json TEXT NOT NULL,
                entry_points_json TEXT NOT NULL, target_audience TEXT, content TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE chunks_fts USING fts5(title, content);
            CREATE TABLE chunk_tags (
                chunk_id TEXT NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL COLLATE NOCASE,
                PRIMARY KEY (chunk_id, kind, value)
            );
            CREATE INDEX idx_chunk_tags_kind_value ON chunk_tags(kind, value, chunk_id);
        """)
        connection.executemany("INSERT INTO schema_metadata(key, value) VALUES (?, ?)", [
            ("schema_version", str(SCHEMA_VERSION)), ("snapshot_fingerprint", snapshot_fingerprint)
        ])

    def build(self, root_id: str) -> IndexBuild:
        normalized = self._policy.require_root(root_id)
        fingerprint = self._repository.snapshot_fingerprint(normalized)
        index_path = self._index_path(normalized)
        temporary_path = index_path.with_suffix(".sqlite3.tmp")
        if temporary_path.exists():
            temporary_path.unlink()
        chunk_count = 0
        try:
            connection = sqlite3.connect(temporary_path)
            try:
                self._create_schema(connection, fingerprint)
                for record in self._repository.active_pages(normalized):
                    metadata = _metadata(record)
                    page_id = str(record["id"])
                    for chunk_index, content in enumerate(_chunks(str(record.get("text", "")))):
                        chunk_id = f"{page_id}:{chunk_index}"
                        connection.execute("""
                            INSERT INTO chunks(chunk_id, root_id, page_id, title, source_url, version_number,
                                collected_at, modules_json, tables_json, parameters_json, routines_json,
                                entry_points_json, target_audience, content)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            chunk_id, normalized, page_id, str(record.get("title", f"page-{page_id}")),
                            str(record.get("url", "")), record.get("version_number"), record.get("fetched_at"),
                            json.dumps(metadata["modules"], ensure_ascii=False), json.dumps(metadata["tables"], ensure_ascii=False),
                            json.dumps(metadata["parameters"], ensure_ascii=False), json.dumps(metadata["routines"], ensure_ascii=False),
                            json.dumps(metadata["entry_points"], ensure_ascii=False), record.get("target_audience"), content,
                        ))
                        rowid = connection.execute("SELECT rowid FROM chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()[0]
                        connection.execute("INSERT INTO chunks_fts(rowid, title, content) VALUES (?, ?, ?)", (rowid, str(record.get("title", "")), content))
                        for kind in ("modules", "tables", "parameters", "routines", "entry_points"):
                            connection.executemany("INSERT OR IGNORE INTO chunk_tags(chunk_id, kind, value) VALUES (?, ?, ?)", [(chunk_id, kind[:-1] if kind.endswith("s") else kind, value) for value in metadata[kind]])
                        chunk_count += 1
                connection.commit()
            finally:
                connection.close()
            os.replace(temporary_path, index_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        return IndexBuild(normalized, index_path, chunk_count, fingerprint)
