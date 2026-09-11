import json
import pytest
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient

from wulf_web_leader.models import CanonicalLead, GeminiIntel
from wulf_web_leader.audit.gemini_verifier import (
    is_gemini_available,
    get_gemini_api_key,
    verify_lead_with_gemini,
)
from wulf_web_leader.web.app import app, scan_manager


def test_is_gemini_available(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert not is_gemini_available()
    assert not is_gemini_available("")
    assert not is_gemini_available("short")

    assert is_gemini_available("AIzaSyD-valid-mock-key-123456789")

    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyD-valid-mock-key-123456789")
    assert is_gemini_available()
    assert get_gemini_api_key() == "AIzaSyD-valid-mock-key-123456789"


@pytest.mark.asyncio
async def test_verify_lead_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    lead = CanonicalLead(
        country="PL",
        name="Hydraulik Jan Kowalski",
        city="Rzeszów",
        industry_label="Hydraulik",
        source="osm",
        source_id="osm_node_111",
    )
    res = await verify_lead_with_gemini(lead, api_key=None)
    assert not res.checked
    assert res.error is not None
    assert "Brak klucza Gemini API" in res.error


@pytest.mark.asyncio
async def test_verify_lead_mocked_success():
    lead = CanonicalLead(
        country="PL",
        name="Auto Serwis Rzeszów",
        city="Rzeszów",
        industry_label="Mechanik samochodowy",
        phone="17 850 00 00",
        source="osm",
        source_id="osm_node_222",
    )

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "found_in_google": True,
                                "google_rating": 4.9,
                                "google_reviews_count": 68,
                                "discovered_website": "https://autoserwis-rzeszow.pl",
                                "social_profiles": ["https://facebook.com/autoserwisrzeszow"],
                                "summary": "Warsztat ma świetne opinie w Google Maps, ale stara strona nie działa na telefonach.",
                                "ai_pitch": "Dzień dobry! Zauważyłem, że w Google Maps macie ponad 60 świetnych recenzji i ocenę 4.9 w Rzeszowie...",
                            })
                        }
                    ]
                },
                "groundingMetadata": {
                    "webSearchQueries": ["Auto Serwis Rzeszów opinie", "Auto Serwis Rzeszów strona"],
                    "groundingChunks": [
                        {
                            "web": {
                                "uri": "https://maps.google.com/?cid=123",
                                "title": "Auto Serwis Rzeszów - Mapy Google",
                            }
                        }
                    ],
                },
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        from unittest.mock import MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_gemini_response
        mock_post.return_value = mock_resp

        res = await verify_lead_with_gemini(lead, api_key="AIzaSy-test-fake-key-123456789")

        assert res.checked is True
        assert res.found_in_google is True
        assert res.google_rating == 4.9
        assert res.google_reviews_count == 68
        assert res.discovered_website == "https://autoserwis-rzeszow.pl"
        assert len(res.social_profiles) == 1
        assert "60 świetnych recenzji" in res.ai_pitch
        assert len(res.grounding_sources) == 1
        assert res.grounding_sources[0]["url"] == "https://maps.google.com/?cid=123"


def test_api_gemini_endpoints():
    client = TestClient(app)

    # 1. Check status endpoint
    res = client.get("/api/gemini/status")
    assert res.status_code == 200
    data = res.json()
    assert "available" in data
    assert data["model"] == "gemini-3.6-flash"

    # 2. Add a dummy lead to scan_manager in-memory
    lead = CanonicalLead(
        country="PL",
        name="Piekarnia Tradycyjna",
        city="Kraków",
        industry_label="Piekarnia",
        phone="12 345 67 89",
        source="osm",
        source_id="test_piekarnia_123",
        score=75,
        verdict="hot",
    )
    scan_manager.leads = [lead]

    # 3. Mock verify_lead_gemini
    mock_intel = GeminiIntel(
        checked=True,
        found_in_google=True,
        google_rating=4.7,
        google_reviews_count=45,
        summary="Ceniona piekarnia w Krakowie bez własnego sklepu online.",
        ai_pitch="Dzień dobry! Wasza piekarnia ma 4.7 na Google Maps w Krakowie...",
    )

    with patch.object(scan_manager, "verify_lead_gemini", new_callable=AsyncMock) as mock_verify:
        lead_copy = lead.model_copy(deep=True)
        lead_copy.gemini_intel = mock_intel
        lead_copy.hooks.insert(0, f"✨ [AI Google Pitch]: {mock_intel.ai_pitch}")
        mock_verify.return_value = lead_copy

        # Call endpoint
        verify_res = client.post(
            f"/api/leads/{lead.source_id}/gemini-verify",
            json={"api_key": "AIzaSyD-dummy-key"},
        )
        assert verify_res.status_code == 200
        res_data = verify_res.json()
        assert res_data["status"] == "ok"
        assert res_data["gemini_intel"]["google_rating"] == 4.7
        assert res_data["gemini_intel"]["google_reviews_count"] == 45
        assert any("AI Google Pitch" in h for h in res_data["lead"]["hooks"])


def test_index_template_has_gemini_ui_elements():
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    # Check modal and header button
    assert "openGeminiModal()" in html
    assert "gemini-modal-dialog" in html
    assert "gemini-api-key-input" in html

    # Check scan form toggle
    assert 'id="scan-use-gemini"' in html

    # Check drawer tabs & quick verify button
    assert 'id="drawer-tab-gemini-btn"' in html
    assert 'id="tab-content-gemini"' in html
    assert 'id="drawer-btn-quick-gemini"' in html
    assert "triggerDrawerGeminiVerify()" in html
