"""Dedicated test suite for Phase 3: Marketing UX, Tracking pixel detection (Meta, GA4, GTM, TikTok),
TTFB latency recording in AuditResult, cold outreach pitch hooks, and HTML report badge/CTA rendering.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from wulf_web_leader.audit.parser import SafeWebsiteHTMLParser
from wulf_web_leader.audit.fetch import audit_website
from wulf_web_leader.export.report import generate_html_report
from wulf_web_leader.models import AuditResult, CanonicalLead
from wulf_web_leader.score.hooks import (
    generate_greeting,
    generate_pitch_hooks,
    generate_salutation,
)


# ==========================================
# 1. Pixel Detection (Meta, GA4, GTM, TikTok)
# ==========================================

def test_parser_detects_meta_pixel():
    """Verify parser identifies Meta/Facebook pixel scripts and noscript tracking tags."""
    samples = [
        "<script>!function(f,b,e,v,n,t,s){fbq('init', '1234567890'); fbq('track', 'PageView');}</script>",
        '<script src="https://connect.facebook.net/en_US/fbevents.js"></script>',
        '<noscript><img height="1" width="1" src="https://www.facebook.com/tr?id=999&ev=PageView"/></noscript>',
    ]
    for sample in samples:
        parser = SafeWebsiteHTMLParser()
        parser.feed(sample)
        parser.close()
        assert "Meta Pixel" in parser.detected_pixels
        assert "Meta Pixel" in parser.pixels


def test_parser_detects_ga4():
    """Verify parser identifies Google Analytics 4 tags (gtag.js, G- ID)."""
    samples = [
        '<script async src="https://www.googletagmanager.com/gtag/js?id=G-ABC12345"></script>',
        "<script>window.dataLayer = window.dataLayer || []; gtag('config', 'G-XYZ987');</script>",
        '<script src="https://www.google-analytics.com/g/collect?v=2&tid=G-TEST"></script>',
    ]
    for sample in samples:
        parser = SafeWebsiteHTMLParser()
        parser.feed(sample)
        parser.close()
        assert "Google Analytics 4" in parser.detected_pixels
        assert "Google Analytics 4" in parser.pixels


def test_parser_detects_gtm():
    """Verify parser identifies Google Tag Manager containers."""
    html = """
    <script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
    new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
    j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
    'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
    })(window,document,'script','dataLayer','GTM-WULF123');</script>
    """
    parser = SafeWebsiteHTMLParser()
    parser.feed(html)
    parser.close()
    assert "Google Tag Manager" in parser.detected_pixels
    assert "Google Tag Manager" in parser.pixels


def test_parser_detects_tiktok_pixel():
    """Verify parser identifies TikTok Pixel script and ttq.load SDK invocation."""
    samples = [
        '<script src="https://analytics.tiktok.com/i18n/pixel/events.js"></script>',
        "<script>!function (w, d, t) { ttq.load('TTK123456'); ttq.page(); }(window, document, 'ttq');</script>",
    ]
    for sample in samples:
        parser = SafeWebsiteHTMLParser()
        parser.feed(sample)
        parser.close()
        assert "TikTok Pixel" in parser.detected_pixels
        assert "TikTok Pixel" in parser.pixels


def test_parser_detects_multiple_pixels_sorted():
    """Verify multiple tracking pixels are detected, deduplicated and alphabetically sorted."""
    html = """
    <html>
      <head>
        <script src="https://connect.facebook.net/en_US/fbevents.js"></script>
        <script src="https://www.googletagmanager.com/gtm.js?id=GTM-999"></script>
        <script src="https://analytics.tiktok.com/i18n/pixel/events.js"></script>
        <script src="https://www.googletagmanager.com/gtag/js?id=G-112233"></script>
      </head>
      <body><h1>Demo</h1></body>
    </html>
    """
    parser = SafeWebsiteHTMLParser()
    parser.feed(html)
    parser.close()
    assert parser.pixels == ["Google Analytics 4", "Google Tag Manager", "Meta Pixel", "TikTok Pixel"]


# ==========================================
# 2. TTFB Latency in AuditResult & Fetch
# ==========================================

def test_audit_result_model_ttfb_field():
    """Verify AuditResult contains ttfb_ms with default None."""
    res_default = AuditResult()
    assert res_default.ttfb_ms is None

    res_measured = AuditResult(reachable=True, ttfb_ms=1850.5)
    assert res_measured.ttfb_ms == 1850.5


@pytest.mark.asyncio
async def test_audit_website_measures_ttfb_and_extracts_pixels():
    """Verify audit_website records ttfb_ms and populates detected_pixels."""
    homepage_html = b"""
    <!DOCTYPE html>
    <html>
      <head>
        <title>Salon Fryzjerski</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://connect.facebook.net/en_US/fbevents.js"></script>
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-12345"></script>
      </head>
      <body>
        <p>Tel: +48 601 222 333</p>
      </body>
    </html>
    """
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://salon-fryzur.pl"
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
        result = await audit_website("https://salon-fryzur.pl", country="PL")

    assert result.reachable is True
    assert result.is_https is True
    assert result.ttfb_ms is not None
    assert result.ttfb_ms >= 0
    assert "Meta Pixel" in result.detected_pixels
    assert "Google Analytics 4" in result.detected_pixels


# ==========================================
# 3. Marketing Pitch Hooks (Cold Call / Email)
# ==========================================

def test_marketing_hooks_missing_pixels_pl_and_de():
    """Verify cold outreach hooks mention missing pixels when website has no tracking."""
    lead_pl = CanonicalLead(
        country="PL",
        name="Serwis Autokompleks",
        city="Rzeszów",
        phone="+48 17 800 00 00",
        website="https://autokompleks.pl",
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
    assert any("Pixel" in h and "Google Analytics" in h for h in hooks_pl)

    lead_de = CanonicalLead(
        country="DE",
        name="Maler Meister Schmidt",
        city="Hannover",
        phone="+49 511 123456",
        website="https://maler-schmidt.de",
        website_kind="own",
        source="osm",
        source_id="node/2",
        industry_label="Maler",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=True,
            detected_pixels=[],
        ),
    )
    hooks_de = generate_pitch_hooks(lead_de, lang="de")
    assert any("Meta-Pixel" in h or "Meta Pixel" in h or "Google Analytics" in h for h in hooks_de)


def test_marketing_hooks_high_ttfb():
    """Verify slow TTFB (>1.5s) produces performance hook for redesign pitching."""
    lead = CanonicalLead(
        country="PL",
        name="Wolna Strona",
        city="Warszawa",
        phone="+48 22 123 45 67",
        website="https://wolnastrona.pl",
        website_kind="own",
        source="osm",
        source_id="node/3",
        industry_label="Usługi",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=True,
            ttfb_ms=2800.0,
        ),
    )
    hooks = generate_pitch_hooks(lead, lang="pl")
    assert any("TTFB" in h and "2800" in h for h in hooks)


def test_personalized_salutation_with_owner_name():
    """Verify salutation and greeting use owner's name when available."""
    lead_pl = CanonicalLead(
        country="PL",
        name="Zakład Hydrauliczny Jan Kowalski",
        city="Rzeszów",
        owner_name="Piotr Zieliński",
        source="osm",
        source_id="node/4",
        industry_label="Hydraulik",
    )
    assert generate_salutation(lead_pl, lang="pl") == "Dzień dobry Panie/Pani Piotr,"
    greeting_pl = generate_greeting(lead_pl, lang="pl")
    assert greeting_pl == "Dzień dobry Panie/Pani Piotr,"

    lead_de_male = CanonicalLead(
        country="DE",
        name="Schmidt Sanitär GmbH",
        city="Berlin",
        owner_name="Thomas Schmidt",
        source="osm",
        source_id="node/5",
        industry_label="Sanitär",
    )
    assert generate_salutation(lead_de_male, lang="de") == "Sehr geehrte(r) Frau/Herr Thomas Schmidt,"
    assert generate_greeting(lead_de_male, lang="de") == "Sehr geehrte(r) Frau/Herr Thomas Schmidt,"

    lead_no_owner_pl = CanonicalLead(
        country="PL",
        name="Anonimowy Zakład",
        city="Kraków",
        source="osm",
        source_id="node/6",
        industry_label="Usługi",
    )
    assert generate_greeting(lead_no_owner_pl, lang="pl") == "Dzień dobry,"

    lead_no_owner_de = CanonicalLead(
        country="DE",
        name="Anonymer Betrieb",
        city="Hamburg",
        source="osm",
        source_id="node/7",
        industry_label="Handwerk",
    )
    assert generate_greeting(lead_no_owner_de, lang="de") == "Sehr geehrte Damen und Herren,"


