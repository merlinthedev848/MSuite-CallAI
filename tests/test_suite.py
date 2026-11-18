import pytest
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from database import (
    init_db,
    save_call_record,
    get_all_records,
    get_record_by_id,
    delete_call_record,
    update_call_status,
    get_analytics_metrics,
    CallRecord
)
from knowledge_base import knowledge_base
from yeastar_client import yeastar_client
from notifications import CallerIntake, generate_email_html
from server import app

client = TestClient(app)


def test_database_crud_and_migrations():
    init_db()

    test_record = CallRecord(
        call_id="test-audit-call-999",
        caller_name="Sarah Connor",
        caller_phone="+15559871234",
        caller_email="sarah@resistance.org",
        company="Cyberdyne Systems",
        department="Emergency Dispatch",
        reason="Server Perimeter Breach",
        details="Critical alert: automated defensive protocol triggered.",
        urgency="emergency",
        sentiment="urgent",
        action_items=["Isolate subnet 192.168.10.0/24", "Dispatch on-call engineer"],
        tags=["#security", "#emergency"],
        preferred_callback_time="Immediate",
        duration_seconds=120,
        transcript="Caller: We have a security alert.\nAssistant: Dispatching emergency response now.",
        ai_summary="Critical security incident reported.",
        status="new"
    )

    rec_id = save_call_record(test_record)
    assert rec_id > 0

    # Retrieve by ID
    single = get_record_by_id(rec_id)
    assert single is not None
    assert single["call_id"] == "test-audit-call-999"
    assert single["department"] == "Emergency Dispatch"
    assert len(single["action_items"]) == 2

    # Search
    search_results = get_all_records(search="Perimeter", limit=5)
    assert any(r["call_id"] == "test-audit-call-999" for r in search_results)

    # Status update
    updated = update_call_status(rec_id, "in_progress", "Contacting security lead.")
    assert updated is True

    # Invalid status rejection
    with pytest.raises(ValueError):
        update_call_status(rec_id, "unsupported_status")

    # Metrics
    metrics = get_analytics_metrics()
    assert metrics["total_calls"] >= 1
    assert "emergency" in metrics["urgency_distribution"]

    # Delete
    deleted = delete_call_record(rec_id)
    assert deleted is True
    assert get_record_by_id(rec_id) is None


def test_knowledge_base_lookups():
    hours = knowledge_base.search_faq("what are your hours of operation?")
    assert "8:30" in hours or "hours" in hours.lower()

    office = knowledge_base.search_faq("where is your office located?")
    assert "Street" in office or "office" in office.lower()

    billing_ext = knowledge_base.get_department_extension("Sales & Billing")
    assert billing_ext == "1002"


@pytest.mark.asyncio
async def test_yeastar_client_originate_and_presence():
    status = await yeastar_client.get_extension_status("1000")
    assert status.get("status") in ("Idle", "Success")

    dial = await yeastar_client.originate_call(desk_extension="1000", destination_phone="+1 (555) 333-4444")
    assert dial.get("success") is True
    assert dial.get("destination") == "+15553334444"


def test_email_html_structure():
    intake = CallerIntake(
        caller_name="David Miller",
        caller_phone="+1 (555) 444-5555",
        caller_email="david@miller.com",
        company="Miller Logistics",
        department="Technical Support",
        reason="Fleet Tracking Server Offline",
        details="GPS tracking server down for 45 vehicles.",
        urgency="high",
        sentiment="frustrated",
        action_items=["Restart telemetry service", "Inspect gateway firewall"],
        tags=["#telemetry", "#outage"],
        ai_summary="Fleet tracking downtime affecting 45 vehicles.",
        transcript="Caller: Tracking is down.\nAssistant: Logging urgent ticket."
    )
    html = generate_email_html(intake)
    assert "David Miller" in html
    assert "Fleet Tracking Server Offline" in html
    assert "Restart telemetry service" in html
    assert "#telemetry" in html


def test_api_endpoints_full_lifecycle():
    # 1. Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["database"] == "connected"

    # 2. Seed a test call
    test_record = CallRecord(
        call_id="api-test-call-001",
        caller_name="API Tester",
        caller_phone="+15550001111",
        reason="API Verification",
        details="Testing API lifecycle",
        urgency="low",
        status="new"
    )
    rec_id = save_call_record(test_record)

    # 3. Get single call
    res_get = client.get(f"/api/calls/{rec_id}")
    assert res_get.status_code == 200
    assert res_get.json()["caller_name"] == "API Tester"

    # 4. Update status valid
    res_up = client.post(f"/api/calls/{rec_id}/status", json={"status": "called_back", "notes": "Tested"})
    assert res_up.status_code == 200
    assert res_up.json()["new_status"] == "called_back"

    # 5. Update status invalid
    res_invalid = client.post(f"/api/calls/{rec_id}/status", json={"status": "not_a_valid_status"})
    assert res_invalid.status_code == 400

    # 6. Click to dial
    res_dial = client.post("/api/dial", json={"caller_phone": "+15550001111", "staff_extension": "1000"})
    assert res_dial.status_code == 200
    assert res_dial.json()["success"] is True

    # 7. Knowledge base API
    res_kb = client.get("/api/knowledge")
    assert res_kb.status_code == 200

    # 8. CSV Export
    res_csv = client.get("/api/export/csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]

    # 9. Delete call
    res_del = client.delete(f"/api/calls/{rec_id}")
    assert res_del.status_code == 200

    # Verify 404 on deleted
    res_404 = client.get(f"/api/calls/{rec_id}")
    assert res_404.status_code == 404
