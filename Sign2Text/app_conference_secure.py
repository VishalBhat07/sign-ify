"""
Echo-Sign 2.0 - Secure WebRTC conferencing entrypoint.

Phase 4 architecture:
- HTTPS/TLS for transport
- Password-protected rooms with signed session tokens
- Socket.IO for signaling only
- WebRTC peer-to-peer media transport
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from secure_conference import create_app, socketio
from secure_conference.config import CERT_PATH, KEY_PATH


app = create_app()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🔒 Echo-Sign 2.0 - SECURE WebRTC Conferencing")
    print("=" * 60)
    print("Security Features:")
    print("  ✅ HTTPS/TLS Transport")
    print("  ✅ Password-Protected Rooms")
    print("  ✅ Signed Session Tokens")
    print("  ✅ Rate Limiting (Brute-force protection)")
    print("  ✅ WebRTC P2P Media (SRTP)")
    print("  ✅ Socket.IO Signaling over HTTPS")
    print("=" * 60)

    port = int(os.environ.get("PORT", 3000))
    disable_ssl = os.environ.get("DISABLE_SSL") == "1"

    if CERT_PATH.exists() and KEY_PATH.exists() and not disable_ssl:
        print("\n🔐 SSL certificates found - Starting HTTPS server")
        print(f"   URL: https://localhost:{port}")
        print("   ⚠️  Accept the self-signed certificate warning")
        print("\n   Press Ctrl+C to stop\n")
        socketio.run(
            app,
            host="0.0.0.0",
            port=port,
            ssl_context=(str(CERT_PATH), str(KEY_PATH)),
            allow_unsafe_werkzeug=True,
        )
    else:
        if disable_ssl:
            print("\n⚠️  Running in HTTP mode (SSL disabled via ENV)")
        else:
            print("\n⚠️  SSL certificates not found!")
            print("   Run: python scripts/generate_ssl.py")
            print("   Or starting in HTTP mode (not recommended)...")
        
        print(f"   URL: http://localhost:{port}\n")
        socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
