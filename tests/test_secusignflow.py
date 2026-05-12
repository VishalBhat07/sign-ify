import base64
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Sign2Text"))

from crypto.aes_encryptor import AESEncryptor
from crypto.key_evolution import PacketHeader, RollingKeyManager
from secure_conference.adaptive_reliability import ReliabilityController
from secure_conference.packet_recovery import ParityBlock, VerifiedParityRecovery
from secure_conference.policy_verification import PolicyVerifier
from secure_conference.rooms import SecureConferenceRoom
from secure_conference.semantic import SemanticLabel, classify_packet
from secure_conference.transport_scheduler import AdaptiveTransportScheduler


def test_semantic_classification_and_policy_mapping():
    semantic = classify_packet("isl_frame_secure", {})
    scheduler = AdaptiveTransportScheduler()
    policy = scheduler.policy_for(semantic.label)
    assert semantic.label == SemanticLabel.CRITICAL
    assert policy.recovery == "aggressive"
    assert scheduler.should_use_parity("CRITICAL")


def test_metadata_encryption_replay_rejection():
    key = os.urandom(32)
    encryptor = AESEncryptor(key)
    header = {
        "packet_id": 1,
        "semantic_label": "CRITICAL",
        "epoch_id": 0,
        "packet_counter": 1,
        "timestamp": 1_700_000_000,
        "commitment_hash": "a" * 64,
        "policy_fingerprint": "policy",
        "parity_group": None,
    }
    header["timestamp"] = __import__("time").time_ns() // 1_000_000_000
    packet = encryptor.encrypt_with_header(b"hello", header)
    plain, decoded = encryptor.decrypt_with_header(packet)
    assert plain == b"hello"
    assert decoded["packet_counter"] == 1
    with pytest.raises(ValueError, match="Duplicate nonce"):
        encryptor.decrypt_with_header(packet)


def test_rolling_key_epoch_rotation_and_stale_epoch_rejection():
    manager = RollingKeyManager(os.urandom(32), "fingerprint", packets_per_epoch=2)
    first_header, first_key, _ = manager.next_header("CRITICAL")
    second_header, second_key, _ = manager.next_header("CRITICAL")
    third_header, third_key, rotated = manager.next_header("CRITICAL")
    assert first_header.epoch_id == 0
    assert second_header.epoch_id == 0
    assert third_header.epoch_id == 1
    assert rotated
    assert first_key != third_key
    manager.current_epoch = 3
    with pytest.raises(ValueError, match="Stale epoch"):
        manager.validate_epoch(0)


def test_duplicate_and_out_of_order_window_behavior():
    manager = RollingKeyManager(os.urandom(32), "fingerprint", replay_window_size=4)
    manager.current_epoch = 0
    header = PacketHeader(3, "CRITICAL", 0, 3, 1, "a" * 64, "fingerprint")
    manager.validate_header(header, "fingerprint")
    manager.validate_header(PacketHeader(2, "CRITICAL", 0, 2, 1, "a" * 64, "fingerprint"), "fingerprint")
    with pytest.raises(ValueError, match="Duplicate"):
        manager.validate_header(header, "fingerprint")


def test_corrupted_commitment_and_policy_downgrade_detection():
    manager = RollingKeyManager(os.urandom(32), "expected")
    bad_policy = PacketHeader(1, "CONTROL", 0, 1, 1, "a" * 64, "downgraded")
    with pytest.raises(ValueError, match="Policy fingerprint"):
        manager.validate_header(bad_policy, "expected")
    assert not manager.verify_commitment(PacketHeader(1, "CONTROL", 0, 1, 1, "bad", "expected"))


def test_policy_signature_failure_and_audit_log():
    verifier = PolicyVerifier()
    policy = {"CONTROL": {"semantic_label": "CONTROL", "reliability": "highest"}}
    signed = verifier.sign_policy(policy)
    tampered = signed.to_dict()
    tampered["policy"] = {"CONTROL": {"semantic_label": "CONTROL", "reliability": "low"}}
    assert not verifier.verify_policy(tampered)
    assert verifier.audit_records()


def test_parity_reconstruction_and_corruption_detection():
    recovery = VerifiedParityRecovery(group_size=3)
    payloads = {1: b"aaa", 2: b"bbb", 3: b"ccc"}
    block = None
    for packet_id, payload in payloads.items():
        block = recovery.add_packet(packet_id, payload, use_parity=True) or block
    assert block is not None
    recovered = recovery.recover(block, {1: b"aaa", 3: b"ccc"}, 2)
    assert recovered == b"bbb"
    corrupted = ParityBlock(block.group_id, block.packet_ids, b"bad", block.digest)
    with pytest.raises(ValueError, match="integrity"):
        recovery.recover(corrupted, {1: b"aaa", 3: b"ccc"}, 2)


def test_room_secure_payload_round_trip_and_replay():
    room = SecureConferenceRoom("room-id", "password")
    packet = room.encrypt_payload(b"gesture", "CRITICAL")
    plain, header = room.decrypt_secure_payload(packet)
    assert plain == b"gesture"
    assert header.semantic_label == "CRITICAL"
    with pytest.raises(ValueError):
        room.decrypt_secure_payload(packet)


def test_deterministic_network_loss_and_baseline_metrics(tmp_path):
    controller = ReliabilityController(loss_threshold=0.10)
    for index in range(20):
        controller.record_sent()
        if index in {1, 5, 9, 13}:
            controller.record_reject()
        else:
            controller.record_accept()
    mode = controller.mode_for("CRITICAL")
    assert controller.snapshot.packet_loss == pytest.approx(0.20)
    assert mode["recovery"] == "aggressive"
    out = tmp_path / "metrics.json"
    controller.export_json(out)
    assert "packet_loss" in out.read_text(encoding="utf-8")


def test_browser_server_header_shape_compatibility():
    header = PacketHeader(1, "CRITICAL", 0, 1, 1234, "a" * 64, "policy", None).to_dict()
    required = {
        "packet_id",
        "semantic_label",
        "epoch_id",
        "packet_counter",
        "timestamp",
        "commitment_hash",
        "policy_fingerprint",
        "parity_group",
    }
    assert set(header) == required
