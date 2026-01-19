"""File-based cache for Jira API responses."""

import json
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

from .config import CACHE_DIR, CACHE_TTL_HOURS


class FileCache:
    """Simple file-based cache with TTL."""

    def __init__(self, namespace: str = "jira"):
        self.cache_dir = CACHE_DIR / namespace
        self.ttl = timedelta(hours=CACHE_TTL_HOURS)

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for a cache key."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{key_hash}.json"

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        path = self._get_cache_path(key)

        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            cached_at = datetime.fromisoformat(data["cached_at"])

            if datetime.now() - cached_at > self.ttl:
                path.unlink()
                return None

            return data["value"]
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def set(self, key: str, value: Any) -> None:
        """Store value in cache."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        path = self._get_cache_path(key)
        data = {
            "cached_at": datetime.now().isoformat(),
            "key": key,
            "value": value,
        }
        path.write_text(json.dumps(data, indent=2))

    def clear(self) -> int:
        """Clear all cached items. Returns count of items cleared."""
        if not self.cache_dir.exists():
            return 0

        count = 0
        for path in self.cache_dir.glob("*.json"):
            path.unlink()
            count += 1
        return count
