# Sign2Text Secure Conference

This folder contains the runnable Flask/WebRTC app for SecuSignFlow.

## Run

```powershell
pip install -r requirements.txt
python scripts\generate_ssl.py
python app_conference_secure.py
```

Open:

```text
https://localhost:3000
```

Accept the self-signed certificate warning.

## Main App Files

```text
app_conference_secure.py              HTTPS entrypoint
secure_conference/                    backend package
templates/conference_secure.html      conference UI
static/css/conference_secure.css      UI styles
static/js/main.js                     room and socket flow
static/js/webrtc.js                   WebRTC media and data channels
static/js/crypto.js                   browser secure packet envelope
static/js/dashboard.js                SecuSignFlow Transport Monitor
```

## Security And Transport Features

- HTTPS/TLS signaling.
- Password-protected rooms.
- Signed room tokens.
- WebRTC media with SRTP.
- AES-GCM secure packet envelope for semantic packets.
- Rolling epoch keys.
- Policy fingerprints.
- Packet class counters.
- Packet loss simulation.
- Metrics export.

## Demo Notes

Use two tabs:

1. Create room as `Signer`.
2. Join room as `Viewer`.
3. Watch the research dashboard while sending gestures or chat.
4. Use packet loss presets to demonstrate transport behavior.
5. Turn viewer camera/microphone on if two-way conferencing is needed.

Viewers are receive-only by default, but they can publish camera and microphone from the setup screen or in-call controls.
