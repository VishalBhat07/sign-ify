# Sign Language Web Conferencing App Architecture

To turn your local sign language model into a real-time conferencing application, we need to restructure it so that it can handle two remote users over a network.

## The Core Problem With The Current App
Currently, your `app.py` uses `cv2.VideoCapture(0)` on the backend. This means the webcam is opened on the **server machine** where the Python code runs. For a real web app, the camera must be opened on the **client side (the user's browser)** and the frames must be sent over the network to the server or directly to the other peer.

---

## Target Architecture

We will build a **Client-Server-Client Architecture** using **WebSockets (Socket.IO)** and **WebRTC**.

### 1. The Signer Client (Frontend A)
* Uses JS `navigator.mediaDevices.getUserMedia` to access the webcam.
* Captures video frames in real-time.
* **Networking:** Sends frames (as Base64 or binary) over WebSockets to the Python backend.

### 2. The Processing Server (Python Backend)
* Receives frames from Frontend A over the network via Socket.io.
* Runs the `mediapipe` and `model.predict()` logic on the incoming frames.
* **Networking:** Uses Socket.IO "Rooms" to establish a conference room. It broadcasts the predicted text to everyone in that room.

### 3. The Receiver Client (Frontend B)
* Connects to the server and joins the same "room".
* **Networking:** Listens for Socket.IO text events from the server.
* Uses the browser's native **Web Speech API** (`window.speechSynthesis`) to instantly read the text out loud as audio.
* Receives the raw video feed so they can also *see* the signer.

---

## Step-by-Step Implementation Plan

### Phase 1: Moving the Camera to the Browser
1. Modify `index.html` to include a `<video id="videoElement">` tag.
2. Write Javascript to request webcam permissions and draw the video frame to a hidden `<canvas>`.
3. Periodically extract frames from the canvas (`canvas.toDataURL('image/jpeg')`) and emit them via Socket.IO: `socket.emit('frame', imageData)`.
4. **Remove** `cv2.VideoCapture(0)` entirely from your Python backend.

### Phase 2: Server-Side Processing
1. Create a socket event on the backend: `@socketio.on('frame')`.
2. When the backend receives a frame, decode the base64 string back into a CV2 `frame`.
3. Run your MediaPipe + classification logic on it.
4. If a sign is detected, emit exactly what you are emitting right now: `socketio.emit('prediction', {'text': predicted_character})`.

### Phase 3: Setting Up "Rooms" (Networking Concept)
To make it a conference, not everyone should receive all messages.
1. When a user opens the app, they generate a Room ID (e.g., `?room=123`).
2. Both the Signer and the Receiver join room `123` using Flask-SocketIO's `join_room()` function.
3. The server only broadcasts the predictions to the specific room: `emit('prediction', data, room=room_id)`.

### Phase 4: Text-to-Speech (Receiver Output)
1. On the receiving end, listen for the `prediction` event.
2. Update a text box on the screen.
3. Use Javascript to speak it out:
   ```javascript
   let utterance = new SpeechSynthesisUtterance("Hello");
   window.speechSynthesis.speak(utterance);
   ```
   *(Note: Browsers require the user to explicitly click a button on the site first to enable audio autoplay.)*

### Phase 5 (Advanced): Migrating Video to WebRTC
WebSockets are okay for sending ~5 frames per second for AI processing, but they are too slow for real, smooth HD video conferencing (like Zoom).
1. We will introduce **WebRTC** to create a Peer-to-Peer video stream between the Signer and Receiver.
2. The server will act purely as a "Signaling Server" to help the two browsers find each other's IP addresses and ports to punch through NATs.
3. Once connected, video goes directly from Browser A to Browser B at 30+ FPS.
4. Browser A will *still* run the AI model either directly in the browser (using ONNX or JS models) or by sending lower-framerate snapshots to your backend Python server.
