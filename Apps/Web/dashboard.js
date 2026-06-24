const SAFY_API_BASE = window.SAFY_API_BASE || '';
let safyCurrentCheck = null;
let safyChatId = null;
let safyModelProfile = null;
let safyDatabaseProfile = null;
let safyDatabaseProfiles = [];
let safySandboxId = null;
let safyRuntimeUsername = '';
let safyUserProfile = null;
const SAFY_AUTH_STORAGE_KEY = 'safy_runtime_user';
const SAFY_UI_SETTINGS_KEY = 'safy_ui_settings_v1';
const SAFY_DEFAULT_UI_SETTINGS = Object.freeze({
  theme: 'dark',
  streaming: true,
  autoReadOnly: true,
});
let safyUiSettings = { ...SAFY_DEFAULT_UI_SETTINGS };

let safySlashCommandIndex = 0;
let safyContextSources = [];
let safyChatRequestPending = false;
const SAFY_CONTEXT_MAX_SOURCES = 5;
const SAFY_CONTEXT_MAX_FILE_BYTES = 1024 * 1024;
const SAFY_SIDEBAR_STATE_KEY = 'safy_sidebar_state_v1';

const SAFY_CHAT_COMMANDS = [
  { command: '/Execute', insert: '/Execute ', title: 'Execute database task', description: 'Run a database task through SAFY guard and runtime.' },
  { command: '/Inspect', insert: '/Inspect ', title: 'Inspect database', description: 'Inspect schema or metadata without executing writes.' },
  { command: '/Help', insert: '/Help', title: 'Show command help', description: 'Show available SAFY chat commands.' },
  { command: '/Cancel', insert: '/Cancel', title: 'Cancel current task', description: 'Cancel or dismiss the current pending workflow.' },
  { command: '/Reset', insert: '/Reset', title: 'Reset chat draft', description: 'Clear the current chat view draft state.' },
  { command: '/Reset_schema', insert: '/Reset_schema', title: 'Reset schema graphs', description: 'Delete all stored backend schema graphs.' },
  { command: '/Delete_schema', insert: '/Delete_schema', title: 'Delete active schema', description: 'Delete the schema graph for the active database.' }
];

function normalizedError(error, fallbackMessage) {
  const rawCode = error?.code || 'SAFY_API_ERROR';
  const rawMessage = error?.message || fallbackMessage || String(error);
  return { code: rawCode, message: friendlyErrorMessage(rawCode, rawMessage), details: {}, next_action: suggestedNextAction(rawCode, rawMessage) };
}

function friendlyErrorMessage(code, message) {
  const text = redactForDisplay(message);
  const codeText = String(code || '');

  if (codeText === 'MODEL_PROFILE_NOT_ACTIVATED') return 'Please save and activate the LM Studio profile first.';
  if (/^AUTH_|login|SAFY_LOGIN_PASSWORD/i.test(codeText + ' ' + text)) {
    if (/invalid password/i.test(text) || codeText === 'AUTH_INVALID_PASSWORD') return 'Invalid password.';
    if (/username/i.test(text) || codeText === 'AUTH_USERNAME_REQUIRED') return 'Username is required.';
    return 'Login failed. Check username and password.';
  }
  if (/SECRET_VALUE_REJECTED/i.test(codeText + ' ' + text)) {
    return 'Database/API secret was rejected before it could be moved to .env. Re-enter the key and save again.';
  }
  if (/PROFILE_NOT_FOUND/i.test(codeText + ' ' + text)) {
    return 'Profile was not saved or activated. Save the connection first, then test it again.';
  }
  if (codeText === 'SQL_POLICY_BLOCKED') {
    return text || 'SAFY blocked an administrative, unknown, or unsupported SQL statement before sandbox validation.';
  }
  if (codeText === 'DESTRUCTIVE_SQL_BLOCKED') {
    return 'DROP and TRUNCATE are blocked by SAFY policy. Use a separately reviewed migration or administrative workflow.';
  }
  if (codeText === 'TRANSACTION_CONTROL_BLOCKED') {
    return 'BEGIN, COMMIT, and ROLLBACK are managed by SAFY and cannot be submitted in the Execute Box. Submit the DDL/DML statement itself.';
  }
  if (/SANDBOX_VALIDATION_FAILED/i.test(codeText)) {
    return text || 'The SQL failed inside the isolated sandbox. Fix the SQL or schema reference, then run Check Safety again.';
  }
  if (/SANDBOX_NOT_READY|SANDBOX_MANAGER_UNAVAILABLE|SANDBOX_NOT_FOUND/i.test(codeText)) {
    return 'The isolated sandbox is not ready. Save or reconnect the database so SAFY can prepare it.';
  }
  if (/DATABASE_PROFILE_REQUIRED/i.test(codeText)) {
    return 'Save and select a database connection before running Check Safety.';
  }
  if (codeText === 'DATABASE_ACCESS_DISABLED') {
    return 'Query execution is disabled for this database profile. Change the saved access mode before retrying.';
  }
  if (codeText === 'DATABASE_READ_ONLY') {
    return 'This database profile is read-only. Only SELECT statements can be executed.';
  }
  if (codeText === 'DATABASE_PERMISSION_MODE_INVALID') {
    return 'The saved database access mode is invalid. Re-save the database profile with a supported mode.';
  }
  if (/SUPABASE_REST_SQL_UNSUPPORTED/i.test(codeText)) {
    return 'Supabase REST can only execute simple read-only SELECT drafts. Edit the SQL to SELECT columns FROM table with optional WHERE/ORDER/LIMIT.';
  }
  if (/DB_RESOURCE_NOT_FOUND|DB_TABLE_NOT_FOUND/i.test(codeText)) {
    return 'The generated SQL references a table or endpoint that was not found. Refresh Schema Graph, then regenerate or edit the table name.';
  }
  if (/DB_AUTH_FAILED|DB_SECRET_MISSING|DB_SECRET_ENV_INVALID|DB_BASE_URL_INVALID|DB_BASE_URL_MISSING/i.test(codeText)) {
    return 'Database credentials or Base URL are invalid. Test Connection can pass only when these values are available to execution too.';
  }
  if (/DB_CONNECTION_FAILED|DB_CONNECTION_TIMEOUT|DB_REQUEST_FAILED/i.test(codeText)) {
    return text || 'Database request failed during execution. The saved connection may still be valid; check the generated SQL/table name.';
  }
  if (/database|db|supabase|postgres|mysql|sqlite|host|port|credential/i.test(codeText + ' ' + text)) {
    return text || 'Database runtime request failed. Check the generated SQL and active database.';
  }
  if (/model|lm studio|llm|provider/i.test(codeText + ' ' + text)) {
    return 'Model server is not reachable. Please start LM Studio and click Test Connection again.';
  }
  if (/sandbox/i.test(text)) return 'Sandbox validation did not complete. Review the error code and active database connection.';
  if (/blocked|policy/i.test(text) || codeText === 'SQL_BLOCKED') return text || 'SQL was blocked by SAFY safety policy.';
  return text || 'SAFY could not complete the request.';
}

function suggestedNextAction(code, message) {
  const text = `${code} ${message}`;
  if (/SQL_POLICY_BLOCKED/i.test(text)) return 'Remove explanatory prose and any administrative or unsupported statements, then run Check Safety again.';
  if (/DESTRUCTIVE_SQL_BLOCKED/i.test(text)) return 'Use a separately reviewed migration or administrative workflow; do not retry DROP/TRUNCATE in the Execute Box.';
  if (/TRANSACTION_CONTROL_BLOCKED/i.test(text)) return 'Remove BEGIN/COMMIT/ROLLBACK and submit only the intended SQL statement.';
  if (/SANDBOX_VALIDATION_FAILED/i.test(text)) return 'Fix the SQL or referenced schema object, then run Check Safety again.';
  if (/SANDBOX_NOT_READY|SANDBOX_MANAGER_UNAVAILABLE|SANDBOX_NOT_FOUND/i.test(text)) return 'Save or reconnect the database so SAFY can create or repair the isolated sandbox.';
  if (/DATABASE_PROFILE_REQUIRED|PROFILE_NOT_FOUND/i.test(text)) return 'Save and select the intended database profile, then run Check Safety again.';
  if (/DATABASE_ACCESS_DISABLED/i.test(text)) return 'Edit the saved database profile and enable query execution before retrying.';
  if (/DATABASE_READ_ONLY/i.test(text)) return 'Use a SELECT statement, or explicitly change the saved database profile access mode.';
  if (/DATABASE_PERMISSION_MODE_INVALID/i.test(text)) return 'Re-save the database profile with credential_permissions, read_only, or disabled.';
  if (/SUPABASE_REST_SQL_UNSUPPORTED|DB_RESOURCE_NOT_FOUND|DB_TABLE_NOT_FOUND/i.test(text)) return 'Refresh Schema Graph, regenerate the SQL draft, or edit the table name before running Check Safety again.';
  if (/SECRET_VALUE_REJECTED/i.test(text)) return 'Re-enter the key so SAFY can move it to .env, then save again.';
  if (/DB_AUTH_FAILED|DB_SECRET_MISSING|DB_SECRET_ENV_INVALID|credential|password|secret/i.test(text)) return 'Verify Base URL/API Key and make sure backend accepts the selected secret mode.';
  if (/model|lm studio|llm/i.test(text)) return 'Start or restart the model server, then test the model connection.';
  if (/sandbox/i.test(text)) return 'Review the sandbox error details and retry Check Safety after the sandbox is ready.';
  if (/blocked|policy/i.test(text)) return 'Review the policy reason and revise the SQL before running Check Safety again.';
  return 'Review the visible settings and try again.';
}

function redactForDisplay(value) {
  return String(value || '')
    .replace(/sk-[A-Za-z0-9_-]+/g, '[REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9._-]+/g, 'Bearer [REDACTED]')
    .replace(/(password|api_key|token)=([^\s&]+)/gi, '$1=[REDACTED]')
    .replace(/(postgres|mysql):\/\/[^\s]+/gi, '$1://[REDACTED]')
    .replace(/Traceback \(most recent call last\):[\s\S]*/g, 'Internal error details redacted.');
}

function executionModeLabel(data = {}) {
  if (data.error && data.error.code === 'WORKSPACE_ACTIVE_LOCKED') return 'Workspace cleanup is locked.';
  if (data.target === 'sandbox') return 'Sandbox checked.';
  return 'Read-only guarded runtime.';
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${SAFY_API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options
  });

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error(`HTTP_${response.status}`);
    error.code = `HTTP_${response.status}`;
    error.body = body;
    throw normalizedError(error, 'Backend request failed.');
  }

  if (!body || body.success !== true) {
    const code = body?.error?.code || 'API_REQUEST_FAILED';
    const message = body?.error?.message || 'Backend request failed.';
    const details = body?.error?.details || null;
    const error = new Error(message);
    error.code = code;
    error.details = details;
    error.body = body;
    throw normalizedError(error, message);
  }

  return body.data;
}

function setConnectionStatus(kind, status, summaryText) {
  const dot = document.getElementById(`${kind}-status-dot`);
  const summary = document.getElementById(`${kind}-summary`);
  dot?.classList.remove('status-off', 'status-connected', 'status-warning', 'status-error');
  dot?.classList.add(status === 'connected' ? 'status-connected' : status === 'error' ? 'status-error' : 'status-off');
  if (summary && summaryText) summary.textContent = summaryText;
}


function showToast(message, tone = 'info') {
  const safeMessage = redactForDisplay(message || '');
  let host = document.getElementById('safy-toast-host');
  if (!host) {
    host = document.createElement('div');
    host.id = 'safy-toast-host';
    host.style.position = 'fixed';
    host.style.right = '18px';
    host.style.bottom = '18px';
    host.style.zIndex = '9999';
    host.style.display = 'grid';
    host.style.gap = '8px';
    document.body.appendChild(host);
  }

  const item = document.createElement('div');
  item.className = `safy-toast safy-toast-${tone}`;
  item.textContent = safeMessage;
  item.style.maxWidth = '360px';
  item.style.padding = '10px 12px';
  item.style.borderRadius = '10px';
  item.style.border = tone === 'success'
    ? '1px solid rgba(34, 197, 94, .45)'
    : tone === 'error'
      ? '1px solid rgba(239, 68, 68, .45)'
      : '1px solid rgba(56, 189, 248, .35)';
  item.style.background = 'rgba(15, 23, 42, .96)';
  item.style.color = 'var(--text, #E5E7EB)';
  item.style.boxShadow = '0 8px 24px rgba(0,0,0,.32)';
  item.style.fontSize = '12px';
  item.style.lineHeight = '1.45';
  host.appendChild(item);

  window.setTimeout(() => {
    item.style.opacity = '0';
    item.style.transition = 'opacity .18s ease';
    window.setTimeout(() => item.remove(), 220);
  }, 2600);
}


