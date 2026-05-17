import { state, elements, socket } from './state.js';
import { decryptPacketBuffer } from './crypto.js';
import { addMessage, updateRemotePlaceholder, showToast, clearIslOverlay } from './ui.js';
import { startIslCapture, stopIslCapture } from './inference.js';
import { processInboundReliability } from './reliability.js';

// ── Mic Audio Visualizer (Google Meet-style wave) ──
let micAnalyserCtx = null;
let micAnalyser = null;
let micSource = null;
let micAnimFrame = null;

function createWaveContainer() {
  let container = document.getElementById('micWaveVisualizer');
  if (container) return container;
  container = document.createElement('div');
  container.id = 'micWaveVisualizer';
  container.className = 'mic-wave-visualizer';
  container.innerHTML = `<div class="mic-wave-bar"></div><div class="mic-wave-bar"></div><div class="mic-wave-bar"></div><div class="mic-wave-bar"></div><div class="mic-wave-bar"></div>`;
  return container;
}

function injectWaveNextToMic() {
  const btn = elements.btnToggleMic;
  if (!btn) return;
  let container = document.getElementById('micWaveVisualizer');
  if (!container) {
    container = createWaveContainer();
    btn.parentElement.insertBefore(container, btn.nextSibling);
  }
  return container;
}

export function startMicVisualizer(stream) {
  stopMicVisualizer();
  const audioTracks = stream.getAudioTracks();
  if (!audioTracks.length || !audioTracks[0].enabled) return;

  const container = injectWaveNextToMic();
  if (!container) return;
  container.classList.add('active');

  try {
    micAnalyserCtx = new (window.AudioContext || window.webkitAudioContext)();
    micAnalyser = micAnalyserCtx.createAnalyser();
    micAnalyser.fftSize = 64;
    micSource = micAnalyserCtx.createMediaStreamSource(stream);
    micSource.connect(micAnalyser);
    // Do NOT connect to destination — we don't want local playback

    const bars = container.querySelectorAll('.mic-wave-bar');
    const dataArray = new Uint8Array(micAnalyser.frequencyBinCount);

    function draw() {
      micAnimFrame = requestAnimationFrame(draw);
      micAnalyser.getByteFrequencyData(dataArray);

      // Pick 5 bands spread across the spectrum
      const step = Math.floor(dataArray.length / bars.length);
      bars.forEach((bar, i) => {
        const value = dataArray[i * step] / 255;
        const height = Math.max(4, value * 28);
        bar.style.height = `${height}px`;
        bar.style.opacity = Math.max(0.3, value);
      });
    }
    draw();
  } catch (e) {
    console.warn('Mic visualizer not available:', e);
  }
}

export function stopMicVisualizer() {
  if (micAnimFrame) {
    cancelAnimationFrame(micAnimFrame);
    micAnimFrame = null;
  }
  if (micSource) {
    micSource.disconnect();
    micSource = null;
  }
  if (micAnalyserCtx) {
    micAnalyserCtx.close().catch(() => {});
    micAnalyserCtx = null;
  }
  micAnalyser = null;
  const container = document.getElementById('micWaveVisualizer');
  if (container) {
    container.classList.remove('active');
    container.querySelectorAll('.mic-wave-bar').forEach(bar => {
      bar.style.height = '4px';
      bar.style.opacity = '0.3';
    });
  }
}

