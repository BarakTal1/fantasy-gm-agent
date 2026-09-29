import time

from fantasy_gm.yahoo_client.cache import ttl_cache


def test_caches_within_ttl_and_expires():
    calls = {"n": 0}

    @ttl_cache(ttl_seconds=1)
    def f():
        calls["n"] += 1
        return calls["n"]

    assert f() == 1
    assert f() == 1          # cached
    time.sleep(1.1)
    assert f() == 2          # expired -> recomputed
