from wulf_web_leader.adapters.osm import OverpassClient


def test_osm_filter_disused_and_dead_pois():
    client = OverpassClient()
    elements = [
        # 1. Prefix disused:
        {
            "type": "node",
            "id": 101,
            "lat": 50.0,
            "lon": 20.0,
            "tags": {
                "name": "Stary Zakład",
                "disused:shop": "hairdresser",
                "phone": "+48 123 456 789",
            },
        },
        # 2. Tag disused=yes
        {
            "type": "node",
            "id": 102,
            "lat": 50.01,
            "lon": 20.01,
            "tags": {
                "name": "Nieczynny Salon",
                "shop": "hairdresser",
                "disused": "yes",
                "phone": "+48 123 456 789",
            },
        },
        # 3. Tag abandoned=yes or prefix abandoned:
        {
            "type": "node",
            "id": 103,
            "lat": 50.02,
            "lon": 20.02,
            "tags": {
                "name": "Porzucony Fryzjer",
                "abandoned:shop": "hairdresser",
            },
        },
        # 4. Tag closed=yes
        {
            "type": "node",
            "id": 104,
            "lat": 50.03,
            "lon": 20.03,
            "tags": {
                "name": "Zamknięty Zakład",
                "shop": "hairdresser",
                "closed": "yes",
            },
        },
        # 5. Tag opening_hours=closed
        {
            "type": "node",
            "id": 105,
            "lat": 50.04,
            "lon": 20.04,
            "tags": {
                "name": "Zawsze Zamknięte",
                "shop": "hairdresser",
                "opening_hours": "closed",
            },
        },
        # 6. Aktywny, poprawny salon (powinien przejść)
        {
            "type": "node",
            "id": 106,
            "lat": 50.05,
            "lon": 20.05,
            "tags": {
                "name": "Czynny Fryzjer",
                "shop": "hairdresser",
                "phone": "+48 123 456 789",
            },
        },
    ]

    leads = client.parse_elements_to_leads(
        elements=elements,
        country="PL",
        default_city="Rzeszów",
        industry_label="Fryzjer",
        industry_code="96.02.Z",
    )

    assert len(leads) == 1
    assert leads[0].name == "Czynny Fryzjer"
    assert leads[0].source_id == "node/106"
