"""
GUI Tabs - Individual tab panels for the Tibia-Vision Bot GUI.
"""

from .bot_control import BotControlTab
from .healing import HealingTab
from .cavebot import CavebotTab
from .targeting import TargetingTab
from .spell_attack import SpellAttackTab
from .status import StatusTab
from .recorder import RecorderTab
from .hardware import HardwareTab
from .diagnostics import DiagnosticsTab
from .dashboard import DashboardPage

__all__ = [
    'BotControlTab', 'HealingTab', 'CavebotTab', 'TargetingTab',
    'SpellAttackTab', 'StatusTab', 'RecorderTab', 'HardwareTab',
    'DiagnosticsTab', 'DashboardPage',
]
