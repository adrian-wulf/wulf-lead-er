import asyncio
import inspect
import json
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from wulf_web_leader.models import CanonicalLead, AuditResult
from wulf_web_leader.adapters.nominatim import NominatimClient, GeocodedLocation
from wulf_web_leader.adapters.osm import OverpassClient
from wulf_web_leader.adapters.pl_ceidg import CEIDGAdapter
from wulf_web_leader.audit.cache import AuditCache
from wulf_web_leader.audit.fetch import AUDIT_USER_AGENT, audit_website
from wulf_web_leader.cli import app, load_leads_from_file
from wulf_web_leader.export.writer import export_leads_to_csv
from wulf_web_leader.export.report import generate_html_report
from wulf_web_leader.pipeline import run_scan_pipeline
from wulf_web_leader.verticals import find_vertical

runner = CliRunner()


# --- BUG 1: import re in fetch.py ---

@pytest.mark.asyncio
async def test_bug1_fetch_regex_fallback_without_crash():
    """Verify that when HTML contains plain-text email but no mailto: links,
    the regex fallback in audit_website executes re.findall cleanly without NameError."""
    html_with_plain_email = (
        b"<!DOCTYPE html><html><head><title>Test</title></head>"
        b"<body><p>Contact us at info@example-firma.pl anytime.</p></body></html>"
    )

    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.url = "https://example-firma.pl"
    mock_resp.is_redirect = False
    mock_resp.headers = {"Content-Type": "text/html"}

    async def fake_aiter_bytes():
        yield html_with_plain_email

    mock_resp.aiter_bytes = fake_aiter_bytes

    stream_cm = MagicMock()
    stream_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    stream_cm.__aexit__ = AsyncMock(return_value=None)

    client_instance = MagicMock()
    client_instance.stream.return_value = stream_cm
    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=client_instance)
    client_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("wulf_web_leader.audit.fetch.validate_url_safety", return_value=(True, None)):
        with patch("httpx.AsyncClient", return_value=client_cm):
            result = await audit_website("https://example-firma.pl")

    assert result.reachable is True
    assert "info@example-firma.pl" in result.extracted_emails


# --- BUG 2: Nominatim _rate_limit async ---

def test_bug2_nominatim_rate_limit_is_coroutine():
    """Verify NominatimClient._rate_limit is an async coroutine function."""
    assert inspect.iscoroutinefunction(NominatimClient._rate_limit)


@pytest.mark.asyncio
async def test_bug2_nominatim_rate_limit_uses_asyncio_sleep(tmp_path: Path):
    """Verify _rate_limit calls await asyncio.sleep when elapsed time < min_interval."""
    nom = NominatimClient(cache_dir=tmp_path, min_interval_seconds=1.0)
    nom._last_request_time = 100.0

    with patch("time.time", side_effect=[100.2, 101.0]):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await nom._rate_limit()
            mock_sleep.assert_awaited_once()
            # elapsed was 0.2, min_interval 1.0 -> sleep roughly 0.8
            args, _ = mock_sleep.call_args
            assert abs(args[0] - 0.8) < 1e-5


# --- BUG 3: AuditCache dirty flag and flush ---

def test_bug3_cache_dirty_flag_and_flush_flow(tmp_path: Path):
    cache = AuditCache(cache_dir=tmp_path)
    assert cache._dirty is False
    assert not cache.cache_file.exists()

    url = "https://cache-perf-test.com"
    audit = AuditResult(reachable=True, status_code=200, final_url=url)

    cache.set(url, audit)
    assert cache._dirty is True
    assert not cache.cache_file.exists()

    cache.flush()
    assert cache._dirty is False
    assert cache.cache_file.exists()


