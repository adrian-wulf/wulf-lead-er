import pytest
from unittest.mock import AsyncMock, patch
import httpx

from wulf_web_leader.adapters.pl_ceidg import CEIDGAdapter
from wulf_web_leader.models import (
    CanonicalLead,
    VerticalDefinition,
    CountryVerticalConfig,
)
from wulf_web_leader.score.engine import calculate_lead_score
from wulf_web_leader.pipeline import run_scan_pipeline
from wulf_web_leader.adapters.nominatim import GeocodedLocation


@pytest.mark.asyncio
async def test_inactive_business_receives_zero_score_and_skip():
    """WD.2: Firma ze statusem ZAWIESZONY w CEIDG otrzymuje registry_status='inactive', score=0, verdict='skip'."""
    adapter = CEIDGAdapter(api_token="valid-token")

    lead = CanonicalLead(
        country="PL",
        name="Zawieszony Zakład",
        city="Rzeszów",
        source="osm",
        source_id="node/1",
        website_kind="none",
        phone="+48178000000",
        industry_label="Hydraulik",
    )

    fake_response = {
        "firmy": [
            {
                "nazwa": "Zawieszony Zakład",
                "status": "ZAWIESZONY",
                "glownyPkd": "43.22.Z",
            }
        ]
    }

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        enriched = await adapter.enrich_lead(lead)

    assert enriched.registry_status == "inactive"
    assert enriched.industry_code == "43.22.Z"

    score, verdict = calculate_lead_score(enriched)
    assert score == 0
    assert verdict == "skip"


@pytest.mark.asyncio
async def test_active_business_keeps_score():
    """WD.2: Firma aktywna w CEIDG otrzymuje registry_status='active' i zachowuje scoring."""
    adapter = CEIDGAdapter(api_token="valid-token")

    lead = CanonicalLead(
        country="PL",
        name="Aktywny Hydraulik",
        city="Rzeszów",
        source="osm",
        source_id="node/2",
        website_kind="none",
        phone="+48178000000",
        industry_label="Hydraulik",
    )

    fake_response = {
        "firmy": [
            {
                "nazwa": "Aktywny Hydraulik",
                "status": "AKTYWNY",
                "glownyPkd": "43.22.Z",
            }
        ]
    }

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        enriched = await adapter.enrich_lead(lead)

    assert enriched.registry_status == "active"
    score, verdict = calculate_lead_score(enriched)
    assert score == 70  # 50 (no website) + 20 (phone)
    assert verdict == "hot"


@pytest.mark.asyncio
async def test_pipeline_integrates_ceidg():
    """WD.2: Pełny pipeline z mockowanym adapterem CEIDG poprawnie filtruje lub oznacza zawieszoną firmę."""
    fake_lead_active = CanonicalLead(
        country="PL",
        name="Dobra Firma",
        city="Rzeszów",
        source="osm",
        source_id="node/10",
        website_kind="none",
        phone="+48171111111",
        industry_label="Hydraulik",
    )
    fake_lead_inactive = CanonicalLead(
        country="PL",
        name="Martwa Firma",
        city="Rzeszów",
        source="osm",
        source_id="node/20",
        website_kind="none",
        phone="+48172222222",
        industry_label="Hydraulik",
    )

    class MockNominatim:
        async def geocode(self, city, country):
            return GeocodedLocation(lat=50.0, lon=22.0, display_name=f"{city}, {country}", city=city)

    class MockOverpass:
        async def execute_query(self, query):
            return []

        def parse_elements_to_leads(self, **kwargs):
            return [fake_lead_active, fake_lead_inactive]

    class MockCEIDG:
        def is_available(self):
            return True

        async def enrich_leads(self, leads):
            for l in leads:
                if l.name == "Martwa Firma":
                    l.registry_status = "inactive"
                else:
                    l.registry_status = "active"
            return leads

    vertical = VerticalDefinition(
        id="plumbers",
        name="Hydraulicy",
        pl=CountryVerticalConfig(query="hydraulik", label="Hydraulik", osm=["craft=plumber"], pkd=["43.22.Z"]),
        de=CountryVerticalConfig(query="klempner", label="Klempner", osm=["craft=plumber"], wz=["43.22"]),
    )

    leads, _ = await run_scan_pipeline(
        country="PL",
        city="Rzeszów",
        vertical=vertical,
        nominatim_client=MockNominatim(),
        overpass_client=MockOverpass(),
        ceidg_adapter=MockCEIDG(),
        do_audit=False,
    )

    by_name = {l.name: l for l in leads}
    assert by_name["Martwa Firma"].score == 0
    assert by_name["Martwa Firma"].verdict == "skip"
    assert by_name["Dobra Firma"].score == 70
    assert by_name["Dobra Firma"].verdict == "hot"
