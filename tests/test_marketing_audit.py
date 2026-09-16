import pytest
from wulf_web_leader.audit.parser import SafeWebsiteHTMLParser
from wulf_web_leader.models import CanonicalLead, AuditResult
from wulf_web_leader.score.hooks import generate_pitch_hooks, generate_greeting, generate_salutation


def test_parser_detects_meta_pixel():
    html_samples = [
        "<script>!function(f,b,e,v,n,t,s){fbq('init', '1234567890'); fbq('track', 'PageView');}</script>",
        '<script src="https://connect.facebook.net/en_US/fbevents.js"></script>',
        '<noscript><img height="1" width="1" src="https://www.facebook.com/tr?id=123456&ev=PageView&noscript=1"/></noscript>',
    ]
    for sample in html_samples:
        parser = SafeWebsiteHTMLParser()
        parser.feed(sample)
        parser.close()
        assert "Meta Pixel" in parser.detected_pixels
        assert "Meta Pixel" in parser.pixels
        assert "Meta Pixel" in parser.get_detected_pixels()


def test_parser_detects_ga4():
    html_samples = [
        "<script async src=\"https://www.googletagmanager.com/gtag/js?id=G-12345ABC\"></script>",
        "<script>window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);} gtag('config', 'G-XYZ123');</script>",
        '<script src="https://www.google-analytics.com/g/collect?v=2&tid=G-TEST"></script>',
    ]
    for sample in html_samples:
        parser = SafeWebsiteHTMLParser()
        parser.feed(sample)
        parser.close()
        assert "Google Analytics 4" in parser.detected_pixels
        assert "Google Analytics 4" in parser.pixels


def test_parser_detects_gtm():
    html = '<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({\'gtm.start\':new Date().getTime(),event:\'gtm.js\'});})(window,document,\'script\',\'dataLayer\',\'GTM-XXXXX\');</script><script src="https://www.googletagmanager.com/gtm.js?id=GTM-XXXXX"></script>'
    parser = SafeWebsiteHTMLParser()
    parser.feed(html)
    parser.close()
    assert "Google Tag Manager" in parser.detected_pixels
    assert "Google Tag Manager" in parser.pixels


def test_parser_detects_tiktok_pixel():
    html_samples = [
        '<script src="https://analytics.tiktok.com/i18n/pixel/events.js"></script>',
        "<script>!function (w, d, t) { ttq.load('ABCDEF123456'); ttq.page(); }(window, document, 'ttq');</script>",
    ]
    for sample in html_samples:
        parser = SafeWebsiteHTMLParser()
        parser.feed(sample)
        parser.close()
        assert "TikTok Pixel" in parser.detected_pixels
        assert "TikTok Pixel" in parser.pixels


def test_parser_detects_multiple_pixels_sorted():
    html = """
    <html>
    <head>
        <script src="https://connect.facebook.net/en_US/fbevents.js"></script>
        <script src="https://www.googletagmanager.com/gtm.js?id=GTM-1"></script>
        <script src="https://analytics.tiktok.com/i18n/pixel/events.js"></script>
        <script>gtag('config', 'g-12345');</script>
    </head>
    </html>
    """
    parser = SafeWebsiteHTMLParser()
    parser.feed(html)
    parser.close()
    expected = ["Google Analytics 4", "Google Tag Manager", "Meta Pixel", "TikTok Pixel"]
    assert parser.pixels == expected
    assert parser.get_detected_pixels() == expected


def test_hooks_missing_pixels():
    lead_pl = CanonicalLead(
        country="PL",
        name="Auto Serwis Kowalski",
        city="Rzeszów",
        phone="+48 17 800 11 22",
        website="https://serwis-kowalski.pl",
        website_kind="own",
        source="osm",
        source_id="node/1",
        industry_label="Mechanik",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=True,
            detected_pixels=[],
        ),
    )
    hooks_pl = generate_pitch_hooks(lead_pl, lang="pl")
    assert any("Strona nie posiada zainstalowanego Pixela Meta ani Google Analytics 4" in h for h in hooks_pl)

    lead_de = CanonicalLead(
        country="DE",
        name="Klaus Sanitär GmbH",
        city="Hannover",
        phone="+49 511 123456",
        website="https://klaus-sanitaer.de",
        website_kind="own",
        source="osm",
        source_id="node/2",
        industry_label="Klempner",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=True,
            has_impressum=True,
            detected_pixels=[],
        ),
    )
    hooks_de = generate_pitch_hooks(lead_de, lang="de")
    assert any("Die Website verfügt weder über ein Meta-Pixel noch über Google Analytics 4" in h for h in hooks_de)


