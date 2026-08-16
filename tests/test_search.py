from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from tdn_protheus_mcp.config import McpConfig
from tdn_protheus_mcp.contracts import PolicyRefusal
from tdn_protheus_mcp.indexer import SnapshotIndexer
from tdn_protheus_mcp.policy import SnapshotPolicy
from tdn_protheus_mcp.search import SnapshotSearch
from tdn_protheus_mcp.snapshot_repository import SnapshotRepository


def prepare(temp_dir: str, records: list[dict]):
    cache = Path(temp_dir) / "cache"
    pages = cache / "1" / "pages"
    pages.mkdir(parents=True)
    manifest_pages = {}
    for record in records:
        (pages / f"{record['id']}.json").write_text(json.dumps(record), encoding="utf-8")
        manifest_pages[str(record["id"])] = {"status": "active"}
    (cache / "1" / "manifest.json").write_text(json.dumps({"schema_version": 1, "root_id": 1, "pages": manifest_pages}), encoding="utf-8")
    policy = SnapshotPolicy(McpConfig(cache_root=cache, allowed_root_ids=frozenset({"1"})))
    repo = SnapshotRepository(policy)
    SnapshotIndexer(repo, policy).build("1")
    return policy, repo, SnapshotSearch(policy)


class SnapshotSearchTests(unittest.TestCase):
    def test_filters_are_applied_before_limit_and_metadata_is_derived(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            records = [{"id": i, "title": f"Genérico {i}", "url": f"https://tdn/{i}", "text": "Documento Entrada genérico."} for i in range(1, 30)]
            records.append({"id": 99, "title": "MATA103 Documento de Entrada", "url": "https://tdn/99", "text": "Documento Entrada MATA103 usa SD1 e MV_TESTE no SIGACOM."})
            policy, _repo, search = prepare(temp_dir, records)
            results = search.search(policy.search_query("Documento Entrada", "1", 1, 12000), routine="MATA103")
            self.assertEqual([r.page_id for r in results], ["99"])
            self.assertEqual([r.page_id for r in search.search(policy.search_query("SD1", "1", 8, 12000), table="SD1")], ["99"])
            self.assertEqual([r.page_id for r in search.search(policy.search_query("MV_TESTE", "1", 8, 12000), parameter="MV_TESTE")], ["99"])
            self.assertEqual([r.page_id for r in search.search(policy.search_query("SIGACOM", "1", 8, 12000), module="SIGACOM")], ["99"])

    def test_non_prefixed_routine_and_missing_routine(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy, _repo, search = prepare(temp_dir, [{"id": 10, "title": "Ponto de Entrada PLRSTPR1", "url": "https://tdn/10", "text": "PLRSTPR1 recebe PARAMIXB."}])
            self.assertEqual([r.page_id for r in search.search(policy.search_query("PLRSTPR1", "1", 8, 12000), routine="PLRSTPR1")], ["10"])
            self.assertEqual(search.search(policy.search_query("PLRSTPR1", "1", 8, 12000), routine="MT103VALIDAITENSXYZ"), ())

    def test_search_rejects_stale_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy, repo, search = prepare(temp_dir, [{"id": 10, "title": "FWRest", "url": "https://tdn/10", "text": "FWRest usa REST."}])
            manifest = policy.cache_root / "1" / "manifest.json"
            data = json.loads(manifest.read_text())
            data["updated_at"] = "changed"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(PolicyRefusal, "POLICY_INDEX_STALE"):
                search.search(policy.search_query("FWRest", "1", 8, 12000))


if __name__ == "__main__":
    unittest.main()
