const loginBtn = document.getElementById('loginBtn');
const errorMsg = document.getElementById('errorMsg');

loginBtn.addEventListener('click', function () {
  const email    = document.getElementById('email').value.trim();
  const password = document.getElementById('password').value.trim();

  errorMsg.textContent = '';

  if (!email || !password) {
    errorMsg.textContent = 'Please enter your email and password.';
    return;
  }

  if (!email.includes('@')) {
    errorMsg.textContent = 'Please enter a valid email address.';
    return;
  }

  if (password.length < 4) {
    errorMsg.textContent = 'Password must be at least 4 characters.';
    return;
  }

  // Use localStorage — persists across pages and direct URL access
  localStorage.setItem('vaakya_userEmail', email);
  localStorage.setItem('vaakya_loggedIn', 'true');

  window.location.href = 'dashboard.html';
});

// Allow pressing Enter to submit
document.addEventListener('keydown', function (e) {
  if (e.key === 'Enter') loginBtn.click();
});