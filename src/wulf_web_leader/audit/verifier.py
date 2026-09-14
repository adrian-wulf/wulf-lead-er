import asyncio
import logging
import os
import re
import socket
from urllib.parse import urlparse, unquote
from typing import Any
import httpx

from wulf_web_leader.models import CanonicalLead, AuditResult

logger = logging.getLogger(__name__)


# Patterns indicating hosting defaults, under-construction templates, or parked domains
PLACEHOLDER_REGEXES = [
    # German hosting & parking templates
    re.compile(r"soeben freigeschaltete homepage", re.IGNORECASE),
    re.compile(r"hier entsteht eine neue (?:internetpräsenz|website|webseite|homepage)", re.IGNORECASE),
    re.compile(r"hier entsteht in kürze", re.IGNORECASE),
    re.compile(r"diese domain (?:wurde|ist) (?:geparkt|registriert|reserviert|soeben freigeschaltet)", re.IGNORECASE),
    re.compile(r"diese (?:website|domain) kaufen", re.IGNORECASE),
    re.compile(r"domain ist zu verkaufen", re.IGNORECASE),
    # Polish hosting & parking templates
    re.compile(r"strona w budowie", re.IGNORECASE),
    re.compile(r"strona w przygotowaniu", re.IGNORECASE),
    re.compile(r"serwis w budowie", re.IGNORECASE),
    re.compile(r"domena zarejestrowana w", re.IGNORECASE),
    re.compile(r"domena zaparkowana", re.IGNORECASE),
    re.compile(r"ta domena jest na sprzedaż", re.IGNORECASE),
    re.compile(r"kup tę domenę", re.IGNORECASE),
    # English & standard server default pages
    re.compile(r"under construction", re.IGNORECASE),
    re.compile(r"coming soon", re.IGNORECASE),
    re.compile(r"default web site page", re.IGNORECASE),
    re.compile(r"welcome to nginx", re.IGNORECASE),
    re.compile(r"apache2 (?:ubuntu|debian) default page", re.IGNORECASE),
    re.compile(r"plesk default page", re.IGNORECASE),
    re.compile(r"buy this domain", re.IGNORECASE),
    re.compile(r"domain for sale", re.IGNORECASE),
    re.compile(r"parked domain", re.IGNORECASE),
    re.compile(r"sedo domain parking", re.IGNORECASE),
    re.compile(r"webmailer\.de/setup", re.IGNORECASE),
]

# Stop words to filter out when tokenizing business names
NAME_STOP_WORDS = {
    # German
    "gmbh", "ag", "kg", "gbr", "ohg", "ug", "haftungsbeschränkt", "und", "soehne", "söhne",
    "partner", "betrieb", "firma", "sanitär", "sanitaer", "heizung", "haustechnik", "installation",
    "klempner", "meisterbetrieb", "service", "technik", "bau", "servicebetrieb",
    # Polish
    "sp", "z", "o.o.", "zoo", "sa", "spółka", "cywilna", "jawna", "komandytowa", "akcyjna",
    "usługi", "uslugi", "handel", "produkcja", "hydraulik", "hydraulika", "instalacje",
    "naprawa", "serwis", "złota", "rączka", "firma", "przedsiębiorstwo",
    # English / general
    "ltd", "llc", "corp", "inc", "the", "and", "co", "company",
}

DIRECTORY_DOMAINS = [
    "facebook.com", "instagram.com", "cylex", "gelbeseiten.de", "dasoertliche.de",
    "dastelefonbuch.de", "panoramafirm.pl", "pkt.pl", "oferteo.pl", "znanylekarz.pl",
    "booksy.com", "google.com", "duckduckgo.com", "bing.com", "wikipedia.org",
    "kompass.com", "linkedin.com", "twitter.com", "x.com", "yellowpages",
    "northdata.de", "companyhouse.de", "branchen-info.net", "implisense.com",
    "regiohandwerker.de", "firmania.de", "firmenwissen.de", "online-handelsregister.de",
    "unternehmensregister.de", "creditreform.de", "krs-online.com.pl", "aleo.com",
    "bizraport.pl", "rejestr.io", "infoveriti.pl", "gowork.pl", "wasserwaermeluft.de",
]

# German area code (Vorwahl without leading 0 / country code) to (Kfz-Kennzeichen, City name)
GERMAN_VORWAHL_TO_INFO: dict[str, tuple[str, str]] = {
    "531": ("bs", "braunschweig"),
    "511": ("h", "hannover"),
    "5121": ("hi", "hildesheim"),
    "5341": ("sz", "salzgitter"),
    "5361": ("wob", "wolfsburg"),
    "5171": ("pe", "peine"),
    "5321": ("gs", "goslar"),
    "5331": ("wf", "wolfenbuettel"),
    "5141": ("ce", "celle"),
    "5151": ("hm", "hameln"),
    "30": ("b", "berlin"),
    "40": ("hh", "hamburg"),
    "89": ("m", "muenchen"),
    "221": ("k", "koeln"),
    "69": ("f", "frankfurt"),
    "711": ("s", "stuttgart"),
    "211": ("d", "duesseldorf"),
    "231": ("do", "dortmund"),
    "201": ("e", "essen"),
    "341": ("l", "leipzig"),
    "421": ("hb", "bremen"),
    "351": ("dd", "dresden"),
    "911": ("n", "nuernberg"),
    "202": ("w", "wuppertal"),
    "208": ("ob", "oberhausen"),
    "209": ("ge", "gelsenkirchen"),
    "228": ("bn", "bonn"),
    "251": ("ms", "muenster"),
    "621": ("ma", "mannheim"),
    "721": ("ka", "karlsruhe"),
    "821": ("a", "augsburg"),
    "611": ("wi", "wiesbaden"),
    "2161": ("mg", "moenchengladbach"),
    "203": ("du", "duisburg"),
    "234": ("bo", "bochum"),
    "431": ("ki", "kiel"),
    "241": ("ac", "aachen"),
    "381": ("hro", "rostock"),
    "541": ("os", "osnabrueck"),
    "441": ("ol", "oldenburg"),
    "521": ("bi", "bielefeld"),
    "561": ("ks", "kassel"),
    "681": ("sb", "saarbruecken"),
    "931": ("wue", "wuerzburg"),
    "941": ("r", "regensburg"),
    "841": ("in", "ingolstadt"),
    "731": ("ul", "ulm"),
    "761": ("fr", "freiburg"),
    "6221": ("hd", "heidelberg"),
    "6131": ("mz", "mainz"),
    "6151": ("da", "darmstadt"),
    "331": ("p", "potsdam"),
    "361": ("ef", "erfurt"),
    "371": ("c", "chemnitz"),
    "391": ("md", "magdeburg"),
    "345": ("hal", "halle"),
}

GERMAN_CITY_TO_KFZ: dict[str, str] = {
    "braunschweig": "bs",
    "hannover": "h",
    "hildesheim": "hi",
    "salzgitter": "sz",
    "wolfsburg": "wob",
    "peine": "pe",
    "goslar": "gs",
    "wolfenbüttel": "wf",
    "wolfenbuettel": "wf",
    "celle": "ce",
    "hameln": "hm",
    "berlin": "b",
    "hamburg": "hh",
    "münchen": "m",
    "muenchen": "m",
    "munich": "m",
    "köln": "k",
    "koeln": "k",
    "cologne": "k",
    "frankfurt": "f",
    "stuttgart": "s",
    "düsseldorf": "d",
    "duesseldorf": "d",
    "dortmund": "do",
    "essen": "e",
    "leipzig": "l",
    "bremen": "hb",
    "dresden": "dd",
    "nürnberg": "n",
    "nuernberg": "n",
    "wuppertal": "w",
    "oberhausen": "ob",
    "gelsenkirchen": "ge",
    "bonn": "bn",
    "münster": "ms",
    "muenster": "ms",
    "mannheim": "ma",
    "karlsruhe": "ka",
    "augsburg": "a",
    "wiesbaden": "wi",
    "mönchengladbach": "mg",
    "moenchengladbach": "mg",
    "duisburg": "du",
    "bochum": "bo",
    "kiel": "ki",
    "aachen": "ac",
    "rostock": "hro",
    "osnabrück": "os",
    "osnabrueck": "os",
    "oldenburg": "ol",
    "bielefeld": "bi",
    "kassel": "ks",
    "saarbrücken": "sb",
    "saarbruecken": "sb",
    "würzburg": "wue",
    "wuerzburg": "wue",
    "regensburg": "r",
    "ingolstadt": "in",
    "ulm": "ul",
    "freiburg": "fr",
    "heidelberg": "hd",
    "mainz": "mz",
    "darmstadt": "da",
    "potsdam": "p",
    "erfurt": "ef",
    "chemnitz": "c",
    "magdeburg": "md",
    "halle": "hal",
}


