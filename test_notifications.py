import asyncio
import logging
from notifications import CallerIntake, dispatch_all_notifications

logging.basicConfig(level=logging.INFO)

async def test():
    print("Testing notification pipeline with sample intake record...")
    
    sample_intake = CallerIntake(
        caller_name="Jane Doe",
        caller_phone="+1 (555) 345-6789",
        company="Pinnacle Tech Solutions",
        reason="Server Maintenance Contract Inquiry",
        details="Caller is requesting an urgent consultation regarding maintenance SLA contracts for 15 servers. Needs a call back by 2 PM EST.",
        urgency="high",
        preferred_callback_time="Today before 2:00 PM EST",
        call_duration_seconds=142,
        transcript="""Assistant: Thank you for calling Acme Services. How may I help you today?
Caller: Hi, I'm Jane Doe from Pinnacle Tech Solutions. We need pricing for urgent server maintenance support.
Assistant: I would be happy to help you with that, Jane. Could you give me the best callback number for you?
Caller: Sure, it's 555-345-6789.
Assistant: Got it. And what is your preferred callback time?
Caller: Today before 2 PM if possible, it's pretty urgent.
Assistant: Perfect. I've logged your request with high priority and someone will call you back before 2 PM. Thank you!"""
    )

    await dispatch_all_notifications(sample_intake)
    print("Notification test completed.")

if __name__ == "__main__":
    asyncio.run(test())
