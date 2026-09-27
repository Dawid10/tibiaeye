"""Gather overlay regions from repository locator caches."""
from typing import List, Dict, Optional

import numpy as np

from ...repositories.statusbar.locators import get_hp_icon_position, get_mana_icon_position
from ...repositories.statusbar.config import BAR_SIZE
from ...repositories.skills.locators import get_skills_icon_position
from ...repositories.battlelist.locators import get_icon_position as bl_get_icon_position
from ...repositories.battlelist.config import load_icon_image, CONTENT_WIDTH
from ...repositories.gamewindow.core import get_game_window_position
from ...repositories.gamewindow.config import load_arrow_images
from ...repositories.radar.locators import get_radar_tools_position
from ...repositories.radar.extractors import get_radar_bbox
from ...repositories.utils.cached_position import is_template_at
from ...repositories.actionBar.core import ActionBarRepository, _locate as ab_locate

# BattleList uses its own cache dict (locator takes cache as param)
_bl_cache: Dict[str, object] = {}
_bl_icon_image = None

# GameWindow arrow caches
_gw_left_cache: Dict[str, object] = {}
_gw_right_cache: Dict[str, object] = {}
_gw_map_top_cache: Dict[str, object] = {}
_gw_arrow_images = None

# ActionBar cache
_ab_left_arrows = None
_ab_left_arrows_pos = None
_ab_initialized = False


def _get_bl_icon_image():
    global _bl_icon_image
    if _bl_icon_image is None:
        _bl_icon_image = load_icon_image()
    return _bl_icon_image


def _get_gw_arrow_images():
    global _gw_arrow_images
    if _gw_arrow_images is None:
        _gw_arrow_images = load_arrow_images()
    return _gw_arrow_images


def _init_actionbar():
    global _ab_left_arrows, _ab_initialized
    if _ab_initialized:
        return
    _ab_initialized = True
    from ...repositories.actionBar.core import _load_gray_image, ACTIONBAR_IMAGES_PATH
    arrows_path = ACTIONBAR_IMAGES_PATH / "arrows"
    _ab_left_arrows = _load_gray_image(str(arrows_path / "left.png"))


def get_overlay_regions(screenshot_gray: np.ndarray) -> List[Dict]:
    regions = []

    # HP Bar region: icon + bar area
    hp_pos = get_hp_icon_position(screenshot_gray)
    if hp_pos is not None:
        x, y, w, h = hp_pos
        region_x = x
        region_y = y
        region_w = 13 + BAR_SIZE + 2
        region_h = h + 2
        regions.append({'name': 'HP Bar', 'bbox': (region_x, region_y, region_w, region_h)})

    # Mana Bar region: icon + bar area
    mana_pos = get_mana_icon_position(screenshot_gray)
    if mana_pos is not None:
        x, y, w, h = mana_pos
        region_x = x
        region_y = y
        region_w = 14 + BAR_SIZE + 2
        region_h = h + 2
        regions.append({'name': 'Mana Bar', 'bbox': (region_x, region_y, region_w, region_h)})

    # Skills panel region
    skills_pos = get_skills_icon_position(screenshot_gray)
    if skills_pos is not None:
        x, y, w, h = skills_pos
        regions.append({'name': 'Skills', 'bbox': (x, y, 170, 200)})

    # BattleList region: icon + content area below
    bl_icon = _get_bl_icon_image()
    if bl_icon is not None:
        bl_pos = bl_get_icon_position(screenshot_gray, bl_icon, _bl_cache)
        if bl_pos is not None:
            x, y, w, h = bl_pos
            content_x = x - 1
            content_y = y
            regions.append({
                'name': 'BattleList',
                'bbox': (content_x, content_y, CONTENT_WIDTH + 2, 220 + h),
            })

    # Game Window region: the map itself, same position the bot clicks with
    arrow_images = _get_gw_arrow_images()
    if arrow_images:
        game_window = get_game_window_position(
            screenshot_gray, arrow_images, _gw_left_cache, _gw_right_cache, _gw_map_top_cache)
        if game_window is not None:
            regions.append({'name': 'Game Window', 'bbox': game_window})

    # Radar/Minimap region: derived from tools position
    radar_pos = get_radar_tools_position(screenshot_gray)
    if radar_pos is not None:
        regions.append({'name': 'Radar', 'bbox': get_radar_bbox(radar_pos)})

    # Action Bar region: from left arrows position
    _init_actionbar()
    global _ab_left_arrows_pos
    if _ab_left_arrows is not None:
        if _ab_left_arrows_pos is not None and not is_template_at(screenshot_gray, _ab_left_arrows, _ab_left_arrows_pos):
            _ab_left_arrows_pos = None
        if _ab_left_arrows_pos is None:
            _ab_left_arrows_pos = ab_locate(screenshot_gray, _ab_left_arrows)
        if _ab_left_arrows_pos is not None:
            x, y, w, h = _ab_left_arrows_pos
            slot_width = ActionBarRepository.SLOT_WIDTH
            slot_spacing = ActionBarRepository.SLOT_SPACING
            num_slots = 12
            bar_x = x
            bar_w = w + (num_slots * (slot_width + slot_spacing))
            regions.append({'name': 'Action Bar', 'bbox': (bar_x, y, bar_w, h)})

    return regions
