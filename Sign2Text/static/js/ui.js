import { elements } from './state.js';

export function showToast(message, timeoutMs = 2600) {
  elements.toast.textContent = message;
  elements.toast.classList.remove("hidden");
  window.clearTimeout(showToast.timerId);
  showToast.timerId = window.setTimeout(() => {
    elements.toast.classList.add("hidden");
  }, timeoutMs);
}

export function showTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach((button) => {
    button.classList.toggle("active", button.dataset.tabTarget === tabName);
  });
  elements.createTab.classList.toggle("active", tabName === "create");
  elements.joinTab.classList.toggle("active", tabName === "join");
}

export function getSelectedRole(groupName) {
  const selected = document.querySelector(
    `[data-role-group="${groupName}"] .role-option.selected`
  );
  return selected ? selected.dataset.role : "";
}

export function setParticipantCount(count) {
  elements.participantCount.textContent = String(count);
}

export function speakText(text) {
  if (!("speechSynthesis" in window) || !text) {
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.92;
  utterance.pitch = 1;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

export function updateRemotePlaceholder(message) {
  elements.remotePlaceholder.textContent = message;
  elements.remotePlaceholder.classList.remove("hidden");
  elements.remoteVideo.srcObject = null;
}

export function clearIslOverlay() {
  elements.islRenderedOverlay.removeAttribute("src");
  elements.islRenderedOverlay.classList.add("hidden");
}

export function addMessage(message) {
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

export function addSystemMessage(text) {
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

export function resetRoomCreatedState() {
  elements.roomCreated.classList.add("hidden");
  elements.btnCreate.classList.remove("hidden");
}

export function setRecordingState(isRecording, stateObj) {
  stateObj.isRecording = isRecording;
  elements.btnVoice.classList.toggle("recording", isRecording);
  elements.btnVoice.innerHTML = isRecording
    ? '<i class="fa-solid fa-stop"></i>'
    : '<i class="fa-solid fa-microphone"></i>';
  elements.btnVoice.title = isRecording ? "Stop recording" : "Record and send";
}
