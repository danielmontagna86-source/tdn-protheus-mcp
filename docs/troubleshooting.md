# Troubleshooting

| Sintoma | Ação |
|---|---|
| `CONFIG_NOT_FOUND` | Copie o arquivo de exemplo e informe `--config` com caminho existente. |
| `SNAPSHOT_NOT_FOUND` | Importe um cache local permitido ou execute `apply-refresh` após habilitar explicitamente a atualização. |
| `POLICY_INDEX_NOT_FOUND` | Execute `tdn-protheus-mcp index` explicitamente para a mesma `root_id`. |
| Servidor fecha no host | Execute `tdn-protheus-mcp doctor` e confirme que o host usa `stdio`, não HTTP. |
| Resultado vazio | Verifique a raiz, recrie o índice e use termos técnicos da página TDN. |