function loadSafyUiSettings() {
  try {
    const parsed = JSON.parse(localStorage.getItem(SAFY_UI_SETTINGS_KEY) || '{}');
    safyUiSettings = {
      ...SAFY_DEFAULT_UI_SETTINGS,
      ...(parsed && typeof parsed === 'object' ? parsed : {})
    };
  } catch {
    safyUiSettings = { ...SAFY_DEFAULT_UI_SETTINGS };
  }
  if (!['dark', 'light'].includes(safyUiSettings.theme)) safyUiSettings.theme = 'dark';
  safyUiSettings.streaming = Boolean(safyUiSettings.streaming);
  safyUiSettings.autoReadOnly = safyUiSettings.autoReadOnly !== false;
  return safyUiSettings;
}

function persistSafyUiSettings(next = {}) {
  safyUiSettings = { ...safyUiSettings, ...(next || {}) };
  localStorage.setItem(SAFY_UI_SETTINGS_KEY, JSON.stringify(safyUiSettings));
  applySafyUiSettings();
  return safyUiSettings;
}

function applySafyUiSettings() {
  document.documentElement.setAttribute('data-theme', safyUiSettings.theme || 'dark');
  const themeSelect = document.getElementById('safy-theme-select');
  const streamingToggle = document.getElementById('safy-streaming-toggle');
  const autoReadOnlyToggle = document.getElementById('safy-auto-readonly-toggle');
  if (themeSelect) themeSelect.value = safyUiSettings.theme || 'dark';
  if (streamingToggle) streamingToggle.checked = Boolean(safyUiSettings.streaming);
  if (autoReadOnlyToggle) autoReadOnlyToggle.checked = safyUiSettings.autoReadOnly !== false;
}

function toggleSettingsPanel() {
  const panel = document.getElementById('safy-settings-panel');
  const button = document.getElementById('settings-toggle-btn');
  if (!panel) return;
  const nextOpen = panel.classList.contains('hidden');
  panel.classList.toggle('hidden', !nextOpen);
  button?.setAttribute('aria-expanded', nextOpen ? 'true' : 'false');
}

function initSettingsPanel() {
  loadSafyUiSettings();
  applySafyUiSettings();
  document.getElementById('settings-toggle-btn')?.addEventListener('click', toggleSettingsPanel);
  document.getElementById('safy-theme-select')?.addEventListener('change', (event) => {
    persistSafyUiSettings({ theme: event.target.value === 'light' ? 'light' : 'dark' });
  });
  document.getElementById('safy-streaming-toggle')?.addEventListener('change', (event) => {
    persistSafyUiSettings({ streaming: Boolean(event.target.checked) });
  });
  document.getElementById('safy-auto-readonly-toggle')?.addEventListener('change', (event) => {
    persistSafyUiSettings({ autoReadOnly: Boolean(event.target.checked) });
  });
}

function streamTextInto(element, text, speed = 12) {
  const content = String(text || '');
  element.textContent = '';
  let index = 0;
  const tick = () => {
    index = Math.min(index + 2, content.length);
    element.textContent = content.slice(0, index);
    const messages = document.getElementById('chat-messages');
    if (messages) messages.scrollTop = messages.scrollHeight;
    if (index < content.length) window.setTimeout(tick, speed);
  };
  tick();
}

function normalizeProviderType(value) {
  const raw = String(value || '').trim().toLowerCase();

  const aliases = {
    'lm studio': 'lmstudio',
    'lm_studio': 'lmstudio',
    'lm-studio': 'lmstudio',
    'lmstudio': 'lmstudio',
    'openrouter': 'openrouter',
    'open_router': 'openrouter',
    'open-router': 'openrouter',
    'openai': 'openai',
    'open_ai': 'openai',
    'open-ai': 'openai',
    'ollama': 'ollama',
    'openai compatible': 'openai_compat',
    'openai_compatible': 'openai_compat',
    'openai-compat': 'openai_compat',
    'openai_compat': 'openai_compat'
  };

  return aliases[raw] || raw;
}

function inferModelAuthFields(providerType) {
  const normalizedProvider = normalizeProviderType(providerType);
  const apiKey = (document.getElementById('model-api-key')?.value || '').trim();

  if (normalizedProvider === 'lmstudio' || normalizedProvider === 'ollama') {
    return { auth_mode: 'local_no_auth', api_key: null, api_key_env: null };
  }

  return {
    auth_mode: 'env_api_key',
    api_key: apiKey || null,
    api_key_env: null
  };
}

function modelProfileIdentity(providerType) {
  const normalizedProvider = normalizeProviderType(providerType);

  if (normalizedProvider === 'lmstudio') {
    return { profile_id: 'lmstudio_local', display_name: 'LM Studio Local' };
  }

  return { profile_id: 'main_model', display_name: normalizedProvider || 'Model provider' };
}

function summarizeModel(profile) {
  if (!profile) return 'Loading...';
  return `${profile.display_name || profile.provider || 'Model'} / ${profile.model_name || profile.model || profile.profile_id}`;
}

function summarizeDatabase(profile) {
  if (!profile) return 'Database: Not connected';
  return parseDatabaseMode(profile).summary;
}

function sandboxStatusText(sandbox) {
  const status = String(sandbox?.status || '').toLowerCase();
  if (!status) return 'Not ready';
  if (status === 'ready') return 'Ready';
  if (status === 'starting') return 'Creating';
  if (status === 'failed') return 'Error';
  return sandbox.status;
}


async function loadProfiles() {
  try {
    const [models, activeModel, databases, activeDatabase] = await Promise.all([
      apiRequest('/model-profiles'),
      apiRequest('/model-profiles/active'),
      apiRequest('/database-profiles'),
      apiRequest('/database-profiles/active')
    ]);
    safyModelProfile = activeModel || models.find(profile => profile.is_active) || models[0] || null;
    safyDatabaseProfiles = Array.isArray(databases) ? databases : [];
    const activeDatabaseProfile = activeDatabase && activeDatabase.profile_id ? activeDatabase : null;
    safyDatabaseProfile = activeDatabaseProfile || safyDatabaseProfiles.find(profile => profile.active) || safyDatabaseProfiles[0] || null;
    setConnectionStatus('model', safyModelProfile ? 'connected' : 'off', summarizeModel(safyModelProfile));
    const dbStatus = parseDatabaseMode(safyDatabaseProfile);
    setConnectionStatus('database', dbStatus.status, dbStatus.summary);
    const topbarModel = document.getElementById('topbar-model-value');
    const topbarDatabase = document.getElementById('topbar-database-value');
    const topbarMode = document.getElementById('topbar-mode-value');
    if (topbarModel) topbarModel.textContent = summarizeModel(safyModelProfile);
    if (topbarDatabase) topbarDatabase.textContent = dbStatus.summary;
    if (topbarMode) topbarMode.textContent = dbStatus.label;
    syncDatabaseFields();
    renderDatabaseSwitchOptions();
    await updateSchemaLaunchHint();
  } catch (error) {
    setConnectionStatus('model', 'error', 'Profile API unavailable');
    setConnectionStatus('database', 'error', 'Profile API unavailable');
    renderNormalizedError(error);
  }
}

async function ensureActiveSandbox() {
  if (!safyDatabaseProfile?.profile_id) return null;
  const ensured = await apiRequest(`/database-profiles/${safyDatabaseProfile.profile_id}/ensure-sandbox`, { method: 'POST' });
  safySandboxId = ensured?.sandbox?.id || null;
  return ensured?.sandbox || null;
}

function applyDatabaseWorkflowResult(data, successMessage) {
  if (!data) return;
  safyDatabaseProfile = {
    ...(safyDatabaseProfile || {}),
    ...data,
    mode: data.mode || 'real',
    connection_status: data.connection_status || 'connected'
  };
  if (data.sandbox?.id) safySandboxId = data.sandbox.id;

  const dbStatus = parseDatabaseMode(safyDatabaseProfile);
  setConnectionStatus('database', dbStatus.status, dbStatus.summary);

  const topbarDatabase = document.getElementById('topbar-database-value');
  const topbarMode = document.getElementById('topbar-mode-value');
  if (topbarDatabase) topbarDatabase.textContent = dbStatus.summary;
  if (topbarMode) topbarMode.textContent = dbStatus.label;

  renderDatabaseSwitchOptions();
  updateSchemaLaunchHint();

  if (data.sandbox_status) {
    const message = data.sandbox_message || `Database connected. Sandbox ${data.sandbox_status}.`;
    const level = data.sandbox_status === 'sandbox_failed' || data.sandbox_status === 'sandbox_not_ready' ? 'info' : 'success';
    showToast(message, level);
  } else if (successMessage) {
    showToast(successMessage, 'success');
  }
}

function renderNormalizedError(error) {
  const box = document.getElementById('normalized-error');
  const data = normalizedError(error, 'Unknown SAFY error.');
  if (!box) return;
  box.style.display = 'block';
  const badge = box.querySelector('.error-code-badge');
  const msg = box.querySelector('.error-message');
  const next = document.getElementById('execute-error-hint');
  if (badge) badge.textContent = data.code;
  if (msg) msg.textContent = data.message;
  if (next) next.textContent = data.next_action;
}

function showInlineStatus(kind, message, tone = 'info') {
  const summary = document.getElementById(`${kind}-summary`);
  const dotStatus = tone === 'error' ? 'error' : tone === 'success' ? 'connected' : 'off';
  setConnectionStatus(kind, dotStatus, message);
  if (kind === 'model') {
    const topbarModel = document.getElementById('topbar-model-value');
    if (topbarModel) topbarModel.textContent = message;
  }
  if (kind === 'database') {
    const topbarDatabase = document.getElementById('topbar-database-value');
    if (topbarDatabase) topbarDatabase.textContent = message;
  }
  if (summary) summary.title = message;
}

function hideNormalizedError() {
  const box = document.getElementById('normalized-error');
  if (box) box.style.display = 'none';
}

function resetExecuteRuntimePanel({ clearSql = false } = {}) {
  safyCurrentCheck = null;
  if (clearSql) {
    const input = document.getElementById('user-query-input');
    if (input) input.value = '';
  }
  const checkStatus = document.getElementById('execute-check-status');
  const runStatus = document.getElementById('execute-run-status');
  const target = document.getElementById('execute-target-used');
  const rows = document.getElementById('execute-row-count');
  const summary = document.getElementById('execution-summary');
  if (checkStatus) checkStatus.textContent = 'not checked';
  if (runStatus) runStatus.textContent = 'not executed';
  if (target) target.textContent = 'none';
  if (rows) rows.textContent = '0';
  if (summary) summary.textContent = 'Review generated SQL, run Check Safety, then Execute if needed.';
  const execute = document.getElementById('execute-query-btn');
  execute?.setAttribute('disabled', 'disabled');
  execute?.classList.add('disabled');
}

function parseDatabaseMode(profile) {
  if (!profile || !profile.profile_id || profile.active === false) {
    return { label: 'Loading...', summary: 'Loading...', status: 'off' };
  }

  const mode = String(profile.mode || (profile.real_db_readonly ? 'real' : 'not_connected')).toLowerCase();
  const connectionStatus = String(profile.connection_status || profile.status || 'unknown').toLowerCase();
  const displayName = profile.display_name || profile.profile_id || 'Database';

  if (mode === 'real' && connectionStatus === 'failed') {
    return { label: 'Database: Real connection failed', summary: `${displayName} · Real connection failed`, status: 'error' };
  }
  if (mode === 'real') {
    return { label: 'Agent readonly · User sandbox-then-real', summary: `${displayName} · Connected`, status: 'connected' };
  }

  return { label: 'Database: Not connected', summary: 'Not connected', status: 'off' };
}

