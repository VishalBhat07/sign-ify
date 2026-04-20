export async function sha256Bytes(input) {
  const digest = await crypto.subtle.digest("SHA-256", input);
  return new Uint8Array(digest);
}

export async function deriveSessionKey(roomId, password) {
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
  if (!sessionKey) {
    throw new Error("Session key not ready");
  }

  stateObj.cryptoSeqNum += 1;
  const nonce = new Uint8Array(12);
  crypto.getRandomValues(nonce);
  const seqBytes = new Uint8Array(new Uint32Array([stateObj.cryptoSeqNum]).buffer);
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
    sessionKey,
    plainBytes
  );

  const cipherBytes = new Uint8Array(ciphertext);
  const packet = new Uint8Array(nonce.length + cipherBytes.length + timestamp.length);
  packet.set(nonce, 0);
  packet.set(cipherBytes, nonce.length);
  packet.set(timestamp, nonce.length + cipherBytes.length);
  return packet;
}

export async function decryptPacket(base64Payload, sessionKey) {
  if (!sessionKey) {
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
    sessionKey,
    ciphertext
  );
  return new Uint8Array(plain);
}
