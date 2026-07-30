"""Small in-process sliding-window API rate limiter."""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        now = monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            values = self._requests[key]
            while values and values[0] <= cutoff:
                values.popleft()
            if len(values) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - values[0])))
                return False, retry_after
            values.append(now)
            return True, 0
