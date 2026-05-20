import threading
from unittest.mock import patch, Mock
from src.telemetry.remote_config import RemoteConfigManager
from src.core.config_merge import deep_merge


class TestDeepMerge:
    def test_shallow_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"healing": {"healthPotion": {"threshold": 30, "hotkey": "1"}}}
        override = {"healing": {"healthPotion": {"threshold": 50}}}
        result = deep_merge(base, override)
        assert result == {"healing": {"healthPotion": {"threshold": 50, "hotkey": "1"}}}

    def test_array_replaced_not_merged(self):
        base = {"whitelist": ["Demon", "Dragon"]}
        override = {"whitelist": ["Rat"]}
        result = deep_merge(base, override)
        assert result == {"whitelist": ["Rat"]}

    def test_does_not_mutate_base(self):
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        result = deep_merge(base, override)
        assert "c" not in base["a"]
        assert result["a"] == {"b": 1, "c": 2}

    def test_empty_override(self):
        base = {"a": 1}
        result = deep_merge(base, {})
        assert result == {"a": 1}

    def test_empty_base(self):
        result = deep_merge({}, {"a": 1})
        assert result == {"a": 1}


class TestRemoteConfigManager:
    def test_initial_state(self):
        mgr = RemoteConfigManager()
        assert not mgr.has_config
        assert mgr.version == 0
        assert mgr.get_config() == {}

    def test_on_config_updated(self):
        mgr = RemoteConfigManager()
        mgr.on_config_updated({"healing": {"threshold": 50}}, 1)
        assert mgr.has_config
        assert mgr.version == 1
        assert mgr.get_config() == {"healing": {"threshold": 50}}

    def test_skips_old_version(self):
        mgr = RemoteConfigManager()
        mgr.on_config_updated({"a": 1}, 2)
        mgr.on_config_updated({"a": 99}, 1)
        assert mgr.get_config() == {"a": 1}
        assert mgr.version == 2

    def test_get_config_returns_deep_copy(self):
        mgr = RemoteConfigManager()
        mgr.on_config_updated({"nested": {"key": "value"}}, 1)
        config1 = mgr.get_config()
        config1["nested"]["key"] = "mutated"
        config2 = mgr.get_config()
        assert config2["nested"]["key"] == "value"

    def test_thread_safety(self):
        """Multiple threads writing config concurrently."""
        mgr = RemoteConfigManager()
        errors = []

        def writer(version):
            try:
                mgr.on_config_updated({"v": version}, version)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(1, 101)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert mgr.has_config
        assert mgr.version == 100

    @patch("requests.get")
    def test_fetch_success(self, mock_get):
        """Successful fetch from API."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "config": {"healing": {"healthPotion": {"threshold": 50}}},
            "version": 3,
        }
        mock_get.return_value = mock_response

        mgr = RemoteConfigManager()
        result = mgr.fetch("http://localhost:3333", "test_key", "char_123")

        assert result
        assert mgr.has_config
        assert mgr.version == 3
        assert mgr.get_config() == {"healing": {"healthPotion": {"threshold": 50}}}

    def test_fetch_graceful_failure(self):
        """Fetch fails gracefully when API is unavailable."""
        mgr = RemoteConfigManager()
        result = mgr.fetch("http://localhost:99999", "fake_key", "fake_id")
        assert not result
        assert not mgr.has_config
