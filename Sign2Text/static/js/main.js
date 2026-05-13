import { state, elements, socket } from './state.js';
import { deriveSessionKey } from './crypto.js';
import { showTab, getSelectedRole, showToast, addMessage, addSystemMessage, resetRoomCreatedState, setParticipantCount, setRecordingState } from './ui.js';
import { stopIslCapture } from './inference.js';
import { cleanupPeer, handleOffer, handleAnswer, handleIceCandidate, createOfferForPeer, initializeLocalMedia, toggleLocalCamera, toggleLocalMic } from './webrtc.js';
import { initDashboard } from './dashboard.js';
import { initDemoPanels, recordDecision } from './demo_components.js';

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
  recordPacketClass("INTERACTIVE");
  elements.voiceInput.value = "";
}

function applyMediaPrefs(groupName, role) {
  const cameraInput = groupName === "create" ? elements.createCamera : elements.joinCamera;
  const micInput = groupName === "create" ? elements.createMic : elements.joinMic;
  state.mediaPrefs = {
    video: role === "signer" || Boolean(cameraInput && cameraInput.checked),
    audio: Boolean(micInput && micInput.checked),
  };
}

function recordPacketClass(label) {
  if (state.transportStats.classCounts[label] !== undefined) {
    state.transportStats.classCounts[label] += 1;
  }
  window.dispatchEvent(new CustomEvent("secusignflow:packet", {
    detail: { label, stage: "Packet Classified", type: "Classified" }
  }));
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

  state.recognition.onstart = () => setRecordingState(true, state);
  state.recognition.onerror = () => {
    setRecordingState(false, state);
    showToast("Mic recording failed.", 3200);
  };
  state.recognition.onend = () => setRecordingState(false, state);
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

async function enterConference(joinPayload) {
  socket.emit("join_room_secure", joinPayload);
}

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
  initDemoPanels();

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
        const group = container.dataset.roleGroup;
        const cameraInput = group === "create" ? elements.createCamera : elements.joinCamera;
        if (cameraInput && button.dataset.role === "signer") {
          cameraInput.checked = true;
        }
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
    applyMediaPrefs("create", role);
    recordPacketClass("CONTROL");
    socket.emit("create_room", { password });
  });

  elements.copyRoomId.addEventListener("click", async () => {
    await navigator.clipboard.writeText(state.roomId);
    showToast("Room ID copied.");
  });

  elements.btnEnterRoom.addEventListener("click", async () => {
    recordPacketClass("CONTROL");
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
    applyMediaPrefs("join", role);
    recordPacketClass("CONTROL");
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

  elements.btnToggleCamera.addEventListener("click", async () => {
    try {
      await toggleLocalCamera();
    } catch (error) {
      console.error("Camera toggle failed:", error);
      showToast("Could not toggle camera.", 3200);
    }
  });

  elements.btnToggleMic.addEventListener("click", async () => {
    try {
      await toggleLocalMic();
    } catch (error) {
      console.error("Mic toggle failed:", error);
      showToast("Could not toggle microphone.", 3200);
    }
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
    const transportSync = data.transport_sync || {};
    state.currentEpoch = transportSync.epoch_id || 0;
    state.packetsPerEpoch = transportSync.packets_per_epoch || 32;
    state.epochGrace = transportSync.epoch_grace || 1;
    state.policyFingerprint = transportSync.policy_fingerprint || "";
    state.transportPolicy = transportSync.policy || null;
    state.packetCounter = 0;
    state.commitmentHash = "";
    state.transportMode = "secusignflow";
    state.sessionKey = await deriveSessionKey(data.room_id, state.roomPassword, state.currentEpoch);
    state.epochKeys.set(state.currentEpoch, state.sessionKey);
    recordDecision("Policy verified -> rolling AES-GCM epoch session established", "CONTROL");
    
    if (window.epochInterval) clearInterval(window.epochInterval);
    window.epochInterval = setInterval(() => {
        for (const epochKey of state.epochKeys.keys()) {
            if (epochKey < state.currentEpoch - state.epochGrace) {
                state.epochKeys.delete(epochKey);
            }
        }
    }, 10000);
    
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

  socket.on("webrtc_offer", (data) => {
    recordPacketClass("CONTROL");
    handleOffer(data);
  });
  socket.on("webrtc_answer", (data) => {
    recordPacketClass("CONTROL");
    handleAnswer(data);
  });
  socket.on("ice_candidate", (data) => {
    recordPacketClass("CONTROL");
    handleIceCandidate(data);
  });

  socket.on("signaling_error", (data) => {
    console.error("Signaling error:", data.error);
    showToast(data.error, 3500);
  });

  socket.on("auth_error", (data) => {
    showToast(`Authentication error: ${data.error}`, 4000);
    window.setTimeout(() => window.location.reload(), 1200);
  });
});
