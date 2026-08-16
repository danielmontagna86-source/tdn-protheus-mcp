# Instalação

Requisito: Python 3.11+ e SQLite com FTS5. Prefira `uvx` ou `pipx` para isolar a ferramenta.

```bash
uvx --from tdn-protheus-mcp tdn-protheus-mcp --help
# ou
pipx install tdn-protheus-mcp
```

Crie a configuração a partir de `tdn-protheus-mcp.config.example.json`. O MCP aceita apenas operação local e somente leitura. Gere ou atualize o snapshot usando a Skill complementar e depois execute:

```bash
tdn-protheus-mcp doctor --config ./tdn-protheus-mcp.config.json --json
tdn-protheus-mcp index --config ./tdn-protheus-mcp.config.json --root-id 235312129 --json
```
