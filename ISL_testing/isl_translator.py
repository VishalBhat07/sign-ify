import cv2
import mediapipe as mp
import numpy as np

# MediaPipe 0.10.32 on Python 3.13 exposes only `tasks` and not `solutions`.
if not hasattr(mp, "solutions"):
    raise RuntimeError(
        "This script requires MediaPipe's `solutions` API, which is missing in your current install. "
        "Use Python 3.11/3.12 with a compatible mediapipe version (for example 0.10.14)."
    )

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)
mp_draw = mp.solutions.drawing_utils

# ───────────────────────────── Helpers ─────────────────────────────

def dist(p1, p2):
    """Euclidean distance between two MediaPipe landmarks."""
    return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)

def is_finger_extended(lm, finger):
    """
    Check if finger is extended using distance-from-wrist heuristic.
    finger: 0=Thumb, 1=Index, 2=Middle, 3=Ring, 4=Pinky
    """
    tip_ids  = [4, 8, 12, 16, 20]
    base_ids = [2, 5,  9, 13, 17]
    wrist = lm[0]
    tip  = lm[tip_ids[finger]]
    base = lm[base_ids[finger]]
    d_tip  = np.sqrt((tip.x - wrist.x)**2 + (tip.y - wrist.y)**2)
    d_base = np.sqrt((base.x - wrist.x)**2 + (base.y - wrist.y)**2)
    return d_tip > d_base * 1.3

def get_finger_state(lm):
    """Return a tuple of bools: (thumb, index, middle, ring, pinky)."""
    return tuple(is_finger_extended(lm, i) for i in range(5))

def is_hand_horizontal(lm):
    """Check if the index finger is pointing more sideways than up/down."""
    dx = abs(lm[8].x - lm[5].x)  # Index tip vs Index MCP
    dy = abs(lm[8].y - lm[5].y)
    return dx > dy

# ───────────────────────── Detection Logic ─────────────────────────
#
# STRATEGY: First check two-handed vowels, then use the number of
#           extended fingers as a primary switch for consonants.
#           Within each group, use secondary features (orientation,
#           tip distances) to disambiguate.
#
# This guarantees NO overlapping checks.

def detect_isl_letter(hand_landmarks_list, hand_label_list):
    # ── Identify dominant (Right) and non-dominant (Left) hands ──
    dom_idx = -1
    non_dom_idx = -1
    for i, label in enumerate(hand_label_list):
        if label == "Right":
            dom_idx = i
        else:
            non_dom_idx = i
    if dom_idx == -1 and len(hand_landmarks_list) > 0:
        dom_idx = 0
    if dom_idx == -1:
        return None

    lm = hand_landmarks_list[dom_idx].landmark
    scale = dist(lm[0], lm[9])  # Wrist → Middle-MCP (used to normalize)

    # ── VOWELS (Two-handed: Right index touches Left fingertip) ──
    if len(hand_landmarks_list) >= 2 and non_dom_idx != -1:
        nd = hand_landmarks_list[non_dom_idx].landmark
        th = scale * 0.45  # touch threshold
        pointer = lm[8]    # dominant index tip
        if dist(pointer, nd[4])  < th: return "A"   # Left Thumb
        if dist(pointer, nd[8])  < th: return "E"   # Left Index
        if dist(pointer, nd[12]) < th: return "I"   # Left Middle
        if dist(pointer, nd[16]) < th: return "O"   # Left Ring
        if dist(pointer, nd[20]) < th: return "U"   # Left Pinky

    # ── CONSONANTS (One-handed, Right hand) ──
    fingers = get_finger_state(lm)
    # fingers = (Thumb, Index, Middle, Ring, Pinky)
    n_up = sum(fingers)

    # ────────── 0 fingers up ──────────
    if n_up == 0:
        # S = Fist  vs  T = Fist with thumb poking between index & middle
        # T: thumb tip is between index-PIP and middle-PIP vertically
        thumb_between = dist(lm[4], lm[6]) < scale * 0.35
        if thumb_between:
            return "T"
        return "S"

    # ────────── 1 finger up ──────────
    if n_up == 1:
        if fingers[1]:  # Index only
            if is_hand_horizontal(lm):
                return "G"   # Index pointing sideways
            else:
                # D vs X:  D = index straight up,  X = index hooked/bent
                # For X, index tip is close to index PIP (landmark 6)
                hook = dist(lm[8], lm[6]) < scale * 0.35
                if hook:
                    return "X"  # Hooked index
                return "D"     # Straight index up
        if fingers[4]:  # Pinky only
            return "J"
        if fingers[0]:  # Thumb only
            return "THUMB"  # (not a standard letter, acts as no-match)

    # ────────── 2 fingers up ──────────
    if n_up == 2:
        if fingers[0] and fingers[1]:  # Thumb + Index
            return "L"
        if fingers[0] and fingers[4]:  # Thumb + Pinky
            return "Y"
        if fingers[1] and fingers[2]:  # Index + Middle
            if is_hand_horizontal(lm):
                return "H"  # Two fingers pointing sideways
            # Vertical: check spacing between index & middle tips
            tip_gap = dist(lm[8], lm[12])
            if tip_gap < scale * 0.15:
                return "R"  # Crossed / very close together
            elif tip_gap > scale * 0.4:
                return "V"  # Peace / spread
            else:
                return "N"  # Together but not crossed

    # ────────── 3 fingers up ──────────
    if n_up == 3:
        if fingers[1] and fingers[2] and fingers[3]:  # Index + Middle + Ring
            return "W"
        if fingers[2] and fingers[3] and fingers[4]:  # Middle + Ring + Pinky
            # F = "OK sign" (thumb & index tips touching, other 3 up)
            if dist(lm[4], lm[8]) < scale * 0.35:
                return "F"
        if fingers[0] and fingers[1] and fingers[2]:  # Thumb + Index + Middle
            return "K"
        if fingers[0] and fingers[1] and fingers[4]:  # Thumb + Index + Pinky
            return "P"  # Custom assignment for P

    # ────────── 4 fingers up ──────────
    if n_up == 4:
        if not fingers[0]:  # All except Thumb
            return "B"
        if not fingers[4]:  # All except Pinky
            return "M"  # Custom: 4 fingers + thumb, no pinky

    # ────────── 5 fingers up (open hand) ──────────
    if n_up == 5:
        return " "  # SPACE gesture = open palm

    return None

