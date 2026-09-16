from wulf_web_leader.adapters.osm import extract_domain_from_email, is_corporate_entity, OverpassClient


def test_extract_domain_from_custom_email():
    assert extract_domain_from_email("info@pefeld.de") == "pefeld.de"
    assert extract_domain_from_email("kontakt@firma-budowlana.pl") == "firma-budowlana.pl"
    assert extract_domain_from_email("mailto:office@dach-bau.de") == "dach-bau.de"


def test_extract_domain_ignores_freemail():
    freemail_examples = [
        "jan.kowalski@gmail.com",
        "adam@wp.pl",
        "biuro@onet.pl",
        "serwis@interia.pl",
        "kontakt@t-online.de",
        "schmidt@gmx.de",
        "meier@web.de",
        "firma@yahoo.com",
        "info@hotmail.com",
        "szef@o2.pl",
    ]
    for email in freemail_examples:
        assert extract_domain_from_email(email) is None


def test_is_corporate_entity():
    assert is_corporate_entity("Feldheim & Söhne GmbH") is True
    assert is_corporate_entity("Schmidt & Partner GbR") is True
    assert is_corporate_entity("Müller Haustechnik AG") is True
    assert is_corporate_entity("Hydraulika Polska Sp. z o.o.") is True
    assert is_corporate_entity("Auto Serwis S.A.") is True

    # Unincorporated businesses / sole traders
    assert is_corporate_entity("Jan Kowalski Usługi Hydrauliczne") is False
    assert is_corporate_entity("Klaus Meier Sanitärbetrieb") is False
    assert is_corporate_entity("Złota Rączka 24h") is False


def test_osm_adapter_discovers_website_from_email():
    client = OverpassClient()
    elements = [
        {
            "type": "node",
            "id": 7208369273,
            "lat": 52.37,
            "lon": 9.74,
            "tags": {
                "name": "Feldheim & Söhne GmbH",
                "craft": "plumber",
                "contact:email": "info@pefeld.de",
                "phone": "+49 511 123456",
            },
        }
    ]

    leads = client.parse_elements_to_leads(
        elements=elements,
        country="DE",
        default_city="Hannover",
        industry_label="Klempner",
    )

    assert len(leads) == 1
    lead = leads[0]
    assert lead.email == "info@pefeld.de"
    assert lead.website == "https://pefeld.de"
    assert lead.website_kind == "own"
