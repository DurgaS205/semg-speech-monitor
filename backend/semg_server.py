import asyncio
import websockets
import json
import time
import threading
from collections import deque
import numpy as np
import serial
from flask import Flask, jsonify
from flask_cors import CORS

PORT            = "COM7"
BAUD            = 115200
FS              = 200

REST_TIME       = 10          
SPEECH_TIME     = 10         
MIN_SPEECH_MS   = 80          

RAW_BUF_SIZE    = 20         
SMOOTH_BUF_SIZE = 3           
STRAIN_BUF_SIZE = 40          

WS_PORT         = 8765
API_PORT        = 5000

CV_MODERATE_THRESH = 0.25     
CV_HIGH_THRESH     = 0.45     

TENSION_THRESH_RATIO = 0.30   

connected_clients = set()

baseline_rms  = 0.0
mvc_rms       = 0.0
signal_range  = 0.0
onset_thresh  = 0.0
offset_thresh = 0.0
snr           = 0.0

session_active  = False
session_start_t = None

app = Flask(__name__)
CORS(app)

@app.route('/start', methods=['POST'])
def api_start():
    global session_active, session_start_t
    session_active  = True
    session_start_t = time.time()
    print("\n  ▶  Session STARTED from browser")
    return jsonify({"status": "started", "time": session_start_t})

@app.route('/stop', methods=['POST'])
def api_stop():
    global session_active, session_start_t
    session_active = False
    duration = round(time.time() - session_start_t, 2) if session_start_t else 0
    m = int(duration) // 60
    s = int(duration) % 60

    print(f"\n  ■  Session STOPPED  ({m:02d}:{s:02d})")
    print("\n══════════════════════════════════════")
    print("  SESSION SUMMARY")
    print("══════════════════════════════════════")
    print(f"  Session duration    : {m:02d}:{s:02d}")
    print(f"  Rest baseline RMS   : {baseline_rms:.2f}")
    print(f"  Max speech RMS      : {mvc_rms:.2f}")
    print(f"  Signal range        : {signal_range:.2f}")
    print(f"  Signal-to-noise     : {snr:.1f}×")
    print(f"  Onset threshold     : {onset_thresh:.2f}")
    print(f"  Offset threshold    : {offset_thresh:.2f}")
    print(f"  Strain detection    : CV > {CV_MODERATE_THRESH} moderate, CV > {CV_HIGH_THRESH} high")
    print("══════════════════════════════════════\n")

    return jsonify({"status": "stopped", "duration": duration})

@app.route('/status', methods=['GET'])
def api_status():
    return jsonify({
        "session_active":    session_active,
        "baseline":          round(float(baseline_rms), 3),
        "mvc":               round(float(mvc_rms), 3),
        "onset":             round(float(onset_thresh), 3),
        "offset":            round(float(offset_thresh), 3),
        "snr":               round(float(snr), 2),
        "cv_moderate_thresh": CV_MODERATE_THRESH,
        "cv_high_thresh":     CV_HIGH_THRESH,
    })

def run_flask():
    app.run(host='0.0.0.0', port=API_PORT, debug=False, use_reloader=False)

