import pytest
import sqlite3
from pathlib import Path

from wulf_web_leader.adapters.de_offeneregister import OffeneRegisterAdapter
from wulf_web_leader.models import CanonicalLead, VerticalDefinition, CountryVerticalConfig
from wulf_web_leader.score.engine import calculate_lead_score
from wulf_web_leader.pipeline import run_scan_pipeline
from wulf_web_leader.adapters.nominatim import GeocodedLocation


def test_offeneregister_no_db_silent_noop(monkeypatch, tmp_path):
    """WE.1: Brak pliku bazy SQLite skutkuje natychmiastowym pominięciem (no-op) bez błędów."""
    monkeypatch.delenv("OFFENEREGISTER_DB_PATH", raising=False)
    adapter = OffeneRegisterAdapter(db_path=tmp_path / "non_existent.db")

    assert adapter.is_available() is False

    lead = CanonicalLead(
        country="DE",
        name="Müller Sanitär GmbH",
        city="Dresden",
        source="osm",
        source_id="node/100",
        industry_label="Klempner",
        registry_status="unknown",
    )

    enriched = adapter.enrich_lead(lead)
    assert enriched.name == "Müller Sanitär GmbH"
    assert enriched.registry_status == "unknown"


def test_offeneregister_sqlite_status_enrichment(tmp_path):
    """WE.1: Miniaturowa baza SQLite poprawnie wzbogaca aktywny i rozwiązany podmiot."""
    db_file = tmp_path / "test_offeneregister.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("""
            CREATE TABLE company (
                name TEXT,
                current_status TEXT,
                company_number TEXT,
                city TEXT
            )
        """)
        conn.execute("INSERT INTO company VALUES ('Müller Sanitär GmbH', 'currently registered', 'HRB 1234', 'Dresden')")
        conn.execute("INSERT INTO company VALUES ('Schmidt Haustechnik UG', 'gelöscht', 'HRB 5678', 'Dresden')")
        conn.commit()

    adapter = OffeneRegisterAdapter(db_path=db_file)
    assert adapter.is_available() is True

    # 1. Active company
    lead_active = CanonicalLead(
        country="DE",
        name="Müller Sanitär GmbH",
        city="Dresden",
        source="osm",
        source_id="node/101",
        website_kind="none",
        phone="+49351000000",
        industry_label="Klempner",
    )
    adapter.enrich_lead(lead_active)
    assert lead_active.registry_status == "active"
    assert lead_active.source_id == "hr/HRB 1234"
    score, verdict = calculate_lead_score(lead_active)
    assert score == 50  # Corporate entity without verified website is capped at WARM
    assert verdict == "warm"

    # 2. Cancelled / dissolved company
    lead_cancelled = CanonicalLead(
        country="DE",
        name="Schmidt Haustechnik UG",
        city="Dresden",
        source="osm",
        source_id="node/102",
        website_kind="none",
        phone="+49351999999",
        industry_label="Klempner",
    )
    adapter.enrich_lead(lead_cancelled)
    assert lead_cancelled.registry_status == "inactive"
    score_c, verdict_c = calculate_lead_score(lead_cancelled)
    assert score_c == 0
    assert verdict_c == "skip"


@pytest.mark.asyncio
async def test_pipeline_de_integrates_offeneregister(tmp_path):
    """WE.1: Pipeline dla kraju DE integruje OffeneRegister i dyskwalifikuje nieaktywne podmioty."""
    db_file = tmp_path / "test_offeneregister.db"
    with sqlite3.connect(db_file) as conn:
        conn.execute("CREATE TABLE company (name TEXT, current_status TEXT, company_number TEXT, city TEXT)")
        conn.execute("INSERT INTO company VALUES ('Inaktive Firma UG', 'in Liquidation', 'HRB 9999', 'Dresden')")
        conn.commit()

    fake_lead_active = CanonicalLead(
        country="DE",
        name="Aktive Firma GmbH",
        city="Dresden",
        source="osm",
        source_id="node/201",
        website_kind="none",
        phone="+49351111111",
        industry_label="Klempner",
    )
    fake_lead_inactive = CanonicalLead(
        country="DE",
        name="Inaktive Firma UG",
        city="Dresden",
        source="osm",
        source_id="node/202",
        website_kind="none",
        phone="+49351222222",
        industry_label="Klempner",
    )

    class MockNominatim:
        async def geocode(self, city, country):
            return GeocodedLocation(lat=51.05, lon=13.73, display_name="Dresden, Germany", city="Dresden")

    class MockOverpass:
        async def execute_query(self, query):
            return []

        def parse_elements_to_leads(self, **kwargs):
            return [fake_lead_active, fake_lead_inactive]

    vertical = VerticalDefinition(
        id="plumbers",
        name="Klempner",
        pl=CountryVerticalConfig(query="hydraulik", label="Hydraulik", osm=["craft=plumber"], pkd=["43.22.Z"]),
        de=CountryVerticalConfig(query="klempner", label="Klempner", osm=["craft=plumber"], wz=["43.22"]),
    )

    adapter = OffeneRegisterAdapter(db_path=db_file)

    leads, _ = await run_scan_pipeline(
        country="DE",
        city="Dresden",
        vertical=vertical,
        nominatim_client=MockNominatim(),
        overpass_client=MockOverpass(),
        offeneregister_adapter=adapter,
        do_audit=False,
    )

    by_name = {l.name: l for l in leads}
    assert by_name["Inaktive Firma UG"].score == 0
    assert by_name["Inaktive Firma UG"].verdict == "skip"
    assert by_name["Aktive Firma GmbH"].score == 50  # Corporate entity without verified website is capped at WARM
    assert by_name["Aktive Firma GmbH"].verdict == "warm"
