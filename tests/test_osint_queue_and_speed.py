import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from pathlib import Path

from wulf_web_leader.models import CanonicalLead, AuditResult
from wulf_web_leader.web.app import app
from wulf_web_leader.web.runner import run_post_scan_osint_queue
from wulf_web_leader.audit.speed import audit_website_speed


@pytest.mark.asyncio
async def test_speed_api_endpoint_with_bare_domain():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/speed?url=manola.pl")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "ok"
        speed = data["data"]
        assert "performance_score" in speed
        assert "mobile_score" in speed
        assert "score" in speed
        assert "grade" in speed


@pytest.mark.asyncio
async def test_revenue_loss_endpoint_aliases():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/revenue-loss?vert=informatyk&country=PL&https=1&rwd=0&load_time=4.5&has_site=1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        rev = data["data"]
        assert "monthly_loss_formatted" in rev
        assert "sales_pitch_hook" in rev


def test_audit_website_speed_normalization():
    res_empty = audit_website_speed("")
    assert res_empty["grade"] == "BRAK STRONY"
    assert res_empty["score"] == 0

    # Test scheme auto-prefixing with direct probe mock
    with patch("httpx.Client.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.content = b"<html><head><title>Test</title></head><body>Hello</body></html>"
        mock_get.return_value = mock_resp

        res = audit_website_speed("example.com")
        assert res["score"] > 50
        assert res["performance_score"] == res["score"]
        assert res["mobile_score"] == res["score"]


@pytest.mark.asyncio
async def test_post_scan_osint_queue_discovers_website(tmp_path: Path):
    lead = CanonicalLead(
        source_id="test_manola",
        name="Manola",
        city="Wrocław",
        country="PL",
        address="Sudecka 106a",
        industry_label="Kosmetologia",
        website_kind="none",
        score=90,
        verdict="hot",
        primary_issue="Brak witryny www w rejestrach OpenStreetMap",
    )

    state = {
        "status": "completed",
        "stage": "done",
        "progress": 100,
        "logs": [],
    }

    mock_audit = AuditResult(
        reachable=True,
        http_status=200,
        is_https=True,
        has_viewport=True,
        entity_match_score=75,
        extracted_phones=["+48730467240"],
        extracted_emails=["gabinet@manola.pl"],
    )

    with patch(
        "wulf_web_leader.audit.verifier.resolve_and_verify_candidate",
        return_value=("https://manola.pl/", mock_audit, "dns_candidate"),
    ):
        await run_post_scan_osint_queue(
            leads=[lead],
            workspace_dir=tmp_path,
            state=state,
            append_log=lambda s, m: None,
            use_gemini=False,
        )

        assert lead.website == "https://manola.pl/"
        assert lead.website_kind == "own"
        assert lead.website_source == "candidate_discovery"
        assert lead.phone == "+48730467240"
        assert lead.email == "gabinet@manola.pl"
        # Score must be recomputed (no longer 90)
        assert lead.score <= 40
        assert lead.verdict == "skip"
        assert state["osint_queue"]["done"] is True
