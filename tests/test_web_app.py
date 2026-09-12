import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient

from wulf_web_leader.web.app import app, scan_manager
from wulf_web_leader.models import CanonicalLead


from wulf_web_leader.web.session_manager import get_manager


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_scan_manager():
    app.dependency_overrides[get_manager] = lambda: scan_manager
    scan_manager.status = "idle"
    scan_manager.stage = "idle"
    scan_manager.progress = 0
    scan_manager.message = "Gotowy do skanowania"
    scan_manager.logs = []
    scan_manager.leads = []
    if scan_manager.scan_task and not scan_manager.scan_task.done():
        scan_manager.scan_task.cancel()
    scan_manager.scan_task = None
    yield
    app.dependency_overrides.clear()



def test_get_dashboard_html(test_client):
    res = test_client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "WULF-WEB-LEADER" in res.text
    assert "Kryteria Skanowania" in res.text
    assert "Pulpit" in res.text
    assert "Uruchom skanowanie" in res.text


def test_health_endpoint(test_client):
    res = test_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "0.3.0"}


def test_api_verticals(test_client):
    res = test_client.get("/api/verticals")
    assert res.status_code == 200
    data = res.json()
    assert "verticals" in data
    assert len(data["verticals"]) == 8
    vertical_ids = [v["id"] for v in data["verticals"]]
    assert "plumbers" in vertical_ids
    assert "veterinary" in vertical_ids


def test_api_leads_empty_and_populated(test_client):
    res = test_client.get("/api/leads")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["counts"]["total"] == 0

    # Populate with sample lead
    lead = CanonicalLead(
        country="PL",
        name="Auto Serwis Kraków",
        city="Kraków",
        phone="+48 12 345 67 89",
        website_kind="none",
        opportunity_type="no_website",
        primary_issue="Brak strony www",
        score=70,
        verdict="hot",
        source="osm",
        source_id="node/200",
        industry_label="Warsztat",
    )
    scan_manager.leads = [lead]

    res2 = test_client.get("/api/leads?verdict=hot")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["total"] == 1
    assert data2["leads"][0]["name"] == "Auto Serwis Kraków"


