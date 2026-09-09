import pytest
from pathlib import Path
from brakstrony.adapters.nominatim import NominatimClient, GeocodedLocation
from brakstrony.adapters.osm import OverpassClient
from brakstrony.pipeline import run_scan_pipeline
from brakstrony.verticals import find_vertical
from brakstrony.export.writer import export_leads_to_csv, export_leads_to_json


class MockNominatim(NominatimClient):
    async def geocode(self, city: str, country: str) -> GeocodedLocation | None:
        return GeocodedLocation(
            lat=50.0411,
            lon=21.9991,
            display_name=f"{city}, Podkarpackie, Poland",
            city=city,
            postcode="35-001",
        )


class MockOverpass(OverpassClient):
    async def execute_query(self, query: str) -> list[dict]:
        return [
            {
                "type": "node",
                "id": 1001,
                "lat": 50.042,
                "lon": 22.001,
                "tags": {
                    "name": "Hydraulik 24h Rzeszów",
                    "contact:phone": "+48 17 888 77 66",
                    "addr:city": "Rzeszów",
                    "addr:street": "ul. Grunwaldzka 5",
                },
            },
            {
                "type": "node",
                "id": 1002,
                "lat": 50.043,
                "lon": 22.002,
                "tags": {
                    "name": "Pogotowie Wod-Kan",
                    "contact:phone": "+48 500 111 222",
                    "website": "https://www.facebook.com/pogotowie.wodkan",
                    "addr:city": "Rzeszów",
                },
            },
            {
                "type": "node",
                "id": 1003,
                "lat": 50.044,
                "lon": 22.003,
                "tags": {
                    "name": "Plumber Service Nowak",
                    "contact:phone": "+48 17 555 44 33",
                    "website": "https://nowak-plumbing.pl",
                    "addr:city": "Rzeszów",
                },
            },
        ]


@pytest.mark.asyncio
async def test_pipeline_offline(tmp_path: Path):
    vertical = find_vertical("plumbers")
    assert vertical is not None

    mock_nom = MockNominatim()
    mock_op = MockOverpass()

    leads, loc = await run_scan_pipeline(
        country="PL",
        city="Rzeszów",
        vertical=vertical,
        radius_km=10.0,
        lang="pl",
        do_audit=False,  # offline mode
        nominatim_client=mock_nom,
        overpass_client=mock_op,
    )

    assert len(leads) == 3
    # First lead has no website + phone -> score = 70 (hot)
    assert leads[0].name == "Hydraulik 24h Rzeszów"
    assert leads[0].website_kind == "none"
    assert leads[0].score == 70
    assert leads[0].verdict == "hot"
    assert "Brak strony www" in leads[0].hooks[0]

    # Second lead has facebook + phone -> score = 55 (warm)
    assert leads[1].name == "Pogotowie Wod-Kan"
    assert leads[1].website_kind == "facebook"
    assert leads[1].score == 55
    assert leads[1].verdict == "warm"

    # Export to CSV and JSON
    csv_file = tmp_path / "leads.csv"
    json_file = tmp_path / "leads.json"

    export_leads_to_csv(leads, csv_file)
    export_leads_to_json(leads, json_file)

    assert csv_file.is_file()
    assert json_file.is_file()

    # Verify CSV content
    csv_text = csv_file.read_text(encoding="utf-8-sig")
    assert "name,city,country,phone,website,website_kind,score,verdict,hook,source,lat,lon" in csv_text
    assert "Hydraulik 24h Rzeszów" in csv_text
    assert "+48178887766" in csv_text
    assert "hot" in csv_text
