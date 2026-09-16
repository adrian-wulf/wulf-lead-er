from wulf_web_leader.models import CanonicalLead, AuditResult
from wulf_web_leader.score.engine import calculate_lead_score
from wulf_web_leader.score.hooks import generate_pitch_hooks


def test_archetype_broken_website_status_code_404():
    """Broken website returning 404 is a high-priority HOT lead (score 85)."""
    lead = CanonicalLead(
        country="PL",
        name="Instalacje Sanitarne Jan Kowalski",
        city="Rzeszów",
        phone="+48 17 111 22 33",
        website="https://hydraulik-jan.pl",
        website_kind="own",
        source="osm",
        source_id="node/101",
        industry_label="Hydraulik",
        audit=AuditResult(reachable=False, status_code=404, error_message="HTTP 404"),
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 85
    assert verdict == "hot"
    assert lead.opportunity_type == "broken_website"
    assert lead.confidence == "high"
    assert "404" in (lead.primary_issue or "")

    hooks = generate_pitch_hooks(lead, lang="pl")
    assert any("nie działa" in h or "błąd" in h for h in hooks)


def test_archetype_broken_website_status_code_500():
    """Broken website returning 500 is a high-priority HOT lead (score 85)."""
    lead = CanonicalLead(
        country="DE",
        name="Klaus Sanitärtechnik",
        city="Hannover",
        phone="+49 511 999 888",
        website="https://klaus-sanitaer.de",
        website_kind="own",
        source="osm",
        source_id="node/102",
        industry_label="Klempner",
        audit=AuditResult(reachable=False, status_code=500, error_message="HTTP 500"),
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 85
    assert verdict == "hot"
    assert lead.opportunity_type == "broken_website"
    assert lead.confidence == "high"


def test_archetype_critical_redesign_no_mobile():
    """Website reachable but missing mobile viewport + no HTTPS is HOT 70."""
    lead = CanonicalLead(
        country="PL",
        name="Auto Naprawa Kowal",
        city="Kraków",
        phone="+48 12 345 67 89",
        website="http://kowal-auto.pl",
        website_kind="own",
        source="osm",
        source_id="node/103",
        industry_label="Mechanik",
        audit=AuditResult(
            reachable=True,
            is_https=False,
            has_viewport=False,
            has_impressum=False,
        ),
    )
    score, verdict = calculate_lead_score(lead)
    # 35 (no viewport) + 15 (no https) + 20 (phone) = 70
    assert score == 70
    assert verdict == "hot"
    assert lead.opportunity_type == "critical_redesign"
    assert lead.confidence == "high"


def test_archetype_critical_redesign_ancient_cms():
    """Website with old generator (FrontPage, Joomla) and missing viewport is HOT 85."""
    lead = CanonicalLead(
        country="DE",
        name="Feldheim & Söhne GmbH",
        city="Hannover",
        phone="+49 511 123456",
        website="https://pefeld.de",
        website_kind="own",
        source="osm",
        source_id="node/104",
        industry_label="Klempner",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=False,
            has_impressum=False,
            generator="HTML EDITOR",
        ),
    )
    score, verdict = calculate_lead_score(lead)
    # 35 (no viewport) + 15 (html editor) + 10 (no impressum DE) = 60 + 20 phone = 80
    assert score == 80
    assert verdict == "hot"
    assert lead.opportunity_type == "critical_redesign"


def test_archetype_social_only_facebook_is_hot():
    """Facebook-only business with phone is HOT 70."""
    lead = CanonicalLead(
        country="PL",
        name="Salon Fryzjerski Bella",
        city="Rzeszów",
        phone="+48 17 888 99 00",
        website="https://www.facebook.com/salonbellakrakow",
        website_kind="facebook",
        source="osm",
        source_id="node/105",
        industry_label="Fryzjer",
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 70
    assert verdict == "hot"
    assert lead.opportunity_type == "social_only"


def test_archetype_corporate_suspect_unverified():
    """Corporate entity without website tag in OSM is flagged as suspect_unverified (capped at WARM 50 to avoid false HOTs)."""
    lead = CanonicalLead(
        country="DE",
        name="Bauer Bauingenieure GmbH",
        city="Dresden",
        phone="+49 351 444 555",
        website=None,
        website_kind="none",
        source="osm",
        source_id="node/106",
        industry_label="Klempner",
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 50
    assert verdict == "warm"
    assert lead.opportunity_type == "suspect_unverified"
    assert lead.confidence == "low"
    assert "Spółka kapitałowa" in (lead.primary_issue or "")

    # Corporate entity without phone is score 30 (skip)
    lead_no_phone = CanonicalLead(
        country="DE",
        name="Bauer Bauingenieure GmbH",
        city="Dresden",
        phone=None,
        website=None,
        website_kind="none",
        source="osm",
        source_id="node/106b",
        industry_label="Klempner",
    )
    score2, verdict2 = calculate_lead_score(lead_no_phone)
    assert score2 == 30
    assert verdict2 == "skip"


def test_archetype_craftsman_no_website():
    """Unincorporated local craftsman without website is no_website with medium confidence."""
    lead = CanonicalLead(
        country="PL",
        name="Hydraulik Jan Nowak",
        city="Rzeszów",
        phone="+48 17 654 32 10",
        website=None,
        website_kind="none",
        source="osm",
        source_id="node/107",
        industry_label="Hydraulik",
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 70
    assert verdict == "hot"
    assert lead.opportunity_type == "no_website"
    assert lead.confidence == "medium"
