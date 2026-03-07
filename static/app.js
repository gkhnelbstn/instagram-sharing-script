/**
 * Instagram Group Sharing — Frontend Application
 */

// ─── API helpers ─────────────────────────────────────────────────────

const API = {
  async get(url) {
    const res = await fetch(url);
    if (res.status === 401) { showAuthOverlay(); throw new Error('Oturum sona erdi.'); }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Bilinmeyen hata');
    }
    return res.json();
  },

  async post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.status === 401 && !url.includes('/auth/')) { showAuthOverlay(); throw new Error('Oturum sona erdi.'); }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Bilinmeyen hata');
    }
    return res.json();
  },

  async put(url, body) {
    const res = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (res.status === 401) { showAuthOverlay(); throw new Error('Oturum sona erdi.'); }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Bilinmeyen hata');
    }
    return res.json();
  },

  async delete(url) {
    const res = await fetch(url, { method: 'DELETE' });
    if (res.status === 401) { showAuthOverlay(); throw new Error('Oturum sona erdi.'); }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Bilinmeyen hata');
    }
    return res.json();
  },
};

// ─── Toast notifications ─────────────────────────────────────────────

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ─── Auth overlay ─────────────────────────────────────────────────────

let authMode = 'login'; // 'login' | 'register'

function showAuthOverlay() {
  document.getElementById('auth-overlay').style.display = '';
  document.getElementById('app-container').style.display = 'none';
  document.getElementById('auth-error').textContent = '';
  document.getElementById('auth-username').value = '';
  document.getElementById('auth-password').value = '';
}

function hideAuthOverlay(username) {
  document.getElementById('auth-overlay').style.display = 'none';
  document.getElementById('app-container').style.display = '';
  document.getElementById('header-username').textContent = `👤 ${username}`;
  loadAccounts();
}

function setAuthMode(mode) {
  authMode = mode;
  const isLogin = mode === 'login';
  document.getElementById('auth-subtitle').textContent = isLogin ? 'Giriş yap' : 'Hesap oluştur';
  document.getElementById('auth-submit-btn').textContent = isLogin ? 'Giriş Yap' : 'Kayıt Ol';
  document.getElementById('auth-toggle-link').innerHTML = isLogin
    ? 'Hesabın yok mu? <span>Kayıt ol</span>'
    : 'Zaten hesabın var mı? <span>Giriş yap</span>';
  document.getElementById('auth-error').textContent = '';
}

document.getElementById('auth-toggle-link').addEventListener('click', () => {
  setAuthMode(authMode === 'login' ? 'register' : 'login');
});

document.getElementById('auth-submit-btn').addEventListener('click', async () => {
  const username = document.getElementById('auth-username').value.trim();
  const password = document.getElementById('auth-password').value;
  const errEl = document.getElementById('auth-error');
  const btn = document.getElementById('auth-submit-btn');

  if (!username || !password) {
    errEl.textContent = 'Kullanıcı adı ve şifre zorunlu.';
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  errEl.textContent = '';

  try {
    const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register';
    const data = await API.post(endpoint, { username, password });
    hideAuthOverlay(data.username);
    showToast(`Hoş geldin, ${data.username}!`, 'success');
  } catch (e) {
    errEl.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = authMode === 'login' ? 'Giriş Yap' : 'Kayıt Ol';
  }
});

// Enter key
document.getElementById('auth-password').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') document.getElementById('auth-submit-btn').click();
});

// Logout
document.getElementById('btn-logout').addEventListener('click', async () => {
  try {
    await API.post('/api/auth/logout', {});
  } catch (_) { /* ignore */ }
  showAuthOverlay();
  showToast('Çıkış yapıldı.', 'info');
});

// ─── Init — oturumu kontrol et ────────────────────────────────────────

async function initApp() {
  try {
    // Önce kurulum gerekli mi kontrol et
    const setup = await fetch('/api/auth/setup').then(r => r.json());
    if (setup.needs_setup) {
      setAuthMode('register');
      document.getElementById('auth-toggle-link').style.display = 'none';
      document.getElementById('auth-subtitle').textContent = 'İlk kullanım — hesap oluştur';
      showAuthOverlay();
      return;
    }

    // Mevcut session kontrol et
    const me = await fetch('/api/auth/me').then(r => r.ok ? r.json() : null);
    if (me) {
      hideAuthOverlay(me.username);
    } else {
      showAuthOverlay();
    }
  } catch (_) {
    showAuthOverlay();
  }
}

