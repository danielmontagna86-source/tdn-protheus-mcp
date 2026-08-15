"""Generic MCP stdio smoke client; it does not depend on any agent harness."""

from __future__ import annotations

import argparse
import anyio

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="caminho da configuração local do MCP")
    parser.add_argument("--root-id", required=True)
    parser.add_argument("--query", default="FWRest")
    parser.add_argument("--command", default="tdn-protheus-mcp")
    return parser.parse_args()


async def exercise(args: argparse.Namespace) -> None:
    parameters = StdioServerParameters(
        command=args.command,
        args=["serve", "--config", args.config, "--transport", "stdio"],
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            result = await session.call_tool("search_tdn_docs", {"query": args.query, "root_id": args.root_id})
            print(result.structuredContent)


def main() -> None:
    anyio.run(exercise, parse_args())


if __name__ == "__main__":
    main()
