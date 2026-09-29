from fantasy_gm.ratelimit import RateLimiter


def test_allows_up_to_limit_then_blocks():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    assert rl.allow("ip1", now=100.0) is True
    assert rl.allow("ip1", now=101.0) is True
    assert rl.allow("ip1", now=102.0) is False        # 3rd within window blocked
    assert rl.allow("ip2", now=102.0) is True          # other key unaffected


def test_window_resets():
    rl = RateLimiter(max_requests=1, window_seconds=10)
    assert rl.allow("ip1", now=0.0) is True
    assert rl.allow("ip1", now=5.0) is False
    assert rl.allow("ip1", now=11.0) is True           # window elapsed
