"""Wikipedia & Wikidata OSINT Knowledge Resolver.

Provides 100% free, unauthenticated, rate-limit-free verification of
commercial entities across Polish (pl.wikipedia.org) and German (de.wikipedia.org)
markets. Detects corporate status, rebrandings, M&A (fuzje/przejęcia),
name changes, and extracts official replacement websites.
"""

from __future__ import annotations

import logging
import re
from typing import Any
import httpx
from pydantic import BaseModel, Field

from wulf_web_leader.models import CanonicalLead

logger = logging.getLogger(__name__)

USER_AGENT = "WulfWebLeader/1.0 (+https://lead.social-wulf.eu; contact@social-wulf.eu)"

CORPORATE_SUFFIX_STRIP = re.compile(
    r"(?:[\s,.\-(]|^)(s\.a\.|spółka\s*akcyjna|\bsa\b|sp\.\s*z\s*o\.\s*o\.|spółka\s*z\s*o\.\s*o\.|sp\.\s*j\.|sp\.\s*k\.|"
    r"\bag\b|aktiengesellschaft|\bse\b|kgaa|gmbh\s*&\s*co\.?\s*kg|gmbh|ug|holding|gruppe|grupa)(?:[\s,.\-)]|$)",
    re.IGNORECASE,
)

# Patterns signaling rebrandings, mergers, acquisitions, or entity changes
REBRANDING_PATTERNS_PL = [
    re.compile(r"zmieni[łl]a\s+nazw[ęe]\s+na\s+([A-Z0-9a-zżźćńółęąśŻŹĆŃÓŁĘĄŚ\s\.\-]+)", re.IGNORECASE),
    re.compile(r"funkcjonuje\s+pod\s+nazw[ąa]\s+([A-Z0-9a-zżźćńółęąśŻŹĆŃÓŁĘĄŚ\s\.\-]+)", re.IGNORECASE),
    re.compile(r"sta[łl]a\s+si[ęe]\s+cz[ęe][śs]ci[ąa]\s+(?:firmy|grupy)?\s+([A-Z0-9a-zżźćńółęąśŻŹĆŃÓŁĘĄŚ\s\.\-]+)", re.IGNORECASE),
    re.compile(r"przej[ęe]ta\s+przez\s+([A-Z0-9a-zżźćńółęąśŻŹĆŃÓŁĘĄŚ\s\.\-]+)", re.IGNORECASE),
    re.compile(r"fuzj[ia]\s+z\s+([A-Z0-9a-zżźćńółęąśŻŹĆŃÓŁĘĄŚ\s\.\-]+)", re.IGNORECASE),
]

REBRANDING_PATTERNS_DE = [
    re.compile(r"(?:wurde\s+)?umbenannt\s+in\s+([A-Z0-9a-zäöüÄÖÜß\s\.\-]+)", re.IGNORECASE),
    re.compile(r"hei[ßs]t\s+heute\s+([A-Z0-9a-zäöüÄÖÜß\s\.\-]+)", re.IGNORECASE),
    re.compile(r"firmiert\s+unter\s+([A-Z0-9a-zäöüÄÖÜß\s\.\-]+)", re.IGNORECASE),
    re.compile(r"(?:wurde\s+)?übernommen\s+(?:von\s+)?([A-Z0-9a-zäöüÄÖÜß\s\.\-]+)", re.IGNORECASE),
    re.compile(r"fusionierte\s+mit\s+([A-Z0-9a-zäöüÄÖÜß\s\.\-]+)", re.IGNORECASE),
    re.compile(r"tochtergesellschaft\s+(?:der|von)\s+([A-Z0-9a-zäöüÄÖÜß\s\.\-]+)", re.IGNORECASE),
]

# Patterns signaling large enterprise scale (revenue, enterprise scope)
ENTERPRISE_SIGNALS_PL = re.compile(
    r"(dystrybutor|operator|koncern|holding|grupa\s+kapitałowa|przychody.*(?:milion|miliard)|"
    r"obrot.*(?:milion|miliard)|spółka\s+akcyjna|giełdowa|przedsiębiorstwo\s+państwowe)",
    re.IGNORECASE,
)

