# Yeastar S100 Integration Guide (S-Series PBX)

This guide provides step-by-step instructions for connecting your **Yeastar S100** (or any Yeastar S-Series: S20, S50, S100, S300, or P-Series) PBX to your real-time Phone AI Agent.

---

## 🎯 What You Can Do With This Integration

1. **Auto-Attendant / Inbound Receptionist**: When a customer calls your main business number, Yeastar routes the call directly to the AI agent.
2. **After-Hours / Holiday Answering**: Yeastar Time Conditions route calls to the AI agent outside normal office hours.
3. **Queue / Ring Group Failover**: If human staff are busy or don't answer within 20 seconds, Yeastar automatically sends the caller to the AI agent to take a message.
4. **IVR Option**: "Press 1 for sales, Press 2 for support, or Press 3 to leave a detailed message with our virtual assistant."
5. **Direct Transfer from Desk Phones**: Staff on physical desk phones or Linkus softphones can blind-transfer callers to an AI agent extension (e.g. extension `8000`).

---

## 📋 Prerequisites

1. Access to the **Yeastar S100 Web GUI** (`https://<your-yeastar-ip>:8088`).
2. An active SIP Trunk in your LiveKit Cloud dashboard (or self-hosted SIP gateway) with:
   - **SIP Server / Registrar**: `<your-project-id>.sip.livekit.cloud` (Port: `5060`)
   - **SIP Username**: `yeastar_s100_trunk` (or your chosen username)
   - **SIP Password**: `YourSecurePassword123`
   - **Transport**: UDP or TLS

---

## Step 1: Create a SIP Trunk on Yeastar S100

1. Log into the Yeastar S100 Web GUI.
2. Navigate to **Settings** > **PBX** > **Trunks**.
3. Click **Add**.
4. In the trunk setup window, configure the following:

### Basic Settings:
- **Trunk Type**: Select **Register Trunk** (recommended if your Yeastar PBX is behind a NAT firewall) or **Peer Trunk** (if you use static public IP authentication).
- **Provider Name**: `AI-Phone-Agent`
- **Hostname / IP**: `<your-project-id>.sip.livekit.cloud`
- **Domain**: `<your-project-id>.sip.livekit.cloud`
- **Port**: `5060`
- **User Name**: `yeastar_s100_trunk`
- **Authentication Name**: `yeastar_s100_trunk`
- **Password**: `YourSecurePassword123`
- **From User**: `yeastar_s100_trunk`

### Codec Settings (Advanced Tab):
- Ensure the following codecs are enabled (in priority order):
  1. **PCMU** (G.711 u-law)
  2. **PCMA** (G.711 a-law)
  3. **Opus** (if enabled in firmware) or **G.722** (HD Voice)
- **DTMF Mode**: `RFC4733` (or `RFC2833`)
- **Transport**: `UDP` (or `TLS` if certificate configured)

5. Click **Save** and then click the orange **Apply** button at the top right of the Yeastar GUI.
6. Verify status: Go to **Status** > **System Status** > **Trunk Status**. Your `AI-Phone-Agent` trunk should show a green **Registered** (or **OK**) icon.

---

## Step 2: Route Calls to the AI Agent

Yeastar gives you total flexibility in how calls reach the agent:

### Scenario A: Route All Inbound Calls (Main Number)
1. Go to **Settings** > **PBX** > **Call Control** > **Inbound Routes**.
2. Click **Add** (or edit your existing Inbound Route).
3. **Name**: `Inbound-To-AI-Agent`
4. **Member Trunks**: Select your incoming PSTN / SIP provider trunk (e.g., your carrier DID).
5. **Destination**:
   - Select **Trunk** > `AI-Phone-Agent`.
6. Click **Save** and **Apply**.

---

### Scenario B: After-Hours / Night Mode Routing (Time Conditions)
1. Go to **Settings** > **PBX** > **Call Control** > **Time Conditions**.
2. Define your **Business Hours** (e.g. Mon-Fri 08:30 - 17:30).
3. Go to **Settings** > **PBX** > **Call Control** > **Inbound Routes** and edit your main line.
4. Enable **Time Condition**:
   - **During Business Hours**: Route to your regular Ring Group, Queue, or Receptionist.
   - **Outside Business Hours (After-Hours)**: Select **Trunk** > `AI-Phone-Agent`.
5. Click **Save** and **Apply**. Any calls arriving outside business hours will be answered immediately by the AI agent!

---

### Scenario C: Failover if Staff Don't Answer (Ring Group / Queue)
1. Go to **Settings** > **PBX** > **Call Features** > **Ring Group** (or **Queue**).
2. Edit your Ring Group (e.g. Ring Group 6200).
3. Under **Failover Destination**:
   - Set destination to **Trunk** > `AI-Phone-Agent`.
   - Set Ring Timeout to `20` seconds.
4. If all desk phones ring for 20 seconds with no answer, Yeastar automatically sends the caller to the AI agent to take detailed information and email/text you immediately.

---

### Scenario D: Transferring Calls to the AI from Desk Phones (Speed Dial / Outbound Route)
To allow any employee on a desk phone (Yealink, Fanvil, Grandstream, Snom) or the Yeastar Linkus mobile app to transfer a call to the AI agent:

1. Go to **Settings** > **PBX** > **Call Control** > **Outbound Routes**.
2. Click **Add**.
3. **Name**: `Transfer-To-AI-Agent`
4. **Dial Pattern**:
   - **Patterns**: `8000` (or any unused 4-digit extension code)
   - **Strip**: `4` (strips the digits before sending to trunk)
5. **Member Extensions**: Select **All Extensions**.
6. **Member Trunks**: Select `AI-Phone-Agent`.
7. Click **Save** and **Apply**.

👉 **Usage**: When a receptionist or team member is on the phone and the caller says *"I just want to leave a detailed message"*, the employee presses **Transfer** > `8000` > **Transfer**. The caller is seamlessly handed off to the AI Voice Agent!

---

## Step 3: Yeastar S100 Audio & NAT Best Practices

If your Yeastar S100 is installed on a local office LAN behind a router/firewall:
1. **SIP NAT Settings**:
   - Go to **Settings** > **System** > **Network** > **Static Route / Public IP**.
   - Under **PBX** > **General** > **SIP** > **NAT**, ensure **External IP Address** or **External Host** (DDNS) is entered.
   - Enable **STUN** if using dynamic IP (`stun.l.google.com:19302`).
2. **Port Forwarding (if using Peer Trunk)**:
   - Ensure SIP port `5060` (UDP) and RTP ports `10000-12000` (UDP) are forwarded or allowed on your firewall.
   - If using **Register Trunk**, port forwarding is usually **not required** because Yeastar initiates the outbound registration state to the cloud.

---

## Step 4: End-to-End Verification

1. Start your AI Agent:
   ```powershell
   cd C:\Users\chris.kendall\.gemini\antigravity\scratch\phone-ai-agent
   uv run python agent.py start
   ```
2. Dial `8000` from an office desk phone or Linkus client.
3. The AI Agent will answer:
   > *"Thank you for calling Acme Services. My name is your virtual assistant. How may I help you today?"*
4. Give your name, contact phone number, inquiry reason, and urgency level.
5. Hang up and verify that the HTML email alert and SMS arrive with your details.
