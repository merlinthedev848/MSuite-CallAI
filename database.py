import sqlite3
import datetime
import json
import logging
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger("phone_agent.database")
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
    audio_url: Optional[str] = None
    transcript: Optional[str] = None
    ai_summary: Optional[str] = None
    status: str = "new"  # new, in_progress, called_back, archived
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def get_db_connection() -> sqlite3.Connection:
    """Creates a thread-safe connection configured with WAL journal mode and busy timeout."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes database schema and executes auto-migrations for schema additions."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS call_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT UNIQUE NOT NULL,
        caller_name TEXT NOT NULL,
        caller_phone TEXT NOT NULL,
        caller_email TEXT,
        company TEXT,
        department TEXT DEFAULT 'General',
        reason TEXT NOT NULL,
        details TEXT NOT NULL,
        urgency TEXT DEFAULT 'medium',
        sentiment TEXT DEFAULT 'neutral',
        action_items TEXT,
        tags TEXT,
        preferred_callback_time TEXT,
        duration_seconds INTEGER,
        audio_url TEXT,
        transcript TEXT,
        ai_summary TEXT,
        status TEXT DEFAULT 'new',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Auto-migration for schema enhancements
    cursor.execute("PRAGMA table_info(call_records);")
    existing_cols = [col["name"] for col in cursor.fetchall()]

    migrations = {
        "caller_email": "TEXT",
        "department": "TEXT DEFAULT 'General'",
        "sentiment": "TEXT DEFAULT 'neutral'",
        "action_items": "TEXT",
        "tags": "TEXT",
        "audio_url": "TEXT"
    }

    for col_name, col_type in migrations.items():
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE call_records ADD COLUMN {col_name} {col_type};")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON call_records(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_urgency ON call_records(urgency);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_department ON call_records(department);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON call_records(created_at);")
    conn.commit()
    conn.close()


def _format_row(row: sqlite3.Row) -> Dict[str, Any]:
    """Serializes database row into a dictionary with parsed JSON fields."""
    d = dict(row)
    if d.get("action_items"):
        try:
            d["action_items"] = json.loads(d["action_items"])
        except Exception:
            d["action_items"] = []
    else:
        d["action_items"] = []

    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
    else:
        d["tags"] = []

    return d


def save_call_record(record: CallRecord) -> int:
    """Inserts a new call or updates existing record on conflict, returning the row id."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    now = datetime.datetime.utcnow().isoformat()
    action_items_json = json.dumps(record.action_items) if record.action_items else None
    tags_json = json.dumps(record.tags) if record.tags else None

    cursor.execute("""
    INSERT INTO call_records (
        call_id, caller_name, caller_phone, caller_email, company, department,
        reason, details, urgency, sentiment, action_items, tags,
        preferred_callback_time, duration_seconds, audio_url, transcript,
        ai_summary, status, notes, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        audio_url=coalesce(excluded.audio_url, call_records.audio_url),
        transcript=excluded.transcript,
        ai_summary=excluded.ai_summary,
        updated_at=excluded.updated_at;
    """, (
        record.call_id, record.caller_name, record.caller_phone, record.caller_email,
        record.company, record.department, record.reason, record.details, record.urgency,
        record.sentiment, action_items_json, tags_json, record.preferred_callback_time,
        record.duration_seconds, record.audio_url, record.transcript, record.ai_summary,
        record.status, record.notes, now, now
    ))
    conn.commit()

    cursor.execute("SELECT id FROM call_records WHERE call_id = ?;", (record.call_id,))
    row = cursor.fetchone()
    row_id = row["id"] if row else cursor.lastrowid
    conn.close()
    return row_id


def get_record_by_id(record_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single record by primary key."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM call_records WHERE id = ?;", (record_id,))
    row = cursor.fetchone()
    conn.close()
    return _format_row(row) if row else None


def get_record_by_call_id(call_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single record by unique call identifier."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM call_records WHERE call_id = ?;", (call_id,))
    row = cursor.fetchone()
    conn.close()
    return _format_row(row) if row else None


