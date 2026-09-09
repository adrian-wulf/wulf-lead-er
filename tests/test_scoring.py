import pytest
from brakstrony.models import CanonicalLead, AuditResult
from brakstrony.score.engine import calculate_lead_score
from brakstrony.score.hooks import generate_pitch_hooks


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
    """No website without phone should be WARM (>=45)."""
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


def test_scoring_social_only_with_phone():
    """Social profile only + phone should be WARM (55)."""
    lead = CanonicalLead(
        country="DE",
        name="Friseur Dresden Meister",
        city="Dresden",
        phone="+49 351 987654",
        website="https://www.facebook.com/friseur.dresden",
        website_kind="facebook",
        source="osm",
        source_id="node/201",
        industry_label="Friseur",
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 55  # 35 (social) + 20 (phone)
    assert verdict == "warm"

    hooks_de = generate_pitch_hooks(lead, lang="de")
    assert any("Facebook" in h for h in hooks_de)


def test_scoring_broken_website():
    """Website exists in OSM but is completely unreachable should be HOT (>=70) if phone present."""
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
    assert score == 60  # 40 (broken) + 20 (phone)
    assert verdict == "warm"


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
    """Business with HTTPS, viewport, modern site should be SKIP (<45)."""
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
            generator="Next.js",
        ),
    )
    score, verdict = calculate_lead_score(lead)
    assert score == 20  # only 20 from phone, 0 from audit penalties
    assert verdict == "skip"
