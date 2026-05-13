import { state, socket } from "./state.js";
import { reliabilityState, networkSimulator } from "./reliability.js";
import { showToast } from "./ui.js";

const FLOW_STAGES = [
  "Packet Created",
  "Packet Classified",
  "Scheduled",
  "Encrypted",
  "Sent",
  "Verified",
  "Recovered",
  "Accepted",
  "Rejected"
];

const CLASS_META = {
  CONTROL: { color: "#4ea3ff", icon: "fa-sitemap" },
  CRITICAL: { color: "#ff4d5e", icon: "fa-triangle-exclamation" },
  INTERACTIVE: { color: "#ffd84d", icon: "fa-hand-pointer" },
  BEST_EFFORT: { color: "#9b9b9b", icon: "fa-layer-group" },
  RECOVERED: { color: "#36d67a", icon: "fa-screwdriver-wrench" },
  REJECTED: { color: "#8b0000", icon: "fa-ban" }
};

export function initDemoPanels() {
  const host = document.getElementById("advancedDemoPanels");
  if (!host) return;

  host.innerHTML = `
    <section class="dashboard-group demo-panel">
      <h4>Demo Mode</h4>
      <div class="mode-toggle" role="group" aria-label="Transport demo mode">
        <button type="button" data-demo-mode="baseline">Baseline Mode</button>
        <button type="button" data-demo-mode="secusignflow" class="active">SecuSignFlow Mode</button>
      </div>
      <div id="baselineComparisonPanel" class="comparison-grid"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Packet Flow</h4>
      <div id="packetFlowVisualizer" class="packet-flow"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Epoch Monitor</h4>
      <div id="epochMonitor"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Replay Attack</h4>
      <div class="demo-button-row">
        <button type="button" id="btnReplayLastPacket" title="Replay last packet"><i class="fa-solid fa-repeat"></i></button>
        <button type="button" id="btnDuplicatePacket" title="Inject duplicate packet"><i class="fa-solid fa-clone"></i></button>
        <button type="button" id="btnStalePacket" title="Simulate stale packet"><i class="fa-solid fa-clock-rotate-left"></i></button>
      </div>
      <div id="replayAttackPanel" class="security-strip"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Recovery</h4>
      <div id="recoveryVisualizer" class="recovery-view"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Reliability State</h4>
      <div id="reliabilityStatePanel"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Packet Timeline</h4>
      <div id="packetTimeline" class="packet-timeline"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Security Dashboard</h4>
      <div id="securityDashboard" class="security-dashboard"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Packet Heatmap</h4>
      <div id="packetHeatmap" class="packet-heatmap"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Decision Log</h4>
      <div id="decisionLogPanel" class="decision-log"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Integrity Chain</h4>
      <div id="integrityChainView" class="integrity-chain"></div>
    </section>

    <section class="dashboard-group demo-panel">
      <h4>Session Resync</h4>
      <div class="demo-button-row">
        <button type="button" id="btnEpochMismatch" title="Force epoch mismatch"><i class="fa-solid fa-code-compare"></i></button>
        <button type="button" id="btnBadCommitment" title="Invalidate commitment chain"><i class="fa-solid fa-link-slash"></i></button>
        <button type="button" id="btnTriggerResync" title="Trigger resync"><i class="fa-solid fa-rotate"></i></button>
      </div>
      <div id="sessionResyncPanel" class="resync-flow"></div>
    </section>
  `;

  document.querySelectorAll("[data-demo-mode]").forEach((button) => {
    button.addEventListener("click", () => setDemoMode(button.dataset.demoMode));
  });
  bindDebugButton("btnReplayLastPacket", "replay_last_packet");
  bindDebugButton("btnDuplicatePacket", "inject_duplicate_packet");
  bindDebugButton("btnStalePacket", "simulate_stale_packet");
  bindDebugButton("btnEpochMismatch", "force_epoch_mismatch");
  bindDebugButton("btnBadCommitment", "invalidate_commitment_chain");
  bindDebugButton("btnTriggerResync", "trigger_resync");

  socket.on("transport_demo_event", (event) => {
    applyDebugEvent(event);
    renderDemoPanels();
  });
  window.addEventListener("secusignflow:packet", (event) => {
    recordPacketEvent(event.detail || {});
    renderDemoPanels();
  });
  window.addEventListener("secusignflow:decision", (event) => {
    const detail = event.detail || {};
    recordDecision(detail.text || "Transport decision recorded", detail.label || "CRITICAL");
    renderDemoPanels();
  });
  window.addEventListener("secusignflow:integrity", (event) => {
    const detail = event.detail || {};
    recordIntegrity(detail.header, detail.valid !== false);
    renderDemoPanels();
  });
  window.addEventListener("secusignflow:recovery", (event) => {
    recordRecovery(event.detail || {});
    renderDemoPanels();
  });
  setInterval(renderDemoPanels, 800);
  renderDemoPanels();
}

