"""Background runner for Wulf Web Leader scan pipeline.

Runs in an independent OS subprocess to decouple long-running pipeline
execution from ephemeral WSGI / Passenger request lifecycles.
"""

import argparse
import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import signal
import sys
import time
from typing import Any

from wulf_web_leader.models import CanonicalLead
from wulf_web_leader.verticals import resolve_or_create_vertical
from wulf_web_leader.pipeline import run_scan_pipeline
from wulf_web_leader.export.writer import export_leads_to_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scan_runner")

STAGE_PROGRESS = {
    "idle": 0,
    "init": 5,
    "geocode": 15,
    "gmaps": 25,
    "overpass": 35,
    "parse": 40,
    "ceidg": 45,
    "offeneregister": 45,
    "audit": 50,
    "score": 88,
    "osint_queue": 94,
    "gemini": 96,
    "done": 100,
    "error": 100,
    "stopped": 100,
}


def atomic_persist_state(workspace_dir: Path, data: dict[str, Any]) -> None:
    """Atomically write scan state to disk so any WSGI worker can read it."""
    state_file = workspace_dir / ".scan_state.json"
    tmp_file = workspace_dir / f".scan_state.tmp.{os.getpid()}"
    try:
        data["pid"] = os.getpid()
        data["updated_at"] = time.time()
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        tmp_file.replace(state_file)
    except Exception as e:
        logger.error("Failed to persist state: %s", e)
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except Exception:
                pass


def compute_counts(leads: list[CanonicalLead]) -> dict[str, int]:
    total = len(leads)
    hot = sum(1 for l in leads if l.verdict == "hot")
    warm = sum(1 for l in leads if l.verdict == "warm")
    skip = sum(1 for l in leads if l.verdict == "skip")
    return {"total": total, "hot": hot, "warm": warm, "skip": skip}


