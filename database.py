import sqlite3
import datetime
import json
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel

DB_PATH = Path(__file__).parent / "calls.db"

class CallRecord(BaseModel):
    id: Optional[int] = None
    call_id: str
    caller_name: str
    caller_phone: str
    caller_email: Optional[str] = None
    company: Optional[str] = None
    department: Optional[str] = "General"
    reason: str
    details: str
    urgency: str = "medium"
    sentiment: Optional[str] = "neutral"
    action_items: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    preferred_callback_time: Optional[str] = None
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    status: str = "new" # new, in_progress, called_back, archived
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def init_db():
    """Initializes the SQLite database with full schema, automatic migrations, and indexes."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS call_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT UNIQUE,
        caller_name TEXT,
        caller_phone TEXT,
        caller_email TEXT,
        company TEXT,
        department TEXT DEFAULT 'General',
        reason TEXT,
        details TEXT,
        urgency TEXT,
        sentiment TEXT DEFAULT 'neutral',
        action_items TEXT,
        tags TEXT,
        preferred_callback_time TEXT,
        duration_seconds INTEGER,
        transcript TEXT,
        ai_summary TEXT,
        status TEXT DEFAULT 'new',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Automatic column migrations for existing databases
    cursor.execute("PRAGMA table_info(call_records)")
    columns = [col[1] for col in cursor.fetchall()]

    new_columns = {
        "caller_email": "TEXT",
        "department": "TEXT DEFAULT 'General'",
        "sentiment": "TEXT DEFAULT 'neutral'",
        "action_items": "TEXT",
        "tags": "TEXT"
    }

    for col_name, col_type in new_columns.items():
        if col_name not in columns:
            cursor.execute(f"ALTER TABLE call_records ADD COLUMN {col_name} {col_type}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON call_records(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_urgency ON call_records(urgency)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_department ON call_records(department)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON call_records(created_at)")
    conn.commit()
    conn.close()


def save_call_record(record: CallRecord) -> int:
    """Inserts or updates a call record."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.datetime.utcnow().isoformat()
    action_items_json = json.dumps(record.action_items) if record.action_items else None
    tags_json = json.dumps(record.tags) if record.tags else None

    cursor.execute("""
    INSERT INTO call_records (
        call_id, caller_name, caller_phone, caller_email, company, department,
        reason, details, urgency, sentiment, action_items, tags,
        preferred_callback_time, duration_seconds, transcript,
        ai_summary, status, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(call_id) DO UPDATE SET
        caller_name=excluded.caller_name,
        caller_phone=excluded.caller_phone,
        caller_email=excluded.caller_email,
        company=excluded.company,
        department=excluded.department,
        reason=excluded.reason,
        details=excluded.details,
        urgency=excluded.urgency,
        sentiment=excluded.sentiment,
        action_items=excluded.action_items,
        tags=excluded.tags,
        preferred_callback_time=excluded.preferred_callback_time,
        duration_seconds=excluded.duration_seconds,
        transcript=excluded.transcript,
        ai_summary=excluded.ai_summary,
        updated_at=excluded.updated_at
    """, (
        record.call_id, record.caller_name, record.caller_phone, record.caller_email,
        record.company, record.department, record.reason, record.details, record.urgency,
        record.sentiment, action_items_json, tags_json, record.preferred_callback_time,
        record.duration_seconds, record.transcript, record.ai_summary,
        record.status, record.notes, now, now
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_all_records(limit: int = 100, status: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves records ordered by most recent first, with optional status and text search."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM call_records WHERE 1=1"
    params = []

    if status and status != "all":
        query += " AND status = ?"
        params.append(status)

    if search:
        search_param = f"%{search.strip()}%"
        query += " AND (caller_name LIKE ? OR caller_phone LIKE ? OR company LIKE ? OR reason LIKE ? OR details LIKE ? OR transcript LIKE ?)"
        params.extend([search_param] * 6)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    results = []
    for row in rows:
        d = dict(row)
        if d.get("action_items"):
            try:
                d["action_items"] = json.loads(d["action_items"])
            except Exception:
                d["action_items"] = []
        if d.get("tags"):
            try:
                d["tags"] = json.loads(d["tags"])
            except Exception:
                d["tags"] = []
        results.append(d)

    conn.close()
    return results


def update_call_status(record_id: int, new_status: str, notes: Optional[str] = None) -> bool:
    """Updates status and staff notes."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()
    
    if notes is not None:
        cursor.execute("UPDATE call_records SET status = ?, notes = ?, updated_at = ? WHERE id = ?", (new_status, notes, now, record_id))
    else:
        cursor.execute("UPDATE call_records SET status = ?, updated_at = ? WHERE id = ?", (new_status, now, record_id))
        
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_analytics_metrics() -> Dict[str, Any]:
    """Computes high-level analytics for dashboard charts."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM call_records")
    total_calls = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM call_records WHERE status = 'new'")
    pending_callbacks = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM call_records WHERE status = 'called_back'")
    called_back = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM call_records WHERE urgency IN ('high', 'emergency') AND status != 'called_back'")
    urgent_pending = cursor.fetchone()["count"]

    cursor.execute("SELECT AVG(duration_seconds) as avg_duration FROM call_records WHERE duration_seconds IS NOT NULL")
    avg_dur = cursor.fetchone()["avg_duration"] or 0

    # Urgency breakdown
    cursor.execute("SELECT urgency, COUNT(*) as count FROM call_records GROUP BY urgency")
    urgency_counts = {r["urgency"]: r["count"] for r in cursor.fetchall()}

    # Department breakdown
    cursor.execute("SELECT department, COUNT(*) as count FROM call_records GROUP BY department")
    department_counts = {r["department"]: r["count"] for r in cursor.fetchall()}

    # Sentiment breakdown
    cursor.execute("SELECT sentiment, COUNT(*) as count FROM call_records GROUP BY sentiment")
    sentiment_counts = {r["sentiment"]: r["count"] for r in cursor.fetchall()}

    conn.close()
    return {
        "total_calls": total_calls,
        "pending_callbacks": pending_callbacks,
        "called_back": called_back,
        "urgent_pending": urgent_pending,
        "avg_duration_seconds": int(avg_dur),
        "urgency_distribution": urgency_counts,
        "department_distribution": department_counts,
        "sentiment_distribution": sentiment_counts
    }
