# TDN Protheus MCP

MCP público e open source para pesquisar documentação TDN Protheus a partir de um **snapshot local controlado pela pessoa usuária**. Funciona por `stdio`, não exige token de LLM e não depende do Chat Protheus IA Lab.

O código usa Apache-2.0. A licença não transfere direitos sobre conteúdo, marcas ou serviços TOTVS/TDN; não publique snapshots nem dados de clientes.

## O que ele faz

- Pesquisa um índice SQLite FTS5 local e devolve citações (`source_url`, página e chunk).
- Expõe tools, resources e prompts MCP para qualquer harness compatível com MCP por `stdio`; Codex e Claude Code são apenas clientes de referência.
- Inicia offline e read-only. Não baixa documentos durante consultas.
- A obtenção e atualização do snapshot são capacidades do próprio pacote, sempre acionadas explicitamente.

## Início rápido

Depois da publicação no PyPI:

```bash
uvx --from "tdn-protheus-mcp[snapshot]" tdn-protheus-mcp doctor --config ./tdn-protheus-mcp.config.json --json
uvx --from "tdn-protheus-mcp[snapshot]" tdn-protheus-mcp index --config ./tdn-protheus-mcp.config.json --root-id 235312129 --json
```

Copie `tdn-protheus-mcp.config.example.json`, altere `cache_root` e, quando quiser atualizar, use `apply-refresh` com os opt-ins exigidos. Veja [instalação](docs/install.md), [segurança](docs/security.md) e o [contrato MCP](docs/mcp-protocol-contract.md).

## Clientes MCP

- [Claude Code](docs/configure-claude-code.md)
- [Codex](docs/configure-codex.md)
- [Configuração genérica](docs/configure-generic-mcp.md)
- [Matriz de compatibilidade de harnesses](docs/harness-compatibility.md)
- [Política de release e suporte](docs/release-policy.md)
- [Telemetria](docs/telemetry.md)

OpenRouter é um gateway/model provider, não um host MCP por si só. Use-o somente através de um cliente que implemente MCP `stdio`.

## Compatibilidade de harness

O servidor não depende do Chat Protheus IA Lab, de um modelo específico ou de um fornecedor de agentes. Claude Code, Codex, Claude Desktop, Cursor, Cline, IDEs e outros harnesses usam o mesmo processo `stdio` e contrato. Qualquer ferramenta que produza o formato público de snapshot local pode alimentar o MCP.

## Desenvolvimento

```bash
python -m pip install -e ".[snapshot]"
python -m unittest discover -s tests -p "test_*.py" -v
python -m build
python -m twine check dist/*
```

Não envie `tdn-cache/`, `.venv/`, snapshots, JSONL, HTML coletado, segredos ou dados de clientes. Consulte [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), [SUPPORT.md](SUPPORT.md) e [CHANGELOG.md](CHANGELOG.md).

