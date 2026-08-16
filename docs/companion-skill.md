# Skill complementar e contrato de snapshot

O `tdn-protheus-skill-kit` e o `tdn-protheus-mcp` são projetos independentes e complementares.

| Componente | Responsabilidade |
|---|---|
| Skill | Localizar, coletar, sanitizar, criar e atualizar o snapshot local. |
| MCP | Ler o snapshot, indexar, buscar, montar contexto e citar via MCP `stdio`. |

**A Skill é o único escritor do snapshot. O MCP é sempre somente leitura.**

O leitor MCP aceita snapshot schema v1 e v2. O manifesto fica em `cache_root/<root_id>/manifest.json`. Quando existir `page_directory`, o MCP resolve as páginas a partir desse diretório; em snapshots v1 legados, o padrão é `pages/`.

Use o mesmo `cache_root` absoluto na Skill e no MCP. Depois de qualquer snapshot ou refresh da Skill:

```bash
tdn-protheus-mcp doctor --config ./tdn-protheus-mcp.config.json --json
tdn-protheus-mcp index --config ./tdn-protheus-mcp.config.json --root-id 235312129 --json
```

Se o snapshot mudar e o índice não for reconstruído, as consultas são recusadas com `POLICY_INDEX_STALE`.
