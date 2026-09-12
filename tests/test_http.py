from __future__ import annotations

import hashlib
import io

import pytest

from public_data_agent.http_util import HttpClient, RateLimiter, SourceHttpError


def test_rate_limiter_does_not_exceed_burst(monkeypatch) -> None:
    clock = {"now": 0.0}
    slept: list[float] = []

    monkeypatch.setattr("public_data_agent.http_util.time.monotonic", lambda: clock["now"])
    monkeypatch.setattr("public_data_agent.http_util.time.sleep", lambda seconds: slept.append(seconds) or clock.update(now=clock["now"] + seconds))

    limiter = RateLimiter(rate=5.0, burst=2)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()
    assert slept
    assert slept[0] == 0.2


class _FileResponse:
    status = 200

    def __init__(self, body: bytes, *, declared_length: int | None = None) -> None:
        self._body = io.BytesIO(body)
        length = len(body) if declared_length is None else declared_length
        self.headers = {"Content-Length": str(length), "ETag": "v1"}

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


def test_download_streams_exact_bytes_to_an_atomic_hashed_file(
    tmp_path, monkeypatch
) -> None:
    body = b"publisher bytes" * 100
    monkeypatch.setattr(
        "public_data_agent.http_util.urllib.request.urlopen",
        lambda request, timeout: _FileResponse(body),
    )
    destination = tmp_path / "snapshot.gz"
    result = HttpClient(max_retries=1).download(
        "https://example.org/snapshot.gz", destination, chunk_size=17
    )
    assert destination.read_bytes() == body
    assert result.sha256 == hashlib.sha256(body).hexdigest()
    assert result.bytes_written == len(body)
    assert not (tmp_path / "snapshot.gz.part").exists()


def test_incomplete_download_is_not_promoted_from_partial_file(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "public_data_agent.http_util.urllib.request.urlopen",
        lambda request, timeout: _FileResponse(b"short", declared_length=100),
    )
    destination = tmp_path / "snapshot.gz"
    with pytest.raises(SourceHttpError, match="incomplete download"):
        HttpClient(max_retries=1, sleeper=lambda _: None).download(
            "https://example.org/snapshot.gz", destination
        )
    assert not destination.exists()
    assert not (tmp_path / "snapshot.gz.part").exists()
