# Testes

## Executar

```bash
./venv/bin/python -m pytest tests/ -v
./venv/bin/python -m pytest tests/<path>/test_<nome>.py -v
./venv/bin/python -m pytest tests/<path>/test_<nome>.py::TestClasse::test_metodo -v
```

## Estrutura

```
tests/
├── core/              # src/core/ (types, timing, cooldown)
├── gameplay/          # gameloop, targeting, pathfinding
│   └── tasks/         # tasks (cavebot, depot, refill, base, vector)
├── repositories/      # repositórios (battlelist, gamewindow, radar, statusbar)
│   └── radar/         # sub-testes de radar (friction)
└── test_optimizations.py
```

## Naming

- Arquivo: `test_<modulo>.py`
- Classe: `Test<Funcionalidade>` (ex: `TestDirection`, `TestBattleListSlotCounting`)
- Método: `test_<descricao>` — descreve cenário, não implementação
- Docstring obrigatória em cada classe e método de teste

## Filosofia dos Testes

- **Testar comportamento, não implementação** — se a interface pública funciona, o teste passa
- **Simples e direto** — sem frameworks de teste complexos, sem helpers genéricos demais
- **Cada teste é independente** — não depende de ordem de execução
- **Um conceito por teste** — se falhou, sabe exatamente o que quebrou
- **Sem overengineering nos testes** — 3 linhas de setup repetidas é melhor que uma fixture abstrata demais

## Context Mock Padrão

Criar helper no escopo do módulo (não em conftest.py):

```python
def create_mock_context():
    return {
        'screenshot': np.zeros((100, 100), dtype=np.uint8),
        'radar': {'coordinate': (32000, 32000, 7), 'previousCoordinate': None},
        'battleList': {'creatures': [], 'beingAttackedCreatureCategory': None},
        'gameWindow': {'monsters': [], 'players': [], 'creatures': [], 'monstersBars': []},
        'statusBar': {'hpPercentage': 100, 'manaPercentage': 100},
        'cavebot': {
            'enabled': False,
            'waypoints': {'items': [], 'currentIndex': 0},
            'closestCreature': None,
            'isAttackingSomeCreature': False,
        },
        'targeting': {'enabled': True, 'mode': 'all', 'whitelist': set(), 'blacklist': set()},
        'pause': False,
    }
```

Incluir apenas as chaves que o teste precisa. Context mínimo é melhor:

```python
# se o teste só checa cavebot, não precisa de statusBar
context = {'cavebot': {'isAttackingSomeCreature': False}}
```

## Padrões de Mock

### Objetos com muitos atributos — @dataclass

```python
@dataclass
class MockCreature:
    name: str
    x: int = 0
    y: int = 0
    width: int = 156
    height: int = 22
    creature_type: str = 'monster'
    is_being_attacked: bool = False
```

### Dependências externas — @patch

```python
@patch('pyautogui.keyDown')
@patch('pyautogui.click')
def test_alt_click_quando_tem_players(self, mock_click, mock_keydown):
    """Deve usar Alt+Click quando há players."""
    # decorators bottom-to-top: primeiro parâmetro = último decorator
    task.do(context)
    mock_keydown.assert_called_once_with('alt')
```

### Repository sem init completo

```python
repo = BattleListRepository.__new__(BattleListRepository)
repo.SLOT_HEIGHT = 22
repo.TEXT_PIXEL_VALUES = (192, 247)
```

### Screenshots e imagens

```python
screenshot = np.zeros((100, 100), dtype=np.uint8)           # grayscale
walkable = np.ones((11, 15), dtype=np.int32)                # 1=walkable, 0=blocked
bar = np.zeros(BAR_SIZE, dtype=np.uint8)                    # HP/mana bar
```

### Tasks para teste

```python
class ImmediateTask(BaseTask):
    """Task que completa imediatamente."""
    def __init__(self, name="ImmediateTask"):
        super().__init__(name)

    def did(self, context):
        return True

class CountingTask(BaseTask):
    """Task que conta chamadas."""
    def __init__(self, name="CountingTask"):
        super().__init__(name)
        self.do_count = 0

    def do(self, context):
        self.do_count += 1
        return context

    def did(self, context):
        return self.do_count >= 3
```

## Assertions

```python
# Valores simples
assert result == expected
assert len(creatures) == 3

# NumPy arrays
np.testing.assert_array_equal(result, expected)

# Mocks
mock_press.assert_called_once_with('f1')
mock_click.assert_not_called()

# Timing (com tolerância)
assert elapsed >= 0.09
assert elapsed < 0.2
```

## Estrutura de um Arquivo de Teste

```python
"""
Testes para <módulo>.

Ensures:
1. Funcionalidade X funciona
2. Edge cases retornam valores seguros
"""

import numpy as np
from unittest.mock import Mock, patch
from dataclasses import dataclass

@dataclass
class MockCreature:
    name: str
    x: int = 0
    y: int = 0

def create_mock_context():
    return {'cavebot': {'isAttackingSomeCreature': False}}

class TestMinhaFuncionalidade:
    """Testes para minha funcionalidade."""

    def test_retorna_vazio_quando_sem_dados(self):
        """Deve retornar lista vazia sem dados."""
        result = minha_funcao(None)
        assert result == []

    def test_processa_dados_validos(self):
        """Deve processar dados válidos corretamente."""
        result = minha_funcao(dados_validos)
        assert len(result) == 3
```

## O Que Testar

- **Funções puras**: input -> output (sem mocks)
- **Tasks**: lifecycle (NOT_STARTED -> RUNNING -> COMPLETED), should_ignore(), did()
- **Facades**: delegação correta para funções puras
- **Edge cases**: None, lista vazia, valores fora do range
- **Nunca**: implementação interna, métodos privados isolados, ordem de chamadas internas
