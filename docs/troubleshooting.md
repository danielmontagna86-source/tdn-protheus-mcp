# Troubleshooting

| Sintoma | Ação |
|---|---|
| `CONFIG_NOT_FOUND` | Copie o arquivo de exemplo e informe `--config` com caminho existente. |
| `CONFIG_READ_ONLY_REQUIRED` | Remova configuração mutável; o MCP aceita somente `offline=true` e `allow_mutations=false`. |
| `SNAPSHOT_NOT_FOUND` / `POLICY_SNAPSHOT_NOT_FOUND` | Crie ou atualize o snapshot com o `tdn-protheus-skill-kit` usando o mesmo `cache_root`. |
| `POLICY_SNAPSHOT_INVALID` | Valide `manifest.json`, `schema_version`, `root_id`, `page_directory` e arquivos de páginas. |
| `POLICY_INDEX_NOT_FOUND` | Execute `tdn-protheus-mcp index` para a mesma `root_id`. |
| `POLICY_INDEX_STALE` | O snapshot mudou depois da indexação; execute `index` novamente. |
| `POLICY_INDEX_INVALID` | Remova/reconstrua o índice derivado com `index`; não altere o snapshot. |
| Servidor fecha no host | Execute `doctor` e confirme que o host usa `stdio`, não HTTP. |
| Resultado vazio | Confirme a raiz, o status do índice e os filtros; depois revise se a evidência realmente existe no snapshot. |

`doctor --json` deve ser o primeiro diagnóstico operacional antes de investigar uma busca vazia ou erro de integração.
