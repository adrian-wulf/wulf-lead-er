import pytest
from unittest.mock import AsyncMock, patch
from wulf_web_leader.models import CanonicalLead, AuditResult
from wulf_web_leader.audit.verifier import (
    check_is_placeholder,
    verify_entity_match,
    generate_domain_candidates,
    resolve_and_verify_candidate,
)
from wulf_web_leader.score.engine import calculate_lead_score


def test_check_is_placeholder_detects_german_and_polish_patterns():
    # 1. pefeld.de webmailer setup page pattern
    html_pefeld = """
    <html>
    <head><base href="http://www.webmailer.de/setup/setup3/"></head>
    <body>
    <h1>Sie sehen hier eine soeben freigeschaltete Homepage</h1>
    </body>
    </html>
    """
    is_p, reason = check_is_placeholder(html_pefeld)
    assert is_p is True
    assert "soeben freigeschaltete Homepage" in (reason or "")

    # 2. German "Hier entsteht"
    html_de_construction = "<html><body>Hier entsteht eine neue Internetpräsenz der Firma</body></html>"
    is_p2, _ = check_is_placeholder(html_de_construction)
    assert is_p2 is True

    # 3. Polish "Strona w budowie"
    html_pl_construction = "<html><body><h1>Strona w budowie</h1><p>Zapraszamy wkrótce.</p></body></html>"
    is_p3, _ = check_is_placeholder(html_pl_construction)
    assert is_p3 is True

    # 4. Polish "Domena zaparkowana"
    html_pl_parked = "<html><body>Ta domena jest na sprzedaż w serwisie AfterMarket</body></html>"
    is_p4, _ = check_is_placeholder(html_pl_parked)
    assert is_p4 is True

    # 5. Real active business page should NOT be flagged as placeholder
    html_real = """
    <html>
    <head><title>Feldheim & Söhne GmbH - Sanitär und Heizung</title></head>
    <body>
    <h1>Willkommen bei Feldheim & Söhne GmbH</h1>
    <p>Lister Meile 31, 30161 Hannover</p>
    <p>Telefon: +49 511 990830</p>
    <p>Notdienst rund um die Uhr für Sanitär und Heizung.</p>
    </body>
    </html>
    """
    is_p_real, reason_real = check_is_placeholder(html_real)
    assert is_p_real is False
    assert reason_real is None


def test_verify_entity_match_accuracy():
    # Case A: pefeld.de has zero entity tokens for Feldheim & Söhne
    pefeld_text = "Sie sehen hier eine soeben freigeschaltete Homepage auf webmailer.de"
    score_a, signals_a, conf_a = verify_entity_match(
        lead_name="Feldheim & Söhne GmbH",
        city="Hannover",
        phone="+49 511 990830",
        address="Lister Meile 31",
        html_text=pefeld_text,
    )
    assert score_a == 0
    assert conf_a == "mismatch"
    assert len(signals_a) == 0

    # Case B: Real site matches name, phone, city, and street
    real_text = """
    Firma Feldheim & Söhne GmbH
    Lister Meile 31, 30161 Hannover
    Telefon: 0511-99083-0
    E-Mail: info@pefeld.de
    """
    score_b, signals_b, conf_b = verify_entity_match(
        lead_name="Feldheim & Söhne GmbH",
        city="Hannover",
        phone="+49 511 990830",
        address="Lister Meile 31",
        html_text=real_text,
    )
    assert score_b == 100
    assert conf_b == "high"
    assert any("name_tokens:feldheim" in s for s in signals_b)
    assert any("phone:990830" in s for s in signals_b)
    assert any("city:Hannover" in s for s in signals_b)
    assert any("street:lister meile" in s for s in signals_b)


def test_generate_domain_candidates():
    candidates_de = generate_domain_candidates(
        company_name="Feldheim & Söhne GmbH",
        city="Hannover",
        country="DE",
        vertical_keywords=["sanitaer", "heizung"],
    )
    assert "feldheim.de" in candidates_de
    assert "feldheim-hannover.de" in candidates_de
    assert "feldheim-sanitaer-heizung.de" in candidates_de

    candidates_pl = generate_domain_candidates(
        company_name="Hydraulik Jan Kowalski",
        city="Rzeszów",
        country="PL",
        vertical_keywords=["hydraulik", "instalacje"],
    )
    assert "kowalski.pl" in candidates_pl
    assert "kowalski-rzeszow.pl" in candidates_pl
    assert "kowalski-rzeszow.com.pl" in candidates_pl


