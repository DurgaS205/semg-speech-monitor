// ─────────────────────────────────────────
//  CONFIG
// ─────────────────────────────────────────
const WS_URL       = 'ws://localhost:8765';
const MAX_POINTS   = 1000;   // points kept in chart at once
const CHART_WINDOW = 5;      // seconds visible on x-axis

// ─────────────────────────────────────────
//  WEBSOCKET
// ─────────────────────────────────────────
let ws            = null;
let calibration   = {};
let reconnectTimer = null;

const wsDot   = document.getElementById('wsDot');
const wsLabel = document.getElementById('wsLabel');

function setWsStatus(state) {
  wsDot.className  = 'ws-dot ' + state;
  wsLabel.textContent = {
    connected:    'Live',
    disconnected: 'Disconnected',
    connecting:   'Connecting…',
  }[state] || 'Connecting…';
}

function connect() {
  setWsStatus('connecting');
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setWsStatus('connected');
    clearTimeout(reconnectTimer);
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'calibration') {
      calibration = msg;
      applyCalibration(msg);
    } else if (msg.type === 'sample') {
      handleSample(msg);
    }
  };

  ws.onclose = () => {
    setWsStatus('disconnected');
    reconnectTimer = setTimeout(connect, 3000);  // auto-reconnect
  };

  ws.onerror = () => ws.close();
}

connect();

// ─────────────────────────────────────────
//  CHART.JS SETUP
// ─────────────────────────────────────────
const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,           // no animation — real-time data
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#1a2c5b',
      titleColor: '#fff',
      bodyColor: '#c8d4f0',
      padding: 10,
      cornerRadius: 8,
    },
  },
  scales: {
    x: {
      type: 'linear',
      grid:   { color: 'rgba(220,228,245,0.5)' },
      ticks:  { color: '#6b7a9d', font: { size: 11 }, maxTicksLimit: 6,
                callback: v => v.toFixed(1) + 's' },
      border: { color: '#dce4f5' },
    },
    y: {
      grid:   { color: 'rgba(220,228,245,0.5)' },
      ticks:  { color: '#6b7a9d', font: { size: 11 } },
      border: { color: '#dce4f5' },
    },
  },
};

// ── RMS Chart ──────────────────────────────────────────────
const rmsCtx   = document.getElementById('rmsChart').getContext('2d');
const rmsChart = new Chart(rmsCtx, {
  type: 'line',
  data: {
    datasets: [
      {
        label: 'Raw RMS',
        data: [],
        borderColor:     '#00cfff',
        backgroundColor: 'transparent',
        borderWidth:     1.2,
        pointRadius:     0,
        tension:         0.2,
      },
      {
        label: 'Smoothed',
        data: [],
        borderColor:     '#ff9f40',
        backgroundColor: 'transparent',
        borderWidth:     1.8,
        pointRadius:     0,
        tension:         0.3,
      },
      {
        label: 'Onset threshold',
        data: [],
        borderColor:     '#ff4444',
        backgroundColor: 'transparent',
        borderWidth:     1,
        borderDash:      [5, 4],
        pointRadius:     0,
      },
      {
        label: 'Offset threshold',
        data: [],
        borderColor:     '#ffaa00',
        backgroundColor: 'transparent',
        borderWidth:     1,
        borderDash:      [5, 4],
        pointRadius:     0,
      },
    ],
  },
  options: {
    ...chartDefaults,
    scales: {
      ...chartDefaults.scales,
      y: {
        ...chartDefaults.scales.y,
        title: { display: true, text: 'RMS Value', color: '#6b7a9d', font: { size: 11 } },
      },
    },
  },
});

// ── Norm Chart ─────────────────────────────────────────────
const normCtx   = document.getElementById('normChart').getContext('2d');
const normChart = new Chart(normCtx, {
  type: 'line',
  data: {
    datasets: [
      {
        label: 'Activation',
        data: [],
        borderColor:     '#7fff00',
        backgroundColor: 'rgba(127,255,0,0.08)',
        fill:            true,
        borderWidth:     1.5,
        pointRadius:     0,
        tension:         0.3,
      },
      {
        label: 'Detection threshold (0.40)',
        data: [],
        borderColor:     '#ff4444',
        backgroundColor: 'transparent',
        borderWidth:     1,
        borderDash:      [5, 4],
        pointRadius:     0,
      },
    ],
  },
  options: {
    ...chartDefaults,
    scales: {
      ...chartDefaults.scales,
      y: {
        ...chartDefaults.scales.y,
        min: 0,
        max: 1.1,
        title: { display: true, text: 'Activation (0–1)', color: '#6b7a9d', font: { size: 11 } },
      },
    },
  },
});

