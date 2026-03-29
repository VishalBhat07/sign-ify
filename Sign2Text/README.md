## Sign2Text

Phase 4 is now implemented as a modular secure WebRTC app.

### Current architecture

- `app_conference_secure.py`
  Thin HTTPS entrypoint.
- `secure_conference/`
  Backend package for app setup, auth, room state, config, and Socket.IO signaling.
- `templates/conference_secure.html`
  Lean page shell.
- `static/css/conference_secure.css`
  Conference styling.
- `static/js/conference_secure.js`
  WebRTC client, secure room flow, and chat logic.
- `scripts/generate_ssl.py`
  SSL certificate generator.

### Security model

- HTTPS/TLS for transport
- Password-protected rooms
- Signed session tokens
- Rate limiting on joins
- WebRTC peer-to-peer media with SRTP
- Socket.IO used only for signaling and room chat

### Run

```bash
pip install -r requirements.txt
python scripts/generate_ssl.py
python app_conference_secure.py
```

Open `https://localhost:5000` and accept the self-signed certificate warning.
