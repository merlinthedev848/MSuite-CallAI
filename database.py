import sqlite3
import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel

DB_PATH = Path(__file__).parent / "calls.db"

class CallRecord(BaseModel):
    id: Optional[int] = None
    call_id: str
    caller_name: str
    caller_phone: str
    company: Optional[str] = None
    reason: str
    details: str
    urgency: str
    preferred_callback_time: Optional[str] = None
    duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    status: str = "new" # new, in_progress, called_back, archived
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def init_db():
    """Initializes the SQLite database schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS call_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT UNIQUE,
        caller_name TEXT,
        caller_phone TEXT,
        company TEXT,
        reason TEXT,
        details TEXT,
        urgency TEXT,
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON call_records(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_urgency ON call_records(urgency)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON call_records(created_at)")
    conn.commit()
    conn.close()


def save_call_record(record: CallRecord) -> int:
    """Inserts or updates a call record."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.datetime.utcnow().isoformat()
    cursor.execute("""
    INSERT INTO call_records (
        call_id, caller_name, caller_phone, company, reason, details,
        urgency, preferred_callback_time, duration_seconds, transcript,
        ai_summary, status, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(call_id) DO UPDATE SET
        caller_name=excluded.caller_name,
        caller_phone=excluded.caller_phone,
        company=excluded.company,
        reason=excluded.reason,
        details=excluded.details,
        urgency=excluded.urgency,
        preferred_callback_time=excluded.preferred_callback_time,
        duration_seconds=excluded.duration_seconds,
        transcript=excluded.transcript,
        ai_summary=excluded.ai_summary,
        updated_at=excluded.updated_at
    """, (
        record.call_id, record.caller_name, record.caller_phone, record.company,
        record.reason, record.details, record.urgency, record.preferred_callback_time,
        record.duration_seconds, record.transcript, record.ai_summary,
        record.status, record.notes, now, now
    ))
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_all_records(limit: int = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves records ordered by most recent first."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if status:
        cursor.execute("SELECT * FROM call_records WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, limit))
    else:
        cursor.execute("SELECT * FROM call_records ORDER BY created_at DESC LIMIT ?", (limit,))
        
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results


def update_call_status(record_id: int, new_status: str, notes: Optional[str] = None) -> bool:
    """Updates status (e.g. 'called_back') and staff notes."""
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
