import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class AppConfig(BaseModel):
    # Company
    company_name: str = Field(default=os.getenv("COMPANY_NAME", "Our Company"))
    company_phone: str = Field(default=os.getenv("COMPANY_PHONE", ""))
    business_hours: str = Field(default=os.getenv("BUSINESS_HOURS", "Monday to Friday 9:00 AM - 5:00 PM"))
    office_address: str = Field(default=os.getenv("OFFICE_ADDRESS", "Main Office"))

    # Yeastar S100 / PBX API Settings
    yeastar_host: str = Field(default=os.getenv("YEASTAR_HOST", "192.168.1.100"))
    yeastar_port: int = Field(default=int(os.getenv("YEASTAR_PORT", "8088")))
    yeastar_username: str = Field(default=os.getenv("YEASTAR_USERNAME", "api_user"))
    yeastar_password: str = Field(default=os.getenv("YEASTAR_PASSWORD", ""))
    default_staff_extension: str = Field(default=os.getenv("DEFAULT_STAFF_EXTENSION", "1000"))

    # LiveKit
    livekit_url: str = Field(default=os.getenv("LIVEKIT_URL", ""))
    livekit_api_key: str = Field(default=os.getenv("LIVEKIT_API_KEY", ""))
    livekit_api_secret: str = Field(default=os.getenv("LIVEKIT_API_SECRET", ""))

    # Deepgram
    deepgram_api_key: str = Field(default=os.getenv("DEEPGRAM_API_KEY", ""))

    # LLM Settings (Supports Ollama, OpenAI, Groq)
    llm_provider: str = Field(default=os.getenv("LLM_PROVIDER", "openai").lower())
    
    # OpenAI / Groq
    openai_api_key: str = Field(default=os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = Field(default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    
    # Ollama (Local / Internal AI)
    ollama_base_url: str = Field(default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"))
    ollama_model: str = Field(default=os.getenv("OLLAMA_MODEL", "llama3.1"))
    use_ollama_for_post_call_summary: bool = Field(default=os.getenv("USE_OLLAMA_FOR_POST_CALL_SUMMARY", "true").lower() in ("true", "1", "yes"))

    # TTS
    tts_provider: str = Field(default=os.getenv("TTS_PROVIDER", "cartesia").lower())
    cartesia_api_key: str = Field(default=os.getenv("CARTESIA_API_KEY", ""))
    cartesia_voice_id: str = Field(default=os.getenv("CARTESIA_VOICE_ID", "a0e99841-438c-4a64-b679-ae501e7d6091"))
    eleven_api_key: str = Field(default=os.getenv("ELEVEN_API_KEY", ""))
    eleven_voice_id: str = Field(default=os.getenv("ELEVEN_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"))

    # Email
    email_enabled: bool = Field(default=os.getenv("EMAIL_NOTIFICATIONS_ENABLED", "false").lower() in ("true", "1", "yes"))
    smtp_host: str = Field(default=os.getenv("SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = Field(default=int(os.getenv("SMTP_PORT", "587")))
    smtp_use_tls: bool = Field(default=os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes"))
    smtp_user: str = Field(default=os.getenv("SMTP_USER", ""))
    smtp_password: str = Field(default=os.getenv("SMTP_PASSWORD", ""))
    notification_recipient_email: str = Field(default=os.getenv("NOTIFICATION_RECIPIENT_EMAIL", ""))
    notification_sender_email: str = Field(default=os.getenv("NOTIFICATION_SENDER_EMAIL", "ai-phone@example.com"))

    # SMS
    sms_enabled: bool = Field(default=os.getenv("SMS_NOTIFICATIONS_ENABLED", "false").lower() in ("true", "1", "yes"))
    twilio_account_sid: str = Field(default=os.getenv("TWILIO_ACCOUNT_SID", ""))
    twilio_auth_token: str = Field(default=os.getenv("TWILIO_AUTH_TOKEN", ""))
    twilio_from_number: str = Field(default=os.getenv("TWILIO_FROM_NUMBER", ""))
    notification_recipient_phone: str = Field(default=os.getenv("NOTIFICATION_RECIPIENT_PHONE", ""))

config = AppConfig()
