"""Tests for file-based cache."""

import pytest
import time
from datetime import datetime, timedelta
from pathlib import Path

from reportminer.cache import FileCache


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """Create a cache instance with temporary directory."""
    monkeypatch.setattr("reportminer.cache.CACHE_DIR", tmp_path)
    monkeypatch.setattr("reportminer.cache.CACHE_TTL_HOURS", 1)
    return FileCache("test")


class TestFileCache:
    """Tests for FileCache class."""

    def test_set_and_get(self, cache):
        cache.set("key1", {"data": "value"})
        result = cache.get("key1")
        assert result == {"data": "value"}

    def test_get_nonexistent_key(self, cache):
        result = cache.get("nonexistent")
        assert result is None

    def test_stores_complex_data(self, cache):
        data = {
            "string": "value",
            "number": 42,
            "list": [1, 2, 3],
            "nested": {"a": "b"},
        }
        cache.set("complex", data)
        result = cache.get("complex")
        assert result == data

    def test_overwrites_existing(self, cache):
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"

    def test_clear_removes_all(self, cache):
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        count = cache.clear()
        assert count == 2
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_clear_empty_cache(self, cache):
        count = cache.clear()
        assert count == 0

    def test_different_namespaces(self, tmp_path, monkeypatch):
        monkeypatch.setattr("reportminer.cache.CACHE_DIR", tmp_path)
        cache1 = FileCache("namespace1")
        cache2 = FileCache("namespace2")

        cache1.set("key", "value1")
        cache2.set("key", "value2")

        assert cache1.get("key") == "value1"
        assert cache2.get("key") == "value2"

    def test_creates_cache_directory(self, tmp_path, monkeypatch):
        cache_dir = tmp_path / "new_cache"
        monkeypatch.setattr("reportminer.cache.CACHE_DIR", cache_dir)
        cache = FileCache("test")
        cache.set("key", "value")
        assert (cache_dir / "test").exists()

    def test_handles_corrupted_cache_file(self, cache, tmp_path):
        # Write corrupted data
        cache.set("key", "value")
        cache_file = list((tmp_path / "test").glob("*.json"))[0]
        cache_file.write_text("not valid json")

        # Should return None for corrupted entry
        result = cache.get("key")
        assert result is None
