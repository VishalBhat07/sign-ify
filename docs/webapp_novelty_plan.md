# Final Plan: Novel Secure Semantic P2P Web App over WebRTC

## Summary
Transform the current web app into a pure browser-based, privacy-first P2P semantic communication system where Flask is only the secure signaling/auth server and all ISL meaning exchange happens directly between peers over WebRTC DataChannels. The novelty is not merely "using WebRTC," but designing a sign-language-aware semantic transport layer on top of it, with local inference, event-driven gesture packets, adaptive reliability, application-layer encryption, and measurable network-efficiency gains.

## Novel Features
1. **Semantic gesture transport instead of frame transport**
   - The app sends recognized gesture-state events, not raw frames for inference.
   - This shifts the system from media streaming to semantic communication.

2. **On-device ISL inference in the browser**
   - Gesture recognition happens on the signer's device.
   - The server no longer sees inference frames in normal operation.

3. **Event-driven packet transmission**
   - Packets are sent only when a gesture starts, changes, ends, or needs periodic refresh.
   - This directly reduces redundant traffic and becomes a measurable novelty claim.

4. **Continuous-vs-event-driven bandwidth comparison**
   - The app logs a software baseline for continuous transmission and compares it live with actual event-driven traffic.
   - This gives a strong experimental result for demo and report.

5. **Priority-aware semantic delivery**
   - Meaning-changing gesture events are treated as high priority.
   - Low-value refresh/context packets are deprioritized or dropped under degradation.

6. **Custom ACK and retransmission for semantic events**
   - Critical gesture packets are acknowledged at the application layer.
   - Lost important semantic events are retransmitted with bounded retries.

7. **Receiver-side reordering and duplicate suppression**
   - The receiver buffers out-of-order packets, restores delivery order for critical events, and drops duplicates.
   - This adds a real protocol contribution beyond plain WebRTC usage.

8. **Adaptive semantic reliability**
   - Reliability policy changes based on RTT/loss.
   - The system protects important gesture transitions while suppressing less valuable updates.

9. **Application-layer end-to-end encryption over WebRTC**
   - Semantic packets are encrypted again at the application layer using browser crypto.
   - This makes the design stronger than default transport-only protection.

10. **Network degradation simulation mode**
    - The UI can inject drop, delay, jitter, and duplication for demonstration and evaluation.
    - This turns the app into its own experimental testbed.

11. **Live research dashboard**
    - The UI shows latency, loss, retransmissions, packet savings, reorder count, and semantic channel status in real time.
    - This makes the novelty visible, not just internal.

12. **Epoch/key rotation as web-friendly moving-target defense**
    - In place of raw UDP port hopping, the web app rotates semantic epochs and keys during a session.
    - This preserves the research idea in a browser-feasible form.

## Key Changes

### 1. Architecture and Data Flow
- Keep Flask + Socket.IO only for room creation, authentication, presence, offer/answer/ICE exchange, and experiment config sync.
- Remove the web app's server-side gesture recognition path and stop using `isl_frame_secure` as the main transport.
- Move gesture detection and classification entirely into the signer browser.
- Establish one WebRTC peer connection per remote participant and open two DataChannels:
  - `critical_semantics`: ordered and reliable
  - `aux_semantics`: unordered or partially reliable
- Keep WebRTC video optional for presence/demo, but make semantic DataChannels the main research path.

### 2. Semantic Protocol
- Add one packet schema with:
  - `version`, `session_id`, `sender_id`, `channel`, `seq`, `epoch`, `sender_ts`, `event_type`, `gesture_id`, `gesture_label`, `confidence`, `priority`, `ack_required`, `payload`
- Use these event types:
  - `gesture_start`
  - `gesture_change`
  - `gesture_hold_refresh`
  - `gesture_end`
  - `ack`
  - `heartbeat`
  - `epoch_rotate`
- Default emission rules:
  - Emit only after gesture stability for 3 inference ticks or 300 ms.
  - End gesture after 500 ms of no confident detection.
  - Hold-refresh every 2 seconds.
  - Minimum confidence for emission: `0.65`.
- Priority mapping:
  - `high`: start/change/end
  - `low`: refresh/telemetry/context

### 3. Reliability and Security
- Maintain per-peer sequence numbers and per-epoch packet tracking.
- ACK all high-priority packets.
- Retransmit after `1.5 x smoothed RTT`, bounded between `150-800 ms`, max 3 retries.
- Receiver deduplicates by `(epoch, seq)` and reorders within a 10-packet buffer window.
- Add browser-side ECDH key exchange, HKDF session derivation, and AES-GCM encryption of semantic payloads.
- Authenticate packet headers as associated data.
- Rotate epoch and rekey every 60 seconds or on reconnect, with a 5-second stale-epoch grace window.

### 4. UI and Evaluation
- Add visible status indicators for:
  - signaling connected
  - WebRTC connected
  - semantic channel connected
  - encryption active
  - current epoch
- Add dashboard metrics for:
  - current gesture
  - packets sent
  - continuous baseline packet count
  - packet savings %
  - RTT
  - loss estimate
  - ACKs
  - retransmissions
  - duplicates
  - reordered packets
- Add experiment modes:
  - `baseline_frame_side_channel`
  - `continuous_semantic`
  - `event_driven_semantic`
  - `adaptive_event_driven_semantic`
- Default demo mode: `adaptive_event_driven_semantic`
- Add network simulator controls:
  - drop `0-30%`
  - delay `0-500 ms`
  - jitter `0-200 ms`
  - duplicate `0-10%`

## Final Project Basic Working
1. Users create or join a secure room through Flask.
2. Flask authenticates peers and only performs signaling duties.
3. Browsers establish a WebRTC peer connection and semantic DataChannels.
4. The signer browser performs ISL inference locally and maintains a gesture-state machine.
5. The state machine emits semantic events only on meaningful changes.
6. High-priority events are sent reliably and tracked for ACK.
7. Low-priority updates are best-effort and adaptive under congestion.
8. Semantic payloads are encrypted at the application layer before transmission.
9. The receiver decrypts, deduplicates, reorders, reconstructs current gesture state, and updates UI/TTS.
10. The dashboard continuously shows connection health, latency, loss, and packet savings.
11. If simulation mode is enabled, degradation is injected and reflected in the metrics live.

## Test Plan
- Verify Flask is only used for signaling/auth and not normal gesture-frame inference.
- Verify start/change/end events fire correctly from local inference.
- Verify event-driven mode sends far fewer packets than continuous mode for held gestures.
- Verify critical packets are ACKed and retransmitted when lost.
- Verify duplicates are dropped and out-of-order packets are reordered.
- Verify low-priority packets are suppressed before high-priority ones under degraded conditions.
- Verify application-layer decryption fails with wrong key or stale epoch.
- Verify epoch rotation does not break active sessions.
- Verify the dashboard reports RTT, retransmissions, loss, and packet savings correctly under injected drop/delay/jitter.

## Assumptions and Defaults
- Scope is only the current web app; the separate Python UDP prototype is ignored.
- The final design remains pure browser-based with no native helper.
- Raw UDP is not used directly; WebRTC DataChannels are the transport base.
- Video is optional and secondary; semantic transport is the primary contribution.
- "Port switching" in the web app is implemented as epoch/key rotation rather than real UDP port hopping.
- If time becomes limited, fully complete event-driven semantics, metrics, ACK/retransmission, and degradation simulation before adding epoch rotation.
