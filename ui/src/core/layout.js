// ═══ LAYOUT MANAGER — drag, resize, lock, persist ═══
// Persist: layout.json di folder project (via /api/layout).

const LAYOUT_URL = '/api/layout';
const getToken = () => document.querySelector('meta[name="ana-token"]')?.content || '';

export class LayoutManager {
  constructor(hud, ids, opts = {}) {
    this.hud = hud;
    this.ids = [...ids];
    // FASE 1 header-lock + map full-body: id statis tetap terdaftar (Options,
    // panel_access gate, disabled) tapi tidak ikut measure/posisi/drag/resize/
    // save. Posisi mereka murni dari CSS. Tanpa ini layout.json px menimpa CSS
    // tiap reload dan header ikut kegeser.
    this.staticIds = new Set(opts.static || []);
    this.minW = opts.minW || 120;
    this.minH = opts.minH || 60;
    this.grid = opts.grid || 4;
    this.locked = true;
    this.config = { locked: true, layouts: {}, disabled: [] };
    this.items = {};
    this.disabled = new Set();
    // Freed panels get an increasing z-index so they sit above the rails
    // (z-index:10). Counting up keeps the stacking order stable and identical
    // across reloads, so a saved layout looks the same every time.
    this.freeZ = 20;
    this.measure();
    this._initRailCursor();
    this.injectHandles();
    this.bind();
    this.applyLock();
    // loadConfig async: save() yang terjadi sebelum GET selesai akan menimpa
    // layout.json dengan disabled:[] kosong. save() menunda via _pendingSave.
    this._loaded = false;
    this._pendingSave = false;
    this.ready = this.loadConfig();
  }

  // Layout.json bisa berasal dari viewport lebih besar (monitor ganti, panel
  // di-drag saat layar lebar). Viewport lebih kecil (tablet): clamp ke dalam
  // layar, bukan tolak — posisi relatif dipertahankan, panel tetap terjangkau.
  applyCfg(el, cfg) {
    if (!el || !cfg) return false;
    if (this.staticIds.has(el.id)) return false; // FASE 1: posisi dari CSS
    if (!cfg.x && !cfg.y && !cfg.w && !cfg.h) return false;
    const pr = this.hud.getBoundingClientRect();
    const num = (v, d = 0) => parseFloat(String(v ?? '').replace('px', '')) || d;
    let w = num(cfg.w, el.offsetWidth), h = num(cfg.h, el.offsetHeight);
    w = Math.min(w || el.offsetWidth, Math.max(80, pr.width - 8));
    h = Math.min(h || el.offsetHeight, Math.max(60, pr.height - 8));
    const x = Math.min(Math.max(num(cfg.x), 0), Math.max(0, pr.width - w));
    const y = Math.min(Math.max(num(cfg.y), 0), Math.max(0, pr.height - h));
    el.style.left = x + 'px';
    el.style.top = y + 'px';
    el.style.width = w + 'px';
    el.style.height = h + 'px';
    el.dataset.free = '1';
    return true;
  }

  // FASE 2 slot per-user (konsep v3 §3/§4): mode dari viewport,
  // <780px = mobile. Tanpa toggle manual — reload saat pindah mode.
  mode() { return window.innerWidth < 780 ? 'mobile' : 'desktop'; }

  async loadConfig() {
    try {
      const res = await fetch(LAYOUT_URL, { headers: { 'X-Ana-Token': getToken() } });
      if (!res.ok) return;
      const data = await res.json();
      if (!data || typeof data !== 'object') return;
      this._mode = this.mode();
      // v3 {desktop:{layouts},mobile:{layouts}} atau legacy {layouts} (token-only).
      const slot = data[this._mode]?.layouts
        || (this._mode === 'mobile' && data.desktop?.layouts && Object.keys(data.mobile?.layouts || {}).length === 0
          ? data.desktop.layouts : null) // seed mobile pertama: copy desktop
        || data.layouts || {};
      this.config = { locked: !!data.locked, layouts: slot, disabled: data.disabled || [] };
      this.locked = !!data.locked;
      this.disabled = new Set(this.config.disabled);
      for (const [id, cfg] of Object.entries(this.config.layouts)) {
        this.applyCfg(this.items[id], cfg);
      }
      // setProperty('display', 'none', 'important'): beberapa panel punya
      // display !important di CSS (mis. .event-log{display:flex!important}) yang
      // menimpa inline style, jadi checkbox OFF tidak berefek. Prioritas inline
      // yang sama menang karena style sheet kalah dari inline !important.
      for (const id of this.disabled) {
        const el = this.items[id];
        if (el) el.style.setProperty('display', 'none', 'important');
      }
      this.applyLock();
      const btn = document.getElementById('layoutLockBtn');
      if (btn) {
        btn.innerHTML = `<span class="toggle-icon">${this.locked ? '🔒' : '✎'}</span>`;
        btn.title = this.locked ? 'Lock — layout terkunci' : 'Unlock — drag + resize aktif';
        btn.classList.toggle('active', !this.locked);
      }
      // Panel dinamis yang register() setelah loadConfig (mapPanel dkk)
      // tidak kebagian applyCfg/disabled. Terapkan ulang ke semua items.
      for (const [rid, el] of Object.entries(this.items)) {
        const cfg = this.config.layouts?.[rid];
        if (cfg) this.applyCfg(el, cfg);
        if (this.disabled.has(rid)) el.style.setProperty('display', 'none', 'important');
      }
    } catch (_) {}
    finally {
      this._loaded = true;
      if (this._pendingSave) { this._pendingSave = false; this.save(); }
    }
  }

