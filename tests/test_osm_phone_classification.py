import pytest
from wulf_web_leader.adapters.osm import (
    classify_phone_type,
    get_whatsapp_url,
    OverpassClient,
)
from wulf_web_leader.models import CanonicalLead


def test_classify_phone_type_pl_mobile():
    # Various formats of Polish mobile
    assert classify_phone_type("+48 601 234 567", "PL") == "mobile"
    assert classify_phone_type("+48-500-111-222", "PL") == "mobile"
    assert classify_phone_type("48790123456", "PL") == "mobile"
    assert classify_phone_type("888123456", "PL") == "mobile"
    assert classify_phone_type("451234567", "PL") == "mobile"
    assert classify_phone_type("721234567", "PL") == "mobile"


def test_classify_phone_type_pl_landline():
    # Polish landline area codes: 17 (Rzeszów), 22 (Warszawa), 12 (Kraków), 71 (Wrocław)
    assert classify_phone_type("+48 17 850 00 00", "PL") == "landline"
    assert classify_phone_type("22 123 45 67", "PL") == "landline"
    assert classify_phone_type("+48123456789", "PL") == "landline"
    assert classify_phone_type("713456789", "PL") == "landline"


def test_classify_phone_type_de_mobile():
    # German mobile prefixes 15, 16, 17
    assert classify_phone_type("+49 151 12345678", "DE") == "mobile"
    assert classify_phone_type("+49 160 9876543", "DE") == "mobile"
    assert classify_phone_type("+49 171 5554433", "DE") == "mobile"
    assert classify_phone_type("0151 12345678", "DE") == "mobile"
    assert classify_phone_type("0170 12345678", "DE") == "mobile"


def test_classify_phone_type_de_landline():
    # German landline prefixes: 30 (Berlin), 40 (Hamburg), 89 (München), 69 (Frankfurt)
    assert classify_phone_type("+49 30 1234567", "DE") == "landline"
    assert classify_phone_type("+49 89 7654321", "DE") == "landline"
    assert classify_phone_type("030 1234567", "DE") == "landline"
    assert classify_phone_type("089 7654321", "DE") == "landline"


def test_classify_phone_type_unknown():
    assert classify_phone_type(None) == "unknown"
    assert classify_phone_type("") == "unknown"
    assert classify_phone_type("123") == "unknown"
    assert classify_phone_type("invalid-phone") == "unknown"


def test_get_whatsapp_url():
    # Mobile numbers generate correct wa.me link
    assert get_whatsapp_url("+48 601 234 567", "mobile") == "https://wa.me/48601234567"
    assert get_whatsapp_url("500111222", "mobile") == "https://wa.me/48500111222"
    assert get_whatsapp_url("+49 151 12345678", "mobile") == "https://wa.me/4915112345678"
    assert get_whatsapp_url("0151 12345678", "mobile") == "https://wa.me/4915112345678"

    # Landline and unknown return None
    assert get_whatsapp_url("+48 17 850 00 00", "landline") is None
    assert get_whatsapp_url("+48 601 234 567", "unknown") is None
    assert get_whatsapp_url(None, "mobile") is None
    assert get_whatsapp_url("", "mobile") is None


def test_osm_adapter_lead_telephony_population():
    op = OverpassClient()
    elements = [
        {
            "type": "node",
            "id": 1,
            "lat": 50.0,
            "lon": 22.0,
            "tags": {
                "name": "Mobilny Hydraulik",
                "phone": "+48 600 123 456",
            },
        },
        {
            "type": "node",
            "id": 2,
            "lat": 50.1,
            "lon": 22.1,
            "tags": {
                "name": "Stacjonarny Serwis",
                "phone": "+48 17 850 00 00",
            },
        },
    ]

    leads = op.parse_elements_to_leads(
        elements=elements,
        country="PL",
        default_city="Rzeszów",
        industry_label="Hydraulik",
    )

    assert len(leads) == 2
    assert leads[0].phone_type == "mobile"
    assert leads[0].whatsapp_url == "https://wa.me/48600123456"

    assert leads[1].phone_type == "landline"
    assert leads[1].whatsapp_url is None
