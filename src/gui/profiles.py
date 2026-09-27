"""
Settings profiles: one gui_config.json per profile (vocation or character).

    profiles/
        active_profile.txt
        Knight/gui_config.json
        Paladin/gui_config.json

The profiles folder holds reconnect credentials - keep it out of git.
"""
import os
import re
import shutil

PROFILES_DIR = "profiles"
ACTIVE_PROFILE_FILE = os.path.join(PROFILES_DIR, "active_profile.txt")
CONFIG_FILENAME = "gui_config.json"
LEGACY_CONFIG_PATH = "gui_config.json"
DEFAULT_PROFILE = "Default"
VALID_NAME = re.compile(r"^[A-Za-z0-9 _-]{1,32}$")


def ensure_profiles():
    """Create the profiles folder; the first time, the old gui_config.json becomes 'Default'."""
    os.makedirs(PROFILES_DIR, exist_ok=True)
    if list_profiles():
        return
    os.makedirs(os.path.join(PROFILES_DIR, DEFAULT_PROFILE), exist_ok=True)
    if os.path.exists(LEGACY_CONFIG_PATH):
        shutil.copyfile(LEGACY_CONFIG_PATH, profile_config_path(DEFAULT_PROFILE))


def list_profiles():
    if not os.path.isdir(PROFILES_DIR):
        return []
    return sorted(
        name for name in os.listdir(PROFILES_DIR)
        if os.path.isdir(os.path.join(PROFILES_DIR, name)) and not name.startswith(("_", "."))
    )


def profile_config_path(name):
    return os.path.join(PROFILES_DIR, name, CONFIG_FILENAME)


def get_active_profile():
    profiles = list_profiles()
    if os.path.exists(ACTIVE_PROFILE_FILE):
        with open(ACTIVE_PROFILE_FILE) as f:
            name = f.read().strip()
        if name in profiles:
            return name
    return profiles[0] if profiles else DEFAULT_PROFILE


def set_active_profile(name):
    with open(ACTIVE_PROFILE_FILE, "w") as f:
        f.write(name)


def create_profile(name, copy_from):
    """New profile seeded with copy_from's settings. Returns an error message or None."""
    name = name.strip()
    if not VALID_NAME.match(name) or name.startswith(("_", ".")):
        return "Use letters, numbers, spaces, - or _ (max 32)."
    if name in list_profiles():
        return f"Profile '{name}' already exists."
    os.makedirs(os.path.join(PROFILES_DIR, name))
    source = profile_config_path(copy_from)
    if os.path.exists(source):
        shutil.copyfile(source, profile_config_path(name))
    return None


def delete_profile(name):
    """Returns an error message or None."""
    if len(list_profiles()) <= 1:
        return "Can't delete the last profile."
    shutil.rmtree(os.path.join(PROFILES_DIR, name))
    return None
