// LinkedIn Lead Agent — Content Script
// Injected into all linkedin.com pages

(function () {
  'use strict';
  if (document.getElementById('lla-fab')) return; // already injected

  // ============ FLOATING ACTION BUTTON ============
  var fab = document.createElement('button');
  fab.id = 'lla-fab';
  fab.textContent = '⚡';
  fab.title = 'LinkedIn Lead Agent';
  document.body.appendChild(fab);

  // ============ PANEL ============
  var panel = document.createElement('div');
  panel.id = 'lla-panel';
  panel.innerHTML = [
    '<div class="lla-header">',
    '  <h3>Lead Agent</h3>',
    '  <button class="lla-close" id="lla-close-btn">&times;</button>',
    '</div>',
    '<div class="lla-body">',
    '  <div id="lla-stats">',
    '    <div class="lla-stat-row"><span class="lla-stat-label">Connections</span><span class="lla-stat-val" id="lla-conn-count">—</span></div>',
    '    <div class="lla-stat-row"><span class="lla-stat-label">Last Sync</span><span class="lla-stat-val" id="lla-last-sync">Never</span></div>',
    '  </div>',
    '  <div style="margin-top:12px">',
    '    <button class="lla-btn lla-btn-sync" id="lla-sync-btn">&#x1F504; Sync All Connections</button>',
    '    <button class="lla-btn lla-btn-msg" id="lla-msg-btn">&#x2709; Check Message Queue</button>',
    '  </div>',
    '  <div id="lla-progress" class="lla-progress" style="display:none"></div>',
    '  <div id="lla-compose"></div>',
    '</div>'
  ].join('\n');
  document.body.appendChild(panel);

  // Toggle panel
  fab.addEventListener('click', function () {
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) loadStats();
  });
  document.getElementById('lla-close-btn').addEventListener('click', function () {
    panel.classList.remove('open');
  });

  // ============ HELPERS ============
  function delay(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function getCsrf() {
    return (document.cookie.match(/JSESSIONID="?([^;"]+)/) || [])[1] || '';
  }
  function liHeaders() {
    return { 'csrf-token': getCsrf(), 'x-restli-protocol-version': '2.0.0' };
  }
  function log(text, type) {
    var prog = document.getElementById('lla-progress');
    prog.style.display = 'block';
    var line = document.createElement('div');
    line.className = 'lla-log-line' + (type ? ' lla-' + type : '');
    line.textContent = text;
    prog.appendChild(line);
    prog.scrollTop = prog.scrollHeight;
  }
  function clearLog() {
    var prog = document.getElementById('lla-progress');
    prog.innerHTML = '';
    prog.style.display = 'none';
  }

  async function loadStats() {
    var data = await chrome.storage.local.get(['connCount', 'lastSync']);
    document.getElementById('lla-conn-count').textContent = data.connCount || '0';
    document.getElementById('lla-last-sync').textContent = data.lastSync || 'Never';
  }

  // ============ SYNC CONNECTIONS ============
  document.getElementById('lla-sync-btn').addEventListener('click', async function () {
    var btn = this;
    btn.disabled = true;
    btn.textContent = 'Syncing...';
    clearLog();

    var csrf = getCsrf();
    if (!csrf) { log('Not logged into LinkedIn', 'err'); btn.disabled = false; btn.textContent = '🔄 Sync All Connections'; return; }

    var H = liHeaders();
    var results = [];
    var seenIds = {};

    function addResult(pid, fn, ln, occ, urn) {
      if (!pid || seenIds[pid]) return false;
      seenIds[pid] = true;
      results.push({
        full_name: ((fn || '') + ' ' + (ln || '')).trim(),
        first_name: fn || '', last_name: ln || '',
        occupation: occ || '',
        profile_url: 'https://www.linkedin.com/in/' + pid,
        public_id: pid, entity_urn: urn || '', avatar_url: ''
      });
      return true;
    }

    function extractFromIncluded(included) {
      var count = 0;
      for (var i = 0; i < included.length; i++) {
        var item = included[i];
        if (!item.firstName) continue;
        var pid = item.publicIdentifier || '';
        var urn = item.entityUrn || '';
        if (pid && addResult(pid, item.firstName, item.lastName, item.occupation, urn)) count++;
      }
      return count;
    }

    // Method A: Connections API with decoration range
    log('Trying Connections API...', 'info');
    var apiWorked = false;

    for (var decNum = 5; decNum <= 25 && !apiWorked; decNum++) {
      try {
        var url = 'https://www.linkedin.com/voyager/api/relationships/dash/connections'
          + '?decorationId=com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-' + decNum
          + '&count=40&q=search&sortType=RECENTLY_ADDED&start=0';
        var resp = await fetch(url, { headers: H, credentials: 'include' });
        if (!resp.ok) continue;
        var data = await resp.json();
        var added = extractFromIncluded(data.included || []);
        if (added > 0) {
          apiWorked = true;
          log('Decoration -' + decNum + ' works! +' + added, 'ok');
          for (var s = 40; s < 99999; s += 40) {
            await delay(400 + Math.random() * 200);
            try {
              var nu = 'https://www.linkedin.com/voyager/api/relationships/dash/connections'
                + '?decorationId=com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-' + decNum
                + '&count=40&q=search&sortType=RECENTLY_ADDED&start=' + s;
              var nr = await fetch(nu, { headers: H, credentials: 'include' });
              if (!nr.ok) break;
              var nd = await nr.json();
              var before = results.length;
              extractFromIncluded(nd.included || []);
              if (results.length === before) break;
              if (s % 200 === 0) log('Progress: ' + results.length + ' connections...', 'info');
            } catch (e) { break; }
          }
        }
      } catch (e) { }
    }

    // Method B: Search API
    if (!apiWorked) {
      log('Trying Search API...', 'info');
      for (var sd = 165; sd <= 200 && !apiWorked; sd += 5) {
        try {
          var searchUrl = 'https://www.linkedin.com/voyager/api/search/dash/clusters'
            + '?decorationId=com.linkedin.voyager.dash.deco.search.SearchClusterCollection-' + sd
            + '&origin=FACETED_SEARCH&q=all'
            + '&query=(flagshipSearchIntent:SEARCH_SRP,queryParameters:List((key:network,value:List(F)),(key:resultType,value:List(PEOPLE))))'
            + '&count=49&start=0';
          var sr = await fetch(searchUrl, { headers: H, credentials: 'include' });
          if (!sr.ok) continue;
          var sdata = await sr.json();
          var sadded = extractFromIncluded(sdata.included || []);
          if (sadded > 0) {
            apiWorked = true;
            log('Search decoration -' + sd + ' works! +' + sadded, 'ok');
            for (var s = 49; s < 99999; s += 49) {
              await delay(400 + Math.random() * 300);
              try {
                var snu = searchUrl.replace('start=0', 'start=' + s);
                var snr = await fetch(snu, { headers: H, credentials: 'include' });
                if (!snr.ok) break;
                var snd = await snr.json();
                var before = results.length;
                extractFromIncluded(snd.included || []);
                if (results.length === before) break;
                if (s % 490 === 0) log('Search: ' + results.length + ' found...', 'info');
              } catch (e) { break; }
            }
          }
        } catch (e) { }
      }
    }

    // Method C: DOM scraping with auto-scroll
    if (results.length < 100) {
      log('DOM scraping with auto-scroll...', 'info');
      for (var scroll = 0; scroll < 80; scroll++) {
        document.querySelectorAll('a[href*="/in/"]').forEach(function (link) {
          try {
            var href = link.href.split('?')[0].replace(/\/$/, '');
            var m = href.match(/\/in\/([a-zA-Z0-9_-]+)/);
            if (!m) return;
            var pid = m[1];
            if (seenIds[pid] || pid.length > 100 || pid.length < 2) return;
            if (link.closest('nav') || link.closest('header') || link.closest('footer')) return;
            var container = link.parentElement;
            for (var i = 0; i < 8 && container; i++) {
              if ((container.innerText || '').length > 30) break;
              container = container.parentElement;
            }
            var ct = (container && container.innerText || '').trim();
            var lines = ct.split('\n').map(function (l) { return l.trim(); }).filter(function (l) {
              return l.length > 1 && l.length < 80 && ['Message', 'Connect', 'Follow', 'Pending', 'More', '...'].indexOf(l) === -1;
            });
            var fn = '', occ = '';
            for (var li = 0; li < lines.length; li++) {
              if (!fn && lines[li].length <= 50 && lines[li].indexOf('mutual') === -1) { fn = lines[li]; continue; }
              if (fn && !occ && lines[li].indexOf('mutual') === -1 && lines[li].length > 3) { occ = lines[li]; break; }
            }
            if (fn && fn.length >= 2) {
              var parts = fn.split(' ');
              addResult(pid, parts[0], parts.slice(1).join(' '), occ, '');
            }
          } catch (e) { }
        });

        var lastCount = results.length;
        window.scrollTo(0, document.body.scrollHeight);
        var showMore = document.querySelector('button.scaffold-finite-scroll__load-button, button[aria-label*="Show more"]');
        if (showMore) showMore.click();
        await delay(1500);
        if (scroll % 10 === 9) log('Scrolled ' + (scroll + 1) + 'x, found ' + results.length, 'info');
        if (results.length === lastCount && scroll > 3) break;
      }
    }

    log('Total: ' + results.length + ' connections', 'ok');

    // Send to backend
    if (results.length > 0) {
      log('Sending to backend...', 'info');
      chrome.runtime.sendMessage(
        { type: 'SYNC_CONNECTIONS', connections: results },
        function (resp) {
          if (resp && resp.success) {
            log('Synced ' + resp.stored + ' to backend!', 'ok');
          } else {
            log('Backend error: ' + (resp ? resp.error : 'no response'), 'err');
            log('Data copied to clipboard as fallback', 'info');
            try {
              var ta = document.createElement('textarea');
              ta.value = JSON.stringify(results);
              ta.style.cssText = 'position:fixed;left:-9999px';
              document.body.appendChild(ta); ta.focus(); ta.select();
              document.execCommand('copy'); document.body.removeChild(ta);
            } catch (e) { }
          }
          loadStats();
        }
      );
    }

    btn.disabled = false;
    btn.textContent = '🔄 Sync All Connections';
  });

  // ============ MESSAGE QUEUE ============
  document.getElementById('lla-msg-btn').addEventListener('click', async function () {
    clearLog();
    log('Checking message queue...', 'info');

    chrome.runtime.sendMessage({ type: 'GET_MESSAGE_QUEUE' }, function (resp) {
      if (!resp || !resp.recipients || resp.recipients.length === 0) {
        log('No messages in queue. Select connections in the app first.', 'info');
        return;
      }

      var R = resp.recipients;
      var M = resp.message;
      var idx = 0, sent = 0;
      var compose = document.getElementById('lla-compose');
      compose.className = 'open';

      function copyMsg() {
        try {
          var ta = document.createElement('textarea');
          ta.value = M; ta.style.cssText = 'position:fixed;left:-9999px';
          document.body.appendChild(ta); ta.focus(); ta.select();
          document.execCommand('copy'); document.body.removeChild(ta);
        } catch (e) { }
      }

      function showNext() {
        if (idx >= R.length) {
          compose.innerHTML = '<div style="text-align:center;padding:12px;color:#86efac;font-weight:600">Done! Sent: ' + sent + '/' + R.length + '</div>';
          chrome.runtime.sendMessage({ type: 'UPDATE_STATS', data: { msgCount: String(sent) } });
          return;
        }
        var r = R[idx];
        compose.innerHTML = [
          '<div class="lla-compose-name">' + (r.name || 'Unknown') + '</div>',
          '<div class="lla-compose-occ">' + (idx + 1) + '/' + R.length + ' — ' + (r.occupation || '') + '</div>',
          '<div class="lla-compose-msg">' + M.substring(0, 120) + (M.length > 120 ? '...' : '') + '</div>',
          '<div class="lla-btn-row">',
          '  <button class="lla-btn-compose" id="lla-do-compose">Compose + Copy</button>',
          '  <button class="lla-btn-skip" id="lla-do-skip">Skip</button>',
          '</div>',
          '<div class="lla-compose-hint">Opens compose tab. Paste (Ctrl+V) + Send, close tab, come back.</div>'
        ].join('');

        document.getElementById('lla-do-compose').addEventListener('click', function () {
          copyMsg();
          window.open('https://www.linkedin.com/messaging/compose/?recipient=' + encodeURIComponent(r.public_id), 'lla_compose');
          sent++; idx++; showNext();
        });
        document.getElementById('lla-do-skip').addEventListener('click', function () {
          idx++; showNext();
        });
        copyMsg();
      }

      log('Loaded ' + R.length + ' recipients', 'ok');
      showNext();
    });
  });

})();