@pytest.mark.asyncio
async def test_resolve_and_verify_candidate_success():
    lead = CanonicalLead(
        country="DE",
        name="Feldheim & Söhne GmbH",
        city="Hannover",
        phone="+49 511 990830",
        address="Lister Meile 31",
        website="https://pefeld.de",
        website_kind="own",
        website_source="email_domain",
        source="osm",
        source_id="node/999",
        industry_label="Klempner",
    )

    fake_real_audit = AuditResult(
        reachable=True,
        status_code=200,
        final_url="https://feldheim-sanitaer-heizung.de/",
        is_https=True,
        has_viewport=True,
        has_impressum=True,
        entity_match=True,
        entity_match_score=100,
        matched_signals=["name_tokens:feldheim", "phone:990830", "city:Hannover"],
    )

    with patch("wulf_web_leader.audit.verifier.check_dns_resolves", new_callable=AsyncMock) as mock_dns, \
         patch("wulf_web_leader.audit.fetch.audit_website", new_callable=AsyncMock) as mock_audit:

        # Mock that feldheim-sanitaer-heizung.de resolves in DNS
        mock_dns.side_effect = lambda d: d == "feldheim-sanitaer-heizung.de"
        mock_audit.return_value = fake_real_audit

        res = await resolve_and_verify_candidate(lead, vertical_keywords=["sanitaer", "heizung"])
        assert res is not None
        verified_url, audit_res, method = res
        assert verified_url == "https://feldheim-sanitaer-heizung.de/"
        assert audit_res.entity_match_score == 100
        assert method == "dns_candidate"


def test_scoring_placeholder_vs_verified_active():
    # 1. Lead with unreplaced placeholder domain -> score 85 HOT (broken_website)
    placeholder_lead = CanonicalLead(
        country="DE",
        name="Parked Craft GmbH",
        city="Hannover",
        phone="+49 511 112233",
        website="https://parked-craft.de",
        website_kind="own",
        qa_status="placeholder",
        source="osm",
        source_id="node/201",
        industry_label="Klempner",
        audit=AuditResult(
            reachable=True,
            status_code=200,
            is_placeholder=True,
            placeholder_reason="Wykryto wzorzec zaślepki/parkingu",
        ),
    )
    score_p, verdict_p = calculate_lead_score(placeholder_lead)
    assert score_p == 85
    assert verdict_p == "hot"
    assert placeholder_lead.opportunity_type == "broken_website"
    assert "zaślepk" in (placeholder_lead.primary_issue or "").lower()

    # 2. Lead where real site was verified and healthy -> score 0 SKIP (modern_active)
    verified_lead = CanonicalLead(
        country="DE",
        name="Feldheim & Söhne GmbH",
        city="Hannover",
        phone="+49 511 990830",
        website="https://feldheim-sanitaer-heizung.de/",
        website_kind="own",
        qa_status="verified",
        source="osm",
        source_id="node/202",
        industry_label="Klempner",
        audit=AuditResult(
            reachable=True,
            status_code=200,
            is_https=True,
            has_viewport=True,
            has_impressum=True,
            is_placeholder=False,
            entity_match=True,
            entity_match_score=100,
        ),
    )
    score_v, verdict_v = calculate_lead_score(verified_lead)
    assert score_v <= 20
    assert verdict_v == "skip"
    assert verified_lead.opportunity_type == "modern_active"


def test_generate_domain_candidates_german_vorwahl_and_kfz():
    """Vorwahl 0531 (+49531) maps to Braunschweig and Kfz 'bs' -> generates bonse-bs.de."""
    candidates = generate_domain_candidates(
        company_name="Gustav Bonse Betr. GmbH+Co.KG",
        city="Nettlingen",
        phone="+49531340801",
        country="DE",
    )
    assert "bonse-bs.de" in candidates
    assert "gustav-bonse-bs.de" in candidates
    assert "bonse-braunschweig.de" in candidates


@pytest.mark.asyncio
async def test_query_google_custom_search_mocked(monkeypatch):
    """Google Custom Search JSON API parser extracts authentic domain and skips directories."""
    from wulf_web_leader.audit.verifier import query_google_custom_search
    import httpx

    monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
    monkeypatch.setenv("GOOGLE_CSE_ID", "fake-cse")

    fake_google_json = {
        "items": [
            {"link": "https://www.gelbeseiten.de/gsbiz/12345"},  # directory -> skipped
            {"link": "https://bonse-bs.de/leistungen/"},         # authentic origin -> accepted
            {"link": "https://facebook.com/bonse"},              # social -> skipped
        ]
    }

    from unittest.mock import MagicMock
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_google_json
    mock_client.get.return_value = mock_resp

    found_url = await query_google_custom_search(
        company_name="Gustav Bonse",
        city="Braunschweig",
        phone="+49531340801",
        client=mock_client,
    )
    assert found_url == "https://bonse-bs.de/"


def test_html_report_renders_google_check_button(tmp_path):
    """Report HTML contains interactive 1-click Google search button for suspect/unverified leads."""
    from wulf_web_leader.export.report import generate_html_report

    lead_suspect = CanonicalLead(
        country="DE",
        name="Gustav Bonse Betr. GmbH+Co.KG",
        city="Braunschweig",
        phone="+49531340801",
        website=None,
        website_kind="none",
        opportunity_type="suspect_unverified",
        qa_status="unverified",
        source="osm",
        source_id="node/9837063414",
        industry_label="Klempner",
        score=50,
        verdict="warm",
    )

    out_file = tmp_path / "test_report.html"
    generate_html_report([lead_suspect], out_file)
    content = out_file.read_text(encoding="utf-8")

    assert "btn-google-check" in content
    assert "google.com/search?q=" in content
    assert "Sprawdź w Google" in content
