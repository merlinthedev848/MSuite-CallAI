# Universal PBX & VoIP SIP Integration Guide

This guide details how to integrate the real-time AI Phone Agent with any standard RFC 3261-compliant VoIP PBX or SIP provider, with dedicated setup guides for **Yeastar S100**, **FreePBX / Asterisk**, **3CX**, **Grandstream UCM**, and **RingCentral**.

---

## 🧭 PBX Quick Index

- 🟢 **[Yeastar S100 / S-Series & P-Series Dedicated Guide](yeastar_setup.md)**
- 🔹 **[FreePBX / Asterisk (PJSIP)](#1-freepbx--asterisk-pjsip)**
- 🔹 **[Grandstream UCM 6200 / 6300 Series](#2-grandstream-ucm-series)**
- 🔹 **[3CX Phone System](#3-3cx-phone-system)**
- 🔹 **[RingCentral](#4-ringcentral)**
- 🔹 **[Direct Carrier Trunks (Twilio / Telnyx / Bandwidth)](#5-direct-carrier-sip-trunking-twilio--telnyx--bandwidth)**

---

## 🏗️ Architecture Overview

The system uses standard SIP trunking (Register Trunk or Peer Trunk) to bridge phone calls from your PBX into the sub-second streaming WebRTC pipeline:

```
[ Inbound Caller ]
       │
       ▼
[ Your PBX System ] (Yeastar S100, FreePBX, 3CX, Grandstream)
       │
       │ SIP Trunk (G.711 / Opus audio)
       ▼
[ LiveKit SIP Gateway ]
       │
       │ WebRTC Audio Stream (< 200ms latency)
       ▼
[ Phone AI Voice Agent (agent.py) ]
       ├── Deepgram STT (Streaming Speech-to-Text)
       ├── LLM (Gemini / OpenAI / Groq)
       ├── Cartesia / ElevenLabs (Streaming Text-to-Speech)
       └── Silero VAD (Interruption & turn detection)
       │
       ▼
[ Immediate Notifications ]
       ├── 📧 Rich HTML Email with caller details & transcript
       └── 📱 SMS alert via Twilio / Telnyx
```

---

## ⚙️ Step 1: Create LiveKit SIP Inbound Trunk & Dispatch Rule

Before connecting your PBX, create an inbound SIP Trunk and Dispatch Rule:

1. Log in to [cloud.livekit.io](https://cloud.livekit.io) and open your project.
2. In the left menu, select **SIP**.
3. Click **Create Inbound Trunk**:
   - **Name**: `PBX-Inbound-Trunk`
   - **Auth Type**: Select `Username / Password` (or IP Whitelist if your PBX has a static public IP).
   - **Username**: e.g., `pbx_agent_trunk`
   - **Password**: e.g., `YourSecurePassword123`
4. Click **Create Dispatch Rule**:
   - **Name**: `Route-To-AI-Agent`
   - **Trunk**: Select `PBX-Inbound-Trunk`.
   - **Rule Type**: Individual Room per Call (Prefix: `phone-call-`).

Note down your SIP Server domain: `<your-project-id>.sip.livekit.cloud`.

---

## ⚙️ Step 2: PBX Configurations

---

### ⭐ Yeastar S100 / S-Series & P-Series

> **See [yeastar_setup.md](yeastar_setup.md) for the complete, illustrated guide.**

1. In the Yeastar Web GUI, go to **Settings** > **PBX** > **Trunks** > **Add**.
2. Set **Trunk Type** to `Register Trunk`.
3. Set **Hostname/IP** to `<your-project-id>.sip.livekit.cloud`, Port `5060`.
4. Enter your SIP Username and Password.
5. In **Call Control** > **Inbound Routes** (or **Outbound Routes**), select your new trunk as the destination (e.g. for after-hours calls, ring group no-answer failover, or speed-dial extension `8000`).

---

### 1. FreePBX / Asterisk (PJSIP)

1. Go to **Connectivity** > **Trunks** > **Add Trunk** > **chan_pjsip**.
2. **General**: Trunk Name: `AI-Agent-Trunk`.
3. **pjsip Settings**:
   - **Authentication**: `Outbound`
   - **Registration**: `Send`
   - **SIP Server**: `<your-project-id>.sip.livekit.cloud`, Port `5060`
   - **Username**: `pbx_agent_trunk`
   - **Secret**: `YourSecurePassword123`
   - **Client URI**: `sip:pbx_agent_trunk@<your-project-id>.sip.livekit.cloud`
4. **Codecs**: Select `opus`, `ulaw`, and `alaw`.
5. Route your desired Inbound Route, IVR option, or Ring Group failover to this trunk.

---

### 2. Grandstream UCM Series (UCM6200 / UCM6300)

1. Go to **Extension / Trunk** > **VoIP Trunks** > **Add SIP Trunk**.
2. **Type**: `Register SIP Trunk`.
3. **Provider Name**: `AI-Phone-Agent`.
4. **Host Name**: `<your-project-id>.sip.livekit.cloud`.
5. Enter **User Name** and **Password**.
6. Under **Advanced Settings**:
   - Audio Codecs: `PCMU`, `PCMA`, `Opus`.
   - DTMF Mode: `RFC2833`.
7. In **Inbound Routes**, set Destination to this SIP Trunk.

---

### 3. 3CX Phone System

1. Go to **SIP Trunks** > **Add SIP Trunk**.
2. **Country**: `Generic` | **Provider**: `Generic SIP Trunk`.
3. **Registrar / Server**: `<your-project-id>.sip.livekit.cloud`, Port `5060`.
4. **Authentication**: `Account based` using your SIP username and password.
5. Route Inbound rules or IVR menu options to the trunk.

---

### 4. RingCentral

1. Go to **Admin Portal** > **Phone System** > **Auto-Receptionist**.
2. Set up call forwarding or SIP URI transfer pointing to:
   `sip:<number>@<your-project-id>.sip.livekit.cloud`

---

### 5. Direct Carrier SIP Trunking (Twilio / Telnyx / Bandwidth)

If you own numbers directly through a carrier:

- **Twilio**: Route incoming voice webhooks to a TwiML Bin:
  ```xml
  <Response>
    <Dial>
      <Sip>sip:caller@<your-project-id>.sip.livekit.cloud?username=pbx_agent_trunk&amp;password=YourSecurePassword123</Sip>
    </Dial>
  </Response>
  ```
- **Telnyx**: In the Portal, create a SIP Connection with FQDN `<your-project-id>.sip.livekit.cloud`.

---

## 🧪 Testing Your Setup

1. Start the agent worker:
   ```powershell
   uv run python agent.py start
   ```
2. Place a call through your PBX (or dial the internal extension / speed dial you assigned).
3. The AI agent will answer, converse naturally, collect the caller's details, and automatically dispatch email and SMS notifications when the call ends.
