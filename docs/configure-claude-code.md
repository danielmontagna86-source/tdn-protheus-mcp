# Claude Code

Após criar configuração e índice locais, adicione o servidor para seu usuário:

```bash
claude mcp add --scope user tdn-protheus -- uvx --from tdn-protheus-mcp tdn-protheus-mcp serve --config /caminho/absoluto/tdn-protheus-mcp.config.json --transport stdio
```

Para configuração compartilhada de projeto, crie `.mcp.json`:

```json
{"mcpServers":{"tdn-protheus":{"command":"uvx","args":["--from","tdn-protheus-mcp","tdn-protheus-mcp","serve","--config","${TDN_PROTHEUS_MCP_CONFIG}","--transport","stdio"]}}}
```

Não inclua o snapshot, credenciais ou caminhos pessoais no repositório.
