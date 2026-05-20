"""
Configuration Manager for GUI settings.

Handles loading and saving GUI configuration to JSON.
All default values come from src.core.defaults (single source of truth).
"""
import copy
import json
import os
from typing import Any, Dict, Optional

from ..core.defaults import DEFAULT_CONFIG


class ConfigManager:
    """Manages GUI configuration persistence."""

    def __init__(self, config_path: str = "gui_config.json"):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.config = json.load(f)
                # Merge with defaults to ensure all keys exist
                self.config = self._merge_with_defaults(self.config, DEFAULT_CONFIG)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}")
                self.config = copy.deepcopy(DEFAULT_CONFIG)
        else:
            self.config = copy.deepcopy(DEFAULT_CONFIG)
        return self.config

    def save(self) -> bool:
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot-notation key."""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by dot-notation key."""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def reset_to_defaults(self) -> None:
        """Reset config to DEFAULT_CONFIG and save."""
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        self.save()

    def _merge_with_defaults(self, config: Dict, defaults: Dict) -> Dict:
        """Merge config with defaults, adding missing keys."""
        result = defaults.copy()
        for key, value in config.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_with_defaults(value, result[key])
            else:
                result[key] = value
        return result
