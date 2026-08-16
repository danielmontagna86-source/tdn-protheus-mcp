# Política de release e suporte

- O MCP é estritamente local, `stdio` e somente leitura.
- Toda release deve passar a matriz Python 3.11/3.12 em Linux, Windows e macOS.
- Cobertura de branch mínima: 75%.
- Wheel e sdist precisam passar `twine check`.
- SBOM e checksums devem acompanhar a GitHub Release.
- Publicação PyPI usa Trusted Publishing e fonte imutável de tag.
- Mudanças incompatíveis no contrato MCP ou formato de configuração exigem incremento de versão compatível com a política SemVer do projeto.
- Um índice nunca pode ser considerado válido sem `snapshot_fingerprint` correspondente ao manifesto ativo.
