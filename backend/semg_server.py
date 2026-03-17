import serial
import time
import numpy as np
from collections import deque
from scipy.signal import find_peaks
import asyncio
import websockets
import json
import threading

# ─────────────────────────────────────────
#  USER SETTINGS
# ─────────────────────────────────────────
PORT          = "COM7"
BAUD          = 115200
FS            = 200
REST_TIME     = 10
SPEECH_TIME   = 10
ONSET_FACTOR  = 2.5
OFFSET_FACTOR = 1.5
MIN_SPEECH_MS = 80
GRAPH_SECONDS = 5
GRAPH_POINTS  = FS * GRAPH_SECONDS
WS_PORT       = 8765   # ← NEW: WebSocket port

# ─────────────────────────────────────────
#  SERIAL SETUP
# ─────────────────────────────────────────
ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)
print("✅ Connected to ESP32 on", PORT)

# ─────────────────────────────────────────
#  BUFFERS
# ─────────────────────────────────────────
raw_buf        = deque(maxlen=40)
smooth_buf     = deque(maxlen=10)
graph_rms      = deque(maxlen=GRAPH_POINTS)
graph_smoothed = deque(maxlen=GRAPH_POINTS)
graph_norm     = deque(maxlen=GRAPH_POINTS)
graph_time     = deque(maxlen=GRAPH_POINTS)
graph_events   = []

baseline_rms  = None
mvc_rms       = None
onset_thresh  = None
offset_thresh = None
in_speech     = False
speech_start  = None
speech_count  = 0
session_start = None

# ← NEW: shared state for WebSocket broadcast
connected_clients = set()
latest_payload    = {}

# ─────────────────────────────────────────
#  CORE FUNCTIONS  (unchanged)
# ─────────────────────────────────────────
def read_raw():
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        try:
            val = float(line)
            if 0 <= val <= 4095:
                return val
        except ValueError:
            continue

def read_rms():
    val = read_raw()
    raw_buf.append(val)
    if len(raw_buf) < 40:
        return None
    dc  = np.mean(raw_buf)
    ac  = np.array(raw_buf) - dc
    return float(np.sqrt(np.mean(ac ** 2)))

def smooth_rms(rms_val):
    smooth_buf.append(rms_val)
    return float(np.mean(smooth_buf))

def normalize(value, rest, mvc):
    if mvc - rest <= 0:
        return 0.0
    return float(np.clip((value - rest) / (mvc - rest), 0.0, 1.0))

def collect_calibration(duration_sec, label):
    values = []
    start  = time.time()
    raw_buf.clear()
    while time.time() - start < duration_sec:
        rms = read_rms()
        if rms is not None:
            values.append(rms)
        remaining = duration_sec - (time.time() - start)
        print(f"  {label} — {remaining:.1f}s remaining   ", end="\r")
    print()
    return values

def intensity_bar(norm, width=20):
    filled = int(norm * width)
    return "█" * filled + "░" * (width - filled)

def strain_label(norm):
    if norm > 0.85:
        return "⚠️  HIGH STRAIN"
    elif norm > 0.6:
        return "⚡ MODERATE"
    else:
        return "✅ normal"

# ─────────────────────────────────────────
#  ← NEW: WEBSOCKET SERVER
# ─────────────────────────────────────────
async def ws_handler(websocket):
    """Handle a browser connection."""
    connected_clients.add(websocket)
    print(f"  🌐 Browser connected  (total: {len(connected_clients)})")
    try:
        # Send calibration info immediately on connect
        await websocket.send(json.dumps({
            "type": "calibration",
            "baseline": baseline_rms,
            "mvc":      mvc_rms,
            "onset":    onset_thresh,
            "offset":   offset_thresh,
        }))
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"  🌐 Browser disconnected (total: {len(connected_clients)})")

async def broadcast(payload):
    """Send JSON payload to all connected browsers."""
    if not connected_clients:
        return
    msg = json.dumps(payload)
    # Use asyncio.gather so all clients get it in parallel
    await asyncio.gather(
        *[ws.send(msg) for ws in list(connected_clients)],
        return_exceptions=True
    )

def start_ws_server():
    """Run the WebSocket server in its own thread + event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _serve():
        async with websockets.serve(ws_handler, "localhost", WS_PORT):
            print(f"  🌐 WebSocket server running on ws://localhost:{WS_PORT}")
            await asyncio.Future()   # run forever

    loop.run_until_complete(_serve())

# Start WebSocket server in background thread  ← NEW
ws_thread = threading.Thread(target=start_ws_server, daemon=True)
ws_thread.start()

# Keep a reference to the WS event loop so we can schedule broadcasts
_ws_loop = None
def _store_loop():
    global _ws_loop
    time.sleep(0.5)   # give thread time to create its loop
    import asyncio
    for t in threading.enumerate():
        if t is ws_thread:
            break
    # grab via introspection
_store_loop_thread = threading.Thread(target=_store_loop, daemon=True)
_store_loop_thread.start()

def broadcast_sync(payload):
    """Call broadcast() from the main (non-async) thread safely."""
    for loop in [t._target.__globals__.get('loop') 
                 for t in threading.enumerate() 
                 if hasattr(t, '_target') and t._target]:
        pass
    # Simpler approach: use a queue
    _broadcast_queue.put_nowait(payload)

import queue
_broadcast_queue = queue.Queue()

def _ws_broadcaster():
    """Dedicated thread: drains the queue and broadcasts over WebSocket."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        while True:
            try:
                payload = _broadcast_queue.get_nowait()
                await broadcast(payload)
            except queue.Empty:
                await asyncio.sleep(0.005)

    loop.run_until_complete(_run())

