import cv2
import mediapipe as mp
import numpy as np

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7)

# Simple rule-based ASL letter classifier (extend with ML for accuracy)
def classify_gesture(landmarks):
    if not landmarks:
        return None
    
    # Normalize to wrist (landmark 0)
    lm = np.array([[l.x, l.y, l.z] for l in landmarks])
    wrist = lm[0]
    lm -= wrist
    
    # Finger tip landmarks: thumb=4, index=8, middle=12, ring=16, pinky=20
    tips = [4, 8, 12, 16, 20]
    finger_up = 0
    
    # Thumb up (special, x-based)
    thumb_tip = lm[4]
    if thumb_tip[0] > 0.3:  # Thumb extended right
        finger_up += 1
    
    # Other fingers: y-distance from pip (3,7,11,15,19)
    pips = [3, 7, 11, 15, 19]
    for tip, pip in zip(tips[1:], pips[1:]):
        if lm[tip][1] < lm[pip][1]:
            finger_up += 1
    
    # Basic mappings (expand rules for full accuracy)
    if finger_up == 0:
        return 'A'  # Fist
    elif finger_up == 1:
        return 'B' if lm[8][1] < lm[6][1] else 'L'  # Index only vs L
    elif finger_up == 2:
        return 'V'  # Index + middle
    elif finger_up == 5:
        return 'H'  # All open-ish
    # Add more rules: e.g., for 'C': curled fingers, check distances
    dists = [np.linalg.norm(lm[i] - lm[0]) for i in tips]
    if max(dists[1:]) < 0.2:  # All fingers curled
        return 'O'
    
    return '?'  # Unknown

# Space: two open palms facing each other
def is_space(landmarks_list):
    if len(landmarks_list) == 2:
        lm1 = landmarks_list[0]
        lm2 = landmarks_list[1]
        # Both palms open, facing (rough z-diff, finger count=5)
        if classify_gesture(lm1) == 'H' and classify_gesture(lm2) == 'H' and abs(lm1[0].z - lm2[0].z) > 0.1:
            return True
    return False

# End: thumbs crossed (right thumb over left)
def is_end_sentence(landmarks_list):
    if len(landmarks_list) == 2:
        lm1_left = landmarks_list[0] if landmarks_list[0][0].x < landmarks_list[1][0].x else landmarks_list[1]
        lm2_right = landmarks_list[1] if landmarks_list[0][0].x < landmarks_list[1][0].x else landmarks_list[0]
        # Thumbs crossed: right thumb tip left of left thumb
        if lm2_right[4].x < lm1_left[4].x:
            return True
    return False

cap = cv2.VideoCapture(0)
current_char = ''
text_buffer = ''
hold_time = 0
font = cv2.FONT_HERSHEY_SIMPLEX

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)
    
    landmarks_list = []
    if results.multi_hand_landmarks:
        for hand_lms in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_lms, mp_hands.HAND_CONNECTIONS)
            landmarks_list.append(hand_lms.landmark)
            
            char = classify_gesture(hand_lms.landmark)
            if char and char != '?':
                hold_time += 1
                if hold_time > 20:  # Hold 20 frames (~0.7s @30fps)
                    if char != current_char:
                        current_char = char
                        text_buffer += char
                        hold_time = 0
            else:
                hold_time = 0
    
    # Check specials
    if is_space(landmarks_list):
        text_buffer += ' '
        cv2.putText(frame, "SPACE", (50, 450), font, 1, (255, 255, 0), 2)
    if is_end_sentence(landmarks_list):
        text_buffer += '.'
        cv2.putText(frame, "END", (50, 480), font, 1, (0, 0, 255), 2)
    
    cv2.putText(frame, f"Current: {current_char}", (50, 100), font, 1, (0, 255, 0), 2)
    cv2.putText(frame, f"Text: {text_buffer}", (50, 130), font, 0.7, (255, 255, 255), 2)
    
    cv2.imshow("Sign Language Translator", frame)
    
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('c'):
        text_buffer = ''

cap.release()
cv2.destroyAllWindows()
print("Final text:", text_buffer)