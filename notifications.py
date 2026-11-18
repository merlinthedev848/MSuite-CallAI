import logging
import datetime
import json
from typing import Optional, List
from email.message import EmailMessage
import aiohttp
import aiosmtplib
from pydantic import BaseModel, Field
from config import config

logger = logging.getLogger("phone_agent.notifications")

class CallerIntake(BaseModel):
    caller_name: str = Field(default="Unknown Caller")
    caller_phone: str = Field(default="Not Provided")
    caller_email: Optional[str] = Field(default=None)
    company: Optional[str] = Field(default=None)
    department: Optional[str] = Field(default="General")
    reason: str = Field(default="General Inquiry")
    details: str = Field(default="No specific details recorded.")
    urgency: str = Field(default="medium") # low, medium, high, emergency
    sentiment: Optional[str] = Field(default="neutral") # positive, neutral, frustrated, angry
    action_items: Optional[List[str]] = Field(default_factory=list)
    tags: Optional[List[str]] = Field(default_factory=list)
    preferred_callback_time: Optional[str] = Field(default=None)
    call_duration_seconds: Optional[int] = Field(default=None)
    transcript: Optional[str] = Field(default=None)
    call_id: Optional[str] = Field(default=None)
    ai_summary: Optional[str] = Field(default=None)
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)


