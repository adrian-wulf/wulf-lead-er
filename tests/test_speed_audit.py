from wulf_web_leader.audit.speed import audit_website_speed


def test_audit_speed_invalid_url():
    res = audit_website_speed("")
    assert res["mobile_score"] == 0
    assert res["grade"] == "BRAK STRONY"


def test_audit_speed_real_or_mock(monkeypatch):
    class MockResp:
        status_code = 200
        content = b"<html><head></head><body><h1>Test</h1></body></html>"

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            return MockResp()

    monkeypatch.setattr("httpx.Client", MockClient)
    res = audit_website_speed("https://example.com")
    assert res["source"] == "network_probe"
    assert res["mobile_score"] >= 80
    assert res["grade"] == "DOBRA"
