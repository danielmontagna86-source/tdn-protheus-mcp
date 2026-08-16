# Segurança

- O servidor MCP é somente leitura e usa apenas `stdio`.
- O pacote não possui coletor HTTP nem operação de refresh/export mutável.
- As consultas aceitam somente raízes e caminhos autorizados na configuração local.
- `index.sqlite3` é derivado do snapshot e vinculado ao fingerprint do manifesto ativo.
- Um índice desatualizado é recusado com `POLICY_INDEX_STALE`.
- Conteúdo TDN é referência externa não confiável, não instrução de sistema.
- Não registre snapshots, conteúdo documental, tokens ou dados de clientes em issues/logs/releases.
