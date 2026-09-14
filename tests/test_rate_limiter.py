import pytest
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient

from wulf_web_leader.web.app import app, scan_manager
from wulf_web_leader.web.rate_limiter import IPRateLimiter, gemini_rate_limiter, scan_rate_limiter
from wulf_web_leader.web.session_manager import get_manager


def test_ip_rate_limiter_unit(monkeypatch):
    monkeypatch.setenv("ENABLE_RATE_LIMIT", "1")
    limiter = IPRateLimiter(cooldown_seconds=60.0)

    # 1st request from IP 1.2.3.4 allowed
    allowed, retry_after = limiter.check("1.2.3.4")
    assert allowed is True
    assert retry_after == 0.0

    # 2nd request from same IP rejected within 60s
    allowed, retry_after = limiter.check("1.2.3.4")
    assert allowed is False
    assert 0 < retry_after <= 60.0

    # Request from different IP allowed
    allowed_diff, _ = limiter.check("5.6.7.8")
    assert allowed_diff is True

    # Reset single IP
    limiter.reset("1.2.3.4")
    allowed_again, _ = limiter.check("1.2.3.4")
    assert allowed_again is True


def test_rate_limit_disabled_by_default():
    # By default, rate limiter is disabled to allow continuous OSINT & multiple scans
    assert scan_rate_limiter.is_disabled() or scan_rate_limiter.cooldown_seconds <= 0
    allowed, _ = scan_rate_limiter.check("1.1.1.1")
    assert allowed is True
    allowed2, _ = scan_rate_limiter.check("1.1.1.1")
    assert allowed2 is True


def test_rate_limit_scan_start_when_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_RATE_LIMIT", "1")
    scan_rate_limiter.cooldown_seconds = 60.0
    client = TestClient(app)
    scan_rate_limiter.reset()

    app.dependency_overrides[get_manager] = lambda: scan_manager
    try:
        scan_manager.status = "idle"
        with patch.object(scan_manager, "start_scan", new_callable=AsyncMock) as mock_start:
            mock_start.return_value = True

            # 1st call succeeds
            res1 = client.post(
                "/api/scan/start",
                json={"country": "PL", "city": "Kraków", "vertical": "informatyk"},
                headers={"X-Forwarded-For": "203.0.113.195"},
            )
            assert res1.status_code == 200

            # 2nd call from same IP immediately gets 429
            res2 = client.post(
                "/api/scan/start",
                json={"country": "PL", "city": "Kraków", "vertical": "informatyk"},
                headers={"X-Forwarded-For": "203.0.113.195"},
            )
            assert res2.status_code == 429
            assert "maksymalnie 1" in res2.json()["detail"]
            assert "Retry-After" in res2.headers

            # Different IP succeeds
            res3 = client.post(
                "/api/scan/start",
                json={"country": "PL", "city": "Kraków", "vertical": "informatyk"},
                headers={"X-Forwarded-For": "203.0.113.196"},
            )
            assert res3.status_code == 200
    finally:
        app.dependency_overrides.clear()
        scan_rate_limiter.reset()
        scan_rate_limiter.cooldown_seconds = 0.0


def test_rate_limit_gemini_verify_when_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_RATE_LIMIT", "1")
    gemini_rate_limiter.cooldown_seconds = 60.0
    client = TestClient(app)
    gemini_rate_limiter.reset()

    with patch.object(scan_manager, "verify_lead_gemini", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = None

        # 1st call gets 404 (because lead not in mock memory) but passes rate limit
        res1 = client.post(
            "/api/leads/test-lead-1/gemini-verify",
            headers={"X-Forwarded-For": "198.51.100.42"},
        )
        assert res1.status_code == 404

        # 2nd call from same IP within 60s gets 429 Too Many Requests
        res2 = client.post(
            "/api/leads/test-lead-1/gemini-verify",
            headers={"X-Forwarded-For": "198.51.100.42"},
        )
        assert res2.status_code == 429
        assert "limit zapytań" in res2.json()["detail"].lower()
        assert "Retry-After" in res2.headers

    gemini_rate_limiter.reset()
    gemini_rate_limiter.cooldown_seconds = 0.0
