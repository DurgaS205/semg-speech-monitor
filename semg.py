import serial
import time
import numpy as np
from collections import deque
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# ─────────────────────────────────────────
#  USER SETTINGS
# ─────────────────────────────────────────
PORT          = "COM7"
BAUD          = 115200
FS            = 200

REST_TIME     = 10
SPEECH_TIME   = 10
MIN_SPEECH_MS = 80

GRAPH_SECONDS  = 5
GRAPH_POINTS   = FS * GRAPH_SECONDS
SESSION_LIMIT  = 120          # ← auto-stop after 2 minutes (120 seconds)

RAW_BUF_SIZE    = 20
SMOOTH_BUF_SIZE = 3
GRAPH_UPDATE_N  = 3

# ─────────────────────────────────────────
#  SERIAL SETUP
# ─────────────────────────────────────────
ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)
print("✅ Connected to ESP32 on", PORT)

# ─────────────────────────────────────────
#  BUFFERS
# ─────────────────────────────────────────
raw_buf        = deque(maxlen=RAW_BUF_SIZE)
smooth_buf     = deque(maxlen=SMOOTH_BUF_SIZE)
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

# ─────────────────────────────────────────
#  CORE FUNCTIONS
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
    if len(raw_buf) < RAW_BUF_SIZE:
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

