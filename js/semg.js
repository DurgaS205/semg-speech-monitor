// ═══════════════════════════════════════════════════════════
//  VAAKYA — LIVE sEMG  (Real Hardware Mode)
//  Data comes from semg_server.py via WebSocket.
//  Start semg_server.py first, then open this page.
// ═══════════════════════════════════════════════════════════

// ─────────────────────────────────────────
//  CONFIG
// ─────────────────────────────────────────
const WS_URL       = 'ws://localhost:8765';
const API_URL      = 'http://localhost:5000';
const MAX_POINTS   = 1000;
const CHART_WINDOW = 5;

// ─────────────────────────────────────────
//  STATE
// ─────────────────────────────────────────
let ws             = null;
let reconnectTimer = null;
let calibration    = {};

let sessionActive   = false;
let sampleCount     = 0;   // counts every sample for history decimation
let sessionData     = null;
let sessionSeconds  = 0;
let sessionInterval = null;

// ─────────────────────────────────────────
//  DOM REFS
// ─────────────────────────────────────────
const wsDot          = document.getElementById('wsDot');
const wsLabel        = document.getElementById('wsLabel');
const sessionBtn     = document.getElementById('sessionBtn');
const sessionBtn2    = document.getElementById('sessionBtn2');
const sessionInfo    = document.getElementById('sessionInfo');
const sessionHint    = document.getElementById('sessionHint');
const sessionHint2   = document.getElementById('sessionHint2');
const sessionTimerEl = document.getElementById('sessionTimer');

// ─────────────────────────────────────────
//  WEBSOCKET STATUS
// ─────────────────────────────────────────
function setWsStatus(state) {
  wsDot.className = 'ws-dot ' + state;
  wsLabel.textContent = {
    connected:    'Live',
    disconnected: 'Disconnected',
    connecting:   'Connecting…',
  }[state] || 'Connecting…';
}

// ─────────────────────────────────────────
//  WEBSOCKET CONNECTION
// ─────────────────────────────────────────
function connect() {
  setWsStatus('connecting');
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setWsStatus('connected');
    clearTimeout(reconnectTimer);
    sessionHint.textContent  = 'Connected — press Start Session to begin';
    sessionHint2.textContent = 'Connected — press Start Session to begin';
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'calibration') {
        calibration = msg;
        console.log('Calibration received:', calibration);
      } else if (msg.type === 'sample') {
        handleSample(msg);
      }
    } catch (err) {
      console.warn('Bad WS message:', e.data);
    }
  };

  ws.onclose = () => {
    setWsStatus('disconnected');
    sessionHint.textContent  = 'Server disconnected — run semg_server.py';
    sessionHint2.textContent = 'Server disconnected — run semg_server.py';
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = () => ws.close();
}

connect();

// ─────────────────────────────────────────
//  SESSION PERSISTENCE
// ─────────────────────────────────────────
function saveSession(data) {
  const existing = JSON.parse(localStorage.getItem('semgSessions') || '[]');
  existing.unshift(data);
  if (existing.length > 50) existing.pop();
  localStorage.setItem('semgSessions', JSON.stringify(existing));
}

// ─────────────────────────────────────────
//  SESSION BUTTON SYNC HELPERS
// ─────────────────────────────────────────
function setBothBtns(html, isStop) {
  [sessionBtn, sessionBtn2].forEach(btn => {
    btn.innerHTML = html;
    if (isStop) btn.classList.add('stopping');
    else btn.classList.remove('stopping');
  });
}

function setBothHints(text) {
  sessionHint.textContent  = text;
  sessionHint2.textContent = text;
}

