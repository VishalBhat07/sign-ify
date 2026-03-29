"""Application factory for the secure conference app."""

from __future__ import annotations

import os

from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO

from .auth import RoomAuth
from .config import MODEL_PATH
from .rooms import RoomRegistry
from .services.recognition import SignLanguageRecognizer
from .socket_events import register_socket_events


socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")
room_registry = RoomRegistry()
room_auth = RoomAuth(secret_key=os.urandom(32).hex())
recognizer = SignLanguageRecognizer(MODEL_PATH)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config["SECRET_KEY"] = os.urandom(32).hex()
    app.config["RECOGNIZER"] = recognizer
    socketio.init_app(app)

    @app.route("/")
    def index():
        return render_template("conference_secure.html")

    @app.route("/security-info")
    def security_info():
        return jsonify(
            {
                "transport": "TLS 1.3",
                "media": "WebRTC SRTP",
                "signaling": "Socket.IO over HTTPS",
                "authentication": "Password + Signed Session Tokens",
                "isl": "Encrypted inference side-channel",
                "active_rooms": len(room_registry),
            }
        )

    register_socket_events(socketio, room_auth, room_registry)
    return app
