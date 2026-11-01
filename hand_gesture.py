
import cv2
import mediapipe as mp
import time
import math

# MediaPipe setup
mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("Cannot open camera. Check your webcam.")
    raise SystemExit

previous_time = 0


def get_finger_states(landmarks, handedness):
    # Thumb, index, middle, ring, little finger
    states = []

    # Thumb: compare horizontal positions
    if handedness == "Right":
        states.append(landmarks[4].x < landmarks[3].x)
    else:
        states.append(landmarks[4].x > landmarks[3].x)

    # Other four fingers
    for tip, pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
        states.append(landmarks[tip].y < landmarks[pip].y)

    return states


def recognize_gesture(states, landmarks):
    thumb, index, middle, ring, little = states
    count = sum(states)

    # Distance between thumb tip and index fingertip
    distance = math.dist(
        (landmarks[4].x, landmarks[4].y),
        (landmarks[8].x, landmarks[8].y)
    )

    if distance < 0.05 and middle and ring and little:
        return "OK Sign", count

    if thumb and not index and not middle and not ring and not little:
        return "Thumbs Up", count

    if index and middle and not ring and not little:
        return "Peace Sign", count

    if count == 0:
        return "Fist", count

    if count == 5:
        return "Open Palm", count

    if count == 1:
        return "One Finger", count

    if count == 2:
        return "Two Fingers", count

    if count == 3:
        return "Three Fingers", count

    if count == 4:
        return "Four Fingers", count

    return "Unknown Gesture", count


print("AI Hand Gesture Recognition started!")
print("Press Q to quit.")

while True:
    success, frame = camera.read()

    if not success:
        print("Unable to read camera.")
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    height, width, _ = frame.shape

    # Dark dashboard header
    cv2.rectangle(frame, (0, 0), (width, 115), (25, 25, 25), -1)
    cv2.putText(
        frame, "AI HAND GESTURE RECOGNITION",
        (20, 35), cv2.FONT_HERSHEY_SIMPLEX,
        0.7, (100, 255, 150), 2
    )

    # FPS calculation
    current_time = time.time()
    fps = 1 / max(current_time - previous_time, 0.001)
    previous_time = current_time

    cv2.putText(
        frame, f"FPS: {int(fps)}",
        (20, 75), cv2.FONT_HERSHEY_SIMPLEX,
        0.6, (255, 255, 255), 2
    )

    detected = 0
    gesture_text = "No hand detected"
    finger_count = 0

    if result.multi_hand_landmarks:
        detected = len(result.multi_hand_landmarks)

        for hand_landmarks, hand_info in zip(
            result.multi_hand_landmarks,
            result.multi_handedness
        ):
            mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
                mp_draw.DrawingSpec(
                    color=(100, 255, 150),
                    thickness=2,
                    circle_radius=3
                ),
                mp_draw.DrawingSpec(
                    color=(255, 200, 50),
                    thickness=2
                )
            )

            landmarks = hand_landmarks.landmark
            handedness = hand_info.classification[0].label

            states = get_finger_states(landmarks, handedness)
            gesture_text, finger_count = recognize_gesture(
                states, landmarks
            )

            # Highlight the detected gesture
            cv2.putText(
                frame, gesture_text,
                (20, 155), cv2.FONT_HERSHEY_SIMPLEX,
                1, (100, 255, 150), 2
            )

            cv2.putText(
                frame, f"Fingers: {finger_count}",
                (20, 195), cv2.FONT_HERSHEY_SIMPLEX,
                0.7, (255, 255, 255), 2
            )

            cv2.putText(
                frame, f"Hand: {handedness}",
                (20, 230), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (255, 220, 100), 2
            )

            # Display one hand per frame for clear status
            break

    if detected == 0:
        cv2.putText(
            frame, "Show your hand to the camera",
            (20, 155), cv2.FONT_HERSHEY_SIMPLEX,
            0.7, (80, 150, 255), 2
        )

    # Status panel
    cv2.rectangle(
        frame, (10, height - 48), (width - 10, height - 10),
        (25, 25, 25), -1
    )

    status = "HAND DETECTED" if detected else "WAITING FOR HAND"
    status_color = (100, 255, 150) if detected else (80, 150, 255)

    cv2.putText(
        frame, status,
        (20, height - 23), cv2.FONT_HERSHEY_SIMPLEX,
        0.55, status_color, 2
    )

    cv2.putText(
        frame, "Q: Quit",
        (width - 115, height - 23), cv2.FONT_HERSHEY_SIMPLEX,
        0.5, (230, 230, 230), 1
    )

    cv2.imshow("AI Hand Gesture Recognition", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

camera.release()
hands.close()
cv2.destroyAllWindows()

