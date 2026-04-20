import { state, elements, socket } from './state.js';
import { decryptPacket } from './crypto.js';
import { addMessage, updateRemotePlaceholder, showToast, clearIslOverlay } from './ui.js';
import { startIslCapture, stopIslCapture } from './inference.js';

export function setRemoteStream(peerSid, stream) {
  state.remoteStreams.set(peerSid, stream);
  state.activeRemoteSid = peerSid;
  elements.remoteVideo.srcObject = stream;
  elements.remotePlaceholder.classList.add("hidden");
  const peer = state.peerMetadata.get(peerSid);
  const label = peer ? `${peer.name} (${peer.role})` : "Connected peer";
  elements.remoteLabel.innerHTML = `<i class="fa-solid fa-lock"></i> <span>${label}</span>`;
  elements.mediaStatus.textContent = "WebRTC connected";
}

export function maybeDisplayAnotherRemote() {
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

export async function initializeLocalMedia() {
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

export async function ensureLocalTracks(peerConnection, peerSid) {
  if (peerConnection.__tracksAdded || !state.localStream) {
    return;
  }

  state.localStream.getTracks().forEach((track) => {
    peerConnection.addTrack(track, state.localStream);
  });
  peerConnection.__tracksAdded = true;
  state.peerMetadata.set(peerSid, state.peerMetadata.get(peerSid) || {});
}

export function ensureMediaTransceivers(peerConnection) {
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
  if (state.activeRemoteSid === peerSid) {
    maybeDisplayAnotherRemote();
  }
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
