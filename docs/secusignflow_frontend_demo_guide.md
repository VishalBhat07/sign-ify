# SecuSignFlow Frontend Demo Guide

This guide explains how to demonstrate the visible SecuSignFlow improvements from the browser UI.

## Demo Setup

Run the app:

```powershell
cd Sign2Text
python app_conference_secure.py
```

Open:

```text
https://localhost:3000
```

Use two browser tabs:

- Tab 1: create room as `Signer`.
- Tab 2: join the same room as `Viewer`.

The viewer may stay receive-only, or enable camera/microphone using the setup checkboxes.

## What To Show Faculty

### 1. Secure Session

Point to:

- TLS Signaling,
- WebRTC SRTP,
- AES-GCM Layer,
- Policy,
- Fingerprint.

Meaning:

```text
The app is not only a video call. It has an authenticated transport policy and secure packet envelope.
```

### 2. Packet Classes

Show counters for:

- `CONTROL`,
- `CRITICAL`,
- `INTERACTIVE`,
- `BEST_EFFORT`.

Meaning:

```text
Packets are classified before scheduling. Critical gesture data receives stronger transport treatment than background traffic.
```

### 3. Rolling Keys

Show:

- Current Epoch,
- Epoch Progress,
- Replay Window.

Meaning:

```text
The room does not rely only on one static AES key. Packet epochs rotate after a bounded number of packets.
```

### 4. Live Metrics

Show:

- Packets Sent,
- Packets Received,
- ACKs Received,
- Retransmissions,
- Dupes Dropped,
- Recovered,
- Replay Rejected.

Meaning:

```text
The system records reliability and security behavior for evaluation.
```

### 5. Degradation Sandbox

Use packet loss presets:

- `0%`,
- `5%`,
- `10%`,
- `20%`.

Recommended demo:

1. Start at `0%`.
2. Send a few gestures.
3. Move to `10%`.
4. Show retransmissions/recovery-related counters increasing.
5. Move to `20%`.
6. Explain that CRITICAL traffic receives more aggressive protection than best-effort traffic.

### 6. Latest Packet Header

Show the JSON header:

```json
{
  "packet_id": 1,
  "semantic_label": "CRITICAL",
  "epoch_id": 0,
  "packet_counter": 1,
  "timestamp": 1234567890,
  "commitment_hash": "...",
  "policy_fingerprint": "...",
  "parity_group": null
}
```

Meaning:

```text
The header is visible for routing and evaluation, but authenticated as AES-GCM associated data.
```

### 7. Metrics Export

Click `Download JSON`.

Use this to show:

- reproducibility,
- experiment traces,
- packet loss settings,
- policy fingerprint,
- latest packet header.

## Viewer Camera And Mic Demo

By default, viewers can join as receive-only participants. To show optional two-way conferencing:

1. Join as viewer.
2. Enable `Publish camera` or `Publish microphone` before joining, or use the in-call camera/mic buttons.
3. Explain that enabling media after joining triggers WebRTC renegotiation.

## Short Presentation Script

Use this wording:

```text
SecuSignFlow treats gesture transport as a security and scheduling problem.
Gesture packets are classified as CRITICAL, bound to signed policy fingerprints, encrypted with rolling epoch keys, protected against replay, and measured in the browser dashboard.
```

Avoid:

```text
This is a new encryption algorithm.
```

Prefer:

```text
This is a transport-security coordination framework built using standard primitives.
```