  save() {
    // Config belum selesai di-GET: _pendingSave agar panel dinamis
    // (register setelah load) tidak menimpa layout.json dengan disabled kosong.
    if (!this._loaded) { this._pendingSave = true; return; }
    const layouts = {};
    for (const [id, el] of Object.entries(this.items)) {
      if (this.staticIds.has(id)) continue; // FASE 1: tidak disimpan
      layouts[id] = {
        x: el.style.left || '', y: el.style.top || '',
        w: el.style.width || '', h: el.style.height || '',
      };
    }
    this.config = { locked: this.locked, layouts, disabled: [...this.disabled] };
    fetch(LAYOUT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ana-Token': getToken() },
      // FASE 2: mode ikut — server tulis ke slot desktop|mobile file per-user.
      body: JSON.stringify({ ...this.config, mode: this._mode || this.mode() }),
    }).catch(() => {});
  }

  setPanelEnabled(id, enabled) {
    const el = this.items[id];
    if (!el) return;
    if (enabled) el.style.removeProperty('display');
    else el.style.setProperty('display', 'none', 'important');
    // #codeViewer visibility-nya dikendalikan class, bukan inline style:
    // .code-viewer{display:none} di hud.css, showCodeDiff() membukanya lewat
    // .visible. Tanpa ini, meng-ON dari menu tidak akan menampilkannya.
    if (el.classList.contains('code-viewer')) el.classList.toggle('visible', enabled);
    if (enabled) this.disabled.delete(id); else this.disabled.add(id);
    this.save();
  }

  // Overlay (codeViewer) ke lapisan atas semua panel: hanya naikkan z via
  // counter freeZ yang sama seperti panel lain. Posisi/ukuran/display tetap
  // aturan semula (centered overlay, hidden default) — tanpa Awak.
  bringToFront(id) {
    const el = this.items[id] || document.getElementById(id);
    if (!el) return;
    el.style.setProperty('z-index', String(this.freeZ++), 'important');
  }

  toggleLock() {
    this.locked = !this.locked;
    this.applyLock();
    this.save();
    return this.locked;
  }

  // Minimum size per panel. Default 60px ada untuk panel biasa; chat bar butuh
  // 41px supaya tinggi minimumnya benar-benar 1 baris (60px = 2 baris penuh).
  // Override per panel lewat atribut data-min-h di HTML/CSS.
  _minH(el) {
    const v = parseFloat(el.dataset.minH);
    return Number.isFinite(v) && v > 0 ? v : this.minH;
  }
  _minW(el) {
    const v = parseFloat(el.dataset.minW);
    return Number.isFinite(v) && v > 0 ? v : this.minW;
  }

  register(id) {
    const el = document.getElementById(id);
    if (!el) return;
    // Panel dibuat ulang (terminal close→open): ref lama sudah detached,
    // ikat ulang ke elemen baru. Panel yang masih menempel: skip.
    if (this.items[id]) {
      if (this.items[id].isConnected) return;
      delete this.items[id];
    }
    if (!this.ids.includes(id)) this.ids.push(id);
    // FASE 1: id statis (header + map full-body) hanya dicatat — tanpa
    // posisi/handle/z, tanpa simpan. Direparent ke .hud agar inset:0 CSS jalan.
    if (this.staticIds.has(id)) {
      if (el.parentElement !== this.hud) this.hud.appendChild(el);
      this.items[id] = el;
      if (this.disabled.has(id)) el.style.setProperty('display', 'none', 'important');
      return;
    }
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
    // z-index naik seperti panel lain agar drag/resize sama (RESPONSE)
    el.style.zIndex = String(this.freeZ++);
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
    const saved = this.config.layouts?.[id];
    if (saved) this.applyCfg(el, saved);
    if (this.disabled.has(id)) el.style.setProperty('display', 'none', 'important');
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
      // FASE 1: id statis tetap terdaftar untuk Options/gate, tapi posisi
      // murni CSS — tanpa data-layout-id (kebal drag) dan tanpa ukur.
      if (this.staticIds.has(id)) { this.items[id] = el; continue; }
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
      el.style.zIndex = String(this.freeZ++);
    }
  }

  injectHandles() {
    for (const [id, el] of Object.entries(this.items)) {
      if (this.staticIds.has(id)) continue;
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

  // A panel dragged past the edge of the window ends up outside the viewport,
  // where no cursor can reach it — the user cannot grab it back and has to hit
  // Reset. Pull it back far enough to always keep a grabbable strip on screen.
  reclamp(el) {
    if (!el) return;
    const pr = this.hud.getBoundingClientRect();
    const w = el.offsetWidth, h = el.offsetHeight;
    const num = v => parseFloat(v) || 0;
    let x = num(el.style.left), y = num(el.style.top);
    if (x > pr.width - 24) x = pr.width - 24;
    if (y > pr.height - 24) y = pr.height - 24;
    if (x < 24 - w) x = 24 - w;
    if (y < 24 - h) y = 24 - h;
    el.style.left = this.snap(x) + 'px';
    el.style.top = this.snap(y) + 'px';
  }

  bind() {
    let mode = null, el = null, dir = null, pid = null;
    let sx = 0, sy = 0, ox = 0, oy = 0, ow = 0, oh = 0;
    const onDown = e => {
      if (this.locked) return;
      if (mode) return; // satu gesture aktif — abaikan jari kedua
      const t = e.target;
      // Touch: drag hanya dari title bar / handle, supaya scroll body panel
      // dan gesture peta (Leaflet) tidak dibajak. Mouse: perilaku lama.
      const isTouch = e.pointerType === 'touch';
      if (t.classList?.contains('layout-handle')) {
        mode = 'resize'; el = t.closest('[data-layout-id]'); dir = t.dataset.dir;
      } else {
        el = t.closest('[data-layout-id]');
        if (!el) return;
        if (isTouch && !t.closest('.panel-title')) return;
        if (t.closest('button, input, select, textarea, a, canvas, .intel-terminal, .response-text, .event-entries')) return;
        mode = 'drag'; dir = null;
      }
      if (!el) return;
      e.preventDefault();
      pid = e.pointerId;
      el.classList.add('dragging');
      sx = e.clientX; sy = e.clientY;
      ox = parseFloat(el.style.left) || 0;
      oy = parseFloat(el.style.top) || 0;
      ow = el.offsetWidth; oh = el.offsetHeight;
    };
    const onMove = e => {
      if (!mode || !el || (pid !== null && e.pointerId !== pid)) return;
      const dx = e.clientX - sx, dy = e.clientY - sy;
      if (mode === 'drag') {
        el.style.left = this.snap(ox + dx) + 'px';
        el.style.top = this.snap(oy + dy) + 'px';
        return;
      }
      let w = ow, h = oh, x = ox, y = oy;
      const minW = this._minW(el), minH = this._minH(el);
      if (dir.includes('e')) w = Math.max(minW, ow + dx);
      if (dir.includes('s')) h = Math.max(minH, oh + dy);
      if (dir.includes('w')) { w = Math.max(minW, ow - dx); x = ox + (ow - w); }
      if (dir.includes('n')) { h = Math.max(minH, oh - dy); y = oy + (oh - h); }
      el.style.width = w + 'px';
      el.style.height = h + 'px';
      el.style.left = this.snap(x) + 'px';
      el.style.top = this.snap(y) + 'px';
    };
    const onUp = e => {
      if (!mode || !el) return;
      if (pid !== null && e.pointerId !== undefined && e.pointerId !== pid) return;
      // reclamp() harus dipanggil SEBELUM el di-null-kan. Urutan yang
      // terbalik membuat reclam() selalu menerima null, jadi batas viewport
      // tidak pernah dipakai setelah drag berakhir.
      this.reclamp(el);
      el.classList.remove('dragging');
      mode = null; el = null; pid = null;
      this.save();
    };
    // Pointer Events: satu jalur untuk mouse + touch (tablet).
    this.hud.addEventListener('pointerdown', onDown);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
  }

  reset() {
    this.config = { locked: true, layouts: {} };
    fetch(LAYOUT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Ana-Token': getToken() },
      body: JSON.stringify({ ...this.config, mode: this._mode || this.mode() }),
    }).catch(() => {});
    for (const el of Object.values(this.items)) el.removeAttribute('data-free');
    location.reload();
  }
}
