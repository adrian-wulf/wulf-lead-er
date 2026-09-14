"""Dedicated test suite for Phase 1: Registry data (CEIDG), Telephony classification (PL/DE),
WhatsApp links, and Google Maps scraper configuration.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from wulf_web_leader.adapters.pl_ceidg import CEIDGAdapter
from wulf_web_leader.adapters.osm import (
    classify_phone_type,
    get_whatsapp_url,
    normalize_phone_number,
)
from wulf_web_leader.adapters.gmaps_scraper import (
    parse_ndjson_line,
    scrape_google_maps,
)
from wulf_web_leader.models import CanonicalLead


# ==========================================
# 1. CEIDG Registry Parsing (Owner, NIP, REGON)
# ==========================================

@pytest.mark.asyncio
async def test_ceidg_enrichment_owner_nip_regon_and_phone():
    """Verify CEIDG payload is correctly parsed into CanonicalLead owner, NIP, REGON and phone."""
    lead = CanonicalLead(
        source="osm",
        source_id="node/101",
        name="Hydraulik Jan Kowalski",
        city="Rzeszów",
        country="PL",
        website=None,
        industry_label="Hydraulik",
    )

    mock_response_data = {
        "firmy": [
            {
                "nazwa": "Hydraulik Jan Kowalski",
                "status": "AKTYWNY",
                "glownyPkd": "43.22.Z",
                "nip": "1234567890",
                "regon": "987654321",
                "wlasciciel": {
                    "imie": "Jan",
                    "nazwisko": "Kowalski",
                },
                "telefon": "+48 601 234 567",
            }
        ]
    }

    from unittest.mock import MagicMock

    adapter = CEIDGAdapter(api_token="mock_token_secret")
    assert adapter.is_available() is True

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    enriched = await adapter.enrich_lead(lead, client=mock_client)

    assert enriched.registry_status == "active"
    assert enriched.industry_code == "43.22.Z"
    assert enriched.owner_name == "Jan Kowalski"
    assert enriched.nip == "1234567890"
    assert enriched.regon == "987654321"
    assert enriched.phone == "+48601234567"
    assert enriched.phone_type == "mobile"
    assert enriched.whatsapp_url == "https://wa.me/48601234567"


@pytest.mark.asyncio
async def test_ceidg_inactive_status_parsing():
    """Verify CEIDG inactive/suspended businesses are marked as inactive."""
    from unittest.mock import MagicMock

    lead = CanonicalLead(
        source="osm",
        source_id="node/102",
        name="Stary Warsztat",
        city="Kraków",
        country="PL",
        industry_label="Mechanik",
    )

    mock_response_data = {
        "firmy": [
            {
                "nazwa": "Stary Warsztat",
                "status": "ZAWIESZONY",
                "nip": "5556667788",
                "wlasciciel": {"imie": "Adam", "nazwisko": "Nowak"},
            }
        ]
    }

    adapter = CEIDGAdapter(api_token="test_token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    enriched = await adapter.enrich_lead(lead, client=mock_client)
    assert enriched.registry_status == "inactive"
    assert enriched.owner_name == "Adam Nowak"
    assert enriched.nip == "5556667788"


# ==========================================
# 2. Telephony Classification (PL & DE)
# ==========================================

def test_classify_phone_type_pl():
    """Test Polish phone numbers: mobile vs landline vs unknown."""
    # Mobile prefixes (45, 50, 51, 53, 57, 60, 66, 69, 72, 73, 78, 79, 88)
    assert classify_phone_type("+48 501 234 567", "PL") == "mobile"
    assert classify_phone_type("601-234-567", "PL") == "mobile"
    assert classify_phone_type("+48691000111", "PL") == "mobile"
    assert classify_phone_type("784 555 666", "PL") == "mobile"
    assert classify_phone_type("+48 451 222 333", "PL") == "mobile"
    assert classify_phone_type("888 123 456", "PL") == "mobile"

    # Landline area codes (17 Rzeszów, 22 Warszawa, 12 Kraków, 71 Wrocław, etc.)
    assert classify_phone_type("+48 17 850 00 00", "PL") == "landline"
    assert classify_phone_type("22 123 45 67", "PL") == "landline"
    assert classify_phone_type("+48123456789", "PL") == "landline"
    assert classify_phone_type("71 789 00 11", "PL") == "landline"

    # Unknown / invalid
    assert classify_phone_type("", "PL") == "unknown"
    assert classify_phone_type("112", "PL") == "unknown"
    assert classify_phone_type(None, "PL") == "unknown"


def test_classify_phone_type_de():
    """Test German phone numbers: mobile vs landline vs unknown."""
    # Mobile prefixes (015x, 016x, 017x)
    assert classify_phone_type("+49 151 12345678", "DE") == "mobile"
    assert classify_phone_type("0170 1234567", "DE") == "mobile"
    assert classify_phone_type("+49 160 99887766", "DE") == "mobile"
    assert classify_phone_type("0152 34567890", "DE") == "mobile"

    # Landline area codes
    assert classify_phone_type("+49 30 12345678", "DE") == "landline"  # Berlin
    assert classify_phone_type("089 1234567", "DE") == "landline"     # Munich
    assert classify_phone_type("+49 40 889900", "DE") == "landline"   # Hamburg
    assert classify_phone_type("05123 45678", "DE") == "landline"     # Nettlingen/Söhlde

    # Unknown / invalid
    assert classify_phone_type("", "DE") == "unknown"
    assert classify_phone_type("00", "DE") == "unknown"
    assert classify_phone_type(None, "DE") == "unknown"


# ==========================================
# 3. WhatsApp Direct URL Generation
# ==========================================

def test_whatsapp_url_generation():
    """Verify wa.me link generation for mobile numbers and rejection of landlines."""
    # PL Mobile
    assert get_whatsapp_url("+48 601 234 567", "mobile") == "https://wa.me/48601234567"
    assert get_whatsapp_url("501234567", "mobile") == "https://wa.me/48501234567"
    assert get_whatsapp_url("+48 784 11 22 33", "mobile") == "https://wa.me/48784112233"

    # DE Mobile
    assert get_whatsapp_url("+49 151 12345678", "mobile") == "https://wa.me/4915112345678"
    assert get_whatsapp_url("0170 1234567", "mobile") == "https://wa.me/491701234567"

    # Landlines must return None
    assert get_whatsapp_url("+48 17 850 00 00", "landline") is None
    assert get_whatsapp_url("+49 30 123456", "landline") is None

    # Unknown or empty must return None
    assert get_whatsapp_url("+48 601 234 567", "unknown") is None
    assert get_whatsapp_url(None, "mobile") is None
    assert get_whatsapp_url("", "mobile") is None


# ==========================================
# 4. Google Maps Scraper Radius & Depth Parameters
# ==========================================

@pytest.mark.asyncio
async def test_gmaps_scraper_cmd_radius_and_depth(monkeypatch):
    """Verify scrape_google_maps passes -radius in meters and -depth to CLI binary."""
    captured_cmd = []

    async def mock_subprocess_exec(*cmd, **kwargs):
        nonlocal captured_cmd
        captured_cmd = list(cmd)
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"", b"")
        return proc

    monkeypatch.setattr(
        "wulf_web_leader.adapters.gmaps_scraper.get_gmaps_scraper_bin",
        lambda: Path("/usr/local/bin/google_maps_scraper"),
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_subprocess_exec)

    await scrape_google_maps(
        query="fryzjer",
        lat=50.041187,
        lon=21.999120,
        country="PL",
        city="Rzeszów",
        radius_km=25.0,
        max_depth=3,
        lang="pl",
    )

    assert "/usr/local/bin/google_maps_scraper" in captured_cmd
    assert "-depth" in captured_cmd
    depth_idx = captured_cmd.index("-depth")
    assert captured_cmd[depth_idx + 1] == "3"

    assert "-radius" in captured_cmd
    radius_idx = captured_cmd.index("-radius")
    # 25.0 km -> 25000 meters
    assert captured_cmd[radius_idx + 1] == "25000"

    assert "-geo" in captured_cmd
    geo_idx = captured_cmd.index("-geo")
    assert captured_cmd[geo_idx + 1] == "50.041187,21.999120"


def test_gmaps_scraper_parse_ndjson_line_fields():
    """Verify parse_ndjson_line extracts google_maps_url, open_state, and classifies phone."""
    record = {
        "title": "Salon Piękności Bella",
        "category": "Beauty salon",
        "link": "https://maps.google.com/?cid=12345678901234",
        "web_site": "https://bella-salon.pl",
        "phone": "+48 501 987 654",
        "status": "OPERATIONAL",
        "latitude": 50.04,
        "longitude": 22.00,
        "complete_address": {"city": "Rzeszów", "street": "Kopernika 5"},
        "review_rating": 4.8,
        "review_count": 120,
    }

    lead = parse_ndjson_line(
        data=record,
        country="PL",
        default_city="Rzeszów",
        vertical_id="hair",
    )

    assert lead is not None
    assert lead.name == "Salon Piękności Bella"
    assert lead.google_maps_url == "https://maps.google.com/?cid=12345678901234"
    assert lead.open_state == "OPERATIONAL"
    assert lead.phone == "+48 501 987 654"
    assert lead.phone_type == "mobile"
    assert lead.whatsapp_url == "https://wa.me/48501987654"
    assert lead.rating == 4.8
    assert lead.reviews_count == 120
