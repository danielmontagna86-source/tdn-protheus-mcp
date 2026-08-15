from __future__ import annotations

import anyio
import json
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from pydantic import AnyUrl


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tdn_protheus_mcp.config import McpConfig  # noqa: E402
from tdn_protheus_mcp.indexer import SnapshotIndexer  # noqa: E402
from tdn_protheus_mcp.policy import SnapshotPolicy  # noqa: E402
from tdn_protheus_mcp.snapshot_repository import SnapshotRepository  # noqa: E402


class McpServerTests(unittest.TestCase):
    def test_stdio_server_exposes_read_only_tools_resources_and_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            pages_dir = cache_root / "1" / "pages"
            pages_dir.mkdir(parents=True)
            (pages_dir / "10.json").write_text(json.dumps({"id": 10, "title": "FWRest", "url": "https://tdn.totvs.com/10", "text": "FWRest consulta serviços REST. " + ("x" * 25000), "fetched_at": "2026-08-15", "html": "<script>não retornar</script>"}), encoding="utf-8")
            (cache_root / "1" / "manifest.json").write_text(json.dumps({"root_id": 1, "last_complete_at": "2026-08-15", "pages": {"10": {"status": "active"}}}), encoding="utf-8")
            config_path = Path(temp_dir) / "mcp.json"
            config_path.write_text(json.dumps({"cache_root": str(cache_root), "allowed_root_ids": ["1"]}), encoding="utf-8")
            policy = SnapshotPolicy(McpConfig(cache_root=cache_root, allowed_root_ids=frozenset({"1"})))
            SnapshotIndexer(SnapshotRepository(policy), policy).build("1")

            async def exercise() -> None:
                parameters = StdioServerParameters(command=sys.executable, args=["-m", "tdn_protheus_mcp", "serve", "--config", str(config_path), "--transport", "stdio"], cwd=ROOT)
                async with stdio_client(parameters) as (reader, writer):
                    async with ClientSession(reader, writer) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        prompts = await session.list_prompts()
                        search = await session.call_tool("search_tdn_docs", {"query": "FWRest", "root_id": "1"})
                        context = await session.call_tool("get_tdn_context", {"question": "Como usar FWRest?", "root_id": "1"})
                        tool_status = await session.call_tool("get_snapshot_status", {"root_id": "1"})
                        status = await session.read_resource(AnyUrl("tdn://snapshot/1/status"))
                        page = await session.read_resource(AnyUrl("tdn://page/1/10"))
                        prompt = await session.get_prompt("investigar_advpl", {"question": "Como usar FWRest?"})

                        self.assertEqual({tool.name for tool in tools.tools}, {"search_tdn_docs", "get_tdn_context", "get_snapshot_status"})
                        self.assertEqual({item.name for item in prompts.prompts}, {"investigar_advpl", "preparar_contexto_hermes"})
                        self.assertEqual(search.structuredContent["results"][0]["source_url"], "https://tdn.totvs.com/10")
                        self.assertEqual(context.structuredContent["citations"][0]["page_id"], "10")
                        self.assertTrue(tool_status.structuredContent["offline"])
                        self.assertTrue(json.loads(status.contents[0].text)["offline"])
                        page_payload = json.loads(page.contents[0].text)
                        self.assertLessEqual(len(page_payload["content"]), 24000)
                        self.assertNotIn("html", page_payload)
                        self.assertIn("referência externa", prompt.messages[0].content.text.lower())

            anyio.run(exercise)


if __name__ == "__main__":
    unittest.main()