# ==========================================
# 4. HTML Report Badges & WhatsApp CTA Rendering
# ==========================================

def test_html_report_renders_whatsapp_and_owner_badges(tmp_path: Path):
    """Verify generated HTML report contains WhatsApp direct CTA, owner badge, NIP, and phone type."""
    lead_mobile = CanonicalLead(
        country="PL",
        name="Elektryk Błyskawica",
        city="Rzeszów",
        street="Lwowska 15",
        phone="+48 601 234 567",
        phone_type="mobile",
        whatsapp_url="https://wa.me/48601234567",
        owner_name="Tadeusz Błysk",
        nip="1234567890",
        regon="987654321",
        website="https://blyskawica-elektryk.pl",
        website_kind="own",
        source="osm",
        source_id="node/10",
        industry_label="Elektryk",
        score=85,
        verdict="hot",
        audit=AuditResult(
            reachable=True,
            is_https=False,
            has_viewport=False,
            ttfb_ms=2200.0,
            detected_pixels=[],
            social_links={"facebook": "https://facebook.com/blyskawica", "instagram": "https://instagram.com/blyskawica"},
        ),
    )

    out_file = tmp_path / "report_test.html"
    report_path = generate_html_report([lead_mobile], output_path=out_file)
    assert report_path.is_file()

    content = report_path.read_text(encoding="utf-8")

    # WhatsApp CTA
    assert "https://wa.me/48601234567" in content
    assert "WhatsApp" in content

    # Registry badges
    assert "Tadeusz Błysk" in content
    assert "1234567890" in content

    # Phone type
    assert "Komórka" in content

    # Social links
    assert "https://facebook.com/blyskawica" in content
    assert "https://instagram.com/blyskawica" in content

    # Pitch modal / hooks
    assert "TTFB" in content
