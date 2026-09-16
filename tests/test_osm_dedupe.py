from wulf_web_leader.adapters.osm import OverpassClient


def test_osm_dedupe_node_and_way():
    """Verify deduplication when node and way have the same phone and nearby location (~100m)."""
    client = OverpassClient()
    elements = [
        # Node with phone, short name, no street
        {
            "type": "node",
            "id": 1001,
            "lat": 50.0411,
            "lon": 21.9991,
            "tags": {
                "name": "Auto Naprawa",
                "phone": "+48 17 850 00 00",
                "shop": "car_repair",
            },
        },
        # Way (building) with same phone, fuller name, and full address
        {
            "type": "way",
            "id": 2002,
            "center": {
                "lat": 50.0412,
                "lon": 21.9992,
            },
            "tags": {
                "name": "Auto Naprawa Jan Kowalski",
                "phone": "+48 17 850 00 00",
                "addr:street": "Rejtana",
                "addr:housenumber": "10A",
                "addr:city": "Rzeszów",
                "shop": "car_repair",
            },
        },
    ]

    leads = client.parse_elements_to_leads(
        elements=elements,
        country="PL",
        default_city="Rzeszów",
        industry_label="Mechanika pojazdowa",
    )

    # Must be deduplicated to exactly 1 lead!
    assert len(leads) == 1
    lead = leads[0]
    assert lead.phone == "+48178500000"
    # Address should be enriched from the way
    assert lead.address == "Rejtana 10A"
