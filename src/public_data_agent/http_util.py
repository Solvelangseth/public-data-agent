from __future__ import annotations

import hashlib
import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

USER_AGENT = "public-data-agent/0.1 (+https://github.com/Solvelangseth/public-data-agent)"


@dataclass(frozen=True)
class JsonResponse:
    status: int
    url: str
    body: Any


@dataclass(frozen=True)
class FileResponse:
    status: int
    url: str
    headers: dict[str, str]
    path: Path | None = None
    sha256: str | None = None
    bytes_written: int = 0


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
        return self.request_json("GET", url, headers=headers).body

    def get_json_response(self, url: str, *, headers: dict[str, str] | None = None) -> JsonResponse:
        return self.request_json("GET", url, headers=headers)

    def get_text(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        """GET a printed document body without requiring JSON."""

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            if self.limiter:
                self.limiter.acquire()
            req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
            if headers:
                req_headers.update(headers)
            request = urllib.request.Request(url, headers=req_headers, method="GET")
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                return raw.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 429 or 500 <= exc.code <= 599:
                    wait = _retry_after(exc) or min(2**attempt, 30)
                    self.sleeper(wait)
                    continue
                body = exc.read().decode("utf-8", errors="replace")
                raise SourceHttpError(exc.code, url, body) from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                self.sleeper(min(2**attempt, 30))
                continue
        raise SourceHttpError(0, url, f"exhausted retries: {last_error}") from last_error

    def head(self, url: str, *, headers: dict[str, str] | None = None) -> FileResponse:
        """Read publisher file metadata without downloading its body."""

        return self._file_request("HEAD", url, headers=headers)

    def download(
        self,
        url: str,
        destination: Path,
        *,
        headers: dict[str, str] | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> FileResponse:
        """Stream a file to an atomic local path while hashing exact bytes."""

        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        return self._file_request(
            "GET", url, headers=headers, destination=destination, chunk_size=chunk_size
        )

    def _file_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        destination: Path | None = None,
        chunk_size: int = 1024 * 1024,
    ) -> FileResponse:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            if self.limiter:
                self.limiter.acquire()
            req_headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
            if headers:
                req_headers.update(headers)
            request = urllib.request.Request(url, headers=req_headers, method=method)
            partial = destination.with_name(destination.name + ".part") if destination else None
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    status = int(response.status)
                    response_headers = {
                        str(key).casefold(): str(value) for key, value in response.headers.items()
                    }
                    if destination is None or method == "HEAD":
                        return FileResponse(status=status, url=url, headers=response_headers)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    digest = hashlib.sha256()
                    written = 0
                    with partial.open("wb") as output:
                        while True:
                            block = response.read(chunk_size)
                            if not block:
                                break
                            output.write(block)
                            digest.update(block)
                            written += len(block)
                    expected = response_headers.get("content-length")
                    if expected is not None and expected.isdigit() and written != int(expected):
                        raise OSError(
                            f"incomplete download: expected {expected} bytes, received {written}"
                        )
                    partial.replace(destination)
                    return FileResponse(
                        status=status,
                        url=url,
                        headers=response_headers,
                        path=destination,
                        sha256=digest.hexdigest(),
                        bytes_written=written,
                    )
            except urllib.error.HTTPError as exc:
                last_error = exc
                if partial is not None and partial.exists():
                    partial.unlink()
                if exc.code == 304:
                    response_headers = {
                        str(key).casefold(): str(value) for key, value in exc.headers.items()
                    }
                    return FileResponse(status=304, url=url, headers=response_headers)
                if exc.code == 429 or 500 <= exc.code <= 599:
                    wait = _retry_after(exc) or min(2**attempt, 30)
                    self.sleeper(wait)
                    continue
                body = exc.read().decode("utf-8", errors="replace")
                raise SourceHttpError(exc.code, url, body) from exc
            except (
                urllib.error.URLError,
                http.client.IncompleteRead,
                TimeoutError,
                OSError,
            ) as exc:
                last_error = exc
                if partial is not None and partial.exists():
                    partial.unlink()
                self.sleeper(min(2**attempt, 30))
                continue
        raise SourceHttpError(0, url, f"exhausted retries: {last_error}") from last_error

    def post_json(
        self,
        url: str,
        body: Any,
        *,
        headers: dict[str, str] | None = None,
    ) -> Any:
        return self.post_json_response(url, body, headers=headers).body

    def post_json_response(
        self,
        url: str,
        body: Any,
        *,
        headers: dict[str, str] | None = None,
    ) -> JsonResponse:
        data = json.dumps(body).encode("utf-8")
        extra = {"Content-Type": "application/json"}
        if headers:
            extra.update(headers)
        return self.request_json("POST", url, data=data, headers=extra)

    def request_json(
        self,
        method: str,
        url: str,
        *,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> JsonResponse:
        return self._json(method, url, data=data, headers=headers)

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
        return self._json("POST", url, data=data, headers=extra).body

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
                    status = int(response.status)
                    raw = response.read()
                if not raw:
                    return JsonResponse(status=status, url=url, body=None)
                return JsonResponse(
                    status=status,
                    url=url,
                    body=json.loads(raw.decode("utf-8")),
                )
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
