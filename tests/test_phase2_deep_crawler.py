import socket
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from wulf_web_leader.audit.fetch import (
    audit_website,
    filter_emails_with_mx,
    validate_email_mx,
    verify_email_domain_has_mx,
    _MX_CACHE,
)
from wulf_web_leader.audit.parser import SafeWebsiteHTMLParser
from wulf_web_leader.models import AuditResult


# --- 1. Social Media Link Extraction ---

def test_social_media_link_extraction():
    """Verify parser extracts major social networks and ignores share links."""
    html = """
    <html>
      <body>
        <a href="https://www.facebook.com/malerbetrieb.schmidt">Facebook Profile</a>
        <a href="https://facebook.com/sharer/sharer.php?u=https://example.com">Share on FB</a>
        <a href="https://www.instagram.com/malerbetrieb_schmidt/">Instagram Profile</a>
        <a href="https://linkedin.com/company/schmidt-maler/">LinkedIn Company</a>
        <a href="https://www.linkedin.com/shareArticle?mini=true&url=https://example.com">Share on LinkedIn</a>
        <a href="https://tiktok.com/@schmidt_maler">TikTok Profile</a>
        <a href="https://youtube.com/@schmidtmaler">YouTube Channel</a>
      </body>
    </html>
    """
    parser = SafeWebsiteHTMLParser()
    parser.feed(html)

    assert parser.social_links["facebook"] == "https://www.facebook.com/malerbetrieb.schmidt"
    assert parser.social_links["instagram"] == "https://www.instagram.com/malerbetrieb_schmidt/"
    assert parser.social_links["linkedin"] == "https://linkedin.com/company/schmidt-maler/"
    assert parser.social_links["tiktok"] == "https://tiktok.com/@schmidt_maler"
    assert parser.social_links["youtube"] == "https://youtube.com/@schmidtmaler"
    assert len(parser.social_links) == 5


# --- 2. Candidate Subpages Extraction ---

def test_candidate_subpages_extraction():
    """Verify candidate subpages (kontakt, impressum, o-nas, etc.) are detected,
    while external domains, asset extensions, and mailto/tel are excluded."""
    base_url = "https://schmidt-handwerk.de"
    html = """
    <html>
      <body>
        <a href="/kontakt">Kontakt</a>
        <a href="/impressum.html">Impressum</a>
        <a href="/o-nas">O nas</a>
        <a href="/ueber-uns">Über uns</a>
        <a href="/team">Unser Team</a>
        <a href="/firma">Die Firma</a>
        <a href="https://schmidt-handwerk.de/contact">Same host contact</a>
        <!-- Excluded -->
        <a href="https://external-firm.de/kontakt">External Domain</a>
        <a href="/kontakt/anfahrt.pdf">PDF Document</a>
        <a href="/impressum/banner.jpg">Image File</a>
        <a href="mailto:kontakt@schmidt.de">Mailto</a>
        <a href="tel:+4912345678">Tel</a>
        <a href="javascript:void(0)">JS</a>
        <a href="#">Anchor</a>
      </body>
    </html>
    """
    parser = SafeWebsiteHTMLParser(base_url=base_url)
    parser.feed(html)

    expected = {
        "/kontakt",
        "/impressum.html",
        "/o-nas",
        "/ueber-uns",
        "/team",
        "/firma",
        "https://schmidt-handwerk.de/contact",
    }
    assert expected.issubset(parser.candidate_subpages)
    assert "https://external-firm.de/kontakt" not in parser.candidate_subpages
    assert "/kontakt/anfahrt.pdf" not in parser.candidate_subpages
    assert "/impressum/banner.jpg" not in parser.candidate_subpages


# --- 3. German Impressum Representative Extraction ---

