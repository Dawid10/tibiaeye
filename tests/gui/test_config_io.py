"""Tests for config import/export functionality."""
import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.gui.config_io import sanitize_config, export_config, import_config


class TestSanitizeConfig:
    def test_removes_password(self):
        """Should replace password fields with empty string."""
        config = {'reconnect': {'enabled': True, 'password': 'secret123'}}
        result = sanitize_config(config)
        assert result['reconnect']['password'] == ''

    def test_removes_email(self):
        """Should replace email fields with empty string."""
        config = {'reconnect': {'email': 'user@example.com'}}
        result = sanitize_config(config)
        assert result['reconnect']['email'] == ''

    def test_preserves_non_sensitive(self):
        """Should preserve non-sensitive fields."""
        config = {'general': {'tickRate': 0.100, 'enableHealing': True}}
        result = sanitize_config(config)
        assert result['general']['tickRate'] == 0.100
        assert result['general']['enableHealing'] is True

    def test_nested_sensitive_fields(self):
        """Should handle deeply nested sensitive fields."""
        config = {'a': {'b': {'password': 'x', 'value': 1}}}
        result = sanitize_config(config)
        assert result['a']['b']['password'] == ''
        assert result['a']['b']['value'] == 1

    def test_lists_preserved(self):
        """Should preserve list values."""
        config = {'spells': [{'name': 'exura', 'hotkey': 'F1'}]}
        result = sanitize_config(config)
        assert result['spells'][0]['name'] == 'exura'


class TestExportConfig:
    def test_export_creates_file(self):
        """Should create a JSON file with sanitized config."""
        config = {'general': {'tickRate': 0.1}, 'reconnect': {'password': 'secret'}}
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
            path = f.name

        try:
            ok, msg = export_config(config, path)
            assert ok
            with open(path) as f:
                exported = json.load(f)
            assert exported['reconnect']['password'] == ''
            assert exported['general']['tickRate'] == 0.1
        finally:
            os.unlink(path)


class TestImportConfig:
    def test_import_valid_json(self):
        """Should import and merge with defaults."""
        config = {'general': {'tickRate': 0.05}}
        with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as f:
            json.dump(config, f)
            path = f.name

        try:
            result, msg = import_config(path)
            assert result is not None
            assert result['general']['tickRate'] == 0.05
            # Should have defaults merged in
            assert 'healing' in result
        finally:
            os.unlink(path)

    def test_import_invalid_json(self):
        """Should fail gracefully on invalid JSON."""
        with tempfile.NamedTemporaryFile(suffix='.json', mode='w', delete=False) as f:
            f.write("not valid json {{{")
            path = f.name

        try:
            result, msg = import_config(path)
            assert result is None
            assert "JSON" in msg
        finally:
            os.unlink(path)

    def test_import_nonexistent_file(self):
        """Should fail gracefully on missing file."""
        result, msg = import_config('/nonexistent/config.json')
        assert result is None
        assert "Erro" in msg
