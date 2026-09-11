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
    "overpass": 35,
    "parse": 40,
    "ceidg": 45,
    "offeneregister": 45,
    "audit": 50,
    "score": 88,
    "gemini": 94,
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
