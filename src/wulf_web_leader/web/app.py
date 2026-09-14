"""FastAPI web application for wulf-web-leader dashboard."""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from wulf_web_leader.verticals import load_all_verticals
from wulf_web_leader.web.rate_limiter import (
    gemini_rate_limiter,
    get_client_ip,
    scan_rate_limiter,
)
from wulf_web_leader.web.scan_manager import ScanManager
from wulf_web_leader.web.session_manager import (
    COOKIE_MAX_AGE,
    SESSION_COOKIE_NAME,
    SESSION_HEADER_NAME,
    get_manager,
    get_session_id,
    sanitize_session_id,
    session_registry,
)

logger = logging.getLogger(__name__)

# Automatically load .env file if present in workspace root or parents
def _load_env_file():
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    for p in candidates:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
                break
            except Exception:
                pass

_load_env_file()

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"

app = FastAPI(
    title="Wulf Web Leader",
    description="Lokalny skaner leadów dla web designerów (Polska i Niemcy)",
    version="0.3.0",
)

# Global default manager reference for backwards compatibility and testing
scan_manager = session_registry.get("default")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.middleware("http")
async def session_cookie_middleware(request: Request, call_next):
    """Ensure every HTTP request has an isolated session ID and cookie."""
    raw_sid = request.cookies.get(SESSION_COOKIE_NAME) or request.headers.get(SESSION_HEADER_NAME)
    sid = sanitize_session_id(raw_sid)
    is_new = (raw_sid != sid)
    request.state.session_id = sid

    response = await call_next(request)

    # Set cookie if absent, sanitized, or not yet set
    if is_new or request.cookies.get(SESSION_COOKIE_NAME) != sid:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=sid,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            path="/",
        )
    return response


class StartScanRequest(BaseModel):
    country: str = Field(default="PL", description="Kod kraju: PL lub DE")
    city: str = Field(..., description="Nazwa miasta")
    vertical: str = Field(..., description="ID branży")
    radius: float = Field(default=15.0, ge=1.0, le=100.0, description="Promień w km")
    radius_km: Optional[float] = Field(default=None, ge=1.0, le=100.0, description="Alias dla promienia w km")
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
async def get_dashboard(request: Request, mgr: ScanManager = Depends(get_manager)):
    """Render main dashboard."""
    verticals = load_all_verticals()
    sid = get_session_id(request)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "version": "0.3.0",
            "session_id": sid,
            "verticals": list(verticals.values()),
            "initial_counts": mgr.counts,
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.3.0"}


@app.post("/api/session/reset")
async def reset_session(request: Request, mgr: ScanManager = Depends(get_manager)):
    """Reset current session workspace, wiping temporary files and clearing leads."""
    sid = get_session_id(request)
    session_registry.reset(sid)
    return {
        "status": "ok",
        "session_id": sid,
        "message": "Sesja została zresetowana.",
        "counts": mgr.counts,
    }


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
async def get_saved_scans(mgr: ScanManager = Depends(get_manager)):
    """List available scan files for this session."""
    return {"scans": mgr.list_saved_scans()}


@app.post("/api/scans/load")
async def load_saved_scan(req: LoadScanRequest, mgr: ScanManager = Depends(get_manager)):
    """Load a specific scan file into memory."""
    target_path = None
    if req.path:
        target_path = Path(req.path)
    elif req.filename:
        target_path = mgr.workspace_dir / req.filename
    else:
        target_path = mgr.workspace_dir / "leads.json"

    if not target_path or not target_path.is_file():
        raise HTTPException(status_code=404, detail=f"Plik '{target_path}' nie istnieje.")

    try:
        count = mgr.load_scan_file(target_path)
        return {"status": "ok", "loaded": count, "counts": mgr.counts}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Błąd odczytu pliku: {e}")


@app.post("/api/scan/start")
async def start_scan(
    req: StartScanRequest,
    request: Request,
    mgr: ScanManager = Depends(get_manager),
):
    """Start an asynchronous lead discovery scan."""
    client_ip = get_client_ip(request)

    # 1. Enforce Gemini rate limit if use_gemini is requested
    if req.use_gemini:
        allowed_gemini, retry_after_gemini = gemini_rate_limiter.check(client_ip)
        if not allowed_gemini:
            raise HTTPException(
                status_code=429,
                detail=f"Przekroczono limit zapytań Gemini AI (maksymalnie 1 użycie na minutę na adres IP). Spróbuj ponownie za {int(retry_after_gemini)} s.",
                headers={"Retry-After": str(int(retry_after_gemini))},
            )

    # 2. Enforce scan start rate limit (1 scan per minute per IP)
    allowed_scan, retry_after_scan = scan_rate_limiter.check(client_ip)
    if not allowed_scan:
        raise HTTPException(
            status_code=429,
            detail=f"Przekroczono limit uruchamiania skanowania (maksymalnie 1 na minutę na adres IP). Spróbuj ponownie za {int(retry_after_scan)} s.",
            headers={"Retry-After": str(int(retry_after_scan))},
        )

    country_norm = req.country.strip().upper()
    if country_norm not in ("PL", "DE"):
        raise HTTPException(status_code=400, detail="Kod kraju musi wynosić 'PL' lub 'DE'.")

    effective_radius = req.radius_km if req.radius_km is not None else req.radius
    started = await mgr.start_scan(
        country=country_norm,
        city=req.city,
        vertical_id=req.vertical,
        radius_km=effective_radius,
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
        "params": mgr.current_params,
        "message": mgr.message,
    }


