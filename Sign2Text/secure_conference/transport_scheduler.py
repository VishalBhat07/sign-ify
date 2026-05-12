"""Deterministic adaptive transport scheduling for SecuSignFlow."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .semantic import SemanticLabel, normalize_label


@dataclass(frozen=True)
class TransportPolicy:
    semantic_label: str
    reliability: str
    redundancy: str
    encryption: str
    recovery: str
    priority: int

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


BASE_POLICIES: dict[SemanticLabel, TransportPolicy] = {
    SemanticLabel.CONTROL: TransportPolicy("CONTROL", "highest", "aggressive", "AES-GCM-epoch", "enabled", 0),
    SemanticLabel.CRITICAL: TransportPolicy("CRITICAL", "high", "parity", "AES-GCM-epoch", "aggressive", 1),
    SemanticLabel.INTERACTIVE: TransportPolicy("INTERACTIVE", "medium", "selective", "AES-GCM-epoch", "selective", 2),
    SemanticLabel.BEST_EFFORT: TransportPolicy("BEST_EFFORT", "low", "none", "AES-GCM-epoch", "disabled", 3),
}


class AdaptiveTransportScheduler:
    """Maps packet importance to deterministic transport behavior."""

    def __init__(self) -> None:
        self.policies = dict(BASE_POLICIES)

    def policy_for(self, label: str | SemanticLabel) -> TransportPolicy:
        return self.policies[normalize_label(label)]

    def policy_table(self) -> dict[str, dict[str, str | int]]:
        return {label.value: policy.to_dict() for label, policy in self.policies.items()}

    def should_use_recovery(self, label: str | SemanticLabel) -> bool:
        return self.policy_for(label).recovery != "disabled"

    def should_use_parity(self, label: str | SemanticLabel) -> bool:
        return self.policy_for(label).redundancy in {"aggressive", "parity"}
