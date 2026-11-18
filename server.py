import csv
import io
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from database import get_all_records, update_call_status, get_analytics_metrics, init_db
from config import config
from yeastar_client import yeastar_client
from knowledge_base import knowledge_base, KNOWLEDGE_PATH

app = FastAPI(title="Phone AI Agent - Call Intake & Dispatch Hub")

init_db()

TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"


class ConnectionManager:
    """Manages active WebSockets for instant live dashboard streaming."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


ws_manager = ConnectionManager()


class StatusUpdateRequest(BaseModel):
    status: str # new, in_progress, called_back, archived
    notes: Optional[str] = None


class ClickToDialRequest(BaseModel):
    caller_phone: str
    staff_extension: Optional[str] = None


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keepalive listener
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@app.get("/api/calls")
def api_get_calls(status: Optional[str] = None, search: Optional[str] = None, limit: int = 100):
    return get_all_records(limit=limit, status=status, search=search)


@app.post("/api/calls/{call_id}/status")
async def api_update_status(call_id: int, req: StatusUpdateRequest):
    success = update_call_status(record_id=call_id, new_status=req.status, notes=req.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Call record not found")

    # Broadcast update to all live dashboards
    await ws_manager.broadcast({"event": "status_updated", "call_id": call_id, "status": req.status})
    return {"success": True, "call_id": call_id, "new_status": req.status}


@app.post("/api/dial")
async def api_click_to_dial(req: ClickToDialRequest):
    """Triggers Yeastar S100 to ring staff desk phone and connect to customer."""
    ext = req.staff_extension or config.default_staff_extension
    result = await yeastar_client.originate_call(desk_extension=ext, destination_phone=req.caller_phone)
    return result


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
    records = get_all_records(limit=1000)
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
