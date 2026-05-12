"""Packet classification for SecuSignFlow transport behavior."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SemanticLabel(str, Enum):
    CONTROL = "CONTROL"
    CRITICAL = "CRITICAL"
    INTERACTIVE = "INTERACTIVE"
    BEST_EFFORT = "BEST_EFFORT"


@dataclass(frozen=True)
class SemanticMetadata:
    label: SemanticLabel
    reason: str


def normalize_label(value: str | SemanticLabel | None) -> SemanticLabel:
    if isinstance(value, SemanticLabel):
        return value
    if not value:
        return SemanticLabel.INTERACTIVE
    try:
        return SemanticLabel[value.upper()]
    except KeyError:
        return SemanticLabel.INTERACTIVE


def classify_packet(event_name: str, payload: dict[str, Any] | None = None) -> SemanticMetadata:
    """Classify application traffic into transport importance classes."""
    payload = payload or {}
    packet_type = str(payload.get("type", "")).lower()

    if event_name in {"webrtc_offer", "webrtc_answer", "ice_candidate", "join_room_secure"}:
        return SemanticMetadata(SemanticLabel.CONTROL, "session signaling")
    if event_name == "isl_frame_secure":
        return SemanticMetadata(SemanticLabel.CRITICAL, "encrypted ISL frame")
    if packet_type in {"ack", "policy_refresh", "epoch_sync"}:
        return SemanticMetadata(SemanticLabel.CONTROL, "transport control message")
    if packet_type in {"gesture_change", "landmarks", "isl"}:
        return SemanticMetadata(SemanticLabel.CRITICAL, "gesture semantics")
    if event_name == "voice_message_secure":
        return SemanticMetadata(SemanticLabel.INTERACTIVE, "live conversation")
    return SemanticMetadata(SemanticLabel.BEST_EFFORT, "auxiliary packet")
