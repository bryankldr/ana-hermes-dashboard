// ═══ LAYOUT MANAGER — drag, resize, lock, persist ═══
// Persist: layout.json di folder project (via /api/layout).

const LAYOUT_URL = '/api/layout';
const getToken = () => document.querySelector('meta[name="ana-token"]')?.content || '';

export class LayoutManager {
  constructor(hud, ids, opts = {}) {
    this.hud = hud;
    this.ids = [...ids];
    this.minW = opts.minW || 120;
    this.minH = opts.minH || 60;
    this.grid = opts.grid || 4;
    this.locked = true;
    this.config = { locked: true, layouts: {} };
    this.items = {};
    this.measure();
    this.injectHandles();
    this.bind();
    this.applyLock();
    this.loadConfig();
  }

  async loadConfig() {
    try {
      const res = await fetch(LAYOUT_URL, { headers: { 'X-Ana-Token': getToken() } });
      if (!res.ok) return;
      const data = await res.json();
      if (!data || typeof data !== 'object') return;
      this.config = { locked: !!data.locked, layouts: data.layouts || {} };
      this.locked = !!data.locked;
      for (const [id, cfg] of Object.entries(this.config.layouts)) {
        const el = this.items[id];
        if (!el || !cfg) continue;
        if (cfg.x) el.style.left = cfg.x;
        if (cfg.y) el.style.top = cfg.y;
        if (cfg.w) el.style.width = cfg.w;
        if (cfg.h) el.style.height = cfg.h;
        el.dataset.free = '1';
      }
      this.applyLock();
      const btn = document.getElementById('layoutLockBtn');
      if (btn) {
        btn.innerHTML = `<span class="toggle-icon">${this.locked ? '🔒' : '✎'}</span> ${this.locked ? 'Lock' : 'Unlock'}`;
        btn.classList.toggle('active', !this.locked);
      }
    } catch (_) {}
  }

