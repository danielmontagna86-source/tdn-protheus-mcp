# Compatibilidade de harnesses

O TDN Protheus MCP é um processo local, somente leitura, por `stdio`. A compatibilidade é definida pelo protocolo MCP e pela capacidade do cliente de iniciar um processo local, não pelo modelo de IA.

| Categoria | Exemplos | Estado | Uso |
|---|---|---|---|
| Clientes de referência | Codex, Claude Code | Suportado | Use os guias específicos do projeto. |
| MCP `stdio` genérico | Claude Desktop, Cursor, Cline, Continue, IDEs e agentes compatíveis | Suportado pelo contrato | Use a configuração genérica e o smoke client. |
| Adaptadores de fluxo | Hermes, Antigravity | Compatível quando o harness aceitar MCP `stdio` | Registre o mesmo servidor local; se o fluxo aceitar somente arquivos, use o JSONL produzido pela Skill. |
| Provedor de modelo | OpenRouter | Não é harness MCP | Use-o por meio de um cliente que hospede MCP `stdio`. |

## Verificação independente

O exemplo `examples/mcp_smoke_client.py` inicia o processo e chama `search_tdn_docs` pelo SDK MCP:

```bash
python examples/mcp_smoke_client.py --config ./tdn-protheus-mcp.config.json --root-id 235312129 --query FWRest
```

Uma integração só deve ser declarada compatível se aceitar comando, argumentos e ambiente para um servidor MCP `stdio`. O projeto não oferece HTTP/SSE, OAuth, conta remota ou instalação automática no harness.

## Perfis de configuração

- **Codex e Claude Code**: usam o mesmo processo `tdn-protheus-mcp serve ... --transport stdio`.
- **Hermes e Antigravity**: use MCP `stdio` quando suportado. Para fluxos baseados em arquivo, gere JSONL com o `tdn-protheus-skill-kit`; o MCP não exporta nem grava arquivos de contexto.
- **OpenRouter**: selecione o modelo no cliente que hospeda o MCP. OpenRouter não recebe diretamente a configuração deste servidor.

## Skill complementar

A Skill [`coletando-documentacao-tdn-protheus`](companion-skill.md) é o único componente responsável por localizar, coletar e atualizar snapshots. Ela produz snapshots schema v2 e mantém leitura/migração de v1. O MCP aceita v1/v2, lê `page_directory` quando presente e nunca escreve o snapshot.

Depois de qualquer snapshot ou refresh da Skill, execute novamente `tdn-protheus-mcp index`. Se o manifesto mudou, uma consulta com índice antigo é recusada com `POLICY_INDEX_STALE`.
