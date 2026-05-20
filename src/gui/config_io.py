"""
Config IO - Export, import, and sanitize GUI configuration.
"""
import copy
import json
from typing import Any, Dict, Optional

from ..core.defaults import DEFAULT_CONFIG

SENSITIVE_KEYS = {'password', 'email', 'apiKey', 'api_key', 'token', 'secret'}


def sanitize_config(config):
    """Remove sensitive fields from config for safe export."""
    if not isinstance(config, dict):
        return config
    result = {}
    for key, value in config.items():
        if key.lower() in {k.lower() for k in SENSITIVE_KEYS}:
            result[key] = ""
        elif isinstance(value, dict):
            result[key] = sanitize_config(value)
        elif isinstance(value, list):
            result[key] = [sanitize_config(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    return result


def export_config(config, path):
    """Export sanitized config to a file.

    Returns:
        (success: bool, message: str)
    """
    try:
        sanitized = sanitize_config(copy.deepcopy(config))
        with open(path, 'w') as f:
            json.dump(sanitized, f, indent=2)
        return True, f"Config exportada para {path}"
    except Exception as e:
        return False, f"Erro ao exportar config: {e}"


def import_config(path):
    """Import config from file and merge with defaults.

    Returns:
        (config: dict | None, message: str)
    """
    try:
        with open(path, 'r') as f:
            imported = json.load(f)
        if not isinstance(imported, dict):
            return None, "Arquivo de config invalido (esperado JSON object)."
        merged = _merge_with_defaults(imported, copy.deepcopy(DEFAULT_CONFIG))
        return merged, "Config importada com sucesso"
    except json.JSONDecodeError:
        return None, "Arquivo nao e um JSON valido."
    except Exception as e:
        return None, f"Erro ao importar config: {e}"


def _merge_with_defaults(config, defaults):
    """Merge imported config with defaults, adding missing keys."""
    result = defaults.copy()
    for key, value in config.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_with_defaults(value, result[key])
        else:
            result[key] = value
    return result
