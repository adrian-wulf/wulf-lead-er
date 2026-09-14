"""
Google Maps Scraper Adapter for WULF LEAD.ER.
Wraps the high-performance gosom/google-maps-scraper Go binary (in fast-mode
with rotating Webshare proxies) to fetch ground-truth business listings,
official websites, phone numbers, ratings, and review counts.
"""

import asyncio
import json
import logging
import math
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from wulf_web_leader.audit.classifier import classify_website_kind
from wulf_web_leader.audit.lead_filter import is_lead_relevant
from wulf_web_leader.audit.proxy_pool import get_proxies_file_path
from wulf_web_leader.models import CanonicalLead, CountryCode

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in kilometers."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def _find_project_root() -> Path:
    curr = Path(__file__).resolve()
    for parent in curr.parents:
        if (parent / "pyproject.toml").is_file() or (parent / "src").is_dir():
            return parent
    return curr.parent.parent.parent


def get_gmaps_scraper_bin() -> Path | None:
    """Locate the google_maps_scraper binary executable."""
    env_bin = os.getenv("GMAPS_SCRAPER_BIN")
    if env_bin:
        p = Path(env_bin).expanduser().resolve()
        if p.is_file() and os.access(p, os.X_OK):
            return p

    root = _find_project_root()
    candidate = root / "bin" / "google_maps_scraper"
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate

    home_bin = Path.home() / "bin" / "google_maps_scraper"
    if home_bin.is_file() and os.access(home_bin, os.X_OK):
        return home_bin

    which_bin = shutil.which("google_maps_scraper")
    if which_bin:
        p = Path(which_bin).resolve()
        if p.is_file() and os.access(p, os.X_OK):
            return p

    return None


def is_gmaps_scraper_available() -> bool:
    """Return True if the scraper binary is installed and executable."""
    return get_gmaps_scraper_bin() is not None


def _clean_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if not url or url.lower() in ("null", "none", "-", "n/a"):
        return None
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def parse_ndjson_line(
    data: dict[str, Any],
    country: CountryCode,
    default_city: str,
    vertical_id: str | None = None,
    center_lat: float | None = None,
    center_lon: float | None = None,
    radius_km: float | None = None,
) -> CanonicalLead | None:
    """Parse a single JSON record from google-maps-scraper output into CanonicalLead."""
    title = (data.get("title") or "").strip()
    if not title:
        return None

    category = (data.get("category") or "").strip()
    if not category:
        categories = data.get("categories") or []
        if categories and isinstance(categories, list):
            category = str(categories[0]).strip()

    # Relevance & Anti-junk filter (chains, public institutions, negative keywords)
    if vertical_id:
        relevant, reason = is_lead_relevant(title, vertical_id=vertical_id, category=category)
        if not relevant:
            logger.debug("Filtered out non-relevant Google Maps lead '%s' (%s): %s", title, category, reason)
            return None

    website = _clean_url(data.get("web_site"))
    phone = (data.get("phone") or "").strip() or None
    address = (data.get("address") or "").strip() or None

    rating_raw = data.get("review_rating")
    rating: float | None = None
    if rating_raw is not None:
        try:
            rating = float(rating_raw)
        except (ValueError, TypeError):
            pass

    reviews_raw = data.get("review_count")
    reviews_count: int | None = None
    if reviews_raw is not None:
        try:
            reviews_count = int(reviews_raw)
        except (ValueError, TypeError):
            pass

    lat_raw = data.get("latitude")
    lon_raw = data.get("longtitude") or data.get("longitude")
    lat: float | None = None
    lon: float | None = None
    if lat_raw is not None:
        try:
            lat = float(lat_raw)
        except (ValueError, TypeError):
            pass
    if lon_raw is not None:
        try:
            lon = float(lon_raw)
        except (ValueError, TypeError):
            pass

    # Geofence distance check (reject leads far outside search radius)
    if lat is not None and lon is not None and center_lat is not None and center_lon is not None and radius_km is not None:
        dist = haversine_km(center_lat, center_lon, lat, lon)
        if dist > radius_km * 1.3:
            logger.debug("Filtered out Google Maps lead '%s' outside radius (%.1f km > %.1f km)", title, dist, radius_km)
            return None

    # Extract street and city from address or complete_address
    comp_addr = data.get("complete_address") or {}
    city = comp_addr.get("city") or default_city
    street = comp_addr.get("street") or None

    website_kind = classify_website_kind(website) if website else "none"

    return CanonicalLead(
        source="google_maps",
        external_id=str(data.get("data_id") or data.get("cid") or title),
        name=title,
        city=city,
        street=street,
        address=address,
        country=country,
        lat=lat,
        lon=lon,
        phone=phone,
        website=website,
        website_kind=website_kind,
        website_source="google_maps" if website else "none",
        industry_label=category or "Usługi",
        rating=rating,
        reviews_count=reviews_count,
        raw_tags={
            "gmaps_data_id": data.get("data_id"),
            "gmaps_cid": data.get("cid"),
            "gmaps_categories": data.get("categories"),
            "gmaps_timezone": data.get("timezone"),
        },
    )


