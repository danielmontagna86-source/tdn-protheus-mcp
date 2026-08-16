# Hardening e critérios de validação

Invariantes obrigatórios antes de merge/release da linha hardening.

## Responsabilidade

- O MCP é estritamente local, somente leitura e usa apenas `stdio`.
- Não contém coletor HTTP, refresh, exportação mutável ou conexão com ERP.
- A Skill complementar é o único escritor do snapshot.

## Integridade

- O leitor aceita snapshots v1 e v2 e respeita `page_directory`.
- `page_directory` permanece dentro da própria `root_id`.
- O índice FTS5 armazena `snapshot_fingerprint` do manifesto ativo.
- Qualquer alteração do manifesto torna o índice stale e a busca deve retornar `POLICY_INDEX_STALE` até reindexação.
- Índices ausentes/corrompidos têm erros estruturados e nunca são usados silenciosamente.

## Retrieval

- Metadados de módulo, tabela, parâmetro, rotina e ponto de entrada são derivados durante indexação.
- Filtros são aplicados no SQL antes do `LIMIT`.
- `MATA103`, `PLRSTPR1`, `SD1100I`, tabelas Protheus comuns e `MV_*` possuem fixtures.
- O caso inventado `MT103VALIDAITENSXYZ` deve produzir zero evidência.
- Avaliações separam citation recall, exact source rate e no-evidence accuracy.

## Contexto

- Chunks usam limites naturais e overlap.
- O assembler respeita orçamento e admite até dois chunks relevantes por página.
- Conteúdo retornado permanece classificado como referência externa.

## Qualidade

- Matriz CI: Linux, Windows e macOS; Python 3.11 e 3.12.
- Ruff, cobertura mínima, auditoria de dependências, smoke MCP real, build/Twine e SBOM.
- Publicação PyPI continua via Trusted Publishing e tag imutável.
- Integração live com Skill deve validar snapshot v2 -> index -> citação e no-evidence.

Nenhuma release deve ser criada enquanto algum gate obrigatório estiver vermelho.
