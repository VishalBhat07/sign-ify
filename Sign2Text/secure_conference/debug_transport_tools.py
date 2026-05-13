"""Deterministic transport-security demo hooks for SecuSignFlow.

These helpers do not add protocol behavior. They expose reproducible events that
let the UI show replay rejection, recovery, and resynchronization decisions.
"""

from __future__ import annotations

from typing import Any


def replay_last_packet(room: Any) -> dict[str, Any]:
    packet_id = max(1, getattr(room.key_manager, "packet_counter", 1))
    room.reliability.record_reject(replay=True)
    return {
        "action": "replay_last_packet",
        "packet_id": packet_id,
        "status": "rejected",
        "reason": "Duplicate packet counter rejected by replay window",
        "integrity": "unchanged",
    }


def inject_duplicate_packet(room: Any) -> dict[str, Any]:
    packet_id = max(1, getattr(room.key_manager, "packet_counter", 1))
    room.reliability.record_reject(replay=True)
    return {
        "action": "inject_duplicate_packet",
        "packet_id": packet_id,
        "status": "rejected",
        "reason": "Duplicate encrypted packet suppressed before application delivery",
        "integrity": "valid_original_only",
    }


def simulate_stale_packet(room: Any) -> dict[str, Any]:
    stale_epoch = max(0, room.epoch_id - room.key_manager.epoch_grace - 1)
    room.reliability.record_reject(replay=True)
    return {
        "action": "simulate_stale_packet",
        "packet_id": max(1, getattr(room.key_manager, "packet_counter", 1)),
        "status": "rejected",
        "reason": f"Stale epoch {stale_epoch} is outside previous-epoch grace validity",
        "epoch_id": stale_epoch,
        "integrity": "stale",
    }


def force_epoch_mismatch(room: Any) -> dict[str, Any]:
    room.failure_count += 1
    room.receiver_state = "REJECT"
    return {
        "action": "force_epoch_mismatch",
        "status": "rejected",
        "reason": "Future epoch outside tolerance",
        "receiver_state": room.receiver_state,
        "failures": room.failure_count,
    }


def invalidate_commitment_chain(room: Any) -> dict[str, Any]:
    room.failure_count += 1
    room.receiver_state = "REJECT"
    return {
        "action": "invalidate_commitment_chain",
        "status": "rejected",
        "reason": "Integrity chain commitment mismatch",
        "receiver_state": room.receiver_state,
        "failures": room.failure_count,
    }


def trigger_resync(room: Any) -> dict[str, Any]:
    room.key_manager.reset_commitment()
    room.failure_count = 0
    room.sender_state = "SESSION_ACTIVE"
    room.receiver_state = "ACCEPT"
    return {
        "action": "trigger_resync",
        "status": "restored",
        "reason": "Commitment root reset and current epoch resynchronized",
        "epoch_id": room.epoch_id,
        "receiver_state": room.receiver_state,
        "failures": room.failure_count,
    }


DEBUG_ACTIONS = {
    "replay_last_packet": replay_last_packet,
    "inject_duplicate_packet": inject_duplicate_packet,
    "simulate_stale_packet": simulate_stale_packet,
    "force_epoch_mismatch": force_epoch_mismatch,
    "invalidate_commitment_chain": invalidate_commitment_chain,
    "trigger_resync": trigger_resync,
}


def run_debug_action(room: Any, action: str) -> dict[str, Any]:
    if action not in DEBUG_ACTIONS:
        raise ValueError(f"Unknown transport debug action: {action}")
    return DEBUG_ACTIONS[action](room)
