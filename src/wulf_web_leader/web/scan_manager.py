"""Scan manager for background scan execution, state management, and SSE broadcasting."""

import asyncio
import io
import json
import logging
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
    "geocode": 15,
    "overpass": 35,
    "ceidg": 50,
    "offeneregister": 50,
    "audit": 75,
    "score": 90,
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
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

        # Attempt to load existing leads.json on startup if present
        default_leads_file = self.workspace_dir / "leads.json"
        if default_leads_file.is_file():
            try:
                self.load_scan_file(default_leads_file)
                self.message = f"Wczytano {len(self.leads)} leadów z {default_leads_file.name}"
            except Exception as e:
                logger.debug("Could not auto-load %s: %s", default_leads_file, e)

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
    ) -> bool:
        """Start a new background scan if no scan is currently active."""
        async with self._lock:
            if self.status == "running":
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
                "started_at": datetime.now().isoformat(),
            }

            log_entry = self._append_log("init", self.message)
            await self.broadcast({"type": "log", **log_entry})
            await self.broadcast({
                "type": "status",
                "status": self.status,
                "stage": self.stage,
                "progress": self.progress,
                "message": self.message,
                "counts": self.counts,
            })

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
                )
            )
            return True

    async def stop_scan(self) -> bool:
        """Gracefully cancel current running scan."""
        async with self._lock:
            if self.status != "running" or not self.scan_task:
                return False

            self.scan_task.cancel()
            self.status = "stopped"
            self.stage = "stopped"
            self.progress = 100
            self.message = "Skanowanie zostało przerwane przez użytkownika."

            log_entry = self._append_log("stopped", self.message)
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
    ) -> None:
        """Execute scan pipeline in background and report events."""
        try:
            vertical = resolve_or_create_vertical(vertical_id, country=country)
            if not vertical:
                raise ValueError(f"Nieznana branża: '{vertical_id}'")

            loop = asyncio.get_running_loop()

            def pipeline_progress_cb(stage: str, msg: str):
                self.stage = stage
                self.progress = STAGE_PROGRESS.get(stage, self.progress)
                self.message = msg
                log_entry = self._append_log(stage, msg)
                # Dispatch async broadcasts from thread/callback safely
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

            leads, location = await run_scan_pipeline(
                country=country,  # type: ignore
                city=city,
                vertical=vertical,
                radius_km=radius_km,
                lang=lang,
                do_audit=do_audit,
                min_score=min_score,
                has_phone_only=has_phone_only,
                progress_callback=pipeline_progress_cb,
            )

            self.leads = leads
            self.status = "completed"
            self.stage = "done"
            self.progress = 100
            self.message = f"Zakończono skanowanie. Znaleziono {len(leads)} kwalifikujących się firm."

            # Broadcast leads to clients
            for lead in leads:
                await self.broadcast({
                    "type": "lead",
                    "lead": lead.model_dump(mode="json"),
                    "counts": self.counts,
                })

            # Auto-persist to leads.json in workspace
            output_json = self.workspace_dir / "leads.json"
            export_leads_to_json(self.leads, output_json)

            log_entry = self._append_log("done", self.message)
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

        except asyncio.CancelledError:
            self.status = "stopped"
            self.stage = "stopped"
            self.progress = 100
            self.message = "Skanowanie zostało przerwane."
            log_entry = self._append_log("stopped", self.message)
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
        """Filter leads currently in memory."""
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
