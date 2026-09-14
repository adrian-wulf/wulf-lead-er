import json
import urllib.parse
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


def test_html_report_phase3_features(tmp_path: Path):
    """Test Phase 3 HTML report badges, CTA buttons, TTFB indicators, and personalized mailto."""
    from wulf_web_leader.models import AuditResult
    out_file = tmp_path / "report_phase3.html"

    leads = [
        CanonicalLead(
            country="PL",
            name="Nowoczesny Warsztat Auto-Fix",
            owner_name="Adam Nowak",
            nip="1234567890",
            regon="987654321",
            city="Rzeszów",
            phone="+48 601 111 222",
            phone_type="mobile",
            whatsapp_url="https://wa.me/48601111222",
            email="adam@autofix.pl",
            website="https://autofix.pl",
            website_kind="own",
            source="osm",
            source_id="node/101",
            industry_label="Mechanik",
            score=75,
            verdict="hot",
            hooks=["Świetna reputacja, idealna baza pod nową stronę WWW."],
            audit=AuditResult(
                reachable=True,
                is_https=True,
                has_viewport=True,
                detected_pixels=["Meta Pixel", "Google Analytics 4"],
                ttfb_ms=280.0,
                social_links={
                    "facebook": "https://facebook.com/autofix",
                    "instagram": "https://instagram.com/autofix",
                    "youtube": "https://youtube.com/@autofix",
                },
            ),
        ),
        CanonicalLead(
            country="DE",
            name="Elektro Müller GmbH",
            owner_name="Stefan Müller",
            city="München",
            phone="+49 89 123456",
            phone_type="landline",
            whatsapp_url=None,
            email="kontakt@elektro-mueller.de",
            website="https://elektro-mueller.de",
            website_kind="own",
            source="osm",
            source_id="node/102",
            industry_label="Elektriker",
            score=60,
            verdict="warm",
            hooks=["Die Website verfügt weder über ein Meta-Pixel noch über Google Analytics 4 — Sie verlieren wertvolle Besucherdaten für Re-Targeting."],
            audit=AuditResult(
                reachable=True,
                is_https=True,
                has_viewport=True,
                has_impressum=True,
                detected_pixels=[],
                ttfb_ms=1350.0,
                social_links={
                    "linkedin": "https://linkedin.com/company/elektro-mueller",
                    "tiktok": "https://tiktok.com/@elektro_mueller",
                },
            ),
        ),
        CanonicalLead(
            country="PL",
            name="Salon Urody Średnia Prędkość",
            city="Kraków",
            phone="+48 12 345 67 89",
            phone_type="landline",
            email=None,
            website="https://uroda-srednia.pl",
            website_kind="own",
            source="osm",
            source_id="node/103",
            industry_label="Kosmetyczka",
            score=50,
            verdict="warm",
            audit=AuditResult(
                reachable=True,
                is_https=True,
                has_viewport=True,
                detected_pixels=["TikTok Pixel"],
                ttfb_ms=750,
            ),
        ),
    ]

    res = generate_html_report(leads, out_file)
    assert res.is_file()
    html = res.read_text(encoding="utf-8")

    # 1. WhatsApp button and phone badges
    assert '<a href="https://wa.me/48601111222" target="_blank" class="btn-whatsapp" title="Czat WhatsApp">💬 WhatsApp</a>' in html
    assert "📱 Komórka (SMS/WhatsApp)" in html
    assert "☎️ Stacjonarny" in html

    # 2. Decision maker / Owner badges & NIP / REGON
    assert '<span class="badge badge-owner">👤 Decydent: Adam Nowak</span>' in html
    assert '<span class="badge badge-nip">NIP: 1234567890</span>' in html
    assert '<span class="badge badge-regon">REGON: 987654321</span>' in html
    assert '<span class="badge badge-owner">👤 Decydent: Stefan Müller</span>' in html

    # 3. Social Media links
    assert "social-facebook" in html and "Facebook" in html
    assert "social-instagram" in html and "Instagram" in html
    assert "social-youtube" in html and "YouTube" in html
    assert "social-linkedin" in html and "LinkedIn" in html
    assert "social-tiktok" in html and "TikTok" in html

    # 4. Marketing Pixels badges & missing analytics warning
    assert "📊 Meta Pixel" in html
    assert "📊 Google Analytics 4" in html
    assert "⚠️ Brak Pixela Meta / GA4 (Brak analityki)" in html

    # 5. TTFB indicators: green (<500ms), yellow (500-1000ms), red (>1000ms)
    assert "ttfb-fast" in html and "⚡ TTFB: 280 ms" in html
    assert "ttfb-medium" in html and "⚡ TTFB: 750 ms" in html
    assert "ttfb-slow" in html and "⚡ TTFB: 1350 ms" in html

    # 6. Personalized mailto body
    assert "Dzie%C5%84%20dobry%20Panie/Pani%20Adam%20Nowak" in html or "Dzień dobry Panie/Pani Adam Nowak" in urllib.parse.unquote(html)
    assert "Sehr%20geehrte%28r%29%20Frau/Herr%20Stefan%20M%C3%BCller" in html or "Sehr geehrte(r) Frau/Herr Stefan Müller" in urllib.parse.unquote(html)

