import { reliabilityState, networkSimulator } from './reliability.js';

export function initDashboard() {
    // Input Mappings
    const packetLossInput = document.getElementById("simPacketLoss");
    const delayInput = document.getElementById("simDelay");
    const jitterInput = document.getElementById("simJitter");
    
    if (packetLossInput) {
        packetLossInput.addEventListener("input", (e) => {
            networkSimulator.packetLossPct = parseInt(e.target.value) || 0;
            document.getElementById("simPacketLossLabel").innerText = `${networkSimulator.packetLossPct}%`;
        });
    }
    
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

    // Live Metrics Tick
    setInterval(() => {
        const statsSent = document.getElementById("statsSent");
        const statsAcked = document.getElementById("statsAcked");
        const statsRetries = document.getElementById("statsRetries");
        const statsDupes = document.getElementById("statsDupes");
        const statsBytes = document.getElementById("statsBytes");
        const statsReceived = document.getElementById("statsReceived");
        
        if (statsSent) statsSent.innerText = reliabilityState.stats.packetsSent;
        if (statsAcked) statsAcked.innerText = reliabilityState.stats.packetsAcked;
        if (statsRetries) statsRetries.innerText = reliabilityState.stats.retransmissions;
        if (statsDupes) statsDupes.innerText = reliabilityState.stats.duplicatesDropped;
        if (statsReceived) statsReceived.innerText = reliabilityState.stats.packetsReceived;
        
        if (statsBytes) {
            // Simulated payload mapping: 1 JSON event is ~180 bytes.
            const rawBytesSent = (reliabilityState.stats.packetsSent + reliabilityState.stats.packetsReceived) * 180; 
            statsBytes.innerText = `${rawBytesSent} B`;
        }
    }, 1000);
}
