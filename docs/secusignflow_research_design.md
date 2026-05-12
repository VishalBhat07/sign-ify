# SecuSignFlow Research Design

SecuSignFlow is a transport-security systems prototype for real-time assistive conferencing. It coordinates packet importance, transport scheduling, rolling session keys, verified recovery, and deterministic reliability control without introducing new cryptographic primitives.

## Packet Format

```text
+----------------+-------------------+--------------+------------------+------------+
| header_length  | JSON packet header | AES-GCM nonce| ciphertext + tag | timestamp  |
| 4 bytes        | authenticated AAD  | 12 bytes     | variable         | 8 bytes    |
+----------------+-------------------+--------------+------------------+------------+
```

Header fields:

```python
{
    "packet_id": int,
    "semantic_label": str,
    "epoch_id": int,
    "packet_counter": int,
    "timestamp": int,
    "commitment_hash": str,
    "policy_fingerprint": str,
    "parity_group": int | None
}
```

## State Machines

Sender:

```text
INIT -> POLICY_VERIFIED -> SESSION_ACTIVE -> KEY_ROTATION -> RECOVERY_MODE -> CLOSED
```

Receiver:

```text
WAIT_POLICY -> VERIFY_HEADER -> VERIFY_COMMITMENT -> ACCEPT
                                             |-> RECOVER
                                             |-> REJECT
```

Epoch transitions:

```text
bootstrap key -> epoch 0 key -> rotate every 32 packets -> retain current + previous epoch
```

Recovery flow:

```text
detect missing CONTROL/CRITICAL packet -> validate parity digest -> XOR reconstruct -> verify header/commitment -> accept or reject
```

## Threat Model

| Threat | Covered | Notes |
|---|---:|---|
| Replay attacks | Yes | AES-GCM nonces plus epoch-aware sliding replay windows. |
| Packet corruption | Yes | AES-GCM tag and parity digest validation. |
| Policy downgrade | Yes | Canonical policy fingerprints and RSA signatures. |
| MITM during policy exchange | Partial | Signed policy objects help; identity binding remains prototype-grade. |
| Traffic analysis | No | Packet importance may still be inferred from timing/size. |
| Denial of service | No | Existing room auth helps, but transport DoS is out of scope. |
| Endpoint compromise | Partial | Rolling keys reduce exposure but cannot protect compromised clients. |
| Stale-client desync | Yes | Epoch grace window and stale epoch rejection. |
| Recovery abuse | Partial | Parity integrity is checked; rate limiting is future work. |

## Security Claims

- Replay resistance is provided by unique nonces, packet counters, and sliding replay windows.
- Policy downgrade resistance is provided by signed policy objects and policy fingerprints bound into packet headers.
- Forward secrecy continuity is approximated through rolling epoch keys derived with HKDF from the room bootstrap secret.
- Verified recovery is provided for high-importance packets using authenticated XOR parity groups.

## Evaluation Baselines

| Baseline | Purpose |
|---|---|
| Static AES session | Compare rolling key overhead. |
| No recovery | Compare verified parity recovery success. |
| Fixed reliability | Compare deterministic reliability control. |
| No packet-importance scheduling | Compare adaptive transport scheduling. |

Metrics are exported as JSON or CSV: encryption latency, epoch rotation overhead, recovery success rate, bandwidth overhead, RTT impact, replay rejection rate, parity reconstruction latency, packet loss, jitter, and delivery rate by packet class.
