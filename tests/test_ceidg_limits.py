import pytest
import time
from unittest.mock import AsyncMock, patch
import httpx

from wulf_web_leader.adapters.pl_ceidg import CEIDGAdapter
from wulf_web_leader.models import CanonicalLead


@pytest.mark.asyncio
async def test_ceidg_rate_limiting():
    """WD.3: Ogranicznik zapytań wymusza odstęp czasu (np. max_rps=10 -> 3 zapytania trwają >=0.2s)."""
    adapter = CEIDGAdapter(api_token="test-token", max_rps=10.0)

    lead = CanonicalLead(
        country="PL",
        name="Firma Testowa",
        city="Rzeszów",
        source="osm",
        source_id="node/1",
        industry_label="Hydraulik",
    )

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"firmy": []}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        start = time.perf_counter()
        await adapter.enrich_lead(lead)
        await adapter.enrich_lead(lead)
        await adapter.enrich_lead(lead)
        duration = time.perf_counter() - start

        # 3 calls at 10 rps should take at least 2 intervals = 0.20s
        assert duration >= 0.18


@pytest.mark.asyncio
async def test_ceidg_http_429_graceful_fallback():
    """WD.3: Odpowiedź HTTP 429 (Too Many Requests) powoduje cichy fallback do OSM bez rzucania wyjątku."""
    adapter = CEIDGAdapter(api_token="test-token", max_rps=0)

    lead = CanonicalLead(
        country="PL",
        name="Firma Zablokowana",
        city="Rzeszów",
        source="osm",
        source_id="node/2",
        phone="+48178000000",
        registry_status="unknown",
        industry_label="Hydraulik",
    )

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 429

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        enriched = await adapter.enrich_lead(lead)

        assert enriched.registry_status == "unknown"
        assert enriched.phone == "+48178000000"


@pytest.mark.asyncio
async def test_ceidg_http_503_graceful_fallback():
    """WD.3: Odpowiedź HTTP 503 (Service Unavailable) nie przerywa działania, lead zostaje z danymi OSM."""
    adapter = CEIDGAdapter(api_token="test-token", max_rps=0)

    lead = CanonicalLead(
        country="PL",
        name="Firma Serwis",
        city="Rzeszów",
        source="osm",
        source_id="node/3",
        phone="+48178000000",
        registry_status="unknown",
        industry_label="Hydraulik",
    )

    mock_resp = AsyncMock(spec=httpx.Response)
    mock_resp.status_code = 503

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        enriched = await adapter.enrich_lead(lead)

        assert enriched.registry_status == "unknown"
        assert enriched.phone == "+48178000000"


@pytest.mark.asyncio
async def test_ceidg_network_timeout_graceful():
    """WD.3: Błąd sieci/timeout nie wywala aplikacji."""
    adapter = CEIDGAdapter(api_token="test-token", max_rps=0)

    lead = CanonicalLead(
        country="PL",
        name="Firma Timeout",
        city="Rzeszów",
        source="osm",
        source_id="node/4",
        phone="+48178000000",
        registry_status="unknown",
        industry_label="Hydraulik",
    )

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectTimeout("Network unreachable")):
        enriched = await adapter.enrich_lead(lead)
        assert enriched.registry_status == "unknown"
        assert enriched.phone == "+48178000000"
