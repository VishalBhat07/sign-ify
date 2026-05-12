"""Rolling session keys and packet integrity chains for SecuSignFlow."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


@dataclass
class PacketHeader:
    packet_id: int
    semantic_label: str
    epoch_id: int
    packet_counter: int
    timestamp: int
    commitment_hash: str
    policy_fingerprint: str
    parity_group: int | None = None

    def to_dict(self) -> dict:
        return {
            "packet_id": self.packet_id,
            "semantic_label": self.semantic_label,
            "epoch_id": self.epoch_id,
            "packet_counter": self.packet_counter,
            "timestamp": self.timestamp,
            "commitment_hash": self.commitment_hash,
            "policy_fingerprint": self.policy_fingerprint,
            "parity_group": self.parity_group,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PacketHeader":
        return cls(
            packet_id=int(data["packet_id"]),
            semantic_label=str(data["semantic_label"]),
            epoch_id=int(data["epoch_id"]),
            packet_counter=int(data["packet_counter"]),
            timestamp=int(data["timestamp"]),
            commitment_hash=str(data["commitment_hash"]),
            policy_fingerprint=str(data["policy_fingerprint"]),
            parity_group=data.get("parity_group"),
        )


@dataclass
class SlidingReplayWindow:
    window_size: int = 64
    highest_seen: int = 0
    seen: set[int] = field(default_factory=set)

    def check_and_mark(self, counter: int) -> None:
        if counter in self.seen:
            raise ValueError("Duplicate packet counter")
        if self.highest_seen and counter < self.highest_seen - self.window_size:
            raise ValueError("Packet counter outside replay window")
        self.seen.add(counter)
        self.highest_seen = max(self.highest_seen, counter)
        cutoff = self.highest_seen - self.window_size
        self.seen = {item for item in self.seen if item >= cutoff}


class RollingKeyManager:
    """Derives one AES key per epoch and tracks packet commitments."""

    def __init__(
        self,
        bootstrap_key: bytes,
        policy_fingerprint: str,
        packets_per_epoch: int = 32,
        epoch_grace: int = 1,
        replay_window_size: int = 64,
    ) -> None:
        if len(bootstrap_key) != 32:
            raise ValueError("Bootstrap key must be 32 bytes")
        self.bootstrap_key = bootstrap_key
        self.policy_fingerprint = policy_fingerprint
        self.packets_per_epoch = packets_per_epoch
        self.epoch_grace = epoch_grace
        self.current_epoch = 0
        self.packet_counter = 0
        self.last_commitment = hashlib.sha256(bootstrap_key + b"secusignflow").hexdigest()
        self.epoch_keys: dict[int, bytes] = {0: self._derive_epoch_key(0)}
        self.replay_windows: dict[int, SlidingReplayWindow] = {
            0: SlidingReplayWindow(window_size=replay_window_size)
        }
        self.replay_window_size = replay_window_size

    def next_header(self, semantic_label: str, parity_group: int | None = None) -> tuple[PacketHeader, bytes, bool]:
        self.packet_counter += 1
        rotated = False
        if self.packet_counter > 1 and (self.packet_counter - 1) % self.packets_per_epoch == 0:
            self.current_epoch += 1
            start = time.perf_counter()
            self.epoch_keys[self.current_epoch] = self._derive_epoch_key(self.current_epoch)
            self._drop_old_epochs()
            rotated = True
            self.last_rotation_latency_ms = (time.perf_counter() - start) * 1000
        key = self.epoch_keys[self.current_epoch]
        commitment = self._commitment(key, self.last_commitment, self.packet_counter, semantic_label, self.current_epoch)
        self.last_commitment = commitment
        header = PacketHeader(
            packet_id=self.packet_counter,
            semantic_label=semantic_label,
            epoch_id=self.current_epoch,
            packet_counter=self.packet_counter,
            timestamp=int(time.time()),
            commitment_hash=commitment,
            policy_fingerprint=self.policy_fingerprint,
            parity_group=parity_group,
        )
        return header, key, rotated

    def key_for_epoch(self, epoch_id: int) -> bytes:
        self.validate_epoch(epoch_id)
        if epoch_id not in self.epoch_keys:
            self.epoch_keys[epoch_id] = self._derive_epoch_key(epoch_id)
        return self.epoch_keys[epoch_id]

    def validate_header(self, header: PacketHeader, expected_policy_fingerprint: str | None = None) -> None:
        if expected_policy_fingerprint and header.policy_fingerprint != expected_policy_fingerprint:
            raise ValueError("Policy fingerprint mismatch")
        self.validate_epoch(header.epoch_id)
        window = self.replay_windows.setdefault(
            header.epoch_id, SlidingReplayWindow(window_size=self.replay_window_size)
        )
        window.check_and_mark(header.packet_counter)

    def validate_epoch(self, epoch_id: int) -> None:
        if epoch_id < self.current_epoch - self.epoch_grace:
            raise ValueError("Stale epoch")
        if epoch_id > self.current_epoch + 1:
            raise ValueError("Future epoch outside tolerance")

    def verify_commitment(self, header: PacketHeader) -> bool:
        return bool(header.commitment_hash) and len(header.commitment_hash) == 64

    def reset_commitment(self) -> None:
        self.last_commitment = hashlib.sha256(self.bootstrap_key + b"secusignflow-resync").hexdigest()

    def _derive_epoch_key(self, epoch_id: int) -> bytes:
        info = f"secusignflow-epoch-{epoch_id}".encode("utf-8")
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self.policy_fingerprint.encode("utf-8"),
            info=info,
            backend=default_backend(),
        ).derive(self.bootstrap_key)

    def _commitment(
        self, key: bytes, previous_commitment: str, packet_counter: int, semantic_label: str, epoch_id: int
    ) -> str:
        material = (
            key
            + previous_commitment.encode("ascii")
            + packet_counter.to_bytes(8, "big")
            + semantic_label.encode("utf-8")
            + epoch_id.to_bytes(4, "big")
        )
        return hashlib.sha256(material).hexdigest()

    def _drop_old_epochs(self) -> None:
        cutoff = self.current_epoch - self.epoch_grace
        self.epoch_keys = {epoch: key for epoch, key in self.epoch_keys.items() if epoch >= cutoff}
        self.replay_windows = {
            epoch: window for epoch, window in self.replay_windows.items() if epoch >= cutoff
        }
