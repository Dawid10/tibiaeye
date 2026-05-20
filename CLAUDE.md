# TibiaEye - Bot de Automação para Tibia

Bot para Tibia desenvolvido em Python, inspirado no [PyTibia](https://github.com/lucasmonstro/PyTibia).

## Projetos Relacionados

| Projeto | Caminho | Descrição |
|---------|---------|-----------|
| **PyTibia** | `../PyTibia/` | Referência original do bot |
| **TibiaEye Web** | `../tibia-services/` | Monorepo Node.js — API + Dashboard + Landing |

O bot Python envia telemetria (kills, loot, XP, posição) para a API Node.js via HTTP e WebSocket.
O dashboard React consome esses dados em tempo real.
Ver `src/telemetry/CLAUDE.md` para detalhes da integração.

### Referência Principal: PyTibia

- **GitHub**: https://github.com/lucasmonstro/PyTibia

## Paradigma Funcional

O projeto prioriza o paradigma funcional seguindo o PyTibia:

- **Funções puras** no nível do módulo para lógica de negócio
- **Composição** via pipeline de middlewares (`Context -> Context`)
- **Sem mutação** desnecessária - context flui pelas funções
- **@njit (Numba)** para hot paths (BFS, bar detection, slot counting)
- **NumPy vetorizado** para operações em batch
- **Type aliases** em vez de herança desnecessária
- **Classes apenas** para tasks (estado necessário) e facades finas dos repositórios
- **Sem `else`** - usar early returns
- **Sem `if` aninhados** - extrair em funções helper
- **Sem comentários óbvios** - código auto-explicativo
- **Sem acronimos** em nomes de variáveis
- **Sem magic numbers** - tudo em `constants.py` ou `defaults.py`

```python
# ❌ ERRADO - OOP desnecessário
class CreatureDetector:
    def detect(self, image):
        if image is not None:
            if self.is_valid(image):
                return self._process(image)
            else:
                return None
        else:
            return None

# ✅ CORRETO - Funções puras com early return
def get_creatures_bars(game_window_image):
    if game_window_image is None:
        return []
    if not is_valid_image(game_window_image):
        return []
    return _detect_bars(game_window_image)
```

## Arquitetura

```
├── main.py                     # Entry point CLI (argparse)
├── gui.py                      # Entry point GUI (wrapper fino)
├── gui_config.json             # Estado persistido da GUI
├── src/
│   ├── core/                   # Tipos, configurações, constantes
│   │   ├── types.py            # Creature, CreatureType, HPColor, Direction, Coordinate
│   │   ├── screen.py           # Captura de tela otimizada
│   │   ├── constants.py        # Constantes técnicas (grid, delays, thresholds)
│   │   └── defaults.py         # Defaults configuráveis (healing, cavebot, refill)
│   │
│   ├── repositories/           # Extração de dados do jogo (funções puras + facade)
│   │   ├── battlelist/         # Detecção de criaturas (FarmHash64)
│   │   │   ├── core.py         # Funções puras + BattleListRepository facade
│   │   │   ├── config.py       # Imagens, hashes, constantes
│   │   │   ├── locators.py     # Localização de elementos UI
│   │   │   ├── extractors.py   # Extração de conteúdo
│   │   │   └── typings.py      # Type aliases (GrayImage, BBox)
│   │   │
│   │   ├── gamewindow/         # Detecção na game window
│   │   │   ├── __init__.py     # Facade + singleton (GameWindowRepository)
│   │   │   ├── core.py         # Template matching, posicionamento
│   │   │   ├── creatures.py    # Bar detection, pathfinding, creature ID (@njit)
│   │   │   └── config.py       # Constantes da game window
│   │   │
│   │   ├── radar/              # Coordenadas e navegação
│   │   │   ├── core.py         # get_coordinate(), funções puras
│   │   │   ├── config.py       # Floor images, hash tables
│   │   │   ├── friction.py     # Tile friction calculation
│   │   │   ├── locators.py     # Minimap location
│   │   │   └── extractors.py   # Coordinate extraction
│   │   │
│   │   ├── statusbar/          # HP/Mana detection (@njit)
│   │   │   ├── core.py         # get_hp_percentage(), get_mana_percentage()
│   │   │   ├── config.py       # Bar colors, sizes
│   │   │   ├── locators.py     # Bar location
│   │   │   └── extractors.py   # Pixel extraction
│   │   │
│   │   ├── skills/             # Food, speed, capacity, stamina (OCR de dígitos)
│   │   ├── inventory/          # Container/backpack detection
│   │   ├── actionBar/          # Action bar cooldowns
│   │   └── refill/             # Trade window detection
│   │
│   ├── gameplay/               # Lógica principal do bot
│   │   ├── gameloop.py         # GameLoop: middleware pipeline + task orchestrator
│   │   ├── context.py          # Context dict (estado global fluindo pelo pipeline)
│   │   ├── targeting.py        # TargetingFilter (whitelist/blacklist)
│   │   ├── stuck_detector.py   # Detecção de stuck
│   │   ├── resolvers.py        # Resolvers de waypoints
│   │   ├── cavebot/            # Navegação radar
│   │   │   └── radar.py        # handle_cavebot() - lógica de combate/navegação
│   │   └── core/
│   │       ├── waypoint.py     # Resolução de waypoints (funções puras)
│   │       └── tasks/          # Sistema de tarefas (único lugar com classes stateful)
│   │           ├── base.py     # BaseTask, TaskState
│   │           ├── vector.py   # VectorTask (composite)
│   │           ├── orchestrator.py  # TasksOrchestrator
│   │           ├── cavebot.py  # Attack, Loot, Waypoint tasks
│   │           ├── common.py   # Walk, Click, Hotkey tasks
│   │           ├── refill.py   # KeyPressTask, LazyVectorTask
│   │           ├── depot.py    # Depot operations
│   │           ├── trade.py    # Trade window tasks
│   │           └── use_hole.py # Rope/Shovel/Ladder
│   │
│   ├── healing/                # Sistema de auto-heal
│   │   ├── observers.py        # HealingObserver ABC, SpellHealingObserver, PotionObserver
│   │   └── cooldown.py         # CooldownManager
│   │
│   ├── gui/                    # Interface gráfica
│   │   ├── app.py              # TibiaVisionGUI
│   │   ├── config_manager.py   # Persistência gui_config.json
│   │   ├── tabs/               # Abas (bot_control, cavebot, healing, targeting, recorder, status)
│   │   └── components/         # Widgets (log_viewer, stat_bar, waypoint_list)
│   │
│   ├── utils/                  # Utilitários puros
│   │   ├── hash.py             # FarmHash64 wrappers
│   │   ├── keyboard.py         # Keyboard helpers
│   │   ├── input.py            # Mouse/click helpers
│   │   ├── timing.py           # Timer utilities
│   │   ├── alerts.py           # Alert system (stuck)
│   │   └── session_logger.py   # Session logging
│   │
│   └── wiki/                   # Base de conhecimento estática
│       ├── creatures.py        # Metadata de criaturas
│       ├── spells.py           # Dados de spells
│       ├── potions.py          # Dados de potions
│       ├── cities.py           # Coordenadas de cidades
│       └── misalignment.py     # Correção de misalignment por criatura
│
├── routes/                     # Rotas de hunt (JSON)
├── tests/                      # Testes automatizados (pytest)
└── captured_monsters/          # Templates de criaturas capturados
```

## Game Loop - Pipeline de Middlewares

O loop principal segue o padrão PyTibia: pipeline de funções puras transformando o context.

```
┌─────────────────────────────────────────┐
│           GameLoop.tick()               │
│   Context -> Middlewares -> Tasks       │
└──────────────────┬──────────────────────┘
                   │
    1. Middlewares (data extraction - Context -> Context)
    ├─ _screenshot_middleware    (freq: 1)  # Captura tela
    ├─ _statusbar_middleware     (freq: 1)  # HP/Mana
    ├─ _battlelist_middleware    (freq: 2)  # Criaturas
    ├─ _gamewindow_middleware    (freq: 2)  # Pathfinding
    ├─ _radar_middleware         (freq: 3)  # Coordenadas
    └─ _skills_middleware        (freq: 10) # Food/Speed
                   │
    2. handle_cavebot()         # Decide próxima ação
                   │
    3. orchestrator.do()        # Executa task ativa
                   │
    4. Healing observers        # Cura reativa
                   │
    5. Eat food / Check stuck   # Manutenção
```

Cada middleware é `Context -> Context`, frequência controlada para economia de CPU.

## Padrões dos Repositórios

Cada repositório segue a mesma estrutura funcional do PyTibia:

```
repository/
├── config.py       # Dados estáticos (imagens, hashes, constantes)
├── core.py         # Funções puras de negócio + facade class fina
├── locators.py     # Localização de elementos na tela
├── extractors.py   # Extração de dados da imagem
└── typings.py      # Type aliases
```

A facade class é fina - apenas delega para funções puras do módulo:

```python
# ❌ ERRADO - Lógica na classe
class BattleListRepository:
    def get_creatures(self, screenshot):
        # 100 linhas de lógica aqui...

# ✅ CORRETO - Funções puras, facade delega
def get_creatures(content, target_names=None):
    filled_slots = get_filled_slots_count(content)
    if filled_slots == 0:
        return []
    names = get_creatures_names(content, filled_slots)
    return _build_creature_list(names, content)

class BattleListRepository:
    def get_creatures(self, screenshot, target_names=None):
        content = get_content(screenshot)
        return get_creatures(content, target_names)
```

## Sistema de Tasks

Único lugar onde classes stateful são necessárias (tarefas têm ciclo de vida):

```
BaseTask                    # Lifecycle: NOT_STARTED -> RUNNING -> COMPLETED
├── KeyPressTask            # Pressiona uma tecla
├── VectorTask              # Composite de sub-tasks
│   └── LazyVectorTask      # Cria sub-tasks no on_before_start()
├── WalkTask                # Walk com step + direction
└── WalkToCoordinateTask    # Walk com pathfinding
```

```python
class MyTask(LazyVectorTask):
    def __init__(self):
        super().__init__("MyTask")

    def create_tasks(self, context):
        self.add_task(SayTask('hi'))
        self.add_task(WaitTask(WAIT_NPC_RESPONSE))
```

## Otimizações de Performance

### Numba @njit (hot paths)

```python
@njit(cache=True, fastmath=True)
def _has_matrix_inside_other(matrix, other):
    # C-level performance para comparação de matrizes
    ...

@njit(cache=True)
def _bfs_flood_fill_jit(walkable, start_y, start_x, ...):
    # BFS pathfinding JIT-compilado
    ...

@njit(cache=True)
def _count_filled_slots_jit(content, slot_height, ...):
    # Contagem de slots 2-4x mais rápido
    ...
```

### Frequência de Middlewares

Nem todo middleware precisa rodar todo tick:

```python
FREQ_SCREENSHOT = 1    # Cada tick
FREQ_STATUSBAR = 1     # Cada tick (crítico pra heal)
FREQ_BATTLELIST = 2    # Cada 2 ticks
FREQ_GAMEWINDOW = 2    # Cada 2 ticks
FREQ_RADAR = 3         # Cada 3 ticks
FREQ_SKILLS = 10       # Cada 10 ticks
```

### Tick Rate Adaptativo

```python
TICK_RATE_COMBAT = 0.080   # 80ms em combate
TICK_RATE_DEFAULT = 0.100  # 100ms normal
TICK_RATE_IDLE = 0.150     # 150ms idle
TICK_RATE_PAUSED = 0.500   # 500ms pausado
```

## Constantes vs Defaults

| Arquivo | Conteúdo |
|---------|----------|
| `src/core/constants.py` | Constantes técnicas (grid, delays, thresholds, frequências) |
| `src/core/defaults.py` | Defaults configuráveis pelo usuário (healing, cavebot, refill) |
| `gui_config.json` | Estado persistido da GUI (sobrescreve defaults) |

```python
# constants.py - nunca muda em runtime
DELAY_HOTKEY = 0.1
GRID_WIDTH = 15
CONFIDENCE_CREATURE = 0.63

# defaults.py - valores padrão que o usuário pode alterar pela GUI
DEFAULT_CONFIG = {
    "healing": {"healthPotion": {"threshold": 30, "hotkey": "1"}},
    "general": {"tickRate": 0.100, "stuckAlertTimeout": 120},
}
```

## Testes

```bash
./venv/bin/python -m pytest tests/ -v

# Específicos
./venv/bin/python -m pytest tests/repositories/test_battlelist.py -v
./venv/bin/python -m pytest tests/gameplay/test_gameloop.py -v
./venv/bin/python -m pytest tests/gameplay/tasks/test_refill_tasks.py -v
```

### E2E Tests — Source of Truth (OBRIGATÓRIO)

O framework `e2e/` é o **source of truth** do projeto. Ele testa o pipeline completo contra screenshots reais do jogo: repositories (BL, GW, Radar, StatusBar, Skills, ActionBar, Inventory), pathfinding (BFS, walkable grid), gameplay (handle_cavebot, targeting, task sequence) e detecção de attack/stuck/trap.

**REGRA: rodar `python e2e/main.py` após qualquer alteração em:**
- `src/repositories/` — qualquer mudança em detecção visual, hashes, templates, locators
- `src/gameplay/` — qualquer mudança em cavebot, targeting, tasks, pathfinding, stuck/trap detection
- `src/core/` — mudanças em types, constants, defaults que afetam o pipeline
- `src/wiki/` — mudanças em creature metadata, spells, misalignment

Se o e2e quebrar, a alteração **NÃO** deve ser mergeada. Corrigir o código ou atualizar as expectations (se o novo comportamento estiver correto).

```bash
# Rodar todos os e2e tests (todos os OS)
python e2e/main.py

# Rodar apenas um OS
python e2e/main.py --os macos

# Rodar imagem específica
python e2e/main.py --image rotworm

# Verbose (mostra diagnósticos detalhados)
python e2e/main.py --verbose

# Adicionar novo screenshot (captura ao vivo)
python e2e/capture.py --os macos

# Adicionar screenshot existente
python e2e/capture.py --file ~/screenshot.png --os macos
```

**Ao criar ou modificar qualquer detecção:**
1. Rodar `python e2e/main.py` — garantir que nada quebrou
2. Se cenário novo, capturar screenshot com `e2e/capture.py`
3. Revisar o `.discovered.json` gerado e salvar como `.expected.json`
4. Validar que o teste passa

**Screenshots por OS** (método de captura muda a coloração):
- `e2e/screenshots/macos/` — screen capture nativo
- `e2e/screenshots/windows/` — capture card (Tibia bloqueia screenshots)
- `e2e/screenshots/linux/` — screen capture nativo

Ver `e2e/CLAUDE.md` para detalhes completos do framework.

## Dependências

- `opencv-python` - Processamento de imagem (template matching)
- `numpy` - Operações matriciais vetorizadas
- `pyautogui` - Automação mouse/teclado
- `pyfarmhash` - Hash O(1) para creature names
- `numba` (opcional) - JIT para BFS, bar detection, slot counting

## Filosofia: Simplicidade Acima de Tudo

O código deve ser simples, direto e fácil de manter. Sem overengineering.

- **Função faz uma coisa** — se precisa de comentário explicando, está complexa demais
- **Sem abstrações prematuras** — 3 linhas repetidas é melhor que uma abstração desnecessária
- **Sem wrappers que só delegam** — se não adiciona lógica, não crie
- **Sem generalizações especulativas** — resolva o problema de hoje, não o de amanhã
- **Sem try/except genérico** — só trate erros que realmente podem acontecer
- **Sem type hints verbosos** — use quando clarifica, omita quando óbvio
- **Complexidade mínima** — a solução mais simples que funciona é a correta

```python
# ❌ ERRADO - overengineering
class CreatureFilterFactory:
    @staticmethod
    def create(mode: str) -> 'BaseFilter':
        filters = {"whitelist": WhitelistFilter, "blacklist": BlacklistFilter}
        return filters[mode]()

# ✅ CORRETO - função direta
def filter_creatures(creatures, whitelist=None, blacklist=None):
    if whitelist:
        return [c for c in creatures if c.name in whitelist]
    if blacklist:
        return [c for c in creatures if c.name not in blacklist]
    return creatures
```

## Como Adicionar um Novo Monstro

O bot precisa de templates para detectar criaturas em dois sistemas independentes:

| Sistema | Diretório | Formato | Uso |
|---------|-----------|---------|-----|
| **BattleList** | `src/repositories/battlelist/images/monsters/` | Grayscale `11x131` | Hash O(1) lookup do nome na Battle List |
| **GameWindow** | `src/repositories/gamewindow/images/monsters/` | Grayscale `13xW` | Template matching do nome acima da HP bar |

### Script de captura

```bash
# A partir de um screenshot salvo:
./venv/bin/python scripts/capture_monster_templates.py <screenshot.png>

# Captura ao vivo da tela:
./venv/bin/python scripts/capture_monster_templates.py --live
```

O script localiza a Battle List e a Game Window, extrai os nomes e pede confirmação antes de salvar.

### Captura manual (quando o script não funciona)

Se os monstros estão aglomerados na GW (nomes sobrepostos), capture com **1 monstro** sozinho na tela:

1. **BL template** — extraído automaticamente do slot na Battle List (sempre funciona)
2. **GW template** — extraído da região acima da HP bar na Game Window (precisa do monstro isolado)

### Colisão de hash

Nomes longos truncados na Battle List (ex: "Muglex Clan Footm..." e "Muglex Clan Assas...") podem produzir o mesmo hash normalizado. O sistema detecta colisões em `build_name_hash_table()` e força template matching fallback para esses casos. Hashes colididos não são salvos em `learned_hashes.json`.

### Validação

Após capturar, criar teste e2e:
1. Salvar screenshot em `e2e-test-images/monsters/<nome>.png`
2. Adicionar expectations em `e2e-test-images/main.py`
3. Rodar: `python e2e-test-images/main.py --image <nome>`

## Como Criar uma Nova Feature

### Novo Repositório
1. Criar pasta `src/repositories/<nome>/` com: `config.py`, `core.py`, `locators.py`, `extractors.py`, `typings.py`
2. Lógica fica em funções puras no módulo — facade class só delega
3. Criar testes em `tests/repositories/test_<nome>.py`
4. Se precisa rodar no pipeline, adicionar middleware em `gameloop.py`
5. Ver `src/repositories/CLAUDE.md` para detalhes

### Nova Task
1. Herdar de `BaseTask` (simples), `VectorTask` (sequência fixa) ou `LazyVectorTask` (sequência dinâmica)
2. Implementar `do(context)` e opcionalmente `did(context)`, `should_ignore(context)`
3. Criar testes em `tests/gameplay/tasks/test_<nome>.py`
4. Ver `src/gameplay/core/tasks/CLAUDE.md` para detalhes

### Nova Tab na GUI
1. Criar `src/gui/tabs/<nome>.py` herdando de `ctk.CTkScrollableFrame`
2. Receber `config_manager` no construtor, implementar `get_settings()`
3. Registrar em `src/gui/app.py`
4. Ver `src/gui/CLAUDE.md` para detalhes

## Como Criar Testes

- Arquivo: `tests/<modulo>/test_<nome>.py`
- Classes: `class Test<Funcionalidade>:`
- Funções: `def test_<descricao_do_cenario>(self):` com docstring
- Mock context com helper `create_mock_context()` no escopo do módulo
- `@dataclass` para mock objects complexos, `Mock()` para dependências
- NumPy arrays para screenshots: `np.zeros((h, w), dtype=np.uint8)`
- Ver `tests/CLAUDE.md` para detalhes

## Erros Comuns (evitar)

- **Imports circulares**: `src/core/` nunca importa de `src/repositories/` ou `src/gameplay/`
- **Lógica na facade**: toda lógica fica em funções puras no nível do módulo
- **Usar `else`**: sempre early return
- **`if` aninhados**: extrair em funções helper
- **Magic numbers**: usar `constants.py` ou `defaults.py`
- **pyautogui em repositories**: repositories só extraem dados, nunca agem
- **Mutar context sem retornar**: middlewares e tasks sempre `return context`
- **Esquecer fallback**: sempre `context.get('key', {}).get('subkey', default)`
- **Classes desnecessárias**: classes só para tasks e facades — resto é função pura
- **Overengineering**: sem factories, sem builders, sem abstrações para um único uso
