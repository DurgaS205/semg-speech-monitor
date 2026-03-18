document.addEventListener('DOMContentLoaded', function () {

  // Auth check using localStorage (works across tabs and direct URL access)
  const loggedIn = localStorage.getItem('vaakya_loggedIn');
  if (!loggedIn) {
    window.location.href = 'login.html';
    return;
  }

  const sessionToggle = document.getElementById('sessionToggle');
  const statusDot     = document.getElementById('statusDot');
  const statusText    = document.getElementById('statusText');
  const electrodeText = document.getElementById('electrodeText');
  const lastUpdated   = document.getElementById('lastUpdated');

  let timerInterval = null;
  let seconds = 0;

  function startTimer() {
    seconds = 0;
    lastUpdated.textContent = 'Just now';
    clearInterval(timerInterval);
    timerInterval = setInterval(function () {
      seconds++;
      if (seconds < 60) {
        lastUpdated.textContent = seconds + ' second' + (seconds === 1 ? '' : 's') + ' ago';
      } else {
        const mins = Math.floor(seconds / 60);
        lastUpdated.textContent = mins + ' minute' + (mins === 1 ? '' : 's') + ' ago';
      }
    }, 1000);
  }

  function stopTimer() {
    clearInterval(timerInterval);
    timerInterval = null;
    seconds = 0;
    lastUpdated.textContent = 'Just now';
  }

  sessionToggle.addEventListener('change', function () {
    if (this.checked) {
      statusDot.style.background = '#2ec87d';
      statusDot.style.boxShadow  = '0 0 0 3px rgba(46,200,125,0.2)';
      statusDot.style.animation  = 'pulse 2s infinite';
      statusText.style.color     = '#2ec87d';
      statusText.textContent     = 'Connected';
      electrodeText.textContent  = 'Active';
      electrodeText.style.color  = '#3ecfb2';
      startTimer();
    } else {
      statusDot.style.background = '#cbd5e0';
      statusDot.style.boxShadow  = 'none';
      statusDot.style.animation  = 'none';
      statusText.style.color     = '#6b7a9d';
      statusText.textContent     = 'Disconnected';
      electrodeText.textContent  = 'Inactive';
      electrodeText.style.color  = '#6b7a9d';
      stopTimer();
    }
  });

  if (sessionToggle.checked) startTimer();

  // FIX: navigate to sibling semg.html
  document.getElementById('liveSignalBtn').addEventListener('click', function () {
    window.location.href = 'semg.html';
  });

  // ── Update episode count from localStorage ──
  function updateEpisodeCount() {
    const sessions     = JSON.parse(localStorage.getItem('semgSessions') || '[]');
    const totalBursts  = sessions.reduce((sum, s) => sum + (s.bursts || 0), 0);
    const countEl      = document.getElementById('episodeCount');
    const labelEl      = document.getElementById('episodeLabel');
    if (!countEl || !labelEl) return;
    countEl.textContent = totalBursts;
    labelEl.textContent = totalBursts === 1
      ? 'Irregular speech event recorded.'
      : totalBursts === 0
        ? 'No episodes recorded yet.'
        : 'Irregular speech events recorded.';
  }

  updateEpisodeCount();

  // Re-check every time user returns to this tab (e.g. from semg page)
  window.addEventListener('focus', updateEpisodeCount);
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible') updateEpisodeCount();
  });

});