def format_time(seconds):
    """Format seconds as MM:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m:02d}:{s:02d}"

def save_and_exit():
    """Clean shutdown — save graph and print summary."""
    print("\n\n══════════════════════════════════════")
    print("  SESSION SUMMARY")
    print("══════════════════════════════════════")
    print(f"  Total speech bursts : {speech_count}")
    print(f"  Rest baseline RMS   : {baseline_rms:.2f}")
    print(f"  Max speech RMS      : {mvc_rms:.2f}")
    print(f"  Signal range        : {signal_range:.2f}")
    print(f"  Signal-to-noise     : {snr:.1f}×")
    print(f"  Pipeline latency    : ~{total_latency_ms:.0f}ms")
    print(f"  Session duration    : {format_time(SESSION_LIMIT)}")
    ser.close()
    print("  Serial port closed.")
    print("══════════════════════════════════════")

    plt.ioff()
    save_path = "semg_session.png"
    plt.savefig(save_path, dpi=150, bbox_inches='tight', facecolor='#1e1e1e')
    print(f"  Graph saved → {save_path}")
    plt.show()

# ─────────────────────────────────────────
#  STEP 1 — REST CALIBRATION
# ─────────────────────────────────────────
print("\n══════════════════════════════════════")
print("  STEP 1 — REST CALIBRATION")
print("══════════════════════════════════════")
print("  • Sit still, jaw and neck fully relaxed")
print("  • Do NOT speak, swallow, or move")
print()
input("  Press Enter when ready...")

rest_vals    = collect_calibration(REST_TIME, "Recording rest")
baseline_rms = np.percentile(rest_vals, 75)
print(f"\n  ✔ Rest RMS baseline : {baseline_rms:.2f}")

# ─────────────────────────────────────────
#  STEP 2 — SPEECH CALIBRATION
# ─────────────────────────────────────────
print("\n══════════════════════════════════════")
print("  STEP 2 — SPEECH CALIBRATION")
print("══════════════════════════════════════")
print("  • Say 'AAAAAAA' loudly and continuously")
print("  • Keep going for the full duration")
print()
input("  Press Enter, then immediately start speaking...")

speech_vals = collect_calibration(SPEECH_TIME, "Recording speech")
mvc_rms     = np.percentile(speech_vals, 90)
snr         = mvc_rms / baseline_rms if baseline_rms > 0 else 0

signal_range  = mvc_rms - baseline_rms
onset_thresh  = baseline_rms + (signal_range * 0.35)
offset_thresh = baseline_rms + (signal_range * 0.15)

total_latency_ms = (RAW_BUF_SIZE + SMOOTH_BUF_SIZE + GRAPH_UPDATE_N) / FS * 1000

print(f"\n  ✔ Max speech RMS    : {mvc_rms:.2f}")
print(f"  ✔ Signal range      : {signal_range:.2f}")
print(f"  ✔ SNR               : {snr:.1f}×")
print(f"  ✔ Onset  threshold  : {onset_thresh:.2f}")
print(f"  ✔ Offset threshold  : {offset_thresh:.2f}")
print(f"  ✔ Latency           : ~{total_latency_ms:.0f}ms")
print(f"  ✔ Session will auto-stop at : {format_time(SESSION_LIMIT)}")

if snr < 1.3:
    print("\n  ⚠️  LOW SNR — check electrode placement")
elif snr >= 2.0:
    print("\n  ✅ Excellent signal quality!")
else:
    print("\n  ✅ Signal OK — proceeding")

# ─────────────────────────────────────────
#  SETUP LIVE GRAPH
# ─────────────────────────────────────────
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 7))
fig.patch.set_facecolor('#1e1e1e')
fig.suptitle(
    f'sEMG Speech Muscle Monitor  |  latency ~{total_latency_ms:.0f}ms  |  auto-stop {format_time(SESSION_LIMIT)}',
    color='white', fontsize=12, fontweight='bold'
)

for ax in (ax1, ax2):
    ax.set_facecolor('#2b2b2b')
    ax.tick_params(colors='white')
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.title.set_color('white')
    for spine in ax.spines.values():
        spine.set_edgecolor('#444444')

# ── Top plot ──────────────────────────────────────────────
ax1.set_title('sEMG RMS Signal + Peaks', fontsize=11)
ax1.set_ylabel('RMS Value')
ax1.set_xlabel('Time (s)')

y_bottom = max(0, baseline_rms * 0.5)
y_top    = max(mvc_rms * 1.3, baseline_rms * 2)
ax1.set_ylim(y_bottom, y_top)

line_rms,      = ax1.plot([], [], color='#00cfff', linewidth=1.2, label='Raw RMS')
line_smooth,   = ax1.plot([], [], color='#ff9f40', linewidth=1.8, label='Smoothed', alpha=0.85)
line_onset,    = ax1.plot([], [], color='#ff4444', linewidth=1.0, linestyle='--', label=f'Onset ({onset_thresh:.2f})')
line_offset,   = ax1.plot([], [], color='#ffaa00', linewidth=1.0, linestyle='--', label=f'Offset ({offset_thresh:.2f})')
scatter_peaks, = ax1.plot([], [], 'v', color='#ff0066', markersize=9, label='Peaks', zorder=5)
ax1.legend(loc='upper left', facecolor='#333333', labelcolor='white', fontsize=8, framealpha=0.8)

# Timer text in top right of ax1
timer_text = ax1.text(
    0.98, 0.95, f"⏱ {format_time(SESSION_LIMIT)} remaining",
    transform=ax1.transAxes,
    color='#ffffff', fontsize=9,
    ha='right', va='top',
    bbox=dict(boxstyle='round,pad=0.3', facecolor='#333333', alpha=0.8)
)

# ── Bottom plot ───────────────────────────────────────────
ax2.set_title('Muscle Activation (Normalized 0–1)', fontsize=11)
ax2.set_ylabel('Activation')
ax2.set_xlabel('Time (s)')
ax2.set_ylim(-0.05, 1.15)

line_norm, = ax2.plot([], [], color='#7fff00', linewidth=1.5, label='Norm activation')
ax2.axhline(y=0.40, color='#ff4444', linestyle='--', linewidth=1, alpha=0.7, label='Detection threshold (0.40)')
ax2.legend(loc='upper left', facecolor='#333333', labelcolor='white', fontsize=8, framealpha=0.8)

plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.ion()
plt.show()

# ─────────────────────────────────────────
#  STEP 3 — REAL-TIME MONITORING + GRAPH
# ─────────────────────────────────────────
print("\n══════════════════════════════════════")
print("  STEP 3 — REAL-TIME SPEECH DETECTION")
print("══════════════════════════════════════")
print(f"  Session runs for {format_time(SESSION_LIMIT)} then auto-stops.")
print("  Or press Ctrl+C to stop early.\n")
print(f"  {'RMS':>7} | {'Smoothed':>8} | {'Norm':>5} | {'Intensity':<22} | Event")
print("  " + "─" * 75)

smooth_buf.clear()
session_start        = time.time()
graph_update_counter = 0
speech_vlines        = []
fill_collection      = [None]

try:
    while True:
        # ── Check 2-minute limit ───────────────────────────
        elapsed   = time.time() - session_start
        remaining = SESSION_LIMIT - elapsed

        if remaining <= 0:
            print(f"\n  ⏱ 2-minute session complete — auto-stopping.")
            break

        rms_val = read_rms()
        if rms_val is None:
            continue

        smoothed = smooth_rms(rms_val)
        norm     = normalize(smoothed, baseline_rms, mvc_rms)
        now_ms   = time.time() * 1000
        now_s    = elapsed   # use elapsed, NOT raw time() — fixes timestamp bug

        graph_rms.append(rms_val)
        graph_smoothed.append(smoothed)
        graph_norm.append(norm)
        graph_time.append(now_s)

        # ── Dual speech detection ──────────────────────────
        is_speaking = (smoothed > onset_thresh) or (norm > 0.40)
        is_silent   = (smoothed < offset_thresh) and (norm < 0.25)

        if not in_speech and is_speaking:
            in_speech    = True
            speech_start = now_ms
            speech_count += 1
            graph_events.append((now_s, 'START'))
            event = "🔴 SPEECH START"

        elif in_speech and is_silent:
            duration_ms = now_ms - speech_start
            in_speech   = False
            if duration_ms > MIN_SPEECH_MS:
                graph_events.append((now_s, 'END'))
                event = f"⭕ END ({duration_ms:.0f}ms)"
            else:
                speech_count -= 1
                event = "   (noise, ignored)"
        else:
            event = "🔴 speaking..." if in_speech else "   silence"

        bar = intensity_bar(norm)
        print(
            f"  {rms_val:7.2f} | "
            f"{smoothed:8.2f} | "
            f"{norm:5.2f} | "
            f"{bar} | "
            f"{event}  {strain_label(norm)}  "
            f"[bursts:{speech_count}]  "
            f"[{format_time(remaining)}]"    # ← countdown shown every line
        )

        # ── Update graph every GRAPH_UPDATE_N samples ─────
        graph_update_counter += 1
        if graph_update_counter % GRAPH_UPDATE_N == 0 and len(graph_time) > 2:

            t_arr  = np.array(graph_time)
            r_arr  = np.array(graph_rms)
            sm_arr = np.array(graph_smoothed)
            n_arr  = np.array(graph_norm)

            line_rms.set_data(t_arr,    r_arr)
            line_smooth.set_data(t_arr, sm_arr)
            line_norm.set_data(t_arr,   n_arr)

            x_min = t_arr[-1] - GRAPH_SECONDS
            x_max = t_arr[-1] + 0.2
            line_onset.set_data( [x_min, x_max], [onset_thresh,  onset_thresh])
            line_offset.set_data([x_min, x_max], [offset_thresh, offset_thresh])

            # Peaks
            if len(sm_arr) > 10:
                peaks, _ = find_peaks(
                    sm_arr,
                    height=onset_thresh,
                    distance=int(FS * 0.2)
                )
                scatter_peaks.set_data(
                    t_arr[peaks] if len(peaks) > 0 else [],
                    sm_arr[peaks] if len(peaks) > 0 else []
                )

            # Fill under norm
            if fill_collection[0] is not None:
                fill_collection[0].remove()
            fill_collection[0] = ax2.fill_between(
                t_arr, n_arr, alpha=0.2, color='#7fff00'
            )

            # Speech event vertical lines
            for vl in speech_vlines:
                vl.remove()
            speech_vlines.clear()
            for ev_t, ev_label in graph_events:
                if x_min <= ev_t <= x_max:
                    color = '#ff4444' if ev_label == 'START' else '#44ff88'
                    vl = ax1.axvline(x=ev_t, color=color, linewidth=1.2,
                                     alpha=0.8, linestyle=':')
                    speech_vlines.append(vl)

            # Dynamic Y scaling
            if len(sm_arr) > 0:
                current_max = max(sm_arr.max(), onset_thresh * 1.1)
                current_min = max(0, sm_arr.min() * 0.8)
                ax1.set_ylim(current_min, current_max * 1.15)

            ax1.set_xlim(x_min, x_max)
            ax2.set_xlim(x_min, x_max)

            # ── Update countdown timer on graph ───────────
            timer_color = '#ff4444' if remaining < 30 else '#ffffff'
            timer_text.set_text(f"{format_time(remaining)} remaining")
            timer_text.set_color(timer_color)

            fig.canvas.draw_idle()
            fig.canvas.flush_events()

except KeyboardInterrupt:
    print(f"\n  Stopped manually at {format_time(elapsed)}.")

finally:
    save_and_exit()
