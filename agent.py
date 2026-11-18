import asyncio
import logging
from typing import Annotated, Optional
import time

from dotenv import load_dotenv
load_dotenv()

from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, silero, openai

from config import config
from notifications import CallerIntake, dispatch_all_notifications
from knowledge_base import knowledge_base
from yeastar_client import yeastar_client

logger = logging.getLogger("phone_agent")


def get_llm():
    """Initializes LLM based on configured provider (Ollama, Groq, or OpenAI)."""
    if config.llm_provider == "ollama":
        logger.info(f"Using Local Ollama LLM: {config.ollama_model} at {config.ollama_base_url}")
        return openai.LLM(
            model=config.ollama_model,
            base_url=config.ollama_base_url,
            api_key="ollama"
        )
    elif config.llm_provider == "groq":
        logger.info(f"Using Groq LLM: {config.openai_model}")
        return openai.LLM(
            model=config.openai_model,
            base_url="https://api.groq.com/openai/v1",
            api_key=config.openai_api_key
        )
    else:
        logger.info(f"Using OpenAI LLM: {config.openai_model}")
        return openai.LLM(
            model=config.openai_model,
            api_key=config.openai_api_key
        )


def get_tts():
    """Initializes TTS based on configured provider (Cartesia or ElevenLabs)."""
    if config.tts_provider == "elevenlabs" and config.eleven_api_key:
        from livekit.plugins import elevenlabs
        logger.info(f"Using ElevenLabs TTS (voice: {config.eleven_voice_id})")
        return elevenlabs.TTS(api_key=config.eleven_api_key, voice_id=config.eleven_voice_id)
    else:
        from livekit.plugins import cartesia
        logger.info(f"Using Cartesia TTS (voice: {config.cartesia_voice_id})")
        return cartesia.TTS(api_key=config.cartesia_api_key, voice=config.cartesia_voice_id)


def build_system_prompt() -> str:
    return f"""You are the professional, friendly virtual AI receptionist for {config.company_name}.
Your mission is to answer incoming telephone calls warmly, answer common questions using your knowledge base, take thorough intake notes, and direct or transfer the caller appropriately.

### Persona & Style:
- Warm, articulate, concise, and calm.
- Speak naturally in short, friendly sentences. Avoid long paragraphs or bulleted lists because the caller is listening over a telephone line.
- Always ask only one question at a time so the caller is never overwhelmed.

### Key Objectives during the Phone Call:
1. Warm Greeting: Introduce yourself as the assistant for {config.company_name} and ask how you may assist them today.
2. Answering Questions: If they ask about services, hours, office location, or emergency procedures, use `search_knowledge_base`.
3. Intake Details (Crucial):
   - Caller Name
   - Best Callback Number (verify digits if needed)
   - Email Address (optional, ask if they'd like email confirmation)
   - Company or Organization (if calling on behalf of a business)
   - Specific Reason & Message Details
   - Urgency Level (Low, Normal, Urgent, or Emergency)
   - Preferred Callback Window (e.g. today before 2 PM, tomorrow morning)
4. Tool Usage:
   - Call `record_caller_identity` as soon as they give their name, phone, or email.
   - Call `record_inquiry_details` as soon as the issue and callback preference are understood.
   - If they specifically ask to speak with an operator or live department, call `transfer_call_to_staff`.
5. Confirmation & Goodbye:
   - Before ending, confirm the key details (e.g. "Thank you, [Name]. I have your number as [Phone] and your message regarding [Topic]. Our team will contact you [Timeframe].").
   - Wish them a pleasant day.

### Safety & Boundaries:
- Do not make binding commitments on pricing or exact contract terms without staff review.
- In life-safety situations, instruct the caller to hang up and dial 911 immediately.
"""


