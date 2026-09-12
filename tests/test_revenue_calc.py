from wulf_web_leader.score.revenue_calc import calculate_lost_revenue


def test_calculate_lost_revenue_no_website():
    res = calculate_lost_revenue(vertical="plumbers", country="PL", has_website=False)
    assert res["currency"] == "PLN"
    assert res["lost_clients_monthly"] > 0
    assert res["lost_revenue_monthly"] > 0
    assert "Brak własnej witryny" in res["pitch"]


def test_calculate_lost_revenue_broken_site_de():
    res = calculate_lost_revenue(vertical="auto_repair", country="DE", has_website=True, http_error=True)
    assert res["currency"] == "EUR"
    assert res["lost_clients_monthly"] >= 10
    assert "Awaria strony" in res["pitch"]


def test_calculate_lost_revenue_no_ssl_no_viewport():
    res = calculate_lost_revenue(vertical="hair", country="PL", has_website=True, is_https=False, has_viewport=False, load_time_seconds=6.5)
    assert res["currency"] == "PLN"
    assert res["leak_percentage"] > 50
    assert res["lost_revenue_annual"] > 0
    assert "brak wersji mobilnej" in res["pitch"]


def test_calculate_lost_revenue_optimized_site():
    res = calculate_lost_revenue(vertical="electricians", country="PL", has_website=True, is_https=True, has_viewport=True, load_time_seconds=1.2)
    assert res["leak_percentage"] <= 15