// ─────────────────────────────────────────
//  CALIBRATION — draw threshold lines
// ─────────────────────────────────────────
function applyCalibration(cal) {
  console.log('Calibration received:', cal);
  // Threshold lines will be drawn dynamically per sample window
}

// ─────────────────────────────────────────
//  SAMPLE HANDLER
// ─────────────────────────────────────────
const rmsData      = [];
const smoothedData = [];
const normData     = [];

function pushPoint(arr, t, y) {
  arr.push({ x: t, y });
  if (arr.length > MAX_POINTS) arr.shift();
}

function trimToWindow(arr, tNow) {
  const cutoff = tNow - CHART_WINDOW - 1;
  while (arr.length > 0 && arr[0].x < cutoff) arr.shift();
}

let lastChartUpdate = 0;

function handleSample(msg) {
  const { t, rms, smoothed, norm, in_speech, speech_count, event } = msg;

  // Store data points
  pushPoint(rmsData,      t, rms);
  pushPoint(smoothedData, t, smoothed);
  pushPoint(normData,     t, norm);

  // Trim old points
  trimToWindow(rmsData,      t);
  trimToWindow(smoothedData, t);
  trimToWindow(normData,     t);

  // Update stats bar
  document.getElementById('statBursts').textContent = speech_count;
  document.getElementById('statRms').textContent    = rms.toFixed(2);
  document.getElementById('statNorm').textContent   = (norm * 100).toFixed(1) + '%';

  const speechEl = document.getElementById('statSpeech');
  if (in_speech) {
    speechEl.textContent  = 'Speaking';
    speechEl.style.color  = '#f04c4c';
  } else {
    speechEl.textContent  = 'Silence';
    speechEl.style.color  = '#2ec87d';
  }

  const strainEl = document.getElementById('statStrain');
  if (norm > 0.85) {
    strainEl.textContent = 'High';
    strainEl.style.color = '#f04c4c';
  } else if (norm > 0.6) {
    strainEl.textContent = 'Moderate';
    strainEl.style.color = '#f59e0b';
  } else {
    strainEl.textContent = 'Normal';
    strainEl.style.color = '#2ec87d';
  }

  // Speech events → log
  if (event === 'SPEECH_START') addEventRow(t, 'start', `Burst #${speech_count} started`);
  if (event === 'SPEECH_END')   addEventRow(t, 'end',   `Burst #${speech_count} ended`);

  // Throttle chart redraws to ~30fps (every ~33ms)
  const now = performance.now();
  if (now - lastChartUpdate < 33) return;
  lastChartUpdate = now;

  // Build threshold lines for the current window
  const xMin = t - CHART_WINDOW;
  const xMax = t + 0.2;
  const onset  = calibration.onset  ?? 0;
  const offset = calibration.offset ?? 0;

  const onsetLine  = [{ x: xMin, y: onset  }, { x: xMax, y: onset  }];
  const offsetLine = [{ x: xMin, y: offset }, { x: xMax, y: offset }];
  const threshLine = [{ x: xMin, y: 0.40   }, { x: xMax, y: 0.40   }];

  // Update RMS chart
  rmsChart.data.datasets[0].data = [...rmsData];
  rmsChart.data.datasets[1].data = [...smoothedData];
  rmsChart.data.datasets[2].data = onsetLine;
  rmsChart.data.datasets[3].data = offsetLine;
  rmsChart.options.scales.x.min  = xMin;
  rmsChart.options.scales.x.max  = xMax;
  rmsChart.update('none');

  // Update norm chart
  normChart.data.datasets[0].data = [...normData];
  normChart.data.datasets[1].data = threshLine;
  normChart.options.scales.x.min  = xMin;
  normChart.options.scales.x.max  = xMax;
  normChart.update('none');
}

// ─────────────────────────────────────────
//  EVENT LOG
// ─────────────────────────────────────────
let firstEvent = true;

function addEventRow(t, type, detail) {
  const log = document.getElementById('eventLog');

  if (firstEvent) {
    log.innerHTML = '';
    firstEvent    = false;
  }

  const mins    = Math.floor(t / 60);
  const secs    = (t % 60).toFixed(1).padStart(4, '0');
  const timeStr = `${mins}:${secs}`;

  const row = document.createElement('div');
  row.className = 'event-row';
  row.innerHTML = `
    <span class="event-time">${timeStr}</span>
    <span class="event-badge ${type === 'start' ? 'badge-start' : 'badge-end'}">
      ${type === 'start' ? 'START' : 'END'}
    </span>
    <span class="event-detail">${detail}</span>
  `;

  log.prepend(row);   // newest at top

  // Keep log from growing forever
  while (log.children.length > 50) log.removeChild(log.lastChild);
}