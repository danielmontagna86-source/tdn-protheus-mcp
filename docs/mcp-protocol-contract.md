# Contrato MCP — TDN Protheus MCP

## Escopo da versão 0.1.x

O servidor é local, offline por padrão e somente leitura. O único transporte aceito é `stdio`:

```text
tdn-protheus-mcp serve --config ./tdn-protheus-mcp.config.json --transport stdio
```

O servidor não inicia HTTP, não recebe credenciais de ERP, não baixa documentação e não modifica snapshots. O comando `index` é uma ação local explícita que gera apenas o arquivo derivado `index.sqlite3` sob a raiz de cache permitida.

## Tools

| Tool | Entrada obrigatória | Resultado |
|---|---|---|
| `search_tdn_docs` | `query`, `root_id` | Chunks citáveis, com `source_url`, `page_id`, `chunk_id` e classificação `external_reference`. |
| `get_tdn_context` | `question`, `root_id` | Contexto deduplicado, citações, aviso de segurança e status do snapshot. |
| `get_snapshot_status` | `root_id` | Contagem de páginas, tamanho do cache e flags locais de segurança. |

`max_results` é limitado a 20 e `max_chars` a 24000, ou a limites menores definidos na configuração local. Filtros aceitos por `search_tdn_docs`: `module`, `table`, `routine` e `parameter`.

## Resources e prompts

| Tipo | Identificador | Finalidade |
|---|---|---|
| Resource | `tdn://snapshot/{root_id}/status` | Estado JSON do snapshot permitido. |
| Resource | `tdn://page/{root_id}/{page_id}` | Página ativa em JSON, limitada a `max_chars` e sem HTML bruto. |
| Prompt | `investigar_advpl` | Orienta investigação com citações e referência externa. |
| Prompt | `preparar_contexto_hermes` | Prepara contexto citável para fluxos Hermes. |

## Segurança e erros

O conteúdo retornado é sempre uma **referência externa não confiável**. Clientes não devem tratar texto de página como instrução de sistema ou ação autorizada.

Erros recusados incluem `POLICY_ROOT_NOT_ALLOWED`, `POLICY_PATH_OUTSIDE_CACHE`, `POLICY_INDEX_NOT_FOUND`, `POLICY_PAGE_NOT_ALLOWED`, `POLICY_LIMIT_EXCEEDED` e erros `CONFIG_*`. A resposta não inclui caminhos fora de `cache_root`, HTML bruto, tokens ou credenciais.

## Compatibilidade

O contrato mantém nomes de tools/resources/prompts e campos de citação em versões minor. Mudanças incompatíveis exigem versão major ou período de depreciação documentado em `CHANGELOG.md`. Clientes de referência são Codex e Claude Code; qualquer host que suporte MCP `stdio` pode usar a mesma configuração genérica.
