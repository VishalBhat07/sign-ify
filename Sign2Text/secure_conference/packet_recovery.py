"""Verified XOR parity recovery for high-importance packets."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


def xor_bytes(chunks: list[bytes]) -> bytes:
    if not chunks:
        return b""
    size = max(len(chunk) for chunk in chunks)
    parity = bytearray(size)
    for chunk in chunks:
        padded = chunk.ljust(size, b"\x00")
        for index, value in enumerate(padded):
            parity[index] ^= value
    return bytes(parity)


@dataclass
class ParityBlock:
    group_id: int
    packet_ids: list[int]
    parity: bytes
    digest: str
    created_at: int = field(default_factory=lambda: int(time.time()))

    @classmethod
    def build(cls, group_id: int, packet_ids: list[int], payloads: list[bytes]) -> "ParityBlock":
        parity = xor_bytes(payloads)
        digest = hashlib.sha256(parity + ",".join(map(str, packet_ids)).encode()).hexdigest()
        return cls(group_id=group_id, packet_ids=packet_ids, parity=parity, digest=digest)

    def verify(self) -> bool:
        expected = hashlib.sha256(self.parity + ",".join(map(str, self.packet_ids)).encode()).hexdigest()
        return expected == self.digest


class VerifiedParityRecovery:
    """Creates and validates one-missing-packet XOR recovery groups."""

    def __init__(self, group_size: int = 3) -> None:
        self.group_size = group_size
        self._next_group_id = 1
        self._groups: dict[int, dict[int, bytes]] = {}
        self._parity: dict[int, ParityBlock] = {}

    def add_packet(self, packet_id: int, payload: bytes, use_parity: bool) -> ParityBlock | None:
        if not use_parity:
            return None
        group_id = self._next_group_id
        group = self._groups.setdefault(group_id, {})
        group[packet_id] = payload
        if len(group) < self.group_size:
            return None
        packet_ids = sorted(group)
        block = ParityBlock.build(group_id, packet_ids, [group[item] for item in packet_ids])
        self._parity[group_id] = block
        self._next_group_id += 1
        return block

    def recover(self, block: ParityBlock, available_payloads: dict[int, bytes], missing_packet_id: int) -> bytes:
        if not block.verify():
            raise ValueError("Parity block integrity check failed")
        if missing_packet_id not in block.packet_ids:
            raise ValueError("Missing packet is not part of the parity group")
        present = [payload for packet_id, payload in available_payloads.items() if packet_id in block.packet_ids]
        if len(present) != len(block.packet_ids) - 1:
            raise ValueError("XOR recovery requires exactly one missing packet")
        return xor_bytes([block.parity, *present])

    def get_parity(self, group_id: int) -> ParityBlock | None:
        return self._parity.get(group_id)
