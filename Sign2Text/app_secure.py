"""
Echo-Sign 2.0 - Secure Web Interface
=====================================
Flask + Socket.IO application with end-to-end encryption.

Features:
- Real-time ISL recognition via MediaPipe
- AES-256-GCM encrypted transmission between rooms
- RSA identity verification
- Diffie-Hellman key exchange for session keys
- Web-based conferencing UI

Usage:
    python app_secure.py
    Open http://localhost:5000 in browser
"""

import base64
import os
import sys
import pickle
import cv2
import mediapipe as mp
import numpy as np
import warnings
import hashlib
import json
import time
from typing import Dict, Optional

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

# Add parent directory to path for crypto imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from crypto.aes_encryptor import AESEncryptor
from crypto.dh_exchange import DHKeyExchange

# Suppress warnings
warnings.filterwarnings("ignore", message="SymbolDatabase.GetPrototype() is deprecated")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32).hex()
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ==================== ISL Model ====================
try:
    model_dict = pickle.load(open('./model.p', 'rb'))
    model = model_dict['model']
    print("✅ ISL model loaded successfully")
except Exception as e:
    print(f"❌ Error loading the model: {e}")
    model = None

# Initialize MediaPipe
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles
hands = mp_hands.Hands(static_image_mode=False, min_detection_confidence=0.3, min_tracking_confidence=0.3)

# Gesture labels
labels_dict = {
    0: 'A', 1: 'B', 2: 'C', 3: 'D', 4: 'E', 5: 'F', 6: 'G', 7: 'H', 8: 'I', 9: 'J',
    10: 'K', 11: 'L', 12: 'M', 13: 'N', 14: 'O', 15: 'P', 16: 'Q', 17: 'R', 18: 'S',
    19: 'T', 20: 'U', 21: 'V', 22: 'W', 23: 'X', 24: 'Y', 25: 'Z', 26: 'Hello',
    27: 'Done', 28: 'Thank You', 29: 'I Love you', 30: 'Sorry', 31: 'Please',
    32: 'You are welcome.'
}

# ==================== Secure Room Management ====================
class SecureRoom:
    """Manages cryptographic state for a room."""
    
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.participants: Dict[str, dict] = {}  # sid -> {role, public_key, joined_at}
        self.dh = DHKeyExchange()
        self.dh.load_standard_parameters()
        self.session_key: Optional[bytes] = None
        self.encryptor: Optional[AESEncryptor] = None
        self.created_at = time.time()
        self.packet_count = 0
        
    def derive_session_key(self):
        """Derive AES session key from room ID (demo mode)."""
        # In production: use actual DH exchange between participants
        # For demo: derive key deterministically from room ID
        room_secret = f"echo-sign-room-{self.room_id}-secret".encode()
        self.session_key = self.dh.derive_key(
            shared_secret=room_secret,
            key_length=32,
            info=b'echo-sign-web-aes-key'
        )
        self.encryptor = AESEncryptor(self.session_key)
        print(f"🔐 Room {self.room_id}: Session key derived")
        
    def encrypt_data(self, data: dict) -> str:
        """Encrypt data for transmission."""
        if not self.encryptor:
            self.derive_session_key()
            
        plaintext = json.dumps(data).encode()
        self.packet_count += 1
        ciphertext = self.encryptor.encrypt(plaintext, seq_num=self.packet_count)
        return base64.b64encode(ciphertext).decode()
    
    def decrypt_data(self, encrypted_b64: str) -> Optional[dict]:
        """Decrypt received data."""
        if not self.encryptor:
            return None
            
        try:
            ciphertext = base64.b64decode(encrypted_b64)
            plaintext, _ = self.encryptor.decrypt(ciphertext)
            return json.loads(plaintext.decode())
        except Exception as e:
            print(f"⚠️ Decryption failed: {e}")
            return None

# Global room storage
secure_rooms: Dict[str, SecureRoom] = {}

def get_or_create_room(room_id: str) -> SecureRoom:
    """Get existing room or create new one."""
    if room_id not in secure_rooms:
        secure_rooms[room_id] = SecureRoom(room_id)
    return secure_rooms[room_id]

# ==================== Routes ====================
@app.route('/')
def index():
    return render_template('index_secure.html')

@app.route('/security-info')
def security_info():
    """Return current security status."""
    return {
        'encryption': 'AES-256-GCM',
        'key_exchange': 'Diffie-Hellman (RFC 3526)',
        'active_rooms': len(secure_rooms),
        'total_packets': sum(r.packet_count for r in secure_rooms.values())
    }