function formatAgentReply(reply) {
  if (hasStructuredQueryResult(reply)) {
    const rowCount = queryRowCountFromPayload(reply);
    return reply?.answer || `Đã đọc dữ liệu an toàn từ database. Row count: ${rowCount}.`;
  }
  if (reply?.answer && !reply?.generated_sql && !reply?.check && !reply?.execute) {
    return String(reply.answer);
  }
  const lines = [];
  if (reply?.answer) lines.push(String(reply.answer));
  if (reply?.generated_sql) {
    lines.push('', 'Generated SQL:', reply.generated_sql);
  }
  if (reply?.check?.decision || reply?.safety?.workflow) {
    lines.push('', `Safety: ${reply.check?.decision || reply.safety?.workflow}`);
  }
  if (reply?.execute?.status || reply?.execute?.summary) {
    lines.push('', `Execute: ${reply.execute.summary || reply.execute.status}`);
  }
  return redactForDisplay(lines.join('\n') || 'Safy backend returned an empty agent response.');
}

function queryRowsFromPayload(data = {}) {
  const display = data.chat_display && typeof data.chat_display === 'object' ? data.chat_display : {};
  if (Array.isArray(display.rows)) return display.rows;
  if (Array.isArray(data.query_result?.rows)) return data.query_result.rows;
  if (Array.isArray(data.execute?.rows)) return data.execute.rows;
  if (Array.isArray(data.rows)) return data.rows;
  if (Array.isArray(data.result?.rows)) return data.result.rows;
  return [];
}

function queryColumnsFromPayload(data = {}) {
  const display = data.chat_display && typeof data.chat_display === 'object' ? data.chat_display : {};
  const candidates = [display.columns, data.query_result?.columns, data.execute?.columns, data.columns, data.result?.columns];
  for (const cols of candidates) {
    if (Array.isArray(cols) && cols.length) return cols.map(String);
  }
  const seen = [];
  for (const row of queryRowsFromPayload(data)) {
    if (!row || typeof row !== 'object' || Array.isArray(row)) continue;
    for (const key of Object.keys(row)) {
      if (!seen.includes(key)) seen.push(key);
    }
  }
  return seen;
}

function queryRowCountFromPayload(data = {}) {
  const display = data.chat_display && typeof data.chat_display === 'object' ? data.chat_display : {};
  const metadata = data.metadata || data.execute?.metadata || {};
  const rows = queryRowsFromPayload(data);
  return display.row_count ?? data.query_result?.row_count ?? data.execute?.row_count ?? data.row_count ?? metadata.row_count ?? rows.length;
}

function querySqlFromPayload(data = {}, fallbackSql = '') {
  const display = data.chat_display && typeof data.chat_display === 'object' ? data.chat_display : {};
  return String(display.sql || data.query_result?.sql || data.executed_sql || data.normalized_sql || data.generated_sql || data.sql || fallbackSql || '').trim();
}

function hasStructuredQueryResult(data = {}) {
  if (!data || typeof data !== 'object') return false;
  const display = data.chat_display && typeof data.chat_display === 'object' ? data.chat_display : null;
  if (display?.type === 'query_result') return true;
  if (Array.isArray(data.query_result?.rows)) return true;
  if (Array.isArray(data.execute?.rows) && (data.execute?.read_only || data.safety?.workflow === 'direct_read')) return true;
  if (Array.isArray(data.rows) && (data.read_only || data.metadata?.read_only)) return true;
  return false;
}

function isDirectReadReply(data = {}) {
  return Boolean(
    data?.safety?.workflow === 'direct_read' ||
    data?.chat_display?.type === 'query_result' ||
    data?.query_result ||
    data?.execute?.read_only ||
    data?.read_only
  );
}

function safeText(value) {
  return redactForDisplay(value === null || value === undefined ? '' : String(value));
}

function makeElement(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined && text !== null) el.textContent = text;
  return el;
}

function buildCodeBlockForChat(sql) {
  const block = makeElement('div', 'safy-chat-code-block');
  const header = makeElement('div', 'safy-chat-code-header');
  header.appendChild(makeElement('span', 'safy-chat-code-label', 'SQL'));
  const copyBtn = makeElement('button', 'safy-chat-copy-btn', 'Copy');
  copyBtn.type = 'button';
  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(sql);
      copyBtn.textContent = 'Copied';
      window.setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1200);
    } catch {
      copyBtn.textContent = 'Copy failed';
      window.setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1200);
    }
  });
  header.appendChild(copyBtn);
  const code = makeElement('pre', 'safy-chat-code-content');
  code.textContent = sql;
  block.appendChild(header);
  block.appendChild(code);
  return block;
}

