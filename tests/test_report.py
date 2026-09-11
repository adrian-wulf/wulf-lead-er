import json
from pathlib import Path
from typer.testing import CliRunner
from wulf_web_leader.cli import app
from wulf_web_leader.models import CanonicalLead
from wulf_web_leader.export.report import generate_html_report

runner = CliRunner()


def test_generate_html_report_contains_lead_data(tmp_path: Path):
    """Test directly generating HTML report from CanonicalLead sequence."""
    out_file = tmp_path / "report.html"
    leads = [
        CanonicalLead(
            country="PL",
            name="Instalator Pro Hydraulika",
            city="Rzeszów",
            street="Hetmańska 15",
            postcode="35-045",
            phone="+48 17 800 11 22",
            email="kontakt@instalator-rzeszow.pl",
            website=None,
            website_kind="none",
            source="osm",
            source_id="node/999",
            lat=50.03,
            lon=22.01,
            industry_label="Hydraulik",
            score=70,
            verdict="hot",
            hooks=["Brak strony www — klienci z okolicy trafiają do konkurencji."],
        ),
        CanonicalLead(
            country="PL",
            name="Stary Warsztat Samochodowy",
            city="Rzeszów",
            phone="+48 17 800 33 44",
            email=None,
            website="https://fb.com/starywarsztat",
            website_kind="facebook",
            source="osm",
            source_id="node/888",
            industry_label="Mechanik",
            score=55,
            verdict="warm",
        ),
    ]

    res = generate_html_report(leads, out_file)
    assert res.is_file()
    html_content = res.read_text(encoding="utf-8")

    # Lead 1: HOT with email
    assert "Instalator Pro Hydraulika" in html_content
    assert "verdict-hot" in html_content
    assert "+48 17 800 11 22" in html_content
    assert "tel:+48 17 800 11 22" in html_content
    assert "kontakt@instalator-rzeszow.pl" in html_content
    assert "mailto:kontakt@instalator-rzeszow.pl" in html_content
    assert "btn-copy-email" in html_content
    assert 'data-has-email="true"' in html_content
    assert "openstreetmap.org/?mlat=50.03&amp;mlon=22.01" in html_content or "openstreetmap.org/?mlat=50.03&mlon=22.01" in html_content
    assert "Brak strony www" in html_content
    assert "Brak strony www — klienci z okolicy" in html_content

    # Lead 2: WARM without email
    assert "Stary Warsztat Samochodowy" in html_content
    assert "verdict-warm" in html_content
    assert 'data-has-email="false"' in html_content
    assert "Brak adresu e-mail" in html_content

    # UI elements
    assert "do uzupełnienia w CSV" in html_content
    assert "OpenStreetMap contributors under ODbL 1.0" in html_content
    assert 'id="email-only-checkbox"' in html_content
    assert "copyEmail(" in html_content


def test_wulf_report_cli_command(tmp_path: Path, monkeypatch):
    """Test wulf report CLI command on a mock leads.json file."""
    monkeypatch.chdir(tmp_path)
    leads = [
        CanonicalLead(
            country="PL",
            name="Super Serwis Rowerowy",
            city="Rzeszów",
            phone="+48 17 855 44 33",
            website=None,
            website_kind="none",
            source="osm",
            source_id="node/12345",
            industry_label="Serwis rowerowy",
            score=70,
            verdict="hot",
            hooks=["Brak strony internetowej w okolicy."],
        )
    ]

    json_path = tmp_path / "leads.json"
    json_path.write_text(
        json.dumps({
            "_attribution": "OSM",
            "count": len(leads),
            "leads": [l.model_dump(mode="json") for l in leads],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    out_html = tmp_path / "custom_report.html"

    result = runner.invoke(
        app,
        ["report", str(json_path), "--out", str(out_html)],
    )
    assert result.exit_code == 0
    assert out_html.is_file()
    content = out_html.read_text(encoding="utf-8")
    assert "Super Serwis Rowerowy" in content
    assert "verdict-hot" in content
    assert "+48 17 855 44 33" in content


def test_wulf_report_cli_default_out(tmp_path: Path, monkeypatch):
    """Test wulf report CLI command with default arguments generates report.html."""
    monkeypatch.chdir(tmp_path)
    leads = [
        CanonicalLead(
            country="PL",
            name="Salon Fryzjerski Pasja",
            city="Rzeszów",
            phone="+48 17 811 22 33",
            source="osm",
            source_id="node/777",
            industry_label="Fryzjer",
            score=70,
            verdict="hot",
        )
    ]
    (tmp_path / "leads.json").write_text(
        json.dumps({
            "count": 1,
            "leads": [l.model_dump(mode="json") for l in leads],
        }, ensure_ascii=False),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0
    default_report = tmp_path / "report.html"
    assert default_report.is_file()
    content = default_report.read_text(encoding="utf-8")
    assert "Salon Fryzjerski Pasja" in content
    assert "verdict-hot" in content


def test_wulf_report_missing_file_error():
    """Test that wulf report with non-existent file gives friendly Polish error without traceback."""
    result = runner.invoke(app, ["report", "nieistniejacy_plik.json"])
    assert result.exit_code == 1
    assert "Błąd:" in result.output
    assert "nie istnieje" in result.output
    assert "Traceback" not in result.output
