"""
Task System - PyTibia style hierarchical task execution.
"""
from .base import BaseTask, TaskState, Context
from .vector import VectorTask
from .orchestrator import TasksOrchestrator
from .common import (
    UseHotkeyTask,
    WalkTask,
    WalkToCoordinateTask,
    ClickTask,
)
from .cavebot import (
    ClickInClosestCreatureTask,
    WalkToTargetCreatureTask,
    AttackClosestCreatureTask,
    SpaceAttackTask,
    LootCorpseTask,
    SetNextWaypointTask,
    WalkToWaypointTask,
    UseRopeTask,
    UseShovelTask,
    UseLadderTask,
    CheckMonstersTask,
)
from .trap import AttackTrappedCreatureTask
from .use_hole import UseHoleTask
from .refill import (
    RefillCheckerTask,
    DepositGoldTask,
    RefillTask,
    RefillPotionsTask,
    DepositItemsTask,
    DropFlasksTask,
    SayTask,
    WaitTask,
)

__all__ = [
    # Base
    'BaseTask',
    'TaskState',
    'Context',
    'VectorTask',
    'TasksOrchestrator',

    # Common
    'UseHotkeyTask',
    'WalkTask',
    'WalkToCoordinateTask',
    'ClickTask',
    'WaitTask',

    # Cavebot
    'ClickInClosestCreatureTask',
    'WalkToTargetCreatureTask',
    'AttackClosestCreatureTask',
    'SpaceAttackTask',
    'LootCorpseTask',
    'SetNextWaypointTask',
    'WalkToWaypointTask',
    'UseRopeTask',
    'UseShovelTask',
    'UseLadderTask',
    'UseHoleTask',
    'CheckMonstersTask',

    # Anti-trap
    'AttackTrappedCreatureTask',

    # Refill
    'RefillCheckerTask',
    'DepositGoldTask',
    'RefillTask',
    'RefillPotionsTask',
    'DepositItemsTask',
    'DropFlasksTask',
    'SayTask',
]
