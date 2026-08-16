"""Command line interface for the local read-only TDN Protheus MCP."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import ConfigError, McpConfig, load_config
from .contracts import PolicyRefusal, SearchResult, SnapshotStatus
from .indexer import SnapshotIndexer
from .policy import SnapshotPolicy
from .search import SnapshotSearch
from .snapshot_repository import SnapshotRepository


def doctor_payload(config: McpConfig) -> dict[str, Any]:
    diagnostics: list[dict[str, str]] = []
    policy = SnapshotPolicy(config)
    repository = SnapshotRepository(policy)
    search = SnapshotSearch(policy)
    for root_id in sorted(config.allowed_root_ids):
        try:
            repository.status(root_id)
        except PolicyRefusal as error:
            diagnostics.append({"code": error.code.replace("POLICY_", ""), "severity": "warning" if error.code == "POLICY_SNAPSHOT_NOT_FOUND" else "error", "message": error.message})
            continue
        status = search.index_status(root_id)
        if status != "current":
            diagnostics.append({"code": f"INDEX_{status.upper()}", "severity": "warning" if status in {"missing", "stale"} else "error", "message": f"índice {status} para root_id={root_id}"})
    return {
        "ok": not any(item["severity"] == "error" for item in diagnostics),
        "config": {"cache_root": str(config.cache_root), "allowed_root_ids": sorted(config.allowed_root_ids), "offline": True, "allow_mutations": False, "max_results": config.max_results, "max_chars": config.max_chars},
        "diagnostics": diagnostics,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tdn-protheus-mcp", description="MCP local e somente leitura para snapshot TDN Protheus.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser("doctor", help="valida configuração, snapshot e índice sem rede")
    index = subcommands.add_parser("index", help="reconstrói o índice local FTS5")
    search = subcommands.add_parser("search", help="pesquisa o índice local")
    status = subcommands.add_parser("status", help="mostra o estado do snapshot local")
    for command in (doctor, index, search, status):
        command.add_argument("--config", required=True)
        command.add_argument("--json", action="store_true")
    index.add_argument("--root-id", required=True)
    status.add_argument("--root-id", required=True)
    search.add_argument("--root-id", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--max-results", type=int, default=8)
    search.add_argument("--max-chars", type=int, default=12000)
    search.add_argument("--module")
    search.add_argument("--table")
    search.add_argument("--routine")
    search.add_argument("--parameter")
    serve = subcommands.add_parser("serve", help="inicia o servidor MCP local por stdio")
    serve.add_argument("--config", required=True)
    serve.add_argument("--transport", choices=("stdio",), default="stdio")
    return parser


def _search_result_payload(result: SearchResult) -> dict[str, Any]:
    return {"root_id": result.root_id, "page_id": result.page_id, "chunk_id": result.chunk_id, "title": result.title, "source_url": result.source_url, "content": result.content, "collected_at": result.collected_at, "version_number": result.version_number}


def _status_payload(status: SnapshotStatus) -> dict[str, Any]:
    return {"root_id": status.root_id, "active_pages": status.active_pages, "removed_pages": status.removed_pages, "cache_bytes": status.cache_bytes, "last_complete_at": status.last_complete_at, "offline": True, "allow_mutations": False}


def _emit(payload: dict[str, Any], as_json: bool) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if as_json else json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "serve":
        from .server import run_server
        try:
            run_server(args.config, args.transport)
        except (ConfigError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 2
        return 0
    try:
        config = load_config(Path(args.config))
        if args.command == "doctor":
            payload = doctor_payload(config)
        else:
            policy = SnapshotPolicy(config)
            repository = SnapshotRepository(policy)
            if args.command == "index":
                build = SnapshotIndexer(repository, policy).build(args.root_id)
                payload = {"root_id": build.root_id, "index_path": str(build.index_path), "chunks_indexed": build.chunks_indexed, "snapshot_fingerprint": build.snapshot_fingerprint}
            elif args.command == "status":
                payload = _status_payload(repository.status(args.root_id))
            else:
                query = policy.search_query(args.query, args.root_id, args.max_results, args.max_chars)
                results = SnapshotSearch(policy).search(query, module=args.module, table=args.table, routine=args.routine, parameter=args.parameter)
                payload = {"root_id": query.root_id, "results": [_search_result_payload(result) for result in results]}
    except (ConfigError, PolicyRefusal, ValueError) as error:
        code = getattr(error, "code", "POLICY_ERROR")
        if args.json:
            print(json.dumps({"ok": False, "error": {"code": code, "message": str(error)}}, ensure_ascii=False))
        else:
            print(str(error), file=sys.stderr)
        return 2
    _emit(payload, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
