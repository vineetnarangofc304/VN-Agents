/**
 * LinkedLeads.ai — Background Service Worker
 * Handles: Auth, LinkedIn session detection, task polling, result reporting
 */

const POLL_INTERVAL_MS = 30000; // 30 seconds
const DAILY_LIMIT_DEFAULT = 20;

// ============ State ============
let state = {
  apiUrl: '',
  jwt: '',
  user: null,
  linkedInSession: null, // { li_at, csrfToken, active }
  isProcessing: false,
  todayStats: { connects: 0, messages: 0, visits: 0 },
  settings: {
    dailyLimit: DAILY_LIMIT_DEFAULT,
    minDelay: 15, // seconds between actions
    maxDelay: 45,
    workingHoursOnly: true,
    workStart: 9,
    workEnd: 18,
    enabled: true,
  }
};

// ============ Storage Helpers ============
async function loadState() {
  const data = await chrome.storage.local.get(['ll_apiUrl', 'll_jwt', 'll_user', 'll_settings', 'll_todayStats', 'll_todayDate']);
  state.apiUrl = data.ll_apiUrl || '';
  state.jwt = data.ll_jwt || '';
  state.user = data.ll_user || null;
  if (data.ll_settings) state.settings = { ...state.settings, ...data.ll_settings };
  
  // Reset daily stats if new day
  const today = new Date().toISOString().split('T')[0];
  if (data.ll_todayDate === today && data.ll_todayStats) {
    state.todayStats = data.ll_todayStats;
  } else {
    state.todayStats = { connects: 0, messages: 0, visits: 0 };
    await chrome.storage.local.set({ ll_todayDate: today, ll_todayStats: state.todayStats });
  }
}

async function saveState(partial) {
  const map = {};
  if (partial.apiUrl !== undefined) { state.apiUrl = partial.apiUrl; map.ll_apiUrl = partial.apiUrl; }
  if (partial.jwt !== undefined) { state.jwt = partial.jwt; map.ll_jwt = partial.jwt; }
  if (partial.user !== undefined) { state.user = partial.user; map.ll_user = partial.user; }
  if (partial.settings !== undefined) { state.settings = { ...state.settings, ...partial.settings }; map.ll_settings = state.settings; }
  if (partial.todayStats !== undefined) { state.todayStats = partial.todayStats; map.ll_todayStats = partial.todayStats; }
  await chrome.storage.local.set(map);
}