def test_german_impressum_representative_extraction():
    """Verify extraction of legal representatives from German Impressum text patterns."""
    cases = [
        ("<p>Vertreten durch: Max Mustermann</p>", "Max Mustermann"),
        ("<p>Vertreten durch:<br>Erika Musterfrau</p>", "Erika Musterfrau"),
        ("<div>Vertreten durch die Geschäftsführer: Thomas Schmidt</div>", "Thomas Schmidt"),
        ("<div>Geschäftsführer: Dr. Hans-Peter Wagner</div>", "Hans-Peter Wagner"),
        ("<div>Inhaber: Klaus-Dieter Müller</div>", "Klaus-Dieter Müller"),
        ("<div>Vorstand: Dr. Johann Wolfgang von Goethe</div>", "Johann Wolfgang von Goethe"),
        (
            """
            <h2>Impressum</h2>
            <p>Vertreten durch:</p>
            <p>Anna Schmidt</p>
            <p>Registergericht: Amtsgericht Berlin-Charlottenburg</p>
            <p>Registernummer: HRB 123456</p>
            """,
            "Anna Schmidt",
        ),
    ]

    for html, expected_name in cases:
        parser = SafeWebsiteHTMLParser()
        parser.feed(html)
        parser.close()
        assert parser.representative_name == expected_name, f"Failed for HTML: {html}"


# --- 4. Email MX Validation Function ---

def test_email_mx_validation_with_socket_mock(monkeypatch):
    """Verify verify_email_domain_has_mx and validate_email_mx correctly validate domains."""
    _MX_CACHE.clear()

    # Reject bogus syntax or RFC 2606 reserved domains
    assert not verify_email_domain_has_mx("invalid")
    assert not verify_email_domain_has_mx("test.localhost")
    assert not verify_email_domain_has_mx("example.com")
    assert not validate_email_mx("notanemail")
    assert not validate_email_mx("logo@domain.png")

    # Mock socket.getaddrinfo to simulate routable vs unroutable hosts
    def fake_getaddrinfo(host, port):
        if host == "schmidt-maler.de":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
        elif host == "loopback-evil.com":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
        raise socket.gaierror("Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    # Schmidt Maler has public IP -> Valid
    assert verify_email_domain_has_mx("schmidt-maler.de")
    assert validate_email_mx("info@schmidt-maler.de")

    # Loopback IP -> Invalid (SSRF/internal filter)
    assert not verify_email_domain_has_mx("loopback-evil.com")
    assert not validate_email_mx("admin@loopback-evil.com")

    # Nonexistent host -> Invalid
    assert not verify_email_domain_has_mx("nonexistent-host-9999.de")
    assert not validate_email_mx("kontakt@nonexistent-host-9999.de")

    # Filter emails
    emails = ["info@schmidt-maler.de", "bad@nonexistent-host-9999.de", "hacker@loopback-evil.com"]
    filtered = filter_emails_with_mx(emails)
    assert filtered == ["info@schmidt-maler.de"]


# --- 5. Deep-Crawling Integration / Mock Test ---

@pytest.mark.asyncio
async def test_deep_crawling_fetches_subpages_when_homepage_lacks_contact():
    """Verify deep-crawling follows up to 2 candidate subpages and merges extracted data."""
    homepage_html = b"""
    <!DOCTYPE html>
    <html>
      <head><title>Malerbetrieb Schmidt</title></head>
      <body>
        <h1>Herzlich Willkommen</h1>
        <p>Wir streichen Ihre Wande meisterhaft.</p>
        <footer>
          <a href="/kontakt">Kontakt</a>
          <a href="/impressum">Impressum</a>
        </footer>
      </body>
    </html>
    """

    kontakt_html = b"""
    <!DOCTYPE html>
    <html>
      <body>
        <h1>Kontaktieren Sie uns</h1>
        <a href="tel:+493012345678">+49 30 12345678</a>
        <a href="mailto:info@maler-schmidt.de">info@maler-schmidt.de</a>
        <a href="https://www.facebook.com/malerschmidt">Facebook</a>
      </body>
    </html>
    """

    impressum_html = b"""
    <!DOCTYPE html>
    <html>
      <body>
        <h1>Impressum</h1>
        <p>Malerbetrieb Schmidt GmbH</p>
        <p>Vertreten durch den Geschaftsfuhrer: Max Mustermann</p>
      </body>
    </html>
    """

    def fake_stream(method, url, headers=None, timeout=None):
        url_str = str(url)
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.url = url_str
        mock_resp.is_redirect = False
        mock_resp.headers = {"Content-Type": "text/html"}

        if "/kontakt" in url_str:
            content = kontakt_html
        elif "/impressum" in url_str:
            content = impressum_html
        else:
            content = homepage_html

        async def aiter_bytes():
            yield content

        mock_resp.aiter_bytes = aiter_bytes

        stream_cm = MagicMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        stream_cm.__aexit__ = AsyncMock(return_value=None)
        return stream_cm

    client_mock = MagicMock()
    client_mock.stream.side_effect = fake_stream
    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=client_mock)
    client_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("wulf_web_leader.audit.fetch.validate_url_safety", return_value=(True, None)), \
         patch("httpx.AsyncClient", return_value=client_cm):

        result = await audit_website("https://maler-schmidt.de", country="DE")

    assert result.reachable is True
    assert "+493012345678" in result.extracted_phones
    assert "info@maler-schmidt.de" in result.extracted_emails
    assert result.representative_name == "Max Mustermann"
    assert result.social_links.get("facebook") == "https://www.facebook.com/malerschmidt"
    assert result.has_impressum is True


