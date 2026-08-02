import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any, Hashable


class AsyncTTLCache:
    def __init__(self, ttl_seconds: float = 30):
        self.ttl_seconds = ttl_seconds
        self._values: dict[Hashable, tuple[float, Any]] = {}
        self._locks: dict[Hashable, asyncio.Lock] = {}

    async def get_or_load(
        self,
        key: Hashable,
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        now = time.monotonic()
        cached = self._values.get(key)
        if cached and cached[0] > now:
            return cached[1]

        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            now = time.monotonic()
            cached = self._values.get(key)
            if cached and cached[0] > now:
                return cached[1]

            value = await loader()
            self._values[key] = (now + self.ttl_seconds, value)
            self._prune(now)
            return value

    def _prune(self, now: float) -> None:
        expired = [key for key, (expires_at, _) in self._values.items() if expires_at <= now]
        for key in expired:
            self._values.pop(key, None)
            self._locks.pop(key, None)


stats_cache = AsyncTTLCache(ttl_seconds=30)
