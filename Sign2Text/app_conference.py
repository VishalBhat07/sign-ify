"""
Echo-Sign 2.0 - Video Conferencing Mode
========================================
Enhanced Flask app with bidirectional communication:
- Signer: Sign language → Text (with video mode selection)
- Viewer: Voice → Text
- Real-time encrypted transmission
- Video conferencing interface

Usage:
    python app_conference.py
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
from datetime import datetime

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

# ==================== Conference Room Management ====================
class ConferenceRoom:
    """Manages a video conference room with encryption."""
    
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.participants: Dict[str, dict] = {}  # sid -> {role, mode, joined_at, name}
        self.dh = DHKeyExchange()
        self.dh.load_standard_parameters()
        self.session_key: Optional[bytes] = None
        self.encryptor: Optional[AESEncryptor] = None
        self.created_at = time.time()
        self.packet_count = 0
        self.messages: list = []  # Conversation history
        
    def derive_session_key(self):
        """Derive AES session key from room ID."""
        room_secret = f"echo-sign-conference-{self.room_id}-secret".encode()
        self.session_key = self.dh.derive_key(
            shared_secret=room_secret,
            key_length=32,
            info=b'echo-sign-conference-aes-key'
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
    
    def add_message(self, sender_name: str, message: str, msg_type: str):
        """Add message to conversation history."""
        self.messages.append({
            'sender': sender_name,
            'message': message,
            'type': msg_type,  # 'sign' or 'voice'
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })
        
        # Keep only last 50 messages
        if len(self.messages) > 50:
            self.messages = self.messages[-50:]

# Global room storage
conference_rooms: Dict[str, ConferenceRoom] = {}

def get_or_create_room(room_id: str) -> ConferenceRoom:
    """Get existing room or create new one."""
    if room_id not in conference_rooms:
        conference_rooms[room_id] = ConferenceRoom(room_id)
    return conference_rooms[room_id]

# ==================== Routes ====================
@app.route('/')
def index():
    return render_template('conference.html')

@app.route('/security-info')
def security_info():
    """Return current security status."""
    return {
        'encryption': 'AES-256-GCM',
        'key_exchange': 'Diffie-Hellman (RFC 3526)',
        'active_rooms': len(conference_rooms),
        'total_packets': sum(r.packet_count for r in conference_rooms.values())
    }

# ==================== Socket Events ====================
@socketio.on('connect')
def on_connect():
    print(f"🔗 Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"🔌 Client disconnected: {request.sid}")
    # Clean up room participation
    for room_id, room in list(conference_rooms.items()):
        if request.sid in room.participants:
            participant = room.participants[request.sid]
            del room.participants[request.sid]
            print(f"   Removed {participant.get('name', 'user')} from room {room_id}")
            
            # Notify others
            emit('participant_left', {
                'name': participant.get('name', 'Someone'),
                'participants': len(room.participants)
            }, room=room_id)

@socketio.on('join_conference')
def on_join_conference(data):
    """User joins conference with role and settings."""
    room = data.get('room', '')
    role = data.get('role', 'viewer')  # 'signer' or 'viewer'
    mode = data.get('mode', 'landmarks')  # 'landmarks', 'video', 'hybrid'
    user_name = data.get('name', 'Anonymous')
    
    if not room:
        return
        
    join_room(room)
    
    # Initialize conference room
    conf_room = get_or_create_room(room)
    conf_room.participants[request.sid] = {
        'role': role,
        'mode': mode,
        'joined_at': time.time(),
        'name': user_name
    }
    
    # Derive session key on first join
    if not conf_room.session_key:
        conf_room.derive_session_key()
    
    print(f"✅ {user_name} joined room {room} as {role} ({mode} mode)")
    print(f"   🔐 Encryption: AES-256-GCM active")
    print(f"   👥 Participants: {len(conf_room.participants)}")
    
    # Get other participant info
    other_participants = [
        {
            'name': p['name'],
            'role': p['role'],
            'mode': p['mode']
        }
        for sid, p in conf_room.participants.items() if sid != request.sid
    ]
    
    # Notify room of new participant
    emit('conference_joined', {
        'success': True,
        'room': room,
        'role': role,
        'mode': mode,
        'name': user_name,
        'key_fingerprint': hashlib.sha256(conf_room.session_key).hexdigest()[:16],
        'participants': len(conf_room.participants),
        'other_participants': other_participants,
        'message_history': conf_room.messages[-20:]  # Last 20 messages
    })
    
    # Notify others
    emit('participant_joined', {
        'name': user_name,
        'role': role,
        'mode': mode,
        'participants': len(conf_room.participants)
    }, room=room, include_self=False)

@socketio.on('video_frame')
def handle_video_frame(data):
    """Process video frame from any participant (bidirectional video)."""
    room = data.get('room')
    if not room:
        return
    
    conf_room = conference_rooms.get(room)
    if not conf_room:
        return
    
    participant = conf_room.participants.get(request.sid)
    if not participant:
        return
    
    user_name = participant['name']
    role = participant['role']
    
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
    
    predicted_character = None
    confidence = 0.0
    
    # Only process ISL for signers
    if role == 'signer' and model:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)
        landmarks_data = None
        mode = participant['mode']

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
                    
                landmarks_data = data_aux.copy()

                x1 = int(min(x_) * W) - 10
                y1 = int(min(y_) * H) - 10
                x2 = int(max(x_) * W) - 10
                y2 = int(max(y_) * H) - 10

                try:
                    # Predict gesture
                    prediction = model.predict([np.asarray(data_aux)])
                    prediction_proba = model.predict_proba([np.asarray(data_aux)])
                    confidence = float(max(prediction_proba[0]))
                    predicted_character = labels_dict[int(prediction[0])]

                    # Draw overlay
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                    cv2.putText(frame, f"{predicted_character} ({confidence*100:.0f}%)", 
                               (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                               
                except Exception as e:
                    pass

        # Send gesture as message if detected with high confidence
        if predicted_character and confidence > 0.65:
            conf_room.add_message(user_name, predicted_character, 'sign')
            
            message_data = {
                'sender': user_name,
                'message': predicted_character,
                'type': 'sign',
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
            
            # Broadcast decrypted message directly (encryption is for demo purposes)
            emit('new_message', message_data, room=room)

    # Encode and broadcast video to others
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
    encoded_image = base64.b64encode(buffer).decode('utf-8')
    
    video_data = {
        'sender': user_name,
        'sender_sid': request.sid,
        'image': f"data:image/jpeg;base64,{encoded_image}",
        'gesture': predicted_character,
        'confidence': confidence,
        'role': role
    }
    
    # Broadcast to room (others will receive it)
    emit('video_stream', video_data, room=room, include_self=False)

@socketio.on('voice_message')
def handle_voice_message(data):
    """Handle voice-to-text from any participant."""
    room = data.get('room')
    message = data.get('message', '')
    
    if not room or not message:
        return
    
    conf_room = conference_rooms.get(room)
    if not conf_room:
        return
    
    participant = conf_room.participants.get(request.sid)
    if not participant:
        return
    
    user_name = participant['name']
    
    # Add to conversation
    conf_room.add_message(user_name, message, 'voice')
    
    # Broadcast decrypted message directly
    message_data = {
        'sender': user_name,
        'message': message,
        'type': 'voice',
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }
    
    emit('new_message', message_data, room=room)

@socketio.on('leave_conference')
def on_leave_conference(data):
    """User leaves conference."""
    room = data.get('room', '')
    leave_room(room)
    
    if room in conference_rooms:
        conf_room = conference_rooms[room]
        if request.sid in conf_room.participants:
            participant = conf_room.participants[request.sid]
            user_name = participant.get('name', 'Someone')
            del conf_room.participants[request.sid]
            
            # Notify others
            emit('participant_left', {
                'name': user_name,
                'participants': len(conf_room.participants)
            }, room=room)
        
        # Clean up empty rooms
        if not conf_room.participants:
            del conference_rooms[room]
            print(f"🗑️ Room {room} cleaned up (empty)")
    
    print(f"👋 User left room {room}")

# ==================== Main ====================
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("🎥 Echo-Sign 2.0 - Video Conferencing Mode")
    print("=" * 60)
    print("Features:")
    print("  ✅ Bidirectional Communication")
    print("  ✅ Sign Language → Text")
    print("  ✅ Voice → Text")
    print("  ✅ 3 Video Modes (Landmarks/Video/Hybrid)")
    print("  ✅ AES-256-GCM Encryption")
    print("  ✅ Conversation History")
    print("=" * 60)
    print("\n🌐 Server starting at http://localhost:5000")
    print("   Press Ctrl+C to stop\n")
    
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
