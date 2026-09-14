"""
Comprehensive tests for lead filtering, relevance verification, and targeting hygiene in WULF LEAD.ER.
"""

import pytest
from wulf_web_leader.audit.lead_filter import is_lead_relevant
from wulf_web_leader.audit.verifier import (
    generate_domain_candidates,
    verify_entity_match,
    GENERIC_DICTIONARY_WORDS,
)
from wulf_web_leader.adapters.osm import OverpassClient
from wulf_web_leader.adapters.gmaps_scraper import parse_ndjson_line


def test_vorwerk_and_espresso_service_filtered_out_for_it():
    """Verify that appliance and coffee machine repairs are rejected for IT verticals."""
    # 1. Vorwerk Thermomix service
    is_rel, reason = is_lead_relevant("Autoryzowany serwis Vorwerk Polska", vertical_id="informatyk")
    assert is_rel is False
    assert "vorwerk" in reason.lower()

    # 2. Espresso Service
    is_rel2, reason2 = is_lead_relevant("Espresso Service naprawa ekspresow do kawy", vertical_id="informatyk")
    assert is_rel2 is False
    assert "ekspres" in reason2.lower() or "kawa" in reason2.lower()

    # 3. AGD repair
    is_rel3, reason3 = is_lead_relevant("Naprawa pralek i lodówek AGD Serwis", vertical_id="informatyk")
    assert is_rel3 is False

    # 4. TV repair
    is_rel4, reason4 = is_lead_relevant("Serwis Naprawa Telewizorów RTV", vertical_id="informatyk")
    assert is_rel4 is False


def test_public_institutions_rejected_across_verticals():
    """Verify that public schools, city halls, hospitals, and police stations are rejected."""
    institutions = [
        ("Urząd Miasta Krakowa", "prawnik"),
        ("Gmina Wieliczka Urząd Stanu Cywilnego", "ksiegowy"),
        ("Szkoła Podstawowa nr 15 im. Jana Pawła II", "szkola_jezykowa"),
        ("VII Liceum Ogólnokształcące", "szkola_jazdy"),
        ("Szpital Uniwersytecki w Krakowie", "lekarz"),
        ("Komisariat Policji I w Krakowie", "ochrona"),
        ("Komenda Miejska Państwowej Straży Pożarnej", "budowlanka"),
        ("Rathaus München Bürgeramt", "prawnik"),
        ("Polizeipräsidium Berlin", "ochrona"),
        ("Städtisches Krankenhaus", "lekarz"),
    ]
    for name, vert in institutions:
        is_rel, reason = is_lead_relevant(name, vertical_id=vert)
        assert is_rel is False, f"Expected '{name}' to be rejected for vertical '{vert}'"
        assert "publiczna" in (reason or "").lower() or "samorządowa" in (reason or "").lower()


def test_chain_brands_and_franchises_rejected():
    """Verify that major retail chains, supermarkets, gas stations, and fast foods are rejected."""
    chains = [
        ("McDonald's", "restaurant"),
        ("KFC Galeria Krakowska", "restaurant"),
        ("Biedronka", "piekarz"),
        ("Żabka Cafe", "kawiarnia"),
        ("Lidl Polska", "piekarz"),
        ("Stacja Paliw Orlen", "mechanik"),
        ("Media Expert", "serwis_komputerowy"),
        ("Castorama Kraków", "budowlanka"),
        ("Rossmann", "kosmetyczka"),
    ]
    for name, vert in chains:
        is_rel, reason = is_lead_relevant(name, vertical_id=vert)
        assert is_rel is False, f"Expected chain '{name}' to be rejected for '{vert}'"
        assert "sieć" in (reason or "").lower() or "franczyza" in (reason or "").lower()


def test_legitimate_businesses_accepted():
    """Verify that genuine target businesses pass relevance checks cleanly."""
    valid = [
        ("CodeCraft Software House", "informatyk"),
        ("RevComp Usługi Informatyczne", "informatyk"),
        ("Jan Kowalski Serwis Laptopów", "serwis_komputerowy"),
        ("Studio Graficzne Pixel", "tworzenie_stron"),
        ("Hydraulik24 Pogotowie Kanalizacyjne", "plumbers"),
        ("Instal-Bud Elektroinstalacje", "electricians"),
        ("Auto Naprawa Nowak", "auto_repair"),
        ("FitStudio Siłownia & Fitness", "gym"),
        ("Kancelaria Adwokacka Anna Wiśniewska", "prawnik"),
    ]
    for name, vert in valid:
        is_rel, reason = is_lead_relevant(name, vertical_id=vert)
        assert is_rel is True, f"Expected '{name}' to pass for '{vert}', but was rejected: {reason}"


