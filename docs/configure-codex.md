# Codex

Adicione ao `~/.codex/config.toml` local:

```toml
[mcp_servers.tdn_protheus]
command = "uvx"
args = ["--from", "tdn-protheus-mcp", "tdn-protheus-mcp", "serve", "--config", "C:/caminho/tdn-protheus-mcp.config.json", "--transport", "stdio"]
```

O MCP devolve apenas referências externas locais; valide as citações antes de usar código ou procedimentos do TDN.
