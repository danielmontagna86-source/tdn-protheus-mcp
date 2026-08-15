# Changelog

Todas as mudanças relevantes deste projeto serão registradas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o versionamento segue [Semantic Versioning](https://semver.org/lang/pt-BR/). 

## [0.3.0] - 2026-08-15

### Added

- Pacote público `tdn-protheus-mcp` com CLI, configuração segura e índice SQLite FTS5 local.
- Servidor MCP `stdio` read-only com tools, resources, prompts e citações rastreáveis.
- Guias de instalação e configuração para Claude Code, Codex e hosts MCP genéricos.
- Contrato de protocolo, documentação de segurança e decisão de distribuição.

### Changed

- Refresh opcional com paginação completa, prazo global propagado a cada chamada HTTP e erros TDN estáveis.
- Publicação de snapshots por geração imutável e invalidação do índice FTS quando o conteúdo é atualizado.
