import pytest
from wulf_web_leader.adapters.osm import OverpassClient


def test_osm_tags_website_classification():
    op = OverpassClient()
    elements = [
        # 1. Plain website URL (own site)
        {
            "type": "node",
            "id": 1,
            "lat": 50.0,
            "lon": 20.0,
            "tags": {"name": "Hydraulik Jan", "website": "https://hydraulik-jan.pl"},
        },
        # 2. contact:website with facebook
        {
            "type": "node",
            "id": 2,
            "lat": 50.0,
            "lon": 20.0,
            "tags": {"name": "Fryzjer Anna", "contact:website": "https://facebook.com/fryzjer.anna"},
        },
        # 3. Dedicated facebook tag (URL)
        {
            "type": "node",
            "id": 3,
            "lat": 50.0,
            "lon": 20.0,
            "tags": {"name": "Auto Serwis", "facebook": "https://www.facebook.com/autoserwis"},
        },
        # 4. Dedicated contact:facebook tag (handle only)
        {
            "type": "node",
            "id": 4,
            "lat": 50.0,
            "lon": 20.0,
            "tags": {"name": "Piekarnia Chleb", "contact:facebook": "piekarnia_chleb"},
        },
        # 5. Dedicated contact:instagram tag (handle only)
        {
            "type": "node",
            "id": 5,
            "lat": 50.0,
            "lon": 20.0,
            "tags": {"name": "Barber Shop", "contact:instagram": "barber_rzeszow"},
        },
        # 6. Dedicated instagram tag (URL)
        {
            "type": "node",
            "id": 6,
            "lat": 50.0,
            "lon": 20.0,
            "tags": {"name": "Studio Paznokci", "instagram": "https://instagram.com/studio_paznokci"},
        },
        # 7. Directory URL in website tag
        {
            "type": "node",
            "id": 7,
            "lat": 50.0,
            "lon": 20.0,
            "tags": {"name": "Weterynarz Vet", "website": "https://znanylekarz.pl/weterynarz-vet"},
        },
        # 8. No website or social tags at all
        {
            "type": "node",
            "id": 8,
            "lat": 50.0,
            "lon": 20.0,
            "tags": {"name": "Kawiarnia Relaks"},
        },
    ]

    leads = op.parse_elements_to_leads(
        elements=elements,
        country="PL",
        default_city="Rzeszów",
        industry_label="Usługi",
    )

    assert len(leads) == 8

    # 1. Own site
    assert leads[0].name == "Hydraulik Jan"
    assert leads[0].website_kind == "own"
    assert leads[0].website == "https://hydraulik-jan.pl"

    # 2. Facebook in contact:website
    assert leads[1].name == "Fryzjer Anna"
    assert leads[1].website_kind == "facebook"
    assert "facebook.com" in leads[1].website

    # 3. Facebook tag URL
    assert leads[2].name == "Auto Serwis"
    assert leads[2].website_kind == "facebook"
    assert "facebook.com" in leads[2].website

    # 4. contact:facebook handle
    assert leads[3].name == "Piekarnia Chleb"
    assert leads[3].website_kind == "facebook"
    assert "facebook.com/piekarnia_chleb" in leads[3].website

    # 5. contact:instagram handle
    assert leads[4].name == "Barber Shop"
    assert leads[4].website_kind == "instagram"
    assert "instagram.com/barber_rzeszow" in leads[4].website

    # 6. instagram tag URL
    assert leads[5].name == "Studio Paznokci"
    assert leads[5].website_kind == "instagram"
    assert "instagram.com/studio_paznokci" in leads[5].website

    # 7. Directory
    assert leads[6].name == "Weterynarz Vet"
    assert leads[6].website_kind == "directory"

    # 8. None
    assert leads[7].name == "Kawiarnia Relaks"
    assert leads[7].website_kind == "none"
    assert leads[7].website is None
