"""
Spell Attack - priority-based offensive spell casting.

Pure functions called directly in the game loop tick, between the task
orchestrator (step 3) and healing observers (step 4). Casts the highest
priority spell that is off cooldown and affordable.

Groups are evaluated in order — first matching group wins. Within a group,
spells are tried in priority order (list index 0 = highest priority).

Cooldowns are tracked as a simple dict {key: timestamp} to avoid
depending on the healing module.
"""
import time
import pyautogui

from ..core.constants import (
    SPELL_ATTACK_GROUP_COOLDOWN_ATTACK,
    SPELL_ATTACK_GROUP_COOLDOWN_SUPPORT,
    SPELL_ATTACK_MIN_CAST_INTERVAL,
)


def handle_spell_attack(context, cooldowns):
    """
    Main entry point. Called every tick from gameloop.

    Args:
        context: Game context dict.
        cooldowns: Dict {key: timestamp} tracking last use times.

    Returns:
        Updated context dict.
    """
    if _should_skip(context):
        return context

    spell_attack = context.get('spellAttack', {})
    groups = spell_attack.get('groups', [])
    mana_reserve = spell_attack.get('manaReservePercent', 30)

    group = _find_matching_group(groups, context)
    if group is None:
        return context

    spells = group.get('spells', [])
    spell = _select_spell(spells, cooldowns)
    if spell is None:
        return context

    if not _has_enough_mana(context, spell, mana_reserve):
        return context

    _cast_spell(spell, cooldowns)
    _log_cast(context, spell.get('name', ''), group.get('name', ''),
              _get_creature_count(context, group.get('countMode', 'nearest')))

    context['spellAttack']['lastCastSpell'] = spell.get('name')
    context['spellAttack']['lastCastTime'] = time.time()

    return context


def _should_skip(context):
    """Skip if disabled, not attacking, or no monsters."""
    spell_attack = context.get('spellAttack', {})
    if not spell_attack.get('enabled', False):
        return True

    if not context.get('cavebot', {}).get('isAttackingSomeCreature', False):
        return True

    monsters = context.get('gameWindow', {}).get('monsters', [])
    if not monsters:
        return True

    return False


def _get_creature_count(context, count_mode):
    """Get creature count based on mode.

    'nearest' uses get_nearest_creatures_count (creatures within 1 sqm of player).
    'total' uses total visible monster count.
    """
    monsters = context.get('gameWindow', {}).get('monsters', [])

    if count_mode == 'total':
        return len(monsters)

    # Default: nearest — count monsters in surrounding 8 tiles
    from ..repositories.gamewindow import get_nearest_creatures_count
    return get_nearest_creatures_count(monsters)


def _match_condition(condition, value, creature_count):
    """Check if creature_count satisfies the condition."""
    if condition == 'lessThan':
        return creature_count < value
    if condition == 'lessThanOrEqual':
        return creature_count <= value
    if condition == 'greaterThan':
        return creature_count > value
    if condition == 'greaterThanOrEqual':
        return creature_count >= value
    return False


def _find_matching_group(groups, context):
    """Find first enabled group whose creature condition matches."""
    for group in groups:
        if not group.get('enabled', True):
            continue

        condition = group.get('compare', 'greaterThanOrEqual')
        value = group.get('value', 1)
        count_mode = group.get('countMode', 'nearest')
        creature_count = _get_creature_count(context, count_mode)

        if _match_condition(condition, value, creature_count):
            return group

    return None


def _select_spell(spells, cooldowns):
    """Select the first spell (priority order) that is off cooldown."""
    for spell in spells:
        if not spell.get('enabled', True):
            continue
        if _can_cast(spell, cooldowns):
            return spell
    return None


def _can_cast(spell, cooldowns):
    """Check global interval, individual cooldown, and group cooldown."""
    now = time.time()

    if not _cooldown_ready(cooldowns, 'spell_attack:global', SPELL_ATTACK_MIN_CAST_INTERVAL, now):
        return False

    name = spell.get('name', '')
    individual_cooldown = spell.get('cooldown', 2.0)
    if not _cooldown_ready(cooldowns, f'spell:{name}', individual_cooldown, now):
        return False

    group = spell.get('spellGroup', 'attack')
    group_cd = (SPELL_ATTACK_GROUP_COOLDOWN_ATTACK if group == 'attack'
                else SPELL_ATTACK_GROUP_COOLDOWN_SUPPORT)
    if not _cooldown_ready(cooldowns, f'group:{group}', group_cd, now):
        return False

    return True


def _cooldown_ready(cooldowns, key, duration, now):
    """Check if a cooldown has expired."""
    last_use = cooldowns.get(key, 0)
    return (now - last_use) >= duration


def _has_enough_mana(context, spell, mana_reserve):
    """Check mana percentage >= reserve.

    Note: statusBar.mana (absolute value) is NOT populated by the middleware,
    only manaPercentage is available. So we only check the percentage-based reserve.
    """
    mana_percent = context.get('statusBar', {}).get('manaPercentage', 100)

    if mana_percent < mana_reserve:
        return False

    return True


def _cast_spell(spell, cooldowns):
    """Press the spell hotkey and record all cooldowns."""
    hotkey = spell.get('hotkey', '')
    if not hotkey:
        return

    pyautogui.press(hotkey)

    now = time.time()
    name = spell.get('name', '')
    group = spell.get('spellGroup', 'attack')

    cooldowns['spell_attack:global'] = now
    cooldowns[f'spell:{name}'] = now
    cooldowns[f'group:{group}'] = now


def _log_cast(context, spell_name, group_name, creature_count):
    """Log the cast via gui_logger if available."""
    message = f"[SpellAttack] Cast '{spell_name}' (group: {group_name}, creatures: {creature_count})"
    gui_logger = context.get('gui_logger')
    if gui_logger:
        gui_logger(message, 'info')
    else:
        print(message)
