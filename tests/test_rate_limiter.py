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
