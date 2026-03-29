# Echo-Sign 2.0 "Secure-Stream"

> **Real-time Indian Sign Language (ISL) to Speech Translation over Secure Networks**

A comprehensive accessibility communication platform integrating Edge AI gesture recognition with secure encryption for private, low-latency ISL translation.

---

## 🎯 Project Overview

Echo-Sign 2.0 addresses the need for privacy-first, low-bandwidth accessibility communication. The system ensures sensitive visual communication remains private and secure through end-to-end encryption.

### Key Features

- **🤖 Edge AI Processing** - ISL recognition runs locally via MediaPipe + Random Forest ML
- **🔐 AES-256-GCM Encryption** - All gesture data encrypted with 128-bit authentication tags
- **🔑 Secure Key Derivation** - HKDF-SHA256 from Diffie-Hellman parameters
- **🌐 Web Interface** - Modern Flask + Socket.IO conferencing with real-time updates
- **🎤 Text-to-Speech** - Automatic speech synthesis of recognized gestures
- **👥 Multi-user Rooms** - Signers and Viewers in encrypted sessions

---

## 🏗️ System Architecture

### Web Interface Mode (Primary - `app_conference_secure.py`)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Flask Web Architecture                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐       WebSocket        ┌─────────────────┐    │
│   │   Browser   │◄─────────────────────►│  Flask Server   │    │
│   │  (Signer)   │    Socket.IO           │(app_conference) │    │
│   │  + Camera   │                        │    _secure)     │    │
│   └─────────────┘                        │  ┌───────────┐  │    │
│                                          │  │ MediaPipe │  │    │
│   ┌─────────────┐       WebSocket        │  │   + ML    │  │    │
│   │   Browser   │◄─────────────────────►│  └───────────┘  │    │
│   │  (Viewer)   │    Encrypted Data      │                 │    │
│   └─────────────┘                        │  ┌───────────┐  │    │
│                                          │  │AES-256-GCM│  │    │
│                                          │  │ Encryptor │  │    │
│                                          │  └───────────┘  │    │
│                                          └─────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Encryption Flow in `app_conference_secure.py`

```
1. User joins room → SecureRoom created
2. Room ID → HKDF (Diffie-Hellman) → AES-256 Session Key
3. Gesture detected → JSON serialized → AES-GCM encrypted
4. Encrypted payload → Base64 → Socket.IO broadcast
5. Viewers receive → Decryption → Display + TTS
```

---

## 🔧 Technical Implementation

### Web Application (`Sign2Text/app_conference_secure.py`)

| Component            | Implementation                         | Lines          |
| -------------------- | -------------------------------------- | -------------- |
| **Flask Server**     | Socket.IO real-time communication      | 43-45          |
| **SecureRoom Class** | Per-room encryption state management   | 72-119         |
| **AES Encryption**   | `AESEncryptor` from `crypto/` module   | 37, 95, 105    |
| **Key Derivation**   | `DHKeyExchange.derive_key()` with HKDF | 38, 90-94      |
| **MediaPipe**        | Real-time hand landmark detection      | 56-60, 242-256 |
| **ML Classifier**    | Random Forest gesture prediction       | 49, 285-288    |

### Crypto Modules Used (`crypto/`)

| Module                 | Used In            | Purpose                                |
| ---------------------- | ------------------ | -------------------------------------- |
| **`aes_encryptor.py`** | `app_conference_secure.py` ✅ | AES-256-GCM encrypt/decrypt            |
| **`dh_exchange.py`**   | `app_conference_secure.py` ✅ | HKDF key derivation                    |
| **`rsa_manager.py`**   | P2P clients only   | Identity verification (not in web app) |

### ISL Recognition (`Sign2Text/`)

| Component     | File                      | Description                            |
| ------------- | ------------------------- | -------------------------------------- |
| **Model**     | `model.p`                 | Random Forest classifier (33 gestures) |
| **Training**  | `train_classifier.py`     | Sklearn RandomForestClassifier         |
| **Inference** | `inference_classifier.py` | Standalone camera inference            |
| **Web App**   | `app_conference_secure.py`           | Flask + Socket.IO + Encryption         |

### Supported Gestures (33 total)

- **Letters**: A-Z (26 gestures)
- **Phrases**: Hello, Done, Thank You, I Love you, Sorry, Please, You are welcome

---

## 🚀 Quick Start

