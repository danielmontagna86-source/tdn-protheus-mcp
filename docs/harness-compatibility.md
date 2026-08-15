# Compatibilidade de harnesses

O TDN Protheus MCP é um processo local por `stdio`. A compatibilidade é definida pelo protocolo MCP, não pelo modelo, IDE ou fornecedor.

| Categoria | Exemplos | Estado | Uso |
|---|---|---|---|
| Referência validada | Codex, Claude Code | Suportado | Use os guias específicos do projeto. |
| MCP `stdio` genérico | Claude Desktop, Cursor, Cline, Continue, IDEs e agentes compatíveis | Suportado pelo contrato | Use a configuração JSON genérica e o smoke client. |
| Adaptadores de fluxo | Hermes, Antigravity | Compatível quando o harness aceitar MCP `stdio` | Use o mesmo processo; `export-hermes` é opcional para contexto JSONL. |
| Provedor de modelo | OpenRouter | Não é harness MCP | Conecte-o por meio de um cliente MCP compatível. |

## Verificação independente

O exemplo `examples/mcp_smoke_client.py` inicia o processo e chama `search_tdn_docs` pelo SDK MCP, sem usar um harness específico:

```bash
python examples/mcp_smoke_client.py --config ./tdn-protheus-mcp.config.json --root-id 235312129 --query FWRest
```

Uma integração deve ser declarada “suportada pelo contrato” somente se aceitar comando, argumentos e ambiente para um servidor MCP `stdio`. Não prometa recursos de UI, OAuth, HTTP ou instalação automática que o harness não ofereça.

## Perfis de configuração

- **Codex e Claude Code**: use os guias `configure-codex.md` e `configure-claude-code.md`; ambos iniciam o mesmo processo `stdio`.
- **Hermes e Antigravity**: registre a configuração JSON genérica quando o produto permitir servidor MCP local. Se só aceitar arquivos de contexto, use `export-hermes` para gerar JSONL do cache já existente; isso não ativa rede.
- **OpenRouter**: escolha o modelo no cliente que hospeda o MCP. OpenRouter não recebe a configuração deste servidor diretamente.

## Skill complementar

Para padronizar a coleta e a manutenção do snapshot, instale separadamente a skill [`coletando-documentacao-tdn-protheus`](companion-skill.md). Ela é opcional, funciona em Codex, Claude Code, Antigravity e loaders compatíveis, e produz o snapshot schema-v1 que o MCP `0.3.x` aceita. A skill não é empacotada no servidor MCP e não altera sua política offline/read-only.

Para atualizar um snapshot, altere conscientemente `offline` para `false` e `allow_mutations` para `true`, defina `tdn_api_base` se usar um espelho HTTPS e execute `apply-refresh --confirm APPLY`. Consultas e inicialização permanecem offline por padrão.
