import httpx
import pytest

from fantasy_gm.yahoo_client.errors import YahooError, classify


def test_401_maps_to_reauth():
    err = classify(httpx.HTTPStatusError(
        "x", request=httpx.Request("GET", "http://x"),
        response=httpx.Response(401)))
    assert err.kind == "reauth"


def test_429_maps_to_rate_limited():
    err = classify(httpx.HTTPStatusError(
        "x", request=httpx.Request("GET", "http://x"),
        response=httpx.Response(429)))
    assert err.kind == "rate_limited"

def test_yahoo_error_is_raisable():
    with pytest.raises(YahooError):
        raise YahooError(kind="unknown", message="boom")