### Prerequisites

```bash
pip install opencv-python mediapipe flask flask-socketio cryptography numpy
```

### Run the Secure Web Interface

```bash
cd Sign2Text
python app_conference_secure.py
# Open https://localhost:5000 in browser
# (Note: Accept the self-signed SSL certificate warning)
```

**Or generate SSL certs first:**

```bash
python scripts/generate_ssl.py
python app_conference_secure.py
```

### How to Use

1. **As Signer (Camera User):**
   - Enter Room ID (e.g., `demo-room`)
   - Click "Join as Signer"
   - Allow camera access
   - Make ISL gestures → See encrypted translation

2. **As Viewer:**
   - Enter same Room ID
   - Click "Viewer"
   - Watch encrypted feed + live translation

---

## 📁 Project Structure

```
Echo-Sign/
├── Sign2Text/                        # Main Application
│   ├── app_conference_secure.py     # Flask + HTTPS + AES-256-GCM encryption ⭐
│   ├── model.p                      # Trained ISL classifier
│   ├── scripts/
│   │   └── generate_ssl.py          # SSL certificate generator
│   └── templates/
│       └── conference_secure.html   # Secure conferencing UI ⭐
│
├── crypto/                           # Cryptography Modules
│   ├── aes_encryptor.py             # AES-256-GCM (used in app) ⭐
│   ├── dh_exchange.py               # HKDF key derivation (used in app) ⭐
│   └── rsa_manager.py               # RSA keys (for P2P clients only)
│
├── networking/                 # Network Layer (for P2P mode)
│   ├── signaling_server.py    # TCP concurrent server
│   ├── signaling_client.py    # TCP client
│   └── udp_media_channel.py   # UDP transport
│
└── client/                     # Terminal P2P Clients
    ├── isl_sender_secure.py   # Encrypted sender (RSA + DH + AES)
    └── isl_receiver_secure.py # Encrypted receiver
```

⭐ = Used in web application

---

## 🔒 Security in `app_conference_secure.py`

### What's Actually Implemented

| Feature                     | Status        | Description                           |
| --------------------------- | ------------- | ------------------------------------- |
| **HTTPS/TLS Transport**     | ✅ Complete   | Self-signed SSL certificates          |
| **AES-256-GCM Encryption**  | ✅ Complete   | Video frame encryption                |
| **Password-Protected Rooms**| ✅ Complete   | PBKDF2-SHA256 key derivation          |
| **JWT Authentication**      | ✅ Complete   | Token-based room access               |
| **Rate Limiting**           | ✅ Complete   | 5 failed attempts = 5 min lockout     |
| **Sequence Numbers**        | ✅ Complete   | Replay attack protection              |

### Security Features

```python
# Password-based key derivation with PBKDF2
key = pbkdf2_sha256(password, room_id, iterations=100000)

# JWT for authenticated sessions
token = jwt.encode({'room_id': room_id, 'exp': expiry}, SECRET_KEY)

# AES-256-GCM for video encryption
encrypted_frame = aes_gcm.encrypt(frame_data, nonce, auth_tag)
ciphertext = self.encryptor.encrypt(plaintext, seq_num=self.packet_count)
return base64.b64encode(ciphertext).decode()
```

### Security Properties

| Property            | Implementation                        |
| ------------------- | ------------------------------------- |
| **Confidentiality** | AES-256-GCM encryption                |
| **Integrity**       | 128-bit GCM authentication tag        |
| **Uniqueness**      | Per-packet nonce from sequence number |
| **Room Isolation**  | Separate session key per room ID      |

---

## 📊 Performance

| Metric              | Value                      |
| ------------------- | -------------------------- |
| Gesture Latency     | ~80-100ms                  |
| Frame Rate          | ~15 FPS                    |
| Encryption Overhead | ~2% CPU                    |
| Gesture Accuracy    | 95%+ (controlled lighting) |

---

## 🎓 Academic Context

**Course**: Network Programming & Security Lab  
**Institution**: RV College of Engineering  
**Semester**: 6th Semester

### Syllabus Coverage

| Unit   | Topic        | Implementation                                 |
| ------ | ------------ | ---------------------------------------------- |
| **IV** | Cryptography | AES-GCM encryption, HKDF key derivation        |
| **V**  | Security     | Secure session management, authentication tags |

---

## 📄 License

Academic project - All rights reserved.