// ─────────────────────────────────────────
//  START SESSION
// ─────────────────────────────────────────
function startSession() {
  // Tell Python server to start
  fetch(`${API_URL}/start`, { method: 'POST' })
    .then(r => r.json())
    .then(() => {
      sessionActive  = true;
      sessionSeconds = 0;
      sessionData = {
        id:          Date.now(),
        startTime:   new Date().toISOString(),
        endTime:     null,
        duration:    0,
        bursts:      0,
        peakNorm:    0,
        events:      [],
        rmsHistory:  [],
        normHistory: [],
      };

      setBothBtns(`
        <svg viewBox="0 0 24 24" fill="currentColor" style="width:16px;height:16px">
          <rect x="6" y="5" width="4" height="14" rx="1" stroke="none"/>
          <rect x="14" y="5" width="4" height="14" rx="1" stroke="none"/>
        </svg>
        Stop Session`, true);

      sessionInfo.style.display = 'flex';
      setBothHints('Recording in progress — speak naturally');

      sessionInterval = setInterval(() => {
        sessionSeconds++;
        const m = String(Math.floor(sessionSeconds / 60)).padStart(2, '0');
        const s = String(sessionSeconds % 60).padStart(2, '0');
        sessionTimerEl.textContent = `${m}:${s}`;
      }, 1000);
    })
    .catch(() => {
      alert('Cannot reach semg_server.py.\nMake sure it is running in your terminal.');
    });
}

// ─────────────────────────────────────────
//  STOP SESSION
// ─────────────────────────────────────────
function stopSession() {
  if (!sessionActive) return;

  const finish = () => {
    sessionActive = false;
    clearInterval(sessionInterval);

    sessionData.endTime  = new Date().toISOString();
    sessionData.duration = sessionSeconds;
    saveSession(sessionData);

    setBothBtns(`
      <svg viewBox="0 0 24 24" fill="currentColor" style="width:16px;height:16px">
        <polygon points="5 3 19 12 5 21 5 3" stroke="none"/>
      </svg>
      Start Session`, false);

    sessionInfo.style.display  = 'none';
    sessionTimerEl.textContent = '00:00';
    setBothHints('Session saved — press Start Session to record again');
    sessionData = null;
  };

  fetch(`${API_URL}/stop`, { method: 'POST' })
    .then(r => r.json())
    .then(finish)
    .catch(finish);   // always save locally even if server unreachable
}

// ─────────────────────────────────────────
//  BUTTON LISTENERS
// ─────────────────────────────────────────
sessionBtn.addEventListener('click',  () => { if (!sessionActive) startSession(); else stopSession(); });
sessionBtn2.addEventListener('click', () => { if (!sessionActive) startSession(); else stopSession(); });

// ─────────────────────────────────────────
//  CHART.JS SETUP
// ─────────────────────────────────────────
const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: { display: false },
    tooltip: { backgroundColor: '#1a2c5b', titleColor: '#fff', bodyColor: '#c8d4f0', padding: 10, cornerRadius: 8 },
  },
  scales: {
    x: {
      type:   'linear',
      grid:   { color: 'rgba(220,228,245,0.5)' },
      ticks:  { color: '#6b7a9d', font: { size: 11 }, maxTicksLimit: 6, callback: v => v.toFixed(1) + 's' },
      border: { color: '#dce4f5' },
    },
    y: {
      grid:   { color: 'rgba(220,228,245,0.5)' },
      ticks:  { color: '#6b7a9d', font: { size: 11 } },
      border: { color: '#dce4f5' },
    },
  },
};

const rmsChart = new Chart(
  document.getElementById('rmsChart').getContext('2d'), {
    type: 'line',
    data: {
      datasets: [
        { label: 'Raw RMS',  data: [], borderColor: '#00cfff', backgroundColor: 'transparent', borderWidth: 1.2, pointRadius: 0, tension: 0.2 },
        { label: 'Smoothed', data: [], borderColor: '#ff9f40', backgroundColor: 'transparent', borderWidth: 1.8, pointRadius: 0, tension: 0.3 },
        { label: 'Onset',    data: [], borderColor: '#ff4444', backgroundColor: 'transparent', borderWidth: 1,   pointRadius: 0, borderDash: [5,4] },
        { label: 'Offset',   data: [], borderColor: '#ffaa00', backgroundColor: 'transparent', borderWidth: 1,   pointRadius: 0, borderDash: [5,4] },
      ],
    },
    options: {
      ...chartDefaults,
      scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, title: { display: true, text: 'RMS Value', color: '#6b7a9d', font: { size: 11 } } } },
    },
  }
);

