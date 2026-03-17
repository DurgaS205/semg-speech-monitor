import serial
import time
import numpy as np
from collections import deque

# ─────────────────────────────────────────
#  USER SETTINGS
# ─────────────────────────────────────────
PORT          = "COM7"       # change to your port
BAUD          = 115200
FS            = 200          # samples per second

REST_TIME     = 10           # seconds for rest calibration
SPEECH_TIME   = 10           # seconds for speech calibration

ONSET_FACTOR  = 2.5          # RMS must be 2.5x baseline to detect speech
OFFSET_FACTOR = 1.5          # RMS must drop to 1.5x baseline to detect silence
MIN_SPEECH_MS = 80           # ignore bursts shorter than this (ms)

# ─────────────────────────────────────────
#  SERIAL SETUP
# ─────────────────────────────────────────
ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)
print("✅ Connected to ESP32 on", PORT)

# ─────────────────────────────────────────
#  BUFFERS
# ─────────────────────────────────────────
raw_buf    = deque(maxlen=40)   # for DC removal + RMS computation
smooth_buf = deque(maxlen=10)   # for smoothing RMS output

baseline_rms = None
mvc_rms      = None
in_speech    = False
speech_start = None
speech_count = 0

# ─────────────────────────────────────────
#  CORE FUNCTIONS
# ─────────────────────────────────────────
def read_raw():
    """Read one valid raw ADC integer from serial."""
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        try:
            val = float(line)
            if 0 <= val <= 4095:
                return val
        except ValueError:
            continue

def read_rms():
    """
    Read raw ADC, remove DC offset, compute true AC RMS.
    Returns None until buffer is full (first 40 samples).
    """
    val = read_raw()
    raw_buf.append(val)

    if len(raw_buf) < 40:
        return None                          # not enough data yet

    dc  = np.mean(raw_buf)                  # rolling DC baseline (~2720 etc)
    ac  = np.array(raw_buf) - dc            # remove DC, keep muscle signal
    rms = float(np.sqrt(np.mean(ac ** 2)))  # true RMS of AC component
    return rms

def smooth_rms(rms_val):
    """Apply simple moving average to RMS."""
    smooth_buf.append(rms_val)
    return float(np.mean(smooth_buf))

def normalize(value, rest, mvc):
    """Normalize RMS to 0.0–1.0 range."""
    if mvc - rest <= 0:
        return 0.0
    return float(np.clip((value - rest) / (mvc - rest), 0.0, 1.0))

def collect_calibration(duration_sec, label):
    """Collect RMS values for a fixed duration. Returns list of values."""
    values = []
    start  = time.time()
    raw_buf.clear()                          # fresh buffer for calibration

    while time.time() - start < duration_sec:
        rms = read_rms()
        if rms is not None:
            values.append(rms)
        remaining = duration_sec - (time.time() - start)
        print(f"  {label} — {remaining:.1f}s remaining   ", end="\r")

    print()
    return values

def intensity_bar(norm, width=20):
    """Draw a text bar showing muscle intensity."""
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
#  STEP 1 — REST CALIBRATION
# ─────────────────────────────────────────
print("\n══════════════════════════════════════")
print("  STEP 1 — REST CALIBRATION")
print("══════════════════════════════════════")
print("  • Sit still, jaw relaxed")
print("  • Do NOT speak, swallow, or move")
print()
input("  Press Enter when ready...")

rest_vals    = collect_calibration(REST_TIME, "Recording rest")
baseline_rms = np.percentile(rest_vals, 75)   # 75th percentile — robust to spikes

onset_thresh  = baseline_rms * ONSET_FACTOR
offset_thresh = baseline_rms * OFFSET_FACTOR

print(f"\n  ✔ Rest RMS baseline      : {baseline_rms:.2f}")
print(f"  ✔ Speech onset threshold : {onset_thresh:.2f}")
print(f"  ✔ Speech offset threshold: {offset_thresh:.2f}")

# ─────────────────────────────────────────
#  STEP 2 — SPEECH CALIBRATION (MVC)
# ─────────────────────────────────────────
print("\n══════════════════════════════════════")
print("  STEP 2 — SPEECH CALIBRATION")
print("══════════════════════════════════════")
print("  • Say 'AAAAAAA' loudly and continuously")
print("  • Keep going for the full duration")
print()
input("  Press Enter, then immediately start speaking...")

speech_vals = collect_calibration(SPEECH_TIME, "Recording speech")
mvc_rms     = np.percentile(speech_vals, 90)  # 90th percentile — ignores brief drops

print(f"\n  ✔ Max speech RMS (MVC)   : {mvc_rms:.2f}")
print(f"  ✔ Signal-to-noise ratio  : {mvc_rms / baseline_rms:.1f}×")

if mvc_rms <= baseline_rms * 1.5:
    print("\n  ⚠️  WARNING: Speech signal too close to baseline!")
    print("     → Press electrodes more firmly onto skin")
    print("     → Move electrodes to jaw muscle (masseter)")
    print("     → Wet the gel pads slightly")
elif mvc_rms / baseline_rms >= 3.0:
    print("\n  ✅ Excellent signal quality!")
else:
    print("\n  ✅ Calibration OK — detection should work")

# ─────────────────────────────────────────
#  STEP 3 — REAL-TIME MONITORING
# ─────────────────────────────────────────
print("\n══════════════════════════════════════")
print("  STEP 3 — REAL-TIME SPEECH DETECTION")
print("══════════════════════════════════════")
print("  Speak naturally. Press Ctrl+C to stop.\n")
print(f"  {'RMS':>7} | {'Smoothed':>8} | {'Norm':>5} | {'Intensity':<22} | Event")
print("  " + "─" * 72)

smooth_buf.clear()   # fresh smoothing buffer

try:
    while True:
        rms_val = read_rms()
        if rms_val is None:
            continue

        smoothed = smooth_rms(rms_val)
        norm     = normalize(smoothed, baseline_rms, mvc_rms)
        now      = time.time() * 1000   # current time in ms

        # ── Speech Activity Detection ─────────────────
        if not in_speech and smoothed > onset_thresh:
            in_speech    = True
            speech_start = now
            speech_count += 1
            event = "🔴 SPEECH START"

        elif in_speech and smoothed < offset_thresh:
            duration_ms = now - speech_start
            in_speech   = False

            if duration_ms > MIN_SPEECH_MS:
                event = f"⭕ END ({duration_ms:.0f}ms)"
            else:
                speech_count -= 1          # too short — noise burst
                event = "   (noise, ignored)"

        else:
            event = "🔴 speaking..." if in_speech else "   silence"

        # ── Print Row ─────────────────────────────────
        bar = intensity_bar(norm)
        print(
            f"  {rms_val:7.2f} | "
            f"{smoothed:8.2f} | "
            f"{norm:5.2f} | "
            f"{bar} | "
            f"{event}  {strain_label(norm)}  "
            f"[bursts: {speech_count}]"
        )

except KeyboardInterrupt:
    print("\n\n══════════════════════════════════════")
    print("  SESSION SUMMARY")
    print("══════════════════════════════════════")
    print(f"  Total speech bursts : {speech_count}")
    print(f"  Rest baseline RMS   : {baseline_rms:.2f}")
    print(f"  Max speech RMS      : {mvc_rms:.2f}")
    print(f"  Signal-to-noise     : {mvc_rms / baseline_rms:.1f}×")
    ser.close()
    print("  Serial port closed.")
    print("══════════════════════════════════════")