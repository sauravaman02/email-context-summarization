"""In-memory TTL cache for summary responses.

Avoids redundant Gemini API calls for recently-generated summaries.
Designed with a pluggable interface — swap to a Redis-backed implementation
for multi-instance production deployments without changing calling code.
"""

import logging
import time
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class TTLCache:
    """In-memory key-value store with per-key time-to-live expiration.

    Thread safety note: CPython's GIL makes dict operations atomic for
    single get/set calls. For multi-threaded scenarios beyond the GIL,
    consider wrapping with a threading.Lock or switching to Redis.
    """

    def __init__(self, default_ttl: int | None = None) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._default_ttl = default_ttl or settings.cache_ttl_seconds

    def get(self, key: str) -> Any | None:
        """Retrieve a value if it exists and hasn't expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            logger.debug("Cache MISS (expired): %s", key)
            return None
        logger.debug("Cache HIT: %s", key)
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value with an optional custom TTL (seconds)."""
        expires_at = time.time() + (ttl or self._default_ttl)
        self._store[key] = (value, expires_at)
        logger.debug("Cache SET: %s (ttl=%ds)", key, ttl or self._default_ttl)

    def delete(self, key: str) -> None:
        """Remove a specific key from the cache."""
        self._store.pop(key, None)
        logger.debug("Cache DELETE: %s", key)

    def clear(self) -> None:
        """Flush all entries from the cache."""
        self._store.clear()

    def make_summary_key(
        self,
        client_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Build a deterministic cache key for a client summary."""
        return f"summary:{client_id}:{start_date or 'none'}:{end_date or 'none'}"


cache = TTLCache()
