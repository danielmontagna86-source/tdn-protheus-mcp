# Contrato MCP — TDN Protheus MCP

## Escopo

Servidor local e somente leitura. O único transporte aceito é `stdio`.

## Tools

| Tool | Entrada | Resultado |
|---|---|---|
| `search_tdn_docs` | `query`, `root_id` | Chunks citáveis com `source_url`, `page_id` e `chunk_id`. |
| `get_tdn_context` | `question`, `root_id` | Contexto deduplicado, citações e status do snapshot. |
| `get_snapshot_status` | `root_id` | Estado local do snapshot. |

Não existe tool de refresh, exportação ou escrita.

Filtros aceitos por `search_tdn_docs`: `module`, `table`, `routine`, `parameter`. Eles são aplicados antes do `LIMIT` de resultados.

## Integridade

O índice registra um fingerprint SHA-256 do manifesto do snapshot usado na construção. Toda busca compara esse valor ao snapshot atual. Diferenças retornam `POLICY_INDEX_STALE` e exigem reindexação explícita.

## Resources e prompts

- `tdn://snapshot/{root_id}/status`
- `tdn://page/{root_id}/{page_id}`
- `investigar_advpl`
- `preparar_contexto_hermes`

Todo conteúdo retornado é classificado como referência externa e deve ser validado antes de qualquer implementação.