# ───────────────────────────── Main Loop ─────────────────────────────

def main():
    cap = cv2.VideoCapture(0)
    sentence = ""
    last_letter = None
    letter_count = 0
    CONFIRM_FRAMES = 12  # Hold sign steady for ~0.4s at 30fps

    print("=" * 60)
    print("  ISL Real-time Translator")
    print("=" * 60)
    print("  Vowels : Two-handed (Right index → Left fingertips)")
    print("  Consonants : One-handed (Right hand shapes)")
    print("  Space  : Open palm (all 5 fingers)")
    print("  Keys   : [C] Clear  [Q] Quit")
    print("=" * 60)

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            continue

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        current_letter = None
        finger_debug = ""

        if results.multi_hand_landmarks:
            hand_lm_list = []
            hand_label_list = []
            for i, hlm in enumerate(results.multi_hand_landmarks):
                mp_draw.draw_landmarks(frame, hlm, mp_hands.HAND_CONNECTIONS)
                hand_lm_list.append(hlm)
                hand_label_list.append(
                    results.multi_handedness[i].classification[0].label
                )

            current_letter = detect_isl_letter(hand_lm_list, hand_label_list)

            # Build debug string for dominant hand
            for idx, lbl in enumerate(hand_label_list):
                if lbl == "Right":
                    fs = get_finger_state(hand_lm_list[idx].landmark)
                    finger_debug = "T:{} I:{} M:{} R:{} P:{}".format(
                        *["UP" if f else "--" for f in fs]
                    )
                    break

        # ── Typing logic ──
        if current_letter and current_letter != "THUMB":
            if current_letter == last_letter:
                letter_count += 1
            else:
                letter_count = 0
            last_letter = current_letter

            if letter_count == CONFIRM_FRAMES:
                if current_letter == " " and sentence.endswith(" "):
                    pass
                else:
                    sentence += current_letter
                    tag = "Space" if current_letter == " " else current_letter
                    print(f"  ✓ Typed: {tag}")
                letter_count = -10
        else:
            last_letter = None
            letter_count = 0

        # ── On-screen UI ──
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 130), (0, 0, 0), -1)

        n_hands = len(results.multi_hand_landmarks) if results.multi_hand_landmarks else 0
        cv2.putText(frame, f"Hands: {n_hands}", (w - 130, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)

        show = current_letter if current_letter and current_letter != "THUMB" else "-"
        if show == " ": show = "SPACE"
        cv2.putText(frame, f"Detected: {show}", (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Sentence: {sentence}", (10, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        if finger_debug:
            cv2.putText(frame, finger_debug, (10, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 200, 255), 1)

        # Bottom legend
        cv2.putText(frame, "[C] Clear  [Q] Quit  |  SPACE = Open Palm",
                    (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        cv2.imshow("ISL Translator", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        elif key == ord(" "):
            if not sentence.endswith(" "):
                sentence += " "
        elif key == ord("c"):
            sentence = ""

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
