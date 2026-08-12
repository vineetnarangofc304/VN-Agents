// Popup script — Multi-Account Support
document.addEventListener('DOMContentLoaded', async () => {
  const data = await chrome.storage.local.get(['backendUrl', 'connCount', 'msgCount', 'lastSync', 'activeAccountId']);

  document.getElementById('backendUrl').value = data.backendUrl || '';
  document.getElementById('connCount').textContent = data.connCount || '0';
  document.getElementById('msgCount').textContent = data.msgCount || '0';
  document.getElementById('lastSync').textContent = data.lastSync || 'Never';

  // Load accounts if backend URL is set
  if (data.backendUrl) {
    await loadAccounts(data.backendUrl, data.activeAccountId || 'default');
  }

  document.getElementById('saveUrl').addEventListener('click', async () => {
    const url = document.getElementById('backendUrl').value.trim().replace(/\/$/, '');
    if (!url) return;
    await chrome.storage.local.set({ backendUrl: url });

    const status = document.getElementById('urlStatus');
    try {
      const resp = await fetch(url + '/api/health', { method: 'GET', mode: 'cors' });
      if (resp.ok) {
        status.className = 'status status-ok';
        status.textContent = 'Connected!';
        await loadAccounts(url);
      } else {
        status.className = 'status status-err';
        status.textContent = 'Server returned ' + resp.status;
      }
    } catch (e) {
      status.className = 'status status-err';
      status.textContent = 'Cannot reach server';
    }
  });

  // Account selector change
  document.getElementById('accountSelect').addEventListener('change', async (e) => {
    const accountId = e.target.value;
    await chrome.storage.local.set({ activeAccountId: accountId });
    const info = document.getElementById('accountInfo');
    info.textContent = 'Active: ' + (e.target.selectedOptions[0]?.textContent || accountId);
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

async function loadAccounts(backendUrl, activeId) {
  const select = document.getElementById('accountSelect');
  const info = document.getElementById('accountInfo');
  try {
    const resp = await fetch(backendUrl + '/api/li-search/accounts');
    if (!resp.ok) {
      info.textContent = 'Could not load accounts';
      return;
    }
    const data = await resp.json();
    const accounts = data.accounts || [];
    select.innerHTML = '';
    accounts.forEach(acc => {
      const opt = document.createElement('option');
      opt.value = acc.account_id;
      opt.textContent = acc.name + ' (' + acc.connection_count + ' contacts)';
      if (acc.account_id === activeId) opt.selected = true;
      select.appendChild(opt);
    });
    if (accounts.length === 0) {
      select.innerHTML = '<option value="default">Default Account</option>';
    }
    // Save active account
    const currentVal = select.value;
    await chrome.storage.local.set({ activeAccountId: currentVal });
    info.textContent = accounts.length + ' account(s) available';
  } catch (e) {
    info.textContent = 'Error loading accounts';
  }
}
