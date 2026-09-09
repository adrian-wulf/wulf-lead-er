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

    # 1. No website hook
    if lead.website_kind == "none":
        hook = hooks_dict.get("no_website")
        if hook:
            results.append(hook)

    # 2. Social-only hook
    elif lead.website_kind in ("facebook", "instagram"):
        hook_tpl = hooks_dict.get("social_only", "")
        platform = extract_platform_name(lead.website)
        if hook_tpl:
            results.append(hook_tpl.format(platform=platform))

    # 3. Directory hook
    elif lead.website_kind == "directory":
        hook_tpl = hooks_dict.get("directory_only", "")
        platform = extract_platform_name(lead.website)
        if hook_tpl:
            results.append(hook_tpl.format(platform=platform))

    # 4. Audit-derived hooks
    if lead.audit and lead.audit.reachable:
        if not lead.audit.is_https:
            hook = hooks_dict.get("http_only")
            if hook:
                results.append(hook)
        if not lead.audit.has_viewport:
            hook = hooks_dict.get("no_viewport")
            if hook:
                results.append(hook)
        if lead.audit.generator:
            hook_tpl = hooks_dict.get("outdated_tech")
            if hook_tpl:
                results.append(hook_tpl.format(generator=lead.audit.generator))

    # 5. Hot prospect summary hook
    if lead.score >= 70 and lead.phone:
        hook = hooks_dict.get("hot_prospect")
        if hook and hook not in results:
            results.append(hook)

    return results