def check_is_placeholder(html_text: str, title: str | None = None) -> tuple[bool, str | None]:
    """Check if the given HTML or page title matches parking, construction, or default hosting patterns."""
    text_to_check = f"{title or ''}\n{html_text[:10000]}"
    
    for pattern in PLACEHOLDER_REGEXES:
        match = pattern.search(text_to_check)
        if match:
            return True, f"Wykryto wzorzec zaślepki/parkingu: '{match.group(0)}'"

    # Check for empty / microscopic stub
    clean_text = re.sub(r"<[^>]+>", " ", html_text).strip()
    if len(clean_text) < 120 and not any(kw in clean_text.lower() for kw in ["tel", "kontakt", "impressum", "o nas", "über uns"]):
        return True, "Zbyt krótka zawartość strony (pusta zaślepka serwera)"

    return False, None


def extract_key_name_tokens(name: str) -> list[str]:
    """Extract distinctive search/matching tokens from business name."""
    cleaned = re.sub(r"[^\w\s-]", " ", name.lower())
    tokens = [t.strip("-") for t in cleaned.split() if len(t) >= 3]
    return [t for t in tokens if t not in NAME_STOP_WORDS]


def verify_entity_match(
    lead_name: str,
    city: str | None,
    phone: str | None,
    address: str | None,
    html_text: str,
) -> tuple[int, list[str], str]:
    """Verify if the audited HTML matches the business identity.
    
    Returns:
        (match_score 0..100, matched_signals list, confidence "high" | "medium" | "low" | "mismatch")
    """
    html_lower = html_text.lower()
    matched_signals: list[str] = []
    score = 0

    # 1. Distinctive name tokens (weight: up to 45 pts)
    tokens = extract_key_name_tokens(lead_name)
    matched_tokens = [t for t in tokens if t in html_lower]
    if matched_tokens:
        token_ratio = len(matched_tokens) / len(tokens)
        token_pts = int(45 * token_ratio)
        score += token_pts
        matched_signals.append(f"name_tokens:{','.join(matched_tokens)}")

    # 2. Phone match (weight: 35 pts)
    if phone:
        digits_only = re.sub(r"\D", "", phone)
        # Check last 6-8 digits (local number part)
        if len(digits_only) >= 6:
            local_phone = digits_only[-6:]
            if local_phone in re.sub(r"\D", "", html_text):
                score += 35
                matched_signals.append(f"phone:{local_phone}")

    # 3. City / Postcode / Street match (weight: 20 pts)
    loc_signals = []
    if city and len(city) >= 3 and city.lower() in html_lower:
        loc_signals.append(f"city:{city}")
    if address:
        street_match = re.search(r"^[^\d,]+", address)
        if street_match:
            street_name = street_match.group(0).strip().lower()
            if len(street_name) >= 4 and street_name in html_lower:
                loc_signals.append(f"street:{street_name}")

    if loc_signals:
        score += 20
        matched_signals.extend(loc_signals)

    # Determine confidence level
    if score >= 55:
        confidence = "high"
    elif score >= 35:
        confidence = "medium"
    elif score > 0:
        confidence = "low"
    else:
        confidence = "mismatch"

    return min(100, score), matched_signals, confidence


