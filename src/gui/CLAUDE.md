# GUI

Interface gráfica com CustomTkinter. Bot roda em thread separada, GUI na main thread.

## Adicionar Nova Tab

### 1. Criar `src/gui/tabs/<nome>.py`

```python
import customtkinter as ctk

class MinhaTab(ctk.CTkScrollableFrame):
    def __init__(self, master, config_manager=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.config_manager = config_manager
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        section = self._create_section("Titulo")
        section.pack(fill="x", padx=5, pady=5)
        # widgets dentro da section...

    def _create_section(self, title):
        section = ctk.CTkFrame(self, fg_color="#16213e", corner_radius=8)
        header = ctk.CTkLabel(section, text=title, font=ctk.CTkFont(size=13, weight="bold"))
        header.pack(fill="x", padx=10, pady=(8, 0))
        return section

    def _load_config(self):
        if self.config_manager:
            self.valor = self.config_manager.get('minha_tab.setting', 'default')

    def _save_config(self):
        if self.config_manager:
            self.config_manager.set('minha_tab.setting', self.valor)
            self.config_manager.save()

    def get_settings(self):
        return {'setting': self.valor}
```

### 2. Exportar em `src/gui/tabs/__init__.py`

```python
from .minha_tab import MinhaTab
```

### 3. Registrar em `src/gui/app.py`

```python
self.tabview.add("Minha Tab")
self.minha_tab = MinhaTab(
    self.tabview.tab("Minha Tab"),
    config_manager=self.config_manager
)
self.minha_tab.pack(fill="both", expand=True)
```

## ConfigManager

Dot notation para ler/escrever configurações persistidas em `gui_config.json`:

```python
config_manager.get('general.tickRate')           # leitura
config_manager.set('general.tickRate', 0.080)    # escrita
config_manager.save()                            # persiste no arquivo
```

## Binding Widget -> Config

```python
self.var = ctk.StringVar(value=str(self.config_manager.get('key', default)))
self.var.trace_add("write", self._on_change)

def _on_change(self, *args):
    self.config_manager.set('key', self.var.get())
    self.config_manager.save()
```

## Componentes Reutilizáveis (`src/gui/components/`)

- `LogViewer` — log em tempo real com queue thread-safe
- `StatBar` — barra HP/MP/CPU com cores por threshold (`bar_type`: "hp", "mp", "cpu", "memory")
- `WaypointList` — editor de waypoints

Usar diretamente, sem wrappers:

```python
from ..components import LogViewer, StatBar

self.log = LogViewer(parent)
self.log.pack(fill="both", expand=True)

self.hp_bar = StatBar(parent, label="HP", bar_type="hp")
self.hp_bar.pack(fill="x", padx=5)
```

## Thread Safety

- Bot roda em thread separada da GUI
- Logging: bot envia via `gui_logger` callback (queue interna no LogViewer)
- Nunca acessar widgets CustomTkinter de outra thread
