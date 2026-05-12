"""Signed transport policy verification and audit records."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from crypto.rsa_manager import RSAKeyManager


def canonical_policy(policy: dict[str, Any]) -> bytes:
    return json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")


def policy_fingerprint(policy: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_policy(policy)).hexdigest()[:16]


@dataclass
class SignedPolicy:
    policy: dict[str, Any]
    signature: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AuditRecord:
    event: str
    fingerprint: str
    accepted: bool
    timestamp: int
    detail: str = ""


class PolicyVerifier:
    """Signs, verifies, and audits transport policy objects."""

    def __init__(self, rsa_manager: RSAKeyManager | None = None) -> None:
        self.rsa_manager = rsa_manager or RSAKeyManager()
        if self.rsa_manager.private_key is None:
            self.rsa_manager.generate_keypair(key_size=2048)
        self.audit_log: list[AuditRecord] = []

    def sign_policy(self, policy: dict[str, Any]) -> SignedPolicy:
        message = canonical_policy(policy)
        signature = self.rsa_manager.sign(message)
        fingerprint = policy_fingerprint(policy)
        self.audit_log.append(AuditRecord("policy_signed", fingerprint, True, int(time.time())))
        return SignedPolicy(policy, base64.b64encode(signature).decode("ascii"), fingerprint)

    def verify_policy(self, signed_policy: SignedPolicy | dict[str, Any]) -> bool:
        if isinstance(signed_policy, dict):
            signed_policy = SignedPolicy(**signed_policy)
        expected_fingerprint = policy_fingerprint(signed_policy.policy)
        accepted = expected_fingerprint == signed_policy.fingerprint
        if accepted:
            signature = base64.b64decode(signed_policy.signature)
            accepted = self.rsa_manager.verify(canonical_policy(signed_policy.policy), signature)
        self.audit_log.append(
            AuditRecord("policy_verified", signed_policy.fingerprint, accepted, int(time.time()))
        )
        return accepted

    def verify_fingerprint(self, policy: dict[str, Any], fingerprint: str) -> bool:
        accepted = policy_fingerprint(policy) == fingerprint
        self.audit_log.append(AuditRecord("fingerprint_checked", fingerprint, accepted, int(time.time())))
        return accepted

    def audit_records(self) -> list[dict[str, Any]]:
        return [asdict(record) for record in self.audit_log]
