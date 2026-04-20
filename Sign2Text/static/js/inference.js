import { state, elements, inferenceState, labelsDict } from './state.js';
import { addMessage } from './ui.js';
import { sendReliableMessage } from './reliability.js';

export function stopIslCapture() {
  if (inferenceState.cameraInstance) {
    inferenceState.cameraInstance.stop();
    inferenceState.cameraInstance = null;
  }
  elements.islRenderedOverlay.removeAttribute("src");
  elements.islRenderedOverlay.classList.add("hidden");
}

export async function broadcastSemanticEvent(gesture, confidence) {
  elements.islStatusBadge.innerHTML = 
      `<i class="fa-solid fa-hands-asl-interpreting"></i> <span>Detected: ${gesture} (${confidence}%)</span>`;
  
  const payloadObj = {
      type: "gesture_change",
      sender: state.userName,
      gesture: gesture,
      confidence: confidence,
      timestamp: new Date().toLocaleTimeString()
  };
  
  addMessage({
      sender: state.userName + " (You)",
      message: gesture,
      type: "sign",
      timestamp: payloadObj.timestamp
  });
  
  for (const peerSid of state.peerConnections.keys()) {
      sendReliableMessage({ ...payloadObj }, peerSid);
  }
}

async function onHandsResults(results) {
  const canvasCtx = elements.islOverlayCanvas.getContext("2d");
  elements.islOverlayCanvas.width = elements.localVideo.videoWidth || 1280;
  elements.islOverlayCanvas.height = elements.localVideo.videoHeight || 720;
  
  canvasCtx.save();
  canvasCtx.clearRect(0, 0, elements.islOverlayCanvas.width, elements.islOverlayCanvas.height);
  
  if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
    for (const landmarks of results.multiHandLandmarks) {
      window.drawConnectors(canvasCtx, landmarks, window.HAND_CONNECTIONS,
                     {color: '#3cffd0', lineWidth: 5});
      window.drawLandmarks(canvasCtx, landmarks, {color: '#5200ff', lineWidth: 3});
    }
  }
  canvasCtx.restore();
  elements.islOverlayCanvas.classList.remove("hidden");

  if (!results.multiHandLandmarks || results.multiHandLandmarks.length === 0 || !inferenceState.ortSession) {
    return;
  }

  const hand = results.multiHandLandmarks[0];
  let x_ = [];
  let y_ = [];
  for (let i = 0; i < hand.length; i++) {
     x_.push(hand[i].x);
     y_.push(hand[i].y);
  }
  const minX = Math.min(...x_);
  const minY = Math.min(...y_);
  
  let dataAux = [];
  for (let i = 0; i < hand.length; i++) {
     dataAux.push(hand[i].x - minX);
     dataAux.push(hand[i].y - minY);
  }

  const tensor = new window.ort.Tensor('float32', Float32Array.from(dataAux), [1, 42]);
  try {
      const fetches = [inferenceState.ortSession.outputNames[0]];
      const output = await inferenceState.ortSession.run({ float_input: tensor }, fetches);
      const labelTensor = output[inferenceState.ortSession.outputNames[0]];
      
      let predictedIdx = labelTensor.data[0];
      if (typeof predictedIdx === 'bigint' || typeof predictedIdx === 'string') {
          predictedIdx = Number(predictedIdx);
      }

      const predictedChar = labelsDict[predictedIdx];
      
      if (predictedChar !== inferenceState.currentGesture) {
          inferenceState.currentGesture = predictedChar;
          inferenceState.gestureStartTime = Date.now();
      } else if (Date.now() - inferenceState.gestureStartTime > 300) {
          await broadcastSemanticEvent(predictedChar, 95);
          inferenceState.gestureStartTime = Date.now() + 2000; 
      }
  } catch (e) {
      console.error("ONNX inference error", e);
  }
}

export async function startIslCapture() {
  stopIslCapture();
  elements.islStatusBadge.innerHTML =
    '<i class="fa-solid fa-hands-asl-interpreting"></i> <span>ISL Model Loading...</span>';

  if (!inferenceState.ortSession) {
    try {
      inferenceState.ortSession = await window.ort.InferenceSession.create('/static/model.onnx');
    } catch (e) {
      console.error("Failed to load ONNX model:", e);
      elements.islStatusBadge.innerHTML =
        '<i class="fa-solid fa-triangle-exclamation"></i> <span>Model load failed</span>';
      return;
    }
  }

  if (!inferenceState.handsTracking) {
    inferenceState.handsTracking = new window.Hands({
      locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
    });
    inferenceState.handsTracking.setOptions({
      maxNumHands: 1,
      modelComplexity: 1,
      minDetectionConfidence: 0.3,
      minTrackingConfidence: 0.3
    });
    inferenceState.handsTracking.onResults(onHandsResults);
  }

  inferenceState.cameraInstance = new window.Camera(elements.localVideo, {
    onFrame: async () => {
      await inferenceState.handsTracking.send({image: elements.localVideo});
    },
    width: 1280,
    height: 720
  });
  inferenceState.cameraInstance.start();
  elements.islStatusBadge.innerHTML =
    '<i class="fa-solid fa-hands-asl-interpreting"></i> <span>ISL monitoring active</span>';
}
