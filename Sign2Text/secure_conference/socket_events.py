"""Socket.IO event handlers for secure conferencing."""

from __future__ import annotations

import base64
import json
from typing import Any, Optional

from flask import current_app, request
from flask_socketio import SocketIO, emit, join_room, leave_room

from .auth import RoomAuth
from .config import STUN_SERVERS
from .rooms import Participant, RoomRegistry


def register_socket_events(socketio: SocketIO, room_auth: RoomAuth, room_registry: RoomRegistry) -> None:
    """Register all Socket.IO handlers."""

    def get_verified_participant(data: dict[str, Any]) -> tuple[Optional[str], Optional[Any], Optional[Any]]:
        room_id = data.get("room", "")
        token = data.get("token", "")
        if not room_id or not token:
            emit("auth_error", {"error": "Missing room or token"})
            return None, None, None

        payload = room_auth.verify_token(token)
        room = room_registry.get(room_id)
        participant = room.get_participant(request.sid) if room else None

        if not payload or payload.get("room_id") != room_id or not room or not participant:
            emit("auth_error", {"error": "Invalid token"})
            return None, None, None

        return room_id, room, participant

    @socketio.on("connect")
    def on_connect():
        print(f"🔗 Client connected: {request.sid}")

    @socketio.on("disconnect")
    def on_disconnect():
        print(f"🔌 Client disconnected: {request.sid}")
        for room in list(room_registry.values()):
            participant = room.remove_participant(request.sid)
            if not participant:
                continue

            emit(
                "participant_left",
                {
                    "name": participant.name,
                    "participants": len(room.participants),
                    "sid": request.sid,
                },
                room=room.room_id,
            )
            if not room.participants:
                room_registry.remove(room.room_id)
                room_auth.remove_room(room.room_id)
                print(f"🗑️ Room {room.room_id[:8]}... cleaned up")

    @socketio.on("create_room")
    def on_create_room(data):
        password = data.get("password", "")
        try:
            room_id = room_auth.create_room(password)
        except ValueError as exc:
            emit("room_error", {"error": str(exc)})
            return

        room_registry.create_room(room_id, password)
        print(f"🏠 Room created: {room_id[:8]}...")
        emit(
            "room_created",
            {
                "room_id": room_id,
                "message": "Room created successfully! Share this ID with others.",
            },
        )

    @socketio.on("join_room_secure")
    def on_join_room_secure(data):
        room_id = data.get("room", "")
        password = data.get("password", "")
        user_name = data.get("name", "Anonymous")
        role = data.get("role", "viewer")
        mode = data.get("mode", "video")
        client_ip = request.remote_addr or "unknown"

        valid, message = room_auth.verify_password(room_id, password, client_ip)
        if not valid:
            emit("join_failed", {"error": message})
            return

        room = room_registry.get_or_create(room_id, password)
        token = room_auth.generate_token(room_id, user_name)
        join_room(room_id)

        participant = Participant(
            sid=request.sid,
            role=role,
            mode=mode,
            name=user_name,
            token=token,
        )
        room.add_participant(participant)
        other_participants = [
            {"sid": sid, "name": member.name, "role": member.role}
            for sid, member in room.participants.items()
            if sid != request.sid
        ]

        print(f"✅ {user_name} joined room {room_id[:8]}... as {role}")
        emit(
            "join_success",
            {
                "room_id": room_id,
                "token": token,
                "role": role,
                "mode": mode,
                "name": user_name,
                "participants": len(room.participants),
                "other_participants": other_participants,
                "message_history": room.messages[-20:],
                "stun_servers": STUN_SERVERS,
                "security": {
                    "transport": "TLS",
                    "media": "WebRTC SRTP",
                    "signaling": "Socket.IO over HTTPS",
                    "isl": "AES-256-GCM over Socket.IO",
                },
                "key_fingerprint": room.key_fingerprint,
            },
        )
        emit(
            "participant_joined",
            {
                "sid": request.sid,
                "name": user_name,
                "role": role,
                "participants": len(room.participants),
            },
            room=room_id,
            include_self=False,
        )

    @socketio.on("voice_message_secure")
    def on_voice_message_secure(data):
        room_id, room, participant = get_verified_participant(data)
        if not room or not participant:
            return

        message = data.get("message", "").strip()
        if not message:
            return

        room.add_message(participant.name, message, "voice")
        emit(
            "new_message",
            {
                "sender": participant.name,
                "message": message,
                "type": "voice",
                "timestamp": room.messages[-1]["timestamp"],
            },
            room=room_id,
        )

    @socketio.on("isl_frame_secure")
    def on_isl_frame_secure(data):
        room_id, room, participant = get_verified_participant(data)
        if not room or not participant:
            return
        if participant.role != "signer":
            return

        encrypted_frame_b64 = data.get("encrypted_frame")
        if not encrypted_frame_b64:
            emit("signaling_error", {"error": "Missing encrypted ISL frame"})
            return

        recognizer = current_app.config.get("RECOGNIZER")
        if not recognizer or not recognizer.available:
            return

        try:
            encrypted_frame = base64.b64decode(encrypted_frame_b64)
            frame_bytes = room.decrypt_payload(encrypted_frame)
        except Exception:
            emit("signaling_error", {"error": "Unable to decrypt ISL frame"})
            return

        result = recognizer.predict_from_image_bytes(frame_bytes)
        recognized = bool(result.gesture and result.confidence > 0.65)

        timestamp = ""
        if recognized:
            room.add_message(participant.name, result.gesture, "sign")
            timestamp = room.messages[-1]["timestamp"]

        payload = json.dumps(
            {
                "sender": participant.name,
                "gesture": result.gesture if recognized else None,
                "confidence": result.confidence,
                "timestamp": timestamp,
                "landmarks": result.landmarks,
                "bbox": result.bbox,
                "annotated_preview": result.annotated_preview,
            }
        ).encode()
        encrypted_result = base64.b64encode(room.encrypt_payload(payload)).decode()

        emit(
            "isl_feedback_secure",
            {
                "encrypted_payload": encrypted_result,
                "sender_sid": request.sid,
            },
            room=room_id,
        )

    @socketio.on("webrtc_offer")
    def on_webrtc_offer(data):
        room_id, _, participant = get_verified_participant(data)
        if not participant:
            return

        target_sid = data.get("target_sid")
        offer = data.get("offer")
        if not target_sid or not offer:
            emit("signaling_error", {"error": "Invalid WebRTC offer payload"})
            return

        socketio.emit(
            "webrtc_offer",
            {
                "room": room_id,
                "offer": offer,
                "sender_sid": request.sid,
                "sender_name": participant.name,
                "sender_role": participant.role,
            },
            to=target_sid,
        )

    @socketio.on("webrtc_answer")
    def on_webrtc_answer(data):
        room_id, _, participant = get_verified_participant(data)
        if not participant:
            return

        target_sid = data.get("target_sid")
        answer = data.get("answer")
        if not target_sid or not answer:
            emit("signaling_error", {"error": "Invalid WebRTC answer payload"})
            return

        socketio.emit(
            "webrtc_answer",
            {
                "room": room_id,
                "answer": answer,
                "sender_sid": request.sid,
                "sender_name": participant.name,
            },
            to=target_sid,
        )

    @socketio.on("ice_candidate")
    def on_ice_candidate(data):
        room_id, _, participant = get_verified_participant(data)
        if not participant:
            return

        target_sid = data.get("target_sid")
        candidate = data.get("candidate")
        if not target_sid or candidate is None:
            emit("signaling_error", {"error": "Invalid ICE candidate payload"})
            return

        socketio.emit(
            "ice_candidate",
            {
                "room": room_id,
                "candidate": candidate,
                "sender_sid": request.sid,
                "sender_name": participant.name,
            },
            to=target_sid,
        )

    @socketio.on("leave_room_secure")
    def on_leave_room_secure(data):
        room_id, room, participant = get_verified_participant(data)
        if not room or not participant:
            return

        leave_room(room_id)
        room.remove_participant(request.sid)
        emit(
            "participant_left",
            {
                "name": participant.name,
                "participants": len(room.participants),
                "sid": request.sid,
            },
            room=room_id,
        )
        if not room.participants:
            room_registry.remove(room_id)
            room_auth.remove_room(room_id)