export function recordPacketEvent(packet) {
  const label = packet.label || "CRITICAL";
  const entry = {
    id: packet.id || state.packetCounter || state.packetFlow.length + 1,
    label,
    stage: packet.stage || "Packet Created",
    status: packet.status || "active",
    timestamp: new Date().toLocaleTimeString(),
    reason: packet.reason || "",
    parityGroup: packet.parityGroup || null
  };
  upsertLimited(state.packetFlow, entry, 8);
  state.packetTimeline.push({ ...entry, type: packet.type || entry.stage });
  limit(state.packetTimeline, 28);
}

export function recordDecision(text, label = "CRITICAL") {
  state.decisionLog.unshift({
    text,
    label,
    timestamp: new Date().toLocaleTimeString()
  });
  limit(state.decisionLog, 12);
}

export function recordIntegrity(header, valid = true) {
  if (!header) return;
  state.integrityChain.push({
    id: header.packet_id || header.packet_counter,
    epoch: header.epoch_id,
    valid,
    hash: String(header.commitment_hash || "").slice(0, 8)
  });
  limit(state.integrityChain, 10);
}

export function recordRecovery(event = {}) {
  const recovery = {
    groupId: event.groupId || event.parity_group || Math.max(1, Math.ceil((state.packetCounter || 1) / 3)),
    missingPacketId: event.missingPacketId || event.packetId || state.packetCounter,
    result: event.result || "Packet Reconstructed",
    valid: event.valid !== false,
    timestamp: new Date().toLocaleTimeString()
  };
  state.recoveryEvents.unshift(recovery);
  limit(state.recoveryEvents, 5);
  state.transportStats.recovered += 1;
  recordPacketEvent({
    id: recovery.missingPacketId,
    label: "RECOVERED",
    stage: "Recovered",
    status: "recovered",
    type: "Recovered",
    parityGroup: recovery.groupId
  });
  recordDecision(`Packet ${recovery.missingPacketId} lost -> parity group ${recovery.groupId} used -> integrity verified`, "RECOVERED");
}

export function renderDemoPanels() {
  renderComparison();
  renderPacketFlow();
  renderEpochMonitor();
  renderReplayPanel();
  renderRecovery();
  renderReliability();
  renderTimeline();
  renderSecurityDashboard();
  renderHeatmap();
  renderDecisionLog();
  renderIntegrityChain();
  renderResync();
}

function setDemoMode(mode) {
  state.transportMode = mode;
  document.querySelectorAll("[data-demo-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.demoMode === mode);
  });
  if (mode === "baseline") {
    recordDecision("Baseline Mode: static AES session, no rolling keys, no adaptive scheduling, no verified recovery", "BEST_EFFORT");
  } else {
    recordDecision("SecuSignFlow Mode: rolling epochs, semantic scheduling, replay rejection, verified recovery", "CONTROL");
  }
  renderDemoPanels();
}

