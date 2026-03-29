"""ISL recognition service used for secure inference side-channel."""

from __future__ import annotations

import base64
import pickle
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np


warnings.filterwarnings("ignore", message="SymbolDatabase.GetPrototype() is deprecated")


LABELS = {
    0: "A",
    1: "B",
    2: "C",
    3: "D",
    4: "E",
    5: "F",
    6: "G",
    7: "H",
    8: "I",
    9: "J",
    10: "K",
    11: "L",
    12: "M",
    13: "N",
    14: "O",
    15: "P",
    16: "Q",
    17: "R",
    18: "S",
    19: "T",
    20: "U",
    21: "V",
    22: "W",
    23: "X",
    24: "Y",
    25: "Z",
    26: "Hello",
    27: "Done",
    28: "Thank You",
    29: "I Love you",
    30: "Sorry",
    31: "Please",
    32: "You are welcome.",
}


@dataclass
class RecognitionResult:
    gesture: Optional[str]
    confidence: float
    landmarks: list[list[float]] | None = None
    bbox: list[float] | None = None
    annotated_preview: Optional[str] = None


class SignLanguageRecognizer:
    """Loads the trained model and predicts gestures from image bytes."""

    def __init__(self, model_path: Path):
        self._model = None
        self._mp_hands = mp.solutions.hands
        self._mp_drawing = mp.solutions.drawing_utils
        self._mp_drawing_styles = mp.solutions.drawing_styles
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=True,
            min_detection_confidence=0.3,
        )
        try:
            with open(model_path, "rb") as model_file:
                self._model = pickle.load(model_file)["model"]
            print("ISL model loaded successfully")
        except Exception as exc:
            print(f"Error loading the model: {exc}")

    @property
    def available(self) -> bool:
        return self._model is not None

    def predict_from_image_bytes(self, image_bytes: bytes) -> RecognitionResult:
        if not self._model:
            return RecognitionResult(gesture=None, confidence=0.0, landmarks=None, bbox=None)

        npimg = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(npimg, cv2.IMREAD_COLOR)
        if frame is None:
            return RecognitionResult(gesture=None, confidence=0.0, landmarks=None, bbox=None)

        # Match the original Flask ISL pipeline: flip first, then run MediaPipe/model.
        flipped_frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(flipped_frame, cv2.COLOR_BGR2RGB)
        results = self._hands.process(frame_rgb)

        if not results.multi_hand_landmarks:
            return RecognitionResult(
                gesture=None,
                confidence=0.0,
                landmarks=None,
                bbox=None,
                annotated_preview=self._encode_preview(flipped_frame),
            )

        best = RecognitionResult(gesture=None, confidence=0.0, landmarks=None, bbox=None)
        frame_height, frame_width, _ = flipped_frame.shape
        for hand_landmarks in results.multi_hand_landmarks:
            preview_frame = flipped_frame.copy()
            self._mp_drawing.draw_landmarks(
                preview_frame,
                hand_landmarks,
                self._mp_hands.HAND_CONNECTIONS,
                self._mp_drawing_styles.get_default_hand_landmarks_style(),
                self._mp_drawing_styles.get_default_hand_connections_style(),
            )
            x_coords = [lm.x for lm in hand_landmarks.landmark]
            y_coords = [lm.y for lm in hand_landmarks.landmark]
            data_aux = []
            for landmark in hand_landmarks.landmark:
                data_aux.append(landmark.x - min(x_coords))
                data_aux.append(landmark.y - min(y_coords))

            try:
                prediction = self._model.predict([np.asarray(data_aux)])
                gesture = LABELS[int(prediction[0])]
                confidence = 1.0
                if hasattr(self._model, "predict_proba"):
                    probabilities = self._model.predict_proba([np.asarray(data_aux)])
                    confidence = float(max(probabilities[0]))

                x1 = max(0.0, min(x_coords) * frame_width - 10)
                y1 = max(0.0, min(y_coords) * frame_height - 10)
                x2 = min(float(frame_width), max(x_coords) * frame_width - 10)
                y2 = min(float(frame_height), max(y_coords) * frame_height - 10)
                cv2.rectangle(
                    preview_frame,
                    (int(x1), int(y1)),
                    (int(max(x1 + 1, x2)), int(max(y1 + 1, y2))),
                    (0, 0, 0),
                    4,
                )
                cv2.putText(
                    preview_frame,
                    f"{gesture} ({confidence * 100:.2f}%)",
                    (int(x1), int(y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 0, 0),
                    3,
                    cv2.LINE_AA,
                )
                if confidence > best.confidence:
                    mirrored_landmarks = [[1.0 - lm.x, lm.y] for lm in hand_landmarks.landmark]
                    mirrored_x1 = max(0.0, frame_width - x2)
                    mirrored_x2 = min(float(frame_width), frame_width - x1)
                    best = RecognitionResult(
                        gesture=gesture,
                        confidence=confidence,
                        landmarks=mirrored_landmarks,
                        bbox=[mirrored_x1, y1, mirrored_x2, y2],
                        annotated_preview=self._encode_preview(preview_frame),
                    )
            except Exception:
                continue

        return best

    def _encode_preview(self, frame: np.ndarray) -> Optional[str]:
        success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
        if not success:
            return None
        return base64.b64encode(buffer.tobytes()).decode()
