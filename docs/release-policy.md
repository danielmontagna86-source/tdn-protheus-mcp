# Política de release e suporte

O projeto usa versionamento semântico. Correções compatíveis usam patch; novos comandos, tools ou campos opcionais usam minor; remoções ou mudanças incompatíveis exigem major ou período de depreciação documentado.

Cada release deve incluir testes offline verdes, CI em Windows/macOS/Linux, wheel, sdist, SBOM, checksums e notas no CHANGELOG. Issues devem conter versão, sistema operacional, comando sem segredos, saída sanitizada e passos de reprodução. Não envie snapshot, HTML TDN, `.env`, token ou dados de cliente.

O suporte é comunitário e best effort. Vulnerabilidades seguem [SECURITY.md](../SECURITY.md).
