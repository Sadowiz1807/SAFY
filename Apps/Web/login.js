const SAFY_API_BASE = window.SAFY_API_BASE || '';
const SAFY_AUTH_STORAGE_KEY = 'safy_runtime_user';
const SAFY_UI_SETTINGS_KEY = 'safy_ui_settings_v1';
const SAFY_PASSWORD_MASK = '********';
let safyUserProfile = null;

function applyStoredTheme() {
  try {
    const settings = JSON.parse(localStorage.getItem(SAFY_UI_SETTINGS_KEY) || '{}');
    const theme = settings?.theme === 'light' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', theme);
  } catch {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
}

applyStoredTheme();

async function apiRequest(path, options = {}) {
  const response = await fetch(`${SAFY_API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => null);
  if (!response.ok || body?.success !== true) {
    const error = new Error(body?.error?.message || `HTTP_${response.status}`);
    error.code = body?.error?.code || `HTTP_${response.status}`;
    throw error;
  }
  return body.data;
}

function setError(message = '') {
  const error = document.getElementById('login-error');
  if (!error) return;
  error.textContent = message;
  error.classList.toggle('hidden', !message);
}

function storeSignedInUser(username) {
  localStorage.setItem(SAFY_AUTH_STORAGE_KEY, JSON.stringify({
    username,
    signed_in_at: new Date().toISOString(),
  }));
}

function storedUser() {
  try {
    const value = JSON.parse(localStorage.getItem(SAFY_AUTH_STORAGE_KEY) || 'null');
    return value?.username ? value : null;
  } catch {
    return null;
  }
}

async function loadProfile() {
  try {
    safyUserProfile = await apiRequest('/auth/profile');
  } catch {
    safyUserProfile = null;
  }

  const username = safyUserProfile?.username || storedUser()?.username || '';
  const usernameField = document.getElementById('login-username');
  const passwordField = document.getElementById('login-password');
  if (usernameField && username) usernameField.value = username;
  if (passwordField && safyUserProfile?.password_configured) {
    passwordField.value = safyUserProfile.password_mask || SAFY_PASSWORD_MASK;
    passwordField.dataset.savedPasswordMask = 'true';
  }
}

async function submitLogin(event) {
  event.preventDefault();
  setError('');

  const username = (document.getElementById('login-username')?.value || '').trim();
  const passwordField = document.getElementById('login-password');
  const password = passwordField?.value || '';
  const usingSavedMask = password === SAFY_PASSWORD_MASK && Boolean(safyUserProfile?.password_configured);

  if (!username) {
    setError('Username is required.');
    return;
  }
  if (!password && !usingSavedMask) {
    setError('Password is required.');
    return;
  }

  const button = document.getElementById('login-submit-btn');
  if (button) button.disabled = true;
  try {
    const profile = await apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        username,
        password: usingSavedMask ? '' : password,
        use_saved_password: usingSavedMask,
      }),
    });
    storeSignedInUser(profile?.username || username);
    window.location.replace('/dashboard');
  } catch (error) {
    setError(error?.code === 'AUTH_INVALID_PASSWORD' ? 'Invalid password.' : (error?.message || 'Login failed.'));
  } finally {
    if (button) button.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  document.getElementById('safy-login-form')?.addEventListener('submit', submitLogin);
  document.getElementById('login-password')?.addEventListener('input', (event) => {
    if (event.target.value !== SAFY_PASSWORD_MASK) event.target.dataset.savedPasswordMask = 'false';
  });
  await loadProfile();
  document.getElementById('login-username')?.focus();
});
