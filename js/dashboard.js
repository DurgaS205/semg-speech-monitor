document.addEventListener('DOMContentLoaded', function () {

  // ── Redirect to login if not authenticated ──
  const userEmail = sessionStorage.getItem('userEmail');
  if (!userEmail) {
    window.location.href = 'login.html';
  }

  // ── Grab all DOM elements ──
  const sessionToggle = document.getElementById('sessionToggle');
  const statusDot     = document.getElementById('statusDot');
  const statusText    = document.getElementById('statusText');
  const electrodeText = document.getElementById('electrodeText');
  const lastUpdated   = document.getElementById('lastUpdated');

  // ── Timer logic ──
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

  // ── Toggle: controls status + timer together ──
  sessionToggle.addEventListener('change', function () {
    if (this.checked) {
      statusDot.style.background  = '#2ec87d';
      statusDot.style.boxShadow   = '0 0 0 3px rgba(46,200,125,0.2)';
      statusDot.style.animation   = 'pulse 2s infinite';
      statusText.style.color      = '#2ec87d';
      statusText.textContent      = 'Connected';
      electrodeText.textContent   = 'Active';
      electrodeText.style.color   = '#3ecfb2';
      startTimer();
    } else {
      statusDot.style.background  = '#cbd5e0';
      statusDot.style.boxShadow   = 'none';
      statusDot.style.animation   = 'none';
      statusText.style.color      = '#6b7a9d';
      statusText.textContent      = 'Disconnected';
      electrodeText.textContent   = 'Inactive';
      electrodeText.style.color   = '#6b7a9d';
      stopTimer();
    }
  });

  // ── Start timer on page load if toggle is already ON ──
  if (sessionToggle.checked) {
    startTimer();
  }

  // ── Live sEMG Signal button ──
  document.getElementById('liveSignalBtn').addEventListener('click', function () {
    window.location.href = 'semg.html';
  });

});