export function setRemoteStream(peerSid, stream) {
  state.remoteStreams.set(peerSid, stream);
  state.activeRemoteSid = peerSid;

  let container = document.querySelector(`.video-container.remote[data-peer="${peerSid}"]`);
  if (!container) {
    const staticContainer = document.querySelector('.video-container.remote:not(.dynamic-remote)');
    const isStaticFree = staticContainer && !staticContainer.hasAttribute('data-peer');
    
    if (isStaticFree) {
      container = staticContainer;
      container.setAttribute('data-peer', peerSid);
      elements.remoteVideo.srcObject = stream;
      elements.remotePlaceholder.classList.add("hidden");
      const peer = state.peerMetadata.get(peerSid);
      const label = peer ? `${peer.name} (${peer.role})` : "Connected peer";
      elements.remoteLabel.innerHTML = `<i class="fa-solid fa-lock"></i> <span>${label}</span>`;
    } else {
      container = document.createElement('article');
      container.className = 'video-container remote dynamic-remote';
      container.id = `remote-container-${peerSid}`;
      container.setAttribute('data-peer', peerSid);
      
      container.innerHTML = `
        <video id="remote-video-${peerSid}" autoplay playsinline></video>
        <div id="remote-placeholder-${peerSid}" class="video-placeholder hidden"></div>
        <div class="video-overlay">
          <div class="video-badge">
            <span id="remote-label-${peerSid}"></span>
          </div>
          <div class="video-badge neon-badge">
            <i class="fa-solid fa-language"></i>
            <span id="remote-gesture-${peerSid}">NO_DATA_RX</span>
          </div>
        </div>
      `;
      document.querySelector('.video-grid').appendChild(container);
      
      container.querySelector('video').srcObject = stream;
      const peer = state.peerMetadata.get(peerSid);
      const label = peer ? `${peer.name} (${peer.role})` : "Connected peer";
      container.querySelector(`#remote-label-${peerSid}`).innerHTML = `<i class="fa-solid fa-lock"></i> <span>${label}</span>`;
    }
  } else {
    if (container.classList.contains('dynamic-remote')) {
      container.querySelector('video').srcObject = stream;
    } else {
      elements.remoteVideo.srcObject = stream;
    }
  }

  elements.mediaStatus.textContent = "WebRTC connected";
}

export function maybeDisplayAnotherRemote() {
  if (state.remoteStreams.size === 0) {
    state.activeRemoteSid = null;
    elements.mediaStatus.textContent = "WebRTC waiting";
  }
}

