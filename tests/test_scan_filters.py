import pytest
from pathlib import Path
from wulf_web_leader.adapters.nominatim import NominatimClient, GeocodedLocation
from wulf_web_leader.adapters.osm import OverpassClient
from wulf_web_leader.pipeline import run_scan_pipeline
from wulf_web_leader.verticals import find_vertical


class MockFilterNominatim(NominatimClient):
    async def geocode(self, city: str, country: str) -> GeocodedLocation | None:
        return GeocodedLocation(lat=50.04, lon=22.00, display_name="Rzeszów, PL", city="Rzeszów")


class MockFilterOverpass(OverpassClient):
    async def execute_query(self, query: str) -> list[dict]:
        return [
            # Lead 1: no website + phone => score 70 (hot), has phone
            {
                "type": "node",
                "id": 1,
                "lat": 50.041,
                "lon": 22.001,
                "tags": {"name": "Firma A (Hot, Phone)", "contact:phone": "+48 17 111 22 33"},
            },
            # Lead 2: no website, no phone => score 50 (warm), no phone
            {
                "type": "node",
                "id": 2,
                "lat": 50.042,
                "lon": 22.002,
                "tags": {"name": "Firma B (Warm, No Phone)"},
            },
            # Lead 3: modern site + phone => score 20 (skip), has phone
            {
                "type": "node",
                "id": 3,
                "lat": 50.043,
                "lon": 22.003,
                "tags": {
                    "name": "Firma C (Skip, Phone)",
                    "website": "https://super-moderna-strona.pl",
                    "contact:phone": "+48 17 333 44 55",
                },
            },
        ]


@pytest.mark.asyncio
async def test_scan_filter_min_score():
    vertical = find_vertical("plumbers")
    assert vertical is not None

    # Filter with min_score = 60 -> only Firma A (score 70) should remain
    leads, _ = await run_scan_pipeline(
        country="PL",
        city="Rzeszów",
        vertical=vertical,
        do_audit=False,
        min_score=60,
        nominatim_client=MockFilterNominatim(),
        overpass_client=MockFilterOverpass(),
    )
    assert len(leads) == 1
    assert leads[0].name == "Firma A (Hot, Phone)"
    assert leads[0].score >= 60


@pytest.mark.asyncio
async def test_scan_filter_has_phone():
    vertical = find_vertical("plumbers")
    assert vertical is not None

    # Filter with has_phone_only = True -> Firma A and Firma C
    leads, _ = await run_scan_pipeline(
        country="PL",
        city="Rzeszów",
        vertical=vertical,
        do_audit=False,
        has_phone_only=True,
        nominatim_client=MockFilterNominatim(),
        overpass_client=MockFilterOverpass(),
    )
    assert len(leads) == 2
    assert all(l.phone for l in leads)
    assert not any(l.name == "Firma B (Warm, No Phone)" for l in leads)


@pytest.mark.asyncio
async def test_scan_filter_combined_min_score_and_has_phone():
    vertical = find_vertical("plumbers")
    assert vertical is not None

    # Filter combined: min_score = 60 and has_phone_only = True
    leads, _ = await run_scan_pipeline(
        country="PL",
        city="Rzeszów",
        vertical=vertical,
        do_audit=False,
        min_score=60,
        has_phone_only=True,
        nominatim_client=MockFilterNominatim(),
        overpass_client=MockFilterOverpass(),
    )
    assert len(leads) == 1
    assert leads[0].name == "Firma A (Hot, Phone)"
    assert leads[0].score == 70
    assert leads[0].phone is not None
