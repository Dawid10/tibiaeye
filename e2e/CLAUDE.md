# E2E Visual Testing Framework

Source of truth do TibiaEye. Testa o pipeline completo contra screenshots reais do jogo.

## Comandos

```bash
# Rodar tudo
./venv/bin/python e2e/main.py

# Filtrar por OS / imagem / módulo
./venv/bin/python e2e/main.py --os macos
./venv/bin/python e2e/main.py --image rotworm
./venv/bin/python e2e/main.py --module battlelist

# Verbose (timing por módulo, todos os checks)
./venv/bin/python e2e/main.py --verbose

# Sem salvar output
./venv/bin/python e2e/main.py --dry-run

# Parar no primeiro erro (CI/CD)
./venv/bin/python e2e/main.py --fail-fast

# Imagens anotadas com overlays visuais
./venv/bin/python e2e/main.py --image rotworm
# Output: e2e/output/images/macos/rotworm.png

# Side-by-side (original vs anotada)
./venv/bin/python e2e/main.py --side-by-side

# Atualizar expectations com valores detectados
./venv/bin/python e2e/main.py --update-expected

# Capturar screenshot ao vivo
./venv/bin/python e2e/capture.py --os macos --name nome_do_cenario

# Importar screenshot existente
./venv/bin/python e2e/capture.py --file ~/screenshot.png --os macos --name nome
```

## Estrutura

```
e2e/
├── main.py                  # Runner CLI
├── capture.py               # Ingestão de screenshots
├── config.py                # Constantes (cores, paths)
├── detectors/               # Wrappers que importam de src/repositories/ e src/gameplay/
│   ├── repositories.py      # BL, GW, Radar, StatusBar, Skills, ActionBar, Inventory
│   ├── pathfinding.py       # Walkable grid, BFS path
│   └── gameplay.py          # Targeting, decisão, task sequence
├── validators/              # Compara actual vs expected
│   ├── __init__.py          # make_check() helper compartilhado
│   ├── repositories.py
│   ├── pathfinding.py
│   └── gameplay.py
├── annotators/              # Desenha overlays nas imagens
│   ├── repositories.py      # Monstros, HP bars, BL inset, status panel
│   ├── pathfinding.py       # Grid walkable, BFS heatmap, path
│   └── gameplay.py          # Decision badge, task sequence legend
├── screenshots/
│   ├── macos/               # Screenshots + .expected.json
│   ├── windows/
│   └── linux/
└── output/                  # Gitignored — imagens anotadas + JSON reports
```

## Como adicionar um novo screenshot

1. Capturar: `./venv/bin/python e2e/capture.py --os macos --name nome`
2. Revisar o `.discovered.json` gerado
3. Renomear para `.expected.json` ajustando valores se necessário
4. Rodar: `./venv/bin/python e2e/main.py --image nome`
5. Verificar que passa

## Formato do .expected.json

```json
{
  "description": "Cenário descrito aqui",
  "resolution": "1920x1080",
  "capture_method": "screen_capture",
  "capture_date": "2026-03-21",
  "tibia_client_version": null,

  "repositories": {
    "battlelist": {"count": 2, "names": ["Rotworm"], "attacking": "Rotworm"},
    "gamewindow": {"monster_count": 2, "max_false_positives": 0, "max_bar_noise": 3, "attacking": true},
    "radar": {"found": true},
    "statusbar": {"hp_range": [80, 100], "mana_range": [90, 100]},
    "skills": null,
    "actionbar": null,
    "inventory": null
  },

  "pathfinding": {
    "walkable_tile_count_range": [40, 80],
    "path_to_target_exists": true,
    "path_max_length": 10
  },

  "gameplay": {
    "context_overrides": {"cavebot": {"enabled": true}, "targeting": {"whitelist": ["Rotworm"]}},
    "decision": "attack",
    "target": "Rotworm",
    "task_sequence": ["AttackTask(Rotworm)"]
  }
}
```

- Campos `null` = módulo não testado nessa screenshot
- `attacking` na battlelist: nome da criatura (string) ou `null`
- `attacking` na gamewindow: `true`/`false`
- Ranges `[min, max]` para valores que variam

## O que cada módulo valida

| Módulo | Checks |
|--------|--------|
| battlelist | Contagem exata, nomes (set equality), detecção de ataque |
| gamewindow | Monstros >= esperado, FP <= max, bars <= max, ataque |
| radar | Coordenada encontrada |
| statusbar | HP e Mana dentro do range |
| skills | Food e Speed dentro do range |
| actionbar | Slots detectados |
| inventory | Depot aberto |
| pathfinding | Tiles walkable no range, path existe, comprimento do path |
| gameplay | Decisão correta, target correto, task sequence |

## Regression tracking

Compara automaticamente com o report anterior (`output/reports/latest.json`):
- **REGRESSION** — teste que passava agora falha
- **FIXED** — teste que falhava agora passa
- **NEW** — teste sem histórico

## Coverage warnings

Ao final da execução, lista monstros com templates em `src/repositories/` que não aparecem em nenhum `.expected.json`.

## Regras

- **OBRIGATÓRIO rodar após alterar**: `src/repositories/`, `src/gameplay/`, `src/core/`, `src/wiki/`
- Se o e2e quebrar, a alteração NÃO deve ser mergeada
- Zero reimplementação — tudo importa de `src/`
- Screenshots por OS porque o método de captura muda a coloração (Windows = capture card, macOS/Linux = screen capture)
- `reset_caches()` é chamado entre screenshots (radar/GW cacheiam posições UI)
