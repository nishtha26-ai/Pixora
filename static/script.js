
const $ = (id) => document.getElementById(id);

let cameraRunning = false;
let events = [];
let lastRecordedGesture = "";
let lastRecordedAt = 0;
let polling = null;

function showToast(message) {
    const toast = $("toast");
    if (!toast) {
        alert(message);
        return;
    }

    toast.textContent = message;
    toast.classList.add("show");

    setTimeout(() => toast.classList.remove("show"), 3000);
}

function setText(id, value) {
    const element = $(id);
    if (element) element.textContent = value;
}

function recordGesture(gesture, fingers) {
    const now = Date.now();

    // Don't add the same gesture repeatedly every second.
    if (gesture === lastRecordedGesture && now - lastRecordedAt < 2500) {
        return;
    }

    lastRecordedGesture = gesture;
    lastRecordedAt = now;

    events.unshift({
        gesture,
        fingers,
        time: new Date().toLocaleTimeString()
    });

    events = events.slice(0, 50);
    updateHistory();
    updateChart();
}

function updateHistory() {
    const list = $("history-list");
    if (!list) return;

    list.replaceChildren();

    if (events.length === 0) {
        const empty = document.createElement("p");
        empty.className = "empty-history";
        empty.textContent = "No gestures recorded yet.";
        list.appendChild(empty);
        return;
    }

    events.slice(0, 5).forEach((event) => {
        const row = document.createElement("div");
        row.className = "history-entry";

        const icon = document.createElement("span");
        icon.className = "history-entry-icon";
        icon.textContent = "✳";

        const details = document.createElement("div");
        const name = document.createElement("strong");
        name.textContent = event.gesture;

        const count = document.createElement("small");
        count.textContent = `${event.fingers} finger(s) detected`;

        details.append(name, count);

        const time = document.createElement("time");
        time.textContent = event.time;

        row.append(icon, details, time);
        list.appendChild(row);
    });
}

function updateChart() {
    setText("event-count", events.length);
    setText("chart-total", events.length);

    const lineElement = $("chart-line");
    const fillElement = $("chart-area-fill");

    if (!lineElement || !fillElement) return;

    const points = Array.from({ length: 13 }, (_, i) => {
        const event = events[i];
        return event ? 30 + (i % 4) * 20 : 115 - i * 2;
    });

    const line = points.map((y, i) => {
        const x = (i / 12) * 600;
        return `${i === 0 ? "M" : "L"}${x},${y}`;
    }).join(" ");

    lineElement.setAttribute("d", line);
    fillElement.setAttribute("d", `${line} L600,145 L0,145 Z`);
}

async function startCamera() {
    const button = $("connect-button");
    if (button) {
        button.disabled = true;
        button.textContent = "Connecting...";
    }

    try {
        const response = await fetch("/api/start", { method: "POST" });
        const data = await response.json();

        if (!response.ok || !data.ok) {
            throw new Error(data.message || "Could not connect camera");
        }

        cameraRunning = true;

        const feed = $("camera-feed");
        const placeholder = $("camera-placeholder");

        if (feed) {
            feed.src = `/video_feed?t=${Date.now()}`;
            feed.classList.remove("hidden");
        }

        if (placeholder) placeholder.classList.add("hidden");

        if (button) button.textContent = "Stop Camera";

        setText("camera-status", "Camera connected");
        setText("camera-subtitle", "Live detection is running");
        setText("session-status", "ACTIVE");
        setText("current-gesture", "Waiting for hand");
        setText("gesture-caption", "Show your hand to the camera");

        showToast("Camera connected successfully!");

        if (polling) clearInterval(polling);
        polling = setInterval(refreshStats, 1000);
        refreshStats();

    } catch (error) {
        cameraRunning = false;

        if (button) button.textContent = "Start Camera";

        showToast(error.message);
        setText("camera-status", "Connection failed");
        console.error(error);
    } finally {
        if (button) button.disabled = false;
    }
}

async function stopCamera() {
    const button = $("connect-button");
    if (button) {
        button.disabled = true;
        button.textContent = "Stopping...";
    }

    try {
        await fetch("/api/stop", { method: "POST" });
    } catch (error) {
        console.error(error);
    }

    cameraRunning = false;

    if (polling) {
        clearInterval(polling);
        polling = null;
    }

    const feed = $("camera-feed");
    const placeholder = $("camera-placeholder");

    if (feed) {
        feed.src = "";
        feed.classList.add("hidden");
    }

    if (placeholder) placeholder.classList.remove("hidden");

    if (button) {
        button.textContent = "Start Camera";
        button.disabled = false;
    }

    setText("camera-status", "Camera stopped");
    setText("camera-subtitle", "Start the camera to begin");
    setText("session-status", "READY");

    showToast("Camera stopped.");
}

async function refreshStats() {
    if (!cameraRunning) return;

    try {
        const response = await fetch("/api/stats");
        if (!response.ok) return;

        const data = await response.json();

        setText("camera-status", data.status);
        setText("current-gesture", data.gesture);
        setText("result-name", data.gesture);
        setText("finger-count", `${data.fingers} / 5`);
        setText("event-count", data.total_detections);
        setText("chart-total", data.total_detections);

        const progress = $("finger-progress");
        if (progress) {
            progress.style.width = `${Math.min(100, data.fingers * 20)}%`;
        }

        if (data.fingers > 0 && data.gesture !== "No hand detected") {
            recordGesture(data.gesture, data.fingers);
        }
    } catch (error) {
        console.error("Stats refresh failed:", error);
    }
}

const connectButton = $("connect-button");

if (connectButton) {
    connectButton.textContent = "Start Camera";

    connectButton.addEventListener("click", () => {
        if (cameraRunning) {
            stopCamera();
        } else {
            startCamera();
        }
    });
}

const clearButton = $("clear-history");

if (clearButton) {
    clearButton.addEventListener("click", () => {
        events = [];
        lastRecordedGesture = "";
        updateHistory();
        updateChart();
        showToast("Session history cleared.");
    });
}

updateHistory();
updateChart();
