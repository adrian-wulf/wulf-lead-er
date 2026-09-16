from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest

from wulf_web_leader.adapters.gmaps_scraper import (
    parse_ndjson_line,
    is_gmaps_scraper_available,
    get_gmaps_scraper_bin,
    scrape_google_maps,
)


def test_gmaps_scraper_available():
    bin_path = get_gmaps_scraper_bin()
    assert bin_path is not None
    assert bin_path.is_file()
    assert is_gmaps_scraper_available() is True


def test_parse_ndjson_line_full():
    sample = {
        "title": "Salon Fryzjerski Bella",
        "category": "Fryzjer",
        "categories": ["Fryzjer", "Salon kosmetyczny"],
        "address": "ul. Świdnicka 10, 50-068 Wrocław",
        "phone": "+48 71 123 45 67",
        "web_site": "https://bellafryzjer.pl",
        "review_rating": 4.9,
        "review_count": 142,
        "latitude": 51.107,
        "longtitude": 17.038,
        "data_id": "0x470fe9c8b7f8c1:0x123456",
        "link": "https://maps.example.com/place/123",
        "status": "OPERATIONAL",
        "complete_address": {
            "city": "Wrocław",
            "street": "Świdnicka 10",
        }
    }

    lead = parse_ndjson_line(sample, country="PL", default_city="Wrocław")
    assert lead is not None
    assert lead.name == "Salon Fryzjerski Bella"
    assert lead.website == "https://bellafryzjer.pl"
    assert lead.website_kind == "own"
    assert lead.website_source == "google_maps"
    assert lead.source == "google_maps"
    assert lead.phone == "+48 71 123 45 67"
    assert lead.phone_type == "landline"
    assert lead.whatsapp_url is None
    assert lead.google_maps_url == "https://maps.example.com/place/123"
    assert lead.open_state == "OPERATIONAL"
    assert lead.rating == 4.9
    assert lead.reviews_count == 142
    assert lead.city == "Wrocław"
    assert lead.street == "Świdnicka 10"


def test_parse_ndjson_line_no_website():
    sample = {
        "title": "Warsztat Janusz",
        "category": "Mechanik samochodowy",
        "phone": "+48 600 000 000",
        "web_site": None,
        "is_closed": False,
        "review_rating": 4.7,
        "review_count": 28,
        "latitude": 51.11,
        "longitude": 17.04,
    }

    lead = parse_ndjson_line(sample, country="PL", default_city="Wrocław")
    assert lead is not None
    assert lead.name == "Warsztat Janusz"
    assert lead.website is None
    assert lead.website_kind == "none"
    assert lead.website_source == "none"
    assert lead.phone_type == "mobile"
    assert lead.whatsapp_url == "https://wa.me/48600000000"
    assert lead.open_state == "open"
    assert lead.rating == 4.7
    assert lead.reviews_count == 28


@pytest.mark.asyncio
async def test_scrape_google_maps_cmd_radius_and_depth():
    with patch("wulf_web_leader.adapters.gmaps_scraper.get_gmaps_scraper_bin") as mock_bin, \
         patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_bin.return_value = Path("/fake/bin/google_maps_scraper")
        proc = AsyncMock()
        proc.communicate.return_value = (b"", b"")
        proc.returncode = 0
        mock_exec.return_value = proc

        await scrape_google_maps(
            query="hydraulik",
            lat=50.0,
            lon=20.0,
            radius_km=12.5,
        )

        assert mock_exec.called
        cmd_args = mock_exec.call_args[0]
        assert "-radius" in cmd_args
        radius_idx = cmd_args.index("-radius")
        assert cmd_args[radius_idx + 1] == "12500"
        assert "-depth" in cmd_args
        depth_idx = cmd_args.index("-depth")
        assert cmd_args[depth_idx + 1] == "2"
