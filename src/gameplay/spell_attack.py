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

from ..core.types import CreatureType

from ..core.constants import (
    MANTRA_ATTACK_PREHOLD, SPELL_ATTACK_DIAG_INTERVAL,
    SPELL_ATTACK_GROUP_COOLDOWN_ATTACK,
    SPELL_ATTACK_GROUP_COOLDOWN_SUPPORT,
    SPELL_ATTACK_MIN_CAST_INTERVAL,
)


def handle_mantra(context, cooldowns) -> bool:
    """
    Monk mantra: press its hotkey when the indicator pixel is lit, in battle, cavebot on.

    Returns True when attack spells must wait this tick: the mantra was just cast, or it is lit and
    comes off its own cooldown within MANTRA_ATTACK_PREHOLD. A flickering indicator can't extend the
    wait (the old "lit since" timer restarted on every flicker and starved attack spells all fight).
    """
    from ..repositories.combat_mode import is_pixel_lit
    from ..utils.input import get_screen_offset

    mantra = context.get('spellAttack', {}).get('mantra', {})
    if not mantra.get('enabled', False) or not mantra.get('hotkey'):
        return False
    if not context.get('cavebot', {}).get('enabled', False):
        return False  # healing-only runs never spend mantra
    if not context.get('battleList', {}).get('creatures'):
        return False
    screenshot_bgr = context.get('screenshotBgr')
    if screenshot_bgr is None:
        return False

    offset_x, offset_y = get_screen_offset()
    x, y = mantra.get('pixelX', 0) - offset_x, mantra.get('pixelY', 0) - offset_y
    if not is_pixel_lit(screenshot_bgr, x, y, mantra.get('pixelColor', [0, 0, 0]), mantra.get('tolerance', 50)):
        return False

    now = time.time()
    remaining = mantra.get('cooldown', 2.0) - (now - cooldowns.get('mantra', 0))
    if remaining > 0:
        if remaining <= MANTRA_ATTACK_PREHOLD:
            _log_skip(cooldowns, f"waiting {remaining:.1f}s for the mantra")
            return True
        return False

    pyautogui.press(mantra['hotkey'])
    cooldowns['mantra'] = now
    print(f"[Mantra] Indicator lit - pressing {mantra['hotkey'].upper()}")
    return True


def handle_spell_attack(context, cooldowns):
    """
    Main entry point. Called every tick from gameloop.

    Args:
        context: Game context dict.
        cooldowns: Dict {key: timestamp} tracking last use times.

    Returns:
        Updated context dict.
    """
    if _should_skip(context, cooldowns):
        return context

    spell_attack = context.get('spellAttack', {})
    groups = spell_attack.get('groups', [])
    mana_reserve = spell_attack.get('manaReservePercent', 30)

    group = _find_matching_group(groups, context)
    if group is None:
        _log_skip(cooldowns, f"no spell group matches (monsters next to you: "
                             f"{_get_creature_count(context, 'nearest')}, on screen: {_get_creature_count(context, 'total')})")
        return context

    spells = group.get('spells', [])
    spell = _select_spell(spells, cooldowns)
    if spell is None:
        return context

    if not _has_enough_mana(context, spell, mana_reserve):
        mana = context.get('statusBar', {}).get('manaPercentage', 100)
        _log_skip(cooldowns, f"mana {mana:.0f}% is below the {mana_reserve}% reserve")
        return context

    _cast_spell(spell, cooldowns)
    _log_cast(context, spell.get('name', ''), group.get('name', ''),
              _get_creature_count(context, group.get('countMode', 'nearest')))

    context['spellAttack']['lastCastSpell'] = spell.get('name')
    context['spellAttack']['lastCastTime'] = time.time()

    return context


def _log_skip(cooldowns, reason):
    """Why no attack spell went out - at most once per SPELL_ATTACK_DIAG_INTERVAL."""
    now = time.time()
    key = 'diag:' + reason.split('(')[0].split(' 0')[0][:30]  # one timer per kind of reason
    if now - cooldowns.get(key, 0) < SPELL_ATTACK_DIAG_INTERVAL:
        return
    cooldowns[key] = now
    print(f"[SpellAttack] not casting: {reason}")


def _should_skip(context, cooldowns=None):
    """Skip if disabled, cavebot off, not fighting, or no monster in the battle list / on screen."""
    cooldowns = {} if cooldowns is None else cooldowns
    spell_attack = context.get('spellAttack', {})
    if not spell_attack.get('enabled', False):
        return True

    if not context.get('cavebot', {}).get('enabled', False):
        return True  # healing-only runs never press attack keys (same rule as the mantra)

    # Only once the bot is fighting: casting before it picked a target covered the monster's health bar
    # with spell effects, so it saw no monster and walked off. The red square alone is often missed mid-fight.
    cavebot = context.get('cavebot', {})
    if not cavebot.get('isAttackingSomeCreature', False) and not cavebot.get('inAttackTask', False):
        _log_skip(cooldowns, "not attacking yet")
        return True

    if not _battle_list_monster_count(context) and not context.get('gameWindow', {}).get('monsters'):
        return True

    return False


def _battle_list_monster_count(context):
    """Monsters by name in the battle list - reliable even when screen text hides health bars."""
    creatures = context.get('battleList', {}).get('creatures', [])
    return sum(1 for c in creatures if getattr(c, 'creature_type', None) == CreatureType.MONSTER)


def _get_creature_count(context, count_mode):
    """Get creature count based on mode.

    'nearest' uses get_nearest_creatures_count (creatures within 1 sqm of player).
    'total' uses the monster count from the battle list (or game screen, whichever is higher).
    """
    monsters = context.get('gameWindow', {}).get('monsters', [])

    if count_mode == 'total':
        return max(len(monsters), _battle_list_monster_count(context))

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
