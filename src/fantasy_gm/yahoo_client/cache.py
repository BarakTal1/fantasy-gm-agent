import time
from collections.abc import Callable
from functools import wraps


def ttl_cache(ttl_seconds: float) -> Callable:
    def decorator(fn: Callable) -> Callable:
        store: dict[tuple, tuple[float, object]] = {}

        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            if key in store:
                ts, val = store[key]
                if now - ts < ttl_seconds:
                    return val
            val = fn(*args, **kwargs)
            store[key] = (now, val)
            return val

        wrapper.cache_clear = store.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
