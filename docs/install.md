# Instalação

Requisito: Python 3.11+ e SQLite com FTS5. Prefira `uvx` ou `pipx` para isolar a ferramenta.

```bash
uvx --from tdn-protheus-mcp tdn-protheus-mcp --help
# ou
pipx install tdn-protheus-mcp
```

Crie a configuração a partir de `tdn-protheus-mcp.config.example.json`; mantenha `offline: true` e `allow_mutations: false`. Importe um snapshot compatível ou atualize-o explicitamente pelo comando `apply-refresh`, valide-o e crie o índice:

```bash
tdn-protheus-mcp doctor --config ./tdn-protheus-mcp.config.json --json
tdn-protheus-mcp index --config ./tdn-protheus-mcp.config.json --root-id 235312129 --json
```

Remoção: `pipx uninstall tdn-protheus-mcp`. A remoção do pacote não apaga o snapshot local.
