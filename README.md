# TDN Protheus MCP

MCP público e open source para pesquisar um **snapshot local controlado pela pessoa usuária** da documentação TDN Protheus. O servidor funciona exclusivamente por `stdio`, é somente leitura e não possui capacidade de rede ou atualização de snapshot.

O código usa Apache-2.0. A licença não transfere direitos sobre conteúdo, marcas ou serviços TOTVS/TDN; não publique snapshots nem dados de clientes.

## Responsabilidade

- Lê snapshots locais produzidos pela skill complementar ou por outro produtor compatível.
- Cria índice SQLite FTS5 local e vincula o índice ao fingerprint exato do snapshot.
- Recusa consultas quando o índice está ausente, inválido ou desatualizado.
- Deriva metadados de módulo, tabela, parâmetro, rotina e ponto de entrada durante a indexação.
- Expõe tools/resources/prompts MCP via `stdio`.

## O que ele não faz

- Não coleta documentação da internet.
- Não atualiza snapshots.
- Não conecta no ERP, banco, AppServer ou RPO.
- Não executa AdvPL/TLPP.

## Início rápido

```bash
uvx --from tdn-protheus-mcp tdn-protheus-mcp doctor --config ./tdn-protheus-mcp.config.json --json
uvx --from tdn-protheus-mcp tdn-protheus-mcp index --config ./tdn-protheus-mcp.config.json --root-id 235312129 --json
```

Depois configure o cliente para iniciar:

```bash
tdn-protheus-mcp serve --config ./tdn-protheus-mcp.config.json --transport stdio
```

Após qualquer snapshot/refresh feito pela Skill, execute `index` novamente. Se isso não ocorrer, a busca retorna `POLICY_INDEX_STALE` em vez de responder com evidência antiga.

## Skill complementar

https://github.com/danielmontagna86-source/tdn-protheus-skill-kit

A Skill é o único componente responsável por localizar, coletar e atualizar a documentação. O MCP somente consome o snapshot já preparado.

## Desenvolvimento

```bash
python -m pip install -e .
python -m unittest discover -s tests -p "test_*.py" -v
python -m build
python -m twine check dist/*
```
