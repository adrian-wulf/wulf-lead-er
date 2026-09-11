"""FastAPI web application for wulf-web-leader dashboard."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from wulf_web_leader.verticals import load_all_verticals
from wulf_web_leader.web.scan_manager import ScanManager

logger = logging.getLogger(__name__)

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"

app = FastAPI(
    title="Wulf Web Leader",
    description="Lokalny skaner leadów dla web designerów (Polska i Niemcy)",
    version="0.3.0",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
scan_manager = ScanManager()


class StartScanRequest(BaseModel):
    country: str = Field(default="PL", description="Kod kraju: PL lub DE")
    city: str = Field(..., description="Nazwa miasta")
    vertical: str = Field(..., description="ID branży")
    radius: float = Field(default=15.0, ge=1.0, le=100.0, description="Promień w km")
    lang: str = Field(default="pl", description="Język hooków: pl, de, en")
    min_score: int = Field(default=0, ge=0, le=100, description="Minimalny wynik leada")
    has_phone: bool = Field(default=False, description="Tylko firmy z telefonem")
    do_audit: bool = Field(default=True, description="Wykonaj audyt techniczny stron")
    use_gemini: bool = Field(default=False, description="Weryfikuj w Google przez Gemini AI")
    gemini_api_key: Optional[str] = Field(default=None, description="Klucz API Gemini (opcjonalny)")


class GeminiVerifyRequest(BaseModel):
    api_key: Optional[str] = None


class LoadScanRequest(BaseModel):
    filename: Optional[str] = None
    path: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Render main dashboard."""
    verticals = load_all_verticals()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "version": "0.3.0",
            "verticals": list(verticals.values()),
            "initial_counts": scan_manager.counts,
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.3.0"}


@app.get("/api/verticals")
async def get_verticals():
    """Get list of all supported industry verticals."""
    verticals = load_all_verticals()
    data = []
    for v in verticals.values():
        data.append({
            "id": v.id,
            "name": v.name,
            "pl": {
                "query": v.pl.query,
                "label": v.pl.label,
                "aliases": v.aliases.pl,
            },
            "de": {
                "query": v.de.query,
                "label": v.de.label,
                "aliases": v.aliases.de,
            },
        })
    return {"verticals": data}


@app.get("/api/scans")
async def get_saved_scans():
    """List available scan files."""
    return {"scans": scan_manager.list_saved_scans()}


@app.post("/api/scans/load")
async def load_saved_scan(req: LoadScanRequest):
    """Load a specific scan file into memory."""
    target_path = None
    if req.path:
        target_path = Path(req.path)
    elif req.filename:
        target_path = scan_manager.workspace_dir / req.filename
    else:
        target_path = scan_manager.workspace_dir / "leads.json"

    if not target_path or not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"Plik '{target_path}' nie istnieje.")

    try:
        count = scan_manager.load_scan_file(target_path)
        return {"status": "ok", "loaded": count, "counts": scan_manager.counts}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Błąd odczytu pliku: {e}")


@app.post("/api/scan/start")
async def start_scan(req: StartScanRequest):
    """Start an asynchronous lead discovery scan."""
    country_norm = req.country.strip().upper()
    if country_norm not in ("PL", "DE"):
        raise HTTPException(status_code=400, detail="Kod kraju musi wynosić 'PL' lub 'DE'.")

    started = await scan_manager.start_scan(
        country=country_norm,
        city=req.city,
        vertical_id=req.vertical,
        radius_km=req.radius,
        lang=req.lang,
        min_score=req.min_score,
        has_phone_only=req.has_phone,
        do_audit=req.do_audit,
        use_gemini=req.use_gemini,
        gemini_api_key=req.gemini_api_key,
    )

    if not started:
        raise HTTPException(status_code=409, detail="Skanowanie jest już w toku. Poczekaj na zakończenie lub zatrzymaj obecne.")

    return {
        "status": "started",
        "params": scan_manager.current_params,
        "message": scan_manager.message,
    }


@app.post("/api/scan/stop")
async def stop_scan():
    """Cancel the active scan."""
    stopped = await scan_manager.stop_scan()
    return {"stopped": stopped, "status": scan_manager.status}


@app.get("/api/scan/status")
async def get_scan_status():
    """Get current scan state, progress, logs, and counts."""
    return {
        "status": scan_manager.status,
        "stage": scan_manager.stage,
        "progress": scan_manager.progress,
        "message": scan_manager.message,
        "counts": scan_manager.counts,
        "current_params": scan_manager.current_params,
        "logs": scan_manager.logs,
    }


@app.get("/api/scan/events")
async def stream_scan_events(request: Request):
    """SSE endpoint streaming live scan events (status, logs, leads, completion)."""
    queue = scan_manager.subscribe()

    async def event_generator():
        try:
            # Yield initial status immediately on connection
            init_event = {
                "type": "status",
                "status": scan_manager.status,
                "stage": scan_manager.stage,
                "progress": scan_manager.progress,
                "message": scan_manager.message,
                "counts": scan_manager.counts,
            }
            yield f"data: {json.dumps(init_event)}\n\n"

            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # SSE keep-alive ping
                    yield ": ping\n\n"

        finally:
            scan_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/leads")
async def get_leads(
    query: Optional[str] = Query(None, description="Filtruj po nazwie, mieście, telefonie, witrynie"),
    verdict: Optional[str] = Query("all", description="Filtruj po ocenie: all, hot, warm, skip"),
    has_phone: bool = Query(False, description="Tylko firmy z numerem telefonu"),
    min_score: int = Query(0, ge=0, le=100, description="Minimalny score"),
):
    """Query currently loaded leads with search and verdict filters."""
    leads = scan_manager.get_leads(
        query=query,
        verdict=verdict,
        has_phone=has_phone,
        min_score=min_score,
    )
    return {
        "total": len(leads),
        "counts": scan_manager.counts,
        "leads": [lead.model_dump(mode="json") for lead in leads],
    }


@app.get("/api/export/{format_type}")
async def export_leads(
    format_type: str,
    query: Optional[str] = Query(None),
    verdict: Optional[str] = Query("all"),
    has_phone: bool = Query(False),
    min_score: int = Query(0),
):
    """Export currently loaded / filtered leads into CSV, JSON, or HTML."""
    try:
        filtered_leads = scan_manager.get_leads(
            query=query,
            verdict=verdict,
            has_phone=has_phone,
            min_score=min_score,
        )
        content_bytes, media_type, filename = scan_manager.export_leads(format_type, filtered_leads)
        return Response(
            content=content_bytes,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/gemini/status")
async def get_gemini_status():
    """Check if Gemini API key is configured and return status."""
    from wulf_web_leader.audit.gemini_verifier import is_gemini_available
    return {
        "available": is_gemini_available(),
        "model": "gemini-2.0-flash",
    }


@app.post("/api/leads/{source_id}/gemini-verify")
async def verify_lead_gemini_endpoint(
    source_id: str,
    req: Optional[GeminiVerifyRequest] = None,
    request: Request = None,
):
    """Verify an individual lead in Google via Gemini API with live Search Grounding."""
    api_key = req.api_key if req else None
    if not api_key and request:
        api_key = request.headers.get("X-Gemini-Api-Key")

    lead = await scan_manager.verify_lead_gemini(source_id=source_id, api_key=api_key)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead o ID '{source_id}' nie został odnaleziony w pamięci.")

    return {
        "status": "ok",
        "lead": lead.model_dump(mode="json"),
        "gemini_intel": lead.gemini_intel.model_dump(mode="json") if lead.gemini_intel else None,
    }

