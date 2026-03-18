document.addEventListener('DOMContentLoaded', function () {

  const sessionsWrap  = document.getElementById('sessionsWrap');
  const emptyState    = document.getElementById('emptyState');
  const totalSessions = document.getElementById('totalSessions');
  const totalBursts   = document.getElementById('totalBursts');
  const avgPeak       = document.getElementById('avgPeak');
  const clearAllBtn   = document.getElementById('clearAllBtn');

  // ── Load sessions from localStorage ──
  function getSessions() {
    return JSON.parse(localStorage.getItem('semgSessions') || '[]');
  }

  function saveSessions(sessions) {
    localStorage.setItem('semgSessions', JSON.stringify(sessions));
  }

  // ── Format helpers ──
  function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  }

  function formatDuration(secs) {
    if (!secs) return '—';
    if (secs < 60) return secs + 's';
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return m + 'm ' + s + 's';
  }

  function strainClass(peak) {
    if (peak > 0.85) return 'strain-high';
    if (peak > 0.6)  return 'strain-moderate';
    return 'strain-normal';
  }

  function strainText(peak) {
    if (peak > 0.85) return 'High Strain';
    if (peak > 0.6)  return 'Moderate';
    return 'Normal';
  }

  // ── Update summary pills ──
  function updateSummary(sessions) {
    totalSessions.textContent = sessions.length;
    const bursts = sessions.reduce((sum, s) => sum + (s.bursts || 0), 0);
    totalBursts.textContent   = bursts;
    const peaks = sessions.filter(s => s.peakNorm > 0).map(s => s.peakNorm);
    avgPeak.textContent = peaks.length
      ? (peaks.reduce((a, b) => a + b, 0) / peaks.length * 100).toFixed(1) + '%'
      : '—';
  }

  // ── Draw mini chart ──
  function drawMiniChart(canvasId, data, color, label) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    if (!data || data.length === 0) {
      // No history data recorded — show a subtle message
      const parent = ctx.parentElement;
      ctx.style.display = 'none';
      if (!parent.querySelector('.no-chart-msg')) {
        const msg = document.createElement('div');
        msg.className = 'no-chart-msg';
        msg.style.cssText = 'font-size:12px;color:#6b7a9d;text-align:center;padding:40px 0;';
        msg.textContent = 'No signal data recorded';
        parent.appendChild(msg);
      }
      return;
    }

    const step    = Math.max(1, Math.floor(data.length / 200));
    const sampled = data.filter((_, i) => i % step === 0);

    new Chart(ctx, {
      type: 'line',
      data: {
        datasets: [{
          data:            sampled.map(p => ({ x: p.t, y: p.v })),
          borderColor:     color,
          backgroundColor: color + '18',
          fill:            true,
          borderWidth:     1.5,
          pointRadius:     0,
          tension:         0.3,
        }],
      },
      options: {
        responsive:          true,
        maintainAspectRatio: false,
        animation:           false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          x: {
            type:  'linear',
            grid:  { color: 'rgba(220,228,245,0.4)' },
            ticks: { color: '#6b7a9d', font: { size: 10 }, maxTicksLimit: 5,
                     callback: v => v.toFixed(0) + 's' },
            border:{ color: '#dce4f5' },
          },
          y: {
            grid:  { color: 'rgba(220,228,245,0.4)' },
            ticks: { color: '#6b7a9d', font: { size: 10 }, maxTicksLimit: 4 },
            border:{ color: '#dce4f5' },
          },
        },
      },
    });
  }

  // ── Build one session card ──
  function buildSessionCard(session, index, total) {
    const sessionNum = total - index;
    const card       = document.createElement('div');
    card.className   = 'session-card';
    card.dataset.id  = session.id;

    const peak  = session.peakNorm || 0;
    const rmsId  = 'rms-chart-' + session.id;
    const normId = 'norm-chart-' + session.id;

    card.innerHTML = `
      <div class="session-card-header" data-id="${session.id}">
        <div class="session-header-left">
          <div class="session-number">#${sessionNum}</div>
          <div>
            <div class="session-title">Session ${sessionNum}</div>
            <div class="session-date">${formatDate(session.startTime)}</div>
          </div>
        </div>
        <div class="session-header-right">
          <div class="session-stat">
            <span class="stat-val">${session.bursts || 0}</span>
            <span class="stat-lbl">Bursts</span>
          </div>
          <div class="session-stat">
            <span class="stat-val">${formatDuration(session.duration)}</span>
            <span class="stat-lbl">Duration</span>
          </div>
          <div class="session-stat">
            <span class="stat-val">${(peak * 100).toFixed(1)}%</span>
            <span class="stat-lbl">Peak</span>
          </div>
          <span class="strain-badge ${strainClass(peak)}">${strainText(peak)}</span>
          <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </div>
      </div>

      <div class="session-body" id="body-${session.id}">
        <div class="session-charts">
          <div class="mini-chart-wrap">
            <div class="mini-chart-label">RMS Signal</div>
            <canvas id="${rmsId}"></canvas>
          </div>
          <div class="mini-chart-wrap">
            <div class="mini-chart-label">Muscle Activation</div>
            <canvas id="${normId}"></canvas>
          </div>
        </div>

        <div class="session-events-title">Speech Events</div>
        <div class="events-list">
          ${buildEventsList(session.events)}
        </div>

        <button class="btn-delete" data-id="${session.id}">Delete Session</button>
      </div>
    `;

    // ── Toggle expand/collapse ──
    card.querySelector('.session-card-header').addEventListener('click', function () {
      const body    = document.getElementById('body-' + session.id);
      const chevron = card.querySelector('.chevron');
      const isOpen  = body.classList.contains('open');

      body.classList.toggle('open');
      chevron.classList.toggle('open');

      if (!isOpen && !card.dataset.chartsDrawn) {
        card.dataset.chartsDrawn = 'true';
        // Wait for CSS transition + layout to complete before drawing
        setTimeout(() => {
          // Force explicit pixel dimensions so Chart.js can measure correctly
          const rmsCanvas  = document.getElementById(rmsId);
          const normCanvas = document.getElementById(normId);
          if (rmsCanvas)  { rmsCanvas.style.width  = '100%'; rmsCanvas.style.height = '120px'; }
          if (normCanvas) { normCanvas.style.width = '100%'; normCanvas.style.height = '120px'; }
          drawMiniChart(rmsId,  session.rmsHistory,  '#00cfff', 'RMS');
          drawMiniChart(normId, session.normHistory, '#7fff00', 'Activation');
        }, 150);
      }
    });

    // ── Delete button ──
    card.querySelector('.btn-delete').addEventListener('click', function (e) {
      e.stopPropagation();
      if (!confirm('Delete this session?')) return;
      const sessions = getSessions().filter(s => s.id !== session.id);
      saveSessions(sessions);
      renderAll();
    });

    return card;
  }

  function buildEventsList(events) {
    if (!events || events.length === 0) {
      return '<div class="no-events">No speech events recorded in this session.</div>';
    }
    return events.map(ev => `
      <div class="event-item">
        <span class="ev-time">${ev.t.toFixed(1)}s</span>
        <span class="ev-badge ${ev.type === 'start' ? 'ev-start' : 'ev-end'}">
          ${ev.type === 'start' ? 'START' : 'END'}
        </span>
        <span>Burst #${ev.burst}</span>
      </div>
    `).join('');
  }

  // ── Render everything ──
  function renderAll() {
    const sessions = getSessions();

    updateSummary(sessions);

    const oldCards = sessionsWrap.querySelectorAll('.session-card');
    oldCards.forEach(c => c.remove());

    if (sessions.length === 0) {
      emptyState.style.display = 'block';
      return;
    }

    emptyState.style.display = 'none';

    sessions.forEach((session, index) => {
      const card = buildSessionCard(session, index, sessions.length);
      sessionsWrap.appendChild(card);
    });
  }

  // ── Clear all ──
  clearAllBtn.addEventListener('click', function () {
    if (!confirm('Delete ALL session history? This cannot be undone.')) return;
    localStorage.removeItem('semgSessions');
    renderAll();
  });

  // ── Initial render ──
  renderAll();

});
