"""Threshold-based reliability controller and metrics export."""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ReliabilitySnapshot:
    packet_loss: float = 0.0
    rtt_ms: float = 0.0
    jitter_ms: float = 0.0
    sent: int = 0
    accepted: int = 0
    rejected: int = 0
    recovered: int = 0
    replay_rejected: int = 0
    encryption_latency_ms: list[float] = field(default_factory=list)
    key_rotation_latency_ms: list[float] = field(default_factory=list)
    recovery_latency_ms: list[float] = field(default_factory=list)


class ReliabilityController:
    """Deterministic adaptation rules for reproducible evaluation."""

    def __init__(self, loss_threshold: float = 0.10, jitter_threshold_ms: float = 80.0) -> None:
        self.loss_threshold = loss_threshold
        self.jitter_threshold_ms = jitter_threshold_ms
        self.snapshot = ReliabilitySnapshot()

    def record_sent(self) -> None:
        self.snapshot.sent += 1

    def record_accept(self) -> None:
        self.snapshot.accepted += 1
        self._update_loss()

    def record_reject(self, replay: bool = False) -> None:
        self.snapshot.rejected += 1
        if replay:
            self.snapshot.replay_rejected += 1
        self._update_loss()

    def record_recovered(self, latency_ms: float = 0.0) -> None:
        self.snapshot.recovered += 1
        if latency_ms:
            self.snapshot.recovery_latency_ms.append(latency_ms)

    def record_encryption_latency(self, latency_ms: float) -> None:
        self.snapshot.encryption_latency_ms.append(latency_ms)

    def record_key_rotation_latency(self, latency_ms: float) -> None:
        self.snapshot.key_rotation_latency_ms.append(latency_ms)

    def update_network(self, packet_loss: float, rtt_ms: float, jitter_ms: float) -> None:
        self.snapshot.packet_loss = packet_loss
        self.snapshot.rtt_ms = rtt_ms
        self.snapshot.jitter_ms = jitter_ms

    def mode_for(self, semantic_label: str) -> dict[str, str | int]:
        high_loss = self.snapshot.packet_loss > self.loss_threshold
        high_jitter = self.snapshot.jitter_ms > self.jitter_threshold_ms
        if semantic_label in {"CONTROL", "CRITICAL"} and (high_loss or high_jitter):
            return {"redundancy": "increased", "recovery": "aggressive", "priority_boost": 1}
        if semantic_label == "BEST_EFFORT" and high_loss:
            return {"redundancy": "none", "recovery": "disabled", "priority_boost": 0}
        return {"redundancy": "normal", "recovery": "policy", "priority_boost": 0}

    def as_dict(self) -> dict:
        data = asdict(self.snapshot)
        data["exported_at"] = int(time.time())
        return data

    def export_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.as_dict(), indent=2), encoding="utf-8")

    def export_csv(self, path: str | Path) -> None:
        data = self.as_dict()
        with Path(path).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["metric", "value"])
            for key, value in data.items():
                writer.writerow([key, json.dumps(value) if isinstance(value, list) else value])

    def _update_loss(self) -> None:
        total = self.snapshot.accepted + self.snapshot.rejected
        self.snapshot.packet_loss = 0.0 if total == 0 else self.snapshot.rejected / total
