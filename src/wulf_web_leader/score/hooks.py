import json
from pathlib import Path
from urllib.parse import urlparse
from wulf_web_leader.models import CanonicalLead

_LOCALES_CACHE: dict[str, dict] = {}


def get_locales_dir() -> Path:
    current = Path(__file__).resolve().parent
    candidates = [
        current.parent.parent.parent / "locales",
        current.parent / "locales",
        Path.cwd() / "locales",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return current.parent.parent.parent / "locales"


def load_locale(lang: str) -> dict:
    lang_code = lang.lower().strip()
    if lang_code in _LOCALES_CACHE:
        return _LOCALES_CACHE[lang_code]

    locales_dir = get_locales_dir()
    locale_file = locales_dir / f"{lang_code}.json"
    if not locale_file.is_file():
        locale_file = locales_dir / "en.json"

    try:
        with open(locale_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            _LOCALES_CACHE[lang_code] = data
            return data
    except Exception:
        return {"hooks": {}}


def extract_platform_name(url: str | None) -> str:
    if not url:
        return "Portal"
    try:
        hostname = (urlparse(url).hostname or "").lower()
        if "facebook" in hostname or "fb.com" in hostname:
            return "Facebook"
        if "instagram" in hostname:
            return "Instagram"
        if "panoramafirm" in hostname:
            return "Panorama Firm"
        if "pkt.pl" in hostname:
            return "PKT.pl"
        if "gelbeseiten" in hostname:
            return "Gelbe Seiten"
        if "dasoertliche" in hostname:
            return "Das Örtliche"
        if "dastelefonbuch" in hostname:
            return "Das Telefonbuch"
        if "znanylekarz" in hostname:
            return "ZnanyLekarz"
        if "booksy" in hostname:
            return "Booksy"
        return hostname.replace("www.", "")
    except Exception:
        return "Katalog"


def generate_pitch_hooks(lead: CanonicalLead, lang: str = "pl") -> list[str]:
    """Generate localized pitch hooks based on lead signals."""
    locale = load_locale(lang)
    hooks_dict = locale.get("hooks", {})
    results: list[str] = []

    # 0. Corporate Enterprise / Holding
    if lead.opportunity_type == "corporate_enterprise":
        hook = hooks_dict.get("corporate_enterprise")
        if hook:
            results.append(hook)
        return results

    # 1. Broken website
    if lead.opportunity_type == "broken_website":
        hook_tpl = hooks_dict.get("broken_website", "")
        url = lead.website or "firmowa strona"
        issue = lead.primary_issue or "błąd serwera"
        if hook_tpl:
            results.append(hook_tpl.format(url=url, issue=issue))


    # 2. Corporate suspect (unverified)
    elif lead.opportunity_type == "suspect_unverified":
        hook = hooks_dict.get("suspect_corporate")
        if hook:
            results.append(hook)

    # 3. No website hook
    elif lead.website_kind == "none" or lead.opportunity_type == "no_website":
        hook = hooks_dict.get("no_website")
        if hook:
            results.append(hook)

    # 4. Social-only hook
    elif lead.website_kind in ("facebook", "instagram"):
        hook_tpl = hooks_dict.get("social_only", "")
        platform = extract_platform_name(lead.website)
        if hook_tpl:
            results.append(hook_tpl.format(platform=platform))

    # 5. Directory hook
    elif lead.website_kind == "directory":
        hook_tpl = hooks_dict.get("directory_only", "")
        platform = extract_platform_name(lead.website)
        if hook_tpl:
            results.append(hook_tpl.format(platform=platform))

    # 6. Audit-derived hooks
    if lead.audit and lead.audit.reachable:
        if not lead.audit.has_viewport:
            hook = hooks_dict.get("no_viewport")
            if hook:
                results.append(hook)
        if not lead.audit.is_https:
            hook = hooks_dict.get("http_only")
            if hook:
                results.append(hook)
        if not lead.audit.has_impressum and lead.country == "DE":
            hook = hooks_dict.get("missing_impressum")
            if hook:
                results.append(hook)
        if lead.audit.generator:
            hook_tpl = hooks_dict.get("outdated_tech")
            if hook_tpl:
                results.append(hook_tpl.format(generator=lead.audit.generator))

        # Marketing intelligence & performance hooks
        if not lead.audit.detected_pixels:
            hook = hooks_dict.get("no_pixels")
            if not hook:
                hook = (
                    "Die Website verfügt weder über ein Meta-Pixel noch über Google Analytics 4 — Sie verlieren wertvolle Besucherdaten für Re-Targeting."
                    if (lang.lower().strip() == "de" or (lead.country == "DE" and lang.lower().strip() != "pl"))
                    else "Strona nie posiada zainstalowanego Pixela Meta ani Google Analytics 4 – tracą Państwo 100% danych o odwiedzających i nie prowadzicie remarketingu."
                )
            results.append(hook)

        if lead.audit.ttfb_ms is not None and lead.audit.ttfb_ms > 1000:
            ttfb_disp = int(lead.audit.ttfb_ms) if isinstance(lead.audit.ttfb_ms, int) or (isinstance(lead.audit.ttfb_ms, float) and lead.audit.ttfb_ms.is_integer()) else round(lead.audit.ttfb_ms)
            hook_tpl = hooks_dict.get("high_ttfb")
            if hook_tpl:
                results.append(hook_tpl.format(ttfb_ms=ttfb_disp))
            else:
                hook = (
                    f"Lange Server-Antwortzeit (TTFB: {ttfb_disp} ms) — langsame Ladezeiten führen zum Abbruch mobiler Besucher."
                    if (lang.lower().strip() == "de" or (lead.country == "DE" and lang.lower().strip() != "pl"))
                    else f"Długi czas odpowiedzi serwera (TTFB: {ttfb_disp} ms) spowalnia ładowanie strony — ponad 50% klientów mobilnych opuszcza wolne witryny."
                )
                results.append(hook)

    # 7. Google Maps rating reputation hook
    if lead.rating and lead.rating >= 4.0:
        rev_text = f" ({lead.reviews_count} opinii)" if lead.reviews_count else ""
        if lead.country == "DE":
            results.append(f"⭐ Hohe Google Maps-Bewertung: {lead.rating:.1f}/5.0{rev_text} — starkes Kundenvertrauen als Hebel nutzen.")
        else:
            results.append(f"⭐ Wysoka ocena w Google Maps: {lead.rating:.1f}/5.0{rev_text} — świetna lokalna reputacja, idealna baza pod nową stronę WWW.")

    # 8. Hot prospect summary hook
    if lead.score >= 70 and lead.phone:
        hook = hooks_dict.get("hot_prospect")
        if hook and hook not in results:
            results.append(hook)

    return results


def generate_greeting(lead: CanonicalLead, lang: str = "pl") -> str:
    """Generate personalized outreach greeting based on owner name or representative name."""
    is_de = lang.lower().strip() == "de" or (lead.country == "DE" and lang.lower().strip() != "pl")
    owner = lead.owner_name or (lead.audit.representative_name if lead.audit else None)

    if not owner:
        return "Sehr geehrte Damen und Herren," if is_de else "Dzień dobry,"

    if is_de:
        return f"Sehr geehrte(r) Frau/Herr {owner},"
    else:
        first_name = owner.split()[0]
        return f"Dzień dobry Panie/Pani {first_name},"


def generate_salutation(lead: CanonicalLead, lang: str = "pl") -> str:
    """Alias for generate_greeting."""
    return generate_greeting(lead, lang)


def generate_outreach_email(lead: CanonicalLead, lang: str | None = None) -> tuple[str, str]:
    """Generate localized cold email subject and body with personalized greeting and primary hook."""
    target_lang = (lang or (lead.country.lower() if lead.country else "pl")).lower().strip()
    primary_hook = lead.hooks[0] if lead.hooks else ""
    owner = lead.owner_name or (lead.audit.representative_name if lead.audit else None)

    if target_lang == "de":
        subject = f"Anfrage zur Website — {lead.name}"
        greeting = f"Sehr geehrte(r) Frau/Herr {owner}," if owner else "Sehr geehrte Damen und Herren,"
        body = (
            f"{greeting}\n\n"
            f"ich habe Ihr Unternehmen {lead.name} in {lead.city or ''} bemerkt.\n"
            f"{primary_hook}\n\n"
            f"Gerne erstelle ich für Sie einen unverbindlichen Vorschlag bzw. Entwurf für einen zeitgemäßen Webauftritt.\n\n"
            f"Mit freundlichen Grüßen"
        )
    else:
        subject = f"Zapytanie o stronę internetową — {lead.name}"
        greeting = f"Dzień dobry Panie/Pani {owner}," if owner else "Dzień dobry,"
        body = (
            f"{greeting}\n\n"
            f"Zauważyłem Państwa firmę {lead.name} w {lead.city or ''}.\n"
            f"{primary_hook}\n\n"
            f"Chętnie przygotuję dla Państwa propozycję / bezpłatny projekt strony www.\n\n"
            f"Pozdrawiam"
        )
    return subject, body
