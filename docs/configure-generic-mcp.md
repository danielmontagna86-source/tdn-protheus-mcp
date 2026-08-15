# Configuração MCP genérica

Hosts que aceitam servidor `stdio` normalmente usam esta estrutura:

```json
{"command":"uvx","args":["--from","tdn-protheus-mcp","tdn-protheus-mcp","serve","--config","/caminho/tdn-protheus-mcp.config.json","--transport","stdio"]}
```

O projeto não oferece HTTP/SSE remoto na versão local. Se o host exigir URL HTTP, ele não é compatível com esta release.
