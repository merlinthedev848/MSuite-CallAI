import os
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


def _get_env_int(key: str, default: int) -> int:
    val = os.getenv(key, "").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key, "").strip().lower()
    if not val:
        return default
    return val in ("true", "1", "yes", "on")


class AppConfig(BaseModel):
    # Company Branding & Identity
    company_name: str = Field(default=os.getenv("COMPANY_NAME", "Acme Services").strip() or "Acme Services")
    company_phone: str = Field(default=os.getenv("COMPANY_PHONE", "+1 (555) 123-4567").strip() or "+1 (555) 123-4567")
    business_hours: str = Field(default=os.getenv("BUSINESS_HOURS", "Monday to Friday 8:30 AM - 5:30 PM EST").strip())
    office_address: str = Field(default=os.getenv("OFFICE_ADDRESS", "123 Main Street, Suite 400, New York, NY 10001").strip())

    # Security & API Protection
    api_auth_token: str = Field(default=os.getenv("API_AUTH_TOKEN", "").strip())
    cors_origins: List[str] = Field(
        default=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
    )

    # Yeastar S-Series (S100, S50, S20, S300) & P-Series PBX API
    yeastar_host: str = Field(default=os.getenv("YEASTAR_HOST", "192.168.1.100").strip() or "192.168.1.100")
    yeastar_port: int = Field(default=_get_env_int("YEASTAR_PORT", 8088))
    yeastar_username: str = Field(default=os.getenv("YEASTAR_USERNAME", "api_user").strip() or "api_user")
    yeastar_password: str = Field(default=os.getenv("YEASTAR_PASSWORD", "").strip())
    default_staff_extension: str = Field(default=os.getenv("DEFAULT_STAFF_EXTENSION", "1000").strip() or "1000")
    yeastar_outbound_prefix: str = Field(default=os.getenv("YEASTAR_OUTBOUND_PREFIX", "").strip())
    yeastar_auto_answer: bool = Field(default=_get_env_bool("YEASTAR_AUTO_ANSWER", True))

    # LiveKit Telephony / WebRTC
    livekit_url: str = Field(default=os.getenv("LIVEKIT_URL", "").strip())
    livekit_api_key: str = Field(default=os.getenv("LIVEKIT_API_KEY", "").strip())
    livekit_api_secret: str = Field(default=os.getenv("LIVEKIT_API_SECRET", "").strip())

    # Silence & DTMF Conversation Policies
    silence_timeout_seconds: float = Field(default=float(_get_env_int("SILENCE_TIMEOUT_SECONDS", 15)))
    max_silence_retries: int = Field(default=_get_env_int("MAX_SILENCE_RETRIES", 2))

    # Speech-to-Text (Deepgram Nova-2)
    deepgram_api_key: str = Field(default=os.getenv("DEEPGRAM_API_KEY", "").strip())

    # LLM Provider Configuration ('openai', 'ollama', or 'groq')
    llm_provider: str = Field(default=os.getenv("LLM_PROVIDER", "openai").strip().lower() or "openai")
    
    # OpenAI / Groq
    openai_api_key: str = Field(default=os.getenv("OPENAI_API_KEY", "").strip())
    openai_model: str = Field(default=os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini")
    
    # Local Ollama AI Engine
    ollama_base_url: str = Field(default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").strip() or "http://localhost:11434/v1")
    ollama_model: str = Field(default=os.getenv("OLLAMA_MODEL", "llama3.1").strip() or "llama3.1")
    ollama_timeout: int = Field(default=_get_env_int("OLLAMA_TIMEOUT", 12))
    use_ollama_for_post_call_summary: bool = Field(default=_get_env_bool("USE_OLLAMA_FOR_POST_CALL_SUMMARY", True))

    # Text-to-Speech (Cartesia Sonic or ElevenLabs)
    tts_provider: str = Field(default=os.getenv("TTS_PROVIDER", "cartesia").strip().lower() or "cartesia")
    cartesia_api_key: str = Field(default=os.getenv("CARTESIA_API_KEY", "").strip())
    cartesia_voice_id: str = Field(default=os.getenv("CARTESIA_VOICE_ID", "a0e99841-438c-4a64-b679-ae501e7d6091").strip())
    eleven_api_key: str = Field(default=os.getenv("ELEVEN_API_KEY", "").strip())
    eleven_voice_id: str = Field(default=os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM").strip())

    # Email Notifications (SMTP / TLS / SSL)
    email_enabled: bool = Field(default=_get_env_bool("EMAIL_NOTIFICATIONS_ENABLED", False))
    smtp_host: str = Field(default=os.getenv("SMTP_HOST", "smtp.gmail.com").strip() or "smtp.gmail.com")
    smtp_port: int = Field(default=_get_env_int("SMTP_PORT", 587))
    smtp_use_tls: bool = Field(default=_get_env_bool("SMTP_USE_TLS", True))
    smtp_user: str = Field(default=os.getenv("SMTP_USER", "").strip())
    smtp_password: str = Field(default=os.getenv("SMTP_PASSWORD", "").strip())
    notification_recipient_email: str = Field(default=os.getenv("NOTIFICATION_RECIPIENT_EMAIL", "").strip())
    notification_sender_email: str = Field(default=os.getenv("NOTIFICATION_SENDER_EMAIL", "ai-phone@example.com").strip() or "ai-phone@example.com")

    # SMS Notifications (Twilio)
    sms_enabled: bool = Field(default=_get_env_bool("SMS_NOTIFICATIONS_ENABLED", False))
    twilio_account_sid: str = Field(default=os.getenv("TWILIO_ACCOUNT_SID", "").strip())
    twilio_auth_token: str = Field(default=os.getenv("TWILIO_AUTH_TOKEN", "").strip())
    twilio_from_number: str = Field(default=os.getenv("TWILIO_FROM_NUMBER", "").strip())
    notification_recipient_phone: str = Field(default=os.getenv("NOTIFICATION_RECIPIENT_PHONE", "").strip())

    @property
    def is_cors_wildcard(self) -> bool:
        return "*" in self.cors_origins


config = AppConfig()
