"""Screen overlay - transparent click-through window with pulsing green borders."""
import sys

if sys.platform == 'win32':
    from .controller_tk import OverlayControllerTk as OverlayController
    from .debug import DebugOverlayController
else:
    from .controller import OverlayController
    from .debug_macos import DebugOverlayController

__all__ = ['OverlayController', 'DebugOverlayController']