// ─── Tab switching ───────────────────────────────────────────────────

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
    if (btn.dataset.tab === 'send') renderSendAccountList();
  });
});

// ─── Config Tab: Account Management ──────────────────────────────────

async function loadAccounts() {
  try {
    const accounts = await API.get('/api/accounts');
    renderAccountList(accounts);
  } catch (e) {
    if (e.message !== 'Oturum sona erdi.') showToast(e.message, 'error');
  }
}

function renderAccountList(accounts) {
  const list = document.getElementById('account-list');
  const empty = document.getElementById('accounts-empty');

  if (accounts.length === 0) {
    list.innerHTML = '';
    empty.style.display = '';
    return;
  }

  empty.style.display = 'none';
  list.innerHTML = accounts.map(acc => `
    <div class="account-item" data-id="${acc.id}">
      <div class="account-avatar">${acc.username[0].toUpperCase()}</div>
      <div class="account-info">
        <div class="account-name">@${acc.username}</div>
        <div class="account-meta">
          ${acc.logged_in
            ? `<span class="badge badge-success">● Giriş yapıldı</span>`
            : `<span class="badge badge-warning">○ Giriş bekleniyor</span>`}
          &nbsp; ${acc.selected_groups_count > 0 ? `📋 ${acc.selected_groups_count} grup seçili` : ''}
        </div>
      </div>
      <div class="account-actions">
        <button class="btn btn-secondary btn-sm" onclick="loginAccount('${acc.id}')">
          🔑 Giriş
        </button>
        <button class="btn btn-secondary btn-sm" onclick="openGroupModal('${acc.id}')">
          📋 Gruplar
        </button>
        <button class="btn btn-danger btn-sm" onclick="deleteAccount('${acc.id}')">
          🗑
        </button>
      </div>
    </div>
  `).join('');
}

// Add account
document.getElementById('btn-add-account').addEventListener('click', async () => {
  const username = document.getElementById('inp-username').value.trim();
  const password = document.getElementById('inp-password').value.trim();

  if (!username || !password) {
    showToast('Kullanıcı adı ve şifre gerekli.', 'error');
    return;
  }

  try {
    await API.post('/api/accounts', { username, password });
    document.getElementById('inp-username').value = '';
    document.getElementById('inp-password').value = '';
    showToast(`@${username} hesabı eklendi.`, 'success');
    loadAccounts();
  } catch (e) {
    showToast(e.message, 'error');
  }
});

// Enter key support for add account
document.getElementById('inp-password').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') document.getElementById('btn-add-account').click();
});

// Login account
async function loginAccount(accountId) {
  const item = document.querySelector(`.account-item[data-id="${accountId}"]`);
  const btn = item?.querySelector('.account-actions .btn:first-child');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';
  }

  try {
    const result = await API.post(`/api/accounts/${accountId}/login`);
    showToast(`@${result.username} hesabına giriş yapıldı.`, 'success');
    loadAccounts();
  } catch (e) {
    showToast(e.message, 'error');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🔑 Giriş';
    }
  }
}

