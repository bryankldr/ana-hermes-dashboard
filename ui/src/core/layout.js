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
    this._initRailCursor();
    this.injectHandles();
    this.bind();
    this.applyLock();
    this.loadConfig();
  }

  // Layout.json bisa berasal dari viewport lebih besar (monitor ganti, panel
  // di-drag saat layar lebar). Terapkan hanya yang masih muat; yang lain
  // dibiarkan pada positioning default hasil measure() — tidak ada cara user
  // menarik panel yang sudah jatuh di luar layar.
  applyCfg(el, cfg) {
    if (!el || !cfg) return false;
    const pr = this.hud.getBoundingClientRect();
    const num = (v, d = 0) => parseFloat(String(v ?? '').replace('px', '')) || d;
    const x = num(cfg.x), y = num(cfg.y);
    const w = num(cfg.w, el.offsetWidth), h = num(cfg.h, el.offsetHeight);
    if (x + w > pr.width + 1 || y + h > pr.height + 1) return false;
    if (cfg.x) el.style.left = cfg.x;
    if (cfg.y) el.style.top = cfg.y;
    if (cfg.w) el.style.width = cfg.w;
    if (cfg.h) el.style.height = cfg.h;
    el.dataset.free = '1';
    return true;
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
        this.applyCfg(this.items[id], cfg);
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
    // Width is still correct here: ensurePanel() appended the panel to its
    // rail and this reads the rect before the detach below. But by now
    // measure() has already emptied the rail, so a plain r.top just returns
    // the rail's own top and every dynamic panel lands on the same y. Use the
    // rail's stacking cursor instead — the only thing that still knows where
    // the rail's contents ended up.
    let x = r.left - pr.left;
    let y = r.top - pr.top;
    const cur = this.railCursor?.[el.dataset.rail];
    if (cur) { x = cur.x; y = cur.y; cur.y += r.height + 4; }
    if (el.parentElement !== this.hud) this.hud.appendChild(el);
    el.dataset.layoutId = id;
    el.style.position = 'absolute';
    el.style.left = x + 'px';
    el.style.top = y + 'px';
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
    this.applyCfg(el, this.config.layouts?.[id]);
  }

  // Where the next dynamic panel in this rail should start: just below the
  // lowest panel already placed in it. Must run after measure(), while the
  // static panels are still on record.
  _initRailCursor() {
    const pr = this.hud.getBoundingClientRect();
    this.railCursor = { left: null, right: null };
    for (const id of this.ids) {
      const el = this.items[id];
      if (!el || !el.getBoundingClientRect().width) continue;
      const r = el.getBoundingClientRect();
      const side = el.dataset.rail;
      if (!side) continue;
      const cur = this.railCursor[side]
        || (this.railCursor[side] = { x: r.left - pr.left, y: r.top - pr.top });
      cur.x = r.left - pr.left;
      cur.y = Math.max(cur.y, r.bottom - pr.top) + 4;
    }
  }

  measure() {
    // Two separate passes, and neither may mutate the DOM mid-measure:
    //  1. read every rect while each panel is still in its rail, so a panel
    //     reports its flex width (.left-rail 220px / .right-rail 240px) —
    //     re-parented under .hud it fills the full 1280px;
    //  2. only then detach them. Appending inside pass 1 would reflow the
    //     rail and shift every not-yet-measured sibling up to the rail top,
    //     so all of them would report the same y.
    const pr = this.hud.getBoundingClientRect();
    const boxes = [];
    for (const id of this.ids) {
      const el = document.getElementById(id);
      if (!el) continue;
      el.dataset.layoutId = id;
      // Remember the rail before the detach below empties it. Only panels that
      // actually live in a rail get a side — .core/.topControls/.eventLog are
      // direct children of .hud and must stay out of the stacking cursors.
      if (!el.dataset.rail) el.dataset.rail = el.closest('.left-rail') ? 'left'
        : el.closest('.right-rail') ? 'right' : '';
      this.items[id] = el;
      // A hidden element reports a 0×0 rect, and writing that back as inline
      // width/height pinned it at zero for good: #codeViewer ships display:none
      // and stayed 0px tall even after .visible was added, so the code diff
      // viewer rendered as a 2px sliver. Nothing hidden gets measured.
      if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') continue;
      const r = el.getBoundingClientRect();
      if (r.width < 1 && r.height < 1) continue;
      boxes.push([el, r.left - pr.left, r.top - pr.top, r.width, r.height]);
    }
    for (const [el, x, y, w, h] of boxes) {
      if (el.parentElement !== this.hud) this.hud.appendChild(el);
      el.style.position = 'absolute';
      el.style.left = x + 'px';
      el.style.top = y + 'px';
      el.style.width = w + 'px';
      el.style.height = h + 'px';
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