function bindDebugButton(id, action) {
  const button = document.getElementById(id);
  if (!button) return;
  button.addEventListener("click", () => {
    if (!state.roomId || !state.authToken) {
      applyDebugEvent({ action, status: "simulated", reason: "Local deterministic demo event" });
      renderDemoPanels();
      return;
    }
    socket.emit("transport_debug_action", {
      room: state.roomId,
      token: state.authToken,
      action
    });
  });
}

function applyDebugEvent(event) {
  const action = event.action || "debug_event";
  const reason = event.reason || "Rejected by replay or integrity guard";
  if (action.includes("replay") || action.includes("duplicate") || action.includes("stale")) {
    state.transportStats.replayRejected += 1;
    state.transportStats.rejected += 1;
    recordPacketEvent({
      id: event.packet_id || state.packetCounter || 1,
      label: "REJECTED",
      stage: "Rejected",
      status: "rejected",
      type: action.includes("stale") ? "Stale Replay" : "Replayed",
      reason
    });
    recordDecision(`Replay rejection: ${reason}`, "REJECTED");
    showToast("Replay packet rejected by transport guard.", 2600);
  }
  if (action === "simulate_stale_packet") {
    state.resyncState.failures += 1;
  }
  if (action === "force_epoch_mismatch") {
    state.resyncState = { stage: "Integrity Failure", failures: state.resyncState.failures + 1 };
    recordDecision("Epoch mismatch detected -> packet rejected outside grace policy", "REJECTED");
  }
  if (action === "invalidate_commitment_chain") {
    state.resyncState = { stage: "Threshold Exceeded", failures: state.resyncState.failures + 1 };
    recordIntegrity({ packet_id: state.packetCounter || 1, epoch_id: state.currentEpoch, commitment_hash: "broken" }, false);
    recordDecision("Integrity chain broken -> resync threshold counter advanced", "REJECTED");
  }
  if (action === "trigger_resync") {
    state.resyncState = { stage: "Session Restored", failures: 0 };
    recordDecision("Session resync triggered -> epoch resynchronized -> session restored", "CONTROL");
  }
}

function renderComparison() {
  const panel = document.getElementById("baselineComparisonPanel");
  if (!panel) return;
  const loss = networkSimulator.packetLossPct;
  const secuRecovery = loss > 0 ? "Verified parity + ACK" : "Ready";
  const rows = [
    ["Packet Loss Recovery", "None", secuRecovery],
    ["Replay Rejection", "Duplicate unseen", `${state.transportStats.replayRejected} rejected`],
    ["Retransmissions", "Manual retry", reliabilityState.stats.retransmissions],
    ["Packet Continuity", "Best effort", state.integrityChain.every((item) => item.valid) ? "Valid" : "Broken"],
    ["RTT Impact", `${networkSimulator.baseDelayMs} ms static`, `${networkSimulator.baseDelayMs + Math.round(networkSimulator.jitterMs / 2)} ms adaptive`],
    ["Critical Packet Delivery", loss > 10 ? "Degraded" : "Normal", loss > 10 ? "Protected" : "Prioritized"]
  ];
  panel.innerHTML = rows.map(([metric, base, secu]) => `
    <div class="comparison-row">
      <span>${metric}</span><b>${base}</b><strong>${secu}</strong>
    </div>
  `).join("");
}

function renderPacketFlow() {
  const panel = document.getElementById("packetFlowVisualizer");
  if (!panel) return;
  const latest = state.packetFlow[0] || { id: "-", label: "CONTROL", stage: "Packet Created" };
  const activeIndex = Math.max(0, FLOW_STAGES.indexOf(latest.stage));
  panel.innerHTML = `
    <div class="flow-card" style="--packet-color:${classColor(latest.label)}">
      <div><span>Packet ${latest.id}</span><b>${latest.label}</b></div>
      <small>${latest.reason || latest.stage}</small>
    </div>
    <div class="flow-rail">
      ${FLOW_STAGES.map((stage, index) => `
        <span class="${index <= activeIndex ? "active" : ""} ${stage === "Rejected" && latest.status === "rejected" ? "rejected" : ""}">
          ${stage.replace("Packet ", "")}
        </span>
      `).join("")}
    </div>
  `;
}

