import asyncio
import logging
import random
import re
from typing import Any
import httpx

from wulf_web_leader.models import CanonicalLead, CountryCode
from wulf_web_leader.audit.classifier import classify_website_kind

logger = logging.getLogger(__name__)

DEFAULT_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def build_overpass_query(osm_tags: list[str], lat: float, lon: float, radius_km: float) -> str:
    """Build Overpass QL query strictly bounded in timeout, size, and geometry output."""
    radius_meters = int(radius_km * 1000)
    lines = ["[out:json][timeout:30][maxsize:67108864];", "("]

    for tag_spec in osm_tags:
        # tag_spec is e.g. "craft=plumber" or "amenity=restaurant"
        if "=" in tag_spec:
            key, val = tag_spec.split("=", 1)
            filter_str = f'["{key.strip()}"="{val.strip()}"]'
        else:
            filter_str = f'["{tag_spec.strip()}"]'

        lines.append(f"  node{filter_str}(around:{radius_meters},{lat},{lon});")
        lines.append(f"  way{filter_str}(around:{radius_meters},{lat},{lon});")
        lines.append(f"  relation{filter_str}(around:{radius_meters},{lat},{lon});")

    lines.append(");")
    lines.append("out center tags qt;")
    return "\n".join(lines)


def normalize_business_name(name: str) -> str:
    """Normalize company name for deduplication."""
    # Lowercase, strip punctuation and extra spaces
    cleaned = re.sub(r"[^\w\s]", "", name.lower())
    return " ".join(cleaned.split())


def normalize_phone_number(raw_phone: str | None, country: CountryCode) -> str | None:
    """Normalize phone numbers into standard callable representation."""
    if not raw_phone:
        return None
    
    # Strip spaces, dashes, slashes, parens
    cleaned = re.sub(r"[\s\-\(\)\/\.]", "", raw_phone.strip())
    
    # Replace leading 00 with +
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
        
    # Add country code if local
    if country == "PL":
        if not cleaned.startswith("+"):
            if len(cleaned) == 9:
                cleaned = "+48" + cleaned
            elif cleaned.startswith("48") and len(cleaned) == 11:
                cleaned = "+" + cleaned
    elif country == "DE":
        if not cleaned.startswith("+"):
            if cleaned.startswith("0"):
                cleaned = "+49" + cleaned[1:]
            elif cleaned.startswith("49") and len(cleaned) >= 10:
                cleaned = "+" + cleaned

    return cleaned


def is_dead_or_disused_poi(tags: dict[str, str]) -> bool:
    """Check if OSM tags indicate a closed, disused, or abandoned business."""
    if not tags:
        return False
    if tags.get("disused") in ("yes", "true", "1") or tags.get("abandoned") in ("yes", "true", "1"):
        return True
    if tags.get("closed") in ("yes", "true", "1"):
        return True
    if tags.get("opening_hours") == "closed" or tags.get("operational_status") in ("closed", "out_of_service", "demolished"):
        return True
    for k in tags.keys():
        lower_k = k.lower()
        if lower_k.startswith(("disused:", "abandoned:", "demolished:")):
            return True
    return False


FREEMAIL_DOMAINS = {
    # Global
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.de", "yahoo.pl",
    "hotmail.com", "hotmail.de", "hotmail.pl", "outlook.com", "live.com",
    "icloud.com", "aol.com", "mail.com", "zoho.com", "proton.me", "protonmail.com",
    # DACH
    "gmx.de", "gmx.net", "gmx.at", "gmx.ch", "web.de", "t-online.de",
    "freenet.de", "arcor.de", "posteo.de", "mailbox.org", "1und1.de", "online.de",
    # Poland
    "wp.pl", "onet.pl", "onet.eu", "interia.pl", "interia.eu", "o2.pl",
    "tlen.pl", "gazeta.pl", "poczta.fm", "autograf.pl", "vp.pl", "buziaczek.pl",
}

CORPORATE_ENTITY_REGEX = re.compile(
    r"(?:^|[\s,.\-(])(gmbh|ag|kg|gbr|ohg|ug|gmbh\s*&\s*co|sp\.\s*z\s*o\.\s*o\.|spółka\s*z\s*o\.\s*o\.|sp\.\s*j\.|sp\.\s*k\.|s\.a\.|spółka\s*akcyjna)(?:$|[\s,.\-)])",
    re.IGNORECASE,
)