def generate_domain_candidates(
    company_name: str,
    city: str | None = None,
    phone: str | None = None,
    country: str = "DE",
    vertical_keywords: list[str] | None = None,
) -> list[str]:
    """Generate deterministic domain candidates for a business based on name tokens, city, phone area code, and vertical keywords."""
    tokens = extract_key_name_tokens(company_name)
    if not tokens:
        return []

    tlds = [".de", ".com"] if country.upper() == "DE" else [".pl", ".com.pl", ".com"]
    candidates: list[str] = []
    seen: set[str] = set()

    def add_domain(domain_base: str):
        base = domain_base.lower().strip("-")
        base = (
            base.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
            .replace("ą", "a")
            .replace("ć", "c")
            .replace("ę", "e")
            .replace("ł", "l")
            .replace("ń", "n")
            .replace("ó", "o")
            .replace("ś", "s")
            .replace("ź", "z")
            .replace("ż", "z")
        )
        base = re.sub(r"[^a-z0-9-]", "", base)
        if len(base) < 3:
            return
        for tld in tlds:
            dom = f"{base}{tld}"
            if dom not in seen:
                seen.add(dom)
                candidates.append(dom)

    multi_token = "-".join(tokens[:2]) if len(tokens) >= 2 else None

    # 1. Base tokens
    for t in tokens[:2]:
        add_domain(t)
    if multi_token:
        add_domain(multi_token)

    # 2. City combinations
    if city:
        city_clean = city.lower().replace(" ", "-")
        if city_clean:
            for t in tokens[:2]:
                add_domain(f"{t}-{city_clean}")
            if multi_token:
                add_domain(f"{multi_token}-{city_clean}")

    # 3. German Vorwahl (phone area code) & Kfz-Kennzeichen regional heuristics (e.g. bonse-bs.de)
    kfz_codes: list[str] = []
    extra_cities: list[str] = []

    if country.upper() == "DE":
        if phone:
            digits = re.sub(r"\D", "", phone)
            if digits.startswith("49"):
                digits = digits[2:]
            elif digits.startswith("0"):
                digits = digits[1:]

            for prefix_len in (4, 3, 2):
                prefix = digits[:prefix_len]
                if prefix in GERMAN_VORWAHL_TO_INFO:
                    kfz, p_city = GERMAN_VORWAHL_TO_INFO[prefix]
                    kfz_codes.append(kfz)
                    extra_cities.append(p_city)
                    break

        if city:
            c_low = city.lower().strip()
            if c_low in GERMAN_CITY_TO_KFZ:
                kfz_codes.append(GERMAN_CITY_TO_KFZ[c_low])

    for kfz in set(kfz_codes):
        for t in tokens[:2]:
            add_domain(f"{t}-{kfz}")
        if multi_token:
            add_domain(f"{multi_token}-{kfz}")

    for p_city in set(extra_cities):
        if city and p_city == city.lower():
            continue
        p_city_clean = p_city.replace(" ", "-")
        for t in tokens[:2]:
            add_domain(f"{t}-{p_city_clean}")
        if multi_token:
            add_domain(f"{multi_token}-{p_city_clean}")

    # 4. Vertical keywords
    if vertical_keywords:
        for kw in vertical_keywords:
            kw_clean = re.sub(r"[^a-zA-Z0-9]", "", kw.lower())
            if kw_clean:
                for t in tokens[:2]:
                    add_domain(f"{t}-{kw_clean}")
        if len(vertical_keywords) >= 2:
            kw1 = re.sub(r"[^a-zA-Z0-9]", "", vertical_keywords[0].lower())
            kw2 = re.sub(r"[^a-zA-Z0-9]", "", vertical_keywords[1].lower())
            for t in tokens[:2]:
                add_domain(f"{t}-{kw1}-{kw2}")

    return candidates


def _sync_dns_check(domain: str) -> bool:
    try:
        socket.getaddrinfo(domain, 80)
        return True
    except (socket.gaierror, socket.herror, TimeoutError, OSError):
        return False


async def check_dns_resolves(domain: str) -> bool:
    """Non-blocking DNS check to see if a candidate domain resolves to an IP."""
    return await asyncio.to_thread(_sync_dns_check, domain)


async def query_google_custom_search(
    company_name: str,
    city: str | None = None,
    phone: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Query Google Custom Search JSON API if GOOGLE_API_KEY and GOOGLE_CSE_ID are set.
    
    Returns the first authentic non-directory URL found in Google results, or None.
    Official programmatic API (100 free queries/day).
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    if not api_key or not cse_id:
        return None

    query_parts = [f'"{company_name}"']
    if city:
        query_parts.append(city)
    if phone:
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 6:
            query_parts.append(digits[-6:])
    query = " ".join(query_parts)

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": 3,
    }

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=5.0)
        close_client = True

    try:
        resp = await client.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            for item in items:
                link = item.get("link", "")
                if not link.startswith(("http://", "https://")):
                    continue
                parsed = urlparse(link)
                netloc = (parsed.hostname or "").lower()
                if not netloc or "." not in netloc:
                    continue
                if any(ign in netloc for ign in DIRECTORY_DOMAINS):
                    continue
                return f"{parsed.scheme}://{parsed.netloc}/"
    except Exception as e:
        logger.debug("Google Custom Search API error: %s", e)
    finally:
        if close_client:
            await client.aclose()

    return None


