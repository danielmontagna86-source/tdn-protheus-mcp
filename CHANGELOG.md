# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.3.1] - 2026-08-16

### Fixed

- A indexação de snapshot inexistente retorna o erro de política estruturado `POLICY_SNAPSHOT_NOT_FOUND`.
- A derivação de rotina em snapshots v1 cobre identificadores documentais como `PLRSTPR1`.
- O modo offline recusa refresh antes de inicializar o coletor HTTP.

## [0.3.0] - 2026-08-15

### Added

- Pacote público `tdn-protheus-mcp` com CLI, configuração segura e índice SQLite FTS5 local.
- Servidor MCP `stdio` read-only com tools, resources, prompts e citações rastreáveis.
- Guias de instalação e configuração para Claude Code, Codex e hosts MCP genéricos.
- Contrato de protocolo, documentação de segurança e decisão de distribuição.

### Changed

- Refresh opcional com paginação completa, prazo global propagado a cada chamada HTTP e erros TDN estáveis.
- Publicação de snapshots por geração imutável e invalidação do índice FTS quando o conteúdo é atualizado.
- Indexação de cache sem manifesto agora devolve `POLICY_SNAPSHOT_NOT_FOUND` estruturado; metadados de rotina são derivados ao indexar snapshots v1 que não os persistem.
