import { state } from './state.js';
import { encryptPacket } from './crypto.js';

export const reliabilityState = {
    outboundSeqNum: 0,
    unackedPackets: new Map(), // map seqNum -> { payloadObj, peerSid, retries, timer }
    inboundSeqCache: new Set(),
    stats: {
        packetsSent: 0,
        packetsAcked: 0,
        retransmissions: 0,
        duplicatesDropped: 0,
        packetsReceived: 0
    }
};

const MAX_RETRIES = 5;
const ACK_TIMEOUT_MS = 250;

export async function sendReliableMessage(payloadObj, peerSid) {
    if (payloadObj.needsAck === undefined) {
        payloadObj.needsAck = true;
    }
    
    if (payloadObj.needsAck) {
        reliabilityState.outboundSeqNum++;
        payloadObj.seqNum = reliabilityState.outboundSeqNum;
    }
    
    // Track stats
    reliabilityState.stats.packetsSent++;
    
    const payloadStr = JSON.stringify(payloadObj);
    const encrypted = await encryptPacket(new TextEncoder().encode(payloadStr), state.sessionKey, state);
    
    if (payloadObj.needsAck) {
        const record = {
            payloadObj: JSON.parse(payloadStr), // Deep copy just in case
            peerSid,
            retries: 0,
            timer: null
        };
        record.timer = setTimeout(() => handleRetransmission(record.payloadObj.seqNum), ACK_TIMEOUT_MS);
        reliabilityState.unackedPackets.set(record.payloadObj.seqNum, record);
    }
    
    executeSend(peerSid, encrypted);
}

async function handleRetransmission(seqNum) {
    const record = reliabilityState.unackedPackets.get(seqNum);
    if (!record) return;

    if (record.retries >= MAX_RETRIES) {
        console.warn(`[Reliability] Dropped packet ${seqNum} after ${MAX_RETRIES} retries.`);
        reliabilityState.unackedPackets.delete(seqNum);
        return;
    }

    record.retries++;
    reliabilityState.stats.retransmissions++;
    console.log(`[Reliability] Retransmitting packet ${seqNum} (Attempt ${record.retries})`);
    
    const payloadStr = JSON.stringify(record.payloadObj);
    const encrypted = await encryptPacket(new TextEncoder().encode(payloadStr), state.sessionKey, state);
    
    executeSend(record.peerSid, encrypted);
    
    record.timer = setTimeout(() => handleRetransmission(seqNum), ACK_TIMEOUT_MS);
}

export const networkSimulator = {
    packetLossPct: 0, 
    baseDelayMs: 0,
    jitterMs: 0
};

function executeSend(peerSid, encryptedBuffer) {
    if (networkSimulator.packetLossPct > 0) {
        if (Math.random() * 100 < networkSimulator.packetLossPct) {
            console.warn("[Simulator] Packet Intentionally Dropped!");
            return; // Simulate loss by never sending
        }
    }
    
    let delay = networkSimulator.baseDelayMs;
    if (networkSimulator.jitterMs > 0) {
        delay += (Math.random() * 2 - 1) * networkSimulator.jitterMs;
    }
    if (delay < 0) delay = 0;
    
    if (delay > 0) {
        setTimeout(() => performRealSend(peerSid, encryptedBuffer), delay);
    } else {
        performRealSend(peerSid, encryptedBuffer);
    }
}

function performRealSend(peerSid, encryptedBuffer) {
    const pc = state.peerConnections.get(peerSid);
    if (pc && pc.semanticChannel && pc.semanticChannel.readyState === "open") {
        pc.semanticChannel.send(encryptedBuffer);
    }
}

export async function processInboundReliability(payload, peerSid) {
    if (payload.type === "ack") {
        const ackedSeq = payload.ackSeqNum;
        if (reliabilityState.unackedPackets.has(ackedSeq)) {
            clearTimeout(reliabilityState.unackedPackets.get(ackedSeq).timer);
            reliabilityState.unackedPackets.delete(ackedSeq);
            reliabilityState.stats.packetsAcked++;
        }
        return false; // Stop further processing
    }
    
    if (payload.needsAck && payload.seqNum) {
        // Build ACK
        const ackPayload = {
            type: "ack",
            ackSeqNum: payload.seqNum,
            needsAck: false
        };
        const ackStr = JSON.stringify(ackPayload);
        const encrypted = await encryptPacket(new TextEncoder().encode(ackStr), state.sessionKey, state);
        executeSend(peerSid, encrypted);
        
        // Deduplication check
        const cacheKey = `${peerSid}_${payload.seqNum}`;
        if (reliabilityState.inboundSeqCache.has(cacheKey)) {
            console.warn(`[Reliability] Duplicate packet suppressed: ${payload.seqNum}`);
            reliabilityState.stats.duplicatesDropped++;
            return false;
        }
        
        reliabilityState.inboundSeqCache.add(cacheKey);
        if (reliabilityState.inboundSeqCache.size > 2000) {
            const firstElement = reliabilityState.inboundSeqCache.values().next().value;
            reliabilityState.inboundSeqCache.delete(firstElement);
        }
    }
    
    reliabilityState.stats.packetsReceived++;
    return true; // Proceed to Application layer
}