  save() {
    const layouts = {};
    for (const [id, el] of Object.entries(this.items)) {
      layouts[id] = {
        x: el.style.left || '', y: el.style.top || '',
        w: el.style.width || '', h: el.style.height || '',
      };
    }
    this.config = { locked: this.locked, layouts };
    fetch(LAYOUT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ana-Token': getToken() },
      body: JSON.stringify(this.config),
    }).catch(() => {});
  }

  toggleLock() {
    this.locked = !this.locked;
    this.applyLock();
    this.save();
    return this.locked;
  }

  register(id) {
    const el = document.getElementById(id);
    if (!el || this.items[id]) return;
    this.ids.push(id);
    const r = el.getBoundingClientRect();
    const pr = this.hud.getBoundingClientRect();
    if (el.parentElement !== this.hud) this.hud.appendChild(el);
    el.dataset.layoutId = id;
    el.style.position = 'absolute';
    el.style.left = (r.left - pr.left) + 'px';
    el.style.top = (r.top - pr.top) + 'px';
    el.style.width = r.width + 'px';
    el.style.height = r.height + 'px';
    el.style.right = 'auto';
    el.style.bottom = 'auto';
    el.style.transform = 'none';
    el.style.margin = '0';
    el.style.flex = 'none';
    el.dataset.free = '1';
    this.items[id] = el;
    for (const dir of ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']) {
      const h = document.createElement('div');
      h.className = 'layout-handle handle-' + dir;
      h.dataset.dir = dir;
      el.appendChild(h);
    }
    const ind = document.createElement('span');
    ind.className = 'layout-lock-indicator';
    ind.textContent = '✎';
    el.appendChild(ind);
    // apply saved config if exists
    const cfg = this.config.layouts?.[id];
    if (cfg) {
      if (cfg.x) el.style.left = cfg.x;
      if (cfg.y) el.style.top = cfg.y;
      if (cfg.w) el.style.width = cfg.w;
      if (cfg.h) el.style.height = cfg.h;
    }
  }

  measure() {
    for (const id of this.ids) {
      const el = document.getElementById(id);
      if (!el) continue;
      if (el.parentElement !== this.hud) this.hud.appendChild(el);
    }
    for (const id of this.ids) {
      const el = document.getElementById(id);
      if (!el) continue;
      const r = el.getBoundingClientRect();
      const pr = this.hud.getBoundingClientRect();
      el.dataset.layoutId = id;
      this.items[id] = el;
      el.style.position = 'absolute';
      el.style.left = (r.left - pr.left) + 'px';
      el.style.top = (r.top - pr.top) + 'px';
      el.style.width = r.width + 'px';
      el.style.height = r.height + 'px';
      el.style.right = 'auto';
      el.style.bottom = 'auto';
      el.style.transform = 'none';
      el.style.margin = '0';
      el.style.flex = 'none';
      el.dataset.free = '1';
    }
  }

  injectHandles() {
    for (const el of Object.values(this.items)) {
      if (el.querySelector(':scope > .layout-handle')) continue;
      for (const dir of ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']) {
        const h = document.createElement('div');
        h.className = 'layout-handle handle-' + dir;
        h.dataset.dir = dir;
        el.appendChild(h);
      }
      const ind = document.createElement('span');
      ind.className = 'layout-lock-indicator';
      ind.textContent = '✎';
      el.appendChild(ind);
    }
  }

  snap(v) { return Math.round(v / this.grid) * this.grid; }

  applyLock() {
    this.hud.classList.toggle('layout-locked', this.locked);
    this.hud.classList.toggle('layout-unlocked', !this.locked);
    if (this.locked) document.getElementById('layout-grid-overlay')?.remove();
    else this.injectSnapOverlay();
  }

  injectSnapOverlay() {
    if (document.getElementById('layout-grid-overlay')) return;
    const ov = document.createElement('div');
    ov.id = 'layout-grid-overlay';
    ov.style.cssText =
      'position:fixed;inset:0;z-index:5000;pointer-events:none;' +
      'background-image:' +
      'linear-gradient(rgba(0,220,255,.06) 1px,transparent 1px),' +
      'linear-gradient(90deg,rgba(0,220,255,.06) 1px,transparent 1px);' +
      `background-size:${this.grid}px ${this.grid}px;`;
    document.body.appendChild(ov);
  }

  bind() {
    let mode = null, el = null, dir = null, sx = 0, sy = 0, ox = 0, oy = 0, ow = 0, oh = 0;
    const onDown = e => {
      if (this.locked) return;
      const t = e.target;
      if (t.classList?.contains('layout-handle')) {
        mode = 'resize'; el = t.closest('[data-layout-id]'); dir = t.dataset.dir;
      } else {
        el = t.closest('[data-layout-id]');
        if (!el) return;
        if (t.closest('button, input, select, textarea, a, canvas, .intel-terminal, .response-text, .event-entries')) return;
        mode = 'drag'; dir = null;
      }
      if (!el) return;
      e.preventDefault();
      el.classList.add('dragging');
      sx = e.clientX; sy = e.clientY;
      ox = parseFloat(el.style.left) || 0;
      oy = parseFloat(el.style.top) || 0;
      ow = el.offsetWidth; oh = el.offsetHeight;
    };
    const onMove = e => {
      if (!mode || !el) return;
      const dx = e.clientX - sx, dy = e.clientY - sy;
      if (mode === 'drag') {
        el.style.left = this.snap(ox + dx) + 'px';
        el.style.top = this.snap(oy + dy) + 'px';
        return;
      }
      let w = ow, h = oh, x = ox, y = oy;
      if (dir.includes('e')) w = Math.max(this.minW, ow + dx);
      if (dir.includes('s')) h = Math.max(this.minH, oh + dy);
      if (dir.includes('w')) { w = Math.max(this.minW, ow - dx); x = ox + (ow - w); }
      if (dir.includes('n')) { h = Math.max(this.minH, oh - dy); y = oy + (oh - h); }
      el.style.width = w + 'px';
      el.style.height = h + 'px';
      el.style.left = this.snap(x) + 'px';
      el.style.top = this.snap(y) + 'px';
    };
    const onUp = () => {
      if (!mode || !el) return;
      el.classList.remove('dragging');
      mode = null; el = null;
      this.save();
    };
    this.hud.addEventListener('mousedown', onDown);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }

  reset() {
    this.config = { locked: true, layouts: {} };
    fetch(LAYOUT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ana-Token': getToken() },
      body: JSON.stringify(this.config),
    }).catch(() => {});
    for (const el of Object.values(this.items)) el.removeAttribute('data-free');
    location.reload();
  }
}