def setup_hardware():
    global baseline_rms, mvc_rms, signal_range, onset_thresh, offset_thresh, snr

    print(f"\n  Connecting to ESP32 on {PORT} at {BAUD} baud...")
    ser = serial.Serial(PORT, BAUD, timeout=1)
    time.sleep(2)
    ser.reset_input_buffer()
    print(f"  ✅  Connected to ESP32 on {PORT}\n")

    raw_buf    = deque(maxlen=RAW_BUF_SIZE)
    smooth_buf = deque(maxlen=SMOOTH_BUF_SIZE)
    strain_buf = deque(maxlen=STRAIN_BUF_SIZE)  

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
        if len(raw_buf) < RAW_BUF_SIZE:
            return None
        dc = np.mean(raw_buf)
        ac = np.array(raw_buf) - dc
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

    print("══════════════════════════════════════")
    print("  STEP 1 — REST CALIBRATION")
    print("══════════════════════════════════════")
    print("  • Sit still, jaw and neck fully relaxed")
    print("  • Do NOT speak, swallow, or move\n")
    input("  Press Enter when ready...")

    rest_vals    = collect_calibration(REST_TIME, "Recording rest")
    baseline_rms = float(np.percentile(rest_vals, 75))
    baseline_std = float(np.std(rest_vals))
    print(f"\n  ✔  Rest RMS baseline : {baseline_rms:.2f}  (std: {baseline_std:.2f})")

    print("\n══════════════════════════════════════")
    print("  STEP 2 — SPEECH CALIBRATION")
    print("══════════════════════════════════════")
    print("  • Say 'AAAAAAA' loudly and continuously")
    print("  • Speak naturally — not forced or tense\n")
    input("  Press Enter, then immediately start speaking...")

    speech_vals   = collect_calibration(SPEECH_TIME, "Recording speech")
    mvc_rms       = float(np.percentile(speech_vals, 90))
    snr           = mvc_rms / baseline_rms if baseline_rms > 0 else 0
    signal_range  = mvc_rms - baseline_rms

    onset_thresh  = baseline_rms + signal_range * 0.25  
    offset_thresh = baseline_rms + signal_range * 0.10  
    
    tension_thresh = baseline_rms + signal_range * TENSION_THRESH_RATIO

    total_latency_ms = (RAW_BUF_SIZE + SMOOTH_BUF_SIZE) / FS * 1000

    if snr < 1.3:
        print("\n  ⚠️  LOW SNR — check electrode placement and redo calibration")
    elif snr >= 2.0:
        print("\n  ✅  Excellent signal quality!")
    else:
        print("\n  ✅  Signal OK")

    print(f"\n  🚀  Ready! Open browser → semg.html → click Start Session\n")

    in_speech_hw    = False
    speech_start_ms = None
    speech_count_hw = 0
    server_start_t  = time.time()
    smooth_buf.clear()
    strain_buf.clear()

    def compute_strain(smoothed, in_speech):
        """
        Strain is computed from two signals:

        1. Coefficient of Variation (CV) of recent smoothed RMS.
           CV = std / mean over ~200ms window.
           - Normal speech: low CV (consistent activation)
           - Stuttering: high CV (erratic bursts and breaks)

        2. Tension during silence: if smoothed RMS stays elevated
           above tension_thresh even when NOT speaking, muscles
           are tense — indicates strain.

        Returns: 'high' | 'moderate' | 'normal'
        """
        strain_buf.append(smoothed)

        if len(strain_buf) < STRAIN_BUF_SIZE // 2:
            return "normal" 

        arr  = np.array(strain_buf)
        mean = np.mean(arr)
        std  = np.std(arr)
        cv   = std / mean if mean > 0 else 0

        if not in_speech and smoothed > tension_thresh:
            return "high"

        if in_speech:
            if cv > CV_HIGH_THRESH:
                return "high"
            elif cv > CV_MODERATE_THRESH:
                return "moderate"

        return "normal"

    def next_sample():
        nonlocal in_speech_hw, speech_start_ms, speech_count_hw
        global session_active

        rms_val = read_rms()
        if rms_val is None:
            return None

        smoothed = smooth_rms(rms_val)
        norm     = normalize(smoothed, baseline_rms, mvc_rms)
        now_ms   = time.time() * 1000
        elapsed  = time.time() - server_start_t

        event  = None
        strain = compute_strain(smoothed, in_speech_hw)

        is_speaking = smoothed > onset_thresh
        is_silent   = smoothed < offset_thresh

        if session_active:
            if not in_speech_hw and is_speaking:
                in_speech_hw    = True
                speech_start_ms = now_ms
                speech_count_hw += 1
                event = "SPEECH_START"
                print(f"  🔴 START  [#{speech_count_hw}]  "
                      f"rms={rms_val:.1f}  norm={norm:.2f}  strain={strain}")

            elif in_speech_hw and is_silent:
                duration_ms  = now_ms - speech_start_ms
                in_speech_hw = False
                if duration_ms > MIN_SPEECH_MS:
                    event = "SPEECH_END"
                    print(f"  ⭕  END  ({duration_ms:.0f}ms)  strain={strain}")
                else:
                    speech_count_hw -= 1  
        else:
            if in_speech_hw:
                in_speech_hw = False
                event = "SPEECH_END"

        return {
            "type":           "sample",
            "t":              round(elapsed, 3),
            "rms":            round(rms_val, 3),
            "smoothed":       round(smoothed, 3),
            "norm":           round(norm, 4),
            "in_speech":      in_speech_hw,
            "speech_count":   speech_count_hw,
            "event":          event,
            "session_active": session_active,
            "strain":         strain,        
        }

    return next_sample, ser

async def ws_handler(websocket):
    global connected_clients
    connected_clients.add(websocket)
    print(f"  🌐  Browser connected  (clients: {len(connected_clients)})")
    try:
        await websocket.send(json.dumps({
            "type":     "calibration",
            "baseline": round(float(baseline_rms), 3),
            "mvc":      round(float(mvc_rms), 3),
            "onset":    round(float(onset_thresh), 3),
            "offset":   round(float(offset_thresh), 3),
            "snr":      round(float(snr), 2),
        }))
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"  🌐  Browser disconnected (clients: {len(connected_clients)})")

async def send_to_all(payload):
    global connected_clients
    if not connected_clients:
        return
    msg  = json.dumps(payload)
    dead = set()
    for ws in list(connected_clients):
        try:
            await ws.send(msg)
        except Exception:
            dead.add(ws)
    connected_clients -= dead

async def broadcast_loop(next_sample_fn):
    loop = asyncio.get_event_loop()
    while True:
        payload = await loop.run_in_executor(None, next_sample_fn)
        if payload is not None:
            await send_to_all(payload)

async def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"  🔌  REST API  → http://localhost:{API_PORT}")

    next_sample_fn, ser = setup_hardware()

    print(f"  🌐  WebSocket → ws://localhost:{WS_PORT}")
    print(f"  ⏹   Press Ctrl+C to stop\n")

    try:
        async with websockets.serve(ws_handler, "localhost", WS_PORT):
            await broadcast_loop(next_sample_fn)
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        print("\n  Serial port closed.")
        print("  Server stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  Server stopped.")
