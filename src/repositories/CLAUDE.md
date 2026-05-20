# Repositórios

Repositórios extraem dados do jogo. Seguem programação funcional: funções puras fazem o trabalho, facade class só organiza.

## Estrutura de um Novo Repositório

```
src/repositories/<nome>/
├── __init__.py     # Exporta facade class
├── config.py       # Constantes, paths, imagens de referência
├── core.py         # Funções puras + facade class fina
├── locators.py     # Encontra elementos na tela (retorna BBox ou None)
├── extractors.py   # Recorta e retorna sub-imagem de uma região
└── typings.py      # Type aliases (GrayImage = np.ndarray)
```

## Regra Principal

Toda lógica em funções puras no nível do módulo. Facade class é fina — só delega.

```python
# core.py

# ===== FUNÇÕES PURAS (aqui fica a lógica) =====

def get_filled_count(content, slot_height, start_y):
    """Função pura: recebe dados, retorna resultado."""
    if content is None:
        return 0
    return _count_slots(content, slot_height, start_y)

def get_name_by_hash(content, slot_index, name_hashes):
    """O(1) lookup por hash."""
    row = content[_get_slot_y(slot_index), :]
    return name_hashes.get(hashit(row))

# ===== FACADE FINA (só delega) =====

class MyRepository:
    def __init__(self):
        self._screen = get_screen_capture()
        self._hashes = load_hashes(HASHES_PATH)

    def get_data(self, screenshot=None):
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)
        content = get_content(screenshot)       # extractors.py
        return get_filled_count(content, self.SLOT_HEIGHT, self.START_Y)
```

```python
# ❌ ERRADO - lógica dentro da classe
class MyRepository:
    def get_data(self, screenshot):
        content = self._extract(screenshot)
        for i in range(len(content)):
            if content[i] > self.threshold:
                # 50 linhas de lógica...

# ❌ ERRADO - overengineering
class BaseRepository(ABC):
    @abstractmethod
    def extract(self): ...
    @abstractmethod
    def process(self): ...

class MyRepository(BaseRepository):
    def extract(self): ...
    def process(self): ...

# ✅ CORRETO - funções puras, facade delega
def process_data(content, threshold):
    if content is None:
        return []
    return [item for item in content if item > threshold]

class MyRepository:
    def get_data(self, screenshot=None):
        content = get_content(screenshot)
        return process_data(content, THRESHOLD)
```

## Responsabilidades

| Arquivo | Faz | Nunca faz |
|---------|-----|-----------|
| `config.py` | Carrega imagens, define constantes, paths | Lógica de negócio |
| `locators.py` | Acha posição de elementos na tela | Interpreta dados |
| `extractors.py` | Recorta região, retorna sub-imagem | Lógica de negócio |
| `core.py` | Funções puras + facade fina | Captura tela diretamente |

## Repositórios Existentes (referência)

- `statusbar/` — mais simples, bom template para começar
- `battlelist/` — mais completo, hash + template matching fallback
- `radar/` — coordinate extraction + friction
- `gamewindow/` — singleton, template matching

## Integração com Game Loop

Após criar o repositório, adicionar middleware em `src/gameplay/gameloop.py`:

```python
def _meu_middleware(self, context):
    data = self._meu_repo.get_data(context['screenshot'])
    context['meuDado'] = data
    return context
```

Registrar com frequência adequada (1=cada tick, 2=cada 2 ticks, etc).
Dados críticos (HP/mana) = freq 1. Dados lentos (skills) = freq 10.