@pytest.mark.asyncio
async def test_bug3_pipeline_calls_cache_flush(tmp_path: Path):
    cache = AuditCache(cache_dir=tmp_path)
    cache.flush = MagicMock(wraps=cache.flush)

    vertical = find_vertical("plumbers")
    assert vertical is not None

    class MockNom(NominatimClient):
        async def geocode(self, city: str, country: str):
            return GeocodedLocation(lat=50.0, lon=20.0, display_name="Test City", city="Test")

    class MockOverpass(OverpassClient):
        async def execute_query(self, query: str):
            return [
                {
                    "type": "node",
                    "id": 123,
                    "lat": 50.0,
                    "lon": 20.0,
                    "tags": {"name": "Test Firma", "website": "https://test-pipe.pl"},
                }
            ]

    fake_res = AuditResult(reachable=True, status_code=200, final_url="https://test-pipe.pl")
    with patch("wulf_web_leader.pipeline.audit_website", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = fake_res

        await run_scan_pipeline(
            country="PL",
            city="Test",
            vertical=vertical,
            do_audit=True,
            audit_cache=cache,
            nominatim_client=MockNom(),
            overpass_client=MockOverpass(),
        )

    cache.flush.assert_called()


# --- BUG 4: User-Agent 0.3.0 ---

def test_bug4_user_agents_updated_to_0_3_0(tmp_path: Path):
    nom_default = NominatimClient(cache_dir=tmp_path)
    assert "0.3.0" in nom_default.headers["User-Agent"]
    assert "0.1.0" not in nom_default.headers["User-Agent"]

    nom_custom = NominatimClient(email="lead@wulf.dev", cache_dir=tmp_path)
    assert "0.3.0" in nom_custom.headers["User-Agent"]
    assert "0.1.0" not in nom_custom.headers["User-Agent"]

    overpass = OverpassClient()
    assert "0.3.0" in overpass.headers["User-Agent"]
    assert "0.1.0" not in overpass.headers["User-Agent"]

    assert "0.3.0" in AUDIT_USER_AGENT
    assert "0.1.0" not in AUDIT_USER_AGENT

    ceidg_path = Path(__file__).resolve().parent.parent / "src/wulf_web_leader/adapters/pl_ceidg.py"
    content = ceidg_path.read_text(encoding="utf-8")
    assert '"User-Agent": "wulf-web-leader/0.3.0"' in content
    assert "wulf-web-leader/0.1.0" not in content


# --- BUG 5: Remove lazy/function-body imports ---

def test_bug5_top_level_imports_in_pipeline_and_fetch():
    import wulf_web_leader.pipeline as pipeline_mod
    import wulf_web_leader.audit.fetch as fetch_mod

    assert hasattr(pipeline_mod, "is_corporate_entity")
    assert hasattr(pipeline_mod, "resolve_and_verify_candidate")

    assert hasattr(fetch_mod, "check_is_placeholder")
    assert hasattr(fetch_mod, "verify_entity_match")

    # Verify no local function imports inside pipeline.py
    pipeline_code = Path(pipeline_mod.__file__).read_text(encoding="utf-8")
    assert "    from wulf_web_leader.adapters.osm import is_corporate_entity" not in pipeline_code
    assert "    from wulf_web_leader.audit.verifier import resolve_and_verify_candidate" not in pipeline_code

    # Verify no local function imports inside fetch.py
    fetch_code = Path(fetch_mod.__file__).read_text(encoding="utf-8")
    assert "    from wulf_web_leader.audit.verifier import check_is_placeholder" not in fetch_code


# --- BUG 6: Remove unnecessary getattr on CanonicalLead ---

def test_bug6_no_getattr_in_export_writer_and_report():
    writer_code = (Path(__file__).resolve().parent.parent / "src/wulf_web_leader/export/writer.py").read_text(encoding="utf-8")
    report_code = (Path(__file__).resolve().parent.parent / "src/wulf_web_leader/export/report.py").read_text(encoding="utf-8")

    assert "getattr(" not in writer_code
    assert "getattr(" not in report_code


def test_bug6_writer_and_report_handle_canonical_lead(tmp_path: Path):
    lead = CanonicalLead(
        country="PL",
        name="Lead Bez Getattr",
        street="Krakowska 5",
        city="Rzeszów",
        postcode="35-001",
        phone="+48170000000",
        email="kontakt@firma.pl",
        website="https://firma.pl",
        website_kind="own",
        opportunity_type="critical_redesign",
        primary_issue="Brak RWD",
        confidence="high",
        qa_status="verified",
        qa_notes="Zweryfikowano pomyślnie",
        status_kontaktu="Do kontaktu",
        notatki="Ważny klient",
        data_kontaktu="2026-09-09",
        source="osm",
        source_id="node/999",
        industry_label="Hydraulik",
        score=85,
        verdict="hot",
        hooks=["Nowoczesna strona zwiększy konwersję."],
    )

    csv_file = tmp_path / "out.csv"
    export_leads_to_csv([lead], csv_file)
    assert csv_file.is_file()
    content = csv_file.read_text(encoding="utf-8-sig")
    assert "Lead Bez Getattr" in content
    assert "Krakowska 5" in content
    assert "kontakt@firma.pl" in content

    html_file = tmp_path / "out.html"
    generate_html_report([lead], html_file)
    assert html_file.is_file()
    html_content = html_file.read_text(encoding="utf-8")
    assert "Lead Bez Getattr" in html_content
    assert "Krakowska 5" in html_content
    assert "kontakt@firma.pl" in html_content


# --- BUG 7: load_leads_from_file in cli.py ---

def test_bug7_load_leads_from_file(tmp_path: Path):
    valid_file = tmp_path / "leads.json"
    data = {
        "leads": [
            {
                "country": "PL",
                "name": "Firma Testowa",
                "source": "osm",
                "source_id": "node/1",
                "industry_label": "Hydraulik",
            }
        ]
    }
    valid_file.write_text(json.dumps(data), encoding="utf-8")

    loaded = load_leads_from_file(valid_file)
    assert len(loaded) == 1
    assert loaded[0].name == "Firma Testowa"

    # Missing file exits with code 1
    with pytest.raises(typer.Exit) as exc_info:
        load_leads_from_file(tmp_path / "non_existent.json")
    assert exc_info.value.exit_code == 1

    # Corrupt file exits with code 1
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("invalid json content", encoding="utf-8")
    with pytest.raises(typer.Exit) as exc_info:
        load_leads_from_file(corrupt_file)
    assert exc_info.value.exit_code == 1


def test_bug7_cli_commands_use_load_leads_from_file(tmp_path: Path):
    input_file = tmp_path / "leads.json"
    data = {
        "leads": [
            {
                "country": "PL",
                "name": "Firma CLI",
                "source": "osm",
                "source_id": "node/2",
                "industry_label": "Hydraulik",
                "score": 80,
                "phone": "+48 111 222 333",
            }
        ]
    }
    input_file.write_text(json.dumps(data), encoding="utf-8")

    # Test export command
    out_csv = tmp_path / "export.csv"
    res_export = runner.invoke(app, ["export", str(input_file), "-o", str(out_csv)])
    assert res_export.exit_code == 0
    assert out_csv.is_file()

    # Test filter command
    out_filter = tmp_path / "filter.csv"
    res_filter = runner.invoke(app, ["filter", str(input_file), "-o", str(out_filter)])
    assert res_filter.exit_code == 0
    assert out_filter.is_file()

    # Test report command
    out_report = tmp_path / "report.html"
    res_report = runner.invoke(app, ["report", str(input_file), "-o", str(out_report)])
    assert res_report.exit_code == 0
    assert out_report.is_file()


# --- BUG 8: Documentation comments for verify=False ---

def test_bug8_ssl_verify_false_comments_present():
    fetch_code = (Path(__file__).resolve().parent.parent / "src/wulf_web_leader/audit/fetch.py").read_text(encoding="utf-8")
    verifier_code = (Path(__file__).resolve().parent.parent / "src/wulf_web_leader/audit/verifier.py").read_text(encoding="utf-8")

    assert "verify=False is intentional" in fetch_code
    assert "scoring criterion" in fetch_code

    assert "verify=False is intentional" in verifier_code
    assert "scoring criterion" in verifier_code
