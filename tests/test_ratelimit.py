from unittest.mock import MagicMock

from app.ratelimit import DAY, GLOBAL_MESSAGE, MINUTE_MESSAGE, RateLimiter, client_ip


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def _limiter(**limits):
    clock = FakeClock()
    return RateLimiter(**{"per_minute": 3, "per_day": 10, "global_per_day": 100, **limits}, clock=clock), clock


def test_per_minute_limit_and_recovery():
    limiter, clock = _limiter()
    assert [limiter.check("a") for _ in range(3)] == [None] * 3
    retry_after, message = limiter.check("a")
    assert message == MINUTE_MESSAGE
    assert 0 < retry_after <= 61
    assert limiter.check("b") is None  # other clients are not affected
    clock.now += 61
    assert limiter.check("a") is None


def test_blocked_requests_are_not_counted():
    limiter, clock = _limiter(per_minute=1)
    limiter.check("a")
    for _ in range(5):
        assert limiter.check("a") is not None
    clock.now += 61
    assert limiter.check("a") is None


def test_per_day_limit():
    limiter, clock = _limiter(per_minute=100, per_day=4)
    for _ in range(4):
        assert limiter.check("a") is None
    retry_after, _ = limiter.check("a")
    assert retry_after > 60
    clock.now += DAY + 1
    assert limiter.check("a") is None


def test_global_limit_across_clients():
    limiter, _ = _limiter(global_per_day=3)
    assert [limiter.check(ip) for ip in ("a", "b", "c")] == [None] * 3
    assert limiter.check("d")[1] == GLOBAL_MESSAGE


def test_blocked_clients_are_not_stored():
    limiter, _ = _limiter(global_per_day=1)
    limiter.check("a")
    for i in range(100):
        limiter.check(f"spam-{i}")
    assert list(limiter._by_client) == ["a"]


def test_idle_clients_are_forgotten():
    limiter, clock = _limiter(global_per_day=20_000)
    for i in range(10_001):
        limiter.check(f"10.0.{i // 256}.{i % 256}")
    clock.now += DAY + 1
    limiter.check("new")
    assert len(limiter._by_client) == 1


def test_client_ip_uses_address_added_by_proxy():
    request = MagicMock()
    request.headers = {"x-forwarded-for": "1.2.3.4, 203.0.113.7"}  # first entry is client-controlled
    assert client_ip(request) == "203.0.113.7"
    request.headers = {}
    request.client.host = "127.0.0.1"
    assert client_ip(request) == "127.0.0.1"
