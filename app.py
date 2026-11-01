

from flask import Flask, render_template, jsonify, Response
import cv2
import mediapipe as mp
import threading
import time

app = Flask(__name__)

# ---------------- CAMERA SETUP ----------------

camera = None
camera_lock = threading.Lock()
stats_lock = threading.Lock()

stats = {
    "status": "Ready",
    "gesture": "Waiting for hand",
    "fingers": 0,
    "total_detections": 0,
    "fps": 0
}

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

last_gesture = ""
last_detection_time = 0
total_detections = 0
previous_frame_time = time.time()


# ---------------- GESTURE RECOGNITION ----------------

def classify_gesture(landmarks, hand_label):
    index = landmarks[8].y < landmarks[6].y
    middle = landmarks[12].y < landmarks[10].y
    ring = landmarks[16].y < landmarks[14].y
    pinky = landmarks[20].y < landmarks[18].y

    # Same thumb direction rule used by the finger counter
    if hand_label == "Right":
        thumb = landmarks[4].x < landmarks[3].x
    else:
        thumb = landmarks[4].x > landmarks[3].x

    if index and middle and ring and pinky:
        return "Open Palm"

    if not index and not middle and not ring and not pinky:
        if thumb and landmarks[4].y < landmarks[3].y:
            return "Thumbs Up"
        return "Fist"

    if index and middle and not ring and not pinky:
        return "Peace Sign"

    if index and not middle and not ring and not pinky:
        return "One Finger"

    if index and middle and ring and not pinky:
        return "Three Fingers"

    return "Unknown Gesture"


# ---------------- FINGER DETECTION ----------------

def detect_gesture(frame):
    global last_gesture
    global last_detection_time
    global total_detections
    global previous_frame_time

    frame = cv2.flip(frame, 1)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    total_fingers = 0
    hand_counts = []
    detected_gestures = []

    gesture = "No hand detected"

    if results.multi_hand_landmarks:

        for i, hand_landmarks in enumerate(results.multi_hand_landmarks):

            landmarks = hand_landmarks.landmark

            mp_draw.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS
            )

            # Get hand orientation
            hand_label = "Right"

            if results.multi_handedness and i < len(results.multi_handedness):
                hand_label = (
                    results.multi_handedness[i]
                    .classification[0].label
                )

            # Count fingers
            finger_count = 0

            # Thumb
            if hand_label == "Right":
                if landmarks[4].x < landmarks[3].x:
                    finger_count += 1
            else:
                if landmarks[4].x > landmarks[3].x:
                    finger_count += 1

            # Index, middle, ring and little fingers
            for tip, joint in [
                (8, 6),
                (12, 10),
                (16, 14),
                (20, 18)
            ]:
                if landmarks[tip].y < landmarks[joint].y:
                    finger_count += 1

            hand_counts.append(finger_count)
            total_fingers += finger_count

            # Recognize gesture
            detected_gesture = classify_gesture(
                landmarks,
                hand_label
            )

            detected_gestures.append(detected_gesture)

            # Draw individual hand information
            cv2.putText(
                frame,
                f"{hand_label}: {detected_gesture} ({finger_count})",
                (20, 45 + (i * 35)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (100, 255, 160),
                2
            )

        gesture = " + ".join(detected_gestures)

        # Count new gesture events
        now = time.time()

        if gesture != last_gesture and now - last_detection_time > 0.7:
            total_detections += 1
            last_gesture = gesture
            last_detection_time = now

    else:
        last_gesture = ""

    # Calculate FPS
    current_time = time.time()
    fps = 1 / max(current_time - previous_frame_time, 0.001)
    previous_frame_time = current_time

    # Update dashboard statistics
    with stats_lock:
        stats["gesture"] = gesture
        stats["fingers"] = total_fingers
        stats["total_detections"] = total_detections
        stats["status"] = (
            "Camera connected" if hand_counts else "Waiting for hand"
        )
        stats["fps"] = round(fps, 1)

    # Display total finger count
    cv2.putText(
        frame,
        f"Total Fingers: {total_fingers}/10",
        (20, 440),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (100, 255, 160),
        2
    )

    return frame


# ---------------- HOME PAGE ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- START CAMERA ----------------

@app.route("/api/start", methods=["POST"])
def start_camera():
    global camera

    with camera_lock:

        if camera is not None and camera.isOpened():
            return jsonify({
                "ok": True,
                "message": "Camera already running"
            })

        new_camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        if not new_camera.isOpened():
            new_camera.release()
            new_camera = cv2.VideoCapture(0)

        if not new_camera.isOpened():
            new_camera.release()

            return jsonify({
                "ok": False,
                "message": "Could not open webcam"
            }), 500

        new_camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        new_camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        camera = new_camera

    with stats_lock:
        stats["status"] = "Camera connected"
        stats["gesture"] = "Waiting for hand"
        stats["fingers"] = 0

    return jsonify({
        "ok": True,
        "message": "Camera connected"
    })


# ---------------- VIDEO STREAM ----------------

def generate_frames():
    global camera

    while True:

        with camera_lock:
            current_camera = camera

            if current_camera is None or not current_camera.isOpened():
                break

            success, frame = current_camera.read()

        if not success:
            time.sleep(0.05)
            continue

        frame = detect_gesture(frame)

        success, buffer = cv2.imencode(".jpg", frame)

        if not success:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# ---------------- STOP CAMERA ----------------

@app.route("/api/stop", methods=["POST"])
def stop_camera():
    global camera

    with camera_lock:
        if camera is not None:
            camera.release()
            camera = None

    with stats_lock:
        stats["status"] = "Ready"
        stats["gesture"] = "Waiting for hand"
        stats["fingers"] = 0

    return jsonify({
        "ok": True,
        "message": "Camera stopped"
    })


# ---------------- DASHBOARD STATS ----------------

@app.route("/api/stats")
def get_stats():
    with stats_lock:
        return jsonify(stats.copy())


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    app.run(
        debug=True,
        use_reloader=False,
        threaded=True
    )
