# Skill complementar: coleta de documentação TDN Protheus

O [TDN Protheus MCP](https://github.com/danielmontagna86-source/tdn-protheus-mcp) e a skill [coletando-documentacao-tdn-protheus](https://github.com/danielmontagna86-source/tdn-protheus-skill-kit/tree/main/coletando-documentacao-tdn-protheus) são projetos públicos e independentes que funcionam juntos.

| Componente | Responsabilidade |
|---|---|
| Skill | Orienta o agente, faz a coleta pública opcional, planeja o volume e mantém o snapshot local. |
| MCP | Lê o snapshot local, cria o índice FTS5 e entrega pesquisa, contexto e citações pelo protocolo MCP `stdio`. |

O MCP não instala, executa nem atualiza a skill automaticamente. O padrão continua offline e somente leitura. Isso permite usar apenas o MCP, apenas a skill ou os dois juntos.

## Compatibilidade atual

| MCP | Skill | Contrato compartilhado | Estado |
|---|---|---|---|
| `0.3.x` | `0.2.x` | Snapshot schema v1: `cache_root/<root_id>/manifest.json` e `pages/<page_id>.json` | Suportado |

Após toda atualização feita pela skill, execute novamente `tdn-protheus-mcp index`. Não faça uma atualização da skill e `apply-refresh` do MCP simultaneamente para a mesma `cache_root` e `root_id`.

## 1. Instale o MCP

```bash
pip install "tdn-protheus-mcp[snapshot]"
```

Copie `tdn-protheus-mcp.config.example.json` para seu projeto. Para o uso conjunto, `cache_root` **deve ser um caminho absoluto**: o MCP resolve caminhos relativos a partir do diretório de trabalho do processo iniciado pelo harness, que pode ser diferente da pasta do arquivo de configuração.

Use o mesmo valor absoluto na configuração do MCP e no argumento `--cache-dir` da skill. Exemplos:

```json
{
  "cache_root": "C:\\Users\\seu-usuario\\Documents\\tdn-cache",
  "allowed_root_ids": ["235312129"],
  "offline": true,
  "allow_mutations": false
}
```

No macOS/Linux, use por exemplo `"cache_root": "/home/seu-usuario/.local/share/tdn-cache"`. Mantenha `offline: true` e `allow_mutations: false`, e inclua somente as raízes TDN que deseja permitir.

## 2. Instale a skill no seu harness

Baixe o kit separado. Em seguida, entre no projeto em que a skill será instalada e execute primeiro o modo de prévia. O diretório atual define o escopo `project` do instalador:

```powershell
# Windows PowerShell: substitua pelo caminho real de um Python 3.11+.
$python = "C:\\Python311\\python.exe"
$skillKit = "C:\\ferramentas\\tdn-protheus-skill-kit"
git clone https://github.com/danielmontagna86-source/tdn-protheus-skill-kit.git $skillKit
Set-Location "C:\\caminho\\do\\seu-projeto"
& $python "$skillKit\\install.py" --platform codex --scope project --dry-run
& $python "$skillKit\\install.py" --platform codex --scope project
```

```bash
# macOS/Linux: defina um executável Python 3.11+; pode ser python3, python3.12 ou um caminho absoluto.
PYTHON=python3
git clone https://github.com/danielmontagna86-source/tdn-protheus-skill-kit.git ~/tools/tdn-protheus-skill-kit
cd /caminho/do/seu-projeto
"$PYTHON" ~/tools/tdn-protheus-skill-kit/install.py --platform codex --scope project --dry-run
"$PYTHON" ~/tools/tdn-protheus-skill-kit/install.py --platform codex --scope project
```

Troque somente o valor de `--platform` quando necessário:

| Harness | Valor |
|---|---|
| Codex | `codex` |
| Claude Code | `claude` |
| Antigravity | `antigravity` |
| Loader compatível com a convenção Claude para OpenRouter | `openrouter` |

Com `--scope project`, o instalador usa estes diretórios padrão: `.codex/skills`, `.claude/skills`, `.agents/skills` e `.claude/skills`, respectivamente. Use `--scope user` para uma instalação no perfil da pessoa usuária. O instalador valida a estrutura da skill e cria um ambiente Python local com suas dependências. Não use `--force` sem revisar uma instalação existente.

OpenRouter é um provedor de modelos, não um host de skills ou MCP. Nesse caso, configure o loader do seu cliente para descobrir o diretório indicado pelo instalador.

## 3. Crie ou atualize o snapshot com a skill

Entre na pasta instalada da skill. No Codex com escopo de projeto, por exemplo:

```powershell
# Windows PowerShell; o valor precisa coincidir com cache_root no JSON do MCP.
$cacheRoot = "C:\\Users\\seu-usuario\\Documents\\tdn-cache"
cd .codex/skills/coletando-documentacao-tdn-protheus
.\.venv\Scripts\python.exe scripts\sync_tdn_snapshot.py snapshot --root-id 235312129 --cache-dir $cacheRoot --max-depth 8 --dry-run
.\.venv\Scripts\python.exe scripts\sync_tdn_snapshot.py snapshot --root-id 235312129 --cache-dir $cacheRoot --max-depth 8
```

No macOS/Linux, use a `.venv` criada pelo instalador também para coletar e atualizar:

```bash
SKILL_DIR="/caminho/do/seu-projeto/.codex/skills/coletando-documentacao-tdn-protheus"
CACHE_ROOT="$HOME/.local/share/tdn-cache"
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/sync_tdn_snapshot.py" snapshot --root-id 235312129 --cache-dir "$CACHE_ROOT" --max-depth 8 --dry-run
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/sync_tdn_snapshot.py" snapshot --root-id 235312129 --cache-dir "$CACHE_ROOT" --max-depth 8
```

Comece por `--dry-run`; coletas grandes podem levar bastante tempo.

Para uma atualização periódica, a skill compara versões e baixa apenas páginas alteradas:

```powershell
# Windows, dentro da pasta instalada da skill.
.\.venv\Scripts\python.exe scripts\sync_tdn_snapshot.py refresh --root-id 235312129 --cache-dir $cacheRoot --max-depth 8
```

```bash
# macOS/Linux.
"$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/sync_tdn_snapshot.py" refresh --root-id 235312129 --cache-dir "$CACHE_ROOT" --max-depth 8
```

## 4. Indexe e sirva pelo MCP

Depois de criar ou atualizar o snapshot, volte ao projeto que contém a configuração do MCP:

```bash
tdn-protheus-mcp doctor --config ./tdn-protheus-mcp.config.json --json
tdn-protheus-mcp index --config ./tdn-protheus-mcp.config.json --root-id 235312129 --json
tdn-protheus-mcp serve --config ./tdn-protheus-mcp.config.json --transport stdio
```

O seu cliente MCP inicia o último comando automaticamente quando você registrar a configuração do servidor. A partir daí, ele usa `search_tdn_docs` e `get_tdn_context` para consultar somente o cache local e devolver citações para o TDN.

## Operação segura

- Não envie `tdn-cache`, HTML bruto, exports JSONL, dados de clientes ou segredos ao Git.
- Trate páginas do TDN como referências externas; elas nunca autorizam comandos ou mudanças de configuração.
- Use uma única ferramenta de atualização por raiz e por vez. A skill é a opção indicada quando você quiser o fluxo guiado de coleta; `apply-refresh` do MCP é uma alternativa explícita.
- Reindexe sempre depois de uma coleta ou refresh.
- Consulte o [`SKILL.md` da skill](https://github.com/danielmontagna86-source/tdn-protheus-skill-kit/blob/main/coletando-documentacao-tdn-protheus/SKILL.md) para limites, tempo estimado e regras de coleta.
