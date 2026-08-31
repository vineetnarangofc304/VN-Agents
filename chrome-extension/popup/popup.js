/**
 * LinkedLeads.ai — Popup Controller
 */
document.addEventListener('DOMContentLoaded', init);

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let activities = [];

async function init() {
  // Load saved server URL
  const data = await chrome.storage.local.get(['ll_apiUrl']);
  if (data.ll_apiUrl) {
    $('#server-url').value = data.ll_apiUrl;
  }

  // Check current state
  const state = await sendMessage({ type: 'GET_STATE' });
  if (state && state.loggedIn) {
    showDashboard(state);
  } else {
    showLogin();
  }

  // Event listeners
  $('#login-form').addEventListener('submit', handleLogin);
  $('#logout-btn').addEventListener('click', handleLogout);
  $('#settings-toggle').addEventListener('click', showSettings);
  $('#settings-back').addEventListener('click', () => showView('dashboard-view'));
  $('#save-settings').addEventListener('click', handleSaveSettings);
  $('#auto-toggle').addEventListener('change', handleAutoToggle);

  // Listen for background messages
  chrome.runtime.onMessage.addListener(handleBackgroundMsg);
}

// ============ Navigation ============
function showView(viewId) {
  $$('.view').forEach(v => v.classList.add('hidden'));
  $(`#${viewId}`).classList.remove('hidden');
}

function showLogin() {
  showView('login-view');
}

function showDashboard(state) {
  showView('dashboard-view');
  updateDashboard(state);
}

function showSettings() {
  showView('settings-view');
  chrome.storage.local.get(['ll_settings']).then(data => {
    const s = data.ll_settings || {};
    $('#set-daily-limit').value = s.dailyLimit || 20;
    $('#set-min-delay').value = s.minDelay || 15;
    $('#set-max-delay').value = s.maxDelay || 45;
    $('#set-working-hours').checked = s.workingHoursOnly !== false;
    $('#set-work-start').value = s.workStart || 9;
    $('#set-work-end').value = s.workEnd || 18;
  });
}

// ============ Dashboard Updates ============
function updateDashboard(state) {
  if (!state) return;

  // User info
  const user = state.user || {};
  $('#user-name').textContent = user.name || 'User';
  $('#user-email').textContent = user.email || '';
  $('#user-avatar').textContent = (user.name || 'U')[0].toUpperCase();

  // LinkedIn session
  const sessionCard = $('#session-card');
  if (state.linkedInActive) {
    sessionCard.className = 'session-card connected';
    $('#session-label').textContent = 'LinkedIn Connected';
    $('#session-detail').textContent = 'Session active — ready to execute tasks';
  } else {
    sessionCard.className = 'session-card disconnected';
    $('#session-label').textContent = 'LinkedIn Not Detected';
    $('#session-detail').textContent = 'Open linkedin.com and log in to start';
  }

  // Stats
  const stats = state.todayStats || {};
  $('#stat-connects').textContent = stats.connects || 0;
  $('#stat-messages').textContent = stats.messages || 0;
  $('#stat-visits').textContent = stats.visits || 0;
  const total = (stats.connects || 0) + (stats.messages || 0);
  const limit = state.settings?.dailyLimit || 20;
  $('#stat-limit').textContent = `${total}/${limit}`;

  // Status pill
  const pill = $('#status-pill');
  if (!state.settings?.enabled) {
    pill.className = 'status-pill paused';
    pill.querySelector('.status-text').textContent = 'Paused';
  } else if (state.linkedInActive) {
    pill.className = 'status-pill active';
    pill.querySelector('.status-text').textContent = 'Active';
  } else {
    pill.className = 'status-pill';
    pill.querySelector('.status-text').textContent = 'Waiting';
  }

  // Toggle
  $('#auto-toggle').checked = state.settings?.enabled !== false;

  // CRM link
  if (state.apiUrl) {
    const crmUrl = state.apiUrl.replace(/\/api$/, '') + '/linkedin-crm';
    $('#open-crm-btn').href = crmUrl;
  }
}

