# ADR 0001 — Distribuição inicial

## Decisão

Distribuir o MCP como pacote Python no PyPI e GitHub Releases. O caminho recomendado é `uvx`; `pipx` é alternativa. Docker não é requisito do MVP.

## Motivo

O servidor `stdio` é local e usa um snapshot sob controle da pessoa usuária. Exigir Docker elevaria a barreira de entrada, principalmente no Windows, sem melhorar o modelo de segurança da primeira versão.

## Consequências

Manter testes multiplataforma e documentação de Python. Uma imagem Docker local poderá ser avaliada após evidência de demanda, sem criar endpoint remoto.
