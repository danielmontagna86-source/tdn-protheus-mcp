# Decisão de distribuição remota

## Decisão atual

Manter somente MCP local por `stdio`. Não há servidor HTTP, conta, autenticação, cache compartilhado ou snapshot centralizado.

## Alternativas avaliadas

| Opção | Decisão | Motivo |
|---|---|---|
| MCP local `stdio` | Escolhida | Privacidade, operação simples e snapshot sob controle da pessoa usuária. |
| Imagem Docker local | Adiada | Pode reduzir fricção em alguns ambientes, mas não é necessária para `stdio`. |
| Streamable HTTP multiusuário | Rejeitada por enquanto | Exigiria OAuth 2.1, tenant isolation, rate limits, retenção, LGPD, direitos de conteúdo e resposta a incidentes. |

## Threat model mínimo

Conteúdo TDN é referência externa não confiável; não pode virar instrução de sistema. Snapshots podem conter dados indevidos; por isso não entram em release. Um serviço remoto adicionaria risco de exfiltração, enumeração de conteúdo, acesso cruzado entre tenants e custo operacional. Qualquer mudança dessa decisão exige ADR nova, revisão de termos/direitos, modelo de ameaça completo e piloto documentado.