ENTERPRISE_ENTITY_REGEX = re.compile(
    r"(?:^|[\s,.\-(])(s\.a\.|spółka\s*akcyjna|\bsa\b|ag|aktiengesellschaft|\bse\b|kgaa|holding|konzern|grupa\s*kapitałowa)(?:$|[\s,.\-)])",
    re.IGNORECASE,
)


def extract_domain_from_email(raw_email: str | None) -> str | None:
    """Extract custom business domain from email, ignoring freemail providers."""
    if not raw_email or "@" not in raw_email:
        return None
    cleaned = raw_email.strip().lower()
    if cleaned.startswith("mailto:"):
        cleaned = cleaned[7:]
    parts = cleaned.split("@")
    if len(parts) != 2:
        return None
    domain = parts[1].strip()
    if not domain or domain in FREEMAIL_DOMAINS:
        return None
    # Basic domain sanity check
    if "." in domain and not domain.startswith(".") and not domain.endswith("."):
        return domain
    return None


def is_corporate_entity(name: str | None) -> bool:
    """Determine if company name indicates a commercial corporation (GmbH, Sp. z o.o., etc.)."""
    if not name:
        return False
    return bool(CORPORATE_ENTITY_REGEX.search(name))


def is_joint_stock_or_enterprise(name: str | None) -> bool:
    """Determine if company is a joint-stock corporation (S.A., AG, SE), holding, or enterprise."""
    if not name:
        return False
    return bool(ENTERPRISE_ENTITY_REGEX.search(name))


