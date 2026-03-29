"""Configuration values for the secure conference app."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CERT_PATH = BASE_DIR / "cert.pem"
KEY_PATH = BASE_DIR / "key.pem"
MODEL_PATH = BASE_DIR / "model.p"
TOKEN_MAX_AGE_SECONDS = 2 * 60 * 60
ROOM_PASSWORD_MIN_LENGTH = 4
ROOM_LOCKOUT_TIME_SECONDS = 300
ROOM_MAX_FAILED_ATTEMPTS = 5
STUN_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
]
