import asyncio
import logging
from typing import Callable
from wulf_web_leader.models import CanonicalLead, CountryCode, VerticalDefinition
from wulf_web_leader.adapters.nominatim import NominatimClient, GeocodedLocation
from wulf_web_leader.adapters.osm import OverpassClient, build_overpass_query, is_corporate_entity
from wulf_web_leader.adapters.pl_ceidg import CEIDGAdapter
from wulf_web_leader.adapters.de_offeneregister import OffeneRegisterAdapter
from wulf_web_leader.audit.cache import AuditCache
from wulf_web_leader.audit.classifier import classify_website_kind
from wulf_web_leader.audit.fetch import audit_website
from wulf_web_leader.audit.verifier import resolve_and_verify_candidate
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
    audit_cache: AuditCache | None = None,
    no_cache: bool = False,
    nominatim_client: NominatimClient | None = None,
    overpass_client: OverpassClient | None = None,
    ceidg_adapter: CEIDGAdapter | None = None,
    offeneregister_adapter: OffeneRegisterAdapter | None = None,
    use_gemini: bool = False,
    gemini_api_key: str | None = None,
    gemini_max_leads: int = 5,
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
        raise ValueError(f"Nie znaleziono miasta '{city}' w kraju {country}. Sprawdź poprawność pisowni.")

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
        if not lead.website_kind or lead.website_kind in ("none", "other"):
            lead.website_kind = classify_website_kind(lead.website)

    # 5b. Polish CEIDG enrichment (optional / token-gated)
    if country == "PL":
        ceidg = ceidg_adapter or CEIDGAdapter()
        if ceidg.is_available():
            notify("ceidg", f"Weryfikacja {len(leads)} podmiotów w rejestrze CEIDG...")
            await ceidg.enrich_leads(leads)

    # 5c. German OffeneRegister enrichment (optional / local SQLite dump)
    if country == "DE":
        offene = offeneregister_adapter or OffeneRegisterAdapter()
        if offene.is_available():
            notify("offeneregister", f"Weryfikacja {len(leads)} podmiotów w bazie OffeneRegister...")
            offene.enrich_leads(leads)

    # 6. Audit websites and run QA Verification gates
    # Determine vertical keywords for domain candidate generation
    vertical_keywords: list[str] = []
    if vertical:
        v_tokens = [t.lower() for t in vertical.id.split("_") if len(t) > 2]
        if country == "DE":
            v_tokens.extend([t.lower() for t in getattr(vertical.de, "query", "").split() if len(t) > 2])
            if vertical.id == "plumbers":
                v_tokens.extend(["sanitaer", "heizung", "haustechnik", "klempner"])
            elif vertical.id == "electricians":
                v_tokens.extend(["elektro", "elektrik", "installation"])
            elif vertical.id == "auto_repair":
                v_tokens.extend(["kfz", "werkstatt", "auto"])
        else:
            v_tokens.extend([t.lower() for t in getattr(vertical.pl, "query", "").split() if len(t) > 2])
            if vertical.id == "plumbers":
                v_tokens.extend(["hydraulik", "instalacje", "sanitarne", "wod-kan"])
            elif vertical.id == "electricians":
                v_tokens.extend(["elektryk", "instalacje"])
            elif vertical.id == "auto_repair":
                v_tokens.extend(["warsztat", "mechanika", "auto"])
        vertical_keywords = list(dict.fromkeys(v_tokens))

    leads_to_audit = [
        lead for lead in leads
        if (lead.website_kind == "own" and lead.website) or (lead.website_kind == "none" and is_corporate_entity(lead.name))
    ]

    if do_audit and leads_to_audit:
        notify("audit", f"Auditing & QA verifying {len(leads_to_audit)} businesses...")
        cache = audit_cache or AuditCache()
        semaphore = asyncio.Semaphore(5)

        async def audit_single(lead: CanonicalLead):
            async with semaphore:
                try:
                    if lead.website:
                        cached_res = None if no_cache else cache.get(lead.website)
                        if cached_res is not None:
                            audit_res = cached_res
                        else:
                            audit_res = await audit_website(
                                lead.website,
                                lead_name=lead.name,
                                city=lead.city,
                                phone=lead.phone,
                                address=lead.address or lead.street,
                            )
                            cache.set(lead.website, audit_res)

                        lead.audit = audit_res
                        if not lead.phone and audit_res.extracted_phones:
                            lead.phone = audit_res.extracted_phones[0]
                        if not lead.email and audit_res.extracted_emails:
                            lead.email = audit_res.extracted_emails[0]

                        # QA Verification Gate on audited website
                        if audit_res.reachable:
                            is_bad_domain = audit_res.is_placeholder or (
                                lead.website_source == "email_domain"
                                and (not audit_res.entity_match or audit_res.entity_match_score < 30)
                            )
                            if is_bad_domain:
                                # Trigger QA Candidate Resolution
                                candidate = await resolve_and_verify_candidate(
                                    lead=lead,
                                    vertical_keywords=vertical_keywords,
                                )
                                if candidate:
                                    cand_url, cand_audit, method = candidate
                                    old_url = lead.website
                                    lead.website = cand_url
                                    lead.website_kind = "own"
                                    lead.website_source = "candidate_discovery"
                                    lead.audit = cand_audit
                                    if not lead.phone and cand_audit.extracted_phones:
                                        lead.phone = cand_audit.extracted_phones[0]
                                    if not lead.email and cand_audit.extracted_emails:
                                        lead.email = cand_audit.extracted_emails[0]
                                    lead.qa_status = "verified"
                                    lead.qa_notes = f"Wykryto i zweryfikowano rzeczywistą witrynę (zastąpiono {old_url})"
                                    lead.confidence = "high"
                                else:
                                    if audit_res.is_placeholder:
                                        lead.qa_status = "placeholder"
                                        lead.qa_notes = audit_res.placeholder_reason or "Zaślepka serwera / domena zaparkowana"
                                        lead.opportunity_type = "broken_website"
                                        lead.primary_issue = "Domena to nieaktywna zaślepka serwera / parking"
                                    else:
                                        lead.qa_status = "mismatch"
                                        lead.qa_notes = "Domena z emaila nie zawiera danych firmy"
                                        lead.opportunity_type = "suspect_unverified"
                                        lead.confidence = "low"
                            else:
                                lead.qa_status = "verified"
                                sigs = f", {', '.join(audit_res.matched_signals)}" if audit_res.matched_signals else ""
                                lead.qa_notes = f"Zweryfikowano tożsamość ({audit_res.entity_match_score}%{sigs})"
                        else:
                            # Website not reachable (4xx, 5xx, SSL, timeout)
                            candidate = await resolve_and_verify_candidate(
                                lead=lead,
                                vertical_keywords=vertical_keywords,
                            )
                            if candidate:
                                cand_url, cand_audit, method = candidate
                                old_url = lead.website
                                lead.website = cand_url
                                lead.audit = cand_audit
                                if not lead.phone and cand_audit.extracted_phones:
                                    lead.phone = cand_audit.extracted_phones[0]
                                if not lead.email and cand_audit.extracted_emails:
                                    lead.email = cand_audit.extracted_emails[0]
                                lead.qa_status = "verified"
                                lead.qa_notes = f"Zastąpiono niedziałającą domenę {old_url} nową witryną"
                                lead.confidence = "high"
                            else:
                                lead.qa_status = "verified"
                                lead.opportunity_type = "broken_website"
                                lead.primary_issue = audit_res.error_message or "Błąd połączenia ze stroną www"
                                lead.qa_notes = f"Potwierdzono awarię witryny: {lead.primary_issue}"

                    else:
                        # Corporate lead without website in OSM/email
                        candidate = await resolve_and_verify_candidate(
                            lead=lead,
                            vertical_keywords=vertical_keywords,
                        )
                        if candidate:
                            cand_url, cand_audit, method = candidate
                            lead.website = cand_url
                            lead.website_kind = "own"
                            lead.audit = cand_audit
                            if not lead.phone and cand_audit.extracted_phones:
                                lead.phone = cand_audit.extracted_phones[0]
                            if not lead.email and cand_audit.extracted_emails:
                                lead.email = cand_audit.extracted_emails[0]
                            lead.qa_status = "verified"
                            lead.qa_notes = f"Wykryto i zweryfikowano witrynę przez {method} (brakowało w OSM)"
                            lead.confidence = "high"
                        else:
                            lead.qa_status = "unverified"
                            lead.opportunity_type = "suspect_unverified"
                            lead.primary_issue = "Spółka kapitałowa bez strony w OSM (wymaga weryfikacji)"
                            lead.qa_notes = "Spółka bez strony w OSM — brak aktywnej witryny pod nazwą"
                            lead.confidence = "low"

                except Exception as e:
                    logger.debug("Failed auditing/verifying %s: %s", lead.name, e)

        await asyncio.gather(*[audit_single(l) for l in leads_to_audit])
        if audit_cache:
            audit_cache.flush()
        else:
            cache.flush()
    else:
        notify("audit", "Skipping website audits (quick mode or no businesses to check).")

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

    # 7b. Optional Google AI Studio (Gemini) Search Grounding enrichment
    if use_gemini:
        from wulf_web_leader.audit.gemini_verifier import verify_lead_with_gemini, is_gemini_available
        if is_gemini_available(gemini_api_key):
            candidates = [l for l in leads if l.verdict in ("hot", "warm") or l.score >= 50][:gemini_max_leads]
            if not candidates and leads:
                candidates = leads[:gemini_max_leads]
            if candidates:
                notify("gemini", f"Weryfikacja {len(candidates)} kluczowych firm w Google przez Gemini AI...")
                for c in candidates:
                    try:
                        intel = await verify_lead_with_gemini(c, api_key=gemini_api_key)
                        c.gemini_intel = intel
                        if not c.website and intel.discovered_website:
                            c.website = intel.discovered_website
                            c.website_kind = "own"
                            c.website_source = "candidate_discovery"
                        if intel.ai_pitch and intel.ai_pitch not in c.hooks:
                            c.hooks.insert(0, f"✨ [AI Google Pitch]: {intel.ai_pitch}")
                        await asyncio.sleep(0.5)
                    except Exception as err:
                        logger.debug("Gemini enrichment failed for %s: %s", c.name, err)

    notify("done", f"Pipeline completed with {len(leads)} qualified leads.")
    return leads, location
