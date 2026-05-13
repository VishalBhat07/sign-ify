export async function sha256Bytes(input) {
  const digest = await crypto.subtle.digest("SHA-256", input);
  return new Uint8Array(digest);
}

export function bytesToHex(bytes) {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export async function deriveSessionKey(roomId, password, epoch = 0) {
  const encoder = new TextEncoder();
  const passwordKey = await crypto.subtle.importKey(
    "raw",
    encoder.encode(password),
    "PBKDF2",
    false,
    ["deriveKey"]
  );
  const saltStr = `${roomId}_epoch_${epoch}`;
  const salt = await sha256Bytes(encoder.encode(saltStr));
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

export function bytesToBase64(bytes) {
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary);
}

export function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

export async function encryptPacket(plainBytes, sessionKey, stateObj) {
  let keyToUse = sessionKey;
  const baselineMode = stateObj && stateObj.transportMode === "baseline";
  if (stateObj && stateObj.epochKeys && stateObj.epochKeys.has(stateObj.currentEpoch)) {
      keyToUse = stateObj.epochKeys.get(stateObj.currentEpoch);
  }
  if (baselineMode) {
      keyToUse = sessionKey;
  }
  
  if (!keyToUse) {
    throw new Error("Session key not ready");
  }

  stateObj.cryptoSeqNum += 1;
  stateObj.packetCounter = (stateObj.packetCounter || 0) + 1;
  emitPacket({ id: stateObj.packetCounter, label: "CRITICAL", stage: "Packet Created", type: "Created" });
  emitPacket({ id: stateObj.packetCounter, label: "CRITICAL", stage: "Packet Classified", type: "Classified" });
  if (!baselineMode && stateObj.packetCounter > 1 && (stateObj.packetCounter - 1) % (stateObj.packetsPerEpoch || 32) === 0) {
    stateObj.currentEpoch += 1;
    const newKey = await deriveSessionKey(stateObj.roomId, stateObj.roomPassword, stateObj.currentEpoch);
    stateObj.epochKeys.set(stateObj.currentEpoch, newKey);
    emitDecision(`Epoch ${stateObj.currentEpoch - 1} -> Epoch ${stateObj.currentEpoch}: rolling key rotated`, "CONTROL");
  }

  const nonce = new Uint8Array(12);
  crypto.getRandomValues(nonce);
  const seqBytes = new Uint8Array(new Uint32Array([stateObj.cryptoSeqNum]).buffer);
  nonce.set(seqBytes.slice(0, 4), 0);

  const timestamp = new Uint8Array(8);
  const view = new DataView(timestamp.buffer);
  view.setBigUint64(0, BigInt(Math.floor(Date.now() / 1000)));

  const commitmentInput = new TextEncoder().encode(
    `${stateObj.commitmentHash || ""}:${stateObj.packetCounter}:CRITICAL:${stateObj.currentEpoch}`
  );
  stateObj.commitmentHash = bytesToHex(await sha256Bytes(commitmentInput));
  const header = {
    packet_id: stateObj.packetCounter,
    semantic_label: "CRITICAL",
    epoch_id: baselineMode ? 0 : stateObj.currentEpoch,
    packet_counter: stateObj.packetCounter,
    timestamp: Number(view.getBigUint64(0)),
    commitment_hash: stateObj.commitmentHash,
    policy_fingerprint: stateObj.policyFingerprint || "",
    parity_group: null
  };
  stateObj.latestPacketHeader = header;
  if (stateObj.transportStats && stateObj.transportStats.classCounts) {
    stateObj.transportStats.classCounts.CRITICAL += 1;
  }
  const headerBytes = new TextEncoder().encode(JSON.stringify(header));
  emitPacket({ id: header.packet_id, label: header.semantic_label, stage: "Scheduled", type: "Scheduled" });

  const ciphertext = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv: nonce,
      additionalData: concatBytes(headerBytes, timestamp),
    },
    keyToUse,
    plainBytes
  );

  const cipherBytes = new Uint8Array(ciphertext);
  emitPacket({ id: header.packet_id, label: header.semantic_label, stage: "Encrypted", type: "Encrypted" });
  emitDecision(
    baselineMode
      ? "Baseline packet: static AES session -> no adaptive priority or replay visualization"
      : "Packet classified as CRITICAL -> parity enabled -> retransmission enabled",
    header.semantic_label
  );
  const packet = new Uint8Array(4 + headerBytes.length + nonce.length + cipherBytes.length + timestamp.length);
  new DataView(packet.buffer).setUint32(0, headerBytes.length, false);
  packet.set(headerBytes, 4);
  packet.set(nonce, 4 + headerBytes.length);
  packet.set(cipherBytes, 4 + headerBytes.length + nonce.length);
  packet.set(timestamp, 4 + headerBytes.length + nonce.length + cipherBytes.length);
  return packet;
}

