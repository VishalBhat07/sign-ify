"""In-memory room and participant state."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from crypto.aes_encryptor import AESEncryptor


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

    @property
    def key_fingerprint(self) -> str:
        return hashlib.sha256(self.session_key).hexdigest()[:16]

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
        plaintext, _ = self.encryptor.decrypt(packet)
        return plaintext

    def encrypt_payload(self, payload: bytes) -> bytes:
        self.isl_packet_count += 1
        return self.encryptor.encrypt(payload, seq_num=self.isl_packet_count)

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
