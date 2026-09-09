import asyncio
import logging
from typing import Callable
from wulf_web_leader.models import CanonicalLead, CountryCode, VerticalDefinition
from wulf_web_leader.adapters.nominatim import NominatimClient, GeocodedLocation
from wulf_web_leader.adapters.osm import OverpassClient, build_overpass_query
from wulf_web_leader.audit.classifier import classify_website_kind
from wulf_web_leader.audit.fetch import audit_website
from wulf_web_leader.score.engine import calculate_lead_score
from wulf_web_leader.score.hooks import generate_pitch_hooks

logger = logging.getLogger(__name__)


async def run_scan_pipeline(
    country: CountryCode,
    city: str,
    vertical: VerticalDefinition,
    radius_km: float = 15.0,
    lang: str = "pl",
    do_audit: bool = True,
    min_score: int = 0,
    has_phone_only: bool = False,
    nominatim_client: NominatimClient | None = None,
    overpass_client: OverpassClient | None = None,
    progress_callback: Callable[[str, str], None] | None = None,
) -> tuple[list[CanonicalLead], GeocodedLocation]:
    """Execute end-to-end lead scanning, auditing, scoring, and hook generation pipeline."""

    def notify(stage: str, msg: str):
        if progress_callback:
            progress_callback(stage, msg)

    # 1. Geocode
    notify("geocode", f"Geocoding {city}, {country}...")
    nom = nominatim_client or NominatimClient()
    location = await nom.geocode(city, country)
    if not location:
        raise ValueError(f"Could not locate city '{city}' in {country}. Please verify spelling.")

    # 2. Prepare OSM tags for vertical & country
    country_key = country.lower()
    country_conf = getattr(vertical, country_key)
    osm_tags = country_conf.osm
    industry_label = country_conf.label
    industry_codes = country_conf.pkd if country == "PL" else country_conf.wz
    industry_code = industry_codes[0] if industry_codes else None

    # 3. Overpass query
    notify("overpass", f"Querying OpenStreetMap within {radius_km} km...")
    query = build_overpass_query(osm_tags, location.lat, location.lon, radius_km)
    op = overpass_client or OverpassClient()
    elements = await op.execute_query(query)

    # 4. Parse & deduplicate
    leads = op.parse_elements_to_leads(
        elements=elements,
        country=country,
        default_city=location.city or city,
        industry_label=industry_label,
        industry_code=industry_code,
    )
    notify("parse", f"Found {len(leads)} matching businesses in OpenStreetMap.")

    # 5. Classify website kinds
    for lead in leads:
        lead.website_kind = classify_website_kind(lead.website)

    # 6. Audit websites (if enabled)
    leads_to_audit = [lead for lead in leads if lead.website_kind == "own" and lead.website]
    if do_audit and leads_to_audit:
        notify("audit", f"Auditing {len(leads_to_audit)} business websites...")
        semaphore = asyncio.Semaphore(5)

        async def audit_single(lead: CanonicalLead):
            async with semaphore:
                try:
                    audit_res = await audit_website(lead.website)
                    lead.audit = audit_res
                    # If phone was missing from OSM, check if phone was found on website
                    if not lead.phone and audit_res.extracted_phones:
                        lead.phone = audit_res.extracted_phones[0]
                except Exception as e:
                    logger.debug("Failed auditing %s: %s", lead.website, e)

        await asyncio.gather(*[audit_single(l) for l in leads_to_audit])
    else:
        notify("audit", "Skipping website audits (quick mode or no own websites to check).")

    # 7. Score and generate hooks
    notify("score", "Scoring leads and generating pitch hooks...")
    for lead in leads:
        score, verdict = calculate_lead_score(lead)
        lead.score = score
        lead.verdict = verdict
        lead.hooks = generate_pitch_hooks(lead, lang=lang)

    # Sort descending by score
    leads.sort(key=lambda l: l.score, reverse=True)

    # Filter by minimum score
    if min_score > 0:
        leads = [l for l in leads if l.score >= min_score]

    # Filter by phone presence if requested
    if has_phone_only:
        leads = [l for l in leads if l.phone]

    notify("done", f"Pipeline completed with {len(leads)} qualified leads.")
    return leads, location
