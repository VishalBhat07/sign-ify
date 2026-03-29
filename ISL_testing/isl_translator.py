"""
ISL Real-time Translator
Uses the SigLIP2-based Alphabet-Sign-Language-Detection model
(prithivMLmods/Alphabet-Sign-Language-Detection) for high-accuracy
sign language alphabet recognition from a live webcam feed.
"""

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, SiglipForImageClassification

# ───────────────────────── Model Loading ─────────────────────────

MODEL_NAME = "prithivMLmods/Alphabet-Sign-Language-Detection"

print("=" * 60)
print("  Loading SigLIP model… (first run downloads ~350 MB)")
print("=" * 60)

processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
model = SiglipForImageClassification.from_pretrained(MODEL_NAME)
model.eval()

# Use MPS (Apple Silicon GPU) if available, else CPU
if torch.backends.mps.is_available():
    device = torch.device("mps")
    print("  ⚡ Using Apple Silicon GPU (MPS)")
elif torch.cuda.is_available():
    device = torch.device("cuda")
    print("  ⚡ Using CUDA GPU")
else:
    device = torch.device("cpu")
    print("  🐢 Using CPU")

model = model.to(device)

# Label mapping (model output index → letter)
LABELS = {i: chr(ord("A") + i) for i in range(26)}

# ───────────────────────── Classification ─────────────────────────

def classify_frame(frame_bgr):
    """
    Classify a BGR OpenCV frame and return (predicted_letter, confidence, all_probs).
    """
    # Convert BGR → RGB PIL Image
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb)

    inputs = processor(images=pil_image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        probs = torch.nn.functional.softmax(logits, dim=1).squeeze()

    top_idx = probs.argmax().item()
    confidence = probs[top_idx].item()
    letter = LABELS[top_idx]

    return letter, confidence, probs.cpu().numpy()


# ───────────────────────────── Main Loop ─────────────────────────────

def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return

    sentence = ""
    last_letter = None
    letter_count = 0
    CONFIRM_FRAMES = 10       # Hold sign steady for ~0.33s at 30fps
    CONFIDENCE_THRESH = 0.60  # Minimum confidence to accept a prediction
    frame_skip = 2            # Run inference every N frames (for speed)
    frame_counter = 0

    # Cache latest prediction between skipped frames
    cached_letter = None
    cached_confidence = 0.0
    cached_top3 = []

    print()
    print("=" * 60)
    print("  ISL Real-time Translator  (SigLIP Model)")
    print("=" * 60)
    print("  Letters A–Z recognised from hand signs")
    print("  Hold a sign steady for ~0.3s to type it")
    print("  Keys: [SPACE] Add space  [BACKSPACE] Delete  [C] Clear  [Q] Quit")
    print("=" * 60)

    while True:
        ok, frame = cap.read()
        if not ok:
            continue

        frame = cv2.flip(frame, 1)
        h, w = frame.shape[:2]
        frame_counter += 1

        # ── Region of Interest (center crop guide) ──
        roi_size = min(h, w) - 60
        rx = (w - roi_size) // 2
        ry = (h - roi_size) // 2
        roi = frame[ry:ry + roi_size, rx:rx + roi_size]

        # ── Run inference (skip some frames for performance) ──
        if frame_counter % frame_skip == 0:
            letter, confidence, probs = classify_frame(roi)
            cached_letter = letter
            cached_confidence = confidence

            # Get top 3 predictions for debug display
            top3_idx = np.argsort(probs)[::-1][:3]
            cached_top3 = [(LABELS[i], probs[i]) for i in top3_idx]

        # ── Typing logic ──
        if cached_letter and cached_confidence >= CONFIDENCE_THRESH:
            if cached_letter == last_letter:
                letter_count += 1
            else:
                letter_count = 0
            last_letter = cached_letter

            if letter_count == CONFIRM_FRAMES:
                sentence += cached_letter
                print(f"  ✓ Typed: {cached_letter}  (conf: {cached_confidence:.1%})")
                letter_count = -8  # Cooldown to avoid rapid repeat
        else:
            last_letter = None
            letter_count = 0

        # ── Draw ROI guide ──
        cv2.rectangle(frame, (rx, ry), (rx + roi_size, ry + roi_size),
                       (0, 255, 200), 2)
        cv2.putText(frame, "Show sign here", (rx + 10, ry - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 200), 2)

        # ── Top bar (dark overlay) ──
        cv2.rectangle(frame, (0, 0), (w, 140), (0, 0, 0), -1)

        # Detected letter + confidence
        show = cached_letter if cached_letter and cached_confidence >= CONFIDENCE_THRESH else "-"
        conf_pct = f"{cached_confidence:.0%}" if cached_letter else ""
        color = (0, 255, 0) if cached_confidence >= CONFIDENCE_THRESH else (0, 100, 255)
        cv2.putText(frame, f"Detected: {show}  {conf_pct}", (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        # Sentence
        display_sentence = sentence if len(sentence) <= 40 else "..." + sentence[-37:]
        cv2.putText(frame, f"Sentence: {display_sentence}", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Top-3 debug
        if cached_top3:
            top3_str = "  ".join([f"{l}:{c:.0%}" for l, c in cached_top3])
            cv2.putText(frame, f"Top3: {top3_str}", (10, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 200, 255), 1)

        # Confirmation progress bar
        if letter_count > 0 and last_letter:
            bar_w = int((letter_count / CONFIRM_FRAMES) * 200)
            cv2.rectangle(frame, (w - 220, 15), (w - 220 + bar_w, 35), (0, 255, 0), -1)
            cv2.rectangle(frame, (w - 220, 15), (w - 20, 35), (100, 100, 100), 1)
            cv2.putText(frame, "Confirming...", (w - 220, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        # Bottom legend
        cv2.putText(frame, "[SPACE] Space  [BS] Delete  [C] Clear  [Q] Quit",
                    (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        cv2.imshow("ISL Translator (SigLIP)", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break
        elif key == ord(" "):
            if not sentence.endswith(" "):
                sentence += " "
                print("  ✓ Typed: SPACE")
        elif key == ord("c"):
            sentence = ""
            print("  ✗ Cleared sentence")
        elif key == 8 or key == 127:  # Backspace / Delete
            if sentence:
                removed = sentence[-1]
                sentence = sentence[:-1]
                print(f"  ← Deleted: {removed}")

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nFinal sentence: {sentence}")


if __name__ == "__main__":
    main()
