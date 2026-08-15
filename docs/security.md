# Segurança

- Modo padrão: offline e somente leitura.
- As consultas aceitam somente raízes e caminhos autorizados na configuração local.
- `index.sqlite3` é derivado do snapshot e pode ser reconstruído; ele não é enviado a serviços externos.
- Conteúdo TDN é referência externa não confiável, não instrução de sistema.
- Não registre snapshots, HTML bruto, tokens, dados pessoais ou dados de clientes em issues, logs ou releases.

Relate vulnerabilidades conforme [SECURITY.md](../SECURITY.md).