def test_api_scan_status(test_client):
    res = test_client.get("/api/scan/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "idle"
    assert "counts" in data
    assert "logs" in data


@pytest.mark.asyncio
async def test_api_scan_start_and_conflict(test_client):
    with patch.object(scan_manager, "start_scan", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = True

        res = test_client.post(
            "/api/scan/start",
            json={
                "country": "PL",
                "city": "Rzeszów",
                "vertical": "plumbers",
                "radius": 15.0,
                "lang": "pl",
            },
        )
        assert res.status_code == 200
        assert res.json()["status"] == "started"

    # Simulate conflict (scan already running)
    with patch.object(scan_manager, "start_scan", new_callable=AsyncMock) as mock_start_conflict:
        mock_start_conflict.return_value = False

        res2 = test_client.post(
            "/api/scan/start",
            json={
                "country": "PL",
                "city": "Rzeszów",
                "vertical": "plumbers",
            },
        )
        assert res2.status_code == 409


def test_api_scan_stop(test_client):
    with patch.object(scan_manager, "stop_scan", new_callable=AsyncMock) as mock_stop:
        mock_stop.return_value = True

        res = test_client.post("/api/scan/stop")
        assert res.status_code == 200
        assert res.json()["stopped"] is True


def test_api_export_csv_and_json_and_html(test_client):
    lead = CanonicalLead(
        country="DE",
        name="Malerbetrieb Schmidt",
        city="Dresden",
        phone="+49 351 123456",
        website="https://schmidt-maler.de",
        website_kind="own",
        opportunity_type="critical_redesign",
        primary_issue="Brak wersji na smartfony (RWD)",
        score=75,
        verdict="hot",
        source="osm",
        source_id="node/300",
        industry_label="Maler",
    )
    scan_manager.leads = [lead]

    # CSV
    res_csv = test_client.get("/api/export/csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Malerbetrieb Schmidt" in res_csv.text

    # JSON
    res_json = test_client.get("/api/export/json")
    assert res_json.status_code == 200
    assert "application/json" in res_json.headers["content-type"]
    data = res_json.json()
    assert data["total_leads"] == 1
    assert data["leads"][0]["name"] == "Malerbetrieb Schmidt"

    # HTML
    res_html = test_client.get("/api/export/html")
    assert res_html.status_code == 200
    assert "text/html" in res_html.headers["content-type"]
    assert "Malerbetrieb Schmidt" in res_html.text

    # Invalid
    res_err = test_client.get("/api/export/pdf")
    assert res_err.status_code == 400


def test_api_scans_list_and_load(test_client, tmp_path):
    scan_manager.workspace_dir = tmp_path
    scan_file = tmp_path / "leads_archive.json"
    lead = CanonicalLead(
        country="PL",
        name="Test Zakład",
        city="Kraków",
        score=55,
        verdict="warm",
        source="osm",
        source_id="node/999",
        industry_label="Test",
    )
    with open(scan_file, "w", encoding="utf-8") as f:
        json.dump([lead.model_dump(mode="json")], f)

    res = test_client.get("/api/scans")
    assert res.status_code == 200
    scans = res.json()["scans"]
    assert any(s["filename"] == "leads_archive.json" for s in scans)

    # Load file
    res_load = test_client.post("/api/scans/load", json={"filename": "leads_archive.json"})
    assert res_load.status_code == 200
    assert res_load.json()["loaded"] == 1
    assert len(scan_manager.leads) == 1

    # Load non-existent file
    res_404 = test_client.post("/api/scans/load", json={"filename": "non_existent.json"})
    assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_api_scan_events_sse():
    from unittest.mock import MagicMock
    from wulf_web_leader.web.app import stream_scan_events

    mock_req = MagicMock()
    mock_req.is_disconnected = AsyncMock(side_effect=[False, True])

    resp = await stream_scan_events(mock_req, mgr=scan_manager)
    assert resp.status_code == 200
    assert resp.media_type == "text/event-stream"

    gen = resp.body_iterator
    first_chunk = await anext(gen)
    assert first_chunk.startswith("data: ")
    event = json.loads(first_chunk[6:])
    assert event["type"] == "status"
    assert event["status"] == "idle"


def test_session_cookie_created_on_first_visit():
    app.dependency_overrides.clear()
    client = TestClient(app)
    res = client.get("/")
    assert res.status_code == 200
    assert "wulf_session_id" in client.cookies
    sid = client.cookies["wulf_session_id"]
    assert len(sid) >= 16


def test_session_isolation_two_clients():
    app.dependency_overrides.clear()
    client_a = TestClient(app)
    client_b = TestClient(app)

    # Client A accesses dashboard and gets session cookie
    res_a = client_a.get("/")
    assert res_a.status_code == 200
    sid_a = client_a.cookies.get("wulf_session_id")
    assert sid_a

    # Client B accesses dashboard and gets different session cookie
    res_b = client_b.get("/")
    assert res_b.status_code == 200
    sid_b = client_b.cookies.get("wulf_session_id")
    assert sid_b
    assert sid_a != sid_b

    # Both start with 0 leads
    assert client_a.get("/api/leads").json()["total"] == 0
    assert client_b.get("/api/leads").json()["total"] == 0

    # Inject a lead directly into Client A's session manager
    from wulf_web_leader.web.session_manager import session_registry
    mgr_a = session_registry.get(sid_a)
    lead_a = CanonicalLead(
        country="PL",
        name="Firma Klienta A",
        city="Warszawa",
        source="osm",
        source_id="lead_a_1",
        score=80,
        verdict="hot",
        industry_label="Test",
    )
    mgr_a.leads = [lead_a]

    # Verify Client A sees the lead, but Client B STILL SEES 0 LEADS (ISOLATION!)
    res_leads_a = client_a.get("/api/leads")
    assert res_leads_a.json()["total"] == 1
    assert res_leads_a.json()["leads"][0]["name"] == "Firma Klienta A"

    res_leads_b = client_b.get("/api/leads")
    assert res_leads_b.json()["total"] == 0


def test_session_reset():
    app.dependency_overrides.clear()
    client = TestClient(app)
    client.get("/")
    sid = client.cookies.get("wulf_session_id")

    from wulf_web_leader.web.session_manager import session_registry
    mgr = session_registry.get(sid)
    mgr.leads = [
        CanonicalLead(
            name="Lead do skasowania",
            country="PL",
            city="Gdańsk",
            industry_label="Test",
            source="osm",
            source_id="del_1",
        )
    ]
    assert client.get("/api/leads").json()["total"] == 1

    # Reset session
    res_reset = client.post("/api/session/reset")
    assert res_reset.status_code == 200
    assert res_reset.json()["status"] == "ok"

    # Verify leads are now 0
    assert client.get("/api/leads").json()["total"] == 0


def test_session_path_traversal_protection():
    app.dependency_overrides.clear()
    client = TestClient(app)
    # Attempt directory traversal attack via header or cookie
    res = client.get("/api/leads", headers={"X-Session-ID": "../../../../etc/passwd"})
    assert res.status_code == 200
    set_cookie = res.headers.get("set-cookie", "")
    assert "wulf_session_id=" in set_cookie
    cookie_val = set_cookie.split("wulf_session_id=")[1].split(";")[0]
    assert "/" not in cookie_val
    assert ".." not in cookie_val
    assert len(cookie_val) == 32