// ============ Handlers ============
async function handleLogin(e) {
  e.preventDefault();
  const btn = $('#login-btn');
  const errEl = $('#login-error');
  errEl.classList.add('hidden');
  btn.disabled = true;
  btn.querySelector('span').textContent = 'Signing in...';

  const apiUrl = $('#server-url').value.trim().replace(/\/$/, '');
  const email = $('#login-email').value.trim();
  const password = $('#login-password').value;

  const result = await sendMessage({
    type: 'LOGIN',
    apiUrl,
    email,
    password,
  });

  btn.disabled = false;
  btn.querySelector('span').textContent = 'Sign In';

  if (result && result.success) {
    const state = await sendMessage({ type: 'GET_STATE' });
    showDashboard(state);
  } else {
    errEl.textContent = result?.error || 'Login failed. Check your credentials.';
    errEl.classList.remove('hidden');
  }
}

async function handleLogout() {
  await sendMessage({ type: 'LOGOUT' });
  showLogin();
}

async function handleAutoToggle() {
  const enabled = $('#auto-toggle').checked;
  await sendMessage({ type: 'UPDATE_SETTINGS', settings: { enabled } });
  const state = await sendMessage({ type: 'GET_STATE' });
  updateDashboard(state);
}

async function handleSaveSettings() {
  const settings = {
    dailyLimit: parseInt($('#set-daily-limit').value) || 20,
    minDelay: parseInt($('#set-min-delay').value) || 15,
    maxDelay: parseInt($('#set-max-delay').value) || 45,
    workingHoursOnly: $('#set-working-hours').checked,
    workStart: parseInt($('#set-work-start').value) || 9,
    workEnd: parseInt($('#set-work-end').value) || 18,
  };
  await sendMessage({ type: 'UPDATE_SETTINGS', settings });
  showView('dashboard-view');
  const state = await sendMessage({ type: 'GET_STATE' });
  updateDashboard(state);
}

// ============ Activity Feed ============
function addActivity(type, text, success) {
  activities.unshift({ type, text, success, time: new Date() });
  if (activities.length > 20) activities.pop();
  renderActivities();
}

function renderActivities() {
  const list = $('#activity-list');
  if (activities.length === 0) {
    list.innerHTML = '<div class="activity-empty">No activity yet. Campaigns will execute automatically when LinkedIn is open.</div>';
    return;
  }
  list.innerHTML = activities.map(a => {
    const dotClass = a.success ? 'success' : (a.success === false ? 'fail' : 'pending');
    const timeStr = a.time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return `
      <div class="activity-item">
        <div class="activity-dot ${dotClass}"></div>
        <span class="activity-text">${escapeHtml(a.text)}</span>
        <span class="activity-time">${timeStr}</span>
      </div>
    `;
  }).join('');
}

// ============ Background Message Handler ============
function handleBackgroundMsg(msg) {
  if (msg.type === 'TASK_EXECUTING') {
    addActivity(msg.task?.type, `Executing: ${msg.task?.type} → ${msg.task?.target_public_id || '...'}`, null);
  }
  if (msg.type === 'TASK_COMPLETED') {
    const label = msg.result?.success ? 'Done' : 'Failed';
    addActivity(msg.task?.type, `${label}: ${msg.task?.type} → ${msg.task?.target_public_id || '...'}`, msg.result?.success);
    // Refresh stats
    sendMessage({ type: 'GET_STATE' }).then(updateDashboard);
  }
  if (msg.type === 'AUTH_EXPIRED') {
    showLogin();
  }
}

// ============ Helpers ============
function sendMessage(msg) {
  return new Promise(resolve => {
    chrome.runtime.sendMessage(msg, (resp) => {
      if (chrome.runtime.lastError) {
        console.warn('[Popup]', chrome.runtime.lastError.message);
        resolve(null);
      } else {
        resolve(resp);
      }
    });
  });
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}