@app.post("/api/scan/stop")
async def stop_scan(mgr: ScanManager = Depends(get_manager)):
    """Cancel the active scan."""
    stopped = await mgr.stop_scan()
    return {"stopped": stopped, "status": mgr.status}


@app.get("/api/scan/status")
async def get_scan_status(mgr: ScanManager = Depends(get_manager)):
    """Get current scan state, progress, logs, and counts."""
    return mgr.get_status_data()


@app.get("/api/scan/events")
async def stream_scan_events(request: Request, mgr: ScanManager = Depends(get_manager)):
    """SSE endpoint streaming live scan events (status, logs, leads, completion)."""
    queue = mgr.subscribe()

    async def event_generator():
        try:
            # Yield initial status immediately on connection
            init_event = {
                "type": "status",
                "status": mgr.status,
                "stage": mgr.stage,
                "progress": mgr.progress,
                "message": mgr.message,
                "counts": mgr.counts,
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
            mgr.unsubscribe(queue)

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
    mgr: ScanManager = Depends(get_manager),
):
    """Query currently loaded leads with search and verdict filters."""
    leads = mgr.get_leads(
        query=query,
        verdict=verdict,
        has_phone=has_phone,
        min_score=min_score,
    )
    return {
        "total": len(leads),
        "counts": mgr.counts,
        "leads": [lead.model_dump(mode="json") for lead in leads],
    }


@app.get("/api/export/{format_type}")
async def export_leads(
    format_type: str,
    query: Optional[str] = Query(None),
    verdict: Optional[str] = Query("all"),
    has_phone: bool = Query(False),
    min_score: int = Query(0),
    mgr: ScanManager = Depends(get_manager),
):
    """Export currently loaded / filtered leads into CSV, JSON, or HTML."""
    try:
        filtered_leads = mgr.get_leads(
            query=query,
            verdict=verdict,
            has_phone=has_phone,
            min_score=min_score,
        )
        content_bytes, media_type, filename = mgr.export_leads(format_type, filtered_leads)
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
    from wulf_web_leader.audit.gemini_verifier import is_gemini_available, DEFAULT_MODEL
    return {
        "available": is_gemini_available(),
        "model": DEFAULT_MODEL,
    }


@app.post("/api/leads/{source_id}/gemini-verify")
async def verify_lead_gemini_endpoint(
    source_id: str,
    request: Request,
    req: Optional[GeminiVerifyRequest] = None,
    mgr: ScanManager = Depends(get_manager),
):
    """Verify an individual lead in Google via Gemini API with live Search Grounding."""
    client_ip = get_client_ip(request)
    allowed, retry_after = gemini_rate_limiter.check(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Przekroczono limit zapytań Gemini AI (maksymalnie 1 użycie na minutę na adres IP). Spróbuj ponownie za {int(retry_after)} s.",
            headers={"Retry-After": str(int(retry_after))},
        )

    api_key = req.api_key if req else None
    if not api_key and request:
        api_key = request.headers.get("X-Gemini-Api-Key")

    lead = await mgr.verify_lead_gemini(source_id=source_id, api_key=api_key)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead o ID '{source_id}' nie został odnaleziony w pamięci.")

    return {
        "status": "ok",
        "lead": lead.model_dump(mode="json"),
        "gemini_intel": lead.gemini_intel.model_dump(mode="json") if lead.gemini_intel else None,
    }


@app.get("/audit-card", response_class=HTMLResponse)
async def get_client_audit_card(request: Request):
    """Serve printable client-facing technical audit sheet."""
    return templates.TemplateResponse(request=request, name="client_audit.html", context={})


@app.get("/demo/preview", response_class=HTMLResponse)
async def get_instant_demo_preview(request: Request):
    """Serve instant live demo concept for prospect's vertical."""
    return templates.TemplateResponse(request=request, name="instant_demo.html", context={})


@app.get("/api/speed")
async def get_speed_audit(url: str = Query(...)):
    """Run real-time speed and Core Web Vitals probe on website."""
    from wulf_web_leader.audit.speed import audit_website_speed
    result = audit_website_speed(url)
    return {"status": "ok", "speed": result}


@app.get("/api/revenue-loss")
async def get_revenue_loss(
    vertical: Optional[str] = Query(None),
    country: str = Query("PL"),
    has_website: bool = Query(True),
    is_https: bool = Query(True),
    has_viewport: bool = Query(True),
    load_time_seconds: Optional[float] = Query(None),
    http_error: bool = Query(False),
):
    """Calculate estimated business loss and lost customers from website defects."""
    from wulf_web_leader.score.revenue_calc import calculate_lost_revenue
    result = calculate_lost_revenue(
        vertical=vertical,
        country=country,
        has_website=has_website,
        is_https=is_https,
        has_viewport=has_viewport,
        load_time_seconds=load_time_seconds,
        http_error=http_error,
    )
    return {"status": "ok", "revenue_loss": result}

