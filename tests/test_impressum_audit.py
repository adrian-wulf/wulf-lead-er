import pytest
from wulf_web_leader.audit.parser import SafeWebsiteHTMLParser
from wulf_web_leader.models import CanonicalLead, AuditResult
from wulf_web_leader.score.engine import calculate_lead_score
from wulf_web_leader.score.hooks import generate_pitch_hooks


def test_parser_detects_impressum():
    """WE.2: Parser poprawnie wykrywa obecność linku do Impressum w HTML."""
    html_with_impressum = """
    <html>
        <body>
            <h1>Malerbetrieb Schmidt</h1>
            <footer>
                <a href="/impressum.html">Impressum & Datenschutz</a>
            </footer>
        </body>
    </html>
    """
    parser1 = SafeWebsiteHTMLParser()
    parser1.feed(html_with_impressum)
    assert parser1.has_impressum is True

    html_without_impressum = """
    <html>
        <body>
            <h1>Malerbetrieb Schmidt</h1>
            <footer>
                <a href="/contact">Kontakt</a>
            </footer>
        </body>
    </html>
    """
    parser2 = SafeWebsiteHTMLParser()
    parser2.feed(html_without_impressum)
    assert parser2.has_impressum is False


def test_missing_impressum_boosts_lead_score():
    """WE.2: Brak Impressum podnosi wynik jakościowy leada (sygnał zaniedbania witryny)."""
    lead_with_impressum = CanonicalLead(
        country="DE",
        name="Schmidt Maler GmbH",
        city="Dresden",
        source="osm",
        source_id="node/1",
        website="https://schmidt-maler.de",
        website_kind="own",
        phone="+49351000000",
        industry_label="Maler",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=True,
            has_impressum=True,
        ),
    )
    score_with, _ = calculate_lead_score(lead_with_impressum)

    lead_no_impressum = CanonicalLead(
        country="DE",
        name="Schmidt Maler GmbH",
        city="Dresden",
        source="osm",
        source_id="node/1",
        website="https://schmidt-maler.de",
        website_kind="own",
        phone="+49351000000",
        industry_label="Maler",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=True,
            has_impressum=False,
        ),
    )
    score_without, _ = calculate_lead_score(lead_no_impressum)

    assert score_without == score_with + 10


def test_impressum_hooks_strictly_business_no_legal_threats():
    """WE.2: Wygenerowane hooki (PL/DE/EN) są biznesowe i nie zawierają gróźb prawnych (Abmahnung, kary itp.)."""
    lead = CanonicalLead(
        country="DE",
        name="Bäcker Müller",
        city="Dresden",
        source="osm",
        source_id="node/2",
        website="https://baecker-mueller.de",
        website_kind="own",
        phone="+49351000000",
        industry_label="Bäcker",
        audit=AuditResult(
            reachable=True,
            is_https=True,
            has_viewport=True,
            has_impressum=False,
        ),
    )

    forbidden_legal_words = [
        "abmahnung",
        "abmahn",
        "ordnungswidrigkeit",
        "bußgeld",
        "kara",
        "kary",
        "pozew",
        "sąd",
        "paragraf",
        "§",
        "illegal",
        "tmg",
        "ddg",
    ]

    for lang in ("de", "pl", "en"):
        hooks = generate_pitch_hooks(lead, lang=lang)
        assert len(hooks) >= 1
        joined = " ".join(hooks).lower()
        for forbidden in forbidden_legal_words:
            assert forbidden not in joined, f"Forbidden word '{forbidden}' found in hook for lang '{lang}': {joined}"
