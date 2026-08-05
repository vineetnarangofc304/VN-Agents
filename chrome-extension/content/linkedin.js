// LinkedIn Lead Agent — Content Script v1.2.0
// Injected into all linkedin.com pages

(function () {
  'use strict';
  if (document.getElementById('lla-fab')) return;

  // ============ FLOATING ACTION BUTTON ============
  var fab = document.createElement('button');
  fab.id = 'lla-fab';
  fab.textContent = '\u26A1';
  fab.title = 'LinkedIn Lead Agent';
  document.body.appendChild(fab);

  // ============ PANEL ============
  var panel = document.createElement('div');
  panel.id = 'lla-panel';
  panel.innerHTML = [
    '<div class="lla-header">',
    '  <h3>Lead Agent <span style="font-size:9px;color:#64748b;font-weight:400">v1.2.0</span></h3>',
    '  <button class="lla-close" id="lla-close-btn">&times;</button>',
    '</div>',
    '<div class="lla-body">',
    '  <div id="lla-stats">',
    '    <div class="lla-stat-row"><span class="lla-stat-label">Connections</span><span class="lla-stat-val" id="lla-conn-count">\u2014</span></div>',
    '    <div class="lla-stat-row"><span class="lla-stat-label">Last Sync</span><span class="lla-stat-val" id="lla-last-sync">Never</span></div>',
    '  </div>',
    '  <div style="margin-top:12px">',
    '    <button class="lla-btn lla-btn-sync" id="lla-sync-btn">Sync All Connections</button>',
    '    <button class="lla-btn lla-btn-msg" id="lla-msg-btn">Check Message Queue</button>',
    '    <button class="lla-btn" id="lla-enrich-btn" style="background:#f59e0b;color:#fff;width:100%;padding:10px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;margin-bottom:8px">Enrich: Fetch Email &amp; Phone</button>',
    '  </div>',
    '  <div id="lla-progress" class="lla-progress" style="display:none"></div>',
    '  <div id="lla-compose"></div>',
    '</div>'
  ].join('\n');
  document.body.appendChild(panel);

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
    if (!csrf) { log('Not logged in', 'err'); btn.disabled = false; btn.textContent = 'Sync All Connections'; return; }

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
        if (pid && addResult(pid, item.firstName, item.lastName, item.occupation || item.headline || '', item.entityUrn || '')) count++;
      }
      return count;
    }

    function extractFromElements(elems, incl) {
      var count = 0;
      for (var i = 0; i < elems.length; i++) {
        var el = elems[i];
        // Pattern 1: connectedMemberResolutionResult has inline profile
        var p = el.connectedMemberResolutionResult || el.connectedMember || el.profile || el.memberProfile || null;
        if (p && typeof p === 'object' && p.firstName) {
          if (addResult(p.publicIdentifier || '', p.firstName, p.lastName, p.occupation || p.headline || '', p.entityUrn || '')) count++;
          continue;
        }
        // Pattern 2: element IS a profile
        if (el.firstName && el.publicIdentifier) {
          if (addResult(el.publicIdentifier, el.firstName, el.lastName, el.occupation || '', el.entityUrn || '')) count++;
          continue;
        }
        // Pattern 3: connectedMember or *connectedMember is a URN → resolve from included
        var ref = (typeof el.connectedMember === 'string') ? el.connectedMember : el['*connectedMember'] || '';
        if (ref && incl) {
          for (var j = 0; j < incl.length; j++) {
            if (incl[j].entityUrn === ref && incl[j].firstName) {
              if (addResult(incl[j].publicIdentifier || '', incl[j].firstName, incl[j].lastName, incl[j].occupation || '', incl[j].entityUrn || '')) count++;
              break;
            }
          }
        }
      }
      return count;
    }

    // ========== METHOD A: Connections API ==========
    log('Trying Connections API...', 'info');
    var apiWorked = false;

    // Diagnostic call first
    try {
      var diagUrl = 'https://www.linkedin.com/voyager/api/relationships/dash/connections?decorationId=com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-16&count=40&q=search&sortType=RECENTLY_ADDED&start=0';
      var diagResp = await fetch(diagUrl, { headers: H, credentials: 'include' });
      log('API: HTTP ' + diagResp.status, diagResp.ok ? 'ok' : 'err');
      if (diagResp.ok) {
        var d = await diagResp.json();
        var elems = d.elements || (d.data && d.data.elements) || [];
        var incl = d.included || [];
        var paging = d.paging || (d.data && d.data.paging) || {};
        var total = paging.total || 0;
        log('elements: ' + elems.length + ', included: ' + incl.length + ', total: ' + total, 'info');

        if (elems.length > 0) {
          log('elem keys: ' + Object.keys(elems[0]).join(', '), 'info');
          log('sample: ' + JSON.stringify(elems[0]).substring(0, 250), 'info');
        }

        var added = extractFromElements(elems, incl) + extractFromIncluded(incl);
        log('First page: +' + added, added > 0 ? 'ok' : 'err');

        if (added > 0) {
          apiWorked = true;
          if (!total) total = 99999;
          for (var s = 40; s < total; s += 40) {
            await delay(350 + Math.random() * 150);
            try {
              var nr = await fetch(diagUrl.replace('start=0', 'start=' + s), { headers: H, credentials: 'include' });
              if (!nr.ok) break;
              var nd = await nr.json();
              var before = results.length;
              extractFromElements(nd.elements || (nd.data && nd.data.elements) || [], nd.included || []);
              extractFromIncluded(nd.included || []);
              if (results.length === before) break;
              if (s % 200 === 0) log('Fetched: ' + results.length + '/' + total, 'info');
            } catch(e) { break; }
          }
          log('API: ' + results.length + ' total', 'ok');
        }
      }
    } catch(e) { log('API error: ' + e.message, 'err'); }

    // Try other decorations
    if (!apiWorked) {
      for (var dn = 5; dn <= 25 && !apiWorked; dn++) {
        if (dn === 16) continue;
        try {
          var u = 'https://www.linkedin.com/voyager/api/relationships/dash/connections?decorationId=com.linkedin.voyager.dash.deco.web.mynetwork.ConnectionListWithProfile-' + dn + '&count=40&q=search&sortType=RECENTLY_ADDED&start=0';
          var r = await fetch(u, { headers: H, credentials: 'include' });
          if (!r.ok) continue;
          var dd = await r.json();
          var added = extractFromElements(dd.elements || [], dd.included || []) + extractFromIncluded(dd.included || []);
          if (added > 0) {
            apiWorked = true;
            log('Decoration -' + dn + ': +' + added, 'ok');
            var t = (dd.paging && dd.paging.total) || 99999;
            for (var s = 40; s < t; s += 40) {
              await delay(400);
              var nr = await fetch(u.replace('start=0', 'start=' + s), { headers: H, credentials: 'include' });
              if (!nr.ok) break;
              var nd = await nr.json();
              var b = results.length;
              extractFromElements(nd.elements || [], nd.included || []);
              extractFromIncluded(nd.included || []);
              if (results.length === b) break;
              if (s % 200 === 0) log('Progress: ' + results.length, 'info');
            }
          }
        } catch(e) {}
      }
    }

    // ========== METHOD B: Search API ==========
    if (!apiWorked) {
      log('Trying Search API...', 'info');
      for (var sd = 165; sd <= 200 && !apiWorked; sd += 5) {
        try {
          var su = 'https://www.linkedin.com/voyager/api/search/dash/clusters?decorationId=com.linkedin.voyager.dash.deco.search.SearchClusterCollection-' + sd + '&origin=FACETED_SEARCH&q=all&query=(flagshipSearchIntent:SEARCH_SRP,queryParameters:List((key:network,value:List(F)),(key:resultType,value:List(PEOPLE))))&count=49&start=0';
          var sr = await fetch(su, { headers: H, credentials: 'include' });
          if (!sr.ok) continue;
          var sd2 = await sr.json();
          var sa = extractFromElements(sd2.elements || [], sd2.included || []) + extractFromIncluded(sd2.included || []);
          if (sa > 0) {
            apiWorked = true;
            log('Search -' + sd + ': +' + sa, 'ok');
            for (var s = 49; s < 99999; s += 49) {
              await delay(400);
              var snr = await fetch(su.replace('start=0', 'start=' + s), { headers: H, credentials: 'include' });
              if (!snr.ok) break;
              var snd = await snr.json();
              var b = results.length;
              extractFromElements(snd.elements || [], snd.included || []);
              extractFromIncluded(snd.included || []);
              if (results.length === b) break;
              if (s % 490 === 0) log('Search: ' + results.length, 'info');
            }
          }
        } catch(e) {}
      }
    }

    // ========== METHOD C: DOM + Auto-scroll ==========
    if (results.length < 100) {
      log('DOM scraping + auto-scroll...', 'info');
      var stale = 0;
      for (var sc = 0; sc < 500; sc++) {
        document.querySelectorAll('a[href*="/in/"]').forEach(function (link) {
          try {
            var m = link.href.split('?')[0].match(/\/in\/([a-zA-Z0-9_-]+)/);
            if (!m) return;
            var pid = m[1];
            if (seenIds[pid] || pid.length > 100 || pid.length < 2) return;
            if (link.closest('nav') || link.closest('header') || link.closest('footer')) return;
            var c = link.parentElement;
            for (var i = 0; i < 8 && c; i++) { if ((c.innerText || '').length > 30) break; c = c.parentElement; }
            var ct = (c && c.innerText || '').trim();
            var lines = ct.split('\n').map(function(l){return l.trim()}).filter(function(l){return l.length>1&&l.length<80&&['Message','Connect','Follow','Pending','More','...'].indexOf(l)===-1});
            var fn = '', oc = '';
            for (var li = 0; li < lines.length; li++) {
              if (!fn && lines[li].length <= 50 && lines[li].indexOf('mutual') === -1) { fn = lines[li]; continue; }
              if (fn && !oc && lines[li].indexOf('mutual') === -1 && lines[li].length > 3) { oc = lines[li]; break; }
            }
            if (fn && fn.length >= 2) { var p = fn.split(' '); addResult(pid, p[0], p.slice(1).join(' '), oc, ''); }
          } catch(e) {}
        });
        var bf = results.length;
        window.scrollBy(0, window.innerHeight);
        document.querySelectorAll('button').forEach(function(b) {
          if (b.offsetParent && (b.textContent||'').toLowerCase().indexOf('show more') >= 0) try { b.click(); } catch(e) {}
        });
        await delay(1200 + Math.random() * 500);
        if (results.length === bf) { stale++; if (stale >= 8) break; } else stale = 0;
        if (sc % 5 === 4) log('Scroll ' + (sc+1) + ': ' + results.length, 'info');
      }
    }

    log('Total: ' + results.length + ' connections', results.length > 0 ? 'ok' : 'err');

    if (results.length > 0) {
      log('Sending to backend...', 'info');
      chrome.runtime.sendMessage({ type: 'SYNC_CONNECTIONS', connections: results }, function (resp) {
        if (resp && resp.success) {
          log('Synced ' + resp.stored + ' (new: ' + (resp.new || 0) + ', dupes: ' + (resp.duplicates || 0) + ')', 'ok');
        } else {
          log('Backend error: ' + (resp ? resp.error : 'no response'), 'err');
          try { var ta = document.createElement('textarea'); ta.value = JSON.stringify(results); ta.style.cssText='position:fixed;left:-9999px'; document.body.appendChild(ta); ta.focus(); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); log('Data copied to clipboard', 'info'); } catch(e) {}
        }
        loadStats();
      });
    }

    btn.disabled = false;
    btn.textContent = 'Sync All Connections';
  });

  // ============ ENRICH CONTACTS ============
  document.getElementById('lla-enrich-btn').addEventListener('click', async function () {
    var btn = this;
    btn.disabled = true;
    btn.textContent = 'Enriching...';
    clearLog();

    var csrf = getCsrf();
    if (!csrf) { log('Not logged in', 'err'); btn.disabled = false; btn.textContent = 'Enrich: Fetch Email & Phone'; return; }
    var H = liHeaders();

    var storageData = await chrome.storage.local.get(['backendUrl']);
    var backendUrl = storageData.backendUrl;
    if (!backendUrl) { log('Set backend URL first!', 'err'); btn.disabled = false; btn.textContent = 'Enrich: Fetch Email & Phone'; return; }

    // Fetch connections that need enrichment (no email/phone)
    log('Fetching contacts to enrich...', 'info');
    var toEnrich = [];
    try {
      var resp = await fetch(backendUrl + '/api/li-search/connections?count=500&sort_by=synced_at&sort_dir=-1');
      if (resp.ok) {
        var data = await resp.json();
        for (var i = 0; i < data.connections.length; i++) {
          var c = data.connections[i];
          if (!c.email && !c.phone && c.public_id) {
            toEnrich.push(c);
          }
        }
      }
    } catch(e) { log('Error: ' + e.message, 'err'); }

    if (toEnrich.length === 0) {
      log('No contacts need enrichment (all have email/phone or none found)', 'info');
      btn.disabled = false; btn.textContent = 'Enrich: Fetch Email & Phone';
      return;
    }

    log('Enriching ' + toEnrich.length + ' contacts...', 'info');
    var enriched = [];
    var batchSize = 50; // Process in batches to avoid overwhelming
    var limit = Math.min(toEnrich.length, 200); // Max 200 per session

    for (var i = 0; i < limit; i++) {
      var c = toEnrich[i];
      try {
        var pUrl = 'https://www.linkedin.com/voyager/api/identity/dash/profiles?q=memberIdentity&memberIdentity=' + encodeURIComponent(c.public_id) + '&decorationId=com.linkedin.voyager.dash.deco.identity.profile.TopCardSupplementary-167';
        var pr = await fetch(pUrl, {headers: H, credentials: 'include'});
        if (pr.ok) {
          var pd = await pr.json();
          var email = '', phone = '', city = '', company = '';
          var items = pd.included || pd.elements || [];
          for (var j = 0; j < items.length; j++) {
            var item = items[j];
            // Look for email
            if (item.emailAddress) email = item.emailAddress;
            if (item['emailAddress'] && !email) email = item['emailAddress'];
            // Look for phone
            if (item.phoneNumber) phone = item.phoneNumber;
            if (item.phoneNumbers) {
              for (var pn = 0; pn < item.phoneNumbers.length; pn++) {
                if (item.phoneNumbers[pn].number) { phone = item.phoneNumbers[pn].number; break; }
              }
            }
            // Look for location
            if (item.locationName && !city) city = item.locationName;
            if (item.geoLocationName && !city) city = item.geoLocationName;
            // Look for company
            if (item.companyName && !company) company = item.companyName;
          }
          if (email || phone || city || company) {
            enriched.push({public_id: c.public_id, email: email, phone: phone, city: city, company: company});
          }
        }
      } catch(e) {}
      if (i % 10 === 9) {
        log('Progress: ' + (i+1) + '/' + limit + ' (' + enriched.length + ' enriched)', 'info');
        await delay(500);
      }
      await delay(300 + Math.random() * 200);
    }

    // Send enriched data to backend
    if (enriched.length > 0) {
      log('Sending ' + enriched.length + ' enriched contacts to backend...', 'info');
      try {
        var er = await fetch(backendUrl + '/api/li-search/connections/enrich', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({contacts: enriched})
        });
        if (er.ok) {
          var erd = await er.json();
          log('Enriched ' + erd.updated + ' contacts!', 'ok');
        }
      } catch(e) { log('Backend error: ' + e.message, 'err'); }
    } else {
      log('No email/phone found for checked profiles', 'info');
    }

    btn.disabled = false;
    btn.textContent = 'Enrich: Fetch Email & Phone';
  });

  // ============ MESSAGE QUEUE ============
  document.getElementById('lla-msg-btn').addEventListener('click', async function () {
    clearLog();
    log('Checking message queue...', 'info');
    
    var data = await chrome.storage.local.get(['backendUrl']);
    var backendUrl = data.backendUrl;
    if (!backendUrl) {
      log('Set backend URL in extension popup first!', 'err');
      return;
    }

    try {
      var resp = await fetch(backendUrl + '/api/li-search/message/queue');
      if (!resp.ok) { log('Server error: ' + resp.status, 'err'); return; }
      var queueData = await resp.json();

      if (!queueData.recipients || queueData.recipients.length === 0) {
        log('No messages in queue. Go to Lead Finder → select contacts → compose → Send to Extension.', 'info');
        return;
      }

      var R = queueData.recipients;
      var M = queueData.message;
      var idx = 0, sent = 0;
      var composeWin = null;

      log('Loaded ' + R.length + ' recipients', 'ok');
      log('Message: ' + M.substring(0, 60) + (M.length > 60 ? '...' : ''), 'info');

      var compose = document.getElementById('lla-compose');
      compose.className = 'open';

      function copyMsg() {
        try { var ta = document.createElement('textarea'); ta.value = M; ta.style.cssText='position:fixed;left:-9999px'; document.body.appendChild(ta); ta.focus(); ta.select(); document.execCommand('copy'); document.body.removeChild(ta); } catch(e) {}
      }

      function showNext() {
        if (idx >= R.length) {
          compose.innerHTML = '<div style="text-align:center;padding:16px"><div style="color:#86efac;font-weight:700;font-size:15px;margin-bottom:4px">All done!</div><div style="color:#94a3b8;font-size:12px">Sent: ' + sent + ' / ' + R.length + '</div></div>';
          chrome.runtime.sendMessage({ type: 'UPDATE_STATS', data: { msgCount: String(sent) } });
          return;
        }
        var r = R[idx];
        compose.innerHTML = '';

        var prog = document.createElement('div');
        prog.style.cssText = 'font-size:10px;color:#64748b;margin-bottom:6px';
        prog.textContent = (idx+1) + ' of ' + R.length + ' (sent: ' + sent + ')';
        compose.appendChild(prog);

        var name = document.createElement('div');
        name.className = 'lla-compose-name';
        name.textContent = r.name || 'Unknown';
        compose.appendChild(name);

        var occ = document.createElement('div');
        occ.className = 'lla-compose-occ';
        occ.textContent = r.occupation || '';
        compose.appendChild(occ);

        var msgPrev = document.createElement('div');
        msgPrev.className = 'lla-compose-msg';
        msgPrev.textContent = M.length > 80 ? M.substring(0, 80) + '...' : M;
        compose.appendChild(msgPrev);

        var btnRow = document.createElement('div');
        btnRow.className = 'lla-btn-row';
        btnRow.style.cssText = 'display:flex;gap:6px;margin-top:8px';

        var openBtn = document.createElement('button');
        openBtn.className = 'lla-btn-compose';
        openBtn.textContent = 'Compose + Copy Msg';
        openBtn.style.cssText = 'flex:1;background:#0a66c2;color:#fff;border:none;padding:10px;border-radius:8px;cursor:pointer;font-size:12px;font-weight:600';
        openBtn.addEventListener('click', function() {
          copyMsg();
          if (composeWin && !composeWin.closed) try { composeWin.close(); } catch(e) {}
          composeWin = window.open('https://www.linkedin.com/messaging/compose/?recipient=' + encodeURIComponent(r.public_id), 'lla_compose');
          // Log message to backend
          fetch(backendUrl + '/api/li-search/messages/log', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({public_id: r.public_id, recipient_name: r.name || '', message: M})
          }).catch(function(){});
          sent++; idx++; showNext();
        });

        var skipBtn = document.createElement('button');
        skipBtn.className = 'lla-btn-skip';
        skipBtn.textContent = 'Skip';
        skipBtn.style.cssText = 'background:#334155;color:#fff;border:none;padding:10px 14px;border-radius:8px;cursor:pointer;font-size:12px';
        skipBtn.addEventListener('click', function() { idx++; showNext(); });

        btnRow.appendChild(openBtn);
        btnRow.appendChild(skipBtn);
        compose.appendChild(btnRow);

        var hint = document.createElement('div');
        hint.style.cssText = 'font-size:9px;color:#64748b;text-align:center;margin-top:6px';
        hint.textContent = 'Opens compose tab. Paste (Ctrl+V) → Send → close tab → come back.';
        compose.appendChild(hint);

        copyMsg();
      }
      showNext();
    } catch(e) {
      log('Error: ' + e.message, 'err');
    }
  });

})();
