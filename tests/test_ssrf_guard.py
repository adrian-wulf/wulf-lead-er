import pytest
from wulf_web_leader.audit.fetch import is_ip_allowed, validate_url_safety


def test_ip_filtering():
    # Forbidden internal IPs
    assert not is_ip_allowed("127.0.0.1")
    assert not is_ip_allowed("127.0.1.1")
    assert not is_ip_allowed("10.0.0.1")
    assert not is_ip_allowed("192.168.1.1")
    assert not is_ip_allowed("172.16.0.1")
    assert not is_ip_allowed("169.254.169.254")  # AWS metadata
    assert not is_ip_allowed("0.0.0.0")
    assert not is_ip_allowed("::1")

    # Allowed public IPs
    assert is_ip_allowed("8.8.8.8")
    assert is_ip_allowed("1.1.1.1")
    assert is_ip_allowed("140.82.121.3")  # GitHub


def test_url_safety():
    # Reject non-http schemes
    is_safe, msg = validate_url_safety("file:///etc/passwd")
    assert not is_safe
    assert "scheme" in msg.lower()

    is_safe, msg = validate_url_safety("gopher://127.0.0.1:70")
    assert not is_safe

    # Reject localhost hostnames
    is_safe, msg = validate_url_safety("http://localhost:8080")
    assert not is_safe