async def run_post_scan_osint_queue(
    leads: list[CanonicalLead],
    workspace_dir: Path,
    state: dict[str, Any],
    append_log: Any,
    use_gemini: bool = False,
    gemini_api_key: str | None = None,
) -> None:
    """
    Background queue running immediately after initial search completes.
    Verifies leads lacking websites against DNS candidates, online presence, and Gemini/Google OSINT.
    """
    from wulf_web_leader.audit.verifier import resolve_and_verify_candidate
    from wulf_web_leader.score.engine import calculate_lead_score
    from wulf_web_leader.score.hooks import generate_pitch_hooks
    import wulf_web_leader.audit.fetch as audit_fetch

    leads_file = workspace_dir / "leads.json"
    state_file = workspace_dir / ".scan_state.json"

    target_leads = [
        l for l in leads
        if not l.website
        or l.website_kind == "none"
        or (l.audit and not l.audit.reachable)
        or l.opportunity_type == "corporate_enterprise"
    ]
    if not target_leads:
        return

    append_log(
        "osint_queue",
        f"⚡ Kolejka OSINT: Uruchomiono weryfikację stron i podmiotów w tle dla {len(target_leads)} firm...",
    )
    state["osint_queue"] = {
        "current": 0,
        "total": len(target_leads),
        "done": False,
    }
    atomic_persist_state(workspace_dir, state)

    from wulf_web_leader.audit.wikipedia_resolver import lookup_company_wikipedia

    for i, lead in enumerate(target_leads, start=1):
        if state_file.is_file():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    disk_state = json.load(f)
                if disk_state.get("status") == "stopped":
                    break
            except Exception:
                pass

        append_log("osint_queue", f"Weryfikacja ({i}/{len(target_leads)}): {lead.name} ({lead.city or ''})...")

        # 1. Wikipedia & Wikidata Knowledge Lookup (PL & DE)
        try:
            wiki_intel = await lookup_company_wikipedia(lead)
            if wiki_intel and wiki_intel.found:
                lead.wikipedia_intel = wiki_intel.model_dump()
                if wiki_intel.notes:
                    lead.qa_notes = (lead.qa_notes + " | " if lead.qa_notes else "") + wiki_intel.notes
                lead.score, lead.verdict = calculate_lead_score(lead)
                lead.hooks = generate_pitch_hooks(lead)
                append_log("osint_queue", f"📚 Wikipedia: Rozpoznano {lead.name} jako podmiot encyklopedyczny ({wiki_intel.title})")
        except Exception as e:
            logger.debug("Wikipedia lookup in runner error for %s: %s", lead.name, e)

        # 2. DNS Candidate Discovery (for missing or broken sites)
        found_site = False
        if not lead.website or (lead.audit and not lead.audit.reachable):
            try:
                cand = await resolve_and_verify_candidate(lead)
                if not cand and lead.wikipedia_intel and isinstance(lead.wikipedia_intel, dict):
                    new_brand = lead.wikipedia_intel.get("new_brand_name")
                    if new_brand:
                        alt_lead = lead.model_copy()
                        alt_lead.name = new_brand
                        cand = await resolve_and_verify_candidate(alt_lead)

                if cand:
                    cand_url, cand_audit, method = cand
                    lead.website = cand_url
                    lead.website_kind = "own"
                    lead.website_source = "candidate_discovery"
                    lead.audit = cand_audit
                    lead.qa_status = "verified"
                    lead.confidence = "high"
                    if not lead.phone and cand_audit.extracted_phones:
                        lead.phone = cand_audit.extracted_phones[0]
                    if not lead.email and cand_audit.extracted_emails:
                        lead.email = cand_audit.extracted_emails[0]
                    lead.score, lead.verdict = calculate_lead_score(lead)
                    lead.hooks = generate_pitch_hooks(lead)
                    found_site = True
                    append_log("osint_queue", f"✅ Znaleziono domenę {cand_url} dla firmy {lead.name}!")
            except Exception as e:
                logger.debug("Candidate resolution error for %s: %s", lead.name, e)


        # Gemini / Google Intel check
        key_to_use = gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if use_gemini or key_to_use:
            try:
                from wulf_web_leader.audit.gemini_verifier import verify_lead_with_gemini
                intel = await verify_lead_with_gemini(lead, api_key=key_to_use)
                if intel and intel.checked:
                    lead.gemini_intel = intel
                    if (not lead.website or (lead.audit and not lead.audit.reachable)) and intel.discovered_website:
                        lead.website = intel.discovered_website
                        lead.website_kind = "own"
                        lead.website_source = "google_osint"
                        audit_res = await audit_fetch.audit_website(
                            intel.discovered_website,
                            lead_name=lead.name,
                            city=lead.city,
                            phone=lead.phone,
                            address=lead.address or lead.street,
                        )
                        lead.audit = audit_res
                        lead.qa_status = "verified"
                        lead.confidence = "high"
                        if not lead.phone and audit_res.extracted_phones:
                            lead.phone = audit_res.extracted_phones[0]
                        if not lead.email and audit_res.extracted_emails:
                            lead.email = audit_res.extracted_emails[0]
                        lead.score, lead.verdict = calculate_lead_score(lead)
                        lead.hooks = generate_pitch_hooks(lead)
                        found_site = True
                    if intel.ai_pitch and intel.ai_pitch not in lead.hooks:
                        lead.hooks.insert(0, f"✨ [AI Google Pitch]: {intel.ai_pitch}")
            except Exception as e:
                logger.debug("Gemini OSINT verification error for %s: %s", lead.name, e)

        export_leads_to_json(leads, leads_file)
        state["counts"] = compute_counts(leads)
        state["osint_queue"] = {
            "current": i,
            "total": len(target_leads),
            "done": False,
            "last_verified": lead.name,
            "found_site": found_site,
        }
        atomic_persist_state(workspace_dir, state)
        await asyncio.sleep(0.3)

    state["osint_queue"] = {
        "current": len(target_leads),
        "total": len(target_leads),
        "done": True,
    }
    append_log("osint_queue", f"Zakończono weryfikację OSINT w tle ({len(target_leads)} firm sprawdzonych).")
    atomic_persist_state(workspace_dir, state)
    export_leads_to_json(leads, leads_file)