const normChart = new Chart(
  document.getElementById('normChart').getContext('2d'), {
    type: 'line',
    data: {
      datasets: [
        { label: 'Activation', data: [], borderColor: '#7fff00', backgroundColor: 'rgba(127,255,0,0.08)', fill: true, borderWidth: 1.5, pointRadius: 0, tension: 0.3 },
        { label: 'Threshold',  data: [], borderColor: '#ff4444', backgroundColor: 'transparent', borderWidth: 1, pointRadius: 0, borderDash: [5,4] },
      ],
    },
    options: {
      ...chartDefaults,
      scales: { ...chartDefaults.scales, y: { ...chartDefaults.scales.y, min: 0, max: 1.1, title: { display: true, text: 'Activation (0–1)', color: '#6b7a9d', font: { size: 11 } } } },
    },
  }
);

// ─────────────────────────────────────────
//  DATA BUFFERS
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

// ─────────────────────────────────────────
//  SAMPLE HANDLER  (called on every WS message)
// ─────────────────────────────────────────
let lastChartUpdate = 0;
let firstEvent      = true;

function handleSample(msg) {
  const { t, rms, smoothed, norm, in_speech, speech_count, event } = msg;

  pushPoint(rmsData,      t, rms);
  pushPoint(smoothedData, t, smoothed);
  pushPoint(normData,     t, norm);
  trimToWindow(rmsData,      t);
  trimToWindow(smoothedData, t);
  trimToWindow(normData,     t);

  // Stats bar
  document.getElementById('statBursts').textContent = speech_count;
  document.getElementById('statRms').textContent    = rms.toFixed(2);
  document.getElementById('statNorm').textContent   = (norm * 100).toFixed(1) + '%';

  const speechEl = document.getElementById('statSpeech');
  speechEl.textContent = in_speech ? 'Speaking' : 'Silence';
  speechEl.style.color = in_speech ? '#f04c4c' : '#2ec87d';

  const strainEl = document.getElementById('statStrain');
  if      (norm > 0.85) { strainEl.textContent = 'High';     strainEl.style.color = '#f04c4c'; }
  else if (norm > 0.6)  { strainEl.textContent = 'Moderate'; strainEl.style.color = '#f59e0b'; }
  else                  { strainEl.textContent = 'Normal';   strainEl.style.color = '#2ec87d'; }

  // Record into active session
  if (sessionActive && sessionData) {
    sessionData.bursts   = speech_count;
    sessionData.peakNorm = Math.max(sessionData.peakNorm, norm);
    sampleCount++;
    if (sampleCount % 5 === 0) {
      sessionData.rmsHistory.push({ t, v: rms });
      sessionData.normHistory.push({ t, v: norm });
    }
    if (event === 'SPEECH_START') {
      sessionData.events.push({ t, type: 'start', burst: speech_count });
      addEventRow(t, 'start', `Burst #${speech_count} started`);
    }
    if (event === 'SPEECH_END') {
      sessionData.events.push({ t, type: 'end', burst: speech_count });
      addEventRow(t, 'end',   `Burst #${speech_count} ended`);
    }
  }

  // Throttle chart redraws to ~30 fps
  const now = performance.now();
  if (now - lastChartUpdate < 33) return;
  lastChartUpdate = now;

  const xMin   = t - CHART_WINDOW;
  const xMax   = t + 0.2;
  const onset  = calibration.onset  ?? 0;
  const offset = calibration.offset ?? 0;

  rmsChart.data.datasets[0].data = [...rmsData];
  rmsChart.data.datasets[1].data = [...smoothedData];
  rmsChart.data.datasets[2].data = [{ x: xMin, y: onset  }, { x: xMax, y: onset  }];
  rmsChart.data.datasets[3].data = [{ x: xMin, y: offset }, { x: xMax, y: offset }];
  rmsChart.options.scales.x.min  = xMin;
  rmsChart.options.scales.x.max  = xMax;
  rmsChart.update('none');

  normChart.data.datasets[0].data = [...normData];
  normChart.data.datasets[1].data = [{ x: xMin, y: 0.40 }, { x: xMax, y: 0.40 }];
  normChart.options.scales.x.min  = xMin;
  normChart.options.scales.x.max  = xMax;
  normChart.update('none');
}

// ─────────────────────────────────────────
//  EVENT LOG
// ─────────────────────────────────────────
function addEventRow(t, type, detail) {
  const log = document.getElementById('eventLog');
  if (firstEvent) { log.innerHTML = ''; firstEvent = false; }

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
  log.prepend(row);
  while (log.children.length > 50) log.removeChild(log.lastChild);
}
