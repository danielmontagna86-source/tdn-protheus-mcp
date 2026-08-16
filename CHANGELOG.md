# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

## [Unreleased]

### Changed

- MCP simplificado para operação estritamente local e somente leitura; capacidades de refresh/export mutáveis foram removidas.
- Índice FTS5 agora é vinculado ao fingerprint do snapshot e buscas recusam índice desatualizado com `POLICY_INDEX_STALE`.
- Metadados de módulo, tabela, parâmetro, rotina e ponto de entrada passam a ser derivados durante a indexação.
- Filtros de busca são aplicados no SQL antes do `LIMIT`.
- Chunking passou a respeitar preferencialmente quebras textuais e overlap.
- CI/release deixaram de instalar o antigo extra `[snapshot]` e passaram a exigir cobertura de branch mínima de 75%.

### Removed

- Coletor HTTP, refresh adapter, audit log de mutações e operações mutáveis do MCP.

## [0.3.1] - 2026-08-16

### Fixed

- A indexação de snapshot inexistente retorna `POLICY_SNAPSHOT_NOT_FOUND`.
- A derivação de rotina em snapshots v1 cobre identificadores como `PLRSTPR1`.
- O modo offline recusa refresh antes de inicializar o coletor HTTP.

## [0.3.0] - 2026-08-15

### Added

- Pacote público `tdn-protheus-mcp` com CLI, configuração segura e índice SQLite FTS5 local.
- Servidor MCP `stdio` com tools, resources, prompts e citações rastreáveis.