function buildQueryResultCard(data = {}, fallbackSql = '') {
  const rows = queryRowsFromPayload(data);
  const columns = queryColumnsFromPayload(data).slice(0, 24);
  const rowCount = queryRowCountFromPayload(data);
  const sql = querySqlFromPayload(data, fallbackSql);
  const card = makeElement('div', 'safy-result-card');

  const header = makeElement('div', 'safy-result-card-header');
  const titleWrap = makeElement('div', 'safy-result-title-wrap');
  titleWrap.appendChild(makeElement('div', 'safy-result-title', 'Database result'));
  titleWrap.appendChild(makeElement('div', 'safy-result-subtitle', 'Read-only query executed safely on the active database.'));
  header.appendChild(titleWrap);

  const badges = makeElement('div', 'safy-result-badges');
  badges.appendChild(makeElement('span', 'safy-result-badge safe', 'Read-only'));
  badges.appendChild(makeElement('span', 'safy-result-badge', `${rowCount} rows`));
  header.appendChild(badges);
  card.appendChild(header);

  if (sql) card.appendChild(buildCodeBlockForChat(sql));

  if (!rows.length) {
    card.appendChild(makeElement('div', 'safy-result-empty', 'Không có dòng nào để hiển thị.'));
    return card;
  }

  const tableWrap = makeElement('div', 'safy-result-table-wrap');
  const table = makeElement('table', 'safy-result-table');
  const thead = document.createElement('thead');
  const headRow = document.createElement('tr');
  columns.forEach((col) => headRow.appendChild(makeElement('th', '', col)));
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  rows.slice(0, 50).forEach((row) => {
    const tr = document.createElement('tr');
    columns.forEach((col) => {
      const td = makeElement('td', '', safeText(row && typeof row === 'object' && !Array.isArray(row) ? row[col] : row));
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  tableWrap.appendChild(table);
  card.appendChild(tableWrap);

  if (rows.length > 50) {
    card.appendChild(makeElement('div', 'safy-result-footnote', `Đang hiển thị 50 dòng đầu tiên; còn ${rows.length - 50} dòng bị ẩn trong preview.`));
  }
  return card;
}

function setChatRequestPending(pending) {
  safyChatRequestPending = Boolean(pending);
  const sendButton = document.getElementById('send-message-btn');
  const inputWrapper = document.querySelector('.chat-input-wrapper');
  const messages = document.getElementById('chat-messages');
  if (sendButton) {
    sendButton.disabled = safyChatRequestPending;
    sendButton.setAttribute('aria-disabled', String(safyChatRequestPending));
  }
  inputWrapper?.classList.toggle('is-request-pending', safyChatRequestPending);
  if (messages) messages.setAttribute('aria-busy', String(safyChatRequestPending));
}

function appendChatLoadingIndicator() {
  const empty = document.getElementById('chat-empty-state');
  const messages = document.getElementById('chat-messages');
  if (empty) empty.style.display = 'none';
  if (!messages) return null;

  messages.style.display = 'block';
  const message = document.createElement('div');
  message.className = 'message assistant-message safy-loading-message';
  message.setAttribute('role', 'status');
  message.setAttribute('aria-label', 'Safy is processing the request');

  const avatar = makeElement('div', 'message-avatar agent-avatar', 'S');
  const content = makeElement('div', 'message-content');
  const bubble = makeElement('div', 'message-bubble safy-loading-bubble');
  const dots = makeElement('div', 'safy-loading-dots');
  dots.setAttribute('aria-hidden', 'true');
  for (let index = 0; index < 3; index += 1) dots.appendChild(makeElement('span', 'safy-loading-dot'));
  bubble.appendChild(dots);
  content.appendChild(bubble);
  message.append(avatar, content);
  messages.appendChild(message);
  messages.scrollTop = messages.scrollHeight;
  return message;
}

function removeChatLoadingIndicator(message) {
  if (!message) return;
  message.remove();
  const messages = document.getElementById('chat-messages');
  if (messages) messages.scrollTop = messages.scrollHeight;
}

function appendChatBubble(role, text, options = {}) {
  const empty = document.getElementById('chat-empty-state');
  const messages = document.getElementById('chat-messages');
  if (empty) empty.style.display = 'none';
  if (!messages) return null;

  const isUser = role === 'user';
  const displayUsername = safyRuntimeUsername || 'User';
  const avatar = isUser ? displayUsername.charAt(0).toUpperCase() : 'S';
  const cssClass = isUser ? 'user-message' : 'assistant-message';
  const meta = isUser ? displayUsername : 'Safy';
  const timeText = options.timeText || new Date().toLocaleTimeString();

  messages.style.display = 'block';
  messages.insertAdjacentHTML('beforeend', `<div class="message ${cssClass}"><div class="message-avatar ${isUser ? 'user-avatar' : 'agent-avatar'}">${avatar}</div><div class="message-content"><div class="message-bubble"></div><div class="message-meta">${meta} - ${timeText}</div></div></div>`);
  const messageEl = messages.lastElementChild;
  const bubble = messageEl.querySelector('.message-bubble');
  if (options.node) {
    messageEl.classList.add('message-rich');
    bubble.classList.add('message-bubble-rich');
    bubble.appendChild(options.node);
  } else if (options.stream && !isUser) {
    streamTextInto(bubble, text);
  } else {
    bubble.textContent = text;
  }
  messages.scrollTop = messages.scrollHeight;
  return messages;
}

function appendQueryResultToChat(data = {}, fallbackSql = '') {
  if (!hasStructuredQueryResult(data) && !Array.isArray(data.rows)) return false;
  const card = buildQueryResultCard(data, fallbackSql);
  appendChatBubble('assistant', '', { node: card });
  return true;
}

function riskPanelForLevel(level, status) {
  const value = String(level || status || '').toLowerCase();
  if (['critical', 'danger', 'destructive', 'blocked', 'block', 'unsafe'].includes(value)) return 'risk-danger';
  if (['high'].includes(value)) return 'risk-danger';
  if (['medium', 'warning', 'warn', 'requires_confirmation'].includes(value)) return 'risk-warning';
  if (['low', 'safe', 'allow', 'allowed', 'read_only'].includes(value)) return 'risk-safe';
  return 'risk-unchecked';
}


function getStoredSafyUser() {
  try {
    const raw = localStorage.getItem(SAFY_AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || !parsed.username) return null;
    return parsed;
  } catch {
    return null;
  }
}

function setStoredSafyUser(username) {
  const safeUsername = String(username || '').trim();
  if (!safeUsername) return;
  localStorage.setItem(SAFY_AUTH_STORAGE_KEY, JSON.stringify({
    username: safeUsername,
    signed_in_at: new Date().toISOString()
  }));
}

function applySafyRuntimeUser(username, profile = {}) {
  safyRuntimeUsername = String(username || '').trim();
  safyUserProfile = { ...(safyUserProfile || {}), ...(profile || {}), username: safyRuntimeUsername };

  const label = document.getElementById('current-user-label');
  if (label) label.textContent = safyRuntimeUsername || 'Not signed in';

  const dbUsername = document.getElementById('db-username');
  if (dbUsername && safyRuntimeUsername) {
    dbUsername.value = safyRuntimeUsername;
  }
}










async function loadDashboardUserProfile() {
  const stored = getStoredSafyUser();
  if (!stored?.username) {
    window.location.replace('/login');
    return false;
  }
  try {
    const profile = await apiRequest('/auth/profile');
    applySafyRuntimeUser(profile?.username || stored.username, profile || {});
  } catch {
    applySafyRuntimeUser(stored.username, { username: stored.username });
  }
  return true;
}

function handleSafyLogout() {
  localStorage.removeItem(SAFY_AUTH_STORAGE_KEY);
  window.location.replace('/login');
}

function schemaUiSlug(value) {
  const normalized = String(value || 'schema-graph')
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, '-')
    .replace(/^[._-]+|[._-]+$/g, '')
    .slice(0, 96);
  return normalized || 'schema-graph';
}

async function openSchemaGraphPage() {
  let slug = 'schema-graph';
  try {
    const graph = await apiRequest('/schema-graph/active');
    slug = schemaUiSlug(graph?.database_name || graph?.database_profile_id || graph?.graph?.name);
  } catch {
    // The graph page can still load and surface the normalized backend error.
  }
  window.location.assign(`/Dashboard/${encodeURIComponent(slug)}`);
}

async function updateSchemaLaunchHint() {
  const hint = document.getElementById('schema-window-launch-hint');
  if (!hint) return;
  try {
    const graph = await apiRequest('/schema-graph/active');
    const tables = Array.isArray(graph?.tables) ? graph.tables.length : 0;
    const edges = Array.isArray(graph?.edges) ? graph.edges.length : 0;
    hint.textContent = graph?.status === 'ready' && tables
      ? `${tables} table(s), ${edges} relationship(s) · opens in the current Dashboard view.`
      : 'No stored graph yet · open the Schema Graph page to refresh.';
  } catch {
    hint.textContent = 'Schema Graph replaces the Dashboard view and keeps browser Back navigation.';
  }
}

async function deleteActiveSchemaGraph() {
  hideNormalizedError();
  try {
    await apiRequest('/schema-graph/active', { method: 'DELETE' });
    await updateSchemaLaunchHint();
    showToast('Active database schema graph deleted.', 'success');
  } catch (error) {
    renderNormalizedError(error);
  }
}

async function resetAllSchemaGraphs() {
  hideNormalizedError();
  try {
    await apiRequest('/schema-graph', { method: 'DELETE' });
    await updateSchemaLaunchHint();
    showToast('All stored schema graphs deleted.', 'success');
  } catch (error) {
    renderNormalizedError(error);
  }
}

function sidebarState() {
  try {
    return JSON.parse(localStorage.getItem(SAFY_SIDEBAR_STATE_KEY) || '{}');
  } catch {
    return {};
  }
}

function persistSidebarState() {
  const shell = document.getElementById('app-shell');
  if (!shell) return;
  localStorage.setItem(SAFY_SIDEBAR_STATE_KEY, JSON.stringify({ left: shell.classList.contains('left-collapsed'), right: shell.classList.contains('right-collapsed') }));
}

function syncSidebarButtons() {
  const shell = document.getElementById('app-shell');
  if (!shell) return;
  const leftCollapsed = shell.classList.contains('left-collapsed');
  const rightCollapsed = shell.classList.contains('right-collapsed');
  const leftButton = document.getElementById('toggle-left-sidebar-btn');
  const rightButton = document.getElementById('toggle-right-sidebar-btn');
  leftButton?.setAttribute('aria-expanded', String(!leftCollapsed));
  rightButton?.setAttribute('aria-expanded', String(!rightCollapsed));
  if (leftButton) leftButton.title = leftCollapsed ? 'Open left sidebar' : 'Close left sidebar';
  if (rightButton) rightButton.title = rightCollapsed ? 'Open right sidebar' : 'Close right sidebar';
}

function restoreSidebarState() {
  const shell = document.getElementById('app-shell');
  if (!shell) return;
  const state = sidebarState();
  shell.classList.toggle('left-collapsed', Boolean(state.left));
  shell.classList.toggle('right-collapsed', Boolean(state.right));
  syncSidebarButtons();
}

function toggleLeftSidebar() {
  document.getElementById('app-shell')?.classList.toggle('left-collapsed');
  syncSidebarButtons();
  persistSidebarState();
}

function toggleRightSidebar() {
  document.getElementById('app-shell')?.classList.toggle('right-collapsed');
  syncSidebarButtons();
  persistSidebarState();
}

function contextSourceError(message = '') {
  const error = document.getElementById('context-source-error');
  if (!error) return;
  error.textContent = message;
  error.classList.toggle('hidden', !message);
}

function contextInlineError(message = '') {
  const error = document.getElementById('context-inline-error');
  if (!error) return;
  error.textContent = message;
  error.classList.toggle('hidden', !message);
}

function contextSourceSize(length) {
  if (length < 1024) return `${length} B`;
  return `${Math.ceil(length / 1024)} KiB`;
}

function removeContextSource(sourceId) {
  safyContextSources = safyContextSources.filter((candidate) => candidate.id !== sourceId);
  renderContextSources();
}

function renderContextSources() {
  const strip = document.getElementById('context-attachment-strip');
  const list = document.getElementById('context-attachment-list');
  const count = document.getElementById('context-source-count');
  const hasSources = safyContextSources.length > 0;

  if (count) {
    count.textContent = `${safyContextSources.length} attached`;
    count.classList.toggle('hidden', !hasSources);
  }
  strip?.classList.toggle('hidden', !hasSources);
  if (!list) return;

  list.replaceChildren();
  safyContextSources.forEach((source) => {
    const chip = document.createElement('div');
    chip.className = 'context-attachment-chip';
    chip.title = `${source.kind === 'url' ? 'Public URL' : 'Local file'} · ${contextSourceSize(source.content.length)}`;

    const icon = document.createElement('span');
    icon.className = 'context-attachment-icon';
    icon.textContent = source.kind === 'url' ? '↗' : 'TXT';
    icon.setAttribute('aria-hidden', 'true');

    const name = document.createElement('span');
    name.className = 'context-attachment-name';
    name.textContent = source.name;

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'context-attachment-remove';
    remove.setAttribute('aria-label', `Remove ${source.name}`);
    remove.title = `Remove ${source.name}`;
    remove.textContent = '×';
    remove.addEventListener('click', () => removeContextSource(source.id));

    chip.append(icon, name, remove);
    list.appendChild(chip);
  });
}

function openContextUrlModal() {
  contextSourceError('');
  document.getElementById('context-url-modal')?.classList.remove('hidden');
  setTimeout(() => document.getElementById('context-url-input')?.focus(), 0);
}

function closeContextUrlModal() {
  document.getElementById('context-url-modal')?.classList.add('hidden');
}

function chooseContextFiles() {
  contextInlineError('');
  document.getElementById('context-file-input')?.click();
}

function addContextSource(source) {
  if (safyContextSources.length >= SAFY_CONTEXT_MAX_SOURCES) {
    throw new Error(`A maximum of ${SAFY_CONTEXT_MAX_SOURCES} context sources is allowed.`);
  }
  const content = String(source?.content || '').trim();
  if (!content) throw new Error('The selected source contains no readable text.');
  safyContextSources.push({
    id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
    kind: source.kind === 'url' ? 'url' : 'file',
    name: String(source.name || source.url || 'context').slice(0, 180),
    url: source.url ? String(source.url).slice(0, 2048) : undefined,
    content: content.slice(0, SAFY_CONTEXT_MAX_FILE_BYTES)
  });
  contextInlineError('');
  renderContextSources();
}

async function addContextUrl() {
  const input = document.getElementById('context-url-input');
  const url = (input?.value || '').trim();
  contextSourceError('');
  if (!url) {
    contextSourceError('Enter a public HTTP/HTTPS URL.');
    return;
  }
  const button = document.getElementById('context-url-add-btn');
  if (button) button.disabled = true;
  try {
    const data = await apiRequest('/context/fetch-url', { method: 'POST', body: JSON.stringify({ url }) });
    addContextSource({ kind: 'url', name: data.title || data.url, url: data.url, content: data.content });
    if (input) input.value = '';
    closeContextUrlModal();
    showToast('Public URL attached for the next message.', 'success');
  } catch (error) {
    contextSourceError(error?.message || 'Could not fetch that URL.');
  } finally {
    if (button) button.disabled = false;
  }
}

function isReadableContextFile(file) {
  const filename = String(file?.name || '').trim().toLowerCase();
  return filename.endsWith('.md') || filename.endsWith('.txt');
}

async function addContextFiles(fileList) {
  contextInlineError('');
  const errors = [];
  let attached = 0;
  for (const file of Array.from(fileList || [])) {
    try {
      if (safyContextSources.length >= SAFY_CONTEXT_MAX_SOURCES) {
        throw new Error(`A maximum of ${SAFY_CONTEXT_MAX_SOURCES} context sources is allowed.`);
      }
      if (!isReadableContextFile(file)) {
        throw new Error(`${file.name}: only .md and .txt files are supported.`);
      }
      if (file.size > SAFY_CONTEXT_MAX_FILE_BYTES) {
        throw new Error(`${file.name}: file exceeds 1 MiB.`);
      }
      addContextSource({ kind: 'file', name: file.name, content: await file.text() });
      attached += 1;
    } catch (error) {
      errors.push(error.message || 'Could not read a selected file.');
    }
  }
  const input = document.getElementById('context-file-input');
  if (input) input.value = '';
  if (errors.length) contextInlineError(errors[0]);
  if (attached) showToast(`${attached} file${attached === 1 ? '' : 's'} attached for the next message.`, 'success');
}

function clearContextSources() {
  safyContextSources = [];
  contextSourceError('');
  contextInlineError('');
  renderContextSources();
}

function contextSourcesForRequest() {
  return safyContextSources.map(({ kind, name, url, content }) => ({ kind, name, url, content }));
}

async function initSafyDashboard() {
  if (!await loadDashboardUserProfile()) return;
  restoreSidebarState();
  initSafyUI();
}

function openModelConfig() {
  syncModelFields();
  setPanel('model', true);
}
function closeModelConfig() { setPanel('model', false); }
function openDatabaseConfig() { syncDatabaseFields(); setPanel('database', true); }
function closeDatabaseConfig() { setPanel('database', false); }

function syncDatabaseFields() {
  const profile = safyDatabaseProfile;
  const nameField = document.getElementById('db-profile-name');
  const baseUrlField = document.getElementById('db-base-url');
  const apiKeyField = document.getElementById('db-api-key');
  const usernameField = document.getElementById('db-username');

  const backendUsername = safyUserProfile?.username || safyRuntimeUsername;

  if (!profile || !profile.profile_id) {
    if (usernameField && backendUsername) usernameField.value = backendUsername;
    if (apiKeyField) apiKeyField.placeholder = 'Enter API key';
    return;
  }

  if (nameField) nameField.value = profile.display_name || profile.profile_id || nameField.value || '';
  if (baseUrlField && profile.base_url) baseUrlField.value = profile.base_url;
  if (usernameField) usernameField.value = backendUsername || profile.username || usernameField.value || '';
  if (apiKeyField) {
    apiKeyField.value = '';
    apiKeyField.placeholder = profile.has_raw_secret || profile.secret_stored ? 'Saved in .env; leave blank to keep existing key' : 'Enter API key';
  }
}

function syncModelFields() {
  const provider = normalizeProviderType(document.getElementById('model-provider')?.value || 'lmstudio');
  const urlField = document.getElementById('model-base-url');
  const nameField = document.getElementById('model-name');
  const apiKeyInput = document.getElementById('model-api-key');
  const apiKeyHelp = document.getElementById('model-api-key-help');

  if (provider === 'lmstudio') {
    if (urlField && (!urlField.value || urlField.value === 'https://api.openrouter.ai/v1' || urlField.value === 'https://api.openai.com/v1')) {
      urlField.value = 'http://localhost:1234/v1';
    }
    if (nameField && (!nameField.value || nameField.value === 'local-model')) {
      nameField.value = 'qwen2.5-coder-7b-instruct';
    }
    if (apiKeyInput) {
      apiKeyInput.required = false;
      apiKeyInput.placeholder = 'Not required for LM Studio';
    }
    if (apiKeyHelp) apiKeyHelp.textContent = 'Optional for local providers like LM Studio/Ollama.';
  } else if (provider === 'ollama') {
    if (apiKeyInput) {
      apiKeyInput.required = false;
      apiKeyInput.placeholder = 'Not required for Ollama';
    }
    if (apiKeyHelp) apiKeyHelp.textContent = 'Optional for local providers like LM Studio/Ollama.';
  } else if (provider === 'openrouter') {
    if (urlField && (!urlField.value || urlField.value === 'http://localhost:1234/v1')) {
      urlField.value = 'https://api.openrouter.ai/v1';
    }
    if (apiKeyInput) {
      apiKeyInput.required = true;
      apiKeyInput.placeholder = 'Enter API key or env var name';
    }
    if (apiKeyHelp) apiKeyHelp.textContent = 'Required for remote providers. Current backend stores env-name style values.';
  } else if (provider === 'openai' || provider === 'openai_compat' || provider === 'anthropic') {
    if (urlField && (!urlField.value || urlField.value === 'http://localhost:1234/v1')) {
      urlField.value = provider === 'anthropic' ? 'https://api.anthropic.com/v1' : 'https://api.openai.com/v1';
    }
    if (apiKeyInput) {
      apiKeyInput.required = true;
      apiKeyInput.placeholder = 'Enter API key or env var name';
    }
    if (apiKeyHelp) apiKeyHelp.textContent = 'Required for remote providers. Current backend stores env-name style values.';
  }
}

function setPanel(kind, open) {
  document.getElementById(`${kind}-config-panel`)?.classList.toggle('hidden', !open);
  document.getElementById(`${kind}-connect-btn`)?.setAttribute('aria-expanded', String(open));
}

function modelFormBody() {
  const rawProvider = document.getElementById('model-provider')?.value || 'lmstudio';
  const normalizedProvider = normalizeProviderType(rawProvider);
  const inferred = inferModelAuthFields(normalizedProvider);
  const identity = modelProfileIdentity(normalizedProvider);
  const modelName = (document.getElementById('model-name')?.value || 'qwen2.5-coder-7b-instruct').trim();

  return {
    profile_id: normalizedProvider === 'lmstudio' ? 'lmstudio_local' : identity.profile_id,
    display_name: identity.display_name,
    provider_type: normalizedProvider,
    provider: normalizedProvider,
    base_url: (document.getElementById('model-base-url')?.value || 'http://localhost:1234/v1').trim(),
    auth_mode: inferred.auth_mode,
    api_key: inferred.api_key,
    api_key_env: inferred.api_key_env,
    model: modelName,
    model_name: modelName,
    is_active: false,
    capabilities: {
      chat: true,
      json_mode: 'optional_or_detected',
      tool_calling: 'optional_or_detected'
    }
  };
}

async function refreshActiveModelProfile() {
  try {
    const activeProfile = await apiRequest('/model-profiles/active');
    safyModelProfile = activeProfile;
    setConnectionStatus('model', activeProfile ? 'connected' : 'off', summarizeModel(activeProfile));
    const topbarModel = document.getElementById('topbar-model-value');
    if (topbarModel) topbarModel.textContent = summarizeModel(activeProfile);
    return activeProfile;
  } catch (error) {
    const activeError = normalizedError({ code: 'MODEL_PROFILE_ACTIVE_REFRESH_FAILED', message: error.message, details: error.details, body: error.body }, 'MODEL_PROFILE_ACTIVE_REFRESH_FAILED');
    throw activeError;
  }
}

async function saveModelConfig() {
  hideNormalizedError();
  try {
    const payload = { ...modelFormBody(), is_active: true };
    const requiresApiKey = !['lmstudio', 'ollama'].includes(payload.provider_type);
    if (!payload.base_url || !payload.model) {
      throw normalizedError({ code: 'MODEL_FORM_INVALID', message: 'Provider, Base URL, and Model Name are required.' }, 'Provider, Base URL, and Model Name are required.');
    }
    if (requiresApiKey && !payload.api_key) {
      throw normalizedError({ code: 'MODEL_API_KEY_REQUIRED', message: 'API Key is required for remote providers.' }, 'API Key is required for remote providers.');
    }
    const data = await apiRequest('/model-profiles', { method: 'POST', body: JSON.stringify(payload) });
    const savedProfileId = data?.profile_id || payload.profile_id;
    await apiRequest(`/model-profiles/${savedProfileId}/activate`, { method: 'POST' });
    const activeProfile = await refreshActiveModelProfile();
    safyModelProfile = activeProfile;
    setConnectionStatus('model', 'connected', summarizeModel(activeProfile));
    const topbarModel = document.getElementById('topbar-model-value');
    if (topbarModel) topbarModel.textContent = summarizeModel(activeProfile);
    hideNormalizedError();
    closeModelConfig();
    showToast(`Model profile saved and activated: ${savedProfileId}.`, 'success');
    return savedProfileId;
  } catch (error) {
    setConnectionStatus('model', 'error', normalizedError(error, 'MODEL_PROFILE_SAVE_FAILED').message);
    renderNormalizedError(error);
    throw error;
  }
}

async function testModelConnection() {
  hideNormalizedError();
  try {
    let targetProfileId = safyModelProfile?.profile_id;
    if (!targetProfileId) {
      targetProfileId = await saveModelConfig();
    }
    const activeProfile = await refreshActiveModelProfile();
    targetProfileId = activeProfile?.profile_id || targetProfileId;
    const data = await apiRequest(`/model-profiles/${targetProfileId}/test`, { method: 'POST' });
    setConnectionStatus('model', 'connected', summarizeModel(activeProfile || safyModelProfile));
    hideNormalizedError();
    showToast(data?.message || 'Model connection tested.', 'success');
    return data;
  } catch (error) {
    setConnectionStatus('model', 'error', normalizedError(error, 'MODEL_CONNECTION_TEST_FAILED').message);
    renderNormalizedError(error);
    throw error;
  }
}

async function activateModelProfile() {
  hideNormalizedError();
  try {
    const savedProfileId = await saveModelConfig();
    await apiRequest(`/model-profiles/${savedProfileId}/activate`, { method: 'POST' });
    const activeProfile = await refreshActiveModelProfile();
    if (activeProfile?.profile_id !== savedProfileId) {
      const activationError = normalizedError({ code: 'MODEL_PROFILE_ACTIVE_REFRESH_FAILED', message: 'MODEL_PROFILE_ACTIVE_REFRESH_FAILED' }, 'MODEL_PROFILE_ACTIVE_REFRESH_FAILED');
      throw activationError;
    }
    closeModelConfig();
    return activeProfile;
  } catch (error) {
    error.message = error.message.startsWith('MODEL_PROFILE_') ? error.message : `MODEL_PROFILE_ACTIVATE_FAILED\n${error.message}`;
    renderNormalizedError(error);
    throw error;
  }
}

function databasePortDefault(driver) {
  return driver === 'mysql' ? 3306 : driver === 'sqlite' ? 0 : driver === 'sqlserver' ? 1433 : driver === 'oracle' ? 1521 : driver === 'supabase_rpc' ? 443 : 5432;
}


function inferDatabaseDriverFromBaseUrl(baseUrl) {
  const raw = String(baseUrl || '').trim().toLowerCase();
  if (raw.includes('supabase.co') && !raw.startsWith('postgres://') && !raw.startsWith('postgresql://')) return 'supabase_rpc';
  if (raw.startsWith('postgres://') || raw.startsWith('postgresql://')) return 'postgresql';
  if (raw.startsWith('mysql://') || raw.startsWith('mariadb://')) return 'mysql';
  if (raw.startsWith('sqlite://') || raw.endsWith('.sqlite') || raw.endsWith('.db')) return 'sqlite';
  if (raw.startsWith('sqlserver://') || raw.startsWith('mssql://')) return 'sqlserver';
  if (raw.startsWith('oracle://')) return 'oracle';
  return 'postgresql';
}

function parseDatabaseBaseUrl(baseUrl, driver) {
  const fallbackPort = databasePortDefault(driver);
  const result = {
    host: 'localhost',
    port: fallbackPort,
    database: '',
    sqlite_path: '',
    base_url: baseUrl || ''
  };

  if (!baseUrl) return result;

  if (driver === 'sqlite') {
    const sqlitePath = baseUrl.replace(/^sqlite:\/\//i, '');
    result.database = sqlitePath;
    result.sqlite_path = sqlitePath;
    result.host = '';
    result.port = 0;
    return result;
  }

  try {
    const parsed = new URL(baseUrl);
    result.host = parsed.hostname || 'localhost';
    result.port = Number(parsed.port || fallbackPort);
    result.database = (parsed.pathname || '').replace(/^\//, '');
    return result;
  } catch {
    result.database = baseUrl;
    return result;
  }
}

function resetChatDraft() {
  safyChatId = null;
  hideNormalizedError();
  const empty = document.getElementById('chat-empty-state');
  const messages = document.getElementById('chat-messages');
  if (empty) empty.style.display = 'block';
  if (messages) {
    messages.style.display = 'none';
    messages.innerHTML = '';
  }
  document.querySelectorAll('.session-item.active').forEach((item) => item.classList.remove('active'));
  updateActiveCommandVisual();
}

async function deleteSession(chatId) {
  if (!chatId) return;
  const confirmed = window.confirm('Delete this session?');
  if (!confirmed) return;
  try {
    await apiRequest(`/sessions/${chatId}`, { method: 'DELETE' });
    if (safyChatId === chatId) resetChatDraft();
    await loadSessions();
  } catch (error) {
    appendChatBubble('assistant', normalizedError(error, 'Failed to delete session.').message);
  }
}

function parseSafyChatCommand(rawText) {
  const original = String(rawText || '').trim();
  const match = original.match(/^\/([a-zA-Z][\w-]*)(?:\s+|$)/);
  const name = match ? match[1].toLowerCase() : '';
  const isExecute = name === 'execute';
  const message = isExecute ? original.replace(/^\/execute(?:\s+|$)/i, '').trim() : original;
  return { original, name, message, isExecute, hasSlashCommand: Boolean(match) };
}

function isDatabaseOperationRequest(text) {
  const value = String(text || '').trim().toLowerCase();
  if (!value) return false;
  const operationPattern = /(create\s+table|alter\s+table|drop\s+table|truncate\s+table|insert\s+into|update\s+\w+|delete\s+from|select\s+.+\s+from|show\s+tables|describe\s+\w+|explain\s+select|run\s+query|execute\s+query|query\s+the|inspect\s+.+table|generate\s+sql|tạo\s+bảng|tao\s+bang|xóa\s+bảng|xoa\s+bang|sửa\s+bảng|sua\s+bang|thêm\s+dữ\s+liệu|them\s+du\s+lieu|truy\s+vấn|truy\s+van|kiểm\s+tra\s+bảng|kiem\s+tra\s+bang|liệt\s+kê\s+bảng|liet\s+ke\s+bang|hiển\s+thị|hien\s+thi|xem\s+dữ\s+liệu|xem\s+du\s+lieu|lấy\s+dữ\s+liệu|lay\s+du\s+lieu)/i;
  return operationPattern.test(value);
}

function isReadOnlyDatabaseRequest(text) {
  const value = String(text || '').trim().toLowerCase();
  if (!value) return false;
  if (/(insert\s+into|update\s+\w+|delete\s+from|create\s+table|alter\s+table|drop\s+table|truncate\s+table|tạo\s+bảng|tao\s+bang|thêm\s+dữ\s+liệu|them\s+du\s+lieu|nhập\s+dữ\s+liệu|nhap\s+du\s+lieu)/i.test(value)) return false;
  const readPattern = /(select\s+.+\s+from|show\s+(?:ra\s+)?(?:.*?)(?:data|rows|records|dữ\s+liệu|du\s+lieu)|display\s+(?:data|rows|records)|hiển\s+thị|hien\s+thi|xem\s+(?:tất\s+cả\s+)?(?:dữ\s+liệu|du\s+lieu|bảng|bang)|lấy\s+(?:tất\s+cả\s+)?(?:dữ\s+liệu|du\s+lieu)|lay\s+(?:tat\s+ca\s+)?du\s+lieu|liệt\s+kê\s+(?:dữ\s+liệu|du\s+lieu|bảng|bang)|liet\s+ke\s+(?:du\s+lieu|bang))/i;
  return readPattern.test(value);
}

function databaseCommandGuardMessage() {
  if (safyDatabaseProfile?.connection_status === 'connected' || safyDatabaseProfile?.profile_id) {
    return 'Database đã kết nối. Lệnh đọc dữ liệu như SELECT/show/xem bảng sẽ chạy trực tiếp ở chế độ read-only. Thao tác ghi/DDL vẫn cần /Execute + Check Safety.';
  }
  return 'Để thao tác database, hãy kết nối database trước rồi dùng /Execute. Chat thường không thực thi hoặc chuẩn bị tác vụ database.';
}

function isSensitiveDataRequest(text) {
  const value = String(text || '').toLowerCase();
  const secretTarget = /(api[_\s-]?key|secret|password|token|bearer|\.env|connection\s*string|dsn|credential|private\s*key|khóa|mat khau|mật khẩu)/i;
  const revealAction = /(show|print|dump|reveal|expose|read|send|give|display|hiển thị|hien thi|in ra|đọc|doc|lộ|lo|xuất|xuat)/i;
  const bypassSafety = /(bypass|ignore|disable|turn\s*off|skip|bỏ qua|bo qua|tắt|tat).*(guard|policy|safety|sql guard|redact|security|bảo mật|bao mat)/i;
  return (secretTarget.test(value) && revealAction.test(value)) || bypassSafety.test(value);
}

function currentSlashCommand(value) {
  const parsed = parseSafyChatCommand(value || '');
  if (!parsed.hasSlashCommand) return null;
  return SAFY_CHAT_COMMANDS.find(item => item.command.toLowerCase() === `/${parsed.name}`) || null;
}

function updateActiveCommandVisual() {
  const inputArea = document.querySelector('.chat-input-area');
  const input = document.getElementById('chat-input');
  if (!inputArea || !input) return;
  let chip = document.getElementById('active-command-chip');
  if (!chip) {
    chip = document.createElement('div');
    chip.id = 'active-command-chip';
    chip.className = 'active-command-chip hidden';
    inputArea.appendChild(chip);
  }
  const command = currentSlashCommand(input.value || '');
  input.classList.toggle('command-active', Boolean(command));
  if (!command) {
    chip.classList.add('hidden');
    chip.textContent = '';
    return;
  }
  chip.innerHTML = '<span class="active-command-name"></span><span class="active-command-label"></span>';
  chip.querySelector('.active-command-name').textContent = command.command;
  chip.querySelector('.active-command-label').textContent = command.title;
  chip.classList.remove('hidden');
}

function ensureSlashCommandMenu() {
  let menu = document.getElementById('slash-command-menu');
  if (menu) return menu;
  const inputArea = document.querySelector('.chat-input-area');
  if (!inputArea) return null;
  menu = document.createElement('div');
  menu.id = 'slash-command-menu';
  menu.className = 'slash-command-menu hidden';
  menu.setAttribute('role', 'listbox');
  menu.setAttribute('aria-label', 'SAFY slash commands');
  inputArea.appendChild(menu);
  return menu;
}

function matchingSlashCommands(value) {
  const query = String(value || '').trim().toLowerCase();
  if (!query.startsWith('/')) return [];
  return SAFY_CHAT_COMMANDS.filter((item) => item.command.toLowerCase().startsWith(query) || item.title.toLowerCase().includes(query.slice(1)));
}

function hideSlashCommandMenu() {
  const menu = document.getElementById('slash-command-menu');
  if (menu) menu.classList.add('hidden');
}

function showSlashCommandMenu(commands, query = '/') {
  const menu = ensureSlashCommandMenu();
  if (!menu) return;
  const items = commands.length ? commands : SAFY_CHAT_COMMANDS;
  safySlashCommandIndex = Math.max(0, Math.min(safySlashCommandIndex, items.length - 1));
  menu.innerHTML = '';
  const title = document.createElement('div');
  title.className = 'slash-command-title';
  title.textContent = 'Commands';
  menu.appendChild(title);
  items.forEach((item, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `slash-command-item ${index === safySlashCommandIndex ? 'active' : ''}`;
    button.setAttribute('role', 'option');
    button.setAttribute('aria-selected', String(index === safySlashCommandIndex));
    button.innerHTML = '<span class="slash-command-name"></span><span class="slash-command-copy"><span class="slash-command-label"></span><span class="slash-command-desc"></span></span>';
    button.querySelector('.slash-command-name').textContent = item.command;
    button.querySelector('.slash-command-label').textContent = item.title;
    button.querySelector('.slash-command-desc').textContent = item.description;
    button.addEventListener('mousedown', (event) => {
      event.preventDefault();
      applySlashCommand(item);
    });
    menu.appendChild(button);
  });
  menu.classList.remove('hidden');
  menu.querySelector('.slash-command-item.active')?.scrollIntoView({ block: 'nearest' });
}

function updateSlashCommandMenu() {
  const input = document.getElementById('chat-input');
  if (!input) return;
  const value = input.value || '';
  const beforeCursor = value.slice(0, input.selectionStart || 0);
  const shouldShow = beforeCursor.startsWith('/') && !beforeCursor.includes('\n') && beforeCursor.indexOf(' ') === -1;
  if (!shouldShow) {
    hideSlashCommandMenu();
    return;
  }
  const commands = matchingSlashCommands(beforeCursor);
  showSlashCommandMenu(commands, beforeCursor);
}

function applySlashCommand(item) {
  const input = document.getElementById('chat-input');
  if (!input || !item) return;
  input.value = item.insert;
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
  updateActiveCommandVisual();
  hideSlashCommandMenu();
}

function handleSlashCommandKeydown(event) {
  const menu = document.getElementById('slash-command-menu');
  const open = menu && !menu.classList.contains('hidden');
  if (!open) return false;
  const input = document.getElementById('chat-input');
  const commands = matchingSlashCommands(input?.value || '');
  const items = commands.length ? commands : SAFY_CHAT_COMMANDS;
  if (event.key === 'ArrowDown') {
    event.preventDefault();
    safySlashCommandIndex = (safySlashCommandIndex + 1) % items.length;
    showSlashCommandMenu(items, input?.value || '/');
    return true;
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault();
    safySlashCommandIndex = (safySlashCommandIndex - 1 + items.length) % items.length;
    showSlashCommandMenu(items, input?.value || '/');
    return true;
  }
  if (event.key === 'Enter' || event.key === 'Tab') {
    event.preventDefault();
    applySlashCommand(items[safySlashCommandIndex] || items[0]);
    return true;
  }
  if (event.key === 'Escape') {
    event.preventDefault();
    hideSlashCommandMenu();
    return true;
  }
  return false;
}

function renderDatabaseSwitchOptions() {
  const select = document.getElementById('database-switch-select');
  if (!select) return;
  const activeId = safyDatabaseProfile?.profile_id || '';
  select.innerHTML = '';
  if (!safyDatabaseProfiles.length) {
    select.insertAdjacentHTML('beforeend', '<option value="">No saved database</option>');
    return;
  }
  safyDatabaseProfiles.forEach((profile) => {
    const option = document.createElement('option');
    option.value = profile.profile_id;
    option.textContent = `${profile.display_name || profile.profile_id}${profile.active || profile.profile_id === activeId ? ' · active' : ''}`;
    option.selected = profile.profile_id === activeId;
    select.appendChild(option);
  });
}








async function switchActiveDatabase() {
  const select = document.getElementById('database-switch-select');
  const profileId = select?.value || '';
  if (!profileId) return;
  hideNormalizedError();
  try {
    const data = await apiRequest(`/database-profiles/${encodeURIComponent(profileId)}/activate`, { method: 'POST' });
    safyDatabaseProfile = { ...(safyDatabaseProfile || {}), ...data, active: true };
    await loadProfiles();
    await updateSchemaLaunchHint();
    showToast(`Switched to ${data.display_name || data.profile_id}.`, 'success');
  } catch (error) {
    renderNormalizedError(error);
  }
}

function databaseProfileIdFromDisplayName(displayName) {
  const base = String(displayName || 'main_database')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'main_database';
  return `db_${base}`;
}

function currentDatabaseProfileIdForForm(displayName) {
  const currentName = String(safyDatabaseProfile?.display_name || '').trim().toLowerCase();
  const nextName = String(displayName || '').trim().toLowerCase();
  if (safyDatabaseProfile?.profile_id && currentName && currentName === nextName) return safyDatabaseProfile.profile_id;
  return databaseProfileIdFromDisplayName(displayName);
}

function databaseFormBody() {
  const baseUrl = (document.getElementById('db-base-url')?.value || '').trim();
  const apiKey = (document.getElementById('db-api-key')?.value || '').trim();
  const username = (safyUserProfile?.username || safyRuntimeUsername || document.getElementById('db-username')?.value || '').trim();
  const displayName = (document.getElementById('db-profile-name')?.value || safyDatabaseProfile?.display_name || 'Main database').trim();
  const driver = inferDatabaseDriverFromBaseUrl(baseUrl);
  const parsed = parseDatabaseBaseUrl(baseUrl, driver);
  const keepSavedSecret = !apiKey && Boolean(safyDatabaseProfile?.secret_env || safyDatabaseProfile?.password_env || safyDatabaseProfile?.api_key_env || safyDatabaseProfile?.has_raw_secret || safyDatabaseProfile?.secret_stored);

  const body = {
    profile_id: currentDatabaseProfileIdForForm(displayName),
    display_name: displayName,
    provider: baseUrl.includes('supabase.co') ? 'supabase' : 'unified',
    driver,
    dbms: driver,
    base_url: baseUrl,
    username,
    host: parsed.host,
    port: parsed.port,
    database: parsed.database,
    sqlite_path: parsed.sqlite_path,
    ssl_mode: driver === 'supabase_rpc' ? 'api' : 'preferred',
    user_query_access_mode: 'credential_permissions',
    read_only: true,
    active: true,
    real_db_readonly: true
  };

  if (apiKey) {
    body.api_key = apiKey;
    body.raw_secret = apiKey;
    body.secret_mode = 'env';
    body.password_mode = 'env';
    body.password_env = safyDatabaseProfile?.password_env || '';
    body.api_key_env = safyDatabaseProfile?.api_key_env || '';
    body.secret_env = safyDatabaseProfile?.secret_env || '';
  } else if (keepSavedSecret) {
    body.preserve_secret = true;
    body.secret_mode = 'env';
    body.password_mode = 'env';
    body.password_env = safyDatabaseProfile?.password_env || safyDatabaseProfile?.secret_env || '';
    body.api_key_env = safyDatabaseProfile?.api_key_env || safyDatabaseProfile?.secret_env || '';
    body.secret_env = safyDatabaseProfile?.secret_env || safyDatabaseProfile?.password_env || safyDatabaseProfile?.api_key_env || '';
  } else {
    body.api_key = '';
    body.raw_secret = '';
    body.secret_mode = 'none';
    body.password_mode = 'none';
    body.password_env = '';
    body.api_key_env = '';
    body.secret_env = '';
  }

  if (driver === 'supabase_rpc') {
    body.connection_kind = 'supabase_rpc';
    body.execution_transport = 'postgrest_rpc';
    body.database = body.database && body.database.toLowerCase().startsWith('rest/v1') ? 'supabase_api' : (body.database || 'supabase_api');
    body.sql_rpc_function = safyDatabaseProfile?.sql_rpc_function || 'safy_execute_sql';
  }

  return body;
}

async function saveDatabaseConfig() {
  hideNormalizedError();
  try {
    const payload = databaseFormBody();
    if (!payload.display_name || !payload.base_url) {
      throw normalizedError({ code: 'DATABASE_FORM_INVALID', message: 'Connection Name and Base URL are required.' }, 'Connection Name and Base URL are required.');
    }
    const data = await apiRequest('/database-profiles', { method: 'POST', body: JSON.stringify(payload) });
    applyDatabaseWorkflowResult(data, `Database profile saved: ${data.profile_id || 'main_database'}.`);
    hideNormalizedError();
    closeDatabaseConfig();
    return data;
  } catch (error) {
    setConnectionStatus('database', 'error', normalizedError(error, 'DATABASE_PROFILE_SAVE_FAILED').message);
    renderNormalizedError(error);
    throw error;
  }
}

async function testDatabaseConnection() {
  hideNormalizedError();
  try {
    const payload = databaseFormBody();
    if (!payload.display_name || !payload.base_url) {
      throw normalizedError({ code: 'DATABASE_FORM_INVALID', message: 'Connection Name and Base URL are required.' }, 'Connection Name and Base URL are required.');
    }
    const data = await apiRequest('/database-profiles/test', { method: 'POST', body: JSON.stringify(payload) });
    setConnectionStatus('database', 'connected', data?.profile_preview?.display_name ? `${data.profile_preview.display_name} · Test passed` : 'Database test passed');
    showToast('Database connection test passed. Save to make it active.', 'success');
    hideNormalizedError();
    return data;
  } catch (error) {
    setConnectionStatus('database', 'error', normalizedError(error, 'DATABASE_CONNECTION_TEST_FAILED').message);
    renderNormalizedError(error);
    throw error;
  }
}



async function startChatSession() {
  try {
    const data = await apiRequest('/sessions', { method: 'POST', body: JSON.stringify({}) });
    safyChatId = data.chat_id;
    await loadSessions();
    // Clear chat UI for new session
    const empty = document.getElementById('chat-empty-state');
    const messages = document.getElementById('chat-messages');
    if (empty) empty.style.display = 'block';
    if (messages) {
      messages.style.display = 'none';
      messages.innerHTML = '';
    }
    return safyChatId;
  } catch (error) {
    renderNormalizedError(error);
    return null;
  }
}

async function loadSessions() {
  try {
    const sessions = await apiRequest('/sessions');
    const list = document.getElementById('session-list');
    if (!list) return;
    list.innerHTML = '';
    if (!sessions.length) {
      list.innerHTML = '<div class="session-item empty-state">No saved chats yet.</div>';
      return;
    }
    sessions.forEach(s => {
      const item = document.createElement('div');
      item.className = `session-item ${s.chat_id === safyChatId ? 'active' : ''}`;
      item.innerHTML = '<span class="session-icon"><svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M2 2h8v6H7l-2 2V8H2V2Z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/></svg></span><span class="session-title"></span><span class="session-time"></span><button type="button" class="session-delete-btn" title="Delete session" aria-label="Delete session">🗑</button>';
      item.addEventListener('click', () => switchSession(s.chat_id));
      item.addEventListener('contextmenu', async (event) => {
        event.preventDefault();
        await deleteSession(s.chat_id);
      });
      item.querySelector('.session-delete-btn')?.addEventListener('click', async (event) => {
        event.preventDefault();
        event.stopPropagation();
        await deleteSession(s.chat_id);
      });
      const date = s.created_at ? new Date(s.created_at) : new Date();
      const formatted = date.toLocaleDateString('en-GB') + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
      item.querySelector('.session-title').textContent = formatted;
      item.querySelector('.session-time').textContent = s.chat_id === safyChatId ? 'active' : 'saved';
      list.appendChild(item);
    });
  } catch (error) {
    console.error('Failed to load sessions', error);
  }
}


function safeParseSessionMetadata(raw) {
  if (!raw) return {};
  if (typeof raw === 'object') return raw;
  if (typeof raw !== 'string') return {};
  try { return JSON.parse(raw || '{}') || {}; } catch { return {}; }
}

function renderHistoryMessage(message) {
  const isUser = message.role === 'user';
  const metadata = safeParseSessionMetadata(message.metadata);
  const created = message.created_at ? new Date(message.created_at).toLocaleTimeString() : new Date().toLocaleTimeString();
  if (!isUser && hasStructuredQueryResult(metadata)) {
    appendChatBubble('assistant', '', { node: buildQueryResultCard(metadata), timeText: created });
    return;
  }
  const bubbleContent = isUser
    ? (message.content_redacted || '')
    : (message.content_redacted || formatAgentReply(metadata));
  appendChatBubble(isUser ? 'user' : 'assistant', bubbleContent, { timeText: created });
}

function restoreExecuteBoxFromHistory(history = []) {
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const item = history[i];
    if (item.role !== 'assistant') continue;
    const metadata = safeParseSessionMetadata(item.metadata);
    if (isDirectReadReply(metadata)) continue;
    if (metadata?.generated_sql || metadata?.sql || metadata?.query || metadata?.execute_box?.sql) {
      updateExecuteBoxFromAgent({
        ...metadata,
        generated_sql: metadata.generated_sql || metadata.sql || metadata.query || metadata.execute_box?.sql,
        summary: metadata.answer || metadata.summary || metadata.execute_box?.summary
      });
      return;
    }
  }
}

async function switchSession(chatId) {
  safyChatId = chatId;
  hideNormalizedError();
  safyCurrentCheck = null;
  const empty = document.getElementById('chat-empty-state');
  const messages = document.getElementById('chat-messages');
  if (empty) empty.style.display = 'none';
  if (messages) {
    messages.style.display = 'block';
    messages.innerHTML = '<div class="loading-history" style="padding: 20px; color: var(--text-dim);">Loading history...</div>';
  }
  try {
    const history = await apiRequest(`/sessions/${chatId}/messages`);
    if (messages) {
      messages.innerHTML = '';
      if (!history.length) {
        messages.innerHTML = '<div class="loading-history" style="padding: 20px; color: var(--text-dim);">No messages saved for this session yet.</div>';
      } else {
        history.forEach(renderHistoryMessage);
        restoreExecuteBoxFromHistory(history);
        messages.scrollTop = messages.scrollHeight;
      }
    }
    await loadSessions();
  } catch (error) {
    renderNormalizedError(error);
  }
}

async function getActiveModelProfileForChat() {
  if (safyModelProfile?.profile_id) return safyModelProfile;
  const activeProfile = await apiRequest('/model-profiles/active');
  safyModelProfile = activeProfile;
  return activeProfile;
}

async function getActiveDatabaseProfileForChat() {
  try {
    const activeProfile = await apiRequest('/database-profiles/active');
    if (activeProfile?.profile_id) {
      safyDatabaseProfile = activeProfile;
      syncDatabaseFields();
    }
    return safyDatabaseProfile;
  } catch {
    return safyDatabaseProfile;
  }
}

async function sendChatMessage() {
  if (safyChatRequestPending) return;
  hideNormalizedError();
  const input = document.getElementById('chat-input');
  const rawText = input?.value?.trim();
  if (!rawText) return;

  const command = parseSafyChatCommand(rawText);
  const readOnlyDbRequest = safyUiSettings.autoReadOnly !== false && !command.hasSlashCommand && isReadOnlyDatabaseRequest(rawText);
  if (command.isExecute && !command.message) {
    appendChatBubble('user', rawText);
    input.value = '';
    appendChatBubble('assistant', 'Please add a database task after /Execute, for example: /Execute show 5 rows from users.');
    return;
  }

  if (isSensitiveDataRequest(rawText)) {
    appendChatBubble('user', rawText);
    input.value = '';
    updateActiveCommandVisual();
    hideSlashCommandMenu();
    appendChatBubble('assistant', 'I can’t reveal secrets, API keys, tokens, credentials, connection strings, .env content, or bypass SAFY safety guards.');
    return;
  }

  if (command.hasSlashCommand && command.name === 'help') {
    appendChatBubble('user', rawText);
    input.value = '';
    updateActiveCommandVisual();
    hideSlashCommandMenu();
    appendChatBubble('assistant', 'Available commands: /Execute for guarded database tasks, /Inspect for schema inspection, /Reset_schema to delete all stored schema graphs, /Delete_schema to delete active database schema, /Cancel to cancel a pending task, /Reset to clear the chat draft.');
    return;
  }

  if (command.hasSlashCommand && command.name === 'reset') {
    input.value = '';
    updateActiveCommandVisual();
    hideSlashCommandMenu();
    resetChatDraft();
    appendChatBubble('assistant', 'Chat draft reset.');
    return;
  }

  if (command.hasSlashCommand && command.name === 'reset_schema') {
    appendChatBubble('user', rawText);
    input.value = '';
    updateActiveCommandVisual();
    hideSlashCommandMenu();
    await resetAllSchemaGraphs();
    appendChatBubble('assistant', 'All stored schema graphs were deleted.');
    return;
  }

  if (command.hasSlashCommand && command.name === 'delete_schema') {
    appendChatBubble('user', rawText);
    input.value = '';
    updateActiveCommandVisual();
    hideSlashCommandMenu();
    await deleteActiveSchemaGraph();
    appendChatBubble('assistant', 'Active database schema graph was deleted.');
    return;
  }

  if (command.hasSlashCommand && !['execute', 'inspect', 'help', 'cancel', 'reset', 'reset_schema', 'delete_schema'].includes(command.name)) {
    appendChatBubble('user', rawText);
    input.value = '';
    updateActiveCommandVisual();
    hideSlashCommandMenu();
    appendChatBubble('assistant', `Unknown command /${command.name}. Type / to choose a supported SAFY command.`);
    return;
  }

  if (!command.isExecute && !readOnlyDbRequest && isDatabaseOperationRequest(rawText)) {
    appendChatBubble('user', rawText);
    input.value = '';
    updateActiveCommandVisual();
    hideSlashCommandMenu();
    await getActiveDatabaseProfileForChat();
    appendChatBubble('assistant', databaseCommandGuardMessage());
    return;
  }

  if (!safyChatId) {
    await startChatSession();
    if (!safyChatId) {
      appendChatBubble('assistant', 'Could not create a chat session. Please check the backend and try again.');
      return;
    }
  }

  appendChatBubble('user', rawText);
  input.value = '';
  hideSlashCommandMenu();

  setChatRequestPending(true);
  const loadingIndicator = appendChatLoadingIndicator();
  try {
    const activeModelProfile = await getActiveModelProfileForChat();
    const modelProfileId = activeModelProfile?.profile_id;
    if (!modelProfileId) {
      throw normalizedError({ code: 'MODEL_PROFILE_NOT_ACTIVATED', message: 'MODEL_PROFILE_NOT_ACTIVATED' }, 'MODEL_PROFILE_NOT_ACTIVATED');
    }

    const shouldUseDatabaseRuntime = command.isExecute || readOnlyDbRequest;
    const activeDatabaseProfile = shouldUseDatabaseRuntime ? await getActiveDatabaseProfileForChat() : null;
    if (shouldUseDatabaseRuntime && !activeDatabaseProfile?.profile_id) {
      appendChatBubble('assistant', 'Chưa có database thật đang active. Hãy Save/Test database trước rồi chạy lại.');
      return;
    }

    const chatPayload = {
      chat_id: safyChatId,
      message: command.isExecute ? command.message : rawText,
      model_profile_id: modelProfileId,
      options: {
        command: command.isExecute ? 'execute' : 'chat',
        read_only_direct: readOnlyDbRequest,
        streaming: Boolean(safyUiSettings.streaming),
        username: safyUserProfile?.username || safyRuntimeUsername || undefined,
        context_sources: contextSourcesForRequest()
      }
    };
    if (shouldUseDatabaseRuntime) {
      chatPayload.target = 'connected_database';
      chatPayload.database_profile_id = activeDatabaseProfile.profile_id;
      chatPayload.auto_execute = true;
    }

    const response = await fetch(`${SAFY_API_BASE}/agent/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(chatPayload)
    });

    const body = await response.json().catch(() => null);
    if (!response.ok) {
      const error = normalizedError({
        code: `HTTP_${response.status}`,
        message: body?.error?.message || 'Chat request failed.'
      }, 'Chat request failed.');
      appendChatBubble('assistant', error.message);
      return;
    }

    if (!body || body.success !== true) {
      const error = normalizedError({
        code: body?.error?.code || 'CHAT_REQUEST_FAILED',
        message: body?.error?.message || 'Chat request failed.'
      }, 'Chat request failed.');
      appendChatBubble('assistant', error.message);
      return;
    }

    const reply = body.data;
    if (isDirectReadReply(reply)) {
      resetExecuteRuntimePanel({ clearSql: true });
    }
    if (!appendQueryResultToChat(reply)) {
      appendChatBubble('assistant', formatAgentReply(reply), { stream: safyUiSettings.streaming });
    }
    if (command.isExecute && !isDirectReadReply(reply)) updateExecuteBoxFromAgent(reply);
    if (safyContextSources.length) clearContextSources();
    await loadSessions();
  } catch (error) {
    appendChatBubble('assistant', normalizedError(error, 'Chat request failed.').message);
  } finally {
    removeChatLoadingIndicator(loadingIndicator);
    setChatRequestPending(false);
  }
}

function renderSafetyReport(data) {
  hideNormalizedError();
  const status = document.getElementById('execute-check-status');
  const target = document.getElementById('execute-target-used');
  if (status) {
    const count = Number(data.statement_count || 1);
    const suffix = count > 1 ? ` (${count} statements)` : '';
    const label = data.check_passed === true
      ? (data.safety_status || 'passed')
      : data.check_passed === false
        ? (data.safety_status || 'blocked')
        : (data.safety_status || data.decision || 'Checked');
    status.textContent = `${label}${suffix}`;
  }
  if (target) target.textContent = data.target || 'Active database';
}

function updateExecuteBoxFromAgent(reply = {}) {
  const sql = reply.generated_sql || reply.sql || reply.query || reply.sql_preview || '';
  const hasStructuredExecutePayload = Boolean(
    sql ||
    reply.check_id ||
    reply.sql_hash ||
    reply.generated_query ||
    reply.result_preview ||
    reply.execution_result ||
    reply.safety_status ||
    reply.decision ||
    reply.target
  );
  if (!hasStructuredExecutePayload) return;

  if (sql) {
    resetExecuteRuntimePanel();
    const input = document.getElementById('user-query-input');
    if (input) input.value = redactForDisplay(sql);
  }
  const summary = document.getElementById('execution-summary');
  if (summary) summary.textContent = redactForDisplay(reply.summary || reply.message || 'Assistant response received. Review generated SQL before execution.');
}


function currentQueryTarget() {
  return 'connected_database';
}

async function loadSandboxes() {
  const list = document.getElementById('sandbox-list');
  const select = document.getElementById('sandbox-select');
  if (!list && !select) return;
  try {
    const sandboxes = await apiRequest('/sandboxes');
    if (select) {
      select.innerHTML = '<option value="">Default sandbox</option>';
      sandboxes.forEach((box) => select.insertAdjacentHTML('beforeend', `<option value="${box.id}">${box.name || box.id} - ${box.status}</option>`));
    }
    if (list) {
      list.textContent = sandboxes.length ? sandboxes.map((box) => `${box.id} | ${box.engine} | ${box.status} | read_only=${box.read_only}`).join('\n') : 'No sandboxes yet.';
    }
    safySandboxId = select?.value || sandboxes[0]?.id || null;
  } catch (error) {
    renderNormalizedError(error);
  }
}

async function createSandbox() {
  hideNormalizedError();
  const body = {
    id: document.getElementById('sandbox-id')?.value || undefined,
    name: document.getElementById('sandbox-name')?.value || 'Local sandbox',
    engine: document.getElementById('sandbox-engine')?.value || 'postgresql',
    source_kind: document.getElementById('sandbox-source-kind')?.value || 'public_dataset',
    source_ref: document.getElementById('sandbox-source-ref')?.value || 'pagila',
    read_only: true,
    network_disabled: true
  };
  try {
    const box = await apiRequest('/sandboxes', { method: 'POST', body: JSON.stringify(body) });
    safySandboxId = box.id;
    await loadSandboxes();
  } catch (error) {
    renderNormalizedError(error);
  }
}

async function sandboxAction(action) {
  hideNormalizedError();
  const id = document.getElementById('sandbox-select')?.value || safySandboxId || 'sandbox_default';
  try {
    const path = action === 'delete' ? `/sandboxes/${id}` : `/sandboxes/${id}/${action}`;
    await apiRequest(path, { method: action === 'delete' ? 'DELETE' : 'POST', body: action === 'restore' ? JSON.stringify({ source_kind: 'public_dataset' }) : undefined });
    await loadSandboxes();
  } catch (error) {
    renderNormalizedError(error);
  }
}


async function checkQuery() {
  hideNormalizedError();
  const sql = document.getElementById('user-query-input')?.value || '';
  try {
    safyCurrentCheck = await apiRequest('/query/check', {
      method: 'POST',
      body: JSON.stringify({
        sql,
        chat_id: safyChatId || null,
        session_id: safyChatId || null,
        target: currentQueryTarget(),
        sandbox_id: safySandboxId || (safyDatabaseProfile?.profile_id ? `db_${safyDatabaseProfile.profile_id}` : null),
        database_profile_id: safyDatabaseProfile?.profile_id || null,
        user_query_access_mode: safyDatabaseProfile?.user_query_access_mode || document.getElementById('db-user-query-access-mode')?.value || 'credential_permissions',
        real_db_mode: Boolean(safyDatabaseProfile?.real_db_readonly)
      })
    });
    renderSafetyReport(safyCurrentCheck);
    const execute = document.getElementById('execute-query-btn');
    const canExecute = Boolean(safyCurrentCheck?.allowed_to_attempt)
      && safyCurrentCheck?.safety_status !== 'blocked'
      && !String(safyCurrentCheck?.decision || '').startsWith('BLOCK');
    if (canExecute) {
      execute?.removeAttribute('disabled');
      execute?.classList.remove('disabled');
    } else {
      execute?.setAttribute('disabled', 'disabled');
      execute?.classList.add('disabled');
    }
  } catch (error) {
    renderNormalizedError(error);
  }
}

function renderExecutionResult(data) {
  hideNormalizedError();
  const status = document.getElementById('execute-run-status');
  const rows = document.getElementById('execute-row-count');
  const summary = document.getElementById('execution-summary');
  const metadata = data?.metadata || {};
  const rowCount = data.row_count ?? metadata.row_count ?? data.rows?.length ?? data.result?.rows?.length ?? 0;
  const statementType = String(metadata.statement_type || data.statement_type || 'SQL').toUpperCase();
  const driver = data.driver || metadata.driver || safyDatabaseProfile?.driver || 'database';
  const transport = metadata.execution_transport || metadata.connection_kind || safyDatabaseProfile?.execution_transport || safyDatabaseProfile?.connection_kind || 'database';
  const baseSuccessMessage = data.success_message || data.summary || `Execution succeeded. ${statementType} completed on ${driver} via ${transport}. Row count: ${rowCount}.`;
  const successMessage = data.schema_refresh_required
    ? `${baseSuccessMessage} Schema changed; the cached Schema Graph was invalidated and should be refreshed.`
    : baseSuccessMessage;
  if (status) status.textContent = data.status || 'Executed successfully';
  if (rows) rows.textContent = String(rowCount);
  if (summary) summary.textContent = redactForDisplay(successMessage);
  showToast(successMessage, 'success');
}


async function executeQuery(userDecision = 'yes') {
  hideNormalizedError();
  if (!safyCurrentCheck) {
    renderNormalizedError({ code: 'QUERY_CHECK_REQUIRED', message: 'Run safety check before execute.', details: {} });
    return;
  }
  try {
    const data = await apiRequest('/query/execute', {
      method: 'POST',
      body: JSON.stringify({
        check_id: safyCurrentCheck.check_id,
        sql_hash: safyCurrentCheck.sql_hash,
        chat_id: safyChatId || null,
        session_id: safyChatId || null,
        target: safyCurrentCheck.target || 'connected_database',
        sandbox_id: safyCurrentCheck.sandbox_id || null,
        database_profile_id: safyCurrentCheck.database_profile_id || safyDatabaseProfile?.profile_id || null,
        user_decision: userDecision,
        confirmation_code: document.getElementById('confirmation-code-input')?.value || null,
        real_db_mode: Boolean(safyDatabaseProfile?.real_db_readonly)
      })
    });
    renderExecutionResult(data);
    appendQueryResultToChat(data, safyCurrentCheck?.normalized_sql || document.getElementById('user-query-input')?.value || '');
    await loadSessions();
  } catch (error) {
    renderNormalizedError(error);
  }
}

async function cancelQueryExecution() {
  return executeQuery('no');
}

async function runRecoveryScan() {
  try {
    const result = await apiRequest('/recovery/scan', { method: 'POST' });
    alert(`Recovery scan complete. Stale locks released: ${result.stale_locks_found}`);
  } catch (error) {
    renderNormalizedError(error);
  }
}

function initSafyUI() {
  initSettingsPanel();
  document.getElementById('sign-out-btn')?.addEventListener('click', handleSafyLogout);
  document.getElementById('attach-context-btn')?.addEventListener('click', chooseContextFiles);
  document.getElementById('attach-url-btn')?.addEventListener('click', openContextUrlModal);
  document.getElementById('context-url-close-btn')?.addEventListener('click', closeContextUrlModal);
  document.getElementById('context-url-backdrop')?.addEventListener('click', closeContextUrlModal);
  document.getElementById('context-url-add-btn')?.addEventListener('click', addContextUrl);
  document.getElementById('context-url-input')?.addEventListener('keydown', (event) => { if (event.key === 'Enter') { event.preventDefault(); addContextUrl(); } });
  document.getElementById('context-file-input')?.addEventListener('change', (event) => addContextFiles(event.target.files));
  document.getElementById('model-connect-btn')?.addEventListener('click', openModelConfig);
  document.getElementById('model-cancel-btn')?.addEventListener('click', closeModelConfig);
  document.getElementById('model-save-btn')?.addEventListener('click', saveModelConfig);
  document.getElementById('model-test-btn')?.addEventListener('click', testModelConnection);
  document.getElementById('database-connect-btn')?.addEventListener('click', openDatabaseConfig);
  document.getElementById('database-cancel-btn')?.addEventListener('click', closeDatabaseConfig);
  document.getElementById('database-save-btn')?.addEventListener('click', saveDatabaseConfig);
  document.getElementById('database-test-btn')?.addEventListener('click', testDatabaseConnection);
  document.getElementById('database-switch-btn')?.addEventListener('click', switchActiveDatabase);
  document.getElementById('schema-open-btn')?.addEventListener('click', openSchemaGraphPage);
  document.getElementById('toggle-left-sidebar-btn')?.addEventListener('click', toggleLeftSidebar);
  document.getElementById('toggle-right-sidebar-btn')?.addEventListener('click', toggleRightSidebar);
  document.getElementById('send-message-btn')?.addEventListener('click', sendChatMessage);
  document.getElementById('new-chat-btn')?.addEventListener('click', resetChatDraft);
  
  // Recovery trigger (attached to logo)
  document.querySelector('.logo-icon')?.addEventListener('dblclick', runRecoveryScan);

  const chatInput = document.getElementById('chat-input');
  chatInput?.addEventListener('input', () => {
    safySlashCommandIndex = 0;
    updateSlashCommandMenu();
    updateActiveCommandVisual();
  });
  chatInput?.addEventListener('keydown', event => {
    if (handleSlashCommandKeydown(event)) return;
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') sendChatMessage();
  });
  document.addEventListener('click', (event) => {
    if (!event.target.closest?.('.chat-input-area')) hideSlashCommandMenu();
  });
  document.getElementById('check-query-btn')?.addEventListener('click', checkQuery);
  document.getElementById('execute-query-btn')?.addEventListener('click', () => executeQuery('yes'));
  loadProfiles();
  loadSessions();
  updateSchemaLaunchHint();
  renderContextSources();
}

window.initSafyUI = initSafyUI;
window.openSchemaGraphPage = openSchemaGraphPage;
window.startChatSession = startChatSession;
window.resetChatDraft = resetChatDraft;
window.deleteSession = deleteSession;
window.sendChatMessage = sendChatMessage;
window.openModelConfig = openModelConfig;
window.closeModelConfig = closeModelConfig;
window.saveModelConfig = saveModelConfig;
window.testModelConnection = testModelConnection;
window.activateModelProfile = activateModelProfile;
window.openDatabaseConfig = openDatabaseConfig;
window.closeDatabaseConfig = closeDatabaseConfig;
window.saveDatabaseConfig = saveDatabaseConfig;
window.testDatabaseConnection = testDatabaseConnection;
window.switchActiveDatabase = switchActiveDatabase;
window.toggleLeftSidebar = toggleLeftSidebar;
window.toggleRightSidebar = toggleRightSidebar;
window.checkQuery = checkQuery;
window.executeQuery = executeQuery;
window.cancelQueryExecution = cancelQueryExecution;
window.renderSafetyReport = renderSafetyReport;
window.renderExecutionResult = renderExecutionResult;
window.renderNormalizedError = renderNormalizedError;
window.setConnectionStatus = setConnectionStatus;
window.loadProfiles = loadProfiles;
window.switchSession = switchSession;

document.addEventListener('DOMContentLoaded', initSafyDashboard);