def test_espresso_pl_not_generated_for_espresso_service():
    """Verify that generic single-word dictionary domains are NOT generated for multi-word companies."""
    candidates = generate_domain_candidates(
        company_name="Espresso Service naprawa ekspresow do kawy",
        city="Kraków",
        phone="+48509434841",
        country="PL",
    )
    # Generic standalone dictionary domain MUST NOT be present
    assert "espresso.pl" not in candidates
    assert "espresso.com.pl" not in candidates
    assert "espresso.com" not in candidates

    # Valid compound candidates may be present
    assert any("espresso" in c and ("ekspresow" in c or "krakow" in c) for c in candidates)


def test_verify_entity_match_distinguishes_generic_word_collision():
    """Verify that scattered common words without exact phrase or phone do NOT yield high match score."""
    generic_coffee_portal_html = """
    <html>
    <head><title>Sklep z kawą - ekspresy do kawy</title></head>
    <body>
    <h1>Wszystko o kawie i espresso</h1>
    <p>Oferujemy najlepsze ziarna kawy do ekspresów ciśnieniowych.</p>
    <p>Dostawa: Warszawa, Kraków, Wrocław, Poznań.</p>
    <p>Infolinia handlowa: 22 123 45 67</p>
    </body>
    </html>
    """
    score, signals, confidence = verify_entity_match(
        lead_name="Espresso Service naprawa ekspresow do kawy",
        city="Kraków",
        phone="+48509434841",
        address="Rybitwy 15",
        html_text=generic_coffee_portal_html,
    )
    # The score should be low and confidence low/mismatch because phone and address do NOT match
    assert score < 50
    assert confidence in ("low", "medium", "mismatch")
    assert confidence != "high"


def test_osm_parser_filters_out_vorwerk_and_espresso():
    """Verify that OverpassClient.parse_elements_to_leads drops Vorwerk and Espresso Service when vertical is informatyk."""
    mock_elements = [
        {
            "type": "node",
            "id": 6456284359,
            "lat": 50.0038,
            "lon": 19.9051,
            "tags": {
                "name": "Autoryzowany serwis Vorwerk Polska",
                "craft": "electronics_repair",
                "addr:city": "Kraków",
                "phone": "+48724606050",
            },
        },
        {
            "type": "way",
            "id": 751990225,
            "lat": 50.0387,
            "lon": 20.0252,
            "tags": {
                "name": "Espresso Service naprawa ekspresow do kawy",
                "craft": "electronics_repair",
                "addr:city": "Kraków",
                "phone": "+48509434841",
            },
        },
        {
            "type": "node",
            "id": 123456789,
            "lat": 50.0647,
            "lon": 19.9450,
            "tags": {
                "name": "Krak-IT Usługi Komputerowe",
                "office": "it",
                "addr:city": "Kraków",
                "phone": "+48123456789",
            },
        },
    ]

    client = OverpassClient()
    leads = client.parse_elements_to_leads(
        elements=mock_elements,
        country="PL",
        default_city="Kraków",
        industry_label="Informatyk",
        vertical_id="informatyk",
    )

    # Only Krak-IT should remain
    assert len(leads) == 1
    assert leads[0].name == "Krak-IT Usługi Komputerowe"


def test_gmaps_parser_filters_out_negative_category_and_distant_leads():
    """Verify that parse_ndjson_line filters out non-relevant categories and out-of-radius leads."""
    # 1. Coffee shop in IT scan
    lead_junk = parse_ndjson_line(
        data={
            "title": "Kawiarnia Espresso Bar",
            "category": "Kawiarnia",
            "latitude": 50.06,
            "longitude": 19.94,
        },
        country="PL",
        default_city="Kraków",
        vertical_id="informatyk",
        center_lat=50.06,
        center_lon=19.94,
        radius_km=15.0,
    )
    assert lead_junk is None

    # 2. Distant lead (80 km away from center)
    lead_far = parse_ndjson_line(
        data={
            "title": "Software House Rzeszów",
            "category": "Usługi informatyczne",
            "latitude": 50.04,
            "longitude": 21.99,  # Rzeszów (~150km from Kraków)
        },
        country="PL",
        default_city="Kraków",
        vertical_id="informatyk",
        center_lat=50.06,
        center_lon=19.94,  # Kraków
        radius_km=15.0,
    )
    assert lead_far is None

    # 3. Valid local IT lead
    lead_valid = parse_ndjson_line(
        data={
            "title": "WebMasters Kraków",
            "category": "Agencja interaktywna",
            "latitude": 50.065,
            "longitude": 19.942,
        },
        country="PL",
        default_city="Kraków",
        vertical_id="informatyk",
        center_lat=50.06,
        center_lon=19.94,
        radius_km=15.0,
    )
    assert lead_valid is not None
    assert lead_valid.name == "WebMasters Kraków"
