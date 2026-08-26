from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "public-data-agent/0.1 (+https://github.com/Solvelangseth/public-data-agent)"


class RateLimiter:
    """Token bucket. rate is tokens per second, burst is the max reserve."""

    def __init__(self, rate: float, burst: int) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        if burst < 1:
            raise ValueError("burst must be at least 1")
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.updated = time.monotonic()

    def acquire(self) -> None:
        while True:
            now = time.monotonic()
            self.tokens = min(self.burst, self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
            time.sleep((1 - self.tokens) / self.rate)


class HttpClient:
    def __init__(
        self,
        *,
        limiter: RateLimiter | None = None,
        timeout: float = 60.0,
        max_retries: int = 6,
        sleeper=time.sleep,
    ) -> None:
        self.limiter = limiter
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleeper = sleeper

    def get_json(self, url: str, *, headers: dict[str, str] | None = None) -> Any:
        return self._json("GET", url, headers=headers)

    def post_json(
        self,
        url: str,
        body: Any,
        *,
        headers: dict[str, str] | None = None,
    ) -> Any:
        data = json.dumps(body).encode("utf-8")
        extra = {"Content-Type": "application/json"}
        if headers:
            extra.update(headers)
        return self._json("POST", url, data=data, headers=extra)

    def post_form(
        self,
        url: str,
        fields: dict[str, str],
        *,
        headers: dict[str, str] | None = None,
    ) -> Any:
        data = urllib.parse.urlencode(fields).encode("utf-8")
        extra = {"Content-Type": "application/x-www-form-urlencoded"}
        if headers:
            extra.update(headers)
        return self._json("POST", url, data=data, headers=extra)

    def _json(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            if self.limiter:
                self.limiter.acquire()
            req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
            if headers:
                req_headers.update(headers)
            request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429 or 500 <= exc.code <= 599:
                    wait = _retry_after(exc) or min(2**attempt, 30)
                    self.sleeper(wait)
                    continue
                body = exc.read().decode("utf-8", errors="replace")
                raise SourceHttpError(exc.code, url, body) from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                self.sleeper(min(2**attempt, 30))
                continue
        raise SourceHttpError(0, url, f"exhausted retries: {last_error}") from last_error


class SourceHttpError(Exception):
    def __init__(self, status: int, url: str, body: str) -> None:
        self.status = status
        self.url = url
        self.body = body
        super().__init__(f"HTTP {status} for {url}: {body[:300]}")


def _retry_after(exc: urllib.error.HTTPError) -> float | None:
    raw = exc.headers.get("Retry-After") if exc.headers else None
    if not raw:
        return None
    try:
        return max(float(raw), 0.0)
    except ValueError:
        return None
