// Popup script
document.addEventListener('DOMContentLoaded', async () => {
  const data = await chrome.storage.local.get(['backendUrl', 'connCount', 'msgCount', 'lastSync']);

  document.getElementById('backendUrl').value = data.backendUrl || '';
  document.getElementById('connCount').textContent = data.connCount || '0';
  document.getElementById('msgCount').textContent = data.msgCount || '0';
  document.getElementById('lastSync').textContent = data.lastSync || 'Never';

  document.getElementById('saveUrl').addEventListener('click', async () => {
    const url = document.getElementById('backendUrl').value.trim().replace(/\/$/, '');
    if (!url) return;
    await chrome.storage.local.set({ backendUrl: url });

    // Test connection
    const status = document.getElementById('urlStatus');
    try {
      const resp = await fetch(url + '/api/health', { method: 'GET', mode: 'cors' });
      if (resp.ok) {
        status.className = 'status status-ok';
        status.textContent = 'Connected!';
      } else {
        status.className = 'status status-err';
        status.textContent = 'Server returned ' + resp.status;
      }
    } catch (e) {
      status.className = 'status status-err';
      status.textContent = 'Cannot reach server';
    }
  });

  document.getElementById('openApp').addEventListener('click', async () => {
    const d = await chrome.storage.local.get(['backendUrl']);
    const url = d.backendUrl || '';
    if (url) {
      chrome.tabs.create({ url: url + '/linkedin-search' });
    } else {
      alert('Set your backend URL first');
    }
  });
});
