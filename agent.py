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

# Configure logging
logging.basicConfig(level=logging.INFO)
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
    return f"""You are the friendly, professional AI voice receptionist for {config.company_name}.
Your job is to answer incoming phone calls warmly, assist callers with basic questions, and take detailed intake information so our team can follow up promptly.

### Personality & Tone:
- Warm, polite, concise, and conversational.
- Speak in natural spoken English with short, friendly sentences (since this is an audio phone call, avoid long monologues or lists).
- Listen carefully and ask clarifying questions one at a time. Do not overwhelm the caller.

### Key Objectives during the Call:
1. Greeting: Introduce yourself as the virtual assistant for {config.company_name} and ask how you can help.
2. Information Intake (Mandatory):
   - Ask for their Full Name.
   - Ask for the Best Callback Phone Number.
   - Ask for their Company or Organization (if applicable).
   - Get the specific details of their request or message.
   - Ask how urgent this matter is (Low, Normal, or Urgent).
   - Ask what time is best for our team to call them back.
3. Record Info: As soon as the caller provides these details, call the `record_caller_identity` and `record_inquiry_details` tools.
4. Confirmation: Briefly confirm the key details before hanging up (e.g., "Got it, [Name]. I have your callback number as [Phone], and I've noted that you need help with [Topic]. We'll be in touch [Timeframe].").
5. Closing: Thank them warmly for calling {config.company_name} and wish them a wonderful day.

### Safety & Guardrails:
- Never make binding promises regarding pricing, contracts, or specific guarantees.
- If it's a life-threatening emergency, advise them to hang up and call 911 immediately.
"""


def create_tools(intake: CallerIntake) -> list:
    """Creates callable tools bound to the current call's intake record."""

    @llm.function_tool(description="Record or update the caller's identity and contact information.")
    def record_caller_identity(
        caller_name: Annotated[str, "Full name of the caller"],
        callback_phone: Annotated[str, "Callback phone number provided by the caller"],
        company: Annotated[Optional[str], "Company or organization name, if mentioned"] = None,
    ) -> str:
        intake.caller_name = caller_name
        intake.caller_phone = callback_phone
        if company:
            intake.company = company
        logger.info(f"Recorded identity: {caller_name} | {callback_phone} | {company}")
        return f"Saved caller details for {caller_name} ({callback_phone})."

    @llm.function_tool(description="Record detailed information about the caller's inquiry, problem, or request.")
    def record_inquiry_details(
        reason: Annotated[str, "Short summary of why they are calling (e.g., Billing Inquiry, Scheduling, Urgent Repair)"],
        detailed_notes: Annotated[str, "Detailed notes explaining their situation or specific request"],
        urgency: Annotated[str, "Urgency level: low, medium, high, or emergency"] = "medium",
        preferred_callback_time: Annotated[Optional[str], "When the caller would like to be reached back"] = None,
    ) -> str:
        intake.reason = reason
        intake.details = detailed_notes
        intake.urgency = urgency
        if preferred_callback_time:
            intake.preferred_callback_time = preferred_callback_time
        logger.info(f"Recorded inquiry: {reason} | Urgency: {urgency} | Callback: {preferred_callback_time}")
        return "Inquiry details successfully recorded."

    @llm.function_tool(description="Look up business information such as hours, office address, or phone number.")
    def check_business_info(
        query_type: Annotated[str, "Type of info needed: 'hours', 'address', 'phone', or 'general'"]
    ) -> str:
        q = query_type.lower()
        if "hour" in q:
            return f"Business hours are {config.business_hours}."
        elif "addr" in q or "locat" in q:
            return f"The office address is {config.office_address}."
        elif "phone" in q:
            return f"Our main office number is {config.company_phone}."
        else:
            return (
                f"{config.company_name} is located at {config.office_address}. "
                f"Hours: {config.business_hours}. Phone: {config.company_phone}."
            )

    return [record_caller_identity, record_inquiry_details, check_business_info]


async def entrypoint(ctx: JobContext):
    logger.info(f"Connecting to room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Initialize caller intake container
    intake = CallerIntake(call_id=ctx.room.name)
    start_time = time.time()

    # Wait for the caller participant to connect
    participant = await ctx.wait_for_participant()
    logger.info(f"Caller connected: identity={participant.identity}, name={participant.name}")

    if participant.identity and participant.identity.startswith("+"):
        intake.caller_phone = participant.identity

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
    )

    # Start voice session in the room
    session.start(agent, room=ctx.room)

    # Greet the caller
    await session.say(
        f"Thank you for calling {config.company_name}. My name is your virtual assistant. How may I help you today?"
    )

    async def handle_call_ended():
        duration = int(time.time() - start_time)
        intake.call_duration_seconds = duration

        # Extract transcript from session history if available
        try:
            transcript_lines = []
            if hasattr(session, "history"):
                for item in session.history:
                    role = getattr(item, "role", None) or "speaker"
                    text = getattr(item, "text", "") or getattr(item, "content", "")
                    if text:
                        transcript_lines.append(f"{role.capitalize()}: {text}")
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
