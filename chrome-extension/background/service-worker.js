// Background service worker
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'SYNC_CONNECTIONS') {
    handleSyncToBackend(msg.connections).then(sendResponse);
    return true; // async
  }
  if (msg.type === 'GET_MESSAGE_QUEUE') {
    getMessageQueue().then(sendResponse);
    return true;
  }
  if (msg.type === 'UPDATE_STATS') {
    chrome.storage.local.set(msg.data);
    return false;
  }
});

async function handleSyncToBackend(connections) {
  try {
    const data = await chrome.storage.local.get(['backendUrl']);
    const url = data.backendUrl;
    if (!url) return { success: false, error: 'No backend URL configured' };

    const resp = await fetch(url + '/api/li-search/connections/push', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ connections })
    });

    if (resp.ok) {
      const result = await resp.json();
      const now = new Date().toLocaleString();
      await chrome.storage.local.set({
        connCount: String(result.stored || connections.length),
        lastSync: now
      });
      return { success: true, stored: result.stored || connections.length };
    } else {
      return { success: false, error: 'Server returned ' + resp.status };
    }
  } catch (e) {
    return { success: false, error: e.message };
  }
}

async function getMessageQueue() {
  try {
    const data = await chrome.storage.local.get(['backendUrl']);
    const url = data.backendUrl;
    if (!url) return { recipients: [], message: '' };

    const resp = await fetch(url + '/api/li-search/message/queue');
    if (resp.ok) {
      return await resp.json();
    }
    return { recipients: [], message: '' };
  } catch (e) {
    return { recipients: [], message: '' };
  }
}
