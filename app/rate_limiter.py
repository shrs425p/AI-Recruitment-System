import threading
import time
from collections import defaultdict


class SimpleRateLimiter:
    """
    Thread-safe, in-memory token-bucket rate limiter.

    Used to protect candidate APIs from request flooding or token guessing.
    """

    def __init__(self, requests_per_minute: int = 30):
        self.rate = requests_per_minute
        self.period = 60.0
        self.lock = threading.Lock()
        # Storage: key -> list of timestamps
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """Check if request from key is allowed under rate limit."""
        now = time.time()
        cutoff = now - self.period

        with self.lock:
            # Prune timestamps older than window
            timestamps = [ts for ts in self.requests[key] if ts > cutoff]
            if len(timestamps) >= self.rate:
                self.requests[key] = timestamps
                return False

            timestamps.append(now)
            self.requests[key] = timestamps
            return True

    def clear(self):
        """Reset rate limiter state (useful for tests)."""
        with self.lock:
            self.requests.clear()