function renderEpochMonitor() {
  const panel = document.getElementById("epochMonitor");
  if (!panel) return;
  const used = state.packetCounter % state.packetsPerEpoch;
  const remaining = state.packetsPerEpoch - used;
  const pct = Math.round((used / state.packetsPerEpoch) * 100);
  panel.innerHTML = `
    <div class="epoch-path">
      <span>Epoch ${Math.max(0, state.currentEpoch - 1)}</span>
      <i class="fa-solid fa-arrow-right"></i>
      <strong>Epoch ${state.currentEpoch}</strong>
      <i class="fa-solid fa-arrow-right"></i>
      <span>Epoch ${state.currentEpoch + 1}</span>
    </div>
    <div class="progress-bar"><i style="width:${pct}%"></i></div>
    <div class="metric-row"><span>Packets before rotation</span><span>${remaining}</span></div>
    <div class="metric-row"><span>Replay window</span><span>${state.transportMode === "baseline" ? "Disabled" : "64 counters"}</span></div>
    <div class="metric-row"><span>Previous epoch grace</span><span>${state.transportMode === "baseline" ? "Off" : `${state.epochGrace} epoch`}</span></div>
  `;
}

function renderReplayPanel() {
  const panel = document.getElementById("replayAttackPanel");
  if (!panel) return;
  panel.innerHTML = `
    <span class="${state.transportStats.replayRejected ? "ok" : "warn"}">Integrity ${state.transportStats.replayRejected ? "Guarded" : "Ready"}</span>
    <span>Replay Count ${state.transportStats.replayRejected}</span>
  `;
}

function renderRecovery() {
  const panel = document.getElementById("recoveryVisualizer");
  if (!panel) return;
  const latest = state.recoveryEvents[0];
  if (!latest) {
    panel.innerHTML = `<div class="empty-mini">Packet Lost -> Parity Used -> Packet Reconstructed -> Integrity Verified</div>`;
    return;
  }
  panel.innerHTML = `
    <div class="recovery-flow">Packet Lost <i class="fa-solid fa-arrow-right"></i> Parity Used <i class="fa-solid fa-arrow-right"></i> Packet Reconstructed <i class="fa-solid fa-arrow-right"></i> Integrity Verified</div>
    <div class="metric-row"><span>Parity Group</span><span>${latest.groupId}</span></div>
    <div class="metric-row"><span>Missing Packet</span><span>${latest.missingPacketId}</span></div>
    <div class="metric-row"><span>Validation</span><span>${latest.valid ? "Verified" : "Failed"}</span></div>
  `;
}

function renderReliability() {
  const panel = document.getElementById("reliabilityStatePanel");
  if (!panel) return;
  const loss = networkSimulator.packetLossPct;
  const protectedMode = state.transportMode === "secusignflow" && loss >= 10;
  panel.innerHTML = `
    <div class="mode-banner ${protectedMode ? "protected" : ""}">
      <span>Loss = ${loss}%</span>
      <strong>Mode = ${protectedMode ? "Protected Critical Transport" : "Normal"}</strong>
    </div>
    <div class="metric-row"><span>Redundancy</span><span>${protectedMode ? "Increased" : "Normal"}</span></div>
    <div class="metric-row"><span>Retransmission</span><span>${protectedMode ? "Enabled" : "Policy"}</span></div>
    <div class="metric-row"><span>Scheduler</span><span>${state.transportMode === "baseline" ? "Static" : "Adaptive"}</span></div>
    <div class="metric-row"><span>Parity</span><span>${protectedMode ? "Active" : "Standby"}</span></div>
    <div class="metric-row"><span>BEST_EFFORT</span><span>${protectedMode ? "Deprioritized" : "Normal"}</span></div>
  `;
}

