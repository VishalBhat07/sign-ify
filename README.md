# SecuSignFlow / Echo-Sign 2.0

> Semantic-aware secure transport for real-time assistive conferencing.

SecuSignFlow extends the original Echo-Sign secure conferencing app into a transport-security research prototype for Indian Sign Language communication. The project still provides live WebRTC conferencing, room authentication, and gesture translation, but now also demonstrates adaptive transport behavior based on packet importance.

The core research idea is:

```text
packet importance -> transport scheduling -> rolling keys -> verified recovery -> metrics
```

## What Is New

- Semantic packet classes: `CONTROL`, `CRITICAL`, `INTERACTIVE`, and `BEST_EFFORT`.
- Adaptive transport scheduler that maps packet class to reliability, recovery, redundancy, and priority.
- Rolling session keys derived by epoch using HKDF from the room bootstrap key.
- Authenticated packet headers bound into AES-GCM associated data.
- Packet integrity chain metadata for transport continuity checks.
- Signed transport policy fingerprints to detect downgrade attempts.
- Verified XOR parity recovery for high-importance packets.
- Deterministic reliability controller for packet loss, RTT, jitter, replay rejection, and recovery metrics.
- Frontend SecuSignFlow Transport Monitor for faculty/demo visibility.
- Optional viewer camera and microphone publishing.

## Architecture

```text
Application Layer
        |
Packet Classification
        |
Adaptive Transport Scheduler
        |
Rolling Session Keys
        |
Verified Recovery
        |
Reliability Controller
        |
WebRTC / Socket.IO / TLS
```

Important files:

```text
crypto/
  aes_encryptor.py              AES-GCM encryption and metadata-aware packets
  key_evolution.py              rolling epoch keys and packet headers

Sign2Text/secure_conference/
  rooms.py                      room state, transport sync, secure packet flow
  socket_events.py              Socket.IO integration point
  semantic.py                   packet classes and classification
  transport_scheduler.py        deterministic policy mapping
  policy_verification.py        signed policy objects and audit trail
  packet_recovery.py            XOR parity recovery
  adaptive_reliability.py       metrics and threshold-based adaptation

Sign2Text/static/js/
  crypto.js                     browser packet header and epoch sync
  dashboard.js                  frontend transport monitor
  webrtc.js                     WebRTC media, data channel, camera/mic toggles
```

## Run

From the project root:

```powershell
cd Sign2Text
pip install -r requirements.txt
python scripts\generate_ssl.py
python app_conference_secure.py
```

Open:

```text
https://localhost:3000
```

Accept the self-signed certificate warning.

## Demo Flow

1. Open one browser tab as `Signer`.
2. Create a room with a password.
3. Open another tab or device as `Viewer`.
4. Join using the same room ID and password.
5. Use the SecuSignFlow Transport Monitor to show:
   - policy verification,
   - packet class counters,
   - current epoch and epoch progress,
   - latest authenticated packet header,
   - packet loss presets,
   - recovery and replay metrics.
6. Increase packet loss to `10%` or `20%` and show reliability behavior changing.
7. Export metrics as JSON from the dashboard.

## Viewer Media Options

Viewers are receive-only by default. They may optionally enable:

- camera publishing,
- microphone publishing,
- in-call camera toggle,
- in-call microphone toggle.

When a viewer enables camera or mic after joining, the WebRTC connection renegotiates and publishes the new track.

## Frontend Metrics

The research dashboard explains the displayed metrics in-app. Key meanings:

| Metric | Meaning |
|---|---|
| Policy Verified | Active transport policy matches the signed fingerprint. |
| Packet Classes | Counters for control, critical, interactive, and best-effort packets. |
| Current Epoch | Current rolling AES-GCM key generation. |
| Epoch Progress | Packets used in the current epoch before key rotation. |
| Recovered | Packets protected by retransmission or verified recovery behavior. |
| Replay Rejected | Duplicate, stale, or out-of-window packets rejected. |
| Latest Header | Authenticated packet metadata used as AES-GCM associated data. |

## Tests

The test suite is under `tests/`.

```powershell
python -m pytest tests\test_secusignflow.py
```

Tests cover replay rejection, stale epochs, duplicate/out-of-order windows, policy downgrade detection, parity reconstruction, rolling key continuity, audit logs, and browser/server header compatibility.

## Research Docs

- `docs/secusignflow_research_design.md`
- `docs/secusignflow_frontend_demo_guide.md`

## Positioning

SecuSignFlow is not a new encryption algorithm. It is a conservative transport-security framework that coordinates existing secure primitives with adaptive transport behavior for assistive conferencing.

Preferred wording:

- transport-security framework,
- semantic-aware transport prototype,
- adaptive secure conferencing architecture,
- rolling session keys,
- verified parity recovery.

Avoid claims like "unbreakable security" or "novel cryptographic algorithm."
