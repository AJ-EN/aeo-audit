"""SQLite-based response cache."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any


class ResponseCache:
    """SQLite cache for crawled responses.

    Key: (url, user_agent, accept_header)
    Value: rendered DOM + extracted data + headers + timing
    """

    def __init__(self, db_path: str = ".aeo_cache.db", ttl: int = 3600) -> None:
        self._db_path = db_path
        self._ttl = ttl
        self._conn: sqlite3.Connection | None = None

    def open(self) -> None:
        """Initialize the cache database."""
        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at REAL NOT NULL
            )"""
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()

    def get(self, url: str, user_agent: str = "", accept: str = "") -> dict[str, Any] | None:
        """Retrieve cached response if not expired."""
        if not self._conn:
            return None
        key = self._make_key(url, user_agent, accept)
        row = self._conn.execute(
            "SELECT value, created_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, created_at = row
        if time.time() - created_at > self._ttl:
            self._conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            self._conn.commit()
            return None
        return json.loads(value)  # type: ignore[no-any-return]

    def set(self, url: str, data: dict[str, Any], user_agent: str = "", accept: str = "") -> None:
        """Store a response in cache."""
        if not self._conn:
            return
        key = self._make_key(url, user_agent, accept)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, created_at) VALUES (?, ?, ?)",
            (key, json.dumps(data), time.time()),
        )
        self._conn.commit()

    def clear(self) -> None:
        """Clear all cached entries."""
        if self._conn:
            self._conn.execute("DELETE FROM cache")
            self._conn.commit()

    @staticmethod
    def _make_key(url: str, user_agent: str, accept: str) -> str:
        """Create composite cache key."""
        return f"{url}|{user_agent}|{accept}"
