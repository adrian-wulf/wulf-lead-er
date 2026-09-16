"""Scan manager for background scan execution, state management, and SSE broadcasting."""

import asyncio
import io
import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from wulf_web_leader.models import CanonicalLead, CountryCode
from wulf_web_leader.verticals import find_vertical, resolve_or_create_vertical
from wulf_web_leader.pipeline import run_scan_pipeline
from wulf_web_leader.export.writer import export_leads_to_csv, export_leads_to_json
from wulf_web_leader.export.report import generate_html_report

logger = logging.getLogger(__name__)

STAGE_PROGRESS = {
    "idle": 0,
    "init": 5,
    "geocode": 15,
    "overpass": 35,
    "parse": 40,
    "ceidg": 45,
    "offeneregister": 45,
    "audit": 60,
    "score": 88,
    "gemini": 94,
    "done": 100,
    "error": 100,
    "stopped": 100,
}


class ScanManager:
    """Manages scan lifecycle, live SSE streaming, and lead caching."""

    def __init__(self, workspace_dir: Path | None = None):
        self.workspace_dir = workspace_dir or Path.cwd()
        self.status: str = "idle"  # idle, running, completed, stopped, error
        self.stage: str = "idle"
        self.progress: int = 0
        self.message: str = "Gotowy do skanowania"
        self.logs: list[dict[str, str]] = []
        self.leads: list[CanonicalLead] = []
        self.current_params: dict[str, Any] = {}
        self.scan_task: asyncio.Task | None = None
        self.scan_proc: subprocess.Popen | None = None
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._state_mtime: float = 0.0
        self._leads_mtime: float = 0.0

        # Attempt to load existing leads.json on startup if present
        default_leads_file = self.workspace_dir / "leads.json"
        if default_leads_file.is_file():
            try:
                self.load_scan_file(default_leads_file)
                self._leads_mtime = default_leads_file.stat().st_mtime
                self.message = f"Wczytano {len(self.leads)} leadów z {default_leads_file.name}"
            except Exception as e:
                logger.debug("Could not auto-load %s: %s", default_leads_file, e)

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def _persist_state(self, pid: int | None = None) -> None:
        """Persist runtime scan state to disk for multi-worker synchronization."""
        try:
            state_file = self.workspace_dir / ".scan_state.json"
            tmp_file = self.workspace_dir / f".scan_state.tmp.{os.getpid()}"
            active_pid = pid or (self.scan_proc.pid if self.scan_proc else os.getpid())
            payload = {
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "message": self.message,
                "counts": self.counts,
                "current_params": self.current_params,
                "logs": self.logs[-200:],
                "pid": active_pid,
                "updated_at": time.time(),
            }
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
            tmp_file.replace(state_file)
            self._state_mtime = state_file.stat().st_mtime
        except Exception as e:
            logger.debug("Failed to persist scan state: %s", e)

    def get_status_data(self) -> dict[str, Any]:
        """Return scan status, loading latest disk state if multi-worker synced."""
        state_file = self.workspace_dir / ".scan_state.json"
        if state_file.is_file():
            try:
                mtime = state_file.stat().st_mtime
                if mtime > self._state_mtime or self.status in ("idle", "running"):
                    with open(state_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._state_mtime = mtime
                    self.status = data.get("status", self.status)
                    self.stage = data.get("stage", self.stage)
                    self.progress = data.get("progress", self.progress)
                    self.message = data.get("message", self.message)
                    self.logs = data.get("logs", self.logs)
                    self.current_params = data.get("current_params", self.current_params)

                    # Auto-detect died background processes
                    if self.status == "running":
                        pid = data.get("pid")
                        updated_at = data.get("updated_at", 0)
                        if pid and (time.time() - updated_at > 45) and not self._is_pid_alive(pid):
                            self.status = "error"
                            self.stage = "error"
                            self.progress = 100
                            self.message = "Proces skanera został przerwany przez serwer."
                            data["status"] = self.status
                            data["stage"] = self.stage
                            data["progress"] = self.progress
                            data["message"] = self.message
                            self._persist_state()

                    return data
            except Exception:
                pass

        return {
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "counts": self.counts,
            "current_params": self.current_params,
            "logs": self.logs,
        }

    @property
    def counts(self) -> dict[str, int]:
        total = len(self.leads)
        hot = sum(1 for l in self.leads if l.verdict == "hot")
        warm = sum(1 for l in self.leads if l.verdict == "warm")
        skip = sum(1 for l in self.leads if l.verdict == "skip")
        return {"total": total, "hot": hot, "warm": warm, "skip": skip}

    def subscribe(self) -> asyncio.Queue:
        """Register a new SSE subscriber queue."""
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Unregister an SSE subscriber queue."""
        self._subscribers.discard(q)

    async def broadcast(self, event: dict[str, Any]) -> None:
        """Broadcast an event payload to all active SSE subscribers."""
        dead_subscribers = set()
        for q in list(self._subscribers):
            try:
                q.put_nowait(event)
            except Exception:
                dead_subscribers.add(q)
        self._subscribers.difference_update(dead_subscribers)

    def _append_log(self, stage: str, message: str) -> dict[str, str]:
        ts = datetime.now().strftime("%H:%M:%S")
        entry = {"time": ts, "stage": stage, "message": message}
        self.logs.append(entry)
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]
        return entry

    async def start_scan(
        self,
        country: str,
        city: str,
        vertical_id: str,
        radius_km: float = 15.0,
        lang: str = "pl",
        min_score: int = 0,
        has_phone_only: bool = False,
        do_audit: bool = True,
        use_gemini: bool = False,
        gemini_api_key: str | None = None,
    ) -> bool:
        """Start a new background scan if no scan is currently active."""
        async with self._lock:
            # Refresh local status from disk state first
            self.get_status_data()

            # Check cross-process state file & process liveness
            state_file = self.workspace_dir / ".scan_state.json"
            if state_file.is_file():
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        disk_state = json.load(f)
                    if disk_state.get("status") == "running":
                        pid = disk_state.get("pid")
                        updated_at = disk_state.get("updated_at", 0)
                        now = time.time()
                        # If updated within the last 45 seconds and PID is alive, scan is active
                        if (now - updated_at < 45) and pid and self._is_pid_alive(pid):
                            return False
                except Exception:
                    pass
            elif self.status == "running":
                return False

            self.status = "running"
            self.stage = "init"
            self.progress = 5
            self.message = f"Rozpoczynanie skanowania: {city} ({country.upper()}), branża {vertical_id}..."
            self.logs = []
            self.leads = []
            self.current_params = {
                "country": country.upper(),
                "city": city.strip(),
                "vertical": vertical_id.strip(),
                "radius_km": radius_km,
                "lang": lang.lower(),
                "min_score": min_score,
                "has_phone_only": has_phone_only,
                "do_audit": do_audit,
                "use_gemini": use_gemini,
                "started_at": datetime.now().isoformat(),
            }

            log_entry = self._append_log("init", self.message)
            self._persist_state()
            await self.broadcast({"type": "log", **log_entry})
            await self.broadcast({
                "type": "status",
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "message": self.message,
                "counts": self.counts,
            })

            # Check if subprocess runner is enabled (default True in production/WSGI)
            use_subprocess = not getattr(self, "_force_in_process", False)
            if use_subprocess:
                try:
                    cmd = [
                        sys.executable,
                        "-m", "wulf_web_leader.web.runner",
                        "--workspace", str(self.workspace_dir),
                        "--country", country.upper(),
                        "--city", city.strip(),
                        "--vertical", vertical_id.strip(),
                        "--radius", str(radius_km),
                        "--lang", lang.lower(),
                        "--min-score", str(min_score),
                    ]
                    if has_phone_only:
                        cmd.append("--has-phone-only")
                    if do_audit:
                        cmd.append("--do-audit")
                    if use_gemini:
                        cmd.append("--use-gemini")
                    if gemini_api_key:
                        cmd.extend(["--gemini-api-key", gemini_api_key])

                    env = dict(os.environ)
                    src_dir = str(Path(__file__).resolve().parent.parent.parent)
                    env["PYTHONPATH"] = f"{src_dir}:{env.get('PYTHONPATH', '')}"
                    env["PYTHONIOENCODING"] = "utf-8"
                    env["LC_ALL"] = "C.UTF-8"
                    env["LANG"] = "C.UTF-8"

                    cmd_bytes = [a.encode("utf-8") if isinstance(a, str) else a for a in cmd]
                    proc = subprocess.Popen(
                        cmd_bytes,
                        cwd=str(self.workspace_dir),
                        env=env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    self.scan_proc = proc
                    self._persist_state(pid=proc.pid)
                    return True
                except Exception as e:
                    logger.warning("Could not launch subprocess runner, falling back to in-process task: %s", e)

            # In-process task fallback
            self.scan_task = asyncio.create_task(
                self._run_scan_task(
                    country=country.upper(),  # type: ignore
                    city=city.strip(),
                    vertical_id=vertical_id.strip(),
                    radius_km=radius_km,
                    lang=lang.lower(),
                    min_score=min_score,
                    has_phone_only=has_phone_only,
                    do_audit=do_audit,
                    use_gemini=use_gemini,
                    gemini_api_key=gemini_api_key,
                )
            )
            return True

    async def stop_scan(self) -> bool:
        """Gracefully cancel current running scan."""
        async with self._lock:
            # 1. Cancel in-process asyncio task if running
            if self.scan_task and not self.scan_task.done():
                self.scan_task.cancel()

            # 2. Terminate subprocess if running
            target_pid = None
            if self.scan_proc and self.scan_proc.poll() is None:
                target_pid = self.scan_proc.pid
            else:
                state_file = self.workspace_dir / ".scan_state.json"
                if state_file.is_file():
                    try:
                        with open(state_file, "r", encoding="utf-8") as f:
                            target_pid = json.load(f).get("pid")
                    except Exception:
                        pass

            if target_pid and target_pid != os.getpid() and self._is_pid_alive(target_pid):
                try:
                    os.kill(target_pid, signal.SIGTERM)
                except Exception:
                    pass

            self.status = "stopped"
            self.stage = "stopped"
            self.progress = 100
            self.message = "Skanowanie zostało przerwane przez użytkownika."

            log_entry = self._append_log("stopped", self.message)
            self._persist_state()
            await self.broadcast({"type": "log", **log_entry})
            await self.broadcast({
                "type": "status",
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "message": self.message,
                "counts": self.counts,
            })
            return True

    async def _run_scan_task(
        self,
        country: str,
        city: str,
        vertical_id: str,
        radius_km: float,
        lang: str,
        min_score: int,
        has_phone_only: bool,
        do_audit: bool,
        use_gemini: bool = False,
        gemini_api_key: str | None = None,
    ) -> None:
        """Execute scan pipeline in background and report events."""
        try:
            vertical = resolve_or_create_vertical(vertical_id, country=country)
            if not vertical:
                raise ValueError(f"Nieznana branża: '{vertical_id}'")

            loop = asyncio.get_running_loop()

            def pipeline_progress_cb(stage: str, msg: str):
                # Check for external stop request via state file
                state_file = self.workspace_dir / ".scan_state.json"
                if state_file.is_file():
                    try:
                        with open(state_file, "r", encoding="utf-8") as f:
                            if json.load(f).get("status") == "stopped":
                                raise asyncio.CancelledError("Scan stopped by user")
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        pass

                self.stage = stage
                if stage == "audit":
                    import re
                    m = re.search(r"\((\d+)/(\d+)\)", msg)
                    if m:
                        curr, total = int(m.group(1)), int(m.group(2))
                        total = max(total, 1)
                        progress = 40 + int((curr / total) * 45)
                        self.progress = min(progress, 85)
                    else:
                        self.progress = 50
                else:
                    self.progress = STAGE_PROGRESS.get(stage, self.progress)

                self.message = msg
                log_entry = self._append_log(stage, msg)
                self._persist_state()

                # Dispatch async broadcasts safely
                try:
                    current_loop = None
                    try:
                        current_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        pass

                    if current_loop is loop:
                        loop.create_task(self.broadcast({"type": "log", **log_entry}))
                        loop.create_task(self.broadcast({
                            "type": "status",
                            "status": self.status,
                            "stage": self.stage,
                            "progress": self.progress,
                            "message": self.message,
                            "counts": self.counts,
                        }))
                    else:
                        asyncio.run_coroutine_threadsafe(
                            self.broadcast({"type": "log", **log_entry}), loop
                        )
                        asyncio.run_coroutine_threadsafe(
                            self.broadcast({
                                "type": "status",
                                "status": self.status,
                                "stage": self.stage,
                                "progress": self.progress,
                                "message": self.message,
                                "counts": self.counts,
                            }),
                            loop,
                        )
                except Exception:
                    pass

            leads, location = await run_scan_pipeline(
                country=country,  # type: ignore
                city=city,
                vertical=vertical,
                radius_km=radius_km,
                lang=lang,
                do_audit=do_audit,
                min_score=min_score,
                has_phone_only=has_phone_only,
                use_gemini=use_gemini,
                gemini_api_key=gemini_api_key,
                progress_callback=pipeline_progress_cb,
            )

            self.leads = leads
            self.status = "completed"
            self.stage = "done"
            self.progress = 100
            self.message = f"Zakończono skanowanie. Znaleziono {len(leads)} kwalifikujących się firm."

            # Auto-persist to leads.json in workspace
            output_json = self.workspace_dir / "leads.json"
            export_leads_to_json(self.leads, output_json)

            log_entry = self._append_log("done", self.message)
            self._persist_state()

            # Broadcast leads to clients
            for lead in leads:
                await self.broadcast({
                    "type": "lead",
                    "lead": lead.model_dump(mode="json"),
                    "counts": self.counts,
                })

            await self.broadcast({"type": "log", **log_entry})
            await self.broadcast({
                "type": "done",
                "total": len(leads),
                "counts": self.counts,
                "message": self.message,
                "output_file": str(output_json.name),
            })
            await self.broadcast({
                "type": "status",
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "message": self.message,
                "counts": self.counts,
            })

            # Launch post-scan OSINT verification queue
            asyncio.create_task(
                self._run_post_scan_osint_queue(
                    gemini_api_key=gemini_api_key,
                    use_gemini=use_gemini,
                )
            )

        except asyncio.CancelledError:
            self.status = "stopped"
            self.stage = "stopped"
            self.progress = 100
            self.message = "Skanowanie zostało przerwane."
            log_entry = self._append_log("stopped", self.message)
            self._persist_state()
            await self.broadcast({"type": "log", **log_entry})
            await self.broadcast({
                "type": "status",
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "message": self.message,
                "counts": self.counts,
            })

        except Exception as e:
            logger.exception("Scan error: %s", e)
            self.status = "error"
            self.stage = "error"
            self.progress = 100
            self.message = f"Błąd skanowania: {e}"
            log_entry = self._append_log("error", self.message)
            self._persist_state()
            await self.broadcast({"type": "log", **log_entry})
            await self.broadcast({"type": "error", "message": str(e)})
            await self.broadcast({
                "type": "status",
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "message": self.message,
                "counts": self.counts,
            })

    def get_leads(
        self,
        query: str | None = None,
        verdict: str | None = None,
        has_phone: bool | None = None,
        min_score: int | None = None,
    ) -> list[CanonicalLead]:
        """Filter leads currently in memory (auto-reloading from disk if empty or updated)."""
        default_leads_file = self.workspace_dir / "leads.json"
        if default_leads_file.is_file():
            try:
                mtime = default_leads_file.stat().st_mtime
                if not self.leads or mtime > getattr(self, "_leads_mtime", 0.0):
                    self.load_scan_file(default_leads_file)
                    self._leads_mtime = mtime
            except Exception:
                pass

        results = []
        q_norm = query.strip().lower() if query else None
        v_norm = verdict.strip().lower() if verdict and verdict.lower() != "all" else None

        for lead in self.leads:
            if v_norm and lead.verdict != v_norm:
                continue
            if min_score is not None and lead.score < min_score:
                continue
            if has_phone and not lead.phone:
                continue
            if q_norm:
                searchable = f"{lead.name} {lead.city or ''} {lead.phone or ''} {lead.website or ''} {lead.primary_issue or ''}".lower()
                if q_norm not in searchable:
                    continue
            results.append(lead)

        return results

    def get_lead_by_source_id(self, source_id: str) -> CanonicalLead | None:
        """Find a single lead in memory by its unique source_id (auto-reloading if empty)."""
        if not self.leads:
            default_leads_file = self.workspace_dir / "leads.json"
            if default_leads_file.is_file():
                try:
                    self.load_scan_file(default_leads_file)
                except Exception:
                    pass

        for lead in self.leads:
            if lead.source_id == source_id:
                return lead
        return None

    async def verify_lead_gemini(
        self,
        source_id: str,
        api_key: str | None = None,
    ) -> CanonicalLead | None:
        """Verify an individual lead using candidate DNS discovery and Gemini Google OSINT."""
        lead = self.get_lead_by_source_id(source_id)
        if not lead:
            return None

        from wulf_web_leader.audit.gemini_verifier import verify_lead_with_gemini
        from wulf_web_leader.audit.wikipedia_resolver import lookup_company_wikipedia
        from wulf_web_leader.audit.verifier import resolve_and_verify_candidate
        from wulf_web_leader.score.engine import calculate_lead_score
        from wulf_web_leader.score.hooks import generate_pitch_hooks
        import wulf_web_leader.audit.fetch as audit_fetch

        # 0. Wikipedia OSINT Lookup (PL & DE)
        try:
            wiki_intel = await lookup_company_wikipedia(lead)
            if wiki_intel and wiki_intel.found:
                lead.wikipedia_intel = wiki_intel.model_dump()
                if wiki_intel.notes:
                    lead.qa_notes = (lead.qa_notes + " | " if lead.qa_notes else "") + wiki_intel.notes
                lead.score, lead.verdict = calculate_lead_score(lead)
                lead.hooks = generate_pitch_hooks(lead)
        except Exception as e:
            logger.debug("Wikipedia lookup in verify_lead_gemini: %s", e)

        intel = await verify_lead_with_gemini(lead, api_key=api_key)
        lead.gemini_intel = intel

        # If lead has no website or website is unreachable, check DNS candidate resolution
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
            except Exception as e:
                logger.debug("Candidate resolution in verify_lead_gemini: %s", e)

        # If still no website or unreachable, check if Gemini discovered an official website
        if (not lead.website or (lead.audit and not lead.audit.reachable)) and intel.discovered_website:
            try:
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
            except Exception as e:
                logger.debug("Gemini discovered website audit: %s", e)

        # If Gemini generated an AI pitch, make it the top primary hook
        if intel.ai_pitch and intel.ai_pitch not in lead.hooks:
            lead.hooks.insert(0, f"✨ [AI Google Pitch]: {intel.ai_pitch}")

        self._persist_current_leads()
        await self.broadcast({
            "type": "lead_updated",
            "lead": lead.model_dump(mode="json"),
            "counts": self.counts,
        })
        return lead

    async def _run_post_scan_osint_queue(
        self,
        gemini_api_key: str | None = None,
        use_gemini: bool = False,
    ) -> None:
        """Background queue running immediately after in-process scan completes."""
        missing = [l for l in self.leads if not l.website or l.website_kind == "none"]
        if not missing:
            return

        total = len(missing)
        log_entry = self._append_log("osint_queue", f"⚡ Kolejka OSINT: Uruchomiono automatyczną weryfikację witryn w tle dla {total} firm...")
        await self.broadcast({"type": "log", **log_entry})
        self._persist_state()

        from wulf_web_leader.audit.verifier import resolve_and_verify_candidate
        from wulf_web_leader.score.engine import calculate_lead_score
        from wulf_web_leader.score.hooks import generate_pitch_hooks
        import wulf_web_leader.audit.fetch as audit_fetch

        for i, lead in enumerate(missing, start=1):
            if self.status == "stopped":
                break

            try:
                cand = await resolve_and_verify_candidate(lead)
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
                    log_entry = self._append_log("osint_queue", f"✅ Znaleziono domenę {cand_url} dla firmy {lead.name}!")
                    await self.broadcast({"type": "log", **log_entry})
            except Exception as e:
                logger.debug("Candidate resolution in queue for %s: %s", lead.name, e)

            key_to_use = gemini_api_key or os.environ.get("GEMINI_API_KEY")
            if use_gemini or key_to_use:
                try:
                    from wulf_web_leader.audit.gemini_verifier import verify_lead_with_gemini
                    intel = await verify_lead_with_gemini(lead, api_key=key_to_use)
                    if intel and intel.checked:
                        lead.gemini_intel = intel
                        if not lead.website and intel.discovered_website:
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
                        if intel.ai_pitch and intel.ai_pitch not in lead.hooks:
                            lead.hooks.insert(0, f"✨ [AI Google Pitch]: {intel.ai_pitch}")
                except Exception as e:
                    logger.debug("Gemini OSINT verification error in queue for %s: %s", lead.name, e)

            self._persist_current_leads()
            await self.broadcast({
                "type": "lead_updated",
                "lead": lead.model_dump(mode="json"),
                "counts": self.counts,
                "queue": {"current": i, "total": total},
            })
            await asyncio.sleep(0.3)

        log_entry = self._append_log("osint_queue", f"Zakończono weryfikację OSINT w tle ({total} firm sprawdzonych).")
        await self.broadcast({"type": "log", **log_entry})
        await self.broadcast({"type": "queue_completed", "total": total})

    def _persist_current_leads(self) -> None:
        """Persist in-memory leads to workspace leads.json if leads are present."""
        if not self.leads:
            return
        output_json = self.workspace_dir / "leads.json"
        try:
            export_leads_to_json(self.leads, output_json)
        except Exception as e:
            logger.warning("Could not auto-persist leads to %s: %s", output_json, e)

    def list_saved_scans(self) -> list[dict[str, Any]]:
        """List historical leads*.json files in workspace directory."""
        scans = []
        for p in self.workspace_dir.glob("leads*.json"):
            if not p.is_file():
                continue
            stat = p.stat()
            count = 0
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data.get("leads", []) if isinstance(data, dict) else data
                    count = len(items)
            except Exception:
                pass

            scans.append({
                "filename": p.name,
                "path": str(p),
                "count": count,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "size_bytes": stat.st_size,
            })

        scans.sort(key=lambda x: x["modified"], reverse=True)
        return scans

    def load_scan_file(self, file_path: Path) -> int:
        """Load leads from a given JSON file into memory."""
        if not file_path.is_file():
            raise FileNotFoundError(f"Plik '{file_path}' nie istnieje.")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_leads = data.get("leads", []) if isinstance(data, dict) else data
        self.leads = [CanonicalLead.model_validate(item) for item in raw_leads]
        self.status = "completed"
        self.stage = "done"
        self.progress = 100
        self.message = f"Wczytano {len(self.leads)} leadów z pliku {file_path.name}"
        return len(self.leads)

    def export_leads(
        self,
        format_type: str,
        leads_to_export: list[CanonicalLead] | None = None,
    ) -> tuple[bytes, str, str]:
        """Export leads to requested format: CSV, JSON, or HTML report.
        
        Returns: (content_bytes, media_type, filename)
        """
        leads = leads_to_export if leads_to_export is not None else self.leads
        fmt = format_type.strip().lower()

        if fmt == "json":
            data = {
                "generated_at": datetime.now().isoformat(),
                "total_leads": len(leads),
                "leads": [lead.model_dump(mode="json") for lead in leads],
            }
            content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            return content, "application/json; charset=utf-8", "leads.json"

        elif fmt == "csv":
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                export_leads_to_csv(leads, tmp_path, delimiter=",")
                content = tmp_path.read_bytes()
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
            return content, "text/csv; charset=utf-8", "leads.csv"

        elif fmt == "html":
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                generate_html_report(leads, tmp_path)
                content = tmp_path.read_bytes()
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
            return content, "text/html; charset=utf-8", "report.html"

        else:
            raise ValueError(f"Nieobsługiwany format eksportu: '{format_type}' (obsługiwane: csv, json, html)")
