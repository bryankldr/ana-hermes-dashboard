// ═══ LAYOUT MANAGER — drag, resize, lock, persist ═══
// Persist: layout.json di folder project (via /api/layout).

const LAYOUT_URL = '/api/layout';
const getToken = () => document.querySelector('meta[name="ana-token"]')?.content || '';
// Deteksi mobile TERPUSAT (device.js): matchMedia 780px, bukan innerWidth
// mentah — tanpa ini CSS 779px vs JS 780px off-by-one di tepi breakpoint.
import { deviceTier as _deviceTier } from './device.js';

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
    // Pair berdampingan (mis. response↔chatBar): geser satu = pasangannya
    // ikut; resize horizontal ikut; resize vertikal jaga tanpa tumpang.
    // opts.dockPair: ['response','chatBar']. Pair yang sama ikut z map.
    this.pairIds = Array.isArray(opts.dockPair) ? opts.dockPair.filter(id => typeof id === 'string') : [];
    this._pairDocked = false;
    this._pairHomeZ = null;
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
  // FASE 3 frac truth (konsep v3 §3): fx/fy/fw/fh 0-1 sumber tunggal,
  // x/y/w/h px cache. applyCfg pakai frac bila ada ( anti-drift lintas
  // viewport), px hanya fallback legacy.
  applyCfg(el, cfg) {
    if (!el || !cfg) return false;
    if (this.staticIds.has(el.id)) return false; // FASE 1: posisi dari CSS
    const pr = this.hud.getBoundingClientRect();
    const num = (v, d = 0) => parseFloat(String(v ?? '').replace('px', '')) || d;
    const fr = v => (typeof v === 'number' && Number.isFinite(v) ? v : null);
    let w, h, x, y;
    if (fr(cfg.fx) !== null && fr(cfg.fy) !== null && fr(cfg.fw) !== null && fr(cfg.fh) !== null && pr.width > 0 && pr.height > 0) {
      w = Math.min(cfg.fw * pr.width, Math.max(80, pr.width - 8));
      h = Math.min(cfg.fh * pr.height, Math.max(60, pr.height - 8));
      x = Math.min(Math.max(cfg.fx * pr.width, 0), Math.max(0, pr.width - w));
      y = Math.min(Math.max(cfg.fy * pr.height, 0), Math.max(0, pr.height - h));
    } else {
      if (!cfg.x && !cfg.y && !cfg.w && !cfg.h) return false;
      w = num(cfg.w, el.offsetWidth); h = num(cfg.h, el.offsetHeight);
      w = Math.min(w || el.offsetWidth, Math.max(80, pr.width - 8));
      h = Math.min(h || el.offsetHeight, Math.max(60, pr.height - 8));
      x = Math.min(Math.max(num(cfg.x), 0), Math.max(0, pr.width - w));
      y = Math.min(Math.max(num(cfg.y), 0), Math.max(0, pr.height - h));
    }
    el.style.left = x + 'px';
    el.style.top = y + 'px';
    el.style.width = w + 'px';
    el.style.height = h + 'px';
    el.dataset.free = '1';
    return true;
  }

  // FASE 2 slot per-user (konsep v3 §3/§4): tablet ikut slot mobile
  // (server cuma desktop|mobile; layout desktop penuh sesak di 820px).
  // Tanpa toggle manual — reload saat pindah mode.
  mode() { try { return _deviceTier() === 'desktop' ? 'desktop' : 'mobile'; } catch (_) { return window.innerWidth > 1180 ? 'desktop' : 'mobile'; } }

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
    const pr = this.hud.getBoundingClientRect();
    const layouts = {};
    for (const [id, el] of Object.entries(this.items)) {
      if (this.staticIds.has(id)) continue; // FASE 1: tidak disimpan
      // FASE 3 frac truth: normalisasi 0-1 terhadap .hud agar posisi
      // relatif lintas viewport (1440↔360). px ikut sebagai cache
      // legacy; applyCfg baca frac dulu bila ada.
      const num = v => parseFloat(String(v ?? '').replace('px', '')) || 0;
      let x = num(el.style.left), y = num(el.style.top);
      const w = num(el.style.width) || el.offsetWidth, h = num(el.style.height) || el.offsetHeight;
      let sx = el.style.left || '', sy = el.style.top || '';
      // Pair sedang dock di map: koordinatnya relatif-map — konversi balik
      // ke relatif-hud agar snapshot tetap kebenaran dashboard (reload aman).
      if (this._pairDocked && this.pairIds && this.pairIds.includes(id)) {
        const off = this._mapOffset();
        if (off) { x += off.dx; y += off.dy; sx = Math.round(x) + 'px'; sy = Math.round(y) + 'px'; }
      }
      layouts[id] = {
        x: sx, y: sy,
        w: el.style.width || '', h: el.style.height || '',
        ...(pr.width > 0 && pr.height > 0 ? {
          fx: +(x / pr.width).toFixed(4), fy: +(y / pr.height).toFixed(4),
          fw: +(w / pr.width).toFixed(4), fh: +(h / pr.height).toFixed(4),
        } : {}),
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

  // Pasangan pair dari panel yang sedang digeser/di-resize: null bila panel
  // bukan pair, pasangannya tak ada/tersembunyi. Drag = translasi kaku;
  // resize horizontal = kunci kolom (kiri+lebar sama); resize vertikal =
  // independen + dorong anti-tumpang.
  _followPartner(el) {
    if (!this.pairIds || this.pairIds.length !== 2 || !el) return null;
    const mine = el.dataset.layoutId || el.id;
    if (!this.pairIds.includes(mine)) return null;
    const other = this.pairIds[0] === mine ? this.pairIds[1] : this.pairIds[0];
    const p = this.items[other] || document.getElementById(other);
    if (!p || !p.isConnected) return null;
    try { if (getComputedStyle(p).display === 'none') return null; } catch (_) {}
    return p;
  }

  // Offset mapPanel terhadap .hud (untuk konversi koordinat pair saat
  // dock/undock/save). null bila map tak ada/tak terukur (display:none).
  _mapOffset() {
    try {
      const map = document.getElementById('mapPanel');
      if (!map || !map.isConnected) return null;
      const mr = map.getBoundingClientRect(), pr = this.hud.getBoundingClientRect();
      if (mr.width < 1 || mr.height < 1) return null;
      return { dx: mr.left - pr.left, dy: mr.top - pr.top };
    } catch (_) { return null; }
  }

  // Map AKTIF: pindahkan pair ke dalam #mapPanel (tanpa ubah ukuran/tampilan
  // visual) + z paling bawah di antara panel .flying (di atas ubin/pane).
  // Urutan pair dipertahankan (response di bawah chatBar, seperti dashboard).
  _dockPairInMap() {
    if (this._pairDocked) return true;
    if (!this.pairIds || this.pairIds.length !== 2) return false;
    const map = document.getElementById('mapPanel');
    if (!map || !map.isConnected) return false;
    const off = this._mapOffset();
    if (!off) return false;
    const els = this.pairIds.map(id => this.items[id] || document.getElementById(id));
    if (els.some(e => !e || !e.isConnected)) return false;
    this._pairHomeZ = {};
    for (const id of this.pairIds) {
      const e = this.items[id] || document.getElementById(id);
      this._pairHomeZ[id] = e.style.zIndex || '';
    }
    let minFly = 315;
    try {
      const zs = [...map.querySelectorAll('.flying')]
        .map(n => parseFloat(getComputedStyle(n).zIndex)).filter(Number.isFinite);
      if (zs.length) minFly = Math.min(...zs);
    } catch (_) {}
    this.pairIds.forEach((id, k) => {
      const e = this.items[id] || document.getElementById(id);
      const nx = (parseFloat(e.style.left) || 0) - off.dx;
      const ny = (parseFloat(e.style.top) || 0) - off.dy;
      if (e.parentElement !== map) map.appendChild(e);
      e.style.left = nx + 'px';
      e.style.top = ny + 'px';
      e.style.zIndex = String(Math.max(1, Math.round(minFly) - this.pairIds.length + k));
    });
    this._pairDocked = true;
    return true;
  }

  // Map DISABLE: kembalikan pair ke .hud pada posisi visual yang sama
  // (konversi balik) + z-index dashboard semula. Display tak disentuh
  // (hormati panel yang di-OFF dari menu).
  _undockPairToHud() {
    if (!this._pairDocked) return;
    const off = this._mapOffset();
    const homeZ = this._pairHomeZ || {};
    for (const id of (this.pairIds || [])) {
      const e = this.items[id] || document.getElementById(id);
      if (!e || !e.isConnected) continue;
      const nx = (parseFloat(e.style.left) || 0) + (off ? off.dx : 0);
      const ny = (parseFloat(e.style.top) || 0) + (off ? off.dy : 0);
      if (e.parentElement !== this.hud) this.hud.appendChild(e);
      e.style.left = this.snap(nx) + 'px';
      e.style.top = this.snap(ny) + 'px';
      if (homeZ[id]) e.style.zIndex = homeZ[id];
      else e.style.removeProperty('z-index');
    }
    this._pairDocked = false;
    this._pairHomeZ = null;
  }

  // Sinkronkan pair dengan status map kini: map tampil = dock, map
  // hilang/OFF = home dashboard. Aman dipanggil kapan saja (boot, toggle).
  syncPairWithMap() {
    try {
      const map = document.getElementById('mapPanel');
      const mapOn = !!map && map.isConnected && !this.disabled.has('mapPanel')
        && getComputedStyle(map).display !== 'none';
      if (mapOn) this._dockPairInMap();
      else this._undockPairToHud();
    } catch (_) {}
  }

  setPanelEnabled(id, enabled) {
    const el = this.items[id];
    if (!el) return;
    // Pair ikut map: undock DULU selagi rect map masih terukur (sebelum
    // display:none), agar posisi visual kembali 1:1 ke dashboard.
    if (id === 'mapPanel' && !enabled) { try { this._undockPairToHud(); } catch (_) {} }
    if (enabled) el.style.removeProperty('display');
    else el.style.setProperty('display', 'none', 'important');
    // #codeViewer visibility-nya dikendalikan class, bukan inline style:
    // .code-viewer{display:none} di hud.css, showCodeDiff() membukanya lewat
    // .visible. Tanpa ini, meng-ON dari menu tidak akan menampilkannya.
    if (el.classList.contains('code-viewer')) el.classList.toggle('visible', enabled);
    if (enabled) this.disabled.delete(id); else this.disabled.add(id);
    // Map dinyalakan: dock pair setelah display pulih (rect terukur).
    if (id === 'mapPanel' && enabled) { try { this._dockPairInMap(); } catch (_) {} }
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
    // Pair yang dock di map dijepit ke rect map (induknya kini); sisanya ke hud.
    let base = this.hud;
    try {
      if (this._pairDocked && this.pairIds && this.pairIds.includes(el.id)) {
        const map = document.getElementById('mapPanel');
        const mr = map?.getBoundingClientRect();
        if (map && mr && mr.width > 0 && mr.height > 0) base = map;
      }
    } catch (_) {}
    const pr = base.getBoundingClientRect();
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
    // Pair-follow: pasangan panel + posisi awalnya selama satu gesture.
    let pEl = null, pox = 0, poy = 0;
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
      // Pair-follow: kunci offset relatif (bulat) di awal gesture agar
      // pembulatan snap tak menumpuk jadi drift antar gesture.
      pEl = this._followPartner(el);
      pox = pEl ? (parseFloat(pEl.style.left) || 0) : 0;
      poy = pEl ? (parseFloat(pEl.style.top) || 0) : 0;
      if (pEl) {
        pEl._pairOffX = Math.round(pox - ((parseFloat(el.style.left)) || 0));
        pEl._pairOffY = Math.round(poy - ((parseFloat(el.style.top)) || 0));
      }
    };
    const onMove = e => {
      if (!mode || !el || (pid !== null && e.pointerId !== pid)) return;
      const dx = e.clientX - sx, dy = e.clientY - sy;
      if (mode === 'drag') {
        el.style.left = this.snap(ox + dx) + 'px';
        el.style.top = this.snap(oy + dy) + 'px';
        // Pair ikut dengan delta yang sama via offset terkunci — kedekatan
        // relatif utuh persis, tanpa drift pembulatan antar gesture.
        if (pEl && pEl.isConnected) {
          const elL = this.snap(ox + dx), elT = this.snap(oy + dy);
          pEl.style.left = (elL + (pEl._pairOffX || 0)) + 'px';
          pEl.style.top = (elT + (pEl._pairOffY || 0)) + 'px';
        }
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
      // Pair KOLOM TERKUNCI: resize horizontal (E/W) membuat kedua panel
      // SELARAS — kiri + lebar partner = kiri + lebar panel yang di-resize
      // (satu kolom utuh; atas + tinggi masing-masing tetap independen).
      // Resize vertikal tak mengubah pasangan — kecuali tabrakan: partner
      // didorong searah secukupnya (ukuran utuh, tetap berdampingan).
      if (pEl && pEl.isConnected) {
        if (dir.includes('e') || dir.includes('w')) {
          pEl.style.left = this.snap(x) + 'px';
          pEl.style.width = Math.max(this._minW(pEl), w) + 'px';
        }
        if (dir.includes('n') || dir.includes('s')) {
          const pn = v => parseFloat(v) || 0;
          const npx = pn(pEl.style.left), pw = pEl.offsetWidth, ph = pEl.offsetHeight;
          const hov = Math.min(x + w, npx + pw) - Math.max(x, npx);
          const vov = Math.min(y + h, poy + ph) - Math.max(y, poy);
          if (hov > 0 && vov > 0) {
            const pdir = (poy + ph / 2) <= (y + h / 2) ? -1 : 1;
            pEl.style.top = this.snap(poy + pdir * vov) + 'px';
          }
        }
      }
    };
    const onUp = e => {
      if (!mode || !el) return;
      if (pid !== null && e.pointerId !== undefined && e.pointerId !== pid) return;
      // reclamp() harus dipanggil SEBELUM el di-null-kan. Urutan yang
      // terbalik membuat reclam() selalu menerima null, jadi batas viewport
      // tidak pernah dipakai setelah drag berakhir.
      this.reclamp(el);
      el.classList.remove('dragging');
      // Pasangan ikut dijepit agar tetap terjangkau.
      if (pEl) { try { this.reclamp(pEl); } catch (_) {} }
      mode = null; el = null; pid = null; pEl = null;
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