class OverpassClient:
    """Resilient client for querying OpenStreetMap entities via Overpass API."""

    def __init__(
        self,
        endpoints: list[str] | None = None,
        timeout: float = 35.0,
        user_agent: str = "wulf-web-leader/0.3.0 (+https://github.com/wulf-org/wulf-web-leader)",
    ):
        self.endpoints = endpoints or list(DEFAULT_OVERPASS_ENDPOINTS)
        self.timeout = timeout
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }

    async def execute_query(self, query: str) -> list[dict[str, Any]]:
        """Execute query across available endpoints with retry and failover."""
        last_exception = None

        for endpoint in self.endpoints:
            for attempt in range(2):  # up to 2 attempts per endpoint
                try:
                    async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                        response = await client.post(endpoint, data={"data": query})
                        
                        if response.status_code == 200:
                            data = response.json()
                            return data.get("elements", [])
                        
                        if response.status_code in (429, 504, 502, 503):
                            # Server busy / rate limited, wait with jitter and retry next mirror
                            delay = 1.0 + random.uniform(0.5, 2.0) * (attempt + 1)
                            await asyncio.sleep(delay)
                            continue
                        
                        # Other non-retryable status
                        response.raise_for_status()

                except Exception as e:
                    last_exception = e
                    await asyncio.sleep(0.5)

        if last_exception:
            raise RuntimeError(f"Wszystkie serwery Overpass API nie odpowiedziały. Ostatni błąd: {last_exception}")
        return []

    def parse_elements_to_leads(
        self,
        elements: list[dict[str, Any]],
        country: CountryCode,
        default_city: str,
        industry_label: str,
        industry_code: str | None = None,
    ) -> list[CanonicalLead]:
        """Convert raw OSM elements into CanonicalLead objects with deduplication."""
        leads: list[CanonicalLead] = []
        seen_osm_ids: set[str] = set()
        seen_geo_names: set[tuple[str, float, float]] = set()
        seen_phone_locations: dict[tuple[str, float, float], int] = {}

        for el in elements:
            el_type = el.get("type", "node")
            el_id = el.get("id")
            source_id = f"{el_type}/{el_id}"

            if source_id in seen_osm_ids:
                continue
            seen_osm_ids.add(source_id)

            tags: dict[str, str] = el.get("tags", {})
            if is_dead_or_disused_poi(tags):
                # Odrzucenie zamkniętych / wygasłych punktów
                continue

            name = tags.get("name") or tags.get("brand") or tags.get("operator")
            if not name:
                # POI without name is not actionable for lead outreach
                continue
            name = name.strip()

            # Coordinates
            if el_type == "node":
                lat = el.get("lat")
                lon = el.get("lon")
            else:
                center = el.get("center", {})
                lat = center.get("lat")
                lon = center.get("lon")

            if lat is None or lon is None:
                continue

            # Phone extraction
            raw_phone = (
                tags.get("contact:phone")
                or tags.get("phone")
                or tags.get("contact:mobile")
                or tags.get("mobile")
            )
            phone = normalize_phone_number(raw_phone, country)

            # Address extraction
            street = tags.get("addr:street")
            housenumber = tags.get("addr:housenumber")
            address_parts = [p for p in [street, housenumber] if p]
            address = " ".join(address_parts) if address_parts else None

            city = tags.get("addr:city") or default_city
            postcode = tags.get("addr:postcode")

            # Website and social media extraction
            raw_website = tags.get("website") or tags.get("contact:website")
            raw_facebook = tags.get("contact:facebook") or tags.get("facebook")
            raw_instagram = tags.get("contact:instagram") or tags.get("instagram")
            raw_email = tags.get("contact:email") or tags.get("email")

            website = None
            website_kind = "none"
            website_source = "none"

            if raw_website and raw_website.strip():
                url = raw_website.strip()
                if not (url.startswith("http://") or url.startswith("https://")):
                    url = f"https://{url}"
                website = url
                website_kind = classify_website_kind(website)
                website_source = "osm_website"

            # If dedicated facebook tag exists
            if raw_facebook and raw_facebook.strip():
                fb = raw_facebook.strip()
                if not (fb.startswith("http://") or fb.startswith("https://")):
                    if "facebook.com" in fb:
                        fb = f"https://{fb}"
                    else:
                        fb = f"https://www.facebook.com/{fb.lstrip('@')}"
                if not website or website_kind in ("none", "other"):
                    website = fb
                    website_kind = "facebook"
                    website_source = "osm_website"

            # If dedicated instagram tag exists
            elif raw_instagram and raw_instagram.strip():
                ig = raw_instagram.strip()
                if not (ig.startswith("http://") or ig.startswith("https://")):
                    if "instagram.com" in ig:
                        ig = f"https://{ig}"
                    else:
                        ig = f"https://www.instagram.com/{ig.lstrip('@')}"
                if not website or website_kind in ("none", "other"):
                    website = ig
                    website_kind = "instagram"
                    website_source = "osm_website"

            email = None
            if raw_email and "@" in raw_email:
                em = raw_email.strip().lower()
                if em.startswith("mailto:"):
                    em = em[7:]
                email = em.split("?")[0].strip()

            # Passive discovery: if no website was found yet, check email for custom company domain
            if (not website or website_kind in ("none", "other")) and raw_email:
                custom_domain = extract_domain_from_email(raw_email)
                if custom_domain:
                    website = f"https://{custom_domain}"
                    website_kind = "own"
                    website_source = "email_domain"

            # Phone + ~100m grid deduplication and merging
            if phone:
                phone_key = (phone, round(lat, 3), round(lon, 3))
                if phone_key in seen_phone_locations:
                    existing_lead = leads[seen_phone_locations[phone_key]]
                    if not existing_lead.address and address:
                        existing_lead.address = address
                    if not existing_lead.postcode and postcode:
                        existing_lead.postcode = postcode
                    if not existing_lead.phone and phone:
                        existing_lead.phone = phone
                    if not existing_lead.email and email:
                        existing_lead.email = email
                    if not existing_lead.website and website:
                        existing_lead.website = website
                        existing_lead.website_kind = website_kind
                    continue

            # Geo-name deduplication (100m grid)
            norm_name = normalize_business_name(name)
            geo_key = (norm_name, round(lat, 3), round(lon, 3))
            if geo_key in seen_geo_names:
                continue
            seen_geo_names.add(geo_key)

            lead = CanonicalLead(
                country=country,
                name=name,
                lat=lat,
                lon=lon,
                address=address,
                city=city,
                postcode=postcode,
                phone=phone,
                email=email,
                website=website,
                website_kind=website_kind,
                website_source=website_source,
                source="osm",
                source_id=source_id,
                industry_code=industry_code,
                industry_label=industry_label,
                registry_status="unknown",
            )
            leads.append(lead)
            if phone:
                seen_phone_locations[phone_key] = len(leads) - 1

        return leads