broadcaster_thread = threading.Thread(target=_ws_broadcaster, daemon=True)
broadcaster_thread.start()

# ─────────────────────────────────────────
#  STEP 1 — REST CALIBRATION  (unchanged)
# ─────────────────────────────────────────
print("\n══════════════════════════════════════")
print("  STEP 1 — REST CALIBRATION")
print("══════════════════════════════════════")
input("  Press Enter when ready...")
rest_vals    = collect_calibration(REST_TIME, "Recording rest")
baseline_rms = np.percentile(rest_vals, 75)
print(f"\n  ✔ Rest RMS baseline : {baseline_rms:.2f}")

# ─────────────────────────────────────────
#  STEP 2 — SPEECH CALIBRATION  (unchanged)
# ─────────────────────────────────────────
print("\n══════════════════════════════════════")
print("  STEP 2 — SPEECH CALIBRATION")
print("══════════════════════════════════════")
input("  Press Enter, then immediately start speaking...")
speech_vals   = collect_calibration(SPEECH_TIME, "Recording speech")
mvc_rms       = np.percentile(speech_vals, 90)
snr           = mvc_rms / baseline_rms if baseline_rms > 0 else 0
signal_range  = mvc_rms - baseline_rms
onset_thresh  = baseline_rms + (signal_range * 0.35)
offset_thresh = baseline_rms + (signal_range * 0.15)

print(f"\n  ✔ Max speech RMS    : {mvc_rms:.2f}")
print(f"  ✔ Onset  threshold  : {onset_thresh:.2f}")
print(f"  ✔ Offset threshold  : {offset_thresh:.2f}")

# ─────────────────────────────────────────
#  STEP 3 — REAL-TIME MONITORING
# ─────────────────────────────────────────
print("\n══════════════════════════════════════")
print("  STEP 3 — REAL-TIME SPEECH DETECTION")
print("══════════════════════════════════════")
print("  Speak naturally. Press Ctrl+C to stop.\n")

smooth_buf.clear()
session_start        = time.time()
graph_update_counter = 0

try:
    while True:
        rms_val = read_rms()
        if rms_val is None:
            continue

        smoothed = smooth_rms(rms_val)
        norm     = normalize(smoothed, baseline_rms, mvc_rms)
        now_ms   = time.time() * 1000
        now_s    = time.time() - session_start

        graph_rms.append(rms_val)
        graph_smoothed.append(smoothed)
        graph_norm.append(norm)
        graph_time.append(now_s)

        is_speaking = (smoothed > onset_thresh) or (norm > 0.40)
        is_silent   = (smoothed < offset_thresh) and (norm < 0.25)
        event_label = None

        if not in_speech and is_speaking:
            in_speech    = True
            speech_start = now_ms
            speech_count += 1
            graph_events.append((now_s, 'START'))
            event_label = "SPEECH_START"
            event = "🔴 SPEECH START"

        elif in_speech and is_silent:
            duration_ms = now_ms - speech_start
            in_speech   = False
            if duration_ms > MIN_SPEECH_MS:
                graph_events.append((now_s, 'END'))
                event_label = "SPEECH_END"
                event = f"⭕ END ({duration_ms:.0f}ms)"
            else:
                speech_count -= 1
                event = "   (noise, ignored)"
        else:
            event = "🔴 speaking..." if in_speech else "   silence"

        # ← NEW: broadcast to browser every sample
        _broadcast_queue.put_nowait({
            "type":        "sample",
            "t":           round(now_s, 3),
            "rms":         round(rms_val, 3),
            "smoothed":    round(smoothed, 3),
            "norm":        round(norm, 4),
            "in_speech":   in_speech,
            "speech_count": speech_count,
            "event":       event_label,   # "SPEECH_START" | "SPEECH_END" | null
        })

        bar = intensity_bar(norm)
        print(
            f"  {rms_val:7.2f} | {smoothed:8.2f} | {norm:5.2f} | "
            f"{bar} | {event}  {strain_label(norm)}  [bursts: {speech_count}]"
        )

except KeyboardInterrupt:
    print("\n\n══════════════════════════════════════")
    print("  SESSION SUMMARY")
    print("══════════════════════════════════════")
    print(f"  Total speech bursts : {speech_count}")
    print(f"  Rest baseline       : {baseline_rms:.2f}")
    print(f"  Max speech RMS      : {mvc_rms:.2f}")
    print(f"  SNR                 : {snr:.1f}×")
    ser.close()
    print("  Serial port closed.")