async def main() -> None:
    parser = argparse.ArgumentParser(description="Wulf Web Leader Background Scan Runner")
    parser.add_argument("--workspace", required=True, help="Workspace directory for leads and state")
    parser.add_argument("--country", required=True, help="Country code (PL or DE)")
    parser.add_argument("--city", required=True, help="Target city")
    parser.add_argument("--vertical", required=True, help="Vertical identifier")
    parser.add_argument("--radius", type=float, default=15.0, help="Radius in km")
    parser.add_argument("--lang", default="pl", help="Language")
    parser.add_argument("--min-score", type=int, default=0, help="Minimum lead score")
    parser.add_argument("--has-phone-only", action="store_true", help="Only keep leads with phone")
    parser.add_argument("--do-audit", action="store_true", help="Audit website availability and DNS")
    parser.add_argument("--use-gemini", action="store_true", help="Use Gemini AI for Google verification")
    parser.add_argument("--gemini-api-key", default=None, help="Gemini API Key")

    args = parser.parse_args()
    workspace_dir = Path(args.workspace).resolve()
    country = args.country.upper()
    city = args.city.strip()
    vertical_id = args.vertical.strip()
    radius_km = args.radius
    lang = args.lang.lower()
    min_score = args.min_score
    has_phone_only = args.has_phone_only
    do_audit = args.do_audit
    use_gemini = args.use_gemini
    gemini_api_key = args.gemini_api_key

    current_params = {
        "country": country,
        "city": city,
        "vertical": vertical_id,
        "radius_km": radius_km,
        "lang": lang,
        "min_score": min_score,
        "has_phone_only": has_phone_only,
        "do_audit": do_audit,
        "use_gemini": use_gemini,
        "started_at": datetime.now().isoformat(),
    }

    logs: list[dict[str, str]] = []
    state: dict[str, Any] = {
        "status": "running",
        "stage": "init",
        "progress": 5,
        "message": f"Rozpoczynanie skanowania: {city} ({country}), branża {vertical_id}...",
        "counts": {"total": 0, "hot": 0, "warm": 0, "skip": 0},
        "current_params": current_params,
        "logs": logs,
    }

    def append_log(stage: str, msg: str) -> dict[str, str]:
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "stage": stage,
            "message": msg,
        }
        logs.append(entry)
        if len(logs) > 200:
            del logs[: len(logs) - 200]
        return entry

    append_log("init", state["message"])
    atomic_persist_state(workspace_dir, state)

    # Handle graceful stop signals
    stop_requested = False

    def handle_sigterm(*_):
        nonlocal stop_requested
        stop_requested = True
        logger.info("Received termination signal, stopping scan runner...")

    try:
        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)
    except Exception:
        pass

    def progress_callback(stage: str, msg: str) -> None:
        if stop_requested:
            raise asyncio.CancelledError("Zatrzymano przez sygnał systemowy")

        # Check disk state for user stop
        state_file = workspace_dir / ".scan_state.json"
        if state_file.is_file():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    disk_state = json.load(f)
                if disk_state.get("status") == "stopped":
                    raise asyncio.CancelledError("Zatrzymano przez użytkownika")
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        state["stage"] = stage
        state["message"] = msg

        # Calculate progress smoothly
        if stage == "audit":
            # Match e.g. "Audyt witryn (12/40): ..."
            m = re.search(r"\((\d+)/(\d+)\)", msg)
            if m:
                curr, total = int(m.group(1)), int(m.group(2))
                total = max(total, 1)
                progress = 40 + int((curr / total) * 45)
                state["progress"] = min(progress, 85)
            else:
                state["progress"] = 50
        else:
            state["progress"] = STAGE_PROGRESS.get(stage, state.get("progress", 50))

        append_log(stage, msg)
        atomic_persist_state(workspace_dir, state)

    try:
        vert = resolve_or_create_vertical(vertical_id, country)
        leads, location = await run_scan_pipeline(
            country=country,  # type: ignore
            city=city,
            vertical=vert,
            radius_km=radius_km,
            lang=lang,
            min_score=min_score,
            has_phone_only=has_phone_only,
            do_audit=do_audit,
            use_gemini=use_gemini,
            gemini_api_key=gemini_api_key,
            progress_callback=progress_callback,
        )

        # Output results
        leads_file = workspace_dir / "leads.json"
        export_leads_to_json(leads, leads_file)
        counts = compute_counts(leads)

        state["status"] = "completed"
        state["stage"] = "done"
        state["progress"] = 100
        state["message"] = f"Zakończono skanowanie. Znaleziono {len(leads)} kwalifikujących się firm."
        state["counts"] = counts
        append_log("done", state["message"])
        atomic_persist_state(workspace_dir, state)
        logger.info("Scan completed successfully: %d leads saved to %s", len(leads), leads_file)

        # Automatic post-scan OSINT verification queue for missing websites
        await run_post_scan_osint_queue(
            leads=leads,
            workspace_dir=workspace_dir,
            state=state,
            append_log=append_log,
            use_gemini=use_gemini,
            gemini_api_key=gemini_api_key,
        )

    except asyncio.CancelledError:
        state["status"] = "stopped"
        state["stage"] = "stopped"
        state["progress"] = 100
        state["message"] = "Skanowanie zostało przerwane."
        append_log("stopped", state["message"])
        atomic_persist_state(workspace_dir, state)
        logger.info("Scan was cancelled.")

    except Exception as e:
        logger.exception("Error during scan: %s", e)
        state["status"] = "error"
        state["stage"] = "error"
        state["progress"] = 100
        state["message"] = f"Błąd skanowania: {e}"
        append_log("error", state["message"])
        atomic_persist_state(workspace_dir, state)


if __name__ == "__main__":
    asyncio.run(main())