def delete_call_record(record_id: int) -> bool:
    """Deletes a call record by primary key."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM call_records WHERE id = ?;", (record_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def _build_filter_query(
    status: Optional[str] = None,
    department: Optional[str] = None,
    urgency: Optional[str] = None,
    search: Optional[str] = None
) -> Tuple[str, List[Any]]:
    """Builds parameterized WHERE clauses with escaped LIKE wildcards."""
    where_clauses = ["1=1"]
    params = []

    if status and status.lower() != "all":
        where_clauses.append("status = ?")
        params.append(status.lower())

    if department and department.lower() != "all":
        where_clauses.append("department = ?")
        params.append(department)

    if urgency and urgency.lower() != "all":
        where_clauses.append("urgency = ?")
        params.append(urgency.lower())

    if search and search.strip():
        # Escape wildcards for safe LIKE query
        clean_search = (
            search.strip()
            .replace("/", "//")
            .replace("%", "/%")
            .replace("_", "/_")
        )
        like_pattern = f"%{clean_search}%"
        where_clauses.append("""(
            caller_name LIKE ? ESCAPE '/' OR 
            caller_phone LIKE ? ESCAPE '/' OR 
            caller_email LIKE ? ESCAPE '/' OR 
            company LIKE ? ESCAPE '/' OR 
            reason LIKE ? ESCAPE '/' OR 
            details LIKE ? ESCAPE '/' OR 
            transcript LIKE ? ESCAPE '/' OR 
            notes LIKE ? ESCAPE '/'
        )""")
        params.extend([like_pattern] * 8)

    return " AND ".join(where_clauses), params


def get_records_count(
    status: Optional[str] = None,
    department: Optional[str] = None,
    urgency: Optional[str] = None,
    search: Optional[str] = None
) -> int:
    """Calculates total matching records for accurate pagination."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    where_sql, params = _build_filter_query(status, department, urgency, search)
    query = f"SELECT COUNT(*) as total FROM call_records WHERE {where_sql};"
    cursor.execute(query, tuple(params))
    count = cursor.fetchone()["total"]
    conn.close()
    return count


def get_all_records(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    department: Optional[str] = None,
    urgency: Optional[str] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Retrieves paginated call records with filtering and text search."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    where_sql, params = _build_filter_query(status, department, urgency, search)
    query = f"SELECT * FROM call_records WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?;"
    params.extend([limit, offset])

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    results = [_format_row(row) for row in rows]
    conn.close()
    return results


def update_call_status(record_id: int, new_status: str, notes: Optional[str] = None) -> bool:
    """Updates the status and staff notes for a specific call record."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.datetime.utcnow().isoformat()

    valid_statuses = ("new", "in_progress", "called_back", "archived")
    if new_status.lower() not in valid_statuses:
        conn.close()
        raise ValueError(f"Invalid status '{new_status}'. Allowed: {valid_statuses}")

    if notes is not None:
        cursor.execute(
            "UPDATE call_records SET status = ?, notes = ?, updated_at = ? WHERE id = ?;",
            (new_status.lower(), notes, now, record_id)
        )
    else:
        cursor.execute(
            "UPDATE call_records SET status = ?, updated_at = ? WHERE id = ?;",
            (new_status.lower(), now, record_id)
        )

    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def get_analytics_metrics() -> Dict[str, Any]:
    """Calculates comprehensive real-time intake metrics and breakdowns."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as count FROM call_records;")
    total_calls = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM call_records WHERE status = 'new';")
    pending_callbacks = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM call_records WHERE status = 'called_back';")
    called_back = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM call_records WHERE urgency IN ('high', 'emergency') AND status != 'called_back';")
    urgent_pending = cursor.fetchone()["count"]

    cursor.execute("SELECT AVG(duration_seconds) as avg_duration FROM call_records WHERE duration_seconds IS NOT NULL AND duration_seconds > 0;")
    avg_dur = cursor.fetchone()["avg_duration"] or 0

    cursor.execute("SELECT urgency, COUNT(*) as count FROM call_records GROUP BY urgency;")
    urgency_counts = {r["urgency"]: r["count"] for r in cursor.fetchall()}

    cursor.execute("SELECT department, COUNT(*) as count FROM call_records GROUP BY department;")
    department_counts = {r["department"]: r["count"] for r in cursor.fetchall()}

    cursor.execute("SELECT sentiment, COUNT(*) as count FROM call_records GROUP BY sentiment;")
    sentiment_counts = {r["sentiment"]: r["count"] for r in cursor.fetchall()}

    conn.close()
    return {
        "total_calls": total_calls,
        "pending_callbacks": pending_callbacks,
        "called_back": called_back,
        "urgent_pending": urgent_pending,
        "avg_duration_seconds": int(round(avg_dur)),
        "urgency_distribution": urgency_counts,
        "department_distribution": department_counts,
        "sentiment_distribution": sentiment_counts
    }
