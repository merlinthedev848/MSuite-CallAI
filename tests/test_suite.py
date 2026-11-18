import pytest
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from database import init_db, save_call_record, get_all_records, update_call_status, get_analytics_metrics, CallRecord
from knowledge_base import knowledge_base
from yeastar_client import yeastar_client
from notifications import CallerIntake, generate_email_html
from server import app

client = TestClient(app)

def test_database_crud():
    init_db()
    
    test_record = CallRecord(
        call_id="test-call-12345",
        caller_name="Alice Smith",
        caller_phone="+15551239999",
        caller_email="alice@example.com",
        company="Smith Enterprise",
        department="Technical Support",
        reason="VPN Outage",
        details="User is unable to access remote servers.",
        urgency="high",
        sentiment="frustrated",
        action_items=["Reset VPN credentials", "Check radius server logs"],
        tags=["#vpn", "#urgent"],
        preferred_callback_time="Immediate",
        duration_seconds=95,
        transcript="Caller: I can't log in.\nAssistant: I will log an urgent ticket for support.",
        ai_summary="VPN connectivity failure affecting remote user.",
        status="new"
    )

    rec_id = save_call_record(test_record)
    assert rec_id > 0

    # Query
    records = get_all_records(limit=10, search="VPN")
    assert any(r["call_id"] == "test-call-12345" for r in records)

    # Update status
    updated = update_call_status(record_id=rec_id, new_status="called_back", notes="Resolved by network team.")
    assert updated is True

    # Check analytics
    metrics = get_analytics_metrics()
    assert metrics["total_calls"] >= 1
    assert "high" in metrics["urgency_distribution"]


def test_knowledge_base():
    hours = knowledge_base.search_faq("what are your hours?")
    assert "8:30" in hours or "hours" in hours.lower()

    address = knowledge_base.search_faq("where is your office?")
    assert "Street" in address or "office" in address.lower()

    support_ext = knowledge_base.get_department_extension("Technical Support")
    assert support_ext == "1001"


@pytest.mark.asyncio
async def test_yeastar_client():
    status = await yeastar_client.get_extension_status("1000")
    assert status.get("status") in ("Idle", "Success")

    dial_res = await yeastar_client.originate_call(desk_extension="1000", destination_phone="+15551234567")
    assert dial_res.get("success") is True


def test_notification_html_rendering():
    intake = CallerIntake(
        caller_name="Mark Johnson",
        caller_phone="+1 (555) 777-8888",
        caller_email="mark@johnson.com",
        company="Johnson Co",
        department="Sales & Billing",
        reason="Contract Renewal",
        details="Wants pricing on 50 additional licenses.",
        urgency="medium",
        sentiment="positive",
        action_items=["Prepare quote", "Email revised SLA"],
        tags=["#sales", "#renewal"],
        ai_summary="Customer requested quote for 50 licenses.",
        transcript="Caller: I'd like to renew.\nAssistant: I've noted that down."
    )
    html = generate_email_html(intake)
    assert "Mark Johnson" in html
    assert "50 additional licenses" in html
    assert "Sales &amp; Billing" in html or "Sales & Billing" in html
    assert "Prepare quote" in html


def test_fastapi_endpoints():
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "html" in res_root.headers.get("content-type", "")

    res_calls = client.get("/api/calls")
    assert res_calls.status_code == 200
    assert isinstance(res_calls.json(), list)

    res_stats = client.get("/api/stats")
    assert res_stats.status_code == 200
    assert "total_calls" in res_stats.json()

    res_dial = client.post("/api/dial", json={"caller_phone": "+15551234567", "staff_extension": "1000"})
    assert res_dial.status_code == 200
    assert res_dial.json().get("success") is True

    res_csv = client.get("/api/export/csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers.get("content-type", "")
