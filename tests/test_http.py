from __future__ import annotations

from public_data_agent.http_util import RateLimiter


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
