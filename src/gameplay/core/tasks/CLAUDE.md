# Tasks

Único lugar do projeto onde classes stateful são necessárias (tasks têm ciclo de vida).
Mesmo assim, manter simples: herdar, implementar 2-3 métodos, pronto.

## Quando Usar Cada Base

| Base | Quando | Exemplo |
|------|--------|---------|
| `BaseTask` | Ação única e simples | Pressionar tecla, clicar, esperar |
| `VectorTask` | Sequência fixa de sub-tasks | Walk + Walk + SetNextWaypoint |
| `LazyVectorTask` | Sequência que depende do context | Refill (cria steps com base no que falta) |

## Lifecycle

```
NOT_STARTED → on_before_start() → RUNNING → did()==True → COMPLETED
                                     ↓ timeout
                                  TIMED_OUT
```

## Métodos para Sobrescrever

Implementar apenas o que precisa. Não sobrescrever método se o default serve.

```python
# Sempre necessário:
do(context) -> Context       # Ação executada ao entrar em RUNNING

# Quando a task não completa imediatamente:
did(context) -> bool         # True = completou (default: True = completa imediato)

# Quando precisa pular a task em certas condições:
should_ignore(context) -> bool  # True = pula (default: False)

# Quando precisa de ação contínua cada frame:
ping(context) -> Context     # Chamado cada frame enquanto RUNNING

# Raramente necessários:
should_restart(context) -> bool
on_before_start(context) -> Context
on_complete(context) -> Context
on_timeout(context) -> Context
```

## Timing (setar no `__init__`)

```python
self.delay_before_start = 0.5   # Espera antes de do()
self.delay_after_complete = 0.1  # Espera depois de did()==True
self.delay_of_timeout = 2.0     # Timeout (0 = sem timeout)
```

## Task Simples (BaseTask)

```python
from .base import BaseTask, Context

class UseHotkeyTask(BaseTask):
    def __init__(self, hotkey):
        super().__init__(f"UseHotkey({hotkey})")
        self.hotkey = hotkey
        self.delay_after_complete = DELAY_HOTKEY

    def do(self, context):
        pyautogui.press(self.hotkey)
        return context
    # did() default retorna True → completa imediato
```

## Task com Condição (BaseTask)

```python
class ClickCreatureTask(BaseTask):
    def __init__(self):
        super().__init__("ClickCreature")
        self.delay_of_timeout = 2.0

    def should_ignore(self, context):
        return context.get('cavebot', {}).get('isAttackingSomeCreature', False)

    def do(self, context):
        creature = context.get('cavebot', {}).get('closestCreature')
        if creature is None:
            return context
        pyautogui.click(*creature.window_coordinate)
        return context

    def did(self, context):
        return context.get('cavebot', {}).get('isAttackingSomeCreature', False)
```

## Sequência Fixa (VectorTask)

```python
from .vector import VectorTask

class MinhaSequencia(VectorTask):
    def __init__(self):
        super().__init__("MinhaSequencia", tasks=[
            UseHotkeyTask("f1"),
            WalkTask("north"),
            UseHotkeyTask("f2"),
        ])
```

## Sequência Dinâmica (LazyVectorTask)

```python
from .vector import LazyVectorTask

class RefillTask(LazyVectorTask):
    def __init__(self):
        super().__init__("Refill")

    def create_tasks(self, context):
        hp = context.get('statusBar', {}).get('hpPercentage', 100)
        if hp < 50:
            self.add_task(UseHotkeyTask("f1"))
        self.add_task(WalkTask("south"))
```

## Acesso ao Context

Sempre usar `.get()` com defaults para não quebrar:

```python
creatures = context.get('battleList', {}).get('creatures', [])
hp = context.get('statusBar', {}).get('hpPercentage', 100)
is_attacking = context.get('cavebot', {}).get('isAttackingSomeCreature', False)
coordinate = context.get('radar', {}).get('coordinate')

# Logger (pode ser None)
gui_logger = context.get('gui_logger')
if gui_logger:
    gui_logger("Mensagem", "info")
```

## Tasks Existentes (referência)

- `cavebot.py` — ClickInClosestCreatureTask (should_ignore + did com condição)
- `common.py` — WalkTask (ping contínuo, did com coordinate check)
- `refill.py` — KeyPressTask (simples), LazyVectorTask (dinâmica)
- `depot.py` — operações compostas de depot

## Evitar

- **Task que faz tudo**: quebrar em sub-tasks menores via VectorTask
- **Estado desnecessário**: se não precisa de estado entre frames, é função pura (não task)
- **Herança profunda**: máximo 1 nível (BaseTask → MinhaTask ou VectorTask → MinhaSequencia)
- **Métodos auxiliares demais na task**: se a lógica é complexa, extrair para função pura no módulo