ENTERPRISE_SIGNALS_DE = re.compile(
    r"(konzern|holding|aktiengesellschaft|großunternehmen|milliarden|millionen|umsatz|"
    r"tochterunternehmen|börsennotiert|industrieunternehmen)",
    re.IGNORECASE,
)


class WikipediaCompanyIntel(BaseModel):
    """Structured knowledge about a company retrieved from Wikipedia / Wikidata."""

    found: bool = False
    title: str | None = None
    language: str = "pl"
    wiki_url: str | None = None
    summary: str | None = None
    is_enterprise: bool = False
    is_rebranded: bool = False
    new_brand_name: str | None = None
    replacement_website: str | None = None
    wikidata_id: str | None = None
    notes: str | None = None



def clean_company_name_for_wiki(raw_name: str) -> str:
    """Normalize and strip corporate suffixes to maximize Wikipedia entity match rate."""
    if not raw_name:
        return ""
    cur = raw_name
    prev = None
    while prev != cur:
        prev = cur
        cur = CORPORATE_SUFFIX_STRIP.sub(" ", cur)
    # Remove special characters, excessive spaces
    cleaned = re.sub(r"[\"\'\(\)\[\]\.\,\-]", " ", cur)
    cleaned = " ".join(cleaned.split()).strip()
    return cleaned



def is_plausible_entity_match(wiki_title: str, clean_name: str, full_name: str) -> bool:
    """Ensure the Wikipedia page actually matches the company, avoiding false positive athletes or cities."""
    w_lower = wiki_title.lower().strip()
    c_lower = clean_name.lower().strip()
    f_lower = full_name.lower().strip()

    # Exact or starts with
    if w_lower == c_lower or w_lower == f_lower:
        return True
    if w_lower.startswith(c_lower) or c_lower.startswith(w_lower):
        return True
    
    # Check token overlap
    w_tokens = set(re.findall(r"\w+", w_lower))
    c_tokens = set(re.findall(r"\w+", c_lower))
    if c_tokens and c_tokens.issubset(w_tokens):
        return True

    return False