async def discover_real_website_candidate(
    company_name: str,
    city: str | None,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Search for the official company website via DuckDuckGo Lite when OSM/email domain is invalid or a placeholder."""
    query = f"{company_name} {city or ''}".strip()
    url = f"https://html.duckduckgo.com/html/?q={httpx.URL('', params={'q': query}).params['q']}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de,pl,en;q=0.9",
    }

    try:
        close_client = False
        if client is None:
            from wulf_web_leader.audit.proxy_pool import get_random_proxy
            proxy = get_random_proxy()
            # verify=False is intentional: many SMB target sites have expired, self-signed, or
            # untrusted SSL certificates. The audit engine specifically evaluates SSL health as a
            # scoring criterion rather than aborting connection attempts.
            client = httpx.AsyncClient(timeout=6.0, headers=headers, verify=False, proxy=proxy)
            close_client = True

        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None

            # Extract result links from DuckDuckGo HTML results
            raw_links = re.findall(r"href=[\x27\x22]([^\x27\x22]+)[\x27\x22]", resp.text)
            for link in raw_links:
                candidate = link
                if "uddg=" in candidate:
                    candidate = unquote(candidate.split("uddg=")[1].split("&")[0])
                elif not candidate.startswith(("http://", "https://")):
                    continue

                parsed = urlparse(candidate)
                netloc = (parsed.hostname or "").lower()
                if not netloc or "." not in netloc:
                    continue

                # Filter out search engines and directories
                if any(ign in netloc for ign in DIRECTORY_DOMAINS):
                    continue

                # Return clean origin URL
                clean_url = f"{parsed.scheme}://{parsed.netloc}/"
                return clean_url

        finally:
            if close_client:
                await client.aclose()

    except Exception:
        return None

    return None


async def resolve_and_verify_candidate(
    lead: CanonicalLead,
    vertical_keywords: list[str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> tuple[str, AuditResult, str] | None:
    """Try to discover and verify the authentic website for a lead.
    
    Tries:
    1. Deterministic domain candidate generation (with German Vorwahl/Kfz heuristics) + parallel DNS resolution.
    2. Google Custom Search API (if GOOGLE_API_KEY and GOOGLE_CSE_ID configured).
    3. DuckDuckGo search fallback.
    
    Returns (verified_url, audit_result, method) if verified, or None.
    """
    import wulf_web_leader.audit.fetch as audit_fetch

    # 1. Deterministic candidates via DNS
    domain_candidates = generate_domain_candidates(
        company_name=lead.name,
        city=lead.city,
        phone=lead.phone,
        country=lead.country,
        vertical_keywords=vertical_keywords,
    )

    if domain_candidates:
        dns_tasks = [check_dns_resolves(d) for d in domain_candidates]
        dns_results = await asyncio.gather(*dns_tasks, return_exceptions=True)
        live_domains = [d for d, resolves in zip(domain_candidates, dns_results) if resolves is True]

        best_candidate = None
        highest_score = 0

        for domain in live_domains:
            cand_url = f"https://{domain}/"
            audit_res = await audit_fetch.audit_website(
                cand_url,
                lead_name=lead.name,
                city=lead.city,
                phone=lead.phone,
                address=lead.address or lead.street,
            )
            if audit_res.reachable and not audit_res.is_placeholder and audit_res.entity_match_score >= 35:
                if audit_res.entity_match_score > highest_score:
                    highest_score = audit_res.entity_match_score
                    best_candidate = (audit_res.final_url or cand_url, audit_res, "dns_candidate")
                    if highest_score >= 55:
                        return best_candidate

        if best_candidate:
            return best_candidate

    # 2. Google Custom Search API (if configured via GOOGLE_API_KEY & GOOGLE_CSE_ID)
    try:
        google_cand = await query_google_custom_search(
            company_name=lead.name,
            city=lead.city,
            phone=lead.phone,
            client=client,
        )
        if google_cand:
            audit_res = await audit_fetch.audit_website(
                google_cand,
                lead_name=lead.name,
                city=lead.city,
                phone=lead.phone,
                address=lead.address or lead.street,
            )
            if audit_res.reachable and not audit_res.is_placeholder and audit_res.entity_match_score >= 35:
                return (audit_res.final_url or google_cand, audit_res, "google_search_api")
    except Exception:
        pass

    # 3. Web search fallback (DuckDuckGo Lite)
    try:
        search_cand = await discover_real_website_candidate(lead.name, lead.city, client=client)
        if search_cand:
            audit_res = await audit_fetch.audit_website(
                search_cand,
                lead_name=lead.name,
                city=lead.city,
                phone=lead.phone,
                address=lead.address or lead.street,
            )
            if audit_res.reachable and not audit_res.is_placeholder and audit_res.entity_match_score >= 35:
                return (audit_res.final_url or search_cand, audit_res, "web_search")
    except Exception:
        pass

    return None
