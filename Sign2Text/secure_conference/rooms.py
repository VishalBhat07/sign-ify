"""In-memory room and participant state."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from crypto.aes_encryptor import AESEncryptor
from crypto.key_evolution import PacketHeader, RollingKeyManager

from .adaptive_reliability import ReliabilityController
from .packet_recovery import VerifiedParityRecovery
from .policy_verification import PolicyVerifier, policy_fingerprint
from .semantic import normalize_label
from .transport_scheduler import AdaptiveTransportScheduler


@dataclass
class Participant:
    sid: str
    name: str
    role: str
    mode: str
    token: str
    joined_at: float = field(default_factory=time.time)


@dataclass
class SecureConferenceRoom:
    room_id: str
    password: str
    created_at: float = field(default_factory=time.time)
    participants: Dict[str, Participant] = field(default_factory=dict)
    messages: list[dict] = field(default_factory=list)
    isl_packet_count: int = 0

    def __post_init__(self):
        self.session_key = self._derive_session_key()
        self.encryptor = AESEncryptor(self.session_key)
        self.scheduler = AdaptiveTransportScheduler()
        self.policy_table = self.scheduler.policy_table()
        self.policy_fingerprint = policy_fingerprint(self.policy_table)
        self.policy_verifier = PolicyVerifier()
        self.signed_policy = self.policy_verifier.sign_policy(self.policy_table)
        self.key_manager = RollingKeyManager(self.session_key, self.policy_fingerprint)
        self.recovery = VerifiedParityRecovery()
        self.reliability = ReliabilityController()
        self.sender_state = "POLICY_VERIFIED"
        self.receiver_state = "WAIT_POLICY"
        self.failure_count = 0
        self.failure_threshold = 3

    @property
    def key_fingerprint(self) -> str:
        return hashlib.sha256(self.session_key).hexdigest()[:16]

    @property
    def epoch_id(self) -> int:
        return self.key_manager.current_epoch

    def add_participant(self, participant: Participant) -> None:
        self.participants[participant.sid] = participant

    def remove_participant(self, sid: str) -> Optional[Participant]:
        return self.participants.pop(sid, None)

    def get_participant(self, sid: str) -> Optional[Participant]:
        return self.participants.get(sid)

    def add_message(self, sender_name: str, message: str, msg_type: str) -> None:
        self.messages.append(
            {
                "sender": sender_name,
                "message": message,
                "type": msg_type,
                "timestamp": time.strftime("%H:%M:%S"),
            }
        )
        if len(self.messages) > 50:
            self.messages = self.messages[-50:]

    def decrypt_payload(self, packet: bytes) -> bytes:
        if self._looks_like_secure_packet(packet):
            plaintext, _ = self.decrypt_secure_payload(packet)
            return plaintext
        plaintext, _ = self.encryptor.decrypt(packet)
        return plaintext

    def encrypt_payload(self, payload: bytes, semantic_label: str = "INTERACTIVE") -> bytes:
        return self.encrypt_secure_payload(payload, semantic_label)

    def encrypt_legacy_payload(self, payload: bytes) -> bytes:
        self.isl_packet_count += 1
        return self.encryptor.encrypt(payload, seq_num=self.isl_packet_count)

    def encrypt_secure_payload(self, payload: bytes, semantic_label: str) -> bytes:
        label = normalize_label(semantic_label).value
        policy = self.scheduler.policy_for(label)
        if not self.policy_verifier.verify_fingerprint(self.policy_table, self.policy_fingerprint):
            self.sender_state = "CLOSED"
            raise ValueError("Transport policy fingerprint is invalid")

        parity_block = self.recovery.add_packet(
            self.key_manager.packet_counter + 1,
            payload,
            self.scheduler.should_use_parity(label),
        )
        parity_group = parity_block.group_id if parity_block else None
        header, epoch_key, rotated = self.key_manager.next_header(label, parity_group=parity_group)
        if rotated:
            self.sender_state = "KEY_ROTATION"
            self.reliability.record_key_rotation_latency(
                getattr(self.key_manager, "last_rotation_latency_ms", 0.0)
            )
        else:
            self.sender_state = "SESSION_ACTIVE"

        start = time.perf_counter()
        packet = self.encryptor.encrypt_with_header(payload, header.to_dict(), key=epoch_key)
        self.reliability.record_encryption_latency((time.perf_counter() - start) * 1000)
        self.reliability.record_sent()
        if policy.recovery == "aggressive":
            self.sender_state = "RECOVERY_MODE"
        return packet

    def decrypt_secure_payload(self, packet: bytes) -> tuple[bytes, PacketHeader]:
        self.receiver_state = "VERIFY_HEADER"

        def key_provider(header_data: dict[str, Any]) -> bytes:
            header_obj = PacketHeader.from_dict(header_data)
            self.key_manager.validate_header(header_obj, self.policy_fingerprint)
            return self.key_manager.key_for_epoch(header_obj.epoch_id)

        try:
            plaintext, header_data = self.encryptor.decrypt_with_header(packet, key_provider=key_provider)
            header = PacketHeader.from_dict(header_data)
            self.receiver_state = "VERIFY_COMMITMENT"
            if not self.key_manager.verify_commitment(header):
                raise ValueError("Packet integrity chain verification failed")
            self.receiver_state = "ACCEPT"
            self.failure_count = 0
            self.reliability.record_accept()
            return plaintext, header
        except ValueError as exc:
            self.failure_count += 1
            replay = "Duplicate" in str(exc) or "replay" in str(exc)
            self.reliability.record_reject(replay=replay)
            self.receiver_state = "RECOVER" if self.failure_count < self.failure_threshold else "REJECT"
            if self.failure_count >= self.failure_threshold:
                self.key_manager.reset_commitment()
            raise

    def transport_sync_payload(self) -> dict[str, Any]:
        return {
            "epoch_id": self.epoch_id,
            "packets_per_epoch": self.key_manager.packets_per_epoch,
            "epoch_grace": self.key_manager.epoch_grace,
            "policy_fingerprint": self.policy_fingerprint,
            "policy": self.policy_table,
            "signed_policy": self.signed_policy.to_dict(),
            "sender_state": self.sender_state,
            "receiver_state": self.receiver_state,
        }

    def _looks_like_secure_packet(self, packet: bytes) -> bool:
        if len(packet) < 4 + 12 + 16 + 8:
            return False
        header_len = int.from_bytes(packet[:4], "big")
        return 0 < header_len < len(packet) - 12 - 16 - 8

    def _derive_session_key(self) -> bytes:
        salt = hashlib.sha256(self.room_id.encode()).digest()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend(),
        )
        return kdf.derive(self.password.encode())


class RoomRegistry:
    """Store active room state."""

    def __init__(self):
        self._rooms: Dict[str, SecureConferenceRoom] = {}

    def create_room(self, room_id: str, password: str) -> SecureConferenceRoom:
        room = SecureConferenceRoom(room_id=room_id, password=password)
        self._rooms[room_id] = room
        return room

    def get(self, room_id: str) -> Optional[SecureConferenceRoom]:
        return self._rooms.get(room_id)

    def get_or_create(self, room_id: str, password: str) -> SecureConferenceRoom:
        room = self.get(room_id)
        return room if room else self.create_room(room_id, password)

    def remove(self, room_id: str) -> None:
        self._rooms.pop(room_id, None)

    def values(self):
        return self._rooms.values()

    def __len__(self) -> int:
        return len(self._rooms)
