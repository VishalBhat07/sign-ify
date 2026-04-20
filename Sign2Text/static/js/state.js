export const socket = window.io();

export const state = {
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
  sessionKey: null,
  cryptoSeqNum: 0,
  recognition: null,
  isRecording: false,
  signalingReady: false,
  pendingSignals: [],
};

export const inferenceState = {
  ortSession: null,
  handsTracking: null,
  cameraInstance: null,
  currentGesture: null,
  gestureStartTime: 0
};

export const labelsDict = {
    0: 'A', 1: 'B', 2: 'C', 3: 'D', 4: 'E', 5: 'F', 6: 'G', 7: 'H', 8: 'I', 9: 'J', 
    10: 'K', 11: 'L', 12: 'M', 13: 'N', 14: 'O', 15: 'P', 16: 'Q', 17: 'R', 18: 'S', 
    19: 'T', 20: 'U', 21: 'V', 22: 'W', 23: 'X', 24: 'Y', 25: 'Z', 26: 'Hello', 
    27: 'Done', 28: 'Thank You', 29: 'I Love you', 30: 'Sorry', 31: 'Please', 32: 'You are welcome.'
};

export const elements = {
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
