# Phone AI Voice Agent (Real-Time VoIP / PBX & SIP Integration)

A real-time, low-latency conversational AI agent designed to answer incoming phone calls from any VoIP / PBX system (Asterisk, FreePBX, 3CX, RingCentral, or SIP trunks), converse naturally with callers, take down detailed information, and immediately dispatch alerts via Email and SMS.

---

## 🌟 Key Features

- **Sub-Second Latency & Natural Voice**: Uses streaming STT (Deepgram), fast LLM inference (Gemini / OpenAI / Groq), and natural streaming TTS (Cartesia / ElevenLabs) with interruptibility (barge-in support).
- **Local AI / Ollama Processing**: Support for your local Ollama server (e.g. `llama3.1`, `qwen2.5`, `mistral`) for both **real-time voice conversation** and **post-call private transcript synthesis**, sentiment evaluation, and action item extraction.
- **Universal PBX & Yeastar S100 Native Integration**: Works with **Yeastar S100 / S-Series & P-Series**, FreePBX, 3CX, Grandstream, and features **Yeastar Click-to-Dial** directly from the web dashboard.
- **Dynamic Knowledge Base**: Answers caller questions about business hours, office directions, pricing policies, and department routing.
- **Live WebSocket Dashboard**: Real-time push updates to staff screens, interactive analytics charts, and call status management (`new`, `in_progress`, `called_back`, `archived`).
- **Comprehensive Automated Test Suite**: Full test coverage with `pytest` and `pytest-asyncio`.
- **Detailed Intake & Function Calling**: Dynamically extracts caller name, callback number, reason for call, message details, urgency level, and preferred callback time.
- **Instant Dispatch**: Automatically sends beautiful HTML summaries and full transcripts via Email (SMTP / Resend / SendGrid) and instant SMS alerts to your team.
- **Local Dev Playground**: Test the agent directly from your microphone and web browser before connecting your phone lines.

---

## 📁 Project Structure

```
phone-ai-agent/
├── agent.py               # Main real-time voice agent with function calling & intake logic
├── notifications.py       # Email (HTML / SMTP / Resend) & SMS (Twilio) notification dispatcher
├── server.py              # FastAPI web dashboard and REST API
├── database.py            # SQLite CDR database operations and schemas
├── templates/
│   └── dashboard.html     # Responsive real-time call intake dashboard UI
├── config.py              # Configuration & environment variable validation
├── yeastar_setup.md       # Dedicated Yeastar S100 / S-Series & P-Series integration guide
├── sip_setup.md           # Universal Multi-PBX integration guide (FreePBX, 3CX, Grandstream, etc.)
├── pbx_profiles.json      # Pre-tuned configurations for Yeastar, Grandstream, FreePBX, etc.
├── sip_dispatch.json      # LiveKit SIP dispatch rules for routing PBX calls to agent
├── test_notifications.py  # Test script for email/SMS alert verification
├── Dockerfile             # Production container definition
├── docker-compose.yml     # Multi-service deployment compose file
├── pyproject.toml         # Dependencies and project metadata
├── .env.example           # Environment template
└── README.md              # Quickstart guide
```

---

## 🖥️ Web Dashboard

Start the web dashboard to monitor calls and manage callbacks:

```powershell
uv run uvicorn server:app --reload --port 8000
```

Open your browser to `http://localhost:8000` to view the live dashboard.

---

## 🚀 Quickstart

### 1. Set Up Environment

This project uses `uv` for fast Python dependency management.

```powershell
# Create virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your keys:

```powershell
cp .env.example .env
```

Required keys:
- **LiveKit**: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (Get free at [cloud.livekit.io](https://cloud.livekit.io))
- **Speech-to-Text**: `DEEPGRAM_API_KEY`
- **LLM**: `OPENAI_API_KEY` or `GEMINI_API_KEY` or `GROQ_API_KEY`
- **Text-to-Speech**: `CARTESIA_API_KEY` or `ELEVEN_API_KEY`
- **Notifications**: SMTP settings or SendGrid/Resend API key, and optional Twilio credentials for SMS.

### 3. Test Locally in Browser / Mic (No Phone Needed)

Run the agent in development mode:

```powershell
uv run python agent.py dev
```

Open the LiveKit Agent Playground link printed in the console (e.g. `https://agents-playground.livekit.io`), connect your microphone, and speak to your agent!

### 4. Connect to Your PBX / VoIP System

See [sip_setup.md](sip_setup.md) for detailed instructions on configuring your PBX (Asterisk, FreePBX, 3CX, RingCentral, etc.) to forward incoming calls to the agent via SIP trunking.