def create_tools(intake: CallerIntake) -> list:
    """Creates callable tools bound to the current call's intake record."""

    @llm.function_tool(description="Record or update the caller's identity and contact information.")
    def record_caller_identity(
        caller_name: Annotated[str, "Full name of the caller"],
        callback_phone: Annotated[str, "Callback telephone number provided by caller"],
        caller_email: Annotated[Optional[str], "Email address if provided"] = None,
        company: Annotated[Optional[str], "Company or organization name, if mentioned"] = None,
    ) -> str:
        intake.caller_name = caller_name
        intake.caller_phone = callback_phone
        if caller_email:
            intake.caller_email = caller_email
        if company:
            intake.company = company
        logger.info(f"Recorded identity: {caller_name} | {callback_phone} | {caller_email} | {company}")
        return f"Saved contact details for {caller_name} ({callback_phone})."

    @llm.function_tool(description="Record detailed notes about why the caller is reaching out.")
    def record_inquiry_details(
        reason: Annotated[str, "Short summary of why they called (e.g. Server Outage, Billing Question, Scheduling)"],
        detailed_notes: Annotated[str, "Detailed notes explaining their situation or request"],
        department: Annotated[str, "Department: Technical Support, Sales & Billing, Emergency Dispatch, or General"] = "General",
        urgency: Annotated[str, "Urgency level: low, medium, high, or emergency"] = "medium",
        preferred_callback_time: Annotated[Optional[str], "When the caller prefers to be called back"] = None,
    ) -> str:
        intake.reason = reason
        intake.details = detailed_notes
        intake.department = department
        intake.urgency = urgency
        if preferred_callback_time:
            intake.preferred_callback_time = preferred_callback_time
        logger.info(f"Recorded inquiry: {reason} | Dept: {department} | Urgency: {urgency}")
        return "Inquiry details successfully logged in the system."

    @llm.function_tool(description="Look up business answers, FAQ, company policies, hours, or office directions.")
    def search_knowledge_base(
        query: Annotated[str, "The question or topic to search (e.g., 'hours', 'billing policy', 'emergency protocol')"]
    ) -> str:
        answer = knowledge_base.search_faq(query)
        logger.info(f"Knowledge base query: '{query}' -> '{answer[:60]}...'")
        return answer

    @llm.function_tool(description="Transfer the caller to a live staff member, operator, or department extension on the Yeastar PBX.")
    async def transfer_call_to_staff(
        department_or_extension: Annotated[str, "Department name (e.g. 'Support', 'Sales', 'Emergency') or extension number (e.g. '1000')"],
        reason: Annotated[str, "Why the transfer is being initiated"]
    ) -> str:
        ext = department_or_extension
        if not ext.isdigit():
            ext = knowledge_base.get_department_extension(department_or_extension)
            
        logger.info(f"Live transfer requested to extension {ext}. Reason: {reason}")
        intake.details += f" [Caller requested transfer to ext {ext}: {reason}]"

        status_info = await yeastar_client.get_extension_status(ext)
        logger.info(f"Yeastar extension {ext} status: {status_info.get('status')}")

        return f"Please hold while I transfer you to extension {ext}."

    return [record_caller_identity, record_inquiry_details, search_knowledge_base, transfer_call_to_staff]


async def entrypoint(ctx: JobContext):
    logger.info(f"Connecting voice worker to room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    intake = CallerIntake(call_id=ctx.room.name)
    start_time = time.time()

    # Handle race condition: check if participant already connected before listener
    participant = next(iter(ctx.room.remote_participants.values()), None)
    if not participant:
        try:
            participant = await asyncio.wait_for(ctx.wait_for_participant(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning(f"No participant joined room {ctx.room.name} within 30s. Exiting.")
            return

    logger.info(f"Participant connected: identity={participant.identity}, name={participant.name}")

    # Extract SIP caller ID and metadata if present
    if participant.identity and (participant.identity.startswith("+") or participant.identity.isdigit()):
        intake.caller_phone = participant.identity

    if hasattr(participant, "attributes") and participant.attributes:
        sip_phone = participant.attributes.get("sip.phoneNumber")
        if sip_phone:
            intake.caller_phone = sip_phone

    # Initialize AI Components
    llm_instance = get_llm()
    stt_instance = deepgram.STT(api_key=config.deepgram_api_key)
    tts_instance = get_tts()
    vad_instance = silero.VAD.load()

    tools = create_tools(intake)

    agent = Agent(
        instructions=build_system_prompt(),
        tools=tools,
    )

    session = AgentSession(
        stt=stt_instance,
        llm=llm_instance,
        tts=tts_instance,
        vad=vad_instance,
        user_away_timeout=25.0,
    )

    # Start voice session in the room
    session.start(agent, room=ctx.room)

    # Greet the caller safely
    try:
        await session.say(
            f"Thank you for calling {config.company_name}. My name is your virtual assistant. How may I help you today?"
        )
    except Exception as e:
        logger.warning(f"Greeting could not be delivered (caller disconnected early): {e}")

    async def handle_call_ended():
        duration = int(time.time() - start_time)
        intake.call_duration_seconds = duration

        # Extract full conversation transcript reliably
        try:
            transcript_lines = []
            if hasattr(session, "history"):
                chat_ctx = session.history
                messages = getattr(chat_ctx, "messages", [])
                for msg in messages:
                    role = getattr(msg, "role", "unknown")
                    if role in ("user", "assistant"):
                        speaker = "Caller" if role == "user" else "Assistant"
                        text = getattr(msg, "text_content", None) or getattr(msg, "raw_text_content", None) or ""
                        if text:
                            transcript_lines.append(f"{speaker}: {text}")
            intake.transcript = "\n".join(transcript_lines)
        except Exception as e:
            logger.warning(f"Could not format transcript: {e}")

        logger.info(f"Call {ctx.room.name} ended. Duration: {duration}s. Triggering notification dispatch...")
        await dispatch_all_notifications(intake)

    @ctx.room.on("disconnected")
    def on_disconnected():
        logger.info(f"Room {ctx.room.name} disconnected.")
        asyncio.create_task(handle_call_ended())


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
