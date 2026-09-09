import time
from collections import defaultdict


class RateLimiter:
    """In-memory sliding-window limiter (single-instance; fine for one Railway dyno)."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = [t for t in self._hits[key] if now - t < self.window]
        if len(hits) >= self.max:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True
