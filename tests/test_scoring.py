import pytest
from wulf_web_leader.models import CanonicalLead, AuditResult
from wulf_web_leader.score.engine import calculate_lead_score
from wulf_web_leader.score.hooks import generate_pitch_hooks


def test_scoring_no_website_with_phone():
    """Prime prospect: no website + listed phone should be HOT (>=70)."""
    lead = CanonicalLead(
        country="PL",
        name="Usługi Hydrauliczne Jan Kowalski",
        city="Rzeszów",
        phone="+48 17 123 45 67",
        website=None,
        website_kind="none",
        source="osm",
        source_id="node/101",
        industry_label="Hydraulik",
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 70  # 50 (no website) + 20 (phone)
    assert verdict == "hot"

    hooks = generate_pitch_hooks(lead, lang="pl")
    assert len(hooks) > 0
    assert "Brak strony www" in hooks[0]


def test_scoring_no_website_without_phone():
    """No website without phone should be WARM (>=45 and <70)."""
    lead = CanonicalLead(
        country="PL",
        name="Hydraulik Rzeszów",
        city="Rzeszów",
        phone=None,
        website=None,
        website_kind="none",
        source="osm",
        source_id="node/102",
        industry_label="Hydraulik",
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 50  # 50 (no website)
    assert verdict == "warm"


def test_scoring_social_and_directory_archetypes():
    """Social profiles (facebook, instagram) with phone are HOT (70); directory listings are WARM (65)."""
    for kind in ("facebook", "instagram"):
        lead = CanonicalLead(
            country="DE",
            name=f"Friseur Dresden {kind}",
            city="Dresden",
            phone="+49 351 987654",
            website=f"https://www.{kind}.com/friseur.dresden",
            website_kind=kind,  # type: ignore
            source="osm",
            source_id="node/201",
            industry_label="Friseur",
        )
        score, verdict = calculate_lead_score(lead)
        assert score == 70  # 50 (social) + 20 (phone)
        assert verdict == "hot"
        assert lead.opportunity_type == "social_only"

    dir_lead = CanonicalLead(
        country="DE",
        name="Friseur Dresden Directory",
        city="Dresden",
        phone="+49 351 987654",
        website="https://www.gelbeseiten.de/friseur.dresden",
        website_kind="directory",
        source="osm",
        source_id="node/202",
        industry_label="Friseur",
    )
    score_d, verdict_d = calculate_lead_score(dir_lead)
    assert score_d == 65  # 45 (directory) + 20 (phone)
    assert verdict_d == "warm"
    assert dir_lead.opportunity_type == "directory_only"


def test_scoring_broken_website():
    """Broken or unreachable website is a prime sales opportunity: HOT (85) with phone."""
    lead = CanonicalLead(
        country="PL",
        name="Elektryk Rzeszów Sp. z o.o.",
        city="Rzeszów",
        phone="+48 600 111 222",
        website="https://stary-elektryk-rzeszow-nie-dziala.pl",
        website_kind="own",
        source="osm",
        source_id="way/301",
        industry_label="Elektryk",
        audit=AuditResult(reachable=False, error_message="DNS resolution error"),
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 85  # 65 (broken) + 20 (phone)
    assert verdict == "hot"
    assert lead.opportunity_type == "broken_website"

    hooks = generate_pitch_hooks(lead, lang="pl")
    assert any("nie działa" in h or "błąd" in h for h in hooks)


def test_scoring_critical_redesign():
    """Outdated website without viewport and without HTTPS is a critical redesign: HOT (70) with phone."""
    lead = CanonicalLead(
        country="PL",
        name="Hydraulik Rzeszów",
        city="Rzeszów",
        phone="+48 600 222 333",
        website="http://hydraulik-rzeszow-stara-strona.pl",
        website_kind="own",
        source="osm",
        source_id="node/302",
        industry_label="Hydraulik",
        audit=AuditResult(
            reachable=True,
            is_https=False,
            has_viewport=False,
            has_impressum=False,
            generator="FrontPage 4.0",
        ),
    )
    score, verdict = calculate_lead_score(lead)
    # 35 (no viewport) + 15 (no https) + 15 (frontpage) = 65 flaws + 20 phone = 85
    assert score == 85
    assert verdict == "hot"
    assert lead.opportunity_type == "critical_redesign"


def test_scoring_inactive_business():
    """Inactive business should be immediately discarded (score 0, skip)."""
    lead = CanonicalLead(
        country="PL",
        name="Zamknięty Zakład",
        city="Rzeszów",
        phone="+48 600 999 888",
        website=None,
        website_kind="none",
        source="osm",
        source_id="node/404",
        industry_label="Hydraulik",
        registry_status="inactive",
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 0
    assert verdict == "skip"


def test_scoring_healthy_modern_website():
    """Business with HTTPS, viewport, modern site should be SKIP (<45), NOT hot or warm."""
    lead = CanonicalLead(
        country="DE",
        name="Top Modern Friseur GmbH",
        city="Dresden",
        phone="+49 351 123456",
        website="https://top-friseur-dresden.de",
        website_kind="own",
        source="osm",
        source_id="node/501",
        industry_label="Friseur",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=True,
            has_impressum=True,
            generator="Next.js",
        ),
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 20  # only 20 from phone, 0 from audit penalties
    assert verdict == "skip"
    assert verdict != "hot"
    assert verdict != "warm"