export async function initializeLocalMedia() {
  const wantsVideo = state.currentRole === "signer" || state.mediaPrefs.video;
  const wantsAudio = state.mediaPrefs.audio;
  if (!wantsVideo && !wantsAudio) {
    state.localStream = new MediaStream();
    elements.localVideo.srcObject = state.localStream;
    elements.localPlaceholder.textContent = "Camera and microphone are off. You can enable them anytime.";
    elements.localPlaceholder.classList.remove("hidden");
    stopIslCapture();
    elements.islOverlayCanvas.classList.add("hidden");
    clearIslOverlay();
    elements.islStatusBadge.innerHTML =
      '<i class="fa-solid fa-eye"></i> <span>Receive-only mode</span>';
    updateMediaToggleButtons();
    return state.localStream;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: wantsVideo
        ? {
            width: { ideal: 1280 },
            height: { ideal: 720 },
          }
        : false,
      audio: wantsAudio,
    });
    state.localStream = stream;
    state.localVideoEnabled = stream.getVideoTracks().some((track) => track.enabled);
    state.localAudioEnabled = stream.getAudioTracks().some((track) => track.enabled);
    elements.localVideo.srcObject = stream;
    if (state.localVideoEnabled) {
      elements.localPlaceholder.classList.add("hidden");
    } else {
      elements.localPlaceholder.textContent = "Microphone is on. Camera is off.";
      elements.localPlaceholder.classList.remove("hidden");
    }
    elements.mediaStatus.textContent = "Camera ready";
    if (state.currentRole === "signer" && state.localVideoEnabled) {
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
    updateMediaToggleButtons();
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

export async function ensureLocalTracks(peerConnection, peerSid) {
  if (!state.localStream) {
    return;
  }

  peerConnection.__addedTrackIds = peerConnection.__addedTrackIds || new Set();
  state.localStream.getTracks().forEach((track) => {
    if (peerConnection.__addedTrackIds.has(track.id)) {
      return;
    }
    peerConnection.addTrack(track, state.localStream);
    peerConnection.__addedTrackIds.add(track.id);
  });
  state.peerMetadata.set(peerSid, state.peerMetadata.get(peerSid) || {});
}

export function ensureMediaTransceivers(peerConnection) {
  const transceivers = peerConnection.getTransceivers();
  const hasVideo = transceivers.some(
    (transceiver) => transceiver.receiver && transceiver.receiver.track.kind === "video"
  );
  const hasAudio = transceivers.some(
    (transceiver) => transceiver.receiver && transceiver.receiver.track.kind === "audio"
  );

  if (!hasVideo) {
    peerConnection.addTransceiver("video", {
      direction: state.localStream ? "sendrecv" : "recvonly",
    });
  }
  if (!hasAudio) {
    peerConnection.addTransceiver("audio", {
      direction: state.localStream ? "sendrecv" : "recvonly",
    });
  }
}

export function cleanupPeer(peerSid) {
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

  const container = document.querySelector(`.video-container.remote[data-peer="${peerSid}"]`);
  if (container) {
    if (container.classList.contains('dynamic-remote')) {
      container.remove();
    } else {
      container.removeAttribute('data-peer');
      elements.remoteVideo.srcObject = null;
      updateRemotePlaceholder("Waiting for a peer connection...");
      elements.remoteLabel.innerHTML = '<i class="fa-solid fa-user-group"></i> <span>No remote peer yet</span>';
    }
  }

  maybeDisplayAnotherRemote();
}

export function setupDataChannel(channel, peerSid) {
    channel.binaryType = "arraybuffer";
    channel.onmessage = async (event) => {
        let buffer;
        if (event.data instanceof Blob) {
           buffer = new Uint8Array(await event.data.arrayBuffer());
        } else {
           buffer = new Uint8Array(event.data);
        }
        try {
            const { plain } = await decryptPacketBuffer(buffer, state);
            const payloadStr = new TextDecoder().decode(plain);
            const payload = JSON.parse(payloadStr);
            
            const shouldProcess = await processInboundReliability(payload, peerSid);
            if (!shouldProcess) return;
            
            if (payload.type === "gesture_change") {
                const container = document.querySelector(`.video-container.remote[data-peer="${peerSid}"]`);
                if (container) {
                    if (container.classList.contains('dynamic-remote')) {
                        container.querySelector(`#remote-gesture-${peerSid}`).innerHTML =
                            `<span>${payload.sender}: ${payload.gesture}</span>`;
                    } else {
                        elements.remoteGestureBadge.innerHTML =
                            `<i class="fa-solid fa-language"></i> <span>${payload.sender}: ${payload.gesture}</span>`;
                    }
                }
                
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

export async function getOrCreatePeerConnection(peerSid, metadata = {}) {
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

export async function createOfferForPeer(peerSid, metadata = {}) {
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

export async function toggleLocalCamera() {
  if (state.localVideoEnabled) {
    setTrackEnabled("video", false);
    state.localVideoEnabled = false;
    elements.localPlaceholder.textContent = "Camera is off.";
    elements.localPlaceholder.classList.remove("hidden");
    if (state.currentRole === "signer") {
      stopIslCapture();
    }
    updateMediaToggleButtons();
    return;
  }

  const existingVideoTracks = state.localStream ? state.localStream.getVideoTracks() : [];
  if (existingVideoTracks.length > 0) {
    setTrackEnabled("video", true);
  } else {
    await addLocalTrack("video");
    await renegotiateAllPeers();
  }
  
  state.localVideoEnabled = true;
  elements.localPlaceholder.classList.add("hidden");
  if (state.currentRole === "signer") {
    startIslCapture();
  }
  updateMediaToggleButtons();
}

export async function toggleLocalMic() {
  if (state.localAudioEnabled) {
    setTrackEnabled("audio", false);
    state.localAudioEnabled = false;
    stopMicVisualizer();
    updateMediaToggleButtons();
    return;
  }

  const existingAudioTracks = state.localStream ? state.localStream.getAudioTracks() : [];
  const hasLiveTrack = existingAudioTracks.some(t => t.readyState === "live");

  if (hasLiveTrack) {
    setTrackEnabled("audio", true);
  } else {
    // Remove any ended tracks before adding fresh one
    existingAudioTracks.forEach(t => {
      t.stop();
      if (state.localStream) state.localStream.removeTrack(t);
    });
    // Clear stale track IDs from all peer connections
    for (const pc of state.peerConnections.values()) {
      if (pc.__addedTrackIds) {
        existingAudioTracks.forEach(t => pc.__addedTrackIds.delete(t.id));
      }
    }
    await addLocalTrack("audio");
    await replaceOrAddAudioTrackOnPeers();
  }

  state.localAudioEnabled = true;
  if (state.localStream) startMicVisualizer(state.localStream);
  updateMediaToggleButtons();
}

async function addLocalTrack(kind) {
  const constraints = kind === "video"
    ? { video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false }
    : { video: false, audio: true };
  const stream = await navigator.mediaDevices.getUserMedia(constraints);
  if (!state.localStream) {
    state.localStream = new MediaStream();
  }
  stream.getTracks().forEach((track) => state.localStream.addTrack(track));
  elements.localVideo.srcObject = state.localStream;
}

function setTrackEnabled(kind, enabled) {
  if (!state.localStream) return;
  state.localStream.getTracks().filter((track) => track.kind === kind).forEach((track) => {
    track.enabled = enabled;
  });
}

async function replaceOrAddAudioTrackOnPeers() {
  const newAudioTrack = state.localStream ? state.localStream.getAudioTracks()[0] : null;
  if (!newAudioTrack) return;

  for (const [peerSid, pc] of state.peerConnections.entries()) {
    const audioSender = pc.getSenders().find(s => s.track && s.track.kind === "audio");
    if (audioSender) {
      // Replace the track in-place — no renegotiation needed
      await audioSender.replaceTrack(newAudioTrack);
    } else {
      // No audio sender yet — add the track and renegotiate
      pc.addTrack(newAudioTrack, state.localStream);
      if (pc.__addedTrackIds) pc.__addedTrackIds.add(newAudioTrack.id);
      await createOfferForPeer(peerSid, state.peerMetadata.get(peerSid) || {});
    }
  }
}

async function renegotiateAllPeers() {
  for (const peerSid of state.peerConnections.keys()) {
    const pc = state.peerConnections.get(peerSid);
    await ensureLocalTracks(pc, peerSid);
    await createOfferForPeer(peerSid, state.peerMetadata.get(peerSid) || {});
  }
}

export function updateMediaToggleButtons() {
  if (elements.btnToggleCamera) {
    elements.btnToggleCamera.classList.toggle("active", state.localVideoEnabled);
    elements.btnToggleCamera.innerHTML = state.localVideoEnabled
      ? '<i class="fa-solid fa-video"></i>'
      : '<i class="fa-solid fa-video-slash"></i>';
    elements.btnToggleCamera.title = state.localVideoEnabled ? "Turn camera off" : "Turn camera on";
  }
  if (elements.btnToggleMic) {
    elements.btnToggleMic.classList.toggle("active", state.localAudioEnabled);
    elements.btnToggleMic.innerHTML = state.localAudioEnabled
      ? '<i class="fa-solid fa-microphone"></i>'
      : '<i class="fa-solid fa-microphone-slash"></i>';
    elements.btnToggleMic.title = state.localAudioEnabled ? "Mute microphone" : "Turn microphone on";
  }
}

export async function handleOffer(data) {
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

export async function handleAnswer(data) {
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

export async function handleIceCandidate(data) {
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