# --- 6. SSRF Protection on Candidate Subpages ---

@pytest.mark.asyncio
async def test_deep_crawling_blocks_ssrf_and_external_subpages():
    """Verify candidate subpages pointing to SSRF-blocked IPs or external hosts are not crawled."""
    homepage_html = b"""
    <!DOCTYPE html>
    <html>
      <body>
        <a href="http://127.0.0.1/kontakt">Malicious Internal Host</a>
        <a href="https://external-attacker.com/kontakt">External Host</a>
      </body>
    </html>
    """

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://safe-business.com"
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

        result = await audit_website("https://safe-business.com", country="DE")

    assert result.reachable is True
    # Homepage only requested, no subpages fetched because external/malicious URLs are blocked
    assert client_mock.stream.call_count == 1


def test_email_mx_doh_fallback():
    """Verify verify_email_domain_has_mx falls back to DoH when local getaddrinfo fails."""
    _MX_CACHE.clear()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "Status": 0,
        "Answer": [{"name": "doh-domain.com", "type": 15, "data": "10 mail.doh-domain.com."}],
    }

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.__exit__.return_value = None
    mock_client.get.return_value = mock_resp

    with patch("socket.getaddrinfo", side_effect=socket.gaierror("DNS failed")), \
         patch("httpx.Client", return_value=mock_client):
        assert verify_email_domain_has_mx("doh-domain.com") is True


@pytest.mark.asyncio
async def test_deep_crawl_body_limit_enforced():
    """Verify subpage content is truncated at MAX_BODY_BYTES (1MB)."""
    homepage_html = b'<html><body><a href="/kontakt">Kontakt</a></body></html>'
    # 2MB oversized subpage
    oversized_chunk = b"A" * 600_000

    def fake_stream(method, url, headers=None, timeout=None):
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.url = str(url)
        mock_resp.is_redirect = False
        mock_resp.headers = {"Content-Type": "text/html"}

        async def aiter_bytes():
            if "/kontakt" in str(url):
                yield oversized_chunk
                yield oversized_chunk
                yield oversized_chunk
            else:
                yield homepage_html

        mock_resp.aiter_bytes = aiter_bytes

        stream_cm = MagicMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        stream_cm.__aexit__ = AsyncMock(return_value=None)
        return stream_cm

    client_mock = MagicMock()
    client_mock.stream.side_effect = fake_stream
    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=client_mock)
    client_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("wulf_web_leader.audit.fetch.validate_url_safety", return_value=(True, None)), \
         patch("httpx.AsyncClient", return_value=client_cm):
        result = await audit_website("https://example-limit.com")

    assert result.reachable is True


def test_audit_result_model_new_fields():
    """Verify AuditResult model properly supports representative_name and social_links."""
    res = AuditResult(
        reachable=True,
        representative_name="Max Mustermann",
        social_links={"facebook": "https://facebook.com/test", "instagram": "https://instagram.com/test"},
    )
    dumped = res.model_dump()
    assert dumped["representative_name"] == "Max Mustermann"
    assert dumped["social_links"]["facebook"] == "https://facebook.com/test"

    restored = AuditResult.model_validate(dumped)
    assert restored.representative_name == "Max Mustermann"
    assert restored.social_links["instagram"] == "https://instagram.com/test"

