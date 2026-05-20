"""
Pre-flight Validation - Checks before starting the bot.

Each check returns (passed: bool, message: str).
Critical checks block startup; optional checks show warnings.
"""


def check_screen_capture():
    """Check if screen capture is working."""
    try:
        from src.core import get_screen_capture
        screen = get_screen_capture()
        img = screen.capture()
        if img is None:
            return False, "Captura de tela falhou. Verifique se a janela do Tibia esta visivel."
        return True, "Captura de tela OK"
    except Exception as e:
        return False, f"Erro na captura de tela: {e}"


def check_battlelist(screenshot_gray):
    """Check if battle list is detected in the screenshot."""
    try:
        from src.repositories.battlelist import BattleListRepository
        repo = BattleListRepository()
        if repo.is_detected:
            return True, "Battle List detectada"
        return False, "Battle List nao detectada. Abra o Battle List no jogo."
    except Exception as e:
        return False, f"Erro ao verificar Battle List: {e}"


def check_radar(screenshot_gray):
    """Check if radar coordinates can be read."""
    try:
        from src.repositories.radar import get_coordinate
        coord = get_coordinate(screenshot_gray)
        if coord is None:
            return False, "Radar nao legivel. Verifique o zoom do minimapa (sem zoom in/out)."
        return True, f"Radar OK (posicao: {coord[0]}, {coord[1]}, {coord[2]})"
    except Exception as e:
        return False, f"Erro ao ler radar: {e}"


def check_route_file(route_file):
    """Check if the route file exists and has waypoints."""
    import os
    if not route_file:
        return False, "Nenhuma rota selecionada."
    if not os.path.exists(route_file):
        return False, f"Arquivo de rota nao encontrado: {route_file}"
    try:
        from src.gameplay.cavebot import load_waypoints_from_file
        waypoints = load_waypoints_from_file(route_file)
        if not waypoints:
            return False, "Arquivo de rota esta vazio (0 waypoints)."
        return True, f"Rota carregada ({len(waypoints)} waypoints)"
    except Exception as e:
        return False, f"Erro ao carregar rota: {e}"


def check_healing_configured(healing_settings):
    """Check if at least one healing option is configured."""
    hp = healing_settings.get('healthPotion', {})
    mp = healing_settings.get('manaPotion', {})
    spells = healing_settings.get('spells', [])

    has_potion = (hp.get('enabled') and hp.get('hotkey')) or (mp.get('enabled') and mp.get('hotkey'))
    has_spell = any(s.get('enabled') and s.get('hotkey') for s in spells)

    if has_potion or has_spell:
        return True, "Healing configurado"
    return False, "Nenhuma potion ou spell de heal configurada."


def check_arduino_connected(hardware_settings):
    """Check if Arduino is connected (only if hardware mode requires it)."""
    mode = hardware_settings.get('mode', 'software')
    if mode in ('software', 'capture_card'):
        return True, "Arduino nao necessario neste modo"
    try:
        from src.hardware.arduino import is_connected
        if is_connected():
            return True, "Arduino conectado"
        return False, "Arduino nao conectado. Verifique o cabo USB e a porta serial."
    except Exception as e:
        return False, f"Erro ao verificar Arduino: {e}"


def run_preflight_checks(screenshot_gray, cavebot_settings, healing_settings, hardware_settings):
    """Run all pre-flight checks.

    Returns:
        (critical_failures, warnings, all_results)
        critical_failures: list of (name, message) for checks that block startup
        warnings: list of (name, message) for optional check failures
        all_results: list of (name, passed, message)
    """
    import cv2
    from src.core import get_screen_capture

    all_results = []
    critical_failures = []
    warnings = []

    # Critical checks
    passed, msg = check_screen_capture()
    all_results.append(("Captura de Tela", passed, msg))
    if not passed:
        critical_failures.append(("Captura de Tela", msg))

    if screenshot_gray is not None:
        passed, msg = check_battlelist(screenshot_gray)
        all_results.append(("Battle List", passed, msg))
        if not passed:
            critical_failures.append(("Battle List", msg))

        passed, msg = check_radar(screenshot_gray)
        all_results.append(("Radar", passed, msg))
        if not passed:
            critical_failures.append(("Radar", msg))

    # Optional checks
    cavebot_data = cavebot_settings.get('cavebot', {})
    route_file = cavebot_data.get('routeFile', '')
    if route_file:
        passed, msg = check_route_file(route_file)
        all_results.append(("Rota", passed, msg))
        if not passed:
            warnings.append(("Rota", msg))

    passed, msg = check_healing_configured(healing_settings)
    all_results.append(("Healing", passed, msg))
    if not passed:
        warnings.append(("Healing", msg))

    passed, msg = check_arduino_connected(hardware_settings)
    all_results.append(("Arduino", passed, msg))
    if not passed:
        warnings.append(("Arduino", msg))

    return critical_failures, warnings, all_results
