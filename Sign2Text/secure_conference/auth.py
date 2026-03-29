"""Authentication and room access control."""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import (
    ROOM_LOCKOUT_TIME_SECONDS,
    ROOM_MAX_FAILED_ATTEMPTS,
    ROOM_PASSWORD_MIN_LENGTH,
    TOKEN_MAX_AGE_SECONDS,
)


@dataclass
class RoomRecord:
    password_hash: str
    created_at: datetime = field(default_factory=datetime.utcnow)


class RoomAuth:
    """Manage room passwords, rate limits, and signed session tokens."""

    def __init__(self, secret_key: str):
        self._serializer = URLSafeTimedSerializer(secret_key)
        self._rooms: Dict[str, RoomRecord] = {}
        self._failed_attempts: Dict[str, list[float]] = {}

    @property
    def rooms(self) -> Dict[str, RoomRecord]:
        return self._rooms

    def create_room(self, password: str) -> str:
        if len(password) < ROOM_PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"Password must be at least {ROOM_PASSWORD_MIN_LENGTH} characters"
            )

        room_id = secrets.token_urlsafe(16)
        self._rooms[room_id] = RoomRecord(password_hash=self._hash_password(password))
        return room_id

    def verify_password(self, room_id: str, password: str, client_ip: str) -> tuple[bool, str]:
        if self._is_locked_out(client_ip):
            return False, "Too many failed attempts. Try again later."

        room = self._rooms.get(room_id)
        if not room:
            self._record_failure(client_ip)
            return False, "Room not found"

        if room.password_hash != self._hash_password(password):
            self._record_failure(client_ip)
            return False, "Invalid password"

        self._clear_failures(client_ip)
        return True, "Success"

    def generate_token(self, room_id: str, user_name: str) -> str:
        payload = {
            "room_id": room_id,
            "user_name": user_name,
            "iat": datetime.utcnow().isoformat(),
            "exp": (datetime.utcnow() + timedelta(seconds=TOKEN_MAX_AGE_SECONDS)).isoformat(),
        }
        return self._serializer.dumps(payload)

    def verify_token(self, token: str) -> Optional[dict]:
        try:
            return self._serializer.loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
        except (BadSignature, SignatureExpired):
            return None

    def remove_room(self, room_id: str) -> None:
        self._rooms.pop(room_id, None)

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def _is_locked_out(self, client_ip: str) -> bool:
        attempts = self._failed_attempts.get(client_ip, [])
        recent_attempts = [
            attempt for attempt in attempts if time.time() - attempt < ROOM_LOCKOUT_TIME_SECONDS
        ]
        if recent_attempts:
            self._failed_attempts[client_ip] = recent_attempts
        else:
            self._failed_attempts.pop(client_ip, None)
        return len(recent_attempts) >= ROOM_MAX_FAILED_ATTEMPTS

    def _record_failure(self, client_ip: str) -> None:
        self._failed_attempts.setdefault(client_ip, []).append(time.time())

    def _clear_failures(self, client_ip: str) -> None:
        self._failed_attempts.pop(client_ip, None)