function renderTimeline() {
  const panel = document.getElementById("packetTimeline");
  if (!panel) return;
  panel.innerHTML = state.packetTimeline.slice(-16).map((item) => `
    <div class="timeline-chip" style="--packet-color:${classColor(item.label)}">
      <i class="fa-solid ${CLASS_META[item.label]?.icon || "fa-circle"}"></i>
      <b>${item.id}</b>
      <span>${item.type}</span>
      <small>${item.timestamp}</small>
    </div>
  `).join("") || `<div class="empty-mini">Timeline waiting for packets.</div>`;
  panel.scrollLeft = panel.scrollWidth;
}

function renderSecurityDashboard() {
  const panel = document.getElementById("securityDashboard");
  if (!panel) return;
  const chainValid = state.integrityChain.every((item) => item.valid);
  const cards = [
    ["Policy Verified", Boolean(state.policyFingerprint)],
    ["Epoch Synced", state.resyncState.stage !== "Integrity Failure"],
    ["Replay Window Healthy", state.transportMode !== "baseline"],
    ["Integrity Chain Valid", chainValid],
    ["Recovery Active", state.transportMode === "secusignflow"]
  ];
  panel.innerHTML = cards.map(([label, ok]) => `<div class="${ok ? "ok" : "warn"}"><span>${label}</span><b>${ok ? "OK" : "Watch"}</b></div>`).join("");
}

function renderHeatmap() {
  const panel = document.getElementById("packetHeatmap");
  if (!panel) return;
  const counts = state.transportStats.classCounts;
  const max = Math.max(1, ...Object.values(counts));
  panel.innerHTML = Object.entries(counts).map(([label, count]) => `
    <div class="heat-row">
      <span>${label}</span>
      <i style="--packet-color:${classColor(label)};width:${Math.max(8, (count / max) * 100)}%"></i>
      <b>${count}</b>
    </div>
  `).join("");
}

function renderDecisionLog() {
  const panel = document.getElementById("decisionLogPanel");
  if (!panel) return;
  panel.innerHTML = state.decisionLog.map((item) => `
    <div style="--packet-color:${classColor(item.label)}">
      <small>${item.timestamp}</small>
      <span>${item.text}</span>
    </div>
  `).join("") || `<div class="empty-mini">Scheduler reasoning will appear here.</div>`;
}

function renderIntegrityChain() {
  const panel = document.getElementById("integrityChainView");
  if (!panel) return;
  panel.innerHTML = state.integrityChain.map((item) => `
    <span class="${item.valid ? "" : "broken"}">P${item.id}<small>E${item.epoch}</small></span>
  `).join(`<i class="fa-solid fa-arrow-right"></i>`) || `<div class="empty-mini">Packet 1 -> Packet 2 -> Packet 3</div>`;
}

function renderResync() {
  const panel = document.getElementById("sessionResyncPanel");
  if (!panel) return;
  const stages = ["Integrity Failure", "Threshold Exceeded", "Session Resync Triggered", "Epoch Resynchronized", "Session Restored"];
  const active = Math.max(0, stages.indexOf(state.resyncState.stage));
  panel.innerHTML = stages.map((stage, index) => `
    <span class="${index <= active ? "active" : ""}">${stage}</span>
  `).join("");
}

function upsertLimited(list, entry, max) {
  const existing = list.findIndex((item) => item.id === entry.id);
  if (existing >= 0) {
    list.splice(existing, 1);
  }
  list.unshift(entry);
  limit(list, max);
}

function limit(list, max) {
  if (list.length > max) list.splice(max);
}

function classColor(label) {
  return CLASS_META[label]?.color || CLASS_META.BEST_EFFORT.color;
}