async def scrape_google_maps(
    query: str,
    lat: float,
    lon: float,
    country: CountryCode = "PL",
    city: str = "",
    radius_km: float = 15.0,
    lang: str = "pl",
    max_depth: int = 1,
    timeout_seconds: float = 45.0,
    vertical_id: str | None = None,
) -> list[CanonicalLead]:
    """
    Execute google-maps-scraper for the given query & coordinates.
    Uses fast-mode (TLS Firefox fingerprinting) with rotating Webshare proxies.
    """
    binary = get_gmaps_scraper_bin()
    if not binary:
        logger.warning("google_maps_scraper binary not found. Skipping Google Maps scrape.")
        return []

    proxies_file = get_proxies_file_path()

    tmp_dir = Path(tempfile.mkdtemp(prefix="wulf_gmaps_"))
    query_file = tmp_dir / "query.txt"
    results_file = tmp_dir / "results.json"

    try:
        with open(query_file, "w", encoding="utf-8") as f:
            f.write(f"{query}\n")

        cmd = [
            str(binary),
            "-input", str(query_file),
            "-results", str(results_file),
            "-json",
            "-depth", str(max_depth),
            "-geo", f"{lat:.6f},{lon:.6f}",
            "-fast-mode",
            "-exit-on-inactivity", "15s",
        ]
        if lang:
            cmd.extend(["-lang", lang])
        if proxies_file and proxies_file.is_file():
            cmd.extend(["-proxies-file", str(proxies_file)])

        logger.info("Starting google_maps_scraper: %s (geo=%s,%s, proxies=%s)", query, lat, lon, bool(proxies_file))

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            logger.warning("google_maps_scraper timed out after %s seconds", timeout_seconds)
            return []

        if proc.returncode != 0 and not results_file.is_file():
            err_msg = (stderr or b"").decode("utf-8", errors="replace")
            logger.warning("google_maps_scraper exited with code %s: %s", proc.returncode, err_msg[:300])
            return []

        leads: list[CanonicalLead] = []
        if results_file.is_file():
            with open(results_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return []

                # It could be NDJSON or a JSON array
                if content.startswith("[") and content.endswith("]"):
                    try:
                        items = json.loads(content)
                        for item in items:
                            lead = parse_ndjson_line(
                                item,
                                country=country,
                                default_city=city,
                                vertical_id=vertical_id,
                                center_lat=lat,
                                center_lon=lon,
                                radius_km=radius_km,
                            )
                            if lead:
                                leads.append(lead)
                    except Exception as e:
                        logger.warning("Failed parsing JSON array from scraper: %s", e)
                else:
                    for line in content.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            lead = parse_ndjson_line(
                                item,
                                country=country,
                                default_city=city,
                                vertical_id=vertical_id,
                                center_lat=lat,
                                center_lon=lon,
                                radius_km=radius_km,
                            )
                            if lead:
                                leads.append(lead)
                        except Exception as e:
                            logger.debug("Failed parsing NDJSON line: %s", e)

        # Deduplicate results by normalized title + address
        deduped: list[CanonicalLead] = []
        seen_keys: set[str] = set()
        for l in leads:
            key = f"{l.name.lower().strip()}|{(l.address or '').lower().strip()}"
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(l)

        logger.info("google_maps_scraper extracted %d verified businesses for '%s'", len(deduped), query)
        return deduped

    except Exception as e:
        logger.exception("Error executing google_maps_scraper: %s", e)
        return []
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