def test_hooks_high_ttfb():
    lead_pl = CanonicalLead(
        country="PL",
        name="Wolna Strona Sp. j.",
        city="Warszawa",
        phone="+48 22 123 45 67",
        website="https://wolnastrona.pl",
        website_kind="own",
        source="osm",
        source_id="node/3",
        industry_label="Dentysta",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=True,
            detected_pixels=["Google Analytics 4"],
            ttfb_ms=1850.0,
        ),
    )
    hooks_pl = generate_pitch_hooks(lead_pl, lang="pl")
    assert any("Długi czas odpowiedzi serwera (TTFB: 1850 ms)" in h for h in hooks_pl)

    lead_de = CanonicalLead(
        country="DE",
        name="Langsame Seite GmbH",
        city="Berlin",
        phone="+49 30 987654",
        website="https://langsame-seite.de",
        website_kind="own",
        source="osm",
        source_id="node/4",
        industry_label="Architekt",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=True,
            has_impressum=True,
            detected_pixels=["Meta Pixel"],
            ttfb_ms=1420,
        ),
    )
    hooks_de = generate_pitch_hooks(lead_de, lang="de")
    assert any("Lange Server-Antwortzeit (TTFB: 1420 ms)" in h for h in hooks_de)


def test_personalized_salutation():
    lead_pl = CanonicalLead(
        country="PL",
        name="Zakład Stolarski",
        owner_name="Piotr Kowalski",
        phone="+48 601 234 567",
        source="osm",
        source_id="node/5",
        industry_label="Stolarz",
    )
    assert generate_greeting(lead_pl, lang="pl") == "Dzień dobry Panie/Pani Piotr,"
    assert generate_salutation(lead_pl, lang="pl") == "Dzień dobry Panie/Pani Piotr,"

    lead_de = CanonicalLead(
        country="DE",
        name="Tischlerei Schmidt",
        owner_name="Johann Schmidt",
        phone="+49 151 12345678",
        source="osm",
        source_id="node/6",
        industry_label="Tischler",
    )
    assert generate_greeting(lead_de, lang="de") == "Sehr geehrte(r) Frau/Herr Johann Schmidt,"
    assert generate_salutation(lead_de, lang="de") == "Sehr geehrte(r) Frau/Herr Johann Schmidt,"

    # Fallback to representative name if owner_name is not set
    lead_rep = CanonicalLead(
        country="DE",
        name="Malerbetrieb Weber",
        owner_name=None,
        phone="+49 151 999999",
        source="osm",
        source_id="node/7",
        industry_label="Maler",
        audit=AuditResult(representative_name="Hans Weber"),
    )
    assert generate_greeting(lead_rep, lang="de") == "Sehr geehrte(r) Frau/Herr Hans Weber,"


@pytest.mark.asyncio
async def test_audit_website_ttfb_and_pixel_detection():
    from unittest.mock import AsyncMock, MagicMock, patch
    from wulf_web_leader.audit.fetch import audit_website

    homepage_html = b"""
    <!DOCTYPE html>
    <html>
      <head>
        <title>Maler Betrieb</title>
        <script src="https://connect.facebook.net/en_US/fbevents.js"></script>
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-12345"></script>
      </head>
      <body>
        <p>Tel: +49 151 123456</p>
      </body>
    </html>
    """
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://maler-betrieb.de"
    mock_resp.is_redirect = False
    mock_resp.headers = {"Content-Type": "text/html"}

    async def aiter_bytes():
        yield homepage_html

    mock_resp.aiter_bytes = aiter_bytes

    stream_cm = MagicMock()
    stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    stream_cm.__aexit__ = AsyncMock(return_value=None)

    client_mock = MagicMock()
    client_mock.stream.return_value = stream_cm
    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=client_mock)
    client_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("wulf_web_leader.audit.fetch.validate_url_safety", return_value=(True, None)), \
         patch("httpx.AsyncClient", return_value=client_cm):
        res = await audit_website("https://maler-betrieb.de", country="DE")

    assert res.reachable is True
    assert res.ttfb_ms is not None
    assert isinstance(res.ttfb_ms, (int, float))
    assert res.ttfb_ms >= 0
    assert "Meta Pixel" in res.detected_pixels
    assert "Google Analytics 4" in res.detected_pixels

