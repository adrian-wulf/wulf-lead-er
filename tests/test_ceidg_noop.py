import pytest
import os
from unittest.mock import AsyncMock, patch
import httpx
from wulf_web_leader.adapters.pl_ceidg import CEIDGAdapter
from wulf_web_leader.models import CanonicalLead


@pytest.mark.asyncio
async def test_ceidg_no_token_silent_noop(monkeypatch):
    """WD.1 Test 1: Brak tokenu CEIDG_API_TOKEN -> is_available=False, zero wyjątku, lead nienaruszony."""
    monkeypatch.delenv("CEIDG_API_TOKEN", raising=False)
    adapter = CEIDGAdapter()

    assert adapter.is_available() is False

    lead = CanonicalLead(
        country="PL",
        name="Zakład Hydrauliczny",
        city="Rzeszów",
        source="osm",
        source_id="node/1",
        industry_label="Hydraulik",
        registry_status="unknown",
    )

    enriched = await adapter.enrich_lead(lead)
    assert enriched.name == "Zakład Hydrauliczny"
    assert enriched.registry_status == "unknown"


@pytest.mark.asyncio
async def test_ceidg_with_mocked_token_queries_api():
    """WD.1 Test 2: Z tokenem -> wykonanie autoryzowanego zapytania HTTP (mock) i aktualizacja leada."""
    adapter = CEIDGAdapter(api_token="test-jwt-secret-token")
    assert adapter.is_available() is True

    lead = CanonicalLead(
        country="PL",
        name="Kowalski Instalacje",
        city="Rzeszów",
        source="osm",
        source_id="node/1",
        industry_label="Hydraulik",
        registry_status="unknown",
    )

    fake_response = {
        "firmy": [
            {
                "nazwa": "Kowalski Instalacje",
                "status": "AKTYWNY",
                "glownyPkd": "43.22.Z",
                "adres": {
                    "miasto": "Rzeszów",
                    "ulica": "Rejtana",
                    "budynek": "5",
                },
                "telefon": "+48 17 800 00 00",
            }
        ]
    }

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        enriched = await adapter.enrich_lead(lead)

        assert mock_get.called
        call_kwargs = mock_get.call_args.kwargs
        assert "Authorization" in call_kwargs["headers"]
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-jwt-secret-token"

        assert enriched.registry_status == "active"
        assert enriched.industry_code == "43.22.Z"
        assert enriched.phone == "+48178000000"