export async function decryptPacket(base64Payload, sessionKey) {
  if (!sessionKey) {
    throw new Error("Session key not ready");
  }

  const packet = base64ToBytes(base64Payload);
  if (packet.length < 40) {
    throw new Error("Encrypted payload too short");
  }

  const nonce = packet.slice(4, 16);
  const timestamp = packet.slice(packet.length - 8);
  const ciphertext = packet.slice(16, packet.length - 8);
  const plain = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv: nonce,
      additionalData: timestamp,
    },
    sessionKey,
    ciphertext
  );
  return new Uint8Array(plain);
}

export async function decryptPacketBuffer(buffer, stateObj) {
  const packet = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  if (packet.length < 40) {
    throw new Error("Encrypted payload too short");
  }
  const headerLength = new DataView(packet.buffer, packet.byteOffset, packet.byteLength).getUint32(0, false);
  const headerStart = 4;
  const headerEnd = headerStart + headerLength;
  const headerBytes = packet.slice(headerStart, headerEnd);
  const header = JSON.parse(new TextDecoder().decode(headerBytes));
  if (stateObj.policyFingerprint && header.policy_fingerprint && header.policy_fingerprint !== stateObj.policyFingerprint) {
    throw new Error("Policy fingerprint mismatch");
  }
  if (header.epoch_id < stateObj.currentEpoch - (stateObj.epochGrace || 1)) {
    if (stateObj.transportStats) stateObj.transportStats.replayRejected += 1;
    throw new Error("Stale epoch");
  }
  stateObj.latestPacketHeader = header;
  emitPacket({ id: header.packet_id, label: header.semantic_label, stage: "Verified", type: "Received" });
  emitIntegrity(header, true);
  if (stateObj.transportStats && stateObj.transportStats.classCounts && header.semantic_label) {
    const label = header.semantic_label in stateObj.transportStats.classCounts ? header.semantic_label : "BEST_EFFORT";
    stateObj.transportStats.classCounts[label] += 1;
  }
  const key = stateObj.epochKeys.has(header.epoch_id)
    ? stateObj.epochKeys.get(header.epoch_id)
    : stateObj.sessionKey;
  const nonce = packet.slice(headerEnd, headerEnd + 12);
  const timestamp = packet.slice(packet.length - 8);
  const ciphertext = packet.slice(headerEnd + 12, packet.length - 8);
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: nonce, additionalData: concatBytes(headerBytes, timestamp) },
    key,
    ciphertext
  );
  emitPacket({ id: header.packet_id, label: header.semantic_label, stage: "Accepted", type: "Accepted" });
  return { plain: new Uint8Array(plain), header };
}

function concatBytes(first, second) {
  const combined = new Uint8Array(first.length + second.length);
  combined.set(first, 0);
  combined.set(second, first.length);
  return combined;
}

function emitPacket(detail) {
  window.dispatchEvent(new CustomEvent("secusignflow:packet", { detail }));
}

function emitDecision(text, label) {
  window.dispatchEvent(new CustomEvent("secusignflow:decision", { detail: { text, label } }));
}

function emitIntegrity(header, valid) {
  window.dispatchEvent(new CustomEvent("secusignflow:integrity", { detail: { header, valid } }));
}