async def lookup_company_wikipedia(
    lead: CanonicalLead,
    timeout: float = 6.0,
) -> WikipediaCompanyIntel | None:
    """Lookup lead in Polish or German Wikipedia to identify large corporate status or rebrandings."""
    if not lead.name:
        return None

    lang = "de" if lead.country == "DE" else "pl"
    clean_name = clean_company_name_for_wiki(lead.name)
    if not clean_name or len(clean_name) < 3:
        return None

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    opensearch_url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "opensearch",
        "search": clean_name,
        "limit": 3,
        "namespace": 0,
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(opensearch_url, params=params, headers=headers)
            if resp.status_code != 200:
                return None

            data = resp.json()
            titles = data[1] if len(data) > 1 else []
            urls = data[3] if len(data) > 3 else []

            if not titles or not urls:
                return None

            # Find matching title
            matched_title = None
            matched_url = None
            for t, u in zip(titles, urls):
                if is_plausible_entity_match(t, clean_name, lead.name):
                    matched_title = t
                    matched_url = u
                    break

            if not matched_title:
                return None

            # Fetch REST summary
            summary_url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{matched_title}"
            s_resp = await client.get(summary_url, headers=headers)
            s_data = s_resp.json() if s_resp.status_code == 200 else {}
            extract = s_data.get("extract", "")
            wikibase_item = s_data.get("wikibase_item")

            # Fetch extended intro extract via Action API to capture second-paragraph rebrandings
            try:
                ext_url = f"https://{lang}.wikipedia.org/w/api.php"
                ext_params = {
                    "action": "query",
                    "prop": "extracts",
                    "explaintext": 1,
                    "exchars": 1500,
                    "titles": matched_title,
                    "format": "json",
                }
                ext_resp = await client.get(ext_url, params=ext_params, headers=headers)
                if ext_resp.status_code == 200:
                    pages = ext_resp.json().get("query", {}).get("pages", {})
                    for _, page in pages.items():
                        full_ext = page.get("extract", "")
                        if len(full_ext) > len(extract):
                            extract = full_ext
            except Exception as e:
                logger.debug("Extended extract fetch failed: %s", e)

            if not extract:
                return None

            # Analyze extract for enterprise signals & rebranding
            is_enterprise = False
            is_rebranded = False
            new_brand = None
            replacement_site = None


            if lang == "pl":
                if ENTERPRISE_SIGNALS_PL.search(extract):
                    is_enterprise = True
                for pat in REBRANDING_PATTERNS_PL:
                    m = pat.search(extract)
                    if m:
                        is_rebranded = True
                        candidate_brand = m.group(1).split(",")[0].strip()
                        if candidate_brand.endswith(".") and not candidate_brand.endswith("S.A."):
                            candidate_brand = candidate_brand[:-1].strip()
                        if len(candidate_brand) > 2 and candidate_brand.lower() != clean_name.lower():
                            new_brand = candidate_brand
                            break
            else:
                if ENTERPRISE_SIGNALS_DE.search(extract):
                    is_enterprise = True
                for pat in REBRANDING_PATTERNS_DE:
                    m = pat.search(extract)
                    if m:
                        is_rebranded = True
                        candidate_brand = m.group(1).split(",")[0].strip()
                        if candidate_brand.endswith(".") and not candidate_brand.endswith("AG"):
                            candidate_brand = candidate_brand[:-1].strip()
                        if len(candidate_brand) > 2 and candidate_brand.lower() != clean_name.lower():
                            new_brand = candidate_brand
                            break


            # If page exists for an S.A. / AG company, it is inherently an enterprise entity
            from wulf_web_leader.adapters.osm import is_joint_stock_or_enterprise
            if is_joint_stock_or_enterprise(lead.name):
                is_enterprise = True

            # If rebranded, try to discover modern replacement website via Wikidata or links
            if wikibase_item:
                try:
                    wd_url = f"https://www.wikidata.org/wiki/Special:EntityData/{wikibase_item}.json"
                    wd_resp = await client.get(wd_url, headers=headers)
                    if wd_resp.status_code == 200:
                        claims = wd_resp.json().get("entities", {}).get(wikibase_item, {}).get("claims", {})
                        # P856 = official website
                        p856 = claims.get("P856", [])
                        for p in p856:
                            val = p.get("mainsnak", {}).get("datavalue", {}).get("value")
                            if val and isinstance(val, str) and val.startswith("http"):
                                replacement_site = val
                                break
                except Exception as e:
                    logger.debug("Wikidata lookup error for %s: %s", wikibase_item, e)

            # Construct human-readable intelligence notes
            notes_parts = []
            if is_rebranded and new_brand:
                notes_parts.append(
                    f"Firma przeszła rebranding / fuzję (obecnie: {new_brand})."
                    if lang == "pl"
                    else f"Das Unternehmen wurde umbenannt / fusioniert (heute: {new_brand})."
                )
            elif is_enterprise:
                notes_parts.append(
                    "Znany podmiot korporacyjny o dużej skali działalności (obecny w Wikipedii)."
                    if lang == "pl"
                    else "Großunternehmen / Konzern mit Eintrag in Wikipedia."
                )

            if replacement_site and replacement_site != lead.website:
                notes_parts.append(
                    f"Wykryto oficjalną domenę w rejestrach Wikimedia: {replacement_site}"
                    if lang == "pl"
                    else f"Offizielle Domain in Wikimedia-Registern: {replacement_site}"
                )

            notes = " ".join(notes_parts) if notes_parts else extract[:250]

            return WikipediaCompanyIntel(
                found=True,
                title=matched_title,
                language=lang,
                wiki_url=matched_url,
                summary=extract[:400],
                is_enterprise=is_enterprise,
                is_rebranded=is_rebranded,
                new_brand_name=new_brand,
                replacement_website=replacement_site,
                wikidata_id=wikibase_item,
                notes=notes,
            )

    except Exception as e:
        logger.debug("Wikipedia resolver exception for %s: %s", lead.name, e)
        return None
