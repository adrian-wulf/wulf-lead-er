import asyncio
import logging
import random
import re
from typing import Any
import httpx

from wulf_web_leader.models import CanonicalLead, CountryCode

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


class OverpassClient:
    """Resilient client for querying OpenStreetMap entities via Overpass API."""

    def __init__(
        self,
        endpoints: list[str] | None = None,
        timeout: float = 35.0,
        user_agent: str = "wulf-web-leader/0.1.0 (+https://github.com/wulf-org/wulf-web-leader)",
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
            raise RuntimeError(f"All Overpass API endpoints failed. Last error: {last_exception}")
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

        for el in elements:
            el_type = el.get("type", "node")
            el_id = el.get("id")
            source_id = f"{el_type}/{el_id}"

            if source_id in seen_osm_ids:
                continue
            seen_osm_ids.add(source_id)

            tags: dict[str, str] = el.get("tags", {})
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

            # Geo-name deduplication (100m grid)
            norm_name = normalize_business_name(name)
            geo_key = (norm_name, round(lat, 3), round(lon, 3))
            if geo_key in seen_geo_names:
                continue
            seen_geo_names.add(geo_key)

            # Phone extraction
            raw_phone = (
                tags.get("contact:phone")
                or tags.get("phone")
                or tags.get("contact:mobile")
                or tags.get("mobile")
            )
            phone = normalize_phone_number(raw_phone, country)

            # Website extraction
            website = (
                tags.get("contact:website")
                or tags.get("website")
                or tags.get("contact:facebook")
                or tags.get("contact:instagram")
            )
            if website:
                website = website.strip()
                if not (website.startswith("http://") or website.startswith("https://")):
                    website = f"https://{website}"

            # Address extraction
            street = tags.get("addr:street")
            housenumber = tags.get("addr:housenumber")
            address_parts = [p for p in [street, housenumber] if p]
            address = " ".join(address_parts) if address_parts else None

            city = tags.get("addr:city") or default_city
            postcode = tags.get("addr:postcode")

            lead = CanonicalLead(
                country=country,
                name=name,
                lat=lat,
                lon=lon,
                address=address,
                city=city,
                postcode=postcode,
                phone=phone,
                website=website,
                website_kind="none" if not website else "other",
                source="osm",
                source_id=source_id,
                industry_code=industry_code,
                industry_label=industry_label,
                registry_status="unknown",
            )
            leads.append(lead)

        return leads