// Delete account
async function deleteAccount(accountId) {
  if (!confirm('Bu hesabı silmek istediğinize emin misiniz?')) return;

  try {
    await API.delete(`/api/accounts/${accountId}`);
    showToast('Hesap silindi.', 'success');
    loadAccounts();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ─── Group Selection Modal ───────────────────────────────────────────

let currentGroupAccountId = null;
let currentGroupSelections = {};  // { thread_id: { thread_id, thread_title, user_count } }

async function openGroupModal(accountId) {
  currentGroupAccountId = accountId;
  currentGroupSelections = {};

  const modal = document.getElementById('modal-groups');
  const body = document.getElementById('modal-groups-body');

  modal.classList.add('visible');
  body.innerHTML = `
    <div class="empty-state">
      <div class="spinner"></div>
      <p style="margin-top:1rem;">Gruplar yükleniyor...</p>
    </div>
  `;

  try {
    const groups = await API.get(`/api/accounts/${accountId}/groups`);

    if (groups.length === 0) {
      body.innerHTML = `
        <div class="empty-state">
          <div class="icon">📭</div>
          <p>Bu hesapta grup sohbeti bulunamadı.</p>
        </div>
      `;
      return;
    }

    // Pre-select already selected groups
    groups.forEach(g => {
      if (g.selected) {
        currentGroupSelections[g.thread_id] = {
          thread_id: g.thread_id,
          thread_title: g.thread_title,
          user_count: g.user_count,
        };
      }
    });

    body.innerHTML = `
      <div style="margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
        <span style="color: var(--text-muted); font-size: 0.85rem;">
          ${groups.length} grup bulundu
        </span>
        <div style="display: flex; gap: 0.5rem;">
          <button class="btn btn-secondary btn-sm" id="btn-select-all">Tümünü Seç</button>
          <button class="btn btn-secondary btn-sm" id="btn-deselect-all">Tümünü Kaldır</button>
        </div>
      </div>
      <div class="group-list" id="modal-group-list">
        ${groups.map(g => `
          <label class="group-item ${g.selected ? 'selected' : ''}" data-tid="${g.thread_id}">
            <input type="checkbox" ${g.selected ? 'checked' : ''}
                   data-tid="${g.thread_id}"
                   data-title="${escapeAttr(g.thread_title)}"
                   data-users="${g.user_count}" />
            <span class="group-name">${escapeHtml(g.thread_title)}</span>
            <span class="group-users">👥 ${g.user_count}</span>
          </label>
        `).join('')}
      </div>
    `;

    // Checkbox events
    body.querySelectorAll('.group-item input[type="checkbox"]').forEach(cb => {
      cb.addEventListener('change', () => {
        const label = cb.closest('.group-item');
        if (cb.checked) {
          label.classList.add('selected');
          currentGroupSelections[cb.dataset.tid] = {
            thread_id: cb.dataset.tid,
            thread_title: cb.dataset.title,
            user_count: parseInt(cb.dataset.users),
          };
        } else {
          label.classList.remove('selected');
          delete currentGroupSelections[cb.dataset.tid];
        }
      });
    });

    // Select all / Deselect all
    document.getElementById('btn-select-all')?.addEventListener('click', () => {
      body.querySelectorAll('.group-item input[type="checkbox"]').forEach(cb => {
        cb.checked = true;
        cb.closest('.group-item').classList.add('selected');
        currentGroupSelections[cb.dataset.tid] = {
          thread_id: cb.dataset.tid,
          thread_title: cb.dataset.title,
          user_count: parseInt(cb.dataset.users),
        };
      });
    });

    document.getElementById('btn-deselect-all')?.addEventListener('click', () => {
      body.querySelectorAll('.group-item input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
        cb.closest('.group-item').classList.remove('selected');
      });
      currentGroupSelections = {};
    });

  } catch (e) {
    body.innerHTML = `
      <div class="empty-state">
        <div class="icon">❌</div>
        <p>${escapeHtml(e.message)}</p>
      </div>
    `;
  }
}

// Save selected groups
document.getElementById('modal-groups-save').addEventListener('click', async () => {
  if (!currentGroupAccountId) return;

  const groups = Object.values(currentGroupSelections);
  try {
    await API.put(`/api/accounts/${currentGroupAccountId}/groups`, { groups });
    showToast(`${groups.length} grup kaydedildi.`, 'success');
    closeGroupModal();
    loadAccounts();
  } catch (e) {
    showToast(e.message, 'error');
  }
});

// Close modal
function closeGroupModal() {
  document.getElementById('modal-groups').classList.remove('visible');
  currentGroupAccountId = null;
  currentGroupSelections = {};
}

document.getElementById('modal-groups-close').addEventListener('click', closeGroupModal);
document.getElementById('modal-groups-cancel').addEventListener('click', closeGroupModal);
document.getElementById('modal-groups').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closeGroupModal();
});

// ─── Send Tab ────────────────────────────────────────────────────────

let sendSelectedAccountIds = new Set();

