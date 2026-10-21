// Core API Client for Hermes Backend
// Device UUID persisten per browser (localStorage ana_device_id) dikirim
// sebagai X-Ana-Device di semua request. Server pakai ini + UA sebagai
// pengenal perangkat (UA saja tak cukup: Chrome laptop vs tablet identik).
// Tanpa ini dua perangkat UA-sama hidup bareng (evict tak jalan).
function anaDeviceId() {
  try {
    let d = localStorage.getItem('ana_device_id') || '';
    if (!/^[A-Za-z0-9_=-]{8,64}$/.test(d)) {
      d = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + '-' + Math.random().toString(36).slice(2)) + '';
      d = d.replace(/[^A-Za-z0-9_=-]/g, '').slice(0, 64);
      if (d.length < 8) d = 'dev-' + Math.random().toString(36).slice(2, 14);
      localStorage.setItem('ana_device_id', d);
    }
    return d;
  } catch { return ''; }
}
export class ApiClient {
  constructor() {
    // Auth browser = cookie sesi HttpOnly. Master token TIDAK ada di klien.
    this.token = '';
    this.evictedHandler = null; // dipasang main.js: banner + ambil alih
  }
  headers(extra = {}) {
    const h = { 'content-type': 'application/json', ...extra };
    if (this.token) h['x-ana-token'] = this.token;
    try {
      const d = anaDeviceId();
      if (d) h['X-Ana-Device'] = d;
    } catch {}
    return h;
  }
  async _fetch(path, opts = {}) {
    const init = { credentials: 'same-origin', ...opts };
    init.headers = { ...this.headers(), ...(opts.headers || {}) };
    const r = await fetch(path, init);
    if (r.status === 401 && !path.startsWith('/api/auth/') && !path.startsWith('/api/token-status')) {
      // Bedakan reason: evicted_by_new_device → banner + ambil alih
      // (JANGAN redirect buta). expired → refresh seperti dulu.
      let reason = '';
      try {
        const j = await r.clone().json();
        reason = j?.error || j?.reason || '';
        if (reason === 'evicted_by_new_device' && typeof this.evictedHandler === 'function') {
          try { this.evictedHandler(j); } catch {}
          return r; // biarkan pemanggil baca body evict
        }
      } catch {}
      if (reason === 'evicted_by_new_device') return r;
      try {
        const rr = await fetch('/api/auth/refresh', { method: 'POST', credentials: 'same-origin', headers: this.headers() });
        if (rr.ok) return fetch(path, init);
      } catch {}
      if (!location.pathname.endsWith('login.html')) {
        const next = encodeURIComponent(location.pathname + location.search);
        location.href = '/login.html?next=' + next;
      }
    }
    return r;
  }
  async getStatus() {
    const res = await this._fetch('/api/status');
    return res.json();
  }
  async getProjects() {
    const res = await this._fetch('/api/projects');
    return res.json();
  }
  async getBriefing() {
    const res = await this._fetch('/api/briefing');
    return res.json();
  }
  async getJobs() {
    const res = await this._fetch('/api/jobs');
    return res.json();
  }
  async getSessions() {
    const res = await this._fetch('/api/sessions');
    return res.json();
  }
  async getVault() {
    const res = await this._fetch('/api/vault');
    return res.json();
  }
  async getAvd() {
    const res = await this._fetch('/api/avd');
    return res.json();
  }
  async avdAction(action) {
    const res = await this._fetch('/api/avd', { method: 'POST', body: JSON.stringify({ action }) });
    return res.json();
  }
  async restart() {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 5000);
    try {
      const res = await this._fetch('/api/restart', { method: 'POST', body: '{}', signal: ctl.signal });
      return res.json();
    } catch (e) {
      return { ok: true, restarting: true, _assumed: true };
    } finally {
      clearTimeout(t);
    }
  }
  async getMissions() {
    const res = await this._fetch('/api/missions');
    return res.json();
  }
  async mapState() {
    const res = await this._fetch('/api/map/state');
    return res.json();
  }
  async mapCommand(op, args = {}) {
    const res = await this._fetch('/api/map/command', {
      method: 'POST',
      body: JSON.stringify({ op, args }),
    });
    return res.json();
  }
  async mapResult(id) {
    const res = await this._fetch('/api/map/result?id=' + encodeURIComponent(id));
    return res.json();
  }
  async setSession(sessionId) {
    const res = await this._fetch('/api/session', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId })
    });
    const data = await res.json();
    if (data.ok) {
      if (data.session) {
        localStorage.setItem('ana_session', JSON.stringify({ id: data.session, meta: data.meta, ts: Date.now() }));
      } else {
        localStorage.removeItem('ana_session');
      }
      window.dispatchEvent(new StorageEvent('storage', { key: 'ana_session', newValue: localStorage.getItem('ana_session') }));
    }
    return data;
  }
  async post(path, body = {}) {
    const res = await this._fetch(path, {
      method: 'POST',
      body: JSON.stringify(body)
    });
    return res.json();
  }
  async get(path) {
    const res = await this._fetch(path);
    return res.json();
  }
  async setMode(mode) {
    const res = await this._fetch('/api/mode', {
      method: 'POST',
      body: JSON.stringify({ mode })
    });
    return res.json();
  }
  async getDbSource() {
    const res = await this._fetch('/api/db-source');
    return res.json();
  }
  async setDbSource(source) {
    const res = await this._fetch('/api/db-source', {
      method: 'POST',
      body: JSON.stringify({ source })
    });
    return res.json();
  }
  async setVoice(voice_id) {
    const res = await this._fetch('/api/voice', {
      method: 'POST',
      body: JSON.stringify({ voice_id })
    });
    return res.json();
  }
  async runStream(message, onEvent, onError) {
    try {
      const res = await this._fetch('/api/run', {
        method: 'POST',
        body: JSON.stringify({ message })
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf('\n')) >= 0) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (line) {
            try { onEvent(JSON.parse(line)); } catch (e) {}
          }
        }
      }
    } catch (err) {
      if (onError) onError(err);
    }
  }
  async authMe() {
    const r = await fetch('/api/auth/me', { credentials: 'same-origin', cache: 'no-store' });
    if (!r.ok) return null;
    try { return await r.json(); } catch { return null; }
  }
  async authLogout() {
    const r = await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
    try { return await r.json(); } catch { return {}; }
  }
}
export const api = new ApiClient();
