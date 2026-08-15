"""Command line interface for the local TDN Protheus MCP."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import ConfigError, McpConfig, load_config
from .contracts import PolicyRefusal, SearchResult, SnapshotStatus
from .indexer import SnapshotIndexer
from .mutations import RefreshOperations
from .policy import SnapshotPolicy
from .public_collector import PublicSnapshotCollector, PublicSnapshotRefresher, TdnHttpFetcher
from .refresh_adapter import SnapshotRefreshAdapter
from .search import SnapshotSearch
from .snapshot_repository import SnapshotRepository


def doctor_payload(config: McpConfig) -> dict[str, Any]:
    diagnostics: list[dict[str, str]] = []
    for root_id in sorted(config.allowed_root_ids):
        manifest = config.cache_root / root_id / "manifest.json"
        if not manifest.is_file():
            diagnostics.append(
                {
                    "code": "SNAPSHOT_NOT_FOUND",
                    "severity": "warning",
                    "message": f"snapshot ausente para root_id={root_id}; importe ou atualize explicitamente um snapshot local",
                }
            )
    return {
        "ok": True,
        "config": {
            "cache_root": str(config.cache_root),
            "allowed_root_ids": sorted(config.allowed_root_ids),
            "offline": config.offline,
            "allow_mutations": config.allow_mutations,
            "max_results": config.max_results,
            "max_chars": config.max_chars,
            "tdn_api_base": config.tdn_api_base,
            "refresh_timeout_seconds": config.refresh_timeout_seconds,
        },
        "diagnostics": diagnostics,
    }


def _refresh_operations(config: McpConfig) -> RefreshOperations:
    fetcher = TdnHttpFetcher(config.tdn_api_base, timeout_seconds=config.refresh_timeout_seconds)
    collector = PublicSnapshotCollector(fetcher, fetch_children=fetcher.list_children)
    runner = SnapshotRefreshAdapter(
        PublicSnapshotRefresher(collector, config.cache_root),
        default_timeout_seconds=config.refresh_timeout_seconds,
    )
    return RefreshOperations(config, refresh_runner=runner)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tdn-protheus-mcp", description="MCP local para snapshot TDN Protheus.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    doctor = subcommands.add_parser("doctor", help="valida a configuração local sem rede")
    index = subcommands.add_parser("index", help="reconstrói o índice local FTS5")
    search = subcommands.add_parser("search", help="pesquisa o índice local")
    status = subcommands.add_parser("status", help="mostra o estado do snapshot local")
    plan_refresh = subcommands.add_parser("plan-refresh", help="planeja uma atualização sem rede ou escrita")
    apply_refresh = subcommands.add_parser("apply-refresh", help="executa atualização somente com autorização explícita")
    export_hermes = subcommands.add_parser("export-hermes", help="exporta contexto local seguro para qualquer harness")
    for command in (doctor, index, search, status, plan_refresh, apply_refresh, export_hermes):
        command.add_argument("--config", required=True, help="caminho para o arquivo JSON de configuração")
        command.add_argument("--json", action="store_true", help="emite resultado estruturado em stdout")
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
    plan_refresh.add_argument("--root-id", required=True)
    plan_refresh.add_argument("--max-depth", type=int, default=8)
    plan_refresh.add_argument("--max-pages", type=int, default=1_000)
    apply_refresh.add_argument("--root-id", required=True)
    apply_refresh.add_argument("--max-depth", type=int, default=8)
    apply_refresh.add_argument("--max-pages", type=int, default=1_000)
    apply_refresh.add_argument("--confirm", required=True)
    export_hermes.add_argument("--root-id", required=True)
    export_hermes.add_argument("--filename", required=True)
    serve = subcommands.add_parser("serve", help="inicia o servidor MCP local por stdio")
    serve.add_argument("--config", required=True, help="caminho para o arquivo JSON de configuração")
    serve.add_argument("--transport", choices=("stdio",), default="stdio")
    return parser


def _search_result_payload(result: SearchResult) -> dict[str, Any]:
    return {
        "root_id": result.root_id,
        "page_id": result.page_id,
        "chunk_id": result.chunk_id,
        "title": result.title,
        "source_url": result.source_url,
        "content": result.content,
        "collected_at": result.collected_at,
        "version_number": result.version_number,
    }


def _status_payload(status: SnapshotStatus) -> dict[str, Any]:
    return {
        "root_id": status.root_id,
        "active_pages": status.active_pages,
        "removed_pages": status.removed_pages,
        "cache_bytes": status.cache_bytes,
        "last_complete_at": status.last_complete_at,
    }


def _emit(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


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
        elif args.command == "plan-refresh":
            plan = RefreshOperations(config).plan_snapshot_refresh(
                args.root_id, max_depth=args.max_depth, max_pages=args.max_pages
            )
            payload = {
                "root_id": plan.root_id,
                "max_depth": plan.max_depth,
                "estimated_pages": plan.estimated_pages,
                "estimated_disk_bytes": plan.estimated_disk_bytes,
                "minimum_duration_seconds": plan.minimum_duration_seconds,
                "network_access": False,
                "writes": False,
            }
        elif args.command == "export-hermes":
            path = RefreshOperations(config).export_hermes_context(args.root_id, args.filename)
            payload = {"root_id": args.root_id, "path": str(path), "format": "jsonl"}
        elif args.command == "apply-refresh":
            payload = _refresh_operations(config).apply_snapshot_refresh(
                args.root_id, max_depth=args.max_depth, max_pages=args.max_pages, confirmation=args.confirm
            )
        else:
            policy = SnapshotPolicy(config)
            repository = SnapshotRepository(policy)
            if args.command == "index":
                build = SnapshotIndexer(repository, policy).build(args.root_id)
                payload = {"root_id": build.root_id, "index_path": str(build.index_path), "chunks_indexed": build.chunks_indexed}
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
    if args.command == "doctor" and not args.json:
        for diagnostic in payload["diagnostics"]:
            print(f"{diagnostic['code']}: {diagnostic['message']}", file=sys.stderr)
    return 0
