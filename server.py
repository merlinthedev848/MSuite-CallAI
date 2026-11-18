import csv
import io
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from database import get_all_records, update_call_status, init_db
from config import config

app = FastAPI(title="Phone AI Agent - Call Intake Dashboard")

init_db()

TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"

class StatusUpdateRequest(BaseModel):
    status: str # new, in_progress, called_back, archived
    notes: Optional[str] = None


@app.get("/api/calls")
def api_get_calls(status: Optional[str] = None, limit: int = 100):
    return get_all_records(limit=limit, status=status)


@app.post("/api/calls/{call_id}/status")
def api_update_status(call_id: int, req: StatusUpdateRequest):
    success = update_call_status(record_id=call_id, new_status=req.status, notes=req.notes)
    if not success:
        raise HTTPException(status_code=404, detail="Call record not found")
    return {"success": True, "call_id": call_id, "new_status": req.status}


@app.get("/api/stats")
def api_get_stats():
    records = get_all_records(limit=1000)
    total = len(records)
    new_count = sum(1 for r in records if r["status"] == "new")
    called_back = sum(1 for r in records if r["status"] == "called_back")
    urgent = sum(1 for r in records if r["urgency"] in ("high", "emergency") and r["status"] != "called_back")
    return {
        "total_calls": total,
        "pending_callbacks": new_count,
        "called_back": called_back,
        "urgent_pending": urgent
    }


@app.get("/api/export/csv")
def api_export_csv():
    records = get_all_records(limit=1000)
    output = io.StringIO()
    writer = csv.writer(output)
    
    headers = [
        "ID", "Timestamp", "Caller Name", "Phone", "Company",
        "Reason", "Urgency", "Callback Time", "Status", "Summary", "Notes"
    ]
    writer.writerow(headers)
    
    for r in records:
        writer.writerow([
            r["id"], r["created_at"], r["caller_name"], r["caller_phone"],
            r.get("company") or "", r["reason"], r["urgency"],
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
    return HTMLResponse(content=html_content)
