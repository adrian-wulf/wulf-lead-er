import pytest
from unittest.mock import AsyncMock, patch

from wulf_web_leader.models import CanonicalLead, AuditResult
from wulf_web_leader.adapters.osm import (
    is_corporate_entity,
    is_joint_stock_or_enterprise,
)
from wulf_web_leader.audit.wikipedia_resolver import (
    clean_company_name_for_wiki,
    is_plausible_entity_match,
    lookup_company_wikipedia,
    WikipediaCompanyIntel,
)
from wulf_web_leader.score.engine import calculate_lead_score
from wulf_web_leader.score.hooks import generate_pitch_hooks


def test_enterprise_legal_form_detection_pl_and_de():
    """Verify detection of joint-stock companies, holdings, and enterprises in PL and DE."""
    # Polish enterprise forms
    assert is_joint_stock_or_enterprise("Veracomp S.A.") is True
    assert is_joint_stock_or_enterprise("Veracomp SA") is True
    assert is_joint_stock_or_enterprise("Asseco Poland Spółka Akcyjna") is True
    assert is_joint_stock_or_enterprise("Grupa Kapitałowa KGHM") is True
    assert is_joint_stock_or_enterprise("Polkomtel Holding") is True

    # German enterprise forms
    assert is_joint_stock_or_enterprise("Siemens AG") is True
    assert is_joint_stock_or_enterprise("Mannesmann Aktiengesellschaft") is True
    assert is_joint_stock_or_enterprise("Allianz SE") is True
    assert is_joint_stock_or_enterprise("Fresenius SE & Co. KGaA") is True
    assert is_joint_stock_or_enterprise("Volkswagen Konzern") is True

    # Non-enterprise entities
    assert is_joint_stock_or_enterprise("Auto Serwis Kowalski") is False
    assert is_joint_stock_or_enterprise("Piekarnia Jan Nowak") is False
    assert is_joint_stock_or_enterprise("Januszpol Sp. z o.o.") is False
    assert is_joint_stock_or_enterprise("Müller GmbH") is False


def test_clean_company_name_for_wiki():
    """Verify corporate suffixes are stripped cleanly for Wikipedia queries."""
    assert clean_company_name_for_wiki("Veracomp S.A.") == "Veracomp"
    assert clean_company_name_for_wiki("Siemens AG") == "Siemens"
    assert clean_company_name_for_wiki("Mannesmann AG") == "Mannesmann"
    assert clean_company_name_for_wiki("Allianz SE") == "Allianz"
    assert clean_company_name_for_wiki("EuroLinux Sp. z o.o.") == "EuroLinux"
    assert clean_company_name_for_wiki("Kowalski Usługi") == "Kowalski Usługi"


def test_is_plausible_entity_match():
    """Verify matching logic avoids false positive entity alignments."""
    assert is_plausible_entity_match("Veracomp", "Veracomp", "Veracomp S.A.") is True
    assert is_plausible_entity_match("Siemens", "Siemens", "Siemens AG") is True
    assert is_plausible_entity_match("Siemens Vectron", "Siemens", "Siemens AG") is True
    assert is_plausible_entity_match("Jan Kowalski (piłkarz)", "Auto Naprawa Kowalski", "Auto Naprawa Kowalski") is False


def test_enterprise_gate_scoring_pl():
    """Verify S.A. entity with dead domain is NEVER scored as HOT (score=0, verdict=skip)."""
    lead = CanonicalLead(
        source_id="v1",
        name="Veracomp S.A.",
        country="PL",
        city="Kraków",
        industry_label="IT",
        phone="+48 12 25 25 555",
        website="http://www.veracomp.pl",
        website_kind="own",
        audit=AuditResult(reachable=False, error_message="HTTP connection failed: ConnectTimeout"),
    )
    score, verdict = calculate_lead_score(lead)
    hooks = generate_pitch_hooks(lead, lang="pl")

    assert score == 0
    assert verdict == "skip"
    assert lead.opportunity_type == "corporate_enterprise"
    assert any("Podmiot korporacyjny" in h for h in hooks)
    assert not any("Idealny kandydat" in h for h in hooks)


def test_enterprise_gate_scoring_de():
    """Verify German AG entity with unreachable domain is scored as skip (score=0)."""
    lead = CanonicalLead(
        source_id="s1",
        name="Siemens AG",
        country="DE",
        city="München",
        industry_label="Elektro",
        phone="+49 89 123456",
        website="http://siemens-dead-domain.de",
        website_kind="own",
        audit=AuditResult(reachable=False, error_message="ConnectTimeout"),
    )
    score, verdict = calculate_lead_score(lead)
    hooks = generate_pitch_hooks(lead, lang="de")

    assert score == 0
    assert verdict == "skip"
    assert lead.opportunity_type == "corporate_enterprise"
    assert any("Großunternehmen" in h for h in hooks)
    assert not any("Top-Kandidat" in h for h in hooks)


def test_network_deadness_vs_active_server_error_scoring():
    """Verify that timeout/DNS deadness gives warm/skip (not 85 HOT), while active 500 gives HOT."""
    # Small business with ConnectTimeout (dead domain)
    lead_timeout = CanonicalLead(
        source_id="sb1",
        name="Auto Serwis Kowalski",
        country="PL",
        city="Wrocław",
        industry_label="Mechanika",
        phone="+48 600 100 200",
        website="http://serwis-kowalski-stary.pl",
        website_kind="own",
        audit=AuditResult(reachable=False, error_message="HTTP connection failed: ConnectTimeout"),
    )
    score_to, verdict_to = calculate_lead_score(lead_timeout)
    assert score_to == 55
    assert verdict_to == "warm"
    assert lead_timeout.opportunity_type == "suspect_unverified"

    # Small business with active HTTP 500 error
    lead_500 = CanonicalLead(
        source_id="sb2",
        name="Auto Serwis Kowalski",
        country="PL",
        city="Wrocław",
        industry_label="Mechanika",
        phone="+48 600 100 200",
        website="http://serwis-kowalski.pl",
        website_kind="own",
        audit=AuditResult(reachable=False, status_code=500, error_message="HTTP 500 Internal Server Error"),
    )
    score_500, verdict_500 = calculate_lead_score(lead_500)
    assert score_500 == 85
    assert verdict_500 == "hot"
    assert lead_500.opportunity_type == "broken_website"


@pytest.mark.asyncio
async def test_wikipedia_lookup_live_pl():
    """Verify live Wikipedia OSINT lookup on Veracomp S.A. detects rebranding and enterprise status."""
    lead = CanonicalLead(
        source_id="v1",
        name="Veracomp S.A.",
        country="PL",
        city="Kraków",
        industry_label="IT",
    )
    intel = await lookup_company_wikipedia(lead)
    assert intel is not None
    assert intel.found is True
    assert intel.title == "Veracomp"
    assert intel.is_enterprise is True
    assert intel.is_rebranded is True
    assert "Exclusive Networks" in (intel.new_brand_name or "")
    assert intel.wiki_url is not None


@pytest.mark.asyncio
async def test_wikipedia_lookup_live_de():
    """Verify live German Wikipedia lookup on Siemens AG detects enterprise status."""
    lead = CanonicalLead(
        source_id="d1",
        name="Siemens AG",
        country="DE",
        city="München",
        industry_label="Elektro",
    )
    intel = await lookup_company_wikipedia(lead)
    assert intel is not None
    assert intel.found is True
    assert intel.title == "Siemens"
    assert intel.is_enterprise is True
    assert "siemens.com" in (intel.replacement_website or "")
