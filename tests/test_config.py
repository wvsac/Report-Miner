"""Tests for configuration module."""

import os
import pytest
from pathlib import Path


class TestEnvironmentVariables:
    """Tests for environment variable configuration."""

    def test_jira_url_from_env(self, monkeypatch):
        monkeypatch.setenv("MINE_JIRA_URL", "https://test.atlassian.net")

        import importlib
        import reportminer.config as config_module
        importlib.reload(config_module)

        assert config_module.JIRA_BASE_URL == "https://test.atlassian.net"

    def test_jira_email_from_env(self, monkeypatch):
        monkeypatch.setenv("MINE_JIRA_EMAIL", "test@example.com")

        import importlib
        import reportminer.config as config_module
        importlib.reload(config_module)

        assert config_module.JIRA_EMAIL == "test@example.com"

    def test_jira_token_from_env(self, monkeypatch):
        monkeypatch.setenv("MINE_JIRA_TOKEN", "secret-token")

        import importlib
        import reportminer.config as config_module
        importlib.reload(config_module)

        assert config_module.JIRA_TOKEN == "secret-token"

    def test_default_values_when_no_env(self, monkeypatch):
        monkeypatch.delenv("MINE_JIRA_URL", raising=False)
        monkeypatch.delenv("MINE_JIRA_EMAIL", raising=False)
        monkeypatch.delenv("MINE_JIRA_TOKEN", raising=False)
        monkeypatch.delenv("MINE_FORMAT", raising=False)
        monkeypatch.delenv("MINE_STATUS", raising=False)

        import importlib
        import reportminer.config as config_module
        importlib.reload(config_module)

        assert config_module.JIRA_BASE_URL == ""
        assert config_module.DEFAULT_FORMAT == "raw"
        assert config_module.DEFAULT_STATUS == "failed"


class TestCacheConfiguration:
    """Tests for cache configuration."""

    def test_cache_dir_from_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MINE_CACHE_DIR", str(tmp_path / "custom_cache"))

        import importlib
        import reportminer.config as config_module
        importlib.reload(config_module)

        assert str(config_module.CACHE_DIR) == str(tmp_path / "custom_cache")

    def test_cache_ttl_from_env(self, monkeypatch):
        monkeypatch.setenv("MINE_CACHE_TTL", "72")

        import importlib
        import reportminer.config as config_module
        importlib.reload(config_module)

        assert config_module.CACHE_TTL_HOURS == 72


class TestSpinnerConfiguration:
    """Tests for spinner style configuration."""

    def test_default_spinner_is_unicode(self, monkeypatch):
        monkeypatch.delenv("MINE_SPINNER", raising=False)

        import importlib
        import reportminer.config as config_module
        importlib.reload(config_module)

        assert config_module.SPINNER_STYLE == "unicode"

    def test_ascii_spinner_from_env(self, monkeypatch):
        monkeypatch.setenv("MINE_SPINNER", "ascii")

        import importlib
        import reportminer.config as config_module
        importlib.reload(config_module)

        assert config_module.SPINNER_STYLE == "ascii"
