from pathlib import Path
from wulf_web_leader.audit.proxy_pool import (
    get_all_proxies,
    get_random_proxy,
    has_proxies,
    get_proxies_file_path,
)


def test_proxy_pool_loads_proxies():
    path = get_proxies_file_path()
    assert path is not None
    assert path.is_file()

    proxies = get_all_proxies()
    assert len(proxies) >= 200
    assert has_proxies() is True

    rnd = get_random_proxy()
    assert rnd is not None
    assert rnd.startswith("http://")
    assert "@" in rnd
    assert ":" in rnd


def test_proxy_pool_custom_file(tmp_path, monkeypatch):
    custom = tmp_path / "test_proxies.txt"
    custom.write_text("1.2.3.4:8080:usr:pwd\nhttp://user2:pass2@5.6.7.8:9090\n")
    monkeypatch.setenv("PROXIES_FILE", str(custom))

    proxies = get_all_proxies(reload=True)
    assert len(proxies) == 2
    assert "http://usr:pwd@1.2.3.4:8080" in proxies
    assert "http://user2:pass2@5.6.7.8:9090" in proxies
