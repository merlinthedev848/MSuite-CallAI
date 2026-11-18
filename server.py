import csv
import io
import json
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from database import (
    get_all_records,
    get_records_count,
    get_record_by_id,
    delete_call_record,
    update_call_status,
    get_analytics_metrics,
    init_db
)
from config import config
from yeastar_client import yeastar_client
from knowledge_base import knowledge_base, KNOWLEDGE_PATH

logger = logging.getLogger("phone_agent.server")

app = FastAPI(
    title="Phone AI Agent - Call Intake & Dispatch Hub",
    description="Enterprise-grade real-time voice receptionist and PBX dispatch API",
    version="1.2.0"
)

# Robust CORS policy configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=not config.is_cors_wildcard,  # True credentials disallowed with wildcard '*'
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"

# In-memory click-to-dial rate limiter
_last_dial_times: Dict[str, float] = {}


class ConnectionManager:
    """Manages active WebSockets for instant live dashboard streaming."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Active: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


ws_manager = ConnectionManager()


class StatusUpdateRequest(BaseModel):
    status: str = Field(description="Allowed: new, in_progress, called_back, archived")
    notes: Optional[str] = Field(default=None, description="Optional internal notes by staff")


class ClickToDialRequest(BaseModel):
    caller_phone: str = Field(description="Destination telephone number to dial")
    staff_extension: Optional[str] = Field(default=None, description="PBX desk extension to ring")


@app.get("/health")
async def health_check():
    """System health check reporting database and Ollama status."""
    db_ok = False
    try:
        init_db()
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "llm_provider": config.llm_provider,
        "yeastar_host": config.yeastar_host,
        "active_websockets": len(ws_manager.active_connections)
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@app.get("/api/calls")
def api_get_calls(
    status: Optional[str] = Query(None, description="Filter by status: new, in_progress, called_back, archived"),
    department: Optional[str] = Query(None, description="Filter by department"),
    urgency: Optional[str] = Query(None, description="Filter by urgency: low, medium, high, emergency"),
    search: Optional[str] = Query(None, description="Text search across caller, notes, transcript"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=200, description="Items per page")
):
    offset = (page - 1) * page_size
    items = get_all_records(
        limit=page_size,
        offset=offset,
        status=status,
        department=department,
        urgency=urgency,
        search=search
    )
    total_count = get_records_count(
        status=status,
        department=department,
        urgency=urgency,
        search=search
    )
    total_pages = max(1, (total_count + page_size - 1) // page_size)

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }


@app.get("/api/calls/{call_id}")
def api_get_single_call(call_id: int):
    record = get_record_by_id(call_id)
    if not record:
        raise HTTPException(status_code=404, detail="Call record not found")
    return record


@app.delete("/api/calls/{call_id}")
async def api_delete_call(call_id: int):
    success = delete_call_record(call_id)
    if not success:
        raise HTTPException(status_code=404, detail="Call record not found")

    await ws_manager.broadcast({"event": "call_deleted", "call_id": call_id})
    return {"success": True, "deleted_id": call_id}


@app.post("/api/calls/{call_id}/status")
async def api_update_status(call_id: int, req: StatusUpdateRequest):
    valid_statuses = ("new", "in_progress", "called_back", "archived")
    if req.status.lower() not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{req.status}'. Must be one of {valid_statuses}"
        )

    success = update_call_status(record_id=call_id, new_status=req.status, notes=req.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Call record not found")

    await ws_manager.broadcast({
        "event": "status_updated",
        "call_id": call_id,
        "status": req.status.lower()
    })
    return {"success": True, "call_id": call_id, "new_status": req.status.lower()}


@app.post("/api/dial")
async def api_click_to_dial(req: ClickToDialRequest):
    """Triggers Yeastar S100 to ring staff desk phone and bridge to caller with throttling."""
    ext = req.staff_extension or config.default_staff_extension
    now = time.time()
    last_time = _last_dial_times.get(ext, 0.0)

    # Throttle: at least 2 seconds between dials per extension
    if now - last_time < 2.0:
        raise HTTPException(status_code=429, detail="Dialing throttled. Please wait 2 seconds between calls.")

    _last_dial_times[ext] = now
    result = await yeastar_client.originate_call(desk_extension=ext, destination_phone=req.caller_phone)
    return result


@app.post("/api/webhook/yeastar")
async def api_yeastar_webhook(request: Request):
    """Receives event notifications (inbound, CDR, hangup) from Yeastar S100."""
    try:
        body = await request.json()
        logger.info(f"Received Yeastar Webhook event: {body}")
        await ws_manager.broadcast({"event": "yeastar_event", "data": body})
        return {"status": "received"}
    except Exception as e:
        logger.warning(f"Error processing Yeastar webhook: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/api/stats")
def api_get_stats():
    return get_analytics_metrics()


@app.get("/api/knowledge")
def api_get_knowledge():
    return knowledge_base.data


@app.post("/api/knowledge")
def api_save_knowledge(data: Dict[str, Any]):
    try:
        KNOWLEDGE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        knowledge_base.load()
        return {"success": True, "message": "Knowledge base updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/csv")
def api_export_csv():
    records = get_all_records(limit=5000)
    output = io.StringIO()
    writer = csv.writer(output)
    
    headers = [
        "ID", "Timestamp", "Caller Name", "Phone", "Email", "Company", "Department",
        "Reason", "Urgency", "Sentiment", "Callback Time", "Status", "Summary", "Notes"
    ]
    writer.writerow(headers)
    
    for r in records:
        writer.writerow([
            r["id"], r["created_at"], r["caller_name"], r["caller_phone"],
            r.get("caller_email") or "", r.get("company") or "", r.get("department") or "",
            r["reason"], r["urgency"], r.get("sentiment") or "",
            r.get("preferred_callback_time") or "", r["status"],
            r.get("ai_summary") or r.get("details") or "", r.get("notes") or ""
        ])
        
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=phone_intake_records.csv"}
    )


@app.get("/", response_class=HTMLResponse)
def dashboard_html():
    if not TEMPLATE_PATH.exists():
        return HTMLResponse("<h1>Dashboard template not found</h1>", status_code=500)
    html_content = TEMPLATE_PATH.read_text(encoding="utf-8")
    html_content = html_content.replace("{{COMPANY_NAME}}", config.company_name)
    html_content = html_content.replace("{{DEFAULT_STAFF_EXT}}", config.default_staff_extension)
    return HTMLResponse(content=html_content)
