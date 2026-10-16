import threading
import time
from collections import OrderedDict


class SimpleRateLimiter:
    """
    Thread-safe, bounded in-memory sliding-window rate limiter with stale key eviction.

    Used to protect candidate APIs from request flooding or token guessing.
    Prevents memory exhaustion by evicting stale keys and enforcing a hard max_keys bound.
    """

    def __init__(
        self,
        requests_per_minute: int = 30,
        max_keys: int = 10000,
        cleanup_interval: float = 60.0,
    ):
        self.rate = requests_per_minute
        self.period = 60.0
        self.max_keys = max_keys
        self.cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        self.lock = threading.Lock()
        # Storage: OrderedDict: key -> list of timestamps
        self.requests: OrderedDict[str, list[float]] = OrderedDict()

    def _cleanup_stale_keys(self, now: float) -> None:
        """Evict all keys whose recorded timestamps are older than the sliding window."""
        cutoff = now - self.period
        stale_keys = [
            k for k, timestamps in self.requests.items()
            if not timestamps or timestamps[-1] <= cutoff
        ]
        for k in stale_keys:
            self.requests.pop(k, None)
        self._last_cleanup = now

    def is_allowed(self, key: str) -> bool:
        """Check if request from key is allowed under rate limit."""
        now = time.time()
        cutoff = now - self.period

        with self.lock:
            # Periodic sweep of expired keys or when capacity is exceeded
            if now - self._last_cleanup > self.cleanup_interval or len(self.requests) > self.max_keys:
                self._cleanup_stale_keys(now)

            timestamps = self.requests.get(key, [])
            # Prune timestamps older than window
            timestamps = [ts for ts in timestamps if ts > cutoff]

            if len(timestamps) >= self.rate:
                self.requests[key] = timestamps
                self.requests.move_to_end(key)
                return False

            # If capacity is still reached even after stale cleanup, evict oldest key (LRU)
            if key not in self.requests and len(self.requests) >= self.max_keys:
                self.requests.popitem(last=False)

            timestamps.append(now)
            self.requests[key] = timestamps
            self.requests.move_to_end(key)
            return True

    def clear(self):
        """Reset rate limiter state (useful for tests)."""
        with self.lock:
            self.requests.clear()
            self._last_cleanup = time.time()