// ============ API Helper ============
async function apiCall(endpoint, options = {}) {
  if (!state.apiUrl || !state.jwt) return null;
  const url = `${state.apiUrl}/api/ext${endpoint}`;
  const resp = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${state.jwt}`,
      ...(options.headers || {}),
    },
  });
  if (resp.status === 401) {
    // Token expired
    await saveState({ jwt: '', user: null });
    broadcastToPopup({ type: 'AUTH_EXPIRED' });
    return null;
  }
  if (!resp.ok) {
    const err = await resp.text();
    console.error(`[LinkedLeads] API ${endpoint} failed: ${resp.status}`, err);
    return null;
  }
  return resp.json();
}

// ============ LinkedIn Session Detection ============
async function detectLinkedInSession() {
  try {
    const liAt = await chrome.cookies.get({ url: 'https://www.linkedin.com', name: 'li_at' });
    const jsessionId = await chrome.cookies.get({ url: 'https://www.linkedin.com', name: 'JSESSIONID' });
    
    if (liAt && jsessionId) {
      const csrfToken = jsessionId.value.replace(/"/g, '');
      state.linkedInSession = {
        li_at: liAt.value,
        csrfToken: csrfToken,
        active: true,
        detectedAt: Date.now(),
      };
      // Report session to backend
      apiCall('/session', {
        method: 'POST',
        body: JSON.stringify({ active: true, li_at_prefix: liAt.value.substring(0, 8) }),
      });
      return true;
    }
  } catch (e) {
    console.error('[LinkedLeads] Session detection error:', e);
  }
  state.linkedInSession = { active: false };
  return false;
}

// ============ Working Hours Check ============
function isWithinWorkingHours() {
  if (!state.settings.workingHoursOnly) return true;
  const now = new Date();
  const hour = now.getHours();
  return hour >= state.settings.workStart && hour < state.settings.workEnd;
}

// ============ Daily Limit Check ============
function hasReachedDailyLimit() {
  const total = state.todayStats.connects + state.todayStats.messages;
  return total >= state.settings.dailyLimit;
}

// ============ Task Polling ============
async function pollAndExecuteTasks() {
  if (!state.jwt || !state.settings.enabled || state.isProcessing) return;
  if (!state.linkedInSession?.active) {
    await detectLinkedInSession();
    if (!state.linkedInSession?.active) return;
  }
  if (!isWithinWorkingHours()) return;
  if (hasReachedDailyLimit()) return;

  state.isProcessing = true;
  try {
    const data = await apiCall('/tasks/next');
    if (!data || !data.task) {
      state.isProcessing = false;
      return;
    }

    const task = data.task;
    broadcastToPopup({ type: 'TASK_EXECUTING', task });

    // Send task to content script on LinkedIn tab
    const result = await executeOnLinkedIn(task);

    // Report result
    await apiCall(`/tasks/${task.task_id}/result`, {
      method: 'POST',
      body: JSON.stringify(result),
    });

    // Update stats
    if (result.success) {
      if (task.type === 'connect') state.todayStats.connects++;
      if (task.type === 'message') state.todayStats.messages++;
      if (task.type === 'visit') state.todayStats.visits++;
      await saveState({ todayStats: state.todayStats });
    }

    broadcastToPopup({ type: 'TASK_COMPLETED', task, result });
  } catch (e) {
    console.error('[LinkedLeads] Task execution error:', e);
  }
  state.isProcessing = false;
}

// ============ Execute on LinkedIn Tab ============
async function executeOnLinkedIn(task) {
  // Find a LinkedIn tab
  const tabs = await chrome.tabs.query({ url: 'https://www.linkedin.com/*' });
  if (tabs.length === 0) {
    return { success: false, error: 'No LinkedIn tab open. Please open LinkedIn in a tab.' };
  }

  const tab = tabs[0];
  
  // Add random human-like delay
  const delay = (state.settings.minDelay + Math.random() * (state.settings.maxDelay - state.settings.minDelay)) * 1000;
  await new Promise(r => setTimeout(r, delay));

  try {
    const response = await chrome.tabs.sendMessage(tab.id, {
      type: 'EXECUTE_TASK',
      task: task,
      csrfToken: state.linkedInSession.csrfToken,
    });
    return response || { success: false, error: 'No response from content script' };
  } catch (e) {
    return { success: false, error: `Content script error: ${e.message}` };
  }
}

// ============ Broadcast to Popup ============
function broadcastToPopup(msg) {
  chrome.runtime.sendMessage(msg).catch(() => {});
}

// ============ Message Handler ============
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handleMessage(msg, sender).then(sendResponse);
  return true; // async response
});

async function handleMessage(msg) {
  switch (msg.type) {
    case 'LOGIN': {
      try {
        const resp = await fetch(`${msg.apiUrl}/api/crm-auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: msg.email, password: msg.password }),
        });
        const data = await resp.json();
        if (!resp.ok) return { success: false, error: data.detail || 'Login failed' };
        
        // CRM login returns 'token' field
        const jwt = data.access_token || data.token;
        if (!jwt) return { success: false, error: 'No token in response' };
        
        await saveState({
          apiUrl: msg.apiUrl,
          jwt: jwt,
          user: data.user || { name: data.name, email: data.email, role: data.role, id: data.id },
        });
        // Start polling
        startPolling();
        await detectLinkedInSession();
        return { success: true, user: data.user };
      } catch (e) {
        return { success: false, error: e.message };
      }
    }

    case 'LOGOUT': {
      await saveState({ jwt: '', user: null });
      stopPolling();
      return { success: true };
    }

    case 'GET_STATE': {
      await detectLinkedInSession();
      return {
        loggedIn: !!state.jwt,
        user: state.user,
        linkedInActive: state.linkedInSession?.active || false,
        todayStats: state.todayStats,
        settings: state.settings,
        isProcessing: state.isProcessing,
        apiUrl: state.apiUrl,
      };
    }

    case 'UPDATE_SETTINGS': {
      await saveState({ settings: msg.settings });
      return { success: true };
    }

    case 'FORCE_POLL': {
      pollAndExecuteTasks();
      return { success: true };
    }

    case 'GET_CAMPAIGNS': {
      const data = await apiCall('/campaigns');
      return data || { campaigns: [] };
    }

    case 'LINKEDIN_SESSION_DETECTED': {
      // Content script detected we're on LinkedIn
      await detectLinkedInSession();
      return { active: state.linkedInSession?.active };
    }

    default:
      return { error: 'Unknown message type' };
  }
}

// ============ Polling via Alarms (MV3) ============
function startPolling() {
  chrome.alarms.create('linkedleads-poll', { periodInMinutes: 0.5 }); // 30 sec
}

function stopPolling() {
  chrome.alarms.clear('linkedleads-poll');
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'linkedleads-poll') {
    pollAndExecuteTasks();
  }
});

// ============ Init ============
loadState().then(() => {
  if (state.jwt) {
    startPolling();
    detectLinkedInSession();
  }
});

// Badge updates
setInterval(async () => {
  if (state.jwt && state.linkedInSession?.active && state.settings.enabled) {
    const total = state.todayStats.connects + state.todayStats.messages;
    chrome.action.setBadgeText({ text: total > 0 ? String(total) : '' });
    chrome.action.setBadgeBackgroundColor({ color: '#2563EB' });
  } else {
    chrome.action.setBadgeText({ text: '' });
  }
}, 5000);
