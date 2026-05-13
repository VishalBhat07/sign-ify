import { state } from './state.js';
import { reliabilityState, networkSimulator } from './reliability.js';

export function initDashboard() {
    // Input Mappings
    const packetLossInput = document.getElementById("simPacketLoss");
    const delayInput = document.getElementById("simDelay");
    const jitterInput = document.getElementById("simJitter");
    
    if (packetLossInput) {
        packetLossInput.addEventListener("input", (e) => {
            setPacketLoss(parseInt(e.target.value) || 0);
        });
    }

    document.querySelectorAll("[data-loss-preset]").forEach((button) => {
        button.addEventListener("click", () => setPacketLoss(parseInt(button.dataset.lossPreset) || 0));
    });
    
    if (delayInput) {
        delayInput.addEventListener("input", (e) => {
            networkSimulator.baseDelayMs = parseInt(e.target.value) || 0;
            document.getElementById("simDelayLabel").innerText = `${networkSimulator.baseDelayMs}ms`;
        });
    }
    
    if (jitterInput) {
        jitterInput.addEventListener("input", (e) => {
            networkSimulator.jitterMs = parseInt(e.target.value) || 0;
            document.getElementById("simJitterLabel").innerText = `${networkSimulator.jitterMs}ms`;
        });
    }

    const exportButton = document.getElementById("btnExportMetrics");
    if (exportButton) {
        exportButton.addEventListener("click", exportMetrics);
    }

    // Live Metrics Tick
    setInterval(() => {
        const statsSent = document.getElementById("statsSent");
        const statsAcked = document.getElementById("statsAcked");
        const statsRetries = document.getElementById("statsRetries");
        const statsDupes = document.getElementById("statsDupes");
        const statsBytes = document.getElementById("statsBytes");
        const statsReceived = document.getElementById("statsReceived");
        const statsRecovered = document.getElementById("statsRecovered");
        const statsReplayRejected = document.getElementById("statsReplayRejected");
        
        if (statsSent) statsSent.innerText = reliabilityState.stats.packetsSent;
        if (statsAcked) statsAcked.innerText = reliabilityState.stats.packetsAcked;
        if (statsRetries) statsRetries.innerText = reliabilityState.stats.retransmissions;
        if (statsDupes) statsDupes.innerText = reliabilityState.stats.duplicatesDropped;
        if (statsReceived) statsReceived.innerText = reliabilityState.stats.packetsReceived;
        if (statsRecovered) statsRecovered.innerText = state.transportStats.recovered + reliabilityState.stats.retransmissions;
        if (statsReplayRejected) statsReplayRejected.innerText = state.transportStats.replayRejected;
        updateTransportMonitor();
        
        if (statsBytes) {
            // Simulated payload mapping: 1 JSON event is ~180 bytes.
            const rawBytesSent = (reliabilityState.stats.packetsSent + reliabilityState.stats.packetsReceived) * 180; 
            statsBytes.innerText = `${rawBytesSent} B`;
        }
    }, 1000);
}

function setPacketLoss(value) {
    networkSimulator.packetLossPct = value;
    const packetLossInput = document.getElementById("simPacketLoss");
    const label = document.getElementById("simPacketLossLabel");
    if (packetLossInput) packetLossInput.value = String(value);
    if (label) label.innerText = `${value}%`;
    document.querySelectorAll("[data-loss-preset]").forEach((button) => {
        button.classList.toggle("active", parseInt(button.dataset.lossPreset) === value);
    });
}

export function updateTransportMonitor() {
    const classCounts = state.transportStats.classCounts;
    setText("classControl", classCounts.CONTROL);
    setText("classCritical", classCounts.CRITICAL);
    setText("classInteractive", classCounts.INTERACTIVE);
    setText("classBestEffort", classCounts.BEST_EFFORT);
    setText("monitorEpoch", state.currentEpoch);
    setText("monitorEpochProgress", `${state.packetCounter % state.packetsPerEpoch} / ${state.packetsPerEpoch}`);
    setText("monitorPolicy", state.policyFingerprint ? "Verified" : "Pending");
    setText("monitorPolicyFingerprint", state.policyFingerprint ? state.policyFingerprint.slice(0, 12) : "...");
    setText("monitorWebrtc", state.peerConnections.size ? "Connected" : "Waiting");

    const headerView = document.getElementById("latestPacketHeader");
    if (headerView) {
        headerView.textContent = JSON.stringify(state.latestPacketHeader || {}, null, 2);
    }
}

function exportMetrics() {
    const payload = {
        exported_at: new Date().toISOString(),
        packet_classes: state.transportStats.classCounts,
        reliability: reliabilityState.stats,
        epoch: state.currentEpoch,
        packet_counter: state.packetCounter,
        transport_mode: state.transportMode,
        policy_fingerprint: state.policyFingerprint,
        latest_packet_header: state.latestPacketHeader,
        packet_flow: state.packetFlow,
        packet_timeline: state.packetTimeline,
        decision_log: state.decisionLog,
        recovery_events: state.recoveryEvents,
        integrity_chain: state.integrityChain,
        simulator: networkSimulator
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `secusignflow-metrics-${Date.now()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
}

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.innerText = String(value);
}
