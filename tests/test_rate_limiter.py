from app.rate_limiter import SimpleRateLimiter


def test_rate_limiter_allows_under_limit():
    limiter = SimpleRateLimiter(requests_per_minute=3)
    key = "127.0.0.1"

    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True


def test_rate_limiter_blocks_exceeding_limit():
    limiter = SimpleRateLimiter(requests_per_minute=2)
    key = "192.168.1.10"

    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is False


def test_rate_limiter_clear():
    limiter = SimpleRateLimiter(requests_per_minute=1)
    key = "10.0.0.1"

    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is False

    limiter.clear()
    assert limiter.is_allowed(key) is True


def test_rate_limiter_evicts_stale_keys(monkeypatch):
    import time

    current_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: current_time)

    limiter = SimpleRateLimiter(requests_per_minute=5, cleanup_interval=10.0)
    limiter.is_allowed("old_key")
    assert "old_key" in limiter.requests

    # Advance time beyond sliding window (60s)
    current_time = 1075.0
    limiter.is_allowed("new_key")

    assert "new_key" in limiter.requests
    assert "old_key" not in limiter.requests


def test_rate_limiter_enforces_max_keys_capacity():
    limiter = SimpleRateLimiter(requests_per_minute=10, max_keys=3)

    limiter.is_allowed("ip_1")
    limiter.is_allowed("ip_2")
    limiter.is_allowed("ip_3")

    assert len(limiter.requests) == 3
    assert "ip_1" in limiter.requests

    # 4th unique IP should evict the oldest key (ip_1)
    limiter.is_allowed("ip_4")
    assert len(limiter.requests) == 3
    assert "ip_1" not in limiter.requests
    assert "ip_4" in limiter.requests

