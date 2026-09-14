from pathlib import Path
from wulf_web_leader.adapters.gmaps_scraper import (
    parse_ndjson_line,
    is_gmaps_scraper_available,
    get_gmaps_scraper_bin,
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
    assert lead.rating == 4.7
    assert lead.reviews_count == 28