async def enrich_with_local_ollama(intake: CallerIntake) -> None:
    """
    Uses local Ollama AI with structured JSON mode to analyze the call transcript,
    extract key details, evaluate caller sentiment, generate an action checklist, and score urgency.
    """
    if not config.use_ollama_for_post_call_summary or not intake.transcript:
        return

    prompt = f"""You are an expert executive phone intake analyst. Analyze this call transcript between a virtual receptionist and a caller.

Transcript:
{intake.transcript}

Return a valid JSON object matching this schema:
{{
  "caller_name": "Full name or 'Unknown'",
  "caller_phone": "Phone number or 'Not Provided'",
  "caller_email": "Email address or null",
  "company": "Company or organization or null",
  "department": "Technical Support, Sales & Billing, Emergency Dispatch, or General",
  "reason": "Short summary of why they called",
  "executive_summary": "Crisp 2-sentence summary of the conversation and situation",
  "urgency": "low, medium, high, or emergency",
  "sentiment": "positive, neutral, frustrated, or angry",
  "action_items": ["Action item 1 for staff", "Action item 2 for staff"],
  "tags": ["#tag1", "#tag2"],
  "preferred_callback_time": "Time specified or null"
}}
"""
    endpoint = f"{config.ollama_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": config.ollama_model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "format": "json",
        "temperature": 0.1
    }

    try:
        logger.info(f"Connecting to local Ollama ({config.ollama_model}) at {endpoint} for structured analysis...")
        async with aiohttp.ClientSession() as session:
            async with session.post(endpoint, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    parsed = json.loads(content.strip())
                    
                    if intake.caller_name == "Unknown Caller" and parsed.get("caller_name"):
                        intake.caller_name = parsed["caller_name"]
                    if intake.caller_phone == "Not Provided" and parsed.get("caller_phone"):
                        intake.caller_phone = parsed["caller_phone"]
                    if not intake.caller_email and parsed.get("caller_email"):
                        intake.caller_email = parsed["caller_email"]
                    if not intake.company and parsed.get("company"):
                        intake.company = parsed["company"]
                    if parsed.get("department"):
                        intake.department = parsed["department"]
                    if parsed.get("executive_summary"):
                        intake.ai_summary = parsed["executive_summary"]
                    if parsed.get("urgency") in ("low", "medium", "high", "emergency"):
                        intake.urgency = parsed["urgency"]
                    if parsed.get("sentiment") in ("positive", "neutral", "frustrated", "angry"):
                        intake.sentiment = parsed["sentiment"]
                    if parsed.get("action_items") and isinstance(parsed["action_items"], list):
                        intake.action_items = parsed["action_items"]
                    if parsed.get("tags") and isinstance(parsed["tags"], list):
                        intake.tags = parsed["tags"]
                    if not intake.preferred_callback_time and parsed.get("preferred_callback_time"):
                        intake.preferred_callback_time = parsed["preferred_callback_time"]
                        
                    logger.info("Successfully completed local Ollama structured intelligence analysis.")
                else:
                    logger.warning(f"Ollama returned HTTP status {resp.status}. Using in-call captured fields.")
    except Exception as e:
        logger.info(f"Local Ollama analysis skipped or unavailable ({e}). Continuing with in-call fields.")


def generate_email_html(intake: CallerIntake) -> str:
    urgency_color = {
        "low": "#28a745",
        "medium": "#007bff",
        "high": "#fd7e14",
        "emergency": "#dc3545",
    }.get(intake.urgency.lower(), "#007bff")

    sentiment_badge = {
        "positive": '<span style="background-color: #d4edda; color: #155724; padding: 3px 8px; border-radius: 4px; font-size: 11px;">😊 Positive</span>',
        "neutral": '<span style="background-color: #e2e3e5; color: #383d41; padding: 3px 8px; border-radius: 4px; font-size: 11px;">😐 Neutral</span>',
        "frustrated": '<span style="background-color: #fff3cd; color: #856404; padding: 3px 8px; border-radius: 4px; font-size: 11px;">😤 Frustrated</span>',
        "angry": '<span style="background-color: #f8d7da; color: #721c24; padding: 3px 8px; border-radius: 4px; font-size: 11px;">😡 Urgent / Angry</span>'
    }.get(str(intake.sentiment).lower(), "")

    time_str = intake.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")

    ai_summary_box = ""
    if intake.ai_summary:
        ai_summary_box = f"""
        <div style="background-color: #f0f7ff; border-left: 4px solid #0066cc; padding: 14px 18px; margin: 16px 0; border-radius: 0 6px 6px 0;">
            <p style="margin: 0; font-size: 12px; font-weight: 700; color: #004c99; text-transform: uppercase;">Executive AI Summary (Ollama):</p>
            <p style="margin: 6px 0 0 0; font-size: 14px; color: #1e3a8a; line-height: 1.5;">{intake.ai_summary}</p>
        </div>
        """

    action_items_box = ""
    if intake.action_items:
        items_html = "".join([f"<li style='margin-bottom: 4px;'>{item}</li>" for item in intake.action_items])
        action_items_box = f"""
        <div style="background-color: #fff9db; border: 1px solid #ffe066; padding: 12px 18px; border-radius: 6px; margin: 16px 0;">
            <p style="margin: 0 0 6px 0; font-size: 12px; font-weight: 700; color: #856404; text-transform: uppercase;">Recommended Next Steps for Staff:</p>
            <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #533f03; line-height: 1.4;">
                {items_html}
            </ul>
        </div>
        """

    tags_html = ""
    if intake.tags:
        tags_badges = " ".join([f"<span style='background:#e9ecef;color:#495057;padding:2px 8px;border-radius:10px;font-size:11px;'>{t}</span>" for t in intake.tags])
        tags_html = f"<div style='margin-top: 12px;'>{tags_badges}</div>"

    transcript_html = ""
    if intake.transcript:
        escaped_transcript = intake.transcript.replace("\n", "<br>")
        transcript_html = f"""
        <div style="margin-top: 24px; border-top: 1px solid #e0e0e0; padding-top: 16px;">
            <h3 style="color: #333; margin-bottom: 8px;">Full Conversation Transcript</h3>
            <div style="background: #f8f9fa; border: 1px solid #eee; border-radius: 6px; padding: 14px; font-family: monospace; font-size: 13px; max-height: 350px; overflow-y: auto; line-height: 1.5; color: #444;">
                {escaped_transcript}
            </div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>New Phone Intake: {intake.caller_name}</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 24px;">
        <table align="center" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 620px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow: hidden;">
            <tr>
                <td style="background-color: #1a202c; padding: 20px 24px;">
                    <table width="100%">
                        <tr>
                            <td>
                                <h2 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 600;">{config.company_name} - Phone Intake</h2>
                                <span style="color: #cbd5e0; font-size: 12px;">Dept: {intake.department}</span>
                            </td>
                            <td align="right">
                                <span style="background-color: {urgency_color}; color: white; padding: 5px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; text-transform: uppercase;">
                                    {intake.urgency}
                                </span>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            <tr>
                <td style="padding: 24px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                        <span style="color: #718096; font-size: 13px;">Call received on <strong>{time_str}</strong></span>
                        {sentiment_badge}
                    </div>
                    
                    {ai_summary_box}
                    {action_items_box}

                    <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse: collapse; margin-top: 12px;">
                        <tr style="border-bottom: 1px solid #edf2f7;">
                            <td style="width: 32%; color: #718096; font-size: 13px; font-weight: 600;">CALLER NAME</td>
                            <td style="color: #1a202c; font-size: 15px; font-weight: 600;">{intake.caller_name}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #edf2f7;">
                            <td style="color: #718096; font-size: 13px; font-weight: 600;">PHONE NUMBER</td>
                            <td style="color: #1a202c; font-size: 15px;">
                                <a href="tel:{intake.caller_phone}" style="color: #0066cc; text-decoration: none; font-weight: 600;">{intake.caller_phone}</a>
                            </td>
                        </tr>
                        {f'<tr style="border-bottom: 1px solid #edf2f7;"><td style="color: #718096; font-size: 13px; font-weight: 600;">EMAIL</td><td style="color: #1a202c; font-size: 14px;"><a href="mailto:{intake.caller_email}">{intake.caller_email}</a></td></tr>' if intake.caller_email else ''}
                        {f'<tr style="border-bottom: 1px solid #edf2f7;"><td style="color: #718096; font-size: 13px; font-weight: 600;">COMPANY</td><td style="color: #1a202c; font-size: 14px;">{intake.company}</td></tr>' if intake.company else ''}
                        <tr style="border-bottom: 1px solid #edf2f7;">
                            <td style="color: #718096; font-size: 13px; font-weight: 600;">REASON FOR CALL</td>
                            <td style="color: #1a202c; font-size: 14px; font-weight: 600;">{intake.reason}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #edf2f7;">
                            <td style="color: #718096; font-size: 13px; font-weight: 600; vertical-align: top;">MESSAGE DETAILS</td>
                            <td style="color: #2d3748; font-size: 14px; line-height: 1.5;">{intake.details}</td>
                        </tr>
                        {f'<tr style="border-bottom: 1px solid #edf2f7;"><td style="color: #718096; font-size: 13px; font-weight: 600;">PREFERRED CALLBACK</td><td style="color: #1a202c; font-size: 14px;">{intake.preferred_callback_time}</td></tr>' if intake.preferred_callback_time else ''}
                        {f'<tr><td style="color: #718096; font-size: 13px; font-weight: 600;">DURATION</td><td style="color: #718096; font-size: 13px;">{intake.call_duration_seconds}s</td></tr>' if intake.call_duration_seconds else ''}
                    </table>

                    {tags_html}

                    <div style="margin-top: 24px; text-align: center;">
                        <a href="tel:{intake.caller_phone}" style="display: inline-block; background-color: #0066cc; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 600; padding: 10px 24px; border-radius: 6px;">
                            📞 Call Back Now
                        </a>
                    </div>

                    {transcript_html}
                </td>
            </tr>
            <tr>
                <td style="background-color: #f7fafc; padding: 14px 24px; text-align: center; border-top: 1px solid #edf2f7; color: #a0aec0; font-size: 12px;">
                    Automated voice intake powered by {config.company_name} AI Phone Agent
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


async def send_email_notification(intake: CallerIntake) -> bool:
    if not config.email_enabled:
        logger.info("Email notifications disabled in configuration.")
        return False

    if not config.smtp_user or not config.smtp_password or not config.notification_recipient_email:
        logger.warning("SMTP credentials or recipient email missing. Skipping email dispatch.")
        return False

    recipients = [r.strip() for r in config.notification_recipient_email.split(",") if r.strip()]
    if not recipients:
        return False

    msg = EmailMessage()
    urgency_tag = f"[{intake.urgency.upper()}] " if intake.urgency.lower() in ("high", "emergency") else ""
    msg["Subject"] = f"{urgency_tag}Phone Intake: {intake.caller_name} - {intake.reason}"
    msg["From"] = config.notification_sender_email
    msg["To"] = ", ".join(recipients)

    plain_text = f"""
New Phone Call Intake
Company: {config.company_name}
Department: {intake.department}
Urgency: {intake.urgency.upper()}
Caller Name: {intake.caller_name}
Phone: {intake.caller_phone}
Email: {intake.caller_email or 'N/A'}
Company/Org: {intake.company or 'N/A'}
Reason: {intake.reason}
Summary: {intake.ai_summary or intake.details}
Preferred Callback: {intake.preferred_callback_time or 'Anytime'}

Transcript:
{intake.transcript or 'No transcript available'}
    """
    msg.set_content(plain_text)
    msg.add_alternative(generate_email_html(intake), subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname=config.smtp_host,
            port=config.smtp_port,
            start_tls=config.smtp_use_tls,
            username=config.smtp_user,
            password=config.smtp_password,
        )
        logger.info(f"Email notification dispatched successfully to {recipients}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False


async def send_sms_notification(intake: CallerIntake) -> bool:
    if not config.sms_enabled:
        logger.info("SMS notifications disabled in configuration.")
        return False

    if not config.twilio_account_sid or not config.twilio_auth_token or not config.notification_recipient_phone:
        logger.warning("Twilio credentials or recipient phone missing. Skipping SMS dispatch.")
        return False

    try:
        from twilio.rest import Client
        client = Client(config.twilio_account_sid, config.twilio_auth_token)
        
        summary_text = intake.ai_summary or intake.details
        sms_body = (
            f"📞 New Intake [{intake.urgency.upper()}]\n"
            f"From: {intake.caller_name} ({intake.caller_phone})\n"
            f"Dept: {intake.department}\n"
            f"Summary: {summary_text[:110]}..."
        )

        message = client.messages.create(
            body=sms_body,
            from_=config.twilio_from_number,
            to=config.notification_recipient_phone,
        )
        logger.info(f"SMS notification sent. Twilio SID: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SMS notification: {e}")
        return False


async def dispatch_all_notifications(intake: CallerIntake):
    """Enriches with Ollama if configured, saves to SQLite DB, then dispatches alerts concurrently."""
    import asyncio
    from database import CallRecord, save_call_record
    
    # 1. Run local Ollama post-call analysis
    await enrich_with_local_ollama(intake)

    # 2. Persist in local SQLite database
    try:
        call_id = intake.call_id or f"call-{int(intake.timestamp.timestamp())}"
        db_record = CallRecord(
            call_id=call_id,
            caller_name=intake.caller_name,
            caller_phone=intake.caller_phone,
            caller_email=intake.caller_email,
            company=intake.company,
            department=intake.department,
            reason=intake.reason,
            details=intake.details,
            urgency=intake.urgency,
            sentiment=intake.sentiment,
            action_items=intake.action_items,
            tags=intake.tags,
            preferred_callback_time=intake.preferred_callback_time,
            duration_seconds=intake.call_duration_seconds,
            transcript=intake.transcript,
            ai_summary=intake.ai_summary,
            status="new"
        )
        save_call_record(db_record)
        logger.info(f"Saved call record {call_id} to database.")
    except Exception as e:
        logger.error(f"Failed to persist call record in database: {e}")

    # 3. Dispatch Email and SMS alerts concurrently
    results = await asyncio.gather(
        send_email_notification(intake),
        send_sms_notification(intake),
        return_exceptions=True
    )
    logger.info(f"Notifications dispatch completed. Results: {results}")
