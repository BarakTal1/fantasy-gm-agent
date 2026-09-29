from dataclasses import dataclass

import httpx


@dataclass
class YahooError(Exception):
    kind: str      # "reauth" | "rate_limited" | "server" | "unknown"
    message: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.message}"


def classify(exc: httpx.HTTPStatusError) -> YahooError:
    status = exc.response.status_code
    if status == 401:
        return YahooError("reauth", "Access rejected; refresh token likely dead.")
    if status == 429:
        return YahooError("rate_limited", "Yahoo rate limit hit; back off.")
    if 500 <= status < 600:
        return YahooError("server", f"Yahoo server error {status}.")
    return YahooError("unknown", f"Unexpected status {status}.")