async function renderSendAccountList() {
  try {
    const accounts = await API.get('/api/accounts');
    const list = document.getElementById('send-account-list');
    const empty = document.getElementById('send-accounts-empty');

    // Filter to accounts that have selected groups
    const readyAccounts = accounts.filter(a => a.selected_groups_count > 0);

    if (readyAccounts.length === 0) {
      list.innerHTML = '';
      empty.style.display = '';
      document.getElementById('btn-send').disabled = true;
      return;
    }

    empty.style.display = 'none';
    list.innerHTML = readyAccounts.map(acc => `
      <label class="account-select-item ${sendSelectedAccountIds.has(acc.id) ? 'selected' : ''}"
             data-id="${acc.id}">
        <input type="checkbox" ${sendSelectedAccountIds.has(acc.id) ? 'checked' : ''}
               data-id="${acc.id}" />
        <div class="account-avatar" style="width:32px;height:32px;font-size:0.85rem;">
          ${acc.username[0].toUpperCase()}
        </div>
        <span class="account-name" style="flex:1;">@${acc.username}</span>
        <span class="badge badge-success">📋 ${acc.selected_groups_count} grup</span>
      </label>
    `).join('');

    // Checkbox events
    list.querySelectorAll('input[type="checkbox"]').forEach(cb => {
      cb.addEventListener('change', () => {
        const label = cb.closest('.account-select-item');
        if (cb.checked) {
          label.classList.add('selected');
          sendSelectedAccountIds.add(cb.dataset.id);
        } else {
          label.classList.remove('selected');
          sendSelectedAccountIds.delete(cb.dataset.id);
        }
        updateSendButton();
      });
    });

    updateSendButton();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function updateSendButton() {
  const link = document.getElementById('inp-link').value.trim();
  const btn = document.getElementById('btn-send');
  btn.disabled = !(link && sendSelectedAccountIds.size > 0);
}

document.getElementById('inp-link').addEventListener('input', updateSendButton);

// Send
document.getElementById('btn-send').addEventListener('click', async () => {
  const link = document.getElementById('inp-link').value.trim();
  const message = document.getElementById('inp-message').value.trim();
  const delay = parseInt(document.getElementById('inp-delay').value) || 8;
  const accountIds = [...sendSelectedAccountIds];

  if (!link || accountIds.length === 0) {
    showToast('Link ve en az bir hesap gerekli.', 'error');
    return;
  }

  const btn = document.getElementById('btn-send');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Gönderiliyor...';

  const progress = document.getElementById('progress-container');
  const progressFill = document.getElementById('progress-fill');
  const progressText = document.getElementById('progress-text');
  progress.classList.add('visible');
  progressFill.style.width = '10%';
  progressText.textContent = 'Gönderim başlatılıyor...';

  const resultsPanel = document.getElementById('results-panel');
  resultsPanel.classList.remove('visible');
  resultsPanel.innerHTML = '';

  try {
    progressFill.style.width = '30%';
    progressText.textContent = `${accountIds.length} hesap için gönderim yapılıyor...`;

    const payload = { link, account_ids: accountIds, delay };
    if (message) payload.message = message;

    const response = await API.post('/api/send', payload);

    progressFill.style.width = '100%';
    progressText.textContent = 'Gönderim tamamlandı!';

    // Render results
    renderResults(response);
    showToast('Gönderim tamamlandı!', 'success');

  } catch (e) {
    showToast(e.message, 'error');
    progressText.textContent = 'Hata oluştu.';
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🚀 Gönder';
    setTimeout(() => {
      progress.classList.remove('visible');
      progressFill.style.width = '0%';
    }, 3000);
  }
});

function renderResults(response) {
  const panel = document.getElementById('results-panel');
  panel.classList.add('visible');

  panel.innerHTML = response.account_results.map(ar => `
    <div class="result-account">
      <div class="result-account-header">
        <span>@${escapeHtml(ar.username)}</span>
        <span class="badge ${ar.failed > 0 ? 'badge-warning' : 'badge-success'}">
          ✅ ${ar.sent} &nbsp; ${ar.failed > 0 ? `❌ ${ar.failed}` : ''}
        </span>
      </div>
      <div class="result-items">
        ${ar.results.map(r => `
          <div class="result-item">
            <span class="result-icon">${r.status === 'ok' ? '✅' : '❌'}</span>
            <span class="result-group-name">${escapeHtml(r.group)}</span>
            <span class="result-status ${r.status}">${r.status === 'ok' ? 'Gönderildi' : r.message || 'Hata'}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');
}

// ─── Utility ─────────────────────────────────────────────────────────

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function escapeAttr(str) {
  return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ─── Init ────────────────────────────────────────────────────────────

initApp();
