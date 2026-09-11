import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from wulf_web_leader.models import CanonicalLead, AuditResult
from wulf_web_leader.web.scan_manager import ScanManager


@pytest.fixture
def sample_leads():
    lead_hot = CanonicalLead(
        country="PL",
        name="Hydraulik 24h Rzeszów",
        city="Rzeszów",
        street="ul. Warszawska 10",
        phone="+48 17 850 00 01",
        website="http://hydraulik-awaria.pl",
        website_kind="own",
        opportunity_type="broken_website",
        primary_issue="Awaria strony (HTTP 500)",
        score=85,
        verdict="hot",
        source="osm",
        source_id="node/101",
        industry_label="Hydraulik",
        hooks=["Strona firmy zgłasza błąd serwera (500)"],
    )
    lead_warm = CanonicalLead(
        country="PL",
        name="Fryzjer Męski",
        city="Rzeszów",
        phone="+48 17 850 00 02",
        website_kind="facebook",
        opportunity_type="social_only",
        primary_issue="Tylko profil w mediach społecznościowych",
        score=60,
        verdict="warm",
        source="osm",
        source_id="node/102",
        industry_label="Fryzjer",
        hooks=["Firma posiada wyłącznie profil na Facebooku"],
    )
    lead_skip = CanonicalLead(
        country="PL",
        name="Supermarket Sp. z o.o.",
        city="Rzeszów",
        website="https://supermarket.pl",
        website_kind="own",
        opportunity_type="modern_active",
        primary_issue="Nowoczesna, działająca witryna",
        score=20,
        verdict="skip",
        source="osm",
        source_id="node/103",
        industry_label="Sklep",
    )
    return [lead_hot, lead_warm, lead_skip]


def test_scan_manager_initial_state(tmp_path: Path):
    mgr = ScanManager(workspace_dir=tmp_path)
    assert mgr.status == "idle"
    assert mgr.stage == "idle"
    assert mgr.progress == 0
    assert mgr.counts == {"total": 0, "hot": 0, "warm": 0, "skip": 0}
    assert len(mgr.leads) == 0


@pytest.mark.asyncio
async def test_scan_manager_subscribe_and_broadcast(tmp_path: Path):
    mgr = ScanManager(workspace_dir=tmp_path)
    q = mgr.subscribe()

    test_event = {"type": "test", "payload": 123}
    await mgr.broadcast(test_event)

    received = await asyncio.wait_for(q.get(), timeout=1.0)
    assert received == test_event

    mgr.unsubscribe(q)
    assert q not in mgr._subscribers


def test_scan_manager_get_leads_filtering(tmp_path: Path, sample_leads):
    mgr = ScanManager(workspace_dir=tmp_path)
    mgr.leads = sample_leads

    assert mgr.counts == {"total": 3, "hot": 1, "warm": 1, "skip": 1}

    # Filter by verdict
    hot_leads = mgr.get_leads(verdict="hot")
    assert len(hot_leads) == 1
    assert hot_leads[0].name == "Hydraulik 24h Rzeszów"

    # Filter by search query
    searched = mgr.get_leads(query="Fryzjer")
    assert len(searched) == 1
    assert searched[0].name == "Fryzjer Męski"

    # Filter by phone only
    with_phone = mgr.get_leads(has_phone=True)
    assert len(with_phone) == 2

    # Filter by min_score
    high_score = mgr.get_leads(min_score=70)
    assert len(high_score) == 1
    assert high_score[0].score == 85


def test_scan_manager_export(tmp_path: Path, sample_leads):
    mgr = ScanManager(workspace_dir=tmp_path)
    mgr.leads = sample_leads

    # Export CSV
    csv_bytes, mime, fname = mgr.export_leads("csv")
    assert mime.startswith("text/csv")
    assert fname == "leads.csv"
    csv_str = csv_bytes.decode("utf-8")
    assert "Hydraulik 24h Rzeszów" in csv_str
    assert "Fryzjer Męski" in csv_str

    # Export JSON
    json_bytes, mime, fname = mgr.export_leads("json")
    assert mime.startswith("application/json")
    assert fname == "leads.json"
    parsed = json.loads(json_bytes.decode("utf-8"))
    assert parsed["total_leads"] == 3

    # Export HTML
    html_bytes, mime, fname = mgr.export_leads("html")
    assert mime.startswith("text/html")
    assert fname == "report.html"
    assert b"Hydraulik 24h Rzesz\xc3\xb3w" in html_bytes or b"Hydraulik" in html_bytes

    # Invalid format raises ValueError
    with pytest.raises(ValueError):
        mgr.export_leads("invalid_format")


def test_scan_manager_save_and_load(tmp_path: Path, sample_leads):
    mgr = ScanManager(workspace_dir=tmp_path)
    mgr.leads = sample_leads

    target_file = tmp_path / "leads_custom.json"
    mgr.export_leads("json")
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump([l.model_dump(mode="json") for l in sample_leads], f)

    scans = mgr.list_saved_scans()
    assert any(s["filename"] == "leads_custom.json" for s in scans)

    mgr2 = ScanManager(workspace_dir=tmp_path)
    loaded_count = mgr2.load_scan_file(target_file)
    assert loaded_count == 3
    assert mgr2.counts["hot"] == 1


@pytest.mark.asyncio
async def test_scan_manager_stop_scan(tmp_path: Path):
    mgr = ScanManager(workspace_dir=tmp_path)
    mgr.status = "running"
    dummy_task = asyncio.create_task(asyncio.sleep(10))
    mgr.scan_task = dummy_task

    stopped = await mgr.stop_scan()
    assert stopped is True
    assert mgr.status == "stopped"
    try:
        await dummy_task
    except asyncio.CancelledError:
        pass
    assert dummy_task.cancelled()


@pytest.mark.asyncio
async def test_scan_manager_duplicate_start_prevented(tmp_path: Path):
    mgr = ScanManager(workspace_dir=tmp_path)
    mgr.status = "running"

    started = await mgr.start_scan(
        country="PL",
        city="Rzeszów",
        vertical_id="plumbers",
    )
    assert started is False