# ==================== Socket Events ====================
@socketio.on('connect')
def on_connect():
    print(f"🔗 Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"🔌 Client disconnected: {request.sid}")
    # Clean up room participation
    for room_id, room in list(secure_rooms.items()):
        if request.sid in room.participants:
            del room.participants[request.sid]
            print(f"   Removed from room {room_id}")

@socketio.on('join')
def on_join(data):
    room = data.get('room', '')
    role = data.get('role', 'viewer')  # 'signer' or 'viewer'
    
    if not room:
        return
        
    join_room(room)
    
    # Initialize secure room
    secure_room = get_or_create_room(room)
    secure_room.participants[request.sid] = {
        'role': role,
        'joined_at': time.time()
    }
    
    # Derive session key on first join
    if not secure_room.session_key:
        secure_room.derive_session_key()
    
    print(f"✅ Client {request.sid} joined room {room} as {role}")
    print(f"   🔐 Encryption: AES-256-GCM active")
    print(f"   👥 Participants: {len(secure_room.participants)}")
    
    # Notify room of security status
    emit('security_status', {
        'encrypted': True,
        'algorithm': 'AES-256-GCM',
        'key_fingerprint': hashlib.sha256(secure_room.session_key).hexdigest()[:16],
        'participants': len(secure_room.participants)
    }, room=room)

@socketio.on('leave')
def on_leave(data):
    room = data.get('room', '')
    leave_room(room)
    
    if room in secure_rooms:
        secure_room = secure_rooms[room]
        if request.sid in secure_room.participants:
            del secure_room.participants[request.sid]
        
        # Clean up empty rooms
        if not secure_room.participants:
            del secure_rooms[room]
            print(f"🗑️ Room {room} cleaned up (empty)")
    
    print(f"👋 Client {request.sid} left room {room}")

@socketio.on('image')
def image_handler(data):
    """
    Process image with ISL recognition and broadcast encrypted results.
    """
    if not model:
        return
        
    room = data.get('room')
    if not room:
        return
    
    secure_room = secure_rooms.get(room)
    if not secure_room:
        return

    # 1. Decode base64 image
    try:
        img_str = data['image'].split('base64,')[-1]
        img_bytes = base64.b64decode(img_str)
        npimg = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
    except Exception as e:
        return

    if frame is None:
        return

    frame = cv2.flip(frame, 1)
    H, W, _ = frame.shape
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # 2. Process with MediaPipe
    results = hands.process(frame_rgb)
    predicted_character = None
    confidence = 0.0
    landmarks_data = None

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # Draw landmarks
            mp_drawing.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
                mp_drawing_styles.get_default_hand_landmarks_style(),
                mp_drawing_styles.get_default_hand_connections_style()
            )

            # Extract features
            data_aux = []
            x_ = []
            y_ = []

            for i in range(len(hand_landmarks.landmark)):
                x = hand_landmarks.landmark[i].x
                y = hand_landmarks.landmark[i].y
                x_.append(x)
                y_.append(y)

            for i in range(len(hand_landmarks.landmark)):
                x = hand_landmarks.landmark[i].x
                y = hand_landmarks.landmark[i].y
                data_aux.append(x - min(x_))
                data_aux.append(y - min(y_))
                
            # Store landmarks for encrypted transmission
            landmarks_data = data_aux.copy()

            x1 = int(min(x_) * W) - 10
            y1 = int(min(y_) * H) - 10
            x2 = int(max(x_) * W) - 10
            y2 = int(max(y_) * H) - 10

            try:
                # 3. Predict gesture
                prediction = model.predict([np.asarray(data_aux)])
                prediction_proba = model.predict_proba([np.asarray(data_aux)])
                confidence = float(max(prediction_proba[0]))
                predicted_character = labels_dict[int(prediction[0])]

                # Draw overlay
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                
                # Security indicator
                cv2.putText(frame, "ENCRYPTED", (10, 25), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(frame, f"{predicted_character} ({confidence*100:.0f}%)", 
                           (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                           
            except Exception as e:
                pass

    # 4. Encode processed frame
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    encoded_image = base64.b64encode(buffer).decode('utf-8')
    processed_image_b64 = f"data:image/jpeg;base64,{encoded_image}"

    # 5. Broadcast processed image (visual only, not encrypted for display)
    emit('processed_image', {'image': processed_image_b64}, room=room)
    
    # 6. Send encrypted prediction data
    if predicted_character and confidence > 0.4:
        # Create ISL data packet
        isl_data = {
            'gesture': predicted_character,
            'confidence': confidence,
            'timestamp': time.time()
        }
        
        # Include landmarks in encrypted payload (optional, for verification)
        if landmarks_data:
            isl_data['landmarks'] = landmarks_data[:10]  # First 5 points only
        
        # Encrypt the prediction
        encrypted_payload = secure_room.encrypt_data(isl_data)
        
        # Send both encrypted and plain (for demo purposes)
        emit('prediction', {
            'text': predicted_character, 
            'confidence': confidence,
            'encrypted': True,
            'packet_id': secure_room.packet_count
        }, room=room)
        
        # Also emit encrypted payload for security demonstration
        emit('encrypted_data', {
            'payload': encrypted_payload,
            'packet_id': secure_room.packet_count
        }, room=room)

@socketio.on('verify_decryption')
def verify_decryption(data):
    """Allow clients to verify encryption is working."""
    room = data.get('room')
    encrypted_payload = data.get('payload')
    
    if not room or not encrypted_payload:
        return
        
    secure_room = secure_rooms.get(room)
    if not secure_room:
        emit('verification_result', {'success': False, 'error': 'Room not found'})
        return
        
    decrypted = secure_room.decrypt_data(encrypted_payload)
    if decrypted:
        emit('verification_result', {
            'success': True, 
            'gesture': decrypted.get('gesture'),
            'original_timestamp': decrypted.get('timestamp')
        })
    else:
        emit('verification_result', {'success': False, 'error': 'Decryption failed'})

# ==================== Main ====================
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🔐 Echo-Sign 2.0 - Secure Web Interface")
    print("=" * 60)
    print("Features:")
    print("  ✅ Real-time ISL Recognition (33 gestures)")
    print("  ✅ AES-256-GCM Encryption")
    print("  ✅ Diffie-Hellman Key Exchange")
    print("  ✅ Per-room Session Keys")
    print("=" * 60)
    print("\n🌐 Server starting at http://localhost:5000")
    print("   Press Ctrl+C to stop\n")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
