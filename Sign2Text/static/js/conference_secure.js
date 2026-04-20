(function () {
  const socket = io();

  const state = {
    roomId: "",
    roomPassword: "",
    userName: "",
    currentRole: "",
    authToken: "",
    localStream: null,
    mediaReadyPromise: Promise.resolve(),
    stunServers: [],
    peerConnections: new Map(),
    remoteStreams: new Map(),
    peerMetadata: new Map(),
    activeRemoteSid: null,
    islIntervalId: null,
    islRequestInFlight: false,
    sessionKey: null,
    cryptoSeqNum: 0,
    recognition: null,
    isRecording: false,
    signalingReady: false,
    pendingSignals: [],
  };

  let ortSession = null;
  let handsTracking = null;
  let cameraInstance = null;
  let currentGesture = null;
  let gestureStartTime = 0;
  
  const labelsDict = {
      0: 'A', 1: 'B', 2: 'C', 3: 'D', 4: 'E', 5: 'F', 6: 'G', 7: 'H', 8: 'I', 9: 'J', 
      10: 'K', 11: 'L', 12: 'M', 13: 'N', 14: 'O', 15: 'P', 16: 'Q', 17: 'R', 18: 'S', 
      19: 'T', 20: 'U', 21: 'V', 22: 'W', 23: 'X', 24: 'Y', 25: 'Z', 26: 'Hello', 
      27: 'Done', 28: 'Thank You', 29: 'I Love you', 30: 'Sorry', 31: 'Please', 32: 'You are welcome.'
  };

  const elements = {
    setupScreen: document.getElementById("setupScreen"),
    conferenceScreen: document.getElementById("conferenceScreen"),
    createTab: document.getElementById("createTab"),
    joinTab: document.getElementById("joinTab"),
    createName: document.getElementById("createName"),
    createPassword: document.getElementById("createPassword"),
    joinName: document.getElementById("joinName"),
    joinRoomId: document.getElementById("joinRoomId"),
    joinPassword: document.getElementById("joinPassword"),
    roomCreated: document.getElementById("roomCreated"),
    newRoomId: document.getElementById("newRoomId"),
    btnCreate: document.getElementById("btnCreate"),
    btnEnterRoom: document.getElementById("btnEnterRoom"),
    btnJoin: document.getElementById("btnJoin"),
    copyRoomId: document.getElementById("copyRoomId"),
    roomName: document.getElementById("roomName"),
    userRole: document.getElementById("userRole"),
    yourRole: document.getElementById("yourRole"),
    keyFingerprint: document.getElementById("keyFingerprint"),
    participantCount: document.getElementById("participantCount"),
    mediaStatus: document.getElementById("mediaStatus"),
    localVideo: document.getElementById("localVideo"),
    islRenderedOverlay: document.getElementById("islRenderedOverlay"),
    islOverlayCanvas: document.getElementById("islOverlayCanvas"),
    islCaptureCanvas: document.getElementById("islCaptureCanvas"),
    localPlaceholder: document.getElementById("localPlaceholder"),
    islStatusBadge: document.getElementById("islStatusBadge"),
    remoteVideo: document.getElementById("remoteVideo"),
    remotePlaceholder: document.getElementById("remotePlaceholder"),
    remoteLabel: document.getElementById("remoteLabel"),
    remoteGestureBadge: document.getElementById("remoteGestureBadge"),
    chatMessages: document.getElementById("chatMessages"),
    voiceInput: document.getElementById("voiceInput"),
    btnSend: document.getElementById("btnSend"),
    btnVoice: document.getElementById("btnVoice"),
    btnLeave: document.getElementById("btnLeave"),
    toast: document.getElementById("toast"),
  };
  const islCaptureContext = elements.islCaptureCanvas.getContext("2d");

  function showToast(message, timeoutMs = 2600) {
    elements.toast.textContent = message;
    elements.toast.classList.remove("hidden");
    window.clearTimeout(showToast.timerId);
    showToast.timerId = window.setTimeout(() => {
      elements.toast.classList.add("hidden");
    }, timeoutMs);
  }

  function showTab(tabName) {
    document.querySelectorAll(".tab-btn").forEach((button) => {
      button.classList.toggle("active", button.dataset.tabTarget === tabName);
    });
    elements.createTab.classList.toggle("active", tabName === "create");
    elements.joinTab.classList.toggle("active", tabName === "join");
  }

  function getSelectedRole(groupName) {
    const selected = document.querySelector(
      `[data-role-group="${groupName}"] .role-option.selected`
    );
    return selected ? selected.dataset.role : "";
  }

  function setParticipantCount(count) {
    elements.participantCount.textContent = String(count);
  }

  function speakText(text) {
    if (!("speechSynthesis" in window) || !text) {
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.92;
    utterance.pitch = 1;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  function updateRemotePlaceholder(message) {
    elements.remotePlaceholder.textContent = message;
    elements.remotePlaceholder.classList.remove("hidden");
    elements.remoteVideo.srcObject = null;
  }

  function clearIslOverlay() {
    elements.islRenderedOverlay.removeAttribute("src");
    elements.islRenderedOverlay.classList.add("hidden");
  }

  async function sha256Bytes(input) {
    const digest = await crypto.subtle.digest("SHA-256", input);
    return new Uint8Array(digest);
  }

  async function deriveSessionKey(roomId, password) {
    const encoder = new TextEncoder();
    const passwordKey = await crypto.subtle.importKey(
      "raw",
      encoder.encode(password),
      "PBKDF2",
      false,
      ["deriveKey"]
    );
    const salt = await sha256Bytes(encoder.encode(roomId));
    return crypto.subtle.deriveKey(
      {
        name: "PBKDF2",
        salt,
        iterations: 100000,
        hash: "SHA-256",
      },
      passwordKey,
      { name: "AES-GCM", length: 256 },
      false,
      ["encrypt", "decrypt"]
    );
  }

  function bytesToBase64(bytes) {
    let binary = "";
    bytes.forEach((byte) => {
      binary += String.fromCharCode(byte);
    });
    return btoa(binary);
  }

  function base64ToBytes(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }

  async function encryptPacket(plainBytes) {
    if (!state.sessionKey) {
      throw new Error("Session key not ready");
    }

    state.cryptoSeqNum += 1;
    const nonce = new Uint8Array(12);
    crypto.getRandomValues(nonce);
    const seqBytes = new Uint8Array(new Uint32Array([state.cryptoSeqNum]).buffer);
    nonce.set(seqBytes.slice(0, 4), 0);

    const timestamp = new Uint8Array(8);
    const view = new DataView(timestamp.buffer);
    view.setBigUint64(0, BigInt(Math.floor(Date.now() / 1000)));

    const ciphertext = await crypto.subtle.encrypt(
      {
        name: "AES-GCM",
        iv: nonce,
        additionalData: timestamp,
      },
      state.sessionKey,
      plainBytes
    );

    const cipherBytes = new Uint8Array(ciphertext);
    const packet = new Uint8Array(nonce.length + cipherBytes.length + timestamp.length);
    packet.set(nonce, 0);
    packet.set(cipherBytes, nonce.length);
    packet.set(timestamp, nonce.length + cipherBytes.length);
    return packet;
  }

  async function decryptPacket(base64Payload) {
    if (!state.sessionKey) {
      throw new Error("Session key not ready");
    }

    const packet = base64ToBytes(base64Payload);
    if (packet.length < 36) {
      throw new Error("Encrypted payload too short");
    }

    const nonce = packet.slice(0, 12);
    const timestamp = packet.slice(packet.length - 8);
    const ciphertext = packet.slice(12, packet.length - 8);
    const plain = await crypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: nonce,
        additionalData: timestamp,
      },
      state.sessionKey,
      ciphertext
    );
    return new Uint8Array(plain);
  }

  function setRemoteStream(peerSid, stream) {
    state.remoteStreams.set(peerSid, stream);
    state.activeRemoteSid = peerSid;
    elements.remoteVideo.srcObject = stream;
    elements.remotePlaceholder.classList.add("hidden");
    const peer = state.peerMetadata.get(peerSid);
    const label = peer ? `${peer.name} (${peer.role})` : "Connected peer";
    elements.remoteLabel.innerHTML = `<i class="fa-solid fa-lock"></i> <span>${label}</span>`;
    elements.mediaStatus.textContent = "WebRTC connected";
  }

  function maybeDisplayAnotherRemote() {
    const remaining = Array.from(state.remoteStreams.entries())[0];
    if (!remaining) {
      state.activeRemoteSid = null;
      updateRemotePlaceholder("Waiting for a peer connection...");
      elements.remoteLabel.innerHTML =
        '<i class="fa-solid fa-user-group"></i> <span>No remote peer yet</span>';
      elements.mediaStatus.textContent = "WebRTC waiting";
      return;
    }

    const [peerSid, stream] = remaining;
    setRemoteStream(peerSid, stream);
  }

  function addMessage(message) {
    const emptyState = elements.chatMessages.querySelector(".empty-state");
    if (emptyState) {
      emptyState.remove();
    }

    const messageNode = document.createElement("div");
    messageNode.className = `message ${message.type || "voice"}`;
    const topLine = document.createElement("div");
    topLine.className = "message-topline";

    const sender = document.createElement("span");
    sender.textContent = message.sender;

    const timestamp = document.createElement("span");
    timestamp.textContent = message.timestamp || "";

    topLine.appendChild(sender);
    topLine.appendChild(timestamp);

    const contentRow = document.createElement("div");
    contentRow.className = "message-row";

    const content = document.createElement("div");
    content.className = "message-content";
    content.textContent = message.message;

    const speakButton = document.createElement("button");
    speakButton.type = "button";
    speakButton.className = "btn-speak";
    speakButton.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
    speakButton.title = "Speak this text";
    speakButton.addEventListener("click", () => speakText(message.message));

    contentRow.appendChild(content);
    contentRow.appendChild(speakButton);

    messageNode.appendChild(topLine);
    messageNode.appendChild(contentRow);
    elements.chatMessages.appendChild(messageNode);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
  }

  function addSystemMessage(text) {
    const emptyState = elements.chatMessages.querySelector(".empty-state");
    if (emptyState) {
      emptyState.remove();
    }

    const node = document.createElement("div");
    node.className = "system-message";
    node.innerHTML = `<i class="fa-solid fa-circle-info"></i> ${text}`;
    elements.chatMessages.appendChild(node);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
  }

  async function initializeLocalMedia() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });
      state.localStream = stream;
      elements.localVideo.srcObject = stream;
      elements.localPlaceholder.classList.add("hidden");
      elements.mediaStatus.textContent = "Camera ready";
      if (state.currentRole === "signer") {
        elements.islOverlayCanvas.classList.add("hidden");
        clearIslOverlay();
        startIslCapture();
      } else {
        stopIslCapture();
        elements.islOverlayCanvas.classList.add("hidden");
        clearIslOverlay();
        elements.islStatusBadge.innerHTML =
          '<i class="fa-solid fa-eye"></i> <span>ISL disabled for viewer</span>';
      }
      return stream;
    } catch (error) {
      console.error("Failed to access camera:", error);
      elements.localPlaceholder.textContent =
        "Could not access the camera. Check browser permissions.";
      elements.localPlaceholder.classList.remove("hidden");
      showToast("Could not access the camera.", 4000);
      throw error;
    }
  }

  function stopIslCapture() {
    if (cameraInstance) {
      cameraInstance.stop();
      cameraInstance = null;
    }
    clearIslOverlay();
  }

  async function startIslCapture() {
    stopIslCapture();
    elements.islStatusBadge.innerHTML =
      '<i class="fa-solid fa-hands-asl-interpreting"></i> <span>ISL Model Loading...</span>';

    if (!ortSession) {
      try {
        ortSession = await ort.InferenceSession.create('/static/model.onnx');
      } catch (e) {
        console.error("Failed to load ONNX model:", e);
        elements.islStatusBadge.innerHTML =
          '<i class="fa-solid fa-triangle-exclamation"></i> <span>Model load failed</span>';
        return;
      }
    }

    if (!handsTracking) {
      handsTracking = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
      });
      handsTracking.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.3,
        minTrackingConfidence: 0.3
      });
      handsTracking.onResults(onHandsResults);
    }

    cameraInstance = new window.Camera(elements.localVideo, {
      onFrame: async () => {
        await handsTracking.send({image: elements.localVideo});
      },
      width: 1280,
      height: 720
    });
    cameraInstance.start();
    elements.islStatusBadge.innerHTML =
      '<i class="fa-solid fa-hands-asl-interpreting"></i> <span>ISL monitoring active</span>';
  }

  async function broadcastSemanticEvent(gesture, confidence) {
      elements.islStatusBadge.innerHTML = 
          `<i class="fa-solid fa-hands-asl-interpreting"></i> <span>Detected: ${gesture} (${confidence}%)</span>`;
      
      const payloadObj = {
          type: "gesture_change",
          sender: state.userName,
          gesture: gesture,
          confidence: confidence,
          timestamp: new Date().toLocaleTimeString()
      };
      const payload = JSON.stringify(payloadObj);

      const encrypted = await encryptPacket(new TextEncoder().encode(payload));
      
      // Show it in our local chat
      addMessage({
          sender: state.userName + " (You)",
          message: gesture,
          type: "sign",
          timestamp: payloadObj.timestamp
      });
      
      // Send over all DataChannels
      for (const [peerSid, pc] of state.peerConnections.entries()) {
          const dc = pc.semanticChannel;
          if (dc && dc.readyState === "open") {
              dc.send(encrypted);
          }
      }
  }

  async function onHandsResults(results) {
    const canvasCtx = elements.islOverlayCanvas.getContext("2d");
    elements.islOverlayCanvas.width = elements.localVideo.videoWidth || 1280;
    elements.islOverlayCanvas.height = elements.localVideo.videoHeight || 720;
    
    canvasCtx.save();
    canvasCtx.clearRect(0, 0, elements.islOverlayCanvas.width, elements.islOverlayCanvas.height);
    
    if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
      for (const landmarks of results.multiHandLandmarks) {
        window.drawConnectors(canvasCtx, landmarks, window.HAND_CONNECTIONS,
                       {color: '#3cffd0', lineWidth: 5});
        window.drawLandmarks(canvasCtx, landmarks, {color: '#5200ff', lineWidth: 3});
      }
    }
    canvasCtx.restore();
    elements.islOverlayCanvas.classList.remove("hidden");

    if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0 || !ortSession) {
      return;
    }

    const hand = results.multiHandLandmarks[0];
    let x_ = [];
    let y_ = [];
    for (let i = 0; i < hand.length; i++) {
       x_.push(hand[i].x);
       y_.push(hand[i].y);
    }
    const minX = Math.min(...x_);
    const minY = Math.min(...y_);
    
    let dataAux = [];
    for (let i = 0; i < hand.length; i++) {
       dataAux.push(hand[i].x - minX);
       dataAux.push(hand[i].y - minY);
    }

    const tensor = new ort.Tensor('float32', Float32Array.from(dataAux), [1, 42]);
    try {
        // Specify that we ONLY want the first output (the predicted label)
        // This avoids fetching the "output_probability" sequence of maps that crashes WASM
        const fetches = [ortSession.outputNames[0]];
        const output = await ortSession.run({ float_input: tensor }, fetches);
        
        const labelTensor = output[ortSession.outputNames[0]];
        
        let predictedIdx = labelTensor.data[0];
        if (typeof predictedIdx === 'bigint' || typeof predictedIdx === 'string') {
            predictedIdx = Number(predictedIdx);
        }

        const predictedChar = labelsDict[predictedIdx];
        
        // Simple event-driven logic
        if (predictedChar !== currentGesture) {
            currentGesture = predictedChar;
            gestureStartTime = Date.now();
        } else if (Date.now() - gestureStartTime > 300) {
            // Emitting gesture stable for 300ms
            await broadcastSemanticEvent(predictedChar, 95); // 95% placeholder format
            // reset start time to act as a hold refresh
            gestureStartTime = Date.now() + 2000; 
        }
    } catch (e) {
        console.error("ONNX inference error", e);
    }
  }

  function sendChatMessage(message) {
    const text = (message || "").trim();
    if (!text) {
      return;
    }

    socket.emit("voice_message_secure", {
      room: state.roomId,
      token: state.authToken,
      message: text,
    });
    elements.voiceInput.value = "";
  }

  function setRecordingState(isRecording) {
    state.isRecording = isRecording;
    elements.btnVoice.classList.toggle("recording", isRecording);
    elements.btnVoice.innerHTML = isRecording
      ? '<i class="fa-solid fa-stop"></i>'
      : '<i class="fa-solid fa-microphone"></i>';
    elements.btnVoice.title = isRecording ? "Stop recording" : "Record and send";
  }

  function setupSpeechRecognition() {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      elements.btnVoice.disabled = true;
      elements.btnVoice.title = "Speech recognition not supported";
      return;
    }

    state.recognition = new SpeechRecognition();
    state.recognition.continuous = false;
    state.recognition.interimResults = false;
    state.recognition.lang = "en-US";

    state.recognition.onstart = () => setRecordingState(true);
    state.recognition.onerror = () => {
      setRecordingState(false);
      showToast("Mic recording failed.", 3200);
    };
    state.recognition.onend = () => setRecordingState(false);
    state.recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript || "";
      elements.voiceInput.value = transcript;
      sendChatMessage(transcript);
    };

    elements.btnVoice.addEventListener("click", () => {
      if (!state.recognition) {
        return;
      }
      if (state.isRecording) {
        state.recognition.stop();
        return;
      }
      state.recognition.start();
    });
  }

  async function ensureLocalTracks(peerConnection, peerSid) {
    if (peerConnection.__tracksAdded || !state.localStream) {
      return;
    }

    state.localStream.getTracks().forEach((track) => {
      peerConnection.addTrack(track, state.localStream);
    });
    peerConnection.__tracksAdded = true;
    state.peerMetadata.set(peerSid, state.peerMetadata.get(peerSid) || {});
  }

  function ensureMediaTransceivers(peerConnection) {
    const transceivers = peerConnection.getTransceivers();
    const hasVideo = transceivers.some(
      (transceiver) => transceiver.receiver && transceiver.receiver.track.kind === "video"
    );

    if (!hasVideo) {
      peerConnection.addTransceiver("video", {
        direction: state.localStream ? "sendrecv" : "recvonly",
      });
    }
  }

  function cleanupPeer(peerSid) {
    const peerConnection = state.peerConnections.get(peerSid);
    if (peerConnection) {
      peerConnection.onicecandidate = null;
      peerConnection.ontrack = null;
      peerConnection.onconnectionstatechange = null;
      peerConnection.close();
    }

    state.peerConnections.delete(peerSid);
    state.peerMetadata.delete(peerSid);
    state.remoteStreams.delete(peerSid);
    if (state.activeRemoteSid === peerSid) {
      maybeDisplayAnotherRemote();
    }
  }

  function setupDataChannel(channel, peerSid) {
      channel.binaryType = "arraybuffer";
      channel.onmessage = async (event) => {
          let buffer;
          if (event.data instanceof Blob) {
             buffer = new Uint8Array(await event.data.arrayBuffer());
          } else {
             buffer = new Uint8Array(event.data);
          }
          try {
              const nonce = buffer.slice(0, 12);
              const timestamp = buffer.slice(buffer.length - 8);
              const ciphertext = buffer.slice(12, buffer.length - 8);
              const plain = await crypto.subtle.decrypt(
                { name: "AES-GCM", iv: nonce, additionalData: timestamp },
                state.sessionKey,
                ciphertext
              );
              
              const payloadStr = new TextDecoder().decode(plain);
              const payload = JSON.parse(payloadStr);
              
              if (payload.type === "gesture_change") {
                  elements.remoteGestureBadge.innerHTML =
                    `<i class="fa-solid fa-language"></i> <span>${payload.sender}: ${payload.gesture}</span>`;
                  
                  addMessage({
                    sender: payload.sender,
                    message: payload.gesture,
                    type: "sign",
                    timestamp: payload.timestamp,
                  });
              }
          } catch(e) {
              console.error("DataChannel Decryption Failed:", e);
          }
      };
  }

  async function getOrCreatePeerConnection(peerSid, metadata = {}) {
    if (state.peerConnections.has(peerSid)) {
      const existingMeta = state.peerMetadata.get(peerSid) || {};
      state.peerMetadata.set(peerSid, { ...existingMeta, ...metadata });
      return state.peerConnections.get(peerSid);
    }

    const peerConnection = new RTCPeerConnection({
      iceServers: state.stunServers,
      iceCandidatePoolSize: 4,
    });

    state.peerConnections.set(peerSid, peerConnection);
    state.peerMetadata.set(peerSid, metadata);

    const semanticChannel = peerConnection.createDataChannel("critical_semantics");
    peerConnection.semanticChannel = semanticChannel;
    setupDataChannel(semanticChannel, peerSid);

    peerConnection.ondatachannel = (event) => {
        if (event.channel.label === "critical_semantics") {
            setupDataChannel(event.channel, peerSid);
            peerConnection.semanticChannel = event.channel;
        }
    };

    peerConnection.onicecandidate = (event) => {
      if (!event.candidate) {
        return;
      }
      socket.emit("ice_candidate", {
        room: state.roomId,
        token: state.authToken,
        target_sid: peerSid,
        candidate: event.candidate,
      });
    };

    peerConnection.ontrack = (event) => {
      if (!event.streams || !event.streams[0]) {
        return;
      }
      setRemoteStream(peerSid, event.streams[0]);
    };

    peerConnection.onconnectionstatechange = () => {
      const status = peerConnection.connectionState;
      if (status === "connected") {
        elements.mediaStatus.textContent = "WebRTC connected";
        return;
      }

      if (status === "failed" || status === "disconnected" || status === "closed") {
        cleanupPeer(peerSid);
      }
    };

    await state.mediaReadyPromise.catch(() => null);
    await ensureLocalTracks(peerConnection, peerSid);
    ensureMediaTransceivers(peerConnection);
    return peerConnection;
  }

  async function createOfferForPeer(peerSid, metadata = {}) {
    const peerConnection = await getOrCreatePeerConnection(peerSid, metadata);
    if (peerConnection.signalingState !== "stable") {
      return;
    }

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    socket.emit("webrtc_offer", {
      room: state.roomId,
      token: state.authToken,
      target_sid: peerSid,
      offer: peerConnection.localDescription,
    });
    elements.mediaStatus.textContent = "Negotiating WebRTC";
  }

  async function handleOffer(data) {
    if (!state.signalingReady) {
      state.pendingSignals.push({ type: "offer", data });
      return;
    }

    const peerConnection = await getOrCreatePeerConnection(data.sender_sid, {
      name: data.sender_name,
      role: data.sender_role,
    });

    if (peerConnection.signalingState !== "stable") {
      try {
        await peerConnection.setLocalDescription({ type: "rollback" });
      } catch (error) {
        console.warn("Rollback skipped:", error);
      }
    }

    await peerConnection.setRemoteDescription(new RTCSessionDescription(data.offer));
    await ensureLocalTracks(peerConnection, data.sender_sid);
    const answer = await peerConnection.createAnswer();
    await peerConnection.setLocalDescription(answer);

    socket.emit("webrtc_answer", {
      room: state.roomId,
      token: state.authToken,
      target_sid: data.sender_sid,
      answer: peerConnection.localDescription,
    });
  }

  async function handleAnswer(data) {
    if (!state.signalingReady) {
      state.pendingSignals.push({ type: "answer", data });
      return;
    }

    const peerConnection = state.peerConnections.get(data.sender_sid);
    if (!peerConnection) {
      return;
    }

    await peerConnection.setRemoteDescription(
      new RTCSessionDescription(data.answer)
    );
  }

  async function handleIceCandidate(data) {
    if (!state.signalingReady) {
      state.pendingSignals.push({ type: "ice", data });
      return;
    }

    const peerConnection = await getOrCreatePeerConnection(data.sender_sid, {
      name: data.sender_name,
    });
    if (!data.candidate) {
      return;
    }
    try {
      await peerConnection.addIceCandidate(new RTCIceCandidate(data.candidate));
    } catch (error) {
      console.error("Failed to add ICE candidate:", error);
    }
  }

  function resetRoomCreatedState() {
    elements.roomCreated.classList.add("hidden");
    elements.btnCreate.classList.remove("hidden");
  }

  async function enterConference(joinPayload) {
    socket.emit("join_room_secure", joinPayload);
  }

  async function flushPendingSignals() {
    if (!state.pendingSignals.length) {
      return;
    }

    const queue = [...state.pendingSignals];
    state.pendingSignals = [];
    for (const item of queue) {
      if (item.type === "offer") {
        await handleOffer(item.data);
      } else if (item.type === "answer") {
        await handleAnswer(item.data);
      } else if (item.type === "ice") {
        await handleIceCandidate(item.data);
      }
    }
  }

  document.querySelectorAll(".tab-btn").forEach((button) => {
    button.addEventListener("click", () => showTab(button.dataset.tabTarget));
  });

  document.querySelectorAll(".role-selector").forEach((container) => {
    container.querySelectorAll(".role-option").forEach((button) => {
      button.addEventListener("click", () => {
        container
          .querySelectorAll(".role-option")
          .forEach((option) => option.classList.remove("selected"));
        button.classList.add("selected");
      });
    });
  });

  elements.btnCreate.addEventListener("click", () => {
    const name = elements.createName.value.trim();
    const password = elements.createPassword.value;
    const role = getSelectedRole("create");

    if (!name || !password || !role) {
      showToast("Name, password, and role are required.");
      return;
    }

    state.userName = name;
    state.roomPassword = password;
    state.currentRole = role;
    socket.emit("create_room", { password });
  });

  elements.copyRoomId.addEventListener("click", async () => {
    await navigator.clipboard.writeText(state.roomId);
    showToast("Room ID copied.");
  });

  elements.btnEnterRoom.addEventListener("click", async () => {
    await enterConference({
      room: state.roomId,
      password: state.roomPassword,
      name: state.userName,
      role: state.currentRole,
      mode: "webrtc",
    });
  });

  elements.btnJoin.addEventListener("click", async () => {
    const name = elements.joinName.value.trim();
    const roomId = elements.joinRoomId.value.trim();
    const password = elements.joinPassword.value;
    const role = getSelectedRole("join");

    if (!name || !roomId || !password || !role) {
      showToast("Name, room ID, password, and role are required.");
      return;
    }

    state.userName = name;
    state.roomId = roomId;
    state.roomPassword = password;
    state.currentRole = role;
    await enterConference({
      room: roomId,
      password,
      name,
      role,
      mode: "webrtc",
    });
  });

  elements.btnSend.addEventListener("click", () => {
    sendChatMessage(elements.voiceInput.value);
  });

  elements.voiceInput.addEventListener("keypress", (event) => {
    if (event.key === "Enter") {
      elements.btnSend.click();
    }
  });

  setupSpeechRecognition();

  elements.btnLeave.addEventListener("click", () => {
    socket.emit("leave_room_secure", {
      room: state.roomId,
      token: state.authToken,
    });
    state.peerConnections.forEach((_, peerSid) => cleanupPeer(peerSid));
    stopIslCapture();
    if (state.localStream) {
      state.localStream.getTracks().forEach((track) => track.stop());
    }
    window.location.reload();
  });

  socket.on("room_created", (data) => {
    state.roomId = data.room_id;
    elements.newRoomId.textContent = data.room_id;
    elements.roomCreated.classList.remove("hidden");
    elements.btnCreate.classList.add("hidden");
  });

  socket.on("room_error", (data) => {
    resetRoomCreatedState();
    showToast(data.error, 3500);
  });

  socket.on("join_failed", (data) => {
    showToast(`Failed to join: ${data.error}`, 4000);
  });

  socket.on("join_success", async (data) => {
    state.roomId = data.room_id;
    state.authToken = data.token;
    state.currentRole = data.role;
    state.stunServers = data.stun_servers || [];
    state.sessionKey = await deriveSessionKey(data.room_id, state.roomPassword);
    state.mediaReadyPromise = initializeLocalMedia();
    state.signalingReady = false;

    try {
      await state.mediaReadyPromise;
    } catch (error) {
      return;
    }

    elements.setupScreen.classList.add("hidden");
    elements.conferenceScreen.classList.remove("hidden");
    elements.roomName.textContent = `Room: ${data.room_id.slice(0, 8)}...`;
    elements.userRole.textContent = `Role: ${data.role} | ${data.security.media}`;
    elements.yourRole.textContent = data.role;
    elements.keyFingerprint.textContent = `Room key: ${data.key_fingerprint}`;
    setParticipantCount(data.participants);
    elements.mediaStatus.textContent = "WebRTC waiting";

    elements.chatMessages.innerHTML = "";
    if (data.message_history && data.message_history.length) {
      data.message_history.forEach(addMessage);
    } else {
      elements.chatMessages.innerHTML =
        '<div class="empty-state">Messages stay inside the authenticated room.</div>';
    }

    state.signalingReady = true;
    await flushPendingSignals();

  });

  socket.on("participant_joined", async (data) => {
    setParticipantCount(data.participants);
    addSystemMessage(`${data.name} joined as ${data.role}`);
    elements.remoteLabel.innerHTML =
      `<i class="fa-solid fa-user-group"></i> <span>${data.name} joined</span>`;
    await createOfferForPeer(data.sid, { name: data.name, role: data.role });
  });

  socket.on("participant_left", (data) => {
    setParticipantCount(data.participants);
    addSystemMessage(`${data.name} left the room`);
    cleanupPeer(data.sid);
  });

  socket.on("new_message", addMessage);
  socket.on("isl_feedback_secure", async (data) => {
    try {
      state.islRequestInFlight = false;
      const payloadBytes = await decryptPacket(data.encrypted_payload);
      const payload = JSON.parse(new TextDecoder().decode(payloadBytes));
      if (payload.gesture) {
        elements.remoteGestureBadge.innerHTML =
          `<i class="fa-solid fa-language"></i> <span>${payload.sender}: ${payload.gesture} (${(payload.confidence * 100).toFixed(0)}%)</span>`;
        addMessage({
          sender: payload.sender,
          message: payload.gesture,
          type: "sign",
          timestamp: payload.timestamp,
        });
      }
      if (data.sender_sid === socket.id) {
        if (payload.annotated_preview) {
          elements.islRenderedOverlay.src =
            `data:image/jpeg;base64,${payload.annotated_preview}`;
          elements.islRenderedOverlay.classList.remove("hidden");
        } else {
          clearIslOverlay();
        }
        if (payload.gesture) {
          elements.islStatusBadge.innerHTML =
            `<i class="fa-solid fa-hands-asl-interpreting"></i> <span>Detected: ${payload.gesture} (${(payload.confidence * 100).toFixed(0)}%)</span>`;
        } else {
          elements.islStatusBadge.innerHTML =
            `<i class="fa-solid fa-hands-asl-interpreting"></i> <span>Scanning for gesture (${(payload.confidence * 100).toFixed(0)}%)</span>`;
        }
      }
    } catch (error) {
      state.islRequestInFlight = false;
      console.error("Failed to decrypt gesture payload:", error);
    }
  });
  socket.on("webrtc_offer", handleOffer);
  socket.on("webrtc_answer", handleAnswer);
  socket.on("ice_candidate", handleIceCandidate);

  socket.on("signaling_error", (data) => {
    console.error("Signaling error:", data.error);
    showToast(data.error, 3500);
  });

  socket.on("auth_error", (data) => {
    showToast(`Authentication error: ${data.error}`, 4000);
    window.setTimeout(() => window.location.reload(), 1200);
  });

  updateRemotePlaceholder("Waiting for a peer connection...");
})();
