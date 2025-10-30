// History sidebar: lists previous chats and shows details.
// Removed user-name filter and tagging functionality.

(function () {
  'use strict';

  let selectedId = null;
  let pollHandle = null;

  async function fetchJSON(url, opts) {
    const res = await fetch(url, { headers: { 'Accept': 'application/json' }, ...(opts||{}) });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  function htmlEscape(s) {
    return (s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function setActiveRow(id) {
    selectedId = id;
    const listEl = document.getElementById('historyList');
    if (!listEl) return;
    Array.from(listEl.querySelectorAll('.history-item')).forEach(li => {
      li.classList.toggle('active', String(li.dataset.id) === String(id));
    });
  }

  async function loadHistory({ selectFirst = false, keepSelection = true } = {}) {
    const listEl = document.getElementById('historyList');
    if (!listEl) return;
    listEl.innerHTML = '<li class="muted">Loading…</li>';
    try {
      const js = await fetchJSON('/conversations/?limit=20&days=365');
      const items = js.items || [];
      if (items.length === 0) {
        listEl.innerHTML = '<li class="muted">No previous chats yet.</li>';
        const detailEl = document.getElementById('chatDetail');
        if (detailEl) detailEl.innerHTML = '<div class="muted">No conversation selected.</div>';
        selectedId = null;
        return;
      }
      listEl.innerHTML = '';
      let selectedSet = false;
      items.forEach((item, idx) => {
        const li = document.createElement('li');
        li.className = 'history-item';
        li.dataset.id = String(item.id);
        li.innerHTML = `
          <div class="title" style="font-weight:600">${htmlEscape(item.title)}</div>
          <div class="snippet" style="opacity:.8">${htmlEscape(item.snippet || '')}</div>
          <div class="meta" style="font-size:12px;opacity:.6">${new Date(item.last_activity).toLocaleString()}</div>
        `;
        li.addEventListener('click', () => {
          setActiveRow(item.id);
          loadDetails(item.id).catch(() => {});
        });
        listEl.appendChild(li);

        if (!selectedSet) {
          if (keepSelection && selectedId && String(selectedId) === String(item.id)) {
            setActiveRow(item.id);
            loadDetails(item.id).catch(() => {});
            selectedSet = true;
          } else if (selectFirst && idx === 0) {
            setActiveRow(item.id);
            loadDetails(item.id).catch(() => {});
            selectedSet = true;
          }
        }
      });
    } catch (e) {
      listEl.innerHTML = `<li class="error">Failed to load history: ${htmlEscape(String(e))}</li>`;
    }
  }

  async function loadDetails(id) {
    const detailEl = document.getElementById('chatDetail');
    if (!detailEl) return;
    detailEl.innerHTML = '<div class="muted">Loading…</div>';
    try {
      const d = await fetchJSON(`/conversations/${id}/`);
      detailEl.innerHTML = `
        <div style="display:flex;align-items:center;gap:12px;justify-content:space-between;">
          <h3 style="margin:0;">Conversation #${d.id}</h3>
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="font-size:12px;opacity:.7">${new Date(d.last_activity).toLocaleString()}</span>
            <button id="deleteConversationBtn" class="btn" data-id="${d.id}" title="Delete this conversation">Delete</button>
          </div>
        </div>
        <div style="margin-top:8px;">
          <div><strong>Summary:</strong></div>
          <div style="white-space:pre-wrap">${htmlEscape(d.summary || '—')}</div>
        </div>
        <div style="margin-top:8px;display:flex;gap:16px;flex-wrap:wrap">
          <div><strong>Satisfaction:</strong> ${d.satisfaction_rating ?? '—'}</div>
          <div><strong>Label:</strong> ${htmlEscape(d.satisfaction_label || '—')}</div>
          <div><strong>Analyzed:</strong> ${d.analysis_timestamp ? new Date(d.analysis_timestamp).toLocaleString() : '—'}</div>
        </div>
        <details style="margin-top:12px;">
          <summary style="cursor:pointer">Full conversation</summary>
          <pre style="white-space:pre-wrap;margin-top:8px">${htmlEscape(d.conversation || '')}</pre>
        </details>
      `;

      const delBtn = document.getElementById('deleteConversationBtn');
      if (delBtn) {
        delBtn.addEventListener('click', async () => {
          const idStr = delBtn.getAttribute('data-id');
          if (!idStr) return;
          const cid = Number(idStr);
          if (!Number.isFinite(cid)) return;
          if (!window.confirm('Delete this conversation permanently?')) return;
          try {
            const ok = await deleteConversation(cid);
            if (ok) {
              document.getElementById('chatDetail').innerHTML = '<div class="muted">Conversation deleted.</div>';
              loadHistory({ selectFirst: true, keepSelection: false }).catch(() => {});
            }
          } catch (_) {}
        });
      }
    } catch (e) {
      detailEl.innerHTML = `<div class="error">Failed to load details: ${htmlEscape(String(e))}</div>`;
    }
  }

  function getCSRFToken() {
    const name = 'csrftoken=';
    const parts = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < parts.length; i++) {
      const c = parts[i].trim();
      if (c.indexOf(name) === 0) return decodeURIComponent(c.substring(name.length));
    }
    return '';
  }

  async function deleteConversation(id) {
    const token = getCSRFToken();
    const res = await fetch(`/conversations/${id}/delete/`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'X-CSRFToken': token,
      }
    });
    if (res.status === 401) { alert('Please login to delete.'); return false; }
    if (res.status === 403) { alert('You do not have permission to delete this conversation.'); return false; }
    if (!res.ok) { alert('Delete failed.'); return false; }
    return true;
  }

  function wireButtons() {
    const newBtn = document.getElementById('newChatBtn');
    if (newBtn) newBtn.addEventListener('click', () => { window.location.href = '/'; });

    const refreshBtn = document.getElementById('refreshHistoryBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', () => loadHistory({ selectFirst: true, keepSelection: false }));
  }

  function ensurePolling() {
    if (pollHandle) clearInterval(pollHandle);
    pollHandle = setInterval(() => loadHistory({ selectFirst: false, keepSelection: true }), 30000);
  }

  function init() {
    wireButtons();
    loadHistory({ selectFirst: true, keepSelection: false }).catch(() => {});
    ensurePolling();

    // Refresh when a conversation ends (if app.js dispatches 'convo:state')
    window.addEventListener('convo:state', (e) => {
      try {
        if (e && e.detail && e.detail.state === 'ended') {
          loadHistory({ selectFirst: true, keepSelection: false });
        }
      } catch (_) {}
    });

    // Refresh when window/tab regains focus
    window.addEventListener('focus', () => {
      loadHistory({ selectFirst: false, keepSelection: true });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();