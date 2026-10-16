// ui/src/map.js — SPATIAL MAP panel (petak KPHBWB). Business Intelligence dashboard.
// HUD = dashboard dev (mode coding). Panel ini = dashboard BI (mode-aware).
// Panel via ensurePanel() -> auto LayoutManager. Leaflet engine via mapControl.js.
import { ensurePanel } from './utils/dom.js';
import { esc } from './utils/helpers.js';
import { bus, state as busState } from './core/bus.js';
import { createLeafletControl } from './mapControl.js';
import {
  BUSINESS_OPTIONS, katOptionsFor,
  getSpatialState, setBusiness, setFilters, setDataset, setMetrics, subscribeSpatial
} from './spatialMapState.js';
import { loadBusinessData, fetchWilayahOptions, fetchAktivitasPoints, resolveTemplate, queryStats } from './businessAdapter.js';
import { initSpatialChart } from './spatialChart.js';
import { initSpatialReport } from './spatialReport.js';
import { initSpatialArchive } from './spatialArchive.js';
import { isMobile as _isMobileDevice } from './core/device.js';

const CENTER = [-8.1915, 114.1491];
const BASE_STYLE = { color: '#2DF2FF', weight: 1, opacity: 0.8, fillColor: '#2DF2FF', fillOpacity: 0.12 };
let _built = false;
let _ctl = null;

export function mapControl() { return _ctl; }

// ANA full control Toolbar atas + Panel Filter + Pencarian petak.
// Op spatial_* di-intercept poll/_drainBusinessQueue ke handler ini
// (bukan method _ctl). Diregistrasi initMapPanel setelah reloadBusiness ada.
let _spatialHandler = null;
export function setSpatialHandler(fn) { _spatialHandler = (typeof fn === 'function') ? fn : null; }

const MAP_BRIDGE_MS = 400;
let _bridgeTimer = null;
// ANA bisa push set_features mentah (template di luar _TEMPLATE_SPATIAL, mis.
// aktivitas_top_petak). Feature count-nya BERBEDA dari load panel sendiri, jadi
// watchdog render panel akan salah menilainya "gagal". Hook ini membatalkan
// _awaitingFeatures/_renderWatchdog — peta jadi milik ANA selama push itu berlaku.
let _onExternalFeatures = null;
export function setExternalFeaturesHook(fn) { _onExternalFeatures = (typeof fn === 'function') ? fn : null; }
export function startMapBridge({ token = '', log = () => {} } = {}) {
  if (_bridgeTimer) return;
  const headers = () => ({ 'X-Ana-Token': token, 'Content-Type': 'application/json' });
  let _pushThrottle = 0;
  const pushState = async () => {
    if (!_ctl || Date.now() - _pushThrottle < 4000) return;
    _pushThrottle = Date.now();
    try {
      await fetch('/api/map/state', {
        method: 'POST', headers: headers(), credentials: 'same-origin',
        body: JSON.stringify({ state: _ctl.get_state() }),
      });
    } catch (_) {}
  };
  const poll = async () => {
    if (!_ctl) return;
    try {
      const r = await fetch('/api/map/queue', { headers: { 'X-Ana-Token': token }, credentials: 'same-origin' });
      if (!r.ok) return;
      const { commands = [] } = await r.json();
      for (const cmd of commands) {
        // ANA full control Toolbar/Filter/Search — intercept sebelum _ctl (bukan method LeafletAdapter)
        // load_viewport is also intercepted since it triggers spatial state + reload via _spatialHandler
        if (cmd.op && (cmd.op.indexOf('spatial_') === 0 || cmd.op === 'load_viewport')) {
          let _ok = true, _data = null, _err = '';
          try {
            if (typeof _spatialHandler !== 'function') throw new Error('panel spatial belum siap');
            _data = await _spatialHandler(cmd.op, cmd.args || {});
          } catch (e) { _ok = false; _err = String((e && e.message) || e).slice(0, 200); }
          try {
            await fetch('/api/map/result', {
              method: 'POST', headers: headers(), credentials: 'same-origin',
              body: JSON.stringify(_ok ? { id: cmd.id, ok: true, data: _data || {} } : { id: cmd.id, ok: false, error: _err }),
            });
          } catch (_) {}
          log('map', 'MAP', 'ANA spatial -> ' + cmd.op + (_ok ? '' : ' gagal: ' + _err));
          continue;
        }
        const fn = _ctl[cmd.op];
        if (typeof fn !== 'function') {
          await fetch('/api/map/result', {
            method: 'POST', headers: headers(), credentials: 'same-origin',
            body: JSON.stringify({ id: cmd.id, ok: false, error: 'op tidak dikenal di adapter: ' + cmd.op }),
          });
          continue;
        }
        const a = cmd.args || {};
        const one = (...keys) => { for (const k of keys) if (a[k] !== undefined) return a[k]; return undefined; };
        let callArgs = [a];
        if (cmd.op === 'set_features') {
          // abort watchdog render milik panel — push ANA yang berlaku sekarang
          if (typeof _onExternalFeatures === 'function') { try { _onExternalFeatures(); } catch (_) {} }
          // teruskan mode render panel (full:false = incremental pan/zoom):
          // bridge default fit:true bikin snapback tiap pan bila flag hilang.
          callArgs = [a.geojson ?? a, { fit: a.fit ?? true, pad: a.pad, style: a.style, ...(a.full === false ? { full: false } : {}) }];
        }
        else if (['clear_features', 'clear_filter'].includes(cmd.op)) callArgs = [];
        else if (cmd.op === 'fit_bounds') callArgs = [a.bounds ?? a];
        else if (cmd.op === 'fit_all') callArgs = [a.pad ?? 0.05];
        else if (cmd.op === 'set_layer_visibility') callArgs = [a.id, a.visible];
        else if (['toggle_layer', 'set_basemap', 'select_feature'].includes(cmd.op)) callArgs = [one('id')];
        else if (cmd.op === 'highlight_features') callArgs = [one('ids', 'id')];
        else if (cmd.op === 'set_filter') callArgs = [one('query', 'q')];
        else if (['get_state', 'reset_view', 'get_layers', 'get_selected', 'clear_selection', 'clear_highlights'].includes(cmd.op)) callArgs = [];
        else if (cmd.op === 'set_aktivitas_points') callArgs = [a.points ?? a.rows ?? a.geojson ?? a, { token: a.token }];
        else if (cmd.op === 'clear_aktivitas_points') callArgs = [];
        else if (cmd.op === 'set_aktivitas_visibility') callArgs = [a.visible ?? a.value ?? true];
        try {
          const data = await fn.apply(_ctl, callArgs);
          await fetch('/api/map/result', {
            method: 'POST', headers: headers(), credentials: 'same-origin',
            body: JSON.stringify({ id: cmd.id, ok: true, data }),
          });
          log('map', 'MAP', 'ANA -> ' + cmd.op);
        } catch (e) {
          await fetch('/api/map/result', {
            method: 'POST', headers: headers(), credentials: 'same-origin',
            body: JSON.stringify({ id: cmd.id, ok: false, error: String(e?.message || e).slice(0, 200) }),
          });
          log('map', 'MAP', 'ANA -> ' + cmd.op + ' gagal: ' + String(e?.message || e).slice(0, 80));
        }
      }
      if (commands.length) pushState();
    } catch (_) {}
  };
  _bridgeTimer = setInterval(poll, MAP_BRIDGE_MS);
  setTimeout(pushState, 3000);
  try { window.addEventListener('anaMapViewChanged', pushState); } catch (_) {}
}

function _opts(list, selected) {
  return list.map(o => '<option value="' + esc(o.value) + '" ' + (String(o.value)===String(selected)?'selected':'') + '>' + esc(o.label || o.value) + '</option>').join('');
}
function _numOpts(range, sel) {
  return range.map(v => '<option value="' + v + '" ' + (String(v)===String(sel)?'selected':'') + '>' + v + '</option>').join('');
}
function _curMode() {
  try { const d = document.documentElement.getAttribute('data-ana-mode'); if (d) return d; } catch (_) {}
  try { if (busState && busState.mode) return busState.mode; } catch (_) {}
  return 'coding';
}

export function initMapPanel({ log = () => {} } = {}) {
  if (_built) {
    const ex = document.getElementById('mapPanel');
    if (ex) { return ex; }
  }
  const bizOpts = _opts(BUSINESS_OPTIONS, 'petak');
  const katOpts = _opts(katOptionsFor('petak'), 'semua');
  const d0 = new Date();
  const curPer = d0.getDate() <= 15 ? '1' : '2';
  const el = ensurePanel({
    id: 'mapPanel', title: 'SPATIAL MAP', rail: 'right',
    body: ''
      + '<div class="map-wrap map-full">'
      + '  <div id="mapBox"></div>'
      + '  <div class="map-fly map-fly-top" aria-label="filter">'
      + '    <button id="spatialToolsToggle" class="spatial-toggle-btn active" title="Tampil/sembunyi toolbar" aria-label="Tampil/sembunyi toolbar"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="6" x2="20" y2="6"/><circle cx="9" cy="6" r="2" fill="rgba(2,15,42,.88)"/><line x1="4" y1="12" x2="20" y2="12"/><circle cx="15" cy="12" r="2" fill="rgba(2,15,42,.88)"/><line x1="4" y1="18" x2="20" y2="18"/><circle cx="7" cy="18" r="2" fill="rgba(2,15,42,.88)"/></svg></button>'
      + '    <div class="spatial-toolbar flying">'
      + '      <select id="spatialBiz" class="spatial-select" title="Kategori bisnis">' + bizOpts + '</select>'
      + '      <select id="spatialKat" class="spatial-select" title="Layer petak">' + katOpts + '</select>'
      + '      <button id="spatialFilterBtn" class="spatial-btn" title="Filter" aria-label="Filter"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.5 10 19 14 21 14 12.5"/></svg></button>'
      + '      <button id="spatialKpiBtn" class="spatial-btn ghost" title="KPI">KPI</button>'
      + '      <button id="spatialRefresh" class="spatial-btn" title="Muat ulang" aria-label="Muat ulang"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg></button>'
      + '    </div>'
      + '    <div id="spatialTilesModal" class="spatial-tiles-modal hidden" role="dialog" aria-label="Pengaturan tiles">'
      + '      <div class="spatial-tiles-card">'
      + '        <div class="spatial-tiles-head"><span>Pengaturan Tiles</span><button id="spatialTilesClose" class="spatial-btn ghost" title="Tutup">✕</button></div>'
      + '        <div id="spatialTilesStatus" class="spatial-tiles-status">memuat…</div>'
      + '        <label class="spatial-tiles-row">Jadwal cron <input id="spatialTilesSched" class="spatial-mini" value="10 6 * * *" spellcheck="false" style="width:120px"></label>'
      + '        <div class="spatial-tiles-row">'
      + '          <button id="spatialTilesRebuild" class="spatial-btn">Rebuild manual</button>'
      + '          <button id="spatialTilesCronOn" class="spatial-btn">Aktifkan cron</button>'
      + '          <button id="spatialTilesCronOff" class="spatial-btn ghost">Matikan cron</button>'
      + '        </div>'
      + '        <div id="spatialTilesMsg" class="spatial-tiles-msg"></div>'
      + '      </div>'
      + '    </div>'
      + '    <div id="spatialFilters" class="spatial-filters flying collapsed">'
      + '      <div class="spatial-fgroup">'
      + '        <div class="spatial-fgroup-title">Waktu <span class="spatial-hint">periode bisnis P1 1-15 / P2 16-akhir / Penuh 1-akhir</span></div>'
      + '        <div class="spatial-row cols4">'
      + '          <label>Tahun <select id="fTahun" class="spatial-mini w-year"><option value="2026" selected>2026</option><option value="2025">2025</option></select></label>'
      + '          <label>Bulan <select id="fBulan" class="spatial-mini w-month">' + _numOpts([1,2,3,4,5,6,7,8,9,10,11,12], d0.getMonth()+1) + '</select></label>'
      + '          <label>Sampai dengan <select id="fSampai" class="spatial-mini" title="Ya = Jan s/d periode · Tidak = periode saja"><option value="">Auto</option><option value="ya">Ya</option><option value="tidak">Tidak</option></select></label>'
      + '          <label>Periode <select id="fPeriode" class="spatial-mini"><option value="0">Penuh (P1+P2)</option><option value="1">P1 (1-15)</option><option value="2">P2 (16-akhir)</option></select></label>'
      + '        </div>'
      + '      </div>'
      + '      <div class="spatial-fgroup">'
      + '        <div class="spatial-fgroup-title">AKTIVITAS <span class="spatial-hint">filter pin + polygon; DB punya 1/2/3</span></div>'
      + '        <div class="spatial-row">'
      + '          <label>Pembaharuan <select id="fPemKe" class="spatial-mini"><option value="">Semua</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option></select></label>'
      + '          <label>Aktivitas <select id="fJenisAkt" class="spatial-mini"><option value="">Semua</option><option value="quare">Quare</option><option value="semprot_cas">Semprot Cas</option><option value="kerok">Kerok</option><option value="naik_batok">Naik Batok</option><option value="budaya_bersih">Budaya Bersih</option><option value="pulung">Pulung</option></select></label>'
      + '        </div>'
      + '      </div>'
      + '      <div class="spatial-fgroup">'
      + '        <div class="spatial-fgroup-title">WILAYAH <span class="spatial-hint">scoped hanya SPATIAL MAP</span></div>'
      + '        <div class="spatial-row">'
      + '          <label>DIVRE <select id="fDivre" class="spatial-mini"><option value="">Semua</option></select></label>'
      + '          <label>KPH <select id="fKph" class="spatial-mini"><option value="">Semua</option></select></label>'
      + '          <label>BKPH <select id="fBkph" class="spatial-mini"><option value="">Semua</option></select></label>'
      + '        </div>'
      + '        <div class="spatial-row">'
      + '          <label>RPH <select id="fRph" class="spatial-mini"><option value="">Semua</option></select></label>'
      + '          <label>TPG <select id="fTpg" class="spatial-mini"><option value="">Semua</option></select></label>'
      + '          <button id="fApply" class="spatial-btn" style="margin-left:auto">Terapkan</button>'
      + '          <button id="fReset" class="spatial-btn danger">Reset</button>'
      + '        </div>'
      + '        <div class="spatial-wilstatus" id="spatialWilStatus" hidden></div>'
      + '      </div>'
      + '      <div id="spatialChips" class="spatial-chips"></div>'
      + '    </div>'
      + '    <div class="map-tools flying"><input id="mapSearch" placeholder="Cari No Petak…" autocomplete="off"><button id="mapFit" title="fit ke semua petak">◎</button></div>'
      + '  </div>'
      + '  <div id="spatialProgress" class="spatial-progress flying hidden" aria-live="polite"><div class="sp-bar"><div id="spBarFill" class="sp-fill" style="width:0%"></div></div><div id="spLabel" class="sp-label">siap</div></div>'
      + '  <div class="map-bottom-bar">'
      + '    <div id="spatialKpi" class="spatial-kpi flying">'
      + '      <div class="kpi"><div class="kpi-label">Total</div><div class="kpi-value" id="kpiTotal">-</div><div class="kpi-sub" id="kpiTotalSub">memuat</div></div>'
      + '      <div class="kpi"><div class="kpi-label" id="kpi2Label">Bongkor</div><div class="kpi-value warn" id="kpi2">-</div><div class="kpi-sub" id="kpi2Sub">merah</div></div>'
      + '      <div class="kpi"><div class="kpi-label" id="kpi3Label">Perhatian</div><div class="kpi-value mid" id="kpi3">-</div><div class="kpi-sub" id="kpi3Sub">kuning/oranye</div></div>'
      + '      <div class="kpi"><div class="kpi-label" id="kpi4Label">Terpenuhi</div><div class="kpi-value ok" id="kpi4">-</div><div class="kpi-sub" id="kpi4Sub">hijau/biru</div></div>'
      + '    </div>'
      + '    <div id="spatialInsight" class="spatial-insight flying"></div>'
      + '    <div class="map-legendbox flying">'
      + '      <div class="map-legend flying" id="mapLegend"></div>'
      + '      <div class="map-meta flying"><span id="mapMetric" class="map-metric">-</span><span id="mapStat" class="map-stat">siap</span></div>'
      + '    </div>'
      + '  </div>'
      + '</div>',
  });
  // Header panel asli SPATIAL MAP — BUSINESS INTELLIGENCE + periode + mode ANA (bukan panel baru di map)
  try {
    const head = el.querySelector('.panel-title');
    if (head && !head.querySelector('#shPeriode')) {
      head.style.display = 'flex';
      head.style.alignItems = 'center';
      head.style.justifyContent = 'space-between';
      head.style.gap = '8px';
      const curP = d0.getDate() <= 15 ? '1' : '2';
      const perTxt = d0.getFullYear() + '-' + String(d0.getMonth()+1).padStart(2,'0') + '-P' + curP;
      // bungkus judul asli
      const titleText = head.textContent.trim() || 'SPATIAL MAP';
      head.innerHTML = '<span style="display:flex;align-items:center;gap:8px;"><span>SPATIAL MAP</span><span class="sh-title" style="font-family:var(--font-disp);font-size:7px;letter-spacing:.12em;color:var(--text-dim);opacity:.9">BUSINESS INTELLIGENCE</span></span>'
        + '<span class="sh-badges" style="display:flex;gap:4px;align-items:center"><span id="shPeriode" class="sh-badge periode">' + perTxt + '</span><span id="shMode" class="sh-badge mode-coding">CODING</span><button id="spatialTilesBtn" class="sh-tiles" title="Pengaturan tiles (rebuild + cron harian)" aria-label="Pengaturan tiles">⚙</button></span>';
    }
  } catch(_) {}
  _built = true;
  const box = el.querySelector('#mapBox');
  const stat = el.querySelector('#mapStat');
  const metric = el.querySelector('#mapMetric');
  const legend = el.querySelector('#mapLegend');
  if (!box) return el;
  if (!window.L) {
    if (stat) stat.textContent = 'leaflet gagal dimuat';
    return el;
  }
  const map = window.L.map(box, {
    zoomControl: false, attributionControl: false,
    // Canvas renderer: ratusan polygon + ribuan pin/garis tetap mulus
    // (SVG = ribuan node DOM = jank tiap render/zoom). Popup/tooltip/
    // dash/bringToFront tetap didukung. Animasi zoom/pan eksplisit.
    preferCanvas: true, zoomAnimation: true, fadeAnimation: true, inertia: true,
  }).setView(CENTER, 11);
  const dark = window.L.tileLayer('/api/tiles/esri/dark/{z}/{x}/{y}', { maxZoom: 18, attribution: 'Esri' });
  const sat = window.L.tileLayer('/api/tiles/esri/sat/{z}/{x}/{y}', { maxZoom: 18, attribution: 'Esri, Maxar, Earthstar Geographics' });
  // Label di pane sendiri: filter redup imagery tak kena teks (cegah halo/bayangan).
  try { map.createPane('labelPane'); const lp = map.getPane('labelPane'); if (lp) { lp.style.zIndex = 250; lp.style.pointerEvents = 'none'; } } catch(_) {}
  const refLbl = window.L.tileLayer('/api/tiles/esri/ref/{z}/{x}/{y}', { maxZoom: 18, pane: 'labelPane' });
  const petakLayer = window.L.layerGroup();
  const satGroup = window.L.layerGroup([sat]);
  const darkGroup = window.L.layerGroup([dark]);
  // Offline-first: ubin Esri (satelit/gelap/label) hanya dipasang bila host-nya
  // reachable. Hasil probe DIINGAT di localStorage: jaringan blokir = cukup
  // SATU error sekali, load berikut NOL request + NOL error. Tanpa ingatan,
  // tiap load mengulang probe yang diblokir (= error abadi di console).
  // Pulih otomatis: tile satelit yang sukses load menandai reachable lagi.
  const ESRI_KEY = 'ana_esri_ok';
  const esriRemembered = (() => {
    try { return window.localStorage.getItem(ESRI_KEY); } catch (_) { return null; }
  })();
  const esriRemember = (v) => {
    try { window.localStorage.setItem(ESRI_KEY, v ? '1' : '0'); } catch (_) {}
  };
  try { sat.on('load', () => esriRemember(true)); } catch (_) {}
  // Demote otomatis: bila Esri tiba-tiba diblokir (jaringan pindah), turunkan
  // ke mode lokal + ingat — error tile tak berulang tiap load berikutnya.
  try {
    let errN = 0;
    const onTileErr = () => {
      if (++errN < 4) return;
      esriRemember(false);
      try { map.removeLayer(satGroup); map.removeLayer(refLbl); } catch (_) {}
      try { log('map', 'BASEMAP', 'Esri gagal — turun ke mode lokal'); } catch (_) {}
    };
    sat.on('tileerror', onTileErr);
    refLbl.on('tileerror', onTileErr);
  } catch (_) {}
  if (esriRemembered === '1') {
    try { satGroup.addTo(map); refLbl.addTo(map); } catch (_) {}
  } else if (esriRemembered !== '0') {
    try {
      const ctrl = ('AbortController' in window) ? new AbortController() : null;
      const timer = setTimeout(() => { try { ctrl && ctrl.abort(); } catch (_) {} }, 3500);
      // Probe via PROXY same-origin (server teruskan ke Esri): gagal = server
      // tak mencapai Esri ATAU offline total → mode lokal. Same-origin =
      // tak pernah diblokir adblock/DNS; r.ok=false (502) = tak reachable.
      fetch('/api/tiles/esri/sat/0/0/0', Object.assign({ cache: 'no-store' }, ctrl ? { signal: ctrl.signal } : {})
      ).then(
        (r) => {
          if (!r || !r.ok) throw new Error('esri-proxy ' + (r && r.status));
          clearTimeout(timer); esriRemember(true);
          try {
            if (!map || !map.getContainer || !map.getContainer().isConnected) return;
            satGroup.addTo(map);
            refLbl.addTo(map); // satu sumber label, default ON — cegah dobel/bayangan
          } catch (_) {}
        },
        () => { clearTimeout(timer); esriRemember(false); }
      );
    } catch (_) {
      try { satGroup.addTo(map); refLbl.addTo(map); } catch (_) {}
    }
  }
  try { log('map', 'BASEMAP', esriRemembered === '0' ? 'Esri diblokir (tersimpan) — mode lokal' : 'basemap Esri aktif/dicek'); } catch (_) {}
  petakLayer.addTo(map);
  window.L.control.scale({ position: 'topright' }).addTo(map);
  window.L.control.layers({ 'Satelit': satGroup, 'Gelap': darkGroup }, { 'Petak': petakLayer, 'Label': refLbl }, { position: 'topright' }).addTo(map);
  window.L.control.zoom({ position: 'topright' }).addTo(map);
  // zoom-badge: info zoom + tier di SEBELAH KIRI skala, tanpa background
  // (teks putih + shadow, baca di atas satelit). Urutan kolom:
  // baris [badge | skala] → layers → zoom.
  (function(){
    try {
      const zb = document.createElement('div');
      zb.id = 'zoomBadge'; zb.className = 'zoom-badge';
      zb.textContent = 'Z' + map.getZoom();
      const tr = box.querySelector('.leaflet-top.leaflet-right');
      if (tr) {
        const sc = tr.querySelector('.leaflet-control-scale');
        const ly = tr.querySelector('.leaflet-control-layers');
        const zm = tr.querySelector('.leaflet-control-zoom');
        const row = document.createElement('div');
        row.className = 'zs-row';
        row.appendChild(zb);
        if (sc) row.appendChild(sc);
        tr.append(row);
        if (ly) tr.appendChild(ly);
        if (zm) tr.appendChild(zm);
      } else box.appendChild(zb);
      window.__anaZoomBadge = zb;
      const upd = () => { try { const z = map.getZoom(); const t = (z <= 11 ? 'PMTiles' : 'GeoJSON'); zb.textContent = 'Z' + z + ' \u00b7 ' + t; zb.dataset.zoom = String(z); } catch(_){} };
      map.on('zoomend', upd); map.on('moveend', upd); // moveend juga untuk sinkron setelah fit_all
      // tier switch juga update badge
      const _origMaybe = (typeof _maybeSwitchTier === 'function' ? _maybeSwitchTier : null);
      if (_origMaybe) { /* badge ikut zoomend, cukup */ }
      upd();
    } catch(_){}
  })();

  _ctl = createLeafletControl(map, {
    home: { lat: CENTER[0], lng: CENTER[1], zoom: 11 },
    baseStyle: BASE_STYLE,
    onEvent: (type, data) => {
      if (type === 'MAP_MOVED') log('map', 'MAP', 'view ' + data.lat + ',' + data.lng + ' z' + data.zoom);
      else if (type === 'MAP_FEATURE_SELECTED' && data.id) log('map', 'MAP', 'petak ' + data.id);
      else if (type === 'MAP_LAYER_CHANGED') { log('map', 'MAP', 'layer ' + data.id + ' ' + (data.visible ? 'on' : 'off')); try { _savePanelStateGated({ business: bizSel?.value || 'petak', filters: collectState().filters }); } catch (_) {} }
      else if (type === 'MAP_FILTER_CHANGED') log('map', 'MAP', 'filter ' + (data.query || '-') + ' (' + data.shown + ')');
      else if (type === 'MAP_HIGHLIGHT_CHANGED') log('map', 'MAP', 'highlight ' + data.ids.length);
      else if (type === 'MAP_STYLE_CHANGED') { log('map', 'MAP', 'basemap ' + _ctl?.get_state().basemap); try { _savePanelStateGated({ business: bizSel?.value || 'petak', filters: collectState().filters }); } catch (_) {} }
      else if (type === 'MAP_FEATURES_LOADED') {
        if (metric) metric.textContent = data.added + ' baru \u00b7 ' + data.total + ' total' + (stat ? ' \u00b7 ' + stat.textContent : '');
        try { const s=getSpatialState(); updateLegend(s.business, s.filters?.kategori); } catch (_) {}
        // ── progress: selesai hanya saat polygon beneran tampil ──
        if (_awaitingFeatures !== null && _awaitingSeq === _loadSeq) {
          if (data.total >= _awaitingFeatures && data.total > 0) {
            if (_renderWatchdog) { clearTimeout(_renderWatchdog); _renderWatchdog = null; }
            _setProgress(96, 'polygon tampil — ' + data.total + ' feat');
            _hideProgressSoon(true);
            _firstLoadDone = true;
            _awaitingFeatures = null;
          } else if (data.total === 0 && _awaitingFeatures > 0) {
            // bridge belum render — masih 0, jangan tutup progress
            _setProgress(64, 'menunggu render ' + _awaitingFeatures + ' polygon di peta…');
          } else if (data.total > 0 && data.total < _awaitingFeatures) {
            const pct = 68 + Math.round(Math.min(22, (data.total/_awaitingFeatures)*22));
            _setProgress(pct, 'merender ' + data.total + '/' + _awaitingFeatures + ' polygon…');
          }
        } else if (_awaitingFeatures === null && data.total > 0) {
          // render di luar reloadBusiness (mis. ANA push) — tetap update metric, jangan ganggu progress
        }
      }
    },
  });
  _ctl.registerBase('Satelit', satGroup, true);
  _ctl.registerBase('Gelap', dark, false);
  _ctl.registerLayer('Petak', petakLayer, true);
  // Label didaftarkan agar visibilitasnya terlacak state _ctl (persistensi
  // + sinkron kontrol native). Flag awal = kenyataan di peta.
  try { _ctl.registerLayer('Label', refLbl, map.hasLayer(refLbl)); } catch (_) {}
  try { window.__anaMap = _ctl; } catch (_) {}
  let _rsz = 0;
  new ResizeObserver(() => {
    clearTimeout(_rsz);
    // panel sempit → BI bottom bar jadi strip tipis; kalau tidak ia wrap jadi
    // 141px dan menutupi 46% peta (polygon ada tapi tak terlihat).
    const narrow = box.offsetWidth < 520;
    if (el.classList.contains('narrow') !== narrow) el.classList.toggle('narrow', narrow);
    _rsz = setTimeout(() => map.invalidateSize(), 120);
  }).observe(box);
  if (box.offsetWidth < 520) el.classList.add('narrow');

  // ---- BI wiring ----
  const $sel = function(s) { return el.querySelector(s); };
  const bizSel = $sel('#spatialBiz');
  const katSel = $sel('#spatialKat');
  const btnFilter = $sel('#spatialFilterBtn');
  const btnKpi = $sel('#spatialKpiBtn');
  const panelFilter = $sel('#spatialFilters');
  const btnRefresh = $sel('#spatialRefresh');
  const fBulan = $sel('#fBulan'), fTahun = $sel('#fTahun'), fPeriode = $sel('#fPeriode');
  const fPemKe = $sel('#fPemKe');
  const fJenisAkt = $sel('#fJenisAkt');
  const fSampai = $sel('#fSampai');
  const fDivre = $sel('#fDivre'), fKph = $sel('#fKph'), fBkph = $sel('#fBkph'), fRph = $sel('#fRph'), fTpg = $sel('#fTpg');
  const fApply = $sel('#fApply'), fReset = $sel('#fReset');
  const chipsBox = $sel('#spatialChips');
  const kpiBox = $sel('#spatialKpi');
  const shPeriode = $sel('#shPeriode'), shMode = $sel('#shMode');
  const insightBox = $sel('#spatialInsight');
  const kpiTotal = $sel('#kpiTotal'), kpiTotalSub = $sel('#kpiTotalSub');
  const kpi2 = $sel('#kpi2'), kpi2Label = $sel('#kpi2Label'), kpi2Sub = $sel('#kpi2Sub');
  const kpi3 = $sel('#kpi3'), kpi3Label = $sel('#kpi3Label'), kpi3Sub = $sel('#kpi3Sub');
  const kpi4 = $sel('#kpi4'), kpi4Label = $sel('#kpi4Label'), kpi4Sub = $sel('#kpi4Sub');

  const d = new Date();
  if (fBulan) fBulan.value = String(d.getMonth()+1);
  if (fPeriode) fPeriode.value = d.getDate() <= 15 ? '1' : '2';

  function curPerLabel() {
    const y = (fTahun && fTahun.value) || String(d.getFullYear());
    const m = String((fBulan && fBulan.value) || (d.getMonth()+1)).padStart(2,'0');
    const p = (fPeriode && fPeriode.value) || '1';
    if (p === '0') return y + '-' + m + '-FULL';
    return y + '-' + m + '-P' + p;
  }
  function syncKatVisibility() {
    // Cascade bisnis → kategori: bangun ulang opsi katSel per bisnis.
    // Pilihan dipertahankan bila valid di bisnis baru, else reset 'semua'.
    // Slug asing (mis. dari ANA: tanpa_penyadap/multi_penyadap/ringkasan)
    // ditambahkan sementara agar spatial_set tak kehilangan state.
    const b = bizSel?.value || 'petak';
    if (!katSel) return;
    try {
      const opts = katOptionsFor(b);
      const cur = katSel.value || 'semua';
      katSel.innerHTML = opts.map(function(o){ return '<option value="' + esc(o.value) + '">' + esc(o.label) + '</option>'; }).join('');
      if (opts.some(function(o){ return o.value === cur; })) katSel.value = cur;
      else if (cur !== '' && cur !== 'semua') {
        const o = document.createElement('option'); o.value = cur; o.textContent = cur;
        katSel.appendChild(o); katSel.value = cur;
      } else katSel.value = 'semua';
      katSel.style.display = '';
    } catch (_) {}
  }
  syncKatVisibility();

  function updateHead() {
    if (shPeriode) shPeriode.textContent = curPerLabel();
    const m = _curMode();
    if (shMode) {
      shMode.textContent = m.toUpperCase();
      shMode.className = 'sh-badge mode-' + m;
    }
    if (insightBox && insightBox.dataset.lastBiz) {
      renderInsight(insightBox.dataset.lastBiz, insightBox.dataset.lastExpl || '', parseInt(insightBox.dataset.lastFeat||'0',10), insightBox.dataset.lastCounts ? JSON.parse(insightBox.dataset.lastCounts) : {});
    }
  }

  function _legendAttrib(){
  return '<span class="lg-attrib" title="Peta: Esri World Imagery + Dark Gray + Boundaries — via Leaflet">Leaflet \u00b7 Esri, Maxar, Earthstar Geographics</span>';
}
function updateLegend(biz, kat) {
    if (!legend) return;
    const k = String(kat||'').toLowerCase();
    const _ovLine = (String(biz || '').toLowerCase() === 'produksi')
      ? '<span class="lg" title="achievement KPH <50% (tertimbang tonase)"><i style="background:#EF4444"></i> KPH rendah</span><span class="lg" title="achievement KPH 50-85%"><i style="background:#EAB308"></i> KPH menengah</span><span class="lg" title="achievement KPH >85%"><i style="background:#22C55E"></i> KPH baik</span><span class="lg" title="overview choropleth KPH (z≤10) — angka per KPH di panel insight">overview KPH</span>'
      : '<span class="lg" title="porsi bongkor ≥25%"><i style="background:#EF4444"></i> KPH rawan</span><span class="lg" title="porsi kurang ≥30% atau terpenuhi <60%"><i style="background:#EAB308"></i> KPH perhatian</span><span class="lg" title="selain itu"><i style="background:#22C55E"></i> KPH baik</span><span class="lg" title="overview choropleth KPH (z≤10) — angka per KPH di panel insight">overview KPH</span>';
    if (biz === 'petak' && k === 'idle') {
      legend.innerHTML = '<span class="lg" title="ada penyadap + aktivitas 2 bln, tapi 0 di periode ini"><i style="background:#EAB308"></i> Idle (kuning)</span><span class="lg"><i style="background:#22C55E"></i> Aktif (hijau)</span>' + _legendAttrib();
    } else if (biz === 'petak' && k === 'multi_penyadap') {
      legend.innerHTML = '<span class="lg"><i style="background:#EAB308"></i> 2 penyadap (kuning)</span><span class="lg"><i style="background:#F97316"></i> 3 (oranye)</span><span class="lg"><i style="background:#22C55E"></i> >3 (hijau)</span>' + _legendAttrib();
    } else if (biz === 'petak') {
      // diperjelas: merah tanpa penyadap, kuning luas_andil<luas_baku, hijau >=
      legend.innerHTML = '<span class="lg" title="tidak ada penyadap"><i style="background:#EF4444"></i> Bongkor (merah)</span><span class="lg" title="luas_andil < luas_baku"><i style="background:#EAB308"></i> Kurang (kuning)</span><span class="lg" title="luas_andil >= luas_baku"><i style="background:#22C55E"></i> Terpenuhi (hijau)</span>' + _legendAttrib();
    } else if (biz === 'produksi') {
      legend.innerHTML = '<span class="lg"><i style="background:#EF4444"></i> 0-25%</span><span class="lg"><i style="background:#F97316"></i> 26-50%</span><span class="lg"><i style="background:#EAB308"></i> 51-75%</span><span class="lg"><i style="background:#22C55E"></i> 76-100%</span><span class="lg"><i style="background:#3B82F6"></i> &gt;100%</span>' + _legendAttrib();
    } else if (biz === 'aktivitas' && k === 'idle') {
      legend.innerHTML = '<span class="lg" title="tanpa penyadap atau >2 bln tanpa aktivitas"><i style="background:#EF4444"></i> Bongkor (merah)</span><span class="lg" title="ada penyadap + aktivitas 2 bln, tapi 0 di periode ini"><i style="background:#EAB308"></i> Idle (kuning)</span><span class="lg"><i style="background:#22C55E"></i> Aktif (hijau)</span><span class="lg" title="pin + garis dashed ke pusat petak"><i style="background:#2DF2FF;border:2px solid #fff;border-radius:50%"></i> Pin Pem1 cyan/2 oranye/3 merah</span>' + _legendAttrib();
    } else if (biz === 'aktivitas') {
      // diperjelas: merah bongkor (tanpa penyadap / >2bln tanpa aktivitas), kuning idle (ada penyadap + aktivitas 2bln, tapi 0 di periode ini), hijau aktif (cur>0)
      legend.innerHTML = '<span class="lg" title="tanpa penyadap atau >2 bln tanpa aktivitas"><i style="background:#EF4444"></i> Bongkor (merah)</span><span class="lg" title="ada penyadap + aktivitas 2 bln, tapi 0 di periode ini"><i style="background:#EAB308"></i> Idle (kuning)</span><span class="lg" title="ada aktivitas periode berjalan"><i style="background:#22C55E"></i> Aktif (hijau)</span><span class="lg" title="pin aktivitas + garis dashed ke pusat petak via kode_evapot; GPS bisa melenceng"><i style="background:#2DF2FF;border:2px solid #fff;border-radius:50%"></i> Pin Pem1/2/3 ● foto — garis ke petak</span>' + _legendAttrib();
    } else if (biz === 'matriks' || biz === 'matrik') {
      legend.innerHTML = '<span class="lg"><i style="background:#EF4444"></i> Bongkor (merah)</span><span class="lg"><i style="background:#F97316"></i> Kurang & cap<50% (oranye)</span><span class="lg"><i style="background:#EAB308"></i> Kurang (kuning)</span><span class="lg"><i style="background:#22C55E"></i> Terpenuhi (hijau)</span><span class="lg"><i style="background:#3B82F6"></i> &gt;100% (biru)</span>' + _legendAttrib();
    } else {
      legend.innerHTML = '<span class="lg"><i style="background:#2DF2FF"></i> Matriks</span>' + _legendAttrib();
    }
    // Guard anti-kedip: overview aktif = bar overview selalu menyertai,
    // dari manapun updateLegend dipanggil (features-loaded, subscribe, ANA).
    // TDZ-aman: _ovOn dideklarasikan belakangan.
    try {
      if (_ovOn && legend.innerHTML.indexOf('overview KPH') === -1) legend.innerHTML = _ovLine + legend.innerHTML;
    } catch (_) {}
  }
  updateLegend('petak', katSel?.value || 'semua');

  // filters.warna tak punya kontrol di panel (mis. subset kuning dari
  // idle_petak_map). Simpan terpisah supaya collectState() mengirimnya lagi
  // ke resolveTemplate — tanpa ini panel render semua petak, menimpa subset.
  let _spatialWarna = '';
  // Template eksplisit dari ANNA via spatial_set (mis. aktivitas_top_petak).
  // resolveTemplate tak kenal template itu → tanpa ini panel fallback ke
  // evaluasi penuh 809 polygon. Direset saat user ubah filter manual.
  let _spatialTemplate = null;
  // Viewport extras (bounds/zoom/page_size/aggregated_level) — tak ada dropdown
  // DOM, disimpan di memori agar collectState → resolveTemplate → server utuh.
  let _viewportExtra = {};
  const _KNOWN_TPL = ['petak_bongkor_map','petak_efektivitas_map','petak_multi_penyadap_map','idle_petak_map','aktivitas_petak_map','aktivitas_top_petak','rkap_map','matriks_map','kph_summary_map','petak_with_geometry'];

  // ── Persistensi filter panel (refresh-safe) ──
  // Bisnis + filter (waktu/wilayah/kategori/pembaharuan) tersimpan di
  // localStorage per-perangkat; refresh memulihkan, reset manual menghapus.
  // Kunci perangkat (bukan user): nilai wilayah di luar scope login dibuang
  // renderWilayah() saat pulih — aman untuk perangkat bersama.
  // Ephemeral, tak disimpan: subset/template ANA + viewport peta.
  const _PANEL_KEY = 'ana_spatial_panel_v1';
  let _panelReady = false; // true setelah opsi wilayah pertama terisi
  let _pendingWilayah = null;
  let _lastSavedFilt = null; // kunci filter terakhir yang tersimpan (anti-clobber)
  let _vpRestored = false; // viewport dipulihkan dari simpanan -> lewati fit pertama
  function _savePanelState(st) {
    if (!_panelReady) return; // jangan timpa simpanan dengan inisialisasi kosong
    try {
      const f = (st && st.filters) || {};
      const keep = {};
      for (const k of ['bulan','tahun','periode','divre','kph','bkph','rph','tpg','kategori','pembaharuan_ke','sampai_dengan','jenis_aktivitas']) {
        const v = f[k];
        keep[k] = (v == null) ? '' : String(v);
      }
      const snap = { business: (st && st.business) || 'petak', filters: keep, at: Date.now() };
      // Fokus peta = posisi aktual (bukan _viewportExtra yang dikosongkan tiap
      // ganti filter): refresh kembali ke area yang sedang dilihat.
      try {
        const bb = map.getBounds();
        snap.filters.bounds = [+bb.getWest().toFixed(6), +bb.getSouth().toFixed(6), +bb.getEast().toFixed(6), +bb.getNorth().toFixed(6)];
        snap.filters.zoom = map.getZoom();
      } catch (_) {}
      // Visibilitas layer = pilihan user via kontrol layer (basemap Satelit/
      // Gelap + overlay Petak/Label). Tier PMTiles-vs-GeoJSON mengikuti zoom
      // (otomatis, tak disimpan). Pin aktivitas mengikuti bisnis+tier.
      try {
        const _ly = { base: null, overlays: {} };
        try { _ly.base = _ctl?.get_state?.()?.basemap || null; } catch (_) {}
        try {
          for (const o of (_ctl?.get_layers?.() || [])) {
            if (o && o.id != null && String(o.id) !== 'Aktivitas' && String(o.id) !== 'PMTilesPetak') _ly.overlays[String(o.id)] = !!o.visible;
          }
        } catch (_) {}
        try { _ly.overlays.Label = map.hasLayer(refLbl); } catch (_) {}
        snap.filters.layers = _ly;
      } catch (_) {}
      localStorage.setItem(_PANEL_KEY, JSON.stringify(snap));
      try { window.__spatialPersist = { ...(window.__spatialPersist || {}), saved: snap }; } catch (_) {}
      try { console.info('[spatial-persist] save', snap.business, JSON.stringify(keep)); } catch (_) {}
    } catch (_) {}
  }
  function _savePanelStateGated(st) {
    // Simpan bila kunci filter, posisi peta, ATAU visibilitas layer berubah.
    // Tab yang tak bergerak tak menimpa simpanan tab lain (anti-clobber).
    try {
      let vk = '';
      try { vk = '|vp:' + map.getBounds().toBBoxString() + 'z' + map.getZoom(); } catch (_) {}
      let lk = '';
      try {
        const _ls = _ctl?.get_state?.();
        lk = '|ly:' + (_ls?.basemap || '') + ':' + (_ctl?.get_layers?.() || []).map(function(o){ return o.id + '=' + (o.visible ? 1 : 0); }).join(',');
      } catch (_) {}
      const k = _filtKey(st) + vk + lk;
      if (k === _lastSavedFilt) return false;
      _lastSavedFilt = k;
      _savePanelState(st);
      return true;
    } catch (_) { return false; }
  }
  function _readPanelState() {
    try {
      const raw = localStorage.getItem(_PANEL_KEY);
      if (!raw) return null;
      const j = JSON.parse(raw);
      if (!j || typeof j !== 'object' || !j.filters) return null;
      return j;
    } catch (_) { return null; }
  }
  function _setSel(elm, val, allow) {
    if (!elm || val == null || val === '') return false;
    const v = String(val);
    if (allow && !allow(v)) return false;
    try {
      const has = [...elm.options].some(function(o){ return o.value === v; });
      if (!has) return false;
      elm.value = v;
      return true;
    } catch (_) { return false; }
  }
  function _restorePanelState() {
    const s = _readPanelState();
    try { window.__spatialPersist = { ...(window.__spatialPersist || {}), bootRead: s ? { business: s.business, filters: s.filters } : null }; } catch (_) {}
    try { console.info('[spatial-persist] boot read', s ? (s.business + ' ' + JSON.stringify(s.filters)) : '(kosong)'); } catch (_) {}
    if (!s) return;
    try {
      const f = s.filters || {};
      if (bizSel && s.business) {
        const b = String(s.business);
        if ([...bizSel.options].some(function(o){ return o.value === b; })) bizSel.value = b;
      }
      syncKatVisibility();
      _setSel(fBulan, f.bulan, function(v){ return /^[1-9]$|^1[0-2]$/.test(v); });
      _setSel(fTahun, f.tahun);
      _setSel(fPeriode, f.periode, function(v){ return v === '0' || v === '1' || v === '2'; });
      _setSel(fPemKe, f.pembaharuan_ke, function(v){ return v === '' || ['1','2','3','4'].includes(v); });
      _setSel(fJenisAkt, f.jenis_aktivitas, function(v){ return v === '' || ['quare','semprot_cas','kerok','naik_batok','budaya_bersih','pulung'].includes(v); });
      _setSel(fSampai, f.sampai_dengan, function(v){ return v === '' || ['ya','tidak'].includes(v); });
      const kc = String(f.kategori || '');
      if (kc && katSel && [...katSel.options].some(function(o){ return o.value === kc; })) katSel.value = kc;
      // Wilayah dipulihkan susulan setelah opsi DB terisi (lihat _populateDropdowns).
      const w = {};
      for (const k of ['divre','kph','bkph','rph','tpg']) if (String(f[k] || '') !== '') w[k] = String(f[k]);
      _pendingWilayah = Object.keys(w).length ? w : null;
      // Fokus peta: kembali ke area + zoom terakhir. Listener moveend/zoomend
      // (_pushViewport) baru dipasang sesudahnya, jadi tanpa reload umpan-balik.
      try {
        let b = f.bounds;
        if (typeof b === 'string') b = b.split(',').map(Number);
        const z = parseInt(f.zoom);
        if (Array.isArray(b) && b.length === 4 && b.every(function(v){ return Number.isFinite(v); })
            && b[0] < b[2] && b[1] < b[3] && Number.isFinite(z)) {
          map.setView([(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], Math.max(0, Math.min(18, z)));
          _vpRestored = true; // fit otomatis pertama dilewati (hormati fokus ini)
          try { console.info('[spatial-persist] viewport pulih z' + z); } catch (_) {}
        }
      } catch (_) {}
      // Visibilitas layer: basemap + overlay sesuai simpanan. Dijaga tier
      // (set_layer_visibility menolak pin di z<12) dan status Esri.
      try {
        const L = f.layers;
        if (L && typeof L === 'object') {
          if (L.base && _ctl && typeof _ctl.set_basemap === 'function') {
            try {
              const cur = _ctl.get_state?.()?.basemap;
              if (cur !== String(L.base)) _ctl.set_basemap(String(L.base));
            } catch (_) {}
          }
          const ov = (L.overlays && typeof L.overlays === 'object') ? L.overlays : {};
          for (const id of Object.keys(ov)) {
            if (id === 'Aktivitas' || id === 'PMTilesPetak' || id === 'KphBounds') continue; // otomatis (zoom/tier), jangan dipaksa
            try {
              if (id === 'Label') {
                if (esriRemembered === '0' && ov[id]) continue; // Esri diblokir: jangan paksa label
                if (ov[id]) { if (!map.hasLayer(refLbl)) refLbl.addTo(map); }
                else if (map.hasLayer(refLbl)) map.removeLayer(refLbl);
              } else if (_ctl && typeof _ctl.set_layer_visibility === 'function') {
                _ctl.set_layer_visibility(id, !!ov[id]);
              }
            } catch (_) {}
          }
          try { console.info('[spatial-persist] layer pulih', JSON.stringify(L)); } catch (_) {}
        }
      } catch (_) {}
      updateHead(); renderChips();
    } catch (_) {}
  }

  function collectState() {
    const base = {
      bulan: fBulan?.value || String(d.getMonth()+1),
      tahun: fTahun?.value || '2026',
      periode: fPeriode?.value || '1',
      divre: fDivre?.value || '',
      kph: fKph?.value || '',
      bkph: fBkph?.value || '',
      rph: fRph?.value || '',
      tpg: fTpg?.value || '',
      kategori: katSel?.value || 'semua',
      ...(_spatialWarna ? { warna: _spatialWarna } : {}),
      ...(fPemKe?.value ? { pembaharuan_ke: fPemKe.value } : {}),
      ...(fJenisAkt?.value ? { jenis_aktivitas: fJenisAkt.value } : {}),
      ...(fSampai?.value ? { sampai_dengan: fSampai.value } : {}),
    };
    // Viewport extras (bounds/zoom/page_size/aggregated_level) — dari memori,
    // bukan dropdown. Tanpa ini bounds hilang sebelum resolveTemplate.
    for (const _k of ['aggregated_level', 'bounds', 'zoom', 'page_size']) {
      if (_viewportExtra[_k] !== undefined && base[_k] === undefined) base[_k] = _viewportExtra[_k];
    }
    return {
      business: bizSel?.value || 'petak',
      filters: base,
    };
  }
  _restorePanelState(); // refresh-safe: pulihkan bisnis+filter tersimpan (di sini agar const di atas sudah terinisialisasi)

  function renderChips() {
    if (!chipsBox) return;
    const st = collectState();
    const f = st.filters;
    const items = [];
    if (f.bkph) items.push({k:'bkph', label:'BKPH', v:_labelWilayah('bkph', f.bkph)});
    if (f.rph) items.push({k:'rph', label:'RPH', v:_labelWilayah('rph', f.rph)});
    if (f.tpg) items.push({k:'tpg', label:'TPG', v:_labelWilayah('tpg', f.tpg)});
    if (f.bulan || f.periode) items.push({k:'waktu', label:'Waktu', v: f.bulan + '/P' + f.periode + '/' + f.tahun});
    if (f.kategori && f.kategori !== 'semua') items.push({k:'kategori', label:'Kategori', v:f.kategori});
    if (f.pembaharuan_ke) items.push({k:'pemke', label:'Pem', v:String(f.pembaharuan_ke)});
    if (f.jenis_aktivitas) items.push({k:'jenisakt', label:'Akt', v:String(f.jenis_aktivitas)});
    if (f.sampai_dengan) items.push({k:'sampai', label:'S/d', v:String(f.sampai_dengan)});
    if (!items.length) { chipsBox.innerHTML = ''; return; }
    chipsBox.innerHTML = items.map(function(it){
      return '<span class="chip"><b>' + esc(it.label) + ':</b> ' + esc(it.v) + ' <i data-k="' + esc(it.k) + '" title="hapus">x</i></span>';
    }).join('') + ' <span class="chip" style="cursor:pointer" data-k="clear">hapus semua</span>';
    chipsBox.querySelectorAll('[data-k]').forEach(function(node){
      node.addEventListener('click', function(){
        const k = node.getAttribute('data-k');
        if (k === 'clear') {
          if (fBkph) fBkph.value=''; if (fRph) fRph.value=''; if (fTpg) fTpg.value='';
          if (fBulan) fBulan.value=String(d.getMonth()+1); if (fTahun) fTahun.value='2026'; if (fPeriode) fPeriode.value=d.getDate()<=15?'1':'2';
          if (katSel) katSel.value='semua';
          if (fPemKe) fPemKe.value='';
    if (typeof fJenisAkt !== 'undefined' && fJenisAkt) fJenisAkt.value='';
        } else if (k==='bkph' && fBkph) fBkph.value='';
        else if (k==='rph' && fRph) fRph.value='';
        else if (k==='tpg' && fTpg) fTpg.value='';
        else if (k==='waktu'){ if(fBulan) fBulan.value=String(d.getMonth()+1); if(fPeriode) fPeriode.value=d.getDate()<=15?'1':'2'; }
        else if (k==='kategori' && katSel) { katSel.value='semua'; _spatialWarna = ''; }
        else if (k==='pemke' && fPemKe) fPemKe.value='';
        else if (k==='jenisakt' && typeof fJenisAkt !== 'undefined' && fJenisAkt) fJenisAkt.value='';
        else if (k==='sampai' && typeof fSampai !== 'undefined' && fSampai) fSampai.value='';
        updateHead(); renderChips(); scheduleReload();
      });
    });
  }

  function renderKPIs(biz, kat, counts, total) {
    const c = counts || {};
    const tot = total || 0;
    const pct = function(n){ return tot? Math.round(n/tot*100)+'%' : '-'; };
    // Total — konteks bisnis: jumlah petak dipantau
    if (kpiTotal) kpiTotal.textContent = String(tot);
    if (kpiTotalSub) {
      const per = curPerLabel();
      let ctx = 'dipantau';
      if (biz==='produksi') ctx = 'target RO/NPS';
      else if (biz==='aktivitas') ctx = 'petak sadap';
      else if (biz==='matriks') ctx = 'matriks';
      else ctx = 'coverage petak';
      kpiTotalSub.textContent = per + ' \u00b7 ' + tot + ' ' + ctx;
      kpiTotalSub.title = 'Total polygon untuk filter ' + per + ' · ' + (biz||'petak');
    }
    let l2='Bongkor', l3='Perhatian', l4='Terpenuhi';
    let v2 = c.merah || 0, v3 = (c.kuning||0)+(c.oranye||0), v4=(c.hijau||0)+(c.emas||0);
    let s2='', s3='', s4='', t2='', t3='', t4='';
    if (biz==='petak' && String(kat).toLowerCase()==='idle') {
      l2='Idle'; l3='Rasio'; l4='Aktif';
      v2=c.kuning||0; v3=Math.round(tot? (v2/tot*100):0); v4=c.hijau||0;
      s2 = pct(v2) + ' \u00b7 butuh kunjungan'; s3 = v3 + '% idle'; s4 = pct(v4) + ' \u00b7 produktif';
      t2='Petak tanpa aktivitas berjalan — perlu cek lapangan'; t3='Persentase idle dari total'; t4='Ada aktivitas berjalan';
    } else if (biz==='petak' && String(kat).toLowerCase()==='multi_penyadap') {
      l2='2 penyadap'; l3='3 penyadap'; l4='>3 penyadap';
      v2=c.kuning||0; v3=c.oranye||0; v4=c.hijau||0;
      s2=pct(v2)+' \u00b7 perlu tambah'; s3=pct(v3)+' \u00b7 cukup'; s4=pct(v4)+' \u00b7 optimal';
      t2='Petak dengan 2 penyadap — cek beban kerja'; t3='3 penyadap'; t4='>3 penyadap — coverage padat';
    } else if (biz==='produksi') {
      l2='Krisis'; l3='Menuju'; l4='Lampaui';
      v2=(c.merah||0)+(c.oranye||0); v3=(c.kuning||0)+(c.hijau||0); v4=c.emas||0;
      s2=pct(v2)+' \u00b7 <50% target'; s3=pct(v3)+' \u00b7 50-100%'; s4=pct(v4)+' \u00b7 >100% target';
      t2='Realisasi <50% — intervensi segera'; t3='Progress menuju target RKAP'; t4='Melebihi target — evaluasi sustain';
    } else if (biz==='aktivitas') {
      l2='Bongkor'; l3='Idle'; l4='Aktif';
      v2=c.merah||0; v3=c.kuning||0; v4=c.hijau||0;
      s2=pct(v2)+' \u00b7 tanpa penyadap/>2 bln'; s3=pct(v3)+' \u00b7 0 di periode ini'; s4=pct(v4)+' \u00b7 ada sadap';
      t2='Tanpa penyadap atau >2 bulan tanpa aktivitas — butuh alokasi ulang'; t3='Ada penyadap + aktivitas 2 bln, tapi 0 di periode ini — cek andil'; t4='Aktivitas sadap berjalan — pin cyan/oranye/merah (Pem1/2/3)';
    } else if (biz==='matriks' || biz==='matrik') {
      l2='Masalah'; l3='Kurang'; l4='Optimal';
      v2=c.merah||0; v3=(c.kuning||0)+(c.oranye||0); v4=(c.hijau||0)+(c.emas||0);
      s2=pct(v2)+' \u00b7 prioritas 1'; s3=pct(v3)+' \u00b7 perbaikan'; s4=pct(v4)+' \u00b7 sesuai';
      t2='Skor matriks terendah — luas/pohon/produksi bermasalah'; t3='Perlu perbaikan'; t4='Skor optimal';
    } else {
      // default petak
      s2=pct(v2)+' \u00b7 perlu penyadap'; s3=pct(v3)+' \u00b7 belum penuh'; s4=pct(v4)+' \u00b7 sesuai';
      t2='Tanpa penyadap — alokasi segera'; t3='luas_andil < luas_baku'; t4='luas_andil >= luas_baku';
    }
    if (kpi2Label) kpi2Label.textContent=l2; if(kpi3Label) kpi3Label.textContent=l3; if(kpi4Label) kpi4Label.textContent=l4;
    if (kpi2) kpi2.textContent=String(v2); if(kpi3) kpi3.textContent=String(v3); if(kpi4) kpi4.textContent=String(v4);
    if (kpi2Sub) { kpi2Sub.textContent=s2; kpi2Sub.title=t2; }
    if (kpi3Sub) { kpi3Sub.textContent=s3; kpi3Sub.title=t3; }
    if (kpi4Sub) { kpi4Sub.textContent=s4; kpi4Sub.title=t4; }
    // tooltip total KPI cards
    try {
      if (kpiTotal) kpiTotal.parentElement.title = 'Total ' + tot + ' petak — ' + (biz||'petak') + ' ' + curPerLabel();
      if (kpi2) kpi2.parentElement.title = t2 + ' — ' + s2;
      if (kpi3) kpi3.parentElement.title = t3 + ' — ' + s3;
      if (kpi4) kpi4.parentElement.title = t4 + ' — ' + s4;
    } catch(_){}
  }

  function renderInsight(biz, explanation, features, counts) {
    if (!insightBox) return;
    const _wasExp = insightBox.classList.contains('expanded');
    insightBox.dataset.lastBiz = biz;
    insightBox.dataset.lastExpl = explanation || '';
    insightBox.dataset.lastFeat = String(features||0);
    try { insightBox.dataset.lastCounts = JSON.stringify(counts||{}); } catch(_){}
    const mode = _curMode();
    const per = curPerLabel();
    const n = features||0;
    const c = counts||{};
    if (!n) {
      insightBox.innerHTML = '<div class="ins-title">Insight \u00b7 ' + esc(per) + '</div>Tidak ada polygon untuk filter ini. Coba longgarkan wilayah atau periode.';
      insightBox.className = 'spatial-insight' + (mode==='coding' ? ' dev' : '') + (_wasExp ? ' expanded' : '');
      return;
    }
    if (mode === 'asisten') {
      const sum = (c.merah||0)+(c.kuning||0)+(c.oranye||0)+(c.hijau||0)+(c.emas||0) || n;
      const merahPct = sum ? Math.round((c.merah||0)/sum*100) : 0;
      let nar = '';
      if (biz==='petak') nar = 'Evaluasi Petak ' + n + ' polygon ' + per + ' — Apakah coverage memadai? Bongkor ' + (c.merah||0) + ' (' + merahPct + '%), kurang ' + ((c.kuning||0)+(c.oranye||0)) + ', terpenuhi ' + ((c.hijau||0)+(c.emas||0)) + '. Luas_andil vs luas_baku.';
      else if (biz==='produksi') nar = 'Evaluasi Produksi ' + n + ' petak ' + per + ' — Target RO/NPS vs aktual. >100% ' + (c.emas||0) + ', 76-100% ' + (c.hijau||0) + ', <50% ' + ((c.merah||0)+(c.oranye||0)) + '.';
      else if (biz==='aktivitas') nar = 'Evaluasi Aktivitas ' + n + ' petak ' + per + ' — Apakah sadap berlangsung? Bongkor ' + (c.merah||0) + ' (tanpa penyadap/>2 bln), Idle ' + (c.kuning||0) + ' (0 di periode ini), Aktif ' + (c.hijau||0) + '. Pin terikat via kode_evapot, garis dashed jika GPS melenceng.';
      else if (biz==='matriks' || biz==='matrik') nar = 'Evaluasi Matriks ' + n + ' petak ' + per + ' — Keseimbangan luas/pohon/andil/produksi. Bongkor ' + (c.merah||0) + ', kurang ' + ((c.kuning||0)+(c.oranye||0)) + ', terpenuhi ' + ((c.hijau||0)+(c.emas||0)) + '.';
      else nar = (explanation||'').slice(0,160) || (n + ' polygon periode ' + per + '.');
      insightBox.innerHTML = '<div class="ins-title">Ringkasan ANNA \u00b7 ' + esc(per) + ' \u00b7 mode asisten</div>' + esc(nar);
      insightBox.className = 'spatial-insight' + (_wasExp ? ' expanded' : '');
    } else {
      const dev = 'template=' + esc(biz) + ' \u00b7 ' + n + ' feat \u00b7 ' + esc(per) + ' \u00b7 warna ' + esc(JSON.stringify(c)) + (explanation ? ' \u00b7 ' + esc(explanation.slice(0,120)) : '');
      insightBox.innerHTML = '<div class="ins-title">Dev detail \u00b7 ' + esc(per) + ' \u00b7 mode coding</div>' + dev;
      insightBox.className = 'spatial-insight dev' + (_wasExp ? ' expanded' : '');
    }
  }

  let _loading = false;
  let _pending = false;
  let _debounce = null;
  let _loadSeq = 0;
  let _firstLoadDone = false;
  let _progressTimer = null;
  let _awaitingFeatures = null; // polygon yang dijanjikan server, nunggu MAP_FEATURES_LOADED beneran
  let _awaitingSeq = 0;
  let _renderWatchdog = null;
  // Retry eksplisit 3x per filter (robust auto-open): blank intermiten pulih
  // sendiri, bukan 'klik Muat'. Reset tiap ganti filter di reloadBusiness.
  // Kunci = business+filtKey agar retry filter lama tak bocor ke filter baru.
  let _retryCount = 0;
  let _retryKey = '';
  // P1 viewport-loop fix: true saat fit programmatic (first-load / ganti
  // filter) — _pushViewport abaikan moveend yang datang dari fit_all, supaya
  // pan/zoom user tak picu reload berulang + snapback ke extent lama.
  let _suppressVp = false;
  let _lastFittedFilt = null; // kunci filter non-viewport terakhir yang di-fit
  let _lastLoadedFilt = null; // kunci filter+template terakhir yang sukses render (incremental guard)
  // KPI dikunci ke bisnis+filter (bukan viewport): renderKPIs hanya jalan saat
  // kunci ini berubah; pan/zoom (bounds saja) tak menyentuh angka KPI.
  let _lastKpiFilt = null;
  // ANA push set_features mentah (template di luar _TEMPLATE_SPATIAL) → feature
  // count tak sama dengan yang panel minta. Batalkan watchdog, atau panel akan
  // bunyi "render gagal" padahal peta berisi tepat seperti yang ANA minta.
  setExternalFeaturesHook(() => {
    if (_renderWatchdog) { clearTimeout(_renderWatchdog); _renderWatchdog = null; }
    _awaitingFeatures = null; _awaitingSeq = 0;
    _hideProgressSoon(true);
    if (stat) stat.textContent = 'peta dari ANA';
  });
  function _setProgress(pct, label) {
    const f = el.querySelector('#spBarFill'); const l = el.querySelector('#spLabel'); const wrap = el.querySelector('#spatialProgress');
    if (!wrap) return;
    wrap.classList.remove('hidden');
    if (f) f.style.width = Math.max(0, Math.min(100, pct)) + '%';
    if (l && label) l.textContent = label;
    if (btnRefresh) btnRefresh.disabled = pct > 0 && pct < 100;
  }
  function _hideProgressSoon(ok) {
    const f = el.querySelector('#spBarFill'); const l = el.querySelector('#spLabel'); const wrap = el.querySelector('#spatialProgress');
    if (!wrap) return;
    if (f) f.style.width = '100%';
    if (l) l.textContent = ok ? 'selesai · ' + (stat?.textContent || '') : 'gagal — coba lagi';
    if (_progressTimer) clearTimeout(_progressTimer);
    _progressTimer = setTimeout(() => { wrap.classList.add('hidden'); if (f) f.style.width = '0%'; }, ok ? 900 : 2200);
    if (btnRefresh) btnRefresh.disabled = false;
  }
  async function _drainBusinessQueue(mapId, incremental, tpl) {
  // tpl = template panel sendiri (res.template): bila ringkasan agregat,
  // titik centroid dilewati (label nama wilayah digambar terpisah).
  // ANA push mentah (id lain) tak tersentuh.
    // Eksekusi langsung perintah set_features milik kita (by map_id) tanpa tunggu interval bridge.
    // Menutup race: bridge poll (400ms) vs clear_features. Id lain tetap dieksekusi spt bridge.
    // incremental=true (pan/zoom, filter sama) → teruskan {full:false} agar
    // set_features diff-by-id, bukan full replace (anti flicker).
    let executed = false;
    try {
      const tok = document.querySelector('meta[name="ana-token"]')?.content || '';
      const r = await fetch('/api/map/queue', { headers: { 'X-Ana-Token': tok }, credentials: 'same-origin' });
      if (!r.ok) return false;
      const { commands = [] } = await r.json();
      for (const cmd of commands) {
        try {
          // ANA spatial_* — intercept di sini juga (drain langsung, tanpa tunggu interval bridge)
          if (cmd.op && cmd.op.indexOf('spatial_') === 0) {
            try {
              const _d = (typeof _spatialHandler === 'function') ? await _spatialHandler(cmd.op, cmd.args || {}) : { accepted: false, reason: 'panel belum siap' };
              if (cmd.id === mapId) executed = true;
              try {
                await fetch('/api/map/result', { method: 'POST', headers: { 'X-Ana-Token': tok, 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify({ id: cmd.id, ok: true, data: _d || {} }) });
              } catch (_) {}
            } catch (_e) {
              try {
                await fetch('/api/map/result', { method: 'POST', headers: { 'X-Ana-Token': tok, 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify({ id: cmd.id, ok: false, error: String((_e && _e.message) || _e).slice(0, 200) }) });
              } catch (_) {}
            }
            continue;
          }
          const fn = _ctl?.[cmd.op];
          const a = cmd.args || {};
          if (typeof fn === 'function' && (cmd.op === 'set_features' || cmd.op === 'clear_features')) {
            if (cmd.op === 'set_features') await fn.call(_ctl, a.geojson ?? a, { fit: a.fit ?? true, pad: a.pad, ...(incremental || a.full === false ? { full: false } : {}), ...(cmd.id === mapId && tpl === 'kph_summary_map' ? { skipPoints: true } : {}) });
            else await fn.call(_ctl);
            if (cmd.id === mapId) executed = true;
          } else if (typeof fn === 'function') {
            // perintah ANA lain (select/highlight/dll) — eksekusi juga agar tak hilang
            try { await fn.call(_ctl, a); } catch (_) {}
          }
          try {
            await fetch('/api/map/result', { method: 'POST', headers: { 'X-Ana-Token': tok, 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify({ id: cmd.id, ok: true, data: { drained: true } }) });
          } catch (_) {}
        } catch (_) {}
      }
      // drain mengeksekusi tanpa lewat poll — poll tak tahu ada render baru dan
      // pushState-nya kena throttle 4s. Push eksplisit agar /api/map/state akurat.
      if (executed) {
        try {
          const st = _ctl?.get_state?.();
          if (st) await fetch('/api/map/state', { method: 'POST', headers: { 'X-Ana-Token': tok, 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify({ state: st }) });
        } catch (_) {}
      }
    } catch (_) {}
    return executed;
  }
  async function reloadBusiness() {
    if (_loading) { _pending = true; return; }
    _scheduleOverview(); // overview KPH ikut filter baru (murah bila kunci sama)
    // filter baru harus menang — batalkan tunggu render sebelumnya
    if (_awaitingFeatures !== null) {
      if (_renderWatchdog) { clearTimeout(_renderWatchdog); _renderWatchdog = null; }
      _awaitingFeatures = null; _awaitingSeq = 0;
    }
    _loading = true; _loadSeq++;
    const mySeq = _loadSeq;
    const st = collectState();
    // KPI = cakupan penuh bisnis+filter: saat kunci filter berubah, buang sisa
    // viewport (bounds/zoom/page_size) dari parameter keluar agar query tak
    // tersaring extent terakhir. Pan/zoom murni (kunci sama) memakai apa yang
    // ada — peta tetap incremental, angka KPI beku pada cakupan filter.
    const _fkNow = st.business + '|' + _filtKey(st);
    const _fkChanged = (_fkNow !== _lastKpiFilt);
    if (_fkChanged) {
      _viewportExtra = {};
      try { delete st.filters.bounds; delete st.filters.zoom; delete st.filters.page_size; delete st.filters.aggregated_level; } catch (_) {}
    }
    // Retry baru untuk filter baru: kunci ganti = hitungan dari nol.
    try { const _rk = st.business + '|' + _filtKey(st); if (_rk !== _retryKey) { _retryKey = _rk; _retryCount = 0; } } catch (_) {}
    _setProgress(12, 'memuat ' + st.business + ' ' + st.filters.tahun + '-' + String(st.filters.bulan).padStart(2,'0') + (String(st.filters.periode) === '0' ? '-FULL' : '-P' + st.filters.periode) + '…');
    setBusiness(st.business);
    setFilters(st.filters);
    _savePanelStateGated(st); // refresh-safe: simpan hanya bila filter berubah
    updateHead(); renderChips();
    const prevStat = stat?.textContent || '';
    if (stat) stat.textContent = 'memuat ' + st.business + '…';
    if (metric) metric.textContent = 'memuat…';
    _setProgress(28, 'memuat polygon…');
    let prevFeatures = null;
    try { prevFeatures = _ctl?.get_state?.()?.count || 0; } catch (_) {}
    // Inkremental (pan/zoom, filter sama): JANGAN clear — diff by id di
    // set_features {full:false} hanya tambah id baru, peta tak berkedip.
    // Filter Bisnis berubah: clear penuh seperti dulu.
    let _wantIncremental = false;
    try {
      const _curKey = st.business + '|' + _filtKey(st);
      if (_lastLoadedFilt && _curKey === _lastLoadedFilt) {
        _wantIncremental = true;
      } else {
        // clear DULU sebelum server push ke antrean — anti balapan bridge vs wipe
        try { _ctl?.clear_features(); } catch (_) {}
      }
    } catch (_) {
      try { _ctl?.clear_features(); } catch (_) {}
    }
    // P2-3 hybrid: matikan PMTiles layer saat bukan business petak
    if (st.business !== 'petak' && _ctl && typeof _ctl.set_pmtiles_visibility === 'function') {
      try { _ctl.set_pmtiles_visibility(false); } catch (_) {}
    }
    _setProgress(42, 'menghubungi server…');
    try {
      const res = await ((_spatialTemplate)
        ? (async () => {
            // Template eksplisit dari ANNA — query langsung, bukan resolveTemplate.
            const _rt = resolveTemplate({ business: st.business, filters: st.filters });
            const _params = { ...(_rt.params || {}), ...(st.filters || {}) };
            // normalisasi angka agar SQL dapat int, bukan string dropdown
            for (const _k of ['tahun','bulan','periode','limit']) {
              const _v = parseInt(_params[_k]);
              if (Number.isFinite(_v)) _params[_k] = _v;
            }
            const _tok2 = document.querySelector('meta[name="ana-token"]')?.content || '';
            const _r = await fetch('/api/simoge/show_on_map', {
              method: 'POST',
              headers: { 'X-Ana-Token': _tok2, 'Content-Type': 'application/json' },
              credentials: 'same-origin',
              body: JSON.stringify({ template: _spatialTemplate, params: _params, drive: false }),
            });
            const _d = await _r.json().catch(() => ({}));
            if (!_r.ok || !_d.ok) return { ok: false, error: _d.error || ('HTTP ' + _r.status), template: _spatialTemplate, params: _params, retriable: _r.status >= 500 };
            return { ok: true, ..._d, template: _d.template || _spatialTemplate, params: _params, warna_counts: _d.warna_counts || {} };
          })()
        : loadBusinessData({ business: st.business, filters: st.filters }));
      if (mySeq !== _loadSeq) { _loading = false; if (_pending) { _pending = false; scheduleReload(); } return; }
      _setProgress(58, res.ok ? 'merender ' + (res.features || 0) + ' polygon…' : 'gagal — ' + (res.error || 'unknown').slice(0,40));
      if (!res.ok) {
        if (stat) stat.textContent = (res.error || 'gagal memuat').slice(0, 120) + (prevFeatures ? ' \u2014 menampilkan data sebelumnya' : '');
        if (metric && !prevFeatures) metric.textContent = '-';
        if (metric && prevFeatures) metric.textContent = prevStat;
        // KPI hanya di-reset saat filter berubah; gagal pada pan/zoom murni
        // mempertahankan angka terakhir (teks error tetap tampil di stat).
        if (_fkChanged) { renderKPIs(st.business, st.filters.kategori, {}, 0); _lastKpiFilt = _fkNow; }
        renderInsight(st.business, res.error || 'gagal', 0, {});
        try { if (_ctl && _ctl.clear_aktivitas_points) _ctl.clear_aktivitas_points(true); } catch (_) {}
        _hideProgressSoon(false);
        log('map', 'MAP', 'gagal ' + st.business + ': ' + (res.error || 'unknown') + (res.retriable ? ' (retriable)' : ''));
        if (!_firstLoadDone && res.retriable && _awaitingFeatures === null) setTimeout(() => { if (!_loading && !_firstLoadDone) reloadBusiness(); }, 1400);
      } else {
        _setProgress(72, 'merender ' + res.features + ' polygon…');
        const msg = res.features + ' polygon \u00b7 ' + res.template;
        if (stat) stat.textContent = msg;
        if (res.features === 0) {
          if (metric) metric.textContent = '0 polygon \u00b7 ' + ((res.explanation || 'tidak ada data untuk filter ini').slice(0, 120));
        } else {
          if (metric) metric.textContent = res.features + ' polygon \u00b7 ' + ((res.explanation || '').slice(0, 100));
        }
        const wc = res.warna_counts || {};
        setDataset({ template: res.template, params: res.params, row_count: res.row_count, features: res.features, warna_counts: wc });
        setMetrics({ shown: res.features, total: res.features, warna_counts: wc });
        // KPI dikunci filter: pan/zoom (kunci sama) = angka tak disentuh.
        if (_fkChanged) { renderKPIs(st.business, st.filters.kategori, wc, res.features); _lastKpiFilt = _fkNow; }
        renderInsight(st.business, res.explanation || '', res.features, wc);
        // polygon belum tentu tampil — tunggu MAP_FEATURES_LOADED (bridge 400ms). Jangan hide di sini.
        if (res.features === 0) {
          _setProgress(84, 'tidak ada polygon untuk filter ini');
          _hideProgressSoon(true);
          _firstLoadDone = true;
          _awaitingFeatures = null;
          if (_renderWatchdog) { clearTimeout(_renderWatchdog); _renderWatchdog = null; }
        } else {
          _awaitingFeatures = res.features;
          _awaitingSeq = mySeq;
          _setProgress(64, 'menunggu render ' + res.features + ' polygon di peta…');
          // drain langsung: jangan tunggu interval bridge.
          // teruskan _wantIncremental agar pan/zoom diff-by-id (anti flicker).
          try { await _drainBusinessQueue(res.map_id, _wantIncremental, res.template); } catch (_) {}
          // Fix ganti-bisnis blank: enforce tier visibility SETELAH drain,
          // sebelum cek ok. Tanpa ini polygon baru nempel tapi hidden bila
          // _tierMode basi (sisa zoom rendah sesi sebelumnya) — count>0
          // tapi peta kosong, dan watchdog salah hitung 'render gagal'.
          try { _maybeSwitchTier(map.getZoom()); } catch (_) {}
          // count < features normal: template punya LIMIT, server masih melapor
          // jumlah pre-limit (809) sementara peta hanya bisa gambar 800. Yang
          // penting render terjadi, bukan angkanya persis sama.
          try {
            const cur0 = _ctl?.get_state?.()?.count || 0;
            const ok = cur0 > 0 && cur0 >= Math.max(1, Math.floor(res.features * 0.8));
            if (ok) {
              if (_renderWatchdog) { clearTimeout(_renderWatchdog); _renderWatchdog = null; }
              // guard inkremental maju HANYA setelah render sukses — pan/zoom
              // berikutnya diff-by-id, bukan clear. Maju sebelum POST membuat
              // data belum render dianggap loaded dan tiap pan re-clear.
              try { _lastLoadedFilt = st.business + '|' + _filtKey(st); } catch (_) {}
              _retryCount = 0; // sukses render = kuota retry pulih untuk gangguan berikut
              _setProgress(96, 'polygon tampil — ' + cur0 + ' feat');
              _hideProgressSoon(true);
              _firstLoadDone = true;
              _awaitingFeatures = null;
              // Fit SEKALI per ganti filter (first load / ANNA spatial_set).
              // Pan/zoom user murni render tanpa fit — tanpa ini fit_all fire
              // moveend → _pushViewport → reload lagi + snapback ke extent lama.
              // Pengecualian: viewport baru dipulihkan dari simpanan (refresh) —
              // hormati fokus user, jangan timpa dengan fit.
              try {
                const _fk = _filtKey(st);
                if (_fk !== _lastFittedFilt) {
                  _lastFittedFilt = _fk;
                  if (_vpRestored) { _vpRestored = false; }
                  else {
                  _suppressVp = true;
                  try { _ctl?.fit_all?.(0.05); } catch (_) {}
                  // moveend dari fit animasi datang async — resync key dulu,
                  // baru buka suppress agar gesture user berikutnya lolos.
                  setTimeout(() => { try { _lastVp = _readVp().key; } catch (_) {} _suppressVp = false; }, 500);
                  }
                }
              } catch (_) {}
            }
            // P2-3 hybrid: init tier setelah render & fit pertama
            try { _maybeSwitchTier(map.getZoom()); } catch (_) {}
          } catch (_) {}
          if (_renderWatchdog) clearTimeout(_renderWatchdog);
          // ambang sama: <80% expected = baru dianggap gagal
          const need = () => Math.max(1, Math.floor((_awaitingFeatures || 0) * 0.8));
          _renderWatchdog = setTimeout(() => {
            const cur = (()=>{ try { return _ctl?.get_state?.()?.count || 0; } catch(_){ return 0; } })();
            if (_awaitingFeatures !== null && cur < need()) {
              _setProgress(64, 'render terlambat (' + cur + '/' + _awaitingFeatures + ') — cek koneksi atau klik Muat');
            }
            // Retry eksplisit maks 3x per filter, lalu fail-hide seperti dulu.
            // Tanpa counter: blank intermiten = user klik manual selamanya.
            setTimeout(() => {
              const cur2 = (()=>{ try { return _ctl?.get_state?.()?.count || 0; } catch(_){ return 0; } })();
              if (_awaitingFeatures !== null && cur2 < need()) {
                if (_retryCount < 3 && !_loading) {
                  _retryCount++;
                  _awaitingFeatures = null;
                  _setProgress(28, 'coba lagi ' + _retryCount + '/3…');
                  try { log('map', 'MAP', 'auto-retry ' + _retryCount + '/3'); } catch (_) {}
                  setTimeout(() => { if (!_loading && !_firstLoadDone) reloadBusiness(); }, 900);
                } else {
                  _awaitingFeatures = null;
                  _hideProgressSoon(false);
                  if (stat) stat.textContent = 'render gagal — klik Muat';
                }
              }
            }, 3000);
          }, 3000);
        }
        // ── pin-point aktivitas (GPS foto) — only when biz=aktivitas ──
        try {
          if (st.business === 'aktivitas' && _ctl && typeof _ctl.set_aktivitas_points === 'function') {
            const _tok = document.querySelector('meta[name="ana-token"]')?.content || '';
            // Cap pin longgar-tetap 4000 (batas aman Leaflet ~4k circleMarker):
            // cap berbasis jumlah polygon TERBUKTI memotong data (polygon
            // bisa tersaring viewport < total; pin periode penuh terpotong
            // ke 600). Periode tersibuk ±2000 baris < 4000. ORDER BY tanggal
            // DESC: bila >4000, yang terpotong = terlama (terdokumentasi).
            const pinLimit = 4000;
            const r2 = await fetchAktivitasPoints({ business: st.business, filters: st.filters }, { limit: pinLimit });
            if (r2 && r2.ok && Array.isArray(r2.rows)) {
              // Return hitung marker yang benar-benar tampil (baris tanpa
              // koordinat dilewati set_aktivitas_points) — itulah angka pin.
              let _pins = r2.rows.length;
              try {
                const _pr = _ctl.set_aktivitas_points(r2.rows, { token: _tok });
                if (_pr && Number.isFinite(_pr.count)) _pins = _pr.count;
              } catch (_) { try { _ctl.set_aktivitas_points(r2.rows, { token: _tok }); } catch (_) {} }
              // Pin hanya tampil di Z>=12 (aturan zoom user 2026-10-04);
              // di bawah itu data tetap dimuat tapi layer hidden.
              const _pz = map.getZoom();
              try { _ctl.set_aktivitas_visibility(_pz >= 12); } catch (_) {}
              const fotoN = r2.rows.filter(function(x){ return x.aktivitas_photo || x.foto_file; }).length;
              // Hitungan jujur dari server (window total, pra-LIMIT): N pin
              // dari M aktivitas, K tanpa koordinat (tak bisa jadi pin).
              const _tot = (r2.rows[0] && r2.rows[0]._total != null) ? Number(r2.rows[0]._total) : r2.rows.length;
              const _nc = (r2.rows[0] && r2.rows[0]._no_coord != null) ? Number(r2.rows[0]._no_coord) : 0;
              const _kat = String(st.filters.kategori || 'semua').toLowerCase();
              const _idleNote = (_kat === 'idle') ? ' (periode lalu)' : '';
              if (stat) {
                stat.textContent += ' \u00b7 ' + _pins + ' pin' + _idleNote + ' dari ' + _tot + ' aktivitas'
                  + (_nc ? ' (' + _nc + ' tanpa koordinat)' : '')
                  + ' (' + fotoN + ' foto)'
                  + (_pz < 12 ? ' \u00b7 pin tersembunyi di zoom ini (\u226512 untuk tampil)' : '');
                if (!r2.rows.length && (_kat === 'idle' || _kat === 'bongkor')) {
                  stat.textContent += ' \u00b7 wajar: petak ' + _kat + ' tanpa aktivitas periode berjalan';
                }
              }
              // pin siap — polygon sudah confirmed via MAP_FEATURES_LOADED, pin hide terpisah
              if (_awaitingFeatures === null) { _setProgress(96, r2.rows.length + ' pin aktivitas'); _hideProgressSoon(true); }
              else { _setProgress(92, r2.rows.length + ' pin aktivitas — menunggu polygon…'); }
              _firstLoadDone = true;
              log('map', 'MAP', 'aktivitas pin ' + _pins + '/' + r2.rows.length + ' (' + fotoN + ' foto)');
            } else if (r2 && !r2.ok) {
              log('map', 'MAP', 'aktivitas pin gagal: ' + (r2.error || 'unknown').slice(0,60));
            }
          } else if (st.business !== 'aktivitas' && _ctl && typeof _ctl.clear_aktivitas_points === 'function') {
            try { _ctl.clear_aktivitas_points(true); _ctl.set_aktivitas_visibility(false); } catch (_) {}
          }
        } catch (e2) {
          log('map', 'MAP', 'aktivitas pin exception ' + String(e2?.message || e2).slice(0,60));
        }
        log('map', 'MAP', st.business + ' -> ' + res.template + ' ' + res.features + ' feat  (menunggu MAP_FEATURES_LOADED)');
        // jangan hide di sini — tunggu event render beneran
      }
    } catch (e) {
      if (stat) stat.textContent = String(e?.message || e).slice(0, 120) + (prevFeatures ? ' \u2014 stale' : '');
      _hideProgressSoon(false);
      log('map', 'MAP', 'exception ' + String(e?.message || e).slice(0, 80));
      // auto-retry once for first load
      if (_renderWatchdog) { clearTimeout(_renderWatchdog); _renderWatchdog=null; } _awaitingFeatures=null;
      if (!_firstLoadDone && _awaitingFeatures === null) setTimeout(() => { if (!_loading && !_firstLoadDone) reloadBusiness(); }, 1600);
    } finally {
      _loading = false;
      if (_pending) { _pending = false; scheduleReload(); }
    }
  }
  function scheduleReload() {
    clearTimeout(_debounce);
    _debounce = setTimeout(reloadBusiness, 420);
  }

  btnFilter?.addEventListener('click', () => {
    panelFilter?.classList.toggle('collapsed');
    btnFilter.classList.toggle('active', !panelFilter?.classList.contains('collapsed'));
    setTimeout(() => map.invalidateSize(), 180);
  });
  btnKpi?.addEventListener('click', () => {
    kpiBox?.classList.toggle('collapsed');
    btnKpi.classList.toggle('active', !kpiBox?.classList.contains('collapsed'));
  });
  // K1: klik insight expand/collapse.
  insightBox?.addEventListener('click', () => { insightBox.classList.toggle('expanded'); });
  // K4: mobile (≤780px, via device.js) KPI mulai collapse — hemat peta 360px. Desktop tetap tampil.
  try {
    if (_isMobileDevice()) kpiBox?.classList.add('collapsed');
  } catch (_) {
    if (window.matchMedia && window.matchMedia('(max-width: 780px)').matches) {
      kpiBox?.classList.add('collapsed');
    }
  }
  bizSel?.addEventListener('change', () => {
    // Ganti bisnis manual = reset kategori ke Semua + buang subset/template
    // ANA (_spatialWarna/_spatialTemplate), agar konteks lama tak terbawa
    // (nyasar) ke bisnis baru. Jalur ANA (spatial_set) tak lewat listener
    // ini (set .value programatik tak fire change) — tetap utuh.
    try { if (katSel) katSel.value = 'semua'; } catch (_) {}
    _spatialWarna = ''; _spatialTemplate = null;
    syncKatVisibility(); updateLegend(bizSel.value, katSel?.value || 'semua'); updateHead(); renderChips(); scheduleReload(); });
  katSel?.addEventListener('change', () => {
    // Kategori manual = niat eksplisit user: buang subset/template ANA agar
    // tak menimpa pilihan (kasus nyasar yang sama). Jalur ANA tak fire change.
    _spatialWarna = ''; _spatialTemplate = null;
    updateLegend(bizSel?.value || 'petak', katSel?.value || 'semua'); renderChips(); scheduleReload(); });
  // Waktu + pembaharuan_ke pakai listener generik; wilayah sudah punya cascade-specific
  [fBulan, fTahun, fPeriode, fPemKe, fSampai, fJenisAkt].forEach(function(c){ if(c) c.addEventListener('change', function(){ updateHead(); renderChips(); scheduleReload(); }); });
  fApply?.addEventListener('click', reloadBusiness);
  fReset?.addEventListener('click', function(){
    if (fBulan) fBulan.value=String(d.getMonth()+1);
    if (fTahun) fTahun.value='2026';
    if (fPeriode) fPeriode.value=d.getDate()<=15?'1':'2';
    if (fPemKe) fPemKe.value='';
    if (typeof fJenisAkt !== 'undefined' && fJenisAkt) fJenisAkt.value='';
    if (typeof fSampai !== 'undefined' && fSampai) fSampai.value='';
    // Respect scope lock: only reset unlocked dropdowns
    if (fDivre && !fDivre.disabled) fDivre.value='';
    if (fKph && !fKph.disabled) fKph.value='';
    if (fBkph && !fBkph.disabled) fBkph.value='';
    if (fRph && !fRph.disabled) fRph.value='';
    if (fTpg && !fTpg.disabled) fTpg.value='';
    try { renderWilayah(); } catch (_) {} // kembalikan opsi anak penuh sesuai scope
    if (katSel) katSel.value='semua'; if (bizSel) bizSel.value='petak';
    _spatialWarna = ''; _spatialTemplate = null; // reset manual = buang semua titipan ANA
    try { localStorage.removeItem('ana_spatial_panel_v1'); } catch (_) {} // refresh mulai dari default lagi
    try { map.setView(CENTER, 11); } catch (_) {} // reset manual = fokus awal juga
    try { // reset manual = layer awal juga (basemap bila Esri ok, overlay nyala)
      if (typeof esriRemembered === 'undefined' || esriRemembered !== '0') {
        try { _ctl?.set_basemap?.('Satelit'); } catch (_) {}
        try { if (!map.hasLayer(refLbl)) refLbl.addTo(map); } catch (_) {}
      }
      try { _ctl?.set_layer_visibility?.('Petak', true); } catch (_) {}
    } catch (_) {}
    syncKatVisibility(); updateLegend('petak','semua'); updateHead(); renderChips(); reloadBusiness();
  });
  btnRefresh?.addEventListener('click', reloadBusiness);

  // ── P2-4: modal Pengaturan Tiles (rebuild manual + cron harian) ──
  // Token dari meta ana-token (disuntik server via __ANA_TOKEN__).
  // Status: GET /api/tiles/status. Rebuild: GET /api/tiles/rebuild (bisa
  // 1-2 menit — tombol dikunci selama jalan). Cron: POST /api/tiles/cron
  // {action: status|enable|disable, schedule}.
  (function(){
    const btn = $sel('#spatialTilesBtn'), modal = $sel('#spatialTilesModal');
    if (!btn || !modal) return;
    const stBox = $sel('#spatialTilesStatus'), msgBox = $sel('#spatialTilesMsg');
    const schedIn = $sel('#spatialTilesSched');
    const tok = () => document.querySelector('meta[name="ana-token"]')?.content || '';
    const H = () => ({ 'X-Ana-Token': tok(), 'Content-Type': 'application/json' });
    const fmtB = (n) => (n == null ? '-' : (n > 1048576 ? (n/1048576).toFixed(1)+' MB' : Math.round(n/1024)+' KB'));
    const fmtT = (t) => { try { return t ? new Date(t*1000).toLocaleString('id-ID') : '-'; } catch(_) { return '-'; } };
    const say = (t, err) => { if (msgBox) { msgBox.textContent = t || ''; msgBox.style.color = err ? '#EF4444' : ''; } };
    async function loadStatus() {
      if (stBox) stBox.textContent = 'memuat…';
      try {
        const r = await fetch('/api/tiles/status', { headers: { 'X-Ana-Token': tok() } });
        const d = await r.json().catch(() => ({}));
        if (!r.ok || d.ok === false) { if (stBox) stBox.textContent = 'gagal: ' + (d.error || ('HTTP '+r.status)); return; }
        const pm = d['petak.pmtiles'] || {}, nd = d['petak.ndjson'] || {};
        const cron = (d.cron && d.cron.length) ? d.cron.join('\n') : '(cron mati — rebuild harian tidak jalan)';
        if (stBox) stBox.innerHTML =
          '<div>PMTiles: <b>' + (pm.exists ? fmtB(pm.bytes)+' · '+fmtT(pm.mtime) : '<span style="color:#EF4444">hilang</span>') + '</b></div>'
          + '<div>NDJSON: <b>' + (nd.exists ? (nd.lines ?? '?')+' baris · '+fmtB(nd.bytes) : '<span style="color:#EF4444">hilang</span>') + '</b></div>'
          + '<div>Cron: <pre style="white-space:pre-wrap;margin:4px 0">' + cron.replace(/</g,'&lt;') + '</pre></div>'
          + '<div>Log: <pre style="white-space:pre-wrap;margin:4px 0;max-height:120px;overflow:auto">' + String(d.log_tail||'').replace(/</g,'&lt;') + '</pre></div>';
        say('');
      } catch(e) { if (stBox) stBox.textContent = 'gagal: ' + String(e?.message || e).slice(0,120); }
    }
    btn.addEventListener('click', () => { modal.classList.toggle('hidden'); if (!modal.classList.contains('hidden')) loadStatus(); });
    $sel('#spatialTilesClose')?.addEventListener('click', () => modal.classList.add('hidden'));
    $sel('#spatialTilesRebuild')?.addEventListener('click', async function(){
      this.disabled = true; say('rebuild jalan… (1-2 menit)');
      try {
        const r = await fetch('/api/tiles/rebuild', { headers: { 'X-Ana-Token': tok() } });
        const d = await r.json().catch(() => ({}));
        say(r.ok && !d.error ? 'rebuild OK — ' + JSON.stringify(d.build || d).slice(0,160) : 'gagal: ' + (d.error || ('HTTP '+r.status)), !(r.ok && !d.error));
        loadStatus();
      } catch(e) { say('gagal: ' + String(e?.message || e).slice(0,120), true); }
      finally { this.disabled = false; }
    });
    async function cronAct(action) {
      say('cron ' + action + '…');
      try {
        const r = await fetch('/api/tiles/cron', { method: 'POST', headers: H(), body: JSON.stringify({ action, schedule: schedIn?.value || '' }) });
        const d = await r.json().catch(() => ({}));
        say(r.ok && d.ok !== false ? 'cron ' + action + ' OK' : 'gagal: ' + (d.error || ('HTTP '+r.status)), !(r.ok && d.ok !== false));
        loadStatus();
      } catch(e) { say('gagal: ' + String(e?.message || e).slice(0,120), true); }
    }
    $sel('#spatialTilesCronOn')?.addEventListener('click', () => cronAct('enable'));
    $sel('#spatialTilesCronOff')?.addEventListener('click', () => cronAct('disable'));
  })();

  // ── P1 viewport: pan/zoom → _viewportExtra + reload debounce ──
  // Tanpa ini bounds/zoom tak pernah terisi, server selalu full-scan 809 polygon.
  let _vpT = null;
  let _lastVp = '';
  function _readVp() {
    const b = map.getBounds();
    const vp = {
      bounds: [+b.getWest().toFixed(6), +b.getSouth().toFixed(6), +b.getEast().toFixed(6), +b.getNorth().toFixed(6)],
      zoom: map.getZoom(),
    };
    vp.key = JSON.stringify(vp.bounds) + '|z=' + vp.zoom;
    return vp;
  }
  // Kunci filter NON-viewport: fit hanya bila filter bisnis berubah
  // (first load / ANNA spatial_set), bukan tiap pan/zoom.
  function _filtKey(st) {
    const f = { ...(st.filters || {}) };
    delete f.bounds; delete f.zoom; delete f.page_size; delete f.aggregated_level;
    return st.business + '|' + JSON.stringify(f);
  }
  function _pushViewport() {
    try {
      if (_suppressVp) return; // gerakan dari fit_all programmatic — bukan user
      const vp = _readVp();
      if (vp.key === _lastVp) return; // guard anti-loop: echo setView/fit yang sama
      _lastVp = vp.key;
      _viewportExtra.bounds = vp.bounds;
      _viewportExtra.zoom = vp.zoom;
      _viewportExtra.page_size = 1000;
      clearTimeout(_vpT);
      _vpT = setTimeout(scheduleReload, 600);
      // P2-3 hybrid: switch PMTiles <-> GeoJSON berdasarkan zoom (hanya business petak)
      try { _maybeSwitchTier(vp.zoom); } catch (_) {}
    } catch (_) {}
  }
  map.on('moveend', _pushViewport);
  map.on('zoomend', _pushViewport);
  map.on('moveend', _scheduleDeclutter);
  map.on('zoomend', _scheduleDeclutter);
  // Kunci viewport awal = posisi boot: moveend/zoomend dari setup
  // (invalidateSize, fit pertama) tidak dianggap gerakan user sehingga tak
  // memicu reload viewport balapan dengan kick awal (sumber hitungan
  // polygon/pin tak stabil antar refresh).
  try { _lastVp = _readVp().key; } catch (_) {}
  // Kontrol layer bawaan Leaflet mengutak-atik layer langsung (bypass state
  // _ctl): selaraskan state lewat API idempoten (tanpa efek ganda) agar
  // visibilitas ikut tersimpan via MAP_LAYER_CHANGED/MAP_STYLE_CHANGED.
  map.on('overlayadd overlayremove', function(e) {
    try {
      const l = e && e.layer;
      const id = (l === petakLayer) ? 'Petak' : ((l === refLbl) ? 'Label' : null);
      if (!id || !_ctl || typeof _ctl.set_layer_visibility !== 'function') return;
      const want = (e.type === 'overlayadd');
      try {
        const cur = (_ctl.get_layers() || []).find(function(o){ return String(o.id) === id; });
        if (cur && !!cur.visible === want) return;
      } catch (_) {}
      try { _ctl.set_layer_visibility(id, want); } catch (_) {}
    } catch (_) {}
  });
  map.on('baselayerchange', function(e) {
    try {
      const l = e && e.layer;
      const id = (l === satGroup) ? 'Satelit' : ((l === darkGroup) ? 'Gelap' : null);
      if (!id || !_ctl || typeof _ctl.set_basemap !== 'function') return;
      try { if (_ctl.get_state && _ctl.get_state().basemap === id) return; } catch (_) {}
      try { _ctl.set_basemap(id); } catch (_) {}
    } catch (_) {}
  });

  // P2-3 hybrid tier — aturan zoom user 2026-10-04:
  // Z<=11 polygon saja (PMTiles, tanpa analisa/pin); Z>=12 analisa + pin tampil (GeoJSON).
  // Dipanggil setelah load sukses + saat zoom berubah (_pushViewport).
  let _tier = null; // 'pmtiles' | 'geojson'
  function _maybeSwitchTier(zoom) {
    // biz dari kontrol panel, fallback state (ANA spatial_set tanpa sentuh dropdown).
    let biz = 'petak';
    try { biz = bizSel?.value || getSpatialState()?.business || 'petak'; } catch (_) {}
    const z = typeof zoom === 'number' ? zoom : map.getZoom();
    // Pin aktivitas hanya tampil di Z>=12, semua business. Harus sebelum
    // return biz — kalau tidak, ganti business di Z rendah pin tetap tampil.
    try {
      if (_ctl && typeof _ctl.set_aktivitas_visibility === 'function') {
        if (z < 12) _ctl.set_aktivitas_visibility(false);
        else if (biz === 'aktivitas' && _ctl.aktivitasPoints && _ctl.aktivitasPoints.size) {
          _ctl.set_aktivitas_visibility(true);
        }
      }
    } catch (_) {}
    // Enforce polygon untuk SEMUA business (fix akar 2026-10-04): return dini
    // biz!=='petak' membuat polygon aktivitas menutupi PMTiles di Z<=11.
    // PMTiles petak = base netral HANYA untuk bisnis petak di Z<=11.
    // Bisnis lain (aktivitas/produksi/matriks) selalu GeoJSON berwarna
    // di semua zoom — kalau tidak, tile/KPI/legenda terkunci warna petak.
    const want = (biz !== 'petak') ? 'geojson' : (z <= 11 ? 'pmtiles' : 'geojson');
    if (want !== _tier) {
      if (want === 'pmtiles') {
        // File petak ter-scope + overview choropleth (ganti URL global legacy).
        _scheduleOverview();
      } else {
        // Aktifkan GeoJSON (warna analisa + popup per-polygon), sembunyikan PMTiles + bounds
        if (_ctl && typeof _ctl.set_pmtiles_visibility === 'function') {
          _ctl.set_pmtiles_visibility(false);
        }
        try { _ctl.set_pmtiles_group_visible && _ctl.set_pmtiles_group_visible('bounds', false); } catch (_) {}
        if (_ovOn) { _ovOn = false; try { updateLegend(bizSel?.value || 'petak', katSel?.value || 'semua'); } catch (_) {} }
      }
      _tier = want;
    }
    _scheduleOverview(); // selaraskan sumber tile scope (murah bila kunci sama)
    _scheduleLabels(); // label wilayah mengikuti zoom (murah: kunci + cache)
    // Selalu enforce (bukan hanya saat tier berubah): reload filter me-render
    // ulang polygon dalam keadaan visible, dan tier guard lama return dini
    // sehingga polygon segar tetap tampil menutupi PMTiles di Z rendah.
    try {
      if (_ctl && typeof _ctl.set_petak_polygons_visibility === 'function') {
        _ctl.set_petak_polygons_visibility(want === 'geojson');
      }
    } catch (_) {}
  }

  // ── Overview choropleth KPH + tile petak ter-scope ──
  // Aturan akses: DIVRE = KPH se-divre; ADM = KPH-nya + bounds netral;
  // DIREKSI = semua. Server menegakkan ulang per request tile (fail-closed).
  // z≤10 + bisnis petak + scope >1 KPH → choropleth bounds berwarna agregat
  // live (merah ≥25% bongkor / kuning ≥30% kurang atau terpenuhi <60% /
  // hijau sisanya); z≤10 single-KPH (ADM) → petak detail + outline netral.
  // Tak pernah reload data bisnis (hanya layer) → anti loop.
  let _tileManifest = null;
  let _manWarned = false;
  let _ovKey = '', _ovTimer = null, _ovOn = false;
  let _ovSeq = 0; // kunci murahan request overview — respons basi dibuang
  const _ovColorCache = {}; // key overview -> {colors, rows} (cap 60)
  const _tokPm = () => { try { return document.querySelector('meta[name="ana-token"]')?.content || ''; } catch (_) { return ''; } };
  async function _tileManifestLoad() {
    if (_tileManifest) return _tileManifest;
    try {
      const r = await fetch('/api/tiles/manifest', { headers: { 'X-Ana-Token': _tokPm() }, credentials: 'same-origin' });
      const j = await r.json().catch(() => ({}));
      if (j && Array.isArray(j.files)) { _tileManifest = j; return j; }
    } catch (_) {}
    return null;
  }
  function _scopeKphList() {
    // KPH dalam scope login (value=kode). Tanpa cache wilayah = [].
    try {
      const scope = _userScope();
      const all = ((_wilayahCache && _wilayahCache.kph) || []).map(function(o){ return String(o.value); });
      if (scope.jabatan === 'DIREKSI' || scope.jabatan === 'ADMINISTRATOR') return all;
      if (scope.kph) return all.filter(function(v){ return v === scope.kph; });
      if (scope.divre) {
        const out = [];
        for (const v of all) {
          try { if (String(_chainOf('kph', v).divre || '') === String(scope.divre)) out.push(v); } catch (_) {}
        }
        return out;
      }
      for (const L of ['bkph', 'rph']) {
        const v = scope[L];
        if (v) { try { const k = _chainOf(L, v).kph; if (k) return [String(k)]; } catch (_) {} }
      }
      return all; // tanpa scope = terbuka (server tetap clamp)
    } catch (_) { return []; }
  }
  function _scopeDivreList() {
    try {
      const scope = _userScope();
      const all = ((_wilayahCache && _wilayahCache.divre) || []).map(function(o){ return String(o.value); });
      if (scope.jabatan === 'DIREKSI' || scope.jabatan === 'ADMINISTRATOR') return all;
      if (scope.divre) return [scope.divre];
      const k = _scopeKphList()[0];
      if (k) { try { const d = _chainOf('kph', k).divre; if (d) return [String(d)]; } catch (_) {} }
      return all;
    } catch (_) { return []; }
  }
  function _ovColor(r) {
    try {
      const t = Number(r.total_petak) || 0;
      if (!t) return null;
      const b = Number(r.bongkor || 0) / t, k = Number(r.kurang || 0) / t, s = Number(r.terpenuhi || 0) / t;
      if (b >= 0.25) return '#EF4444';
      if (k >= 0.30 || s < 0.60) return '#EAB308';
      return '#22C55E';
    } catch (_) { return null; }
  }
  function _ovLegend() {
    // Guard di updateLegend menyertakan bar overview bila _ovOn (anti duplikat).
    try { updateLegend(bizSel?.value || 'petak', katSel?.value || 'semua'); } catch (_) {}
  }
  function _ovInsight(rows, biz) {
    // Angka per KPH menyertai warna. Label mengikuti bisnis:
    // petak = B/K/T; aktivitas = B/I/A;
    // produksi = actual vs target + achievement% (basis warna KPH).
    try {
      if (!insightBox || !Array.isArray(rows) || !rows.length) return;
      const b = String(biz || 'petak');
      const tag = b === 'aktivitas' ? ['B', 'I', 'A'] : ['B', 'K', 'T'];
      const lines = rows.map(function(r) {
        if (b === 'produksi') {
          const a = Number(r.achievement_pct);
          const av = Number(r.actual_kg || 0), tv = Number(r.target_kg || 0);
          return esc(String(r.kph || r.nama_wilayah || r.kode_kph || r.kode_wilayah)) + ' ' + av.toLocaleString('id-ID') + '/' + tv.toLocaleString('id-ID') + ' kg (' + (Number.isFinite(a) ? a.toFixed(1).replace('.', ',') + '%' : '-') + ')';
        }
        return esc(String(r.kph || r.kode_kph)) + ' ' + (r.total_petak || 0) + ' petak — ' + tag[0] + (r.bongkor || 0) + ' ' + tag[1] + (r.kurang || 0) + ' ' + tag[2] + (r.terpenuhi || 0);
      });
      insightBox.dataset.lastBiz = 'petak';
      insightBox.dataset.lastExpl = lines.join(' · ');
      insightBox.dataset.lastFeat = String(rows.length);
      insightBox.dataset.lastCounts = '{}';
      updateHead();
    } catch (_) {}
  }
  function _scheduleOverview() {
    try { clearTimeout(_ovTimer); } catch (_) {}
    _ovTimer = setTimeout(function() { try { _refreshOverview(); } catch (_) {} }, 200);
  }
  async function _refreshOverview() {
    const mySeq = ++_ovSeq;
    try {
      if (!_ctl || typeof _ctl.set_pmtiles_sources !== 'function') return;
      const biz = bizSel?.value || 'petak';
      const z = map.getZoom();
      const tahun = parseInt(fTahun?.value) || new Date().getFullYear();
      const tok = _tokPm();
      const man = await _tileManifestLoad();
      const have = new Set(((man && man.files) || []).map(function(f){ return f.name; }));
      const kphList = _scopeKphList();
      try { log('map', 'MAP', 'overview check z' + map.getZoom() + ' biz=' + biz + ' kph=' + kphList.length + ' divre=' + _scopeDivreList().join(',')); } catch (_) {}
      // 1. Grup petak: reconcile ke file scope (ganti URL global legacy).
      // Manifest tak terbaca = JANGAN asumsikan semua file ada (fail-safe:
      // request file tak ada = 404 + error vendor tiap zoom). Fallback legacy.
      const manOk = !!(man && Array.isArray(man.files));
      if (!manOk && !_manWarned) {
        _manWarned = true;
        try { log('map', 'MAP', 'manifest tile tak terbaca — pakai legacy sementara'); } catch (_) {}
      }
      const petakSrc = [];
      if (manOk) {
        const _byBase = {};
        for (const f of ((man && man.files) || [])) {
          try {
            const _nm = String(f.name || '');
            // varian bertahun menang atas legacy tanpa tahun
            const _m = _nm.match(/^(kph_\d+?)(?:_(\d{4}))?\.pmtiles$/);
            if (!_m) continue;
            const _base = _m[1] + '.pmtiles';
            const _yr = _m[2] ? parseInt(_m[2]) : 0;
            if (!_byBase[_base] || _yr > _byBase[_base].yr) _byBase[_base] = { yr: _yr, name: _nm };
          } catch (_) {}
        }
        for (const k of kphList) {
          const hit = _byBase['kph_' + k + '.pmtiles'];
          if (!hit) continue; // belum dibangun → lewati (tanpa 404)
          const suffix = hit.yr ? '_' + hit.yr : '';
          petakSrc.push({ url: '/api/tiles/scope/kph/' + k + suffix + '.pmtiles', kind: 'petak' });
        }
      }
      if (!petakSrc.length) {
        // Fallback legacy bila manifest tak ada / file belum dibangun.
        try { _ctl.set_pmtiles({ url: '/api/tiles/petak.pmtiles', visible: map.getZoom() <= 11, token: tok }); } catch (_) {}
      } else {
        try { _ctl.set_pmtiles_sources('petak', petakSrc, { token: tok }); } catch (_) {}
      }
      // Reconcile menambah layer ke peta; di tier geojson (z>10) grup petak
      // harus tetap sembunyi (detail dari GeoJSON, bukan tile).
      try { if (map.getZoom() > 11) _ctl.set_pmtiles_group_visible('petak', false); } catch (_) {}
      // 2. Choropleth overview: petak/aktivitas/produksi/matriks + z≤10.
      // Multi-KPH selalu; scope 1-KPH di DB tetap overview berwarna bila
      // jabatan level atas (DIREKSI/ADMINISTRATOR/DIVRE) — bukan outline netral.
      // Warna tile = bake per-KPH sesuai bisnis (export_kph_overview per biz);
      // agregat angka per bisnis via template *_per_kph (kolom selaras).
      const multi = kphList.length !== 1;
      let _jabTop = '';
      try { _jabTop = (_userScope().jabatan || '').toUpperCase(); } catch (_) {}
      const _isTop = (_jabTop === 'DIREKSI' || _jabTop === 'ADMINISTRATOR' || _jabTop === 'DIVRE');
      const _ovBiz = (biz === 'petak' || biz === 'aktivitas' || biz === 'produksi' || biz === 'matriks' || biz === 'matrik') ? biz : '';
      const _kBulan = Math.max(1, Math.min(12, parseInt(fBulan?.value) || new Date().getMonth() + 1));
      const _kP = parseInt(fPeriode?.value);
      const _kPer = (_kP === 0 || _kP === 1 || _kP === 2) ? _kP : 1;
      const _kPemke = (String(fPemKe?.value || '').trim() || '');
      const _kJenis = (String((typeof fJenisAkt !== 'undefined' && fJenisAkt ? fJenisAkt.value : '') || '').trim() || '');
      const _kSampai = (String((typeof fSampai !== 'undefined' && fSampai ? fSampai.value : '') || '').trim() || '');
      const key = _ovBiz + '|' + z + '|' + tahun + '|' + _kBulan + '|' + _kPer + '|' + _kPemke + '|' + _kJenis + '|' + _kSampai + '|' + kphList.join(',') + '|' + _scopeDivreList().join(',');
      const wantOv = (!!_ovBiz && z <= 10 && kphList.length > 0 && (multi || _isTop));
      if (!wantOv) {
        try { window.__spatialOverview = { key: key, wantOv: false, kph: kphList.length, on: false }; } catch (_) {}
        if (_ovOn) {
          _ovOn = false;
          try { _ovHideGeo(); } catch (_) {}
          try { updateLegend(bizSel?.value || 'petak', katSel?.value || 'semua'); } catch (_) {}
        }
        _ovKey = key;
        // ADM single-KPH: outline netral konteks tetangga (tanpa warna bisnis).
        if (_ovBiz && z <= 10 && kphList.length === 1) { _neutralBounds(); }
        else { try { _ovHideGeo(); } catch (_) {} }
        return;
      }
      if (key === _ovKey && _ovOn) return; // sudah tampil
      _ovKey = key;
      const _bulan = _kBulan;
      const _periode = _kPer;
      const _pemke = _kPemke;
      const _jenis = _kJenis;
      if (['quare','semprot_cas','kerok','naik_batok','budaya_bersih','pulung'].includes(_jenis)) _ovParams.jenis_aktivitas = _jenis;
      const _sampai = _kSampai;
      if (['ya','tidak'].includes(_sampai)) _ovParams.sampai_dengan = _sampai;
      const _ovTpl = _ovBiz === 'aktivitas' ? 'aktivitas_per_kph'
        : _ovBiz === 'produksi' ? 'produksi_per_wilayah'
        : _ovBiz === 'matriks' || _ovBiz === 'matrik' ? 'efektivitas_per_kph'
        : 'efektivitas_per_kph';
      const _ovParams = { tahun };
      if (_ovBiz === 'aktivitas' || _ovBiz === 'produksi') {
        _ovParams.bulan = _bulan; _ovParams.periode = _periode;
        if (_ovBiz === 'aktivitas' && ['1', '2', '3', '4'].includes(_pemke)) _ovParams.pembaharuan_ke = _pemke;
        if (_ovBiz === 'produksi') _ovParams.level = 'kode_kph';
      }
      let rows = [];
      const colors = {};
      // Cache kunci warna: kombinasi pernah dihitung = pakai langsung,
      // tanpa query ulang (ganti bolak-balik bisnis/filter responsif).
      try {
        const _hit = _ovColorCache[key + '|c'];
        if (_hit && _hit.colors && Object.keys(_hit.colors).length) {
          rows = _hit.rows || [];
          for (const kk of Object.keys(_hit.colors)) colors[kk] = _hit.colors[kk];
        }
      } catch (_) {}
      if (!Object.keys(colors).length) {
        try {
          const rr = await queryStats(_ovTpl, _ovParams, { timeoutMs: 8000 });
          if (mySeq !== _ovSeq) return; // basi: bisnis/filter sudah ganti
          if (rr && rr.ok && Array.isArray(rr.rows)) rows = rr.rows;
        } catch (_) {}
      }
      for (const r of rows) {
        // Produksi: achievement tertimbang per KPH (bukan porsi petak hijau).
        // Merah <50, kuning 50-85, hijau >85 — selaras rkap_map 5 pita.
        try {
          if (_ovBiz === 'produksi') {
            const a = Number(r.achievement_pct);
            if (!Number.isFinite(a)) continue;
            const c = a < 50 ? '#EF4444' : a <= 85 ? '#EAB308' : '#22C55E';
            const k = String(r.kode_kph || r.kode_wilayah || '');
            if (k) colors[k] = c;
            continue;
          }
          const c = _ovColor(r); if (c) colors[String(r.kode_kph)] = c;
        } catch (_) {}
      }
      // Cache kunci warna per kombinasi biz|tahun|bulan|periode|pemke|scope —
      // ganti bolak-balik bisnis/filter = cat langsung, tanpa query ulang.
      try {
        const _ck = key + '|c';
        if (_ovColorCache[_ck]) { for (const kk of Object.keys(_ovColorCache[_ck])) colors[kk] = _ovColorCache[_ck][kk]; }
        else _ovColorCache[_ck] = colors;
      } catch (_) {}
      if (!Object.keys(colors).length) {
        // Agregat kosong/gagal: jangan tampilkan outline putih tanpa warna.
        _ovOn = false;
        try { _ovHideGeo(); } catch (_) {}
        try { log('map', 'MAP', 'overview off: agregat kosong'); } catch (_) {}
        return;
      }
      // Render: tile overview SOLID per divre (warna bake) + hit-layer transparan
      // (tooltip + klik drill). Aturan warna statis = pola tile petak.
      // Hanya file yang ada di manifest (fail-safe anti-404 seperti di atas).
      const oSrc = [];
      if (manOk) {
        const _byBase2 = {};
        for (const f of ((man && man.files) || [])) {
          try {
            const _nm = String(f.name || '');
            const _m = _nm.match(/^(overview_\d+?)(?:_(\d{4}))?\.pmtiles$/);
            if (!_m) continue;
            const _base = _m[1] + '.pmtiles';
            const _yr = _m[2] ? parseInt(_m[2]) : 0;
            if (!_byBase2[_base] || _yr > _byBase2[_base].yr) _byBase2[_base] = { yr: _yr, name: _nm };
          } catch (_) {}
        }
        for (const d of _scopeDivreList()) {
          const hit = _byBase2['overview_' + d + '.pmtiles'];
          if (!hit) continue;
          const suffix = hit.yr ? '_' + hit.yr : '';
          // Petak = warna bake file; bisnis lain = geometri sama, warna dari
          // agregat *_per_kph periode berjalan (filter per kode_kph).
          const _rules = (_ovBiz === 'petak') ? _ovTileRules() : _ovTileRules(colors);
          oSrc.push({ url: '/api/tiles/scope/overview_' + d + suffix + '.pmtiles', kind: 'petak',
                      rules: _rules, maxDataZoom: 10 });
        }
      }
      let ovOk = false;
      try {
        const rr = _ctl.set_pmtiles_sources('bounds', oSrc, { token: tok });
        ovOk = !!(rr && (rr.added > 0 || (rr.active || []).length > 0));
      } catch (_) { ovOk = false; }
      // Fallback: tanpa file overview (belum dibangun) = mode lama.
      if (!ovOk) {
        _ovOn = false;
        try { log('map', 'MAP', 'overview off: file overview tak ada'); } catch (_) {}
        return;
      }
      try { _ctl.set_pmtiles_group_visible('petak', false); } catch (_) {} // choropleth ganti petak di overview
      // Hit-layer transparan utk tooltip + klik (binding post-hoc, pola terverifikasi).
      try { await _ovShowHit(rows, false, _ovBiz); } catch (_) {}
      _ovOn = true;
      try { log('map', 'MAP', 'overview ON kph berwarna=' + Object.keys(colors).length); } catch (_) {}
      try { window.__spatialOverview = { key: key, wantOv: !!wantOv, kph: kphList.length, on: true, colored: Object.keys(colors).length }; } catch (_) {}
      _ovInsight(rows, _ovBiz);
      _ovLegend();
    } catch (_) {}
  }
  // Rules tile overview SOLID (fill penuh, bukan transparan/gradasi).
  // Default: filter prop `warna` bawaan file (bisnis petak). Bila colors
  // per-bisnis diberi (aktivitas/produksi/matriks), filter per kode_kph —
  // geometri file sama, warna dari agregat *_per_kph periode berjalan.
  function _ovTileRules(colors) {
    try {
      const P = window.protomapsL;
      const mk = function(fill) {
        return new P.PolygonSymbolizer({ fill: fill, opacity: 0.92, stroke: fill, width: 1.5, strokeOpacity: 0.9 });
      };
      if (colors && typeof colors === 'object') {
        const setOf = function(hex) {
          const s = new Set();
          for (const k of Object.keys(colors)) { if (colors[k] === hex) s.add(String(k)); }
          return s;
        };
        const reds = setOf('#EF4444'), yels = setOf('#EAB308'), grns = setOf('#22C55E');
        const kf = function(set) { return function(z, f) { try { return set.has(String((f && f.props && f.props.kode_kph) || '')); } catch (_) { return false; } }; };
        return [
          { dataLayer: 'petak', symbolizer: mk('#EF4444'), filter: kf(reds) },
          { dataLayer: 'petak', symbolizer: mk('#EAB308'), filter: kf(yels) },
          { dataLayer: 'petak', symbolizer: mk('#22C55E'), filter: kf(grns) },
        ];
      }
      const wf = function(w) { return function(z, f) { return String((f && f.props && f.props.warna) || '').toLowerCase() === w; }; };
      return [
        { dataLayer: 'petak', symbolizer: mk('#EF4444'), filter: wf('merah') },
        { dataLayer: 'petak', symbolizer: mk('#EAB308'), filter: wf('kuning') },
        { dataLayer: 'petak', symbolizer: mk('#22C55E'), filter: wf('hijau') },
      ];
    } catch (_) { return []; }
  }
  let _ovLayer = null; // hit-layer transparan (tooltip + klik drill)
  function _ovEnsureLayer() {
    try {
      if (_ovLayer) return _ovLayer;
      _ovLayer = window.L.geoJSON([], {
        style: function() {
          return { color: '#FFFFFF', weight: 0, opacity: 0, fillColor: '#FFFFFF', fillOpacity: 0, interactive: true };
        },
      });
      return _ovLayer;
    } catch (_) { return null; }
  }
  async function _ovFetchBounds() {
    // Geometri dissolve per divre dalam scope (scope ditegakkan server).
    const out = [];
    for (const d of _scopeDivreList()) {
      try {
        const r = await fetch('/api/tiles/bounds_geo?divre=' + encodeURIComponent(d), {
          headers: { 'X-Ana-Token': _tokPm() }, credentials: 'same-origin',
        });
        const j = await r.json().catch(() => ({}));
        if (j && Array.isArray(j.features)) for (const f of j.features) out.push(f);
      } catch (_) {}
    }
    return out;
  }
  function _ovHideGeo() {
    try { if (_ovLayer && map.hasLayer(_ovLayer)) map.removeLayer(_ovLayer); } catch (_) {}
    try { if (_ovLayer) _ovLayer.clearLayers(); } catch (_) {}
  }
  function _ovBindHit(layer, nums, biz) {
    // Binding post-hoc (pola terverifikasi): tooltip + klik drill per fitur.
    // Label tooltip mengikuti bisnis: aktivitas = B/I/A;
    // produksi = actual/target + achievement%.
    const _bb = String(biz || 'petak');
    const _tag = _bb === 'aktivitas' ? ['B', 'I', 'A'] : ['B', 'K', 'T'];
    try {
      layer.eachLayer(function(ll) {
        try {
          const p = (ll.feature && ll.feature.properties) || {};
          const nm = p.kph || p.kode_kph || 'KPH';
          let tip = '<b>' + esc(String(nm)) + '</b>';
          const m = nums[String(p.kode_kph || '')] || null;
          // Angka sesuai bisnis: produksi = actual/target + achievement%.
          if (m && m.prod) {
            const _pc = Number(m.pct);
            const _cs = !Number.isFinite(_pc) ? '#9CA3AF' : _pc < 50 ? '#EF4444' : _pc <= 85 ? '#EAB308' : '#22C55E';
            tip += '<br><span style="color:' + _cs + ';font-weight:700">' + Number(m.a).toLocaleString('id-ID') + '/' + Number(m.t).toLocaleString('id-ID') + ' kg'
              + ' (' + (Number.isFinite(_pc) ? _pc.toFixed(1).replace('.', ',') + '%' : '-') + ')</span>'
              + '<span style="opacity:.65"> dari ' + m.n + ' petak</span>';
          } else if (m) tip += '<br><span style="color:#EF4444;font-weight:700">' + esc(_tag[0]) + ' ' + m.b + '</span> '
            + '<span style="color:#EAB308;font-weight:700">' + esc(_tag[1]) + ' ' + m.k + '</span> '
            + '<span style="color:#22C55E;font-weight:700">' + esc(_tag[2]) + ' ' + m.t + '</span>'
            + '<span style="opacity:.65"> dari ' + m.n + ' petak</span>';
          else tip += '<br>Klik untuk filter KPH ini';
          ll.bindTooltip(tip, { sticky: true, direction: 'top' });
          ll.on('click', function() {
            try {
              const kode = String((ll.feature && ll.feature.properties && ll.feature.properties.kode_kph) || '');
              if (!kode || !fKph) return;
              let has = false;
              for (const o of fKph.options) { if (o.value === kode) { has = true; break; } }
              if (!has) return; // di luar scope menu
              fKph.value = kode;
              try {
                const bb = ll.getBounds && ll.getBounds();
                if (bb && bb.isValid && bb.isValid()) map.fitBounds(bb.pad(0.1));
              } catch (_) {}
              renderWilayah(); updateHead(); renderChips(); scheduleReload();
            } catch (_) {}
          });
        } catch (_) {}
      });
    } catch (_) {}
  }
  async function _ovShowHit(rows, neutral, biz) {
    // Return true bila hit-layer tampil. numbers: kode -> {b,k,t,n}.
    try {
      const layer = _ovEnsureLayer();
      if (!layer) return false;
      const feats = await _ovFetchBounds();
      if (!feats.length) { _ovHideGeo(); return false; }
      const nums = {};
      for (const r of (rows || [])) {
        try {
          const _kk = String(r.kode_kph || r.kode_wilayah || '');
          if (!_kk) continue;
          if (String(biz || '') === 'produksi') {
            nums[_kk] = { prod: true, a: Number(r.actual_kg || 0), t: Number(r.target_kg || 0),
                          pct: Number(r.achievement_pct), n: r.n_petak || r.total_petak || 0 };
          } else {
            nums[_kk] = { b: r.bongkor || 0, k: r.kurang || 0, t: r.terpenuhi || 0, n: r.total_petak || 0 };
          }
        } catch (_) {}
      }
      const gj = [];
      for (const f of feats) {
        try {
          const p = (f && f.properties) || {};
          const kode = String(p.kode_kph || '');
          const g = f.geometry;
          if (!kode || !g || (g.type !== 'Polygon' && g.type !== 'MultiPolygon')) continue;
          gj.push({ type: 'Feature', geometry: g,
                    properties: { kode_kph: kode, kph: p.kph || kode } });
        } catch (_) {}
      }
      if (!gj.length) { _ovHideGeo(); return false; }
      layer.clearLayers();
      layer.addData({ type: 'FeatureCollection', features: gj });
      if (!map.hasLayer(layer)) layer.addTo(map);
      _ovBindHit(layer, neutral ? {} : nums, biz);
      try { window.__spatialOvLayer = layer; } catch (_) {}
      return true;
    } catch (_) { try { _ovHideGeo(); } catch (_) {} return false; }
  }
  async function _neutralBounds() {
    // Outline KPH netral se-divre untuk konteks (ADM): tile netral + hit-layer.
    try {
      const tok = _tokPm();
      const man = await _tileManifestLoad();
      const bSrc = [];
      if (man && Array.isArray(man.files)) {
        const _byBase3 = {};
        for (const f of (man.files || [])) {
          try {
            const _nm = String(f.name || '');
            const _m = _nm.match(/^(bounds_\d+?)(?:_(\d{4}))?\.pmtiles$/);
            if (!_m) continue;
            const _base = _m[1] + '.pmtiles';
            const _yr = _m[2] ? parseInt(_m[2]) : 0;
            if (!_byBase3[_base] || _yr > _byBase3[_base].yr) _byBase3[_base] = { yr: _yr, name: _nm };
          } catch (_) {}
        }
        for (const d of _scopeDivreList()) {
          const hit = _byBase3['bounds_' + d + '.pmtiles'];
          if (!hit) continue;
          const suffix = hit.yr ? '_' + hit.yr : '';
          bSrc.push({ url: '/api/tiles/scope/bounds_' + d + suffix + '.pmtiles', kind: 'kph', maxDataZoom: 10,
                      rules: _ctl.kph_bounds_rules({}, { neutral: true }) });
        }
      }
      if (!bSrc.length) return;
      _ctl.set_pmtiles_sources('bounds', bSrc, { token: tok });
      await _ovShowHit([], true);
    } catch (_) {}
  }

  // ── Label nama wilayah (pengganti lingkaran centroid agregat) ──
  // z≤8: BKPH; z9-10: BKPH+RPH; z11-12: TPG kecil; >12: sembunyi.
  // Permanen (bukan hover) di jangkauannya; klik = drill filter wilayah.
  // Data: kph_summary_map per level (centroid+nma+count), cache per kunci.
  let _labelGroups = null;
  let _labelCache = {};
  let _labelTimer = null;
  let _labelBuilt = {}; // level -> kunci terakhir yang sudah dibangun (anti rebuild)
  let _labelFetching = {}; // level -> kunci yang sedang di-fetch (anti dobel)
  // CSS sekali suntik (tanpa ubah file CSS): transisi halus + sembunyi
  // seketika selama animasi zoom (kelas bawaan Leaflet), muncul fade-in sesudahnya.
  try {
    if (!document.getElementById('wilAnimCss')) {
      const _st = document.createElement('style');
      _st.id = 'wilAnimCss';
      _st.textContent = '.wil-label>span{transition:opacity .22s ease;}.leaflet-zoom-anim .wil-label>span{opacity:0 !important;}';
      document.head.appendChild(_st);
    }
  } catch (_) {}
  const _LABEL_STYLE = {
    kph: 'font-size:14px;font-weight:800;color:#fff;text-shadow:0 1px 4px #000,0 0 8px #000;letter-spacing:.06em;white-space:nowrap;',
    bkph: 'font-size:13px;font-weight:800;color:#fff;text-shadow:0 1px 4px #000,0 0 8px #000;letter-spacing:.06em;white-space:nowrap;',
    rph: 'font-size:11px;font-weight:700;color:#FFE9A8;text-shadow:0 1px 3px #000,0 0 6px #000;white-space:nowrap;',
    tpg: 'font-size:10px;font-weight:600;color:#9BDCFF;text-shadow:0 1px 3px #000,0 0 6px #000;white-space:nowrap;',
  };
  const _LABEL_PREFIX = { kph: 'KPH', bkph: 'BKPH', rph: 'RPH', tpg: 'TPG' };
  function _labelLevels() {
    // Disepakati: Z<=10 KPH; Z11 BKPH; Z12 BKPH+RPH; Z13 RPH+TPG; Z14+ TPG.
    const z = map.getZoom();
    if (z <= 10) return ['kph'];
    if (z === 11) return ['bkph'];
    if (z === 12) return ['bkph', 'rph'];
    if (z === 13) return ['rph', 'tpg'];
    return ['tpg'];
  }
  function _labelKey(level) {
    const f = collectState().filters;
    return level + '|' + f.tahun + '|' + [f.divre, f.kph, f.bkph, f.rph, f.tpg].join(',');
  }
  function _ensureLabelGroups() {
    if (_labelGroups) return _labelGroups;
    _labelGroups = {};
    for (const L of ['kph', 'bkph', 'rph', 'tpg']) _labelGroups[L] = window.L.layerGroup();
    return _labelGroups;
  }
  function _scheduleLabels() {
    try { clearTimeout(_labelTimer); } catch (_) {}
    _labelTimer = setTimeout(function() { try { _refreshLabels(); } catch (_) {} }, 600);
  }
  // Declutter: label bertumpuk (centroid BKPH/RPH/TPG berdekatan) —
  // prioritas BKPH > RPH > TPG; yang kalah disembunyikan (tetap ada).
  // Hitung ulang tiap peta berhenti bergerak (tanpa reload data).
  let _declutterTimer = null;
  const _LABEL_PR = { kph: 0, bkph: 1, rph: 2, tpg: 3 };
  function _scheduleDeclutter() {
    try { clearTimeout(_declutterTimer); } catch (_) {}
    _declutterTimer = setTimeout(function() { try { _declutterLabels(); } catch (_) {} }, 300);
  }
  function _declutterLabels() {
    try {
      const items = [];
      for (const L of ['kph', 'bkph', 'rph', 'tpg']) {
        const g = _labelGroups && _labelGroups[L];
        if (!g || !map.hasLayer(g)) continue;
        g.eachLayer(function(mk) {
          try {
            const ll = mk.getLatLng && mk.getLatLng();
            if (!ll) return;
            const pt = map.latLngToContainerPoint(ll);
            const el = mk.getElement && mk.getElement();
            // KPH mengecil mengikuti zoom jauh (Z≤7 kecil, Z8 sedang, Z9-10
            // normal) agar tak mendominasi; tetap terbaca. Ukur setelahnya.
            try {
              if (L === 'kph' && el) {
                const z = map.getZoom();
                const sp = el.querySelector && el.querySelector('span');
                if (sp) sp.style.fontSize = z <= 7 ? '10px' : (z <= 8 ? '11px' : '12px');
              }
            } catch (_) {}
            const w = el ? (el.offsetWidth || 60) : 60;
            // Histeresis: yang sedang tampil dipertahankan dulu dalam prioritas
            // sama — geser kecil tak membuat label berkedip tukar.
            let vis = false;
            try { vis = !!el && el.style.display !== 'none'; } catch (_) {}
            items.push({ mk, el, vis, pr: (_LABEL_PR[L] ?? 9), x0: pt.x - w / 2 - 4, x1: pt.x + w / 2 + 4, y0: pt.y - 9, y1: pt.y + 9 });
          } catch (_) {}
        });
      }
      items.sort((a, b) => (a.pr - b.pr) || ((b.vis ? 1 : 0) - (a.vis ? 1 : 0)));
      const kept = [];
      for (const it of items) {
        let clash = false;
        for (const k of kept) {
          if (it.x0 < k.x1 && it.x1 > k.x0 && it.y0 < k.y1 && it.y1 > k.y0) { clash = true; break; }
        }
        if (!clash) kept.push(it);
        try { if (it.el) it.el.style.display = clash ? 'none' : ''; } catch (_) {}
      }
    } catch (_) {}
  }
  async function _refreshLabels() {
    try {
      const groups = _ensureLabelGroups();
      const want = _labelLevels();
      for (const L of ['kph', 'bkph', 'rph', 'tpg']) {
        const g = groups[L];
        const on = want.indexOf(L) !== -1;
        if (on && !map.hasLayer(g)) g.addTo(map);
        if (!on && map.hasLayer(g)) map.removeLayer(g);
      }
      if (!want.length) return;
      const st = collectState();
      const w = {};
      const _ck = { divre: 'kode_divre', kph: 'kode_kph', bkph: 'kode_bkph', rph: 'kode_rph', tpg: 'kode_tpg' };
      for (const k of Object.keys(_ck)) if (st.filters[k]) w[_ck[k]] = st.filters[k];
      for (const L of want) {
        const key = _labelKey(L);
        if (_labelBuilt[L] === key) continue; // sudah tampil untuk kunci ini
        if (_labelFetching[L] === key) continue; // fetch berjalan, jangan dobel
        _labelFetching[L] = key;
        let rows = _labelCache[key];
        if (!rows) {
          try {
            const rr = await queryStats('kph_summary_map', { tahun: parseInt(st.filters.tahun) || 2026, limit: 200, aggregated_level: 'kode_' + L, ...w }, { timeoutMs: 10000 });
            rows = (rr && rr.ok && Array.isArray(rr.rows)) ? rr.rows : [];
          } catch (_) { rows = []; }
          _labelCache[key] = rows;
          try { const ks = Object.keys(_labelCache); if (ks.length > 12) delete _labelCache[ks[0]]; } catch (_) {}
        }
        // Bangun ulang hanya bila kunci berubah sejak bangun terakhir
        // (tugas fetch lain mungkin sudah membangun duluan).
        if (_labelBuilt[L] !== key) {
          _buildLabelLevel(L, rows);
          _labelBuilt[L] = key;
        }
        try { delete _labelFetching[L]; } catch (_) {}
      }
    } catch (_) {}
    _scheduleDeclutter(); // rapikan tumpukan setelah bangun ulang
  }
  function _buildLabelLevel(L, rows) {
    try {
      const g = _ensureLabelGroups()[L];
      g.clearLayers();
      const selMap = { kph: fKph, bkph: fBkph, rph: fRph, tpg: fTpg };
      for (const r of (rows || [])) {
        let pt = null;
        try {
          const c = typeof r.centroid === 'string' ? JSON.parse(r.centroid) : r.centroid;
          const co = c && c.coordinates;
          if (Array.isArray(co) && Number.isFinite(co[0]) && Number.isFinite(co[1])) pt = [co[1], co[0]];
        } catch (_) {}
        if (!pt) continue;
        const nm = String(r.nama_wilayah || r.kode_wilayah || '');
        if (!nm) continue;
        const label = ((_LABEL_PREFIX[L] || '') + ' ' + nm).trim();
        const kode = String(r.kode_wilayah || '');
        const mk = window.L.marker(pt, { interactive: true, keyboard: false,
          icon: window.L.divIcon({ className: 'wil-label', html: '<span style="' + _LABEL_STYLE[L] + '">' + esc(label) + '</span>', iconSize: null }) });
        mk.on('click', function() {
          try {
            const sel = selMap[L];
            if (!sel || !kode) return;
            let has = false;
            for (const o of sel.options) { if (o.value === kode) { has = true; break; } }
            if (!has) return; // di luar scope menu
            sel.value = kode;
            renderWilayah(); updateHead(); renderChips(); scheduleReload();
          } catch (_) {}
        });
        mk.addTo(g);
      }
    } catch (_) {}
  }

  // 1 tombol sembunyikan toolbar + filter + pencarian sekaligus.
  // Default tampil; klik → collapsed jadi 1 tombol 30x30 (seperti layer).
  $sel('#spatialToolsToggle')?.addEventListener('click', function() {
    const wrap = el.querySelector('.map-fly-top');
    if (!wrap) return;
    wrap.classList.toggle('tools-collapsed');
    this.classList.toggle('active', !wrap.classList.contains('tools-collapsed'));
    setTimeout(() => map.invalidateSize(), 180);
  });

  let _wilayahCache = null;
  // Indeks rantai kode wilayah ("level:value" → {divre,kph,bkph,rph}) untuk renderWilayah.

  function _labelWilayah(kind, kode) {
    if (!kode || !_wilayahCache) return String(kode);
    const arr = _wilayahCache[kind] || [];
    const s = String(kode);
    const hit = arr.find(function(o){ return String(o.value||o) === s; });
    if (hit) return hit.label || s;
    return s;
  }

  // ── Filter wilayah terintegrasi user login + cascade dua arah ──
  // Scope dari KODE user + KODE JABATAN (cermin server): DIREKSI/ADMINISTRATOR
  // bebas semua; DIVRE kunci DIVRE-nya (KPH/BKPH/RPH/TPG se-DIVRE itu);
  // ADM kunci DIVRE+KPH (BKPH/RPH/TPG se-KPH itu); BKPH-level kunci s/d BKPH;
  // TPG-level hanya TPG miliknya (fail-closed). Tanpa kode → semua terbuka.
  // Server menegakkan hal yang sama (_enforce_wilayah_scope di
  // /api/simoge/query|packet|show_on_map, cookie sesi ikut via
  // credentials:same-origin) — curl/devtools tak bisa tamper filter selama
  // sesi login ada. Frontend = UX, server = kebenaran.
  // Cascade: pilih anak → induk auto-isi sesuai rantai kode (bila opsinya ada
  // di menu); pilih induk → opsi anak di luar wilayahnya dibuang. Satu
  // renderWilayah() jadi sumber kebenaran (murni client-side dari cache —
  // tanpa fetch per klik).
  const _WLEVELS = ['divre', 'kph', 'bkph', 'rph', 'tpg'];
  const _WPARENT_LVL = { kph: 'divre', bkph: 'kph', rph: 'bkph', tpg: 'rph' };
  const _WCHAIN_KEY = ['divre', 'kph', 'bkph', 'rph'];
  // Ancestor tiap level untuk saring fail-closed (opsi tanpa rantai
  // terverifikasi dibuang bila induk efektif terisi).
  const _WANCESTORS = { kph: ['divre'], bkph: ['kph', 'divre'], rph: ['bkph', 'kph', 'divre'], tpg: ['rph', 'bkph', 'kph', 'divre'] };
  let _wChain = {};
  function _userScope() {
    // Scope dari KODE user + KODE JABATAN (cermin server _wilayah_scope_from_session):
    // DIREKSI/ADMINISTRATOR → {} (semua); DIVRE → {divre}; ADM → {divre,kph};
    // ASPER/KSSPROD/MANTRI → s/d {bkph}; lain → apa adanya (terdalam menang).
    // Session menyimpan hasil expand (dict) atau mentah (int/str) — semua bisa.
    const pick = (v, k) => {
      try {
        if (v == null) return '';
        if (typeof v === 'object' && !Array.isArray(v)) {
          const c = v[k];
          return (c == null || c === '') ? '' : String(c).trim();
        }
        if (Array.isArray(v)) return '';
        const s = String(v).trim();
        return (s === '' || s.toLowerCase() === 'none' || s.toLowerCase() === 'null') ? '' : s;
      } catch (_) { return ''; }
    };
    try {
      const u = window._authUser || {};
      let jab = '';
      try {
        const _j = u.jabatan;
        if (_j && typeof _j === 'object' && !Array.isArray(_j)) jab = String(_j.kode_jabatan || _j.nama_jabatan || '').trim().toUpperCase();
        else if (_j != null && _j !== '') jab = String(_j).trim().toUpperCase();
      } catch (_) {}
      if (jab === 'DIREKSI' || jab === 'ADMINISTRATOR') return { divre: '', kph: '', bkph: '', rph: '', tpgList: [], jabatan: jab };
      const dv = pick(u.kode_divre, 'kode_divre');
      const kp = pick(u.kode_kph, 'kode_kph');
      const bk = pick(u.kode_bkph, 'kode_bkph');
      const rp = pick(u.kode_rph, 'kode_rph');
      const scope = { divre: '', kph: '', bkph: '', rph: '', tpgList: [], jabatan: jab };
      if (jab === 'DIVRE') { scope.divre = dv; }
      else if (jab === 'ADM') { scope.divre = dv; scope.kph = kp; }
      else if (jab === 'ASPER' || jab === 'KSSPROD' || jab === 'MANTRI') { scope.divre = dv; scope.kph = kp; scope.bkph = bk; }
      else { scope.divre = dv; scope.kph = kp; scope.bkph = bk; scope.rph = rp; }
      // User TPG-level: kode_tpg = list M2M [{kode_tpg,...},...] atau mentah.
      // DIVRE/ADM bukan TPG-level — abaikan agar tak menyempitkan wilayahnya.
      try {
        const t = u.kode_tpg;
        if ((jab !== 'DIVRE' && jab !== 'ADM') && Array.isArray(t)) for (const e of t) {
          const c = (e && typeof e === 'object') ? e.kode_tpg : e;
          if (c != null && String(c).trim() !== '') scope.tpgList.push(String(c).trim());
        }
      } catch (_) {}
      return scope;
    } catch (_) { return { divre: '', kph: '', bkph: '', rph: '', tpgList: [] }; }
  }
  function _buildWIdx() {
    _wChain = {};
    try {
      const O = _wilayahCache || {};
      const byVal = {};
      for (const L of _WLEVELS) for (const o of (O[L] || [])) {
        if (o && o.value != null) byVal[L + ':' + String(o.value)] = o;
      }
      const chain = function(L, v) {
        const o = byVal[L + ':' + String(v)];
        if (!o) return {};
        const c = {};
        const P = function(k) { return (o[k] != null && String(o[k]).trim() !== '') ? String(o[k]).trim() : ''; };
        if (L === 'kph') { const d = P('kode_divre'); if (d) c.divre = d; }
        else if (L === 'bkph') { const k = P('kode_kph'); if (k) { c.kph = k; Object.assign(c, chain('kph', k)); } if (!c.divre) { const dd = P('kode_divre'); if (dd) c.divre = dd; } }
        else if (L === 'rph') { const b = P('kode_bkph'); if (b) { c.bkph = b; Object.assign(c, chain('bkph', b)); } if (!c.kph) { const kk = P('kode_kph'); if (kk) c.kph = kk; } if (!c.divre) { const dd = P('kode_divre'); if (dd) c.divre = dd; } }
        else if (L === 'tpg') {
          const r = P('kode_rph'); if (r) { c.rph = r; Object.assign(c, chain('rph', r)); }
          if (!c.bkph) { const b = P('kode_bkph'); if (b) c.bkph = b; }
          if (!c.kph && c.bkph) { const up = chain('bkph', c.bkph); if (up.kph) c.kph = up.kph; if (up.divre) c.divre = up.divre; }
          if (!c.kph) { const kk = P('kode_kph'); if (kk) c.kph = kk; }
          if (!c.divre) { const dd = P('kode_divre'); if (dd) c.divre = dd; }
        }
        return c;
      };
      for (const L of _WLEVELS) for (const o of (O[L] || [])) {
        if (o && o.value != null) _wChain[L + ':' + String(o.value)] = chain(L, o.value);
      }
    } catch (_) { _wChain = {}; }
  }
  function _chainOf(level, value) {
    if (value == null || value === '') return {};
    return _wChain[level + ':' + String(value)] || {};
  }
  function _wSel() { return { divre: fDivre, kph: fKph, bkph: fBkph, rph: fRph, tpg: fTpg }; }
  function _effScope(scope, cur) {
    // Induk efektif = scope login, kecuali panel memilih yang LEBIH SEMPIT
    // dan masih di dalam scope itu (mis. KPH dipilih manual di dalam DIVRE).
    // Aturan: pilihan di LUAR scope tak pernah jadi induk efektif (sudah
    // dibuang validasi) — jadi BKPH tak bisa "membuka" KPH lain.
    const eff = { divre: scope.divre || '', kph: '', bkph: '', rph: '' };
    try {
      if (cur.divre && (!scope.divre || cur.divre === scope.divre)) eff.divre = cur.divre;
      if (cur.kph && (!scope.kph || cur.kph === scope.kph)) eff.kph = cur.kph;
      else if (scope.kph) eff.kph = scope.kph;
      if (cur.bkph && (!scope.bkph || cur.bkph === scope.bkph)) eff.bkph = cur.bkph;
      else if (scope.bkph) eff.bkph = scope.bkph;
      if (cur.rph && (!scope.rph || cur.rph === scope.rph)) eff.rph = cur.rph;
      else if (scope.rph) eff.rph = scope.rph;
    } catch (_) {}
    return eff;
  }
  function renderWilayah() {
    if (!_wilayahCache) return;
    const SEL = _wSel();
    const scope = _userScope();
    const cur = {};
    for (const L of _WLEVELS) cur[L] = SEL[L] ? String(SEL[L].value || '') : '';
    // Scope login menang atas nilai panel: divre/kph/bkph/rph/tpg user dipaksa.
    if (scope.divre) cur.divre = scope.divre;
    if (scope.kph) cur.kph = scope.kph;
    if (scope.bkph) cur.bkph = scope.bkph;
    if (scope.rph) cur.rph = scope.rph;
    if (scope.tpgList && scope.tpgList.length === 1 && !cur.tpg) cur.tpg = scope.tpgList[0];
    // validasi top-down: nilai di luar scope/rantai induk dibuang
    for (const L of _WLEVELS) {
      const v = cur[L];
      if (!v) continue;
      // Fail-closed TPG: user TPG-level hanya boleh TPG miliknya.
      if (L === 'tpg' && scope.tpgList && scope.tpgList.length && scope.tpgList.indexOf(v) === -1) { cur[L] = ''; continue; }
      const ch = _chainOf(L, v);
      let ok = true;
      // Opsi tanpa rantai yang bisa diverifikasi + di luar scope login = buang.
      const _scopeHit = { divre: scope.divre, kph: scope.kph, bkph: scope.bkph, rph: scope.rph };
      for (const sL of ['divre', 'kph', 'bkph', 'rph']) {
        if (!_scopeHit[sL]) continue;
        if (L === sL) { if (v !== _scopeHit[sL]) ok = false; }
        else if (ch[sL] && ch[sL] !== _scopeHit[sL]) ok = false;
      }
      if (ok) {
        let a = _WPARENT_LVL[L];
        while (a) {
          if (cur[a] && ch[a] && ch[a] !== cur[a]) { ok = false; break; }
          a = _WPARENT_LVL[a];
        }
      }
      if (!ok) cur[L] = '';
    }
    const eff = _effScope(scope, cur);
    // bangun ulang opsi per level (batch innerHTML — responsif)
    const _optCount = {};
    for (const L of _WLEVELS) {
      const sel = SEL[L];
      if (!sel) continue;
      const arr = _wilayahCache[L] || [];
      const list = arr.filter(function(o) {
        const v = String(o.value);
        // Fail-closed TPG: menu user TPG-level hanya berisi TPG miliknya.
        if (L === 'tpg' && scope.tpgList && scope.tpgList.length && scope.tpgList.indexOf(v) === -1) return false;
        const ch = _chainOf(L, v);
        // Scope login: level di luar scope dibuang (termasuk tanpa rantai).
        if (scope.divre && L === 'divre' && v !== scope.divre) return false;
        if (scope.kph && L === 'kph' && v !== scope.kph) return false;
        if (scope.bkph && L === 'bkph' && v !== scope.bkph) return false;
        if (scope.rph && L === 'rph' && v !== scope.rph) return false;
        // Fail-closed: opsi anak tanpa rantai terverifikasi dibuang bila
        // induk efektif terisi (tak bisa buktikan ia di dalam wilayah).
        for (const a of (_WANCESTORS[L] || [])) {
          if (!eff[a]) continue;
          if (L === a) continue;
          if (!ch[a]) return false;
          if (ch[a] !== eff[a]) return false;
        }
        // Pilihan induk di panel (bila bukan scope paksa) tetap menyaring.
        let a = _WPARENT_LVL[L];
        while (a) {
          if (cur[a] && ch[a] && ch[a] !== cur[a]) return false;
          a = _WPARENT_LVL[a];
        }
        return true;
      });
      const keep = cur[L] && list.some(function(o) { return String(o.value) === cur[L]; }) ? cur[L] : '';
      cur[L] = keep;
      let html = '<option value="">Semua</option>';
      for (const o of list) html += '<option value="' + esc(String(o.value)) + '">' + esc(o.label || String(o.value)) + '</option>';
      _optCount[L] = list.length;
      sel.innerHTML = html;
      sel.value = keep;
      // Select yang dipaksa scope = disabled (tak bisa diubah user).
      const _scopeVal = { divre: scope.divre, kph: scope.kph, bkph: scope.bkph, rph: scope.rph }[L] || '';
      const pinned = !!_scopeVal && !!keep && keep === _scopeVal;
      try {
        sel.disabled = !!pinned;
        sel.title = pinned ? ('Wilayah login — ' + keep) : '';
      } catch (_) {}
    }
    // Mis-scope terdeteksi: scope login aktif tapi SEMUA menu anak kosong =
    // kode user tak cocok data apa pun (bukan bug cascade). Tampilkan jujur
    // agar admin betulkan penugasan, bukan dikira menu rusak.
    try {
      const _scoped = !!(scope.divre || scope.kph || scope.bkph || scope.rph || (scope.tpgList && scope.tpgList.length));
      const _kidsEmpty = ['kph', 'bkph', 'rph', 'tpg'].every(function(L) { return !(_optCount[L] > 0); });
      if (_scoped && _kidsEmpty) {
        const _lbl = scope.kph || scope.divre || scope.bkph || scope.rph || (scope.tpgList || []).join(',');
        _wilScopeMsg = 'Cakupan login (' + _lbl + ') tak cocok data mana pun — hubungi admin';
        _setWilStatus('scope', _wilScopeMsg);
        return;
      }
      _wilScopeMsg = '';
    } catch (_) {}
  }
  let _cascadeAttached = false;
  let _wilScopeMsg = '';
  function _attachWilayahCascade() {
    if (_cascadeAttached) return;
    _cascadeAttached = true;
    const SEL = _wSel();
    for (const L of _WLEVELS) {
      const sel = SEL[L];
      if (!sel) continue;
      sel.addEventListener('change', function() {
        try {
          const v = String(this.value || '');
          if (v) {
            const ch = _chainOf(L, v);
            const S = _wSel();
            for (const key of _WCHAIN_KEY) {
              const t = S[key];
              // Isi induk dari rantai kode — hanya bila select-nya bisa diubah
              // DAN opsinya memang ada di menu (menu KPH scope tak muat KPH lain).
              if (ch[key] && t && !t.disabled) {
                try {
                  let has = false;
                  for (const o of t.options) { if (o.value === ch[key]) { has = true; break; } }
                  if (has) t.value = ch[key];
                } catch (_) {}
              }
            }
          }
          renderWilayah();
        } catch (e) { try { log('error', 'MAP', 'cascade: ' + e.message); } catch (_) {} }
        updateHead(); renderChips(); scheduleReload();
      });
    }
  }
  // Dipanggil main.js setelah requireAuth mengisi window._authUser (initMapPanel
  // jalan sebelum auth selesai, jadi scope login diterapkan susulan di sini).
  try {
    window.__spatialApplyUserScope = function() {
      try {
        renderWilayah();
        // Sinkron PENUH (bisnis + filter): setFilters saja memancarkan snap
        // hibrida {bisnis basi + filter baru} yang membuat subscribe menimpa
        // dropdown bisnis ke nilai basi (bug reset-saat-refresh).
        try { const st = collectState(); setBusiness(st.business); setFilters(st.filters); } catch (_) {}
        renderChips();
        _scheduleOverview(); // scope login berubah → sumber tile + overview ikut
        _scheduleLabels(); // + label wilayah ikut scope
        if (_autoKicked && !_loading) scheduleReload();
      } catch (_) {}
    };
  } catch (_) {}

  function _applyScopeLock() {
    // Kompat: scope KODE user sekarang dipasang renderWilayah() (lihat _userScope).
    // Fungsi lama dipertahankan sebagai no-op agar pemanggil lama tak error.
    try { renderWilayah(); } catch (_) {}
  }

  // ── Isi dropdown: bangun indeks rantai → render sesuai scope login → pasang cascade ──
  // Urutan: fetch → _buildWIdx → renderWilayah (scope kode user) → lock lama
  // (kompat) → auto-filter lama (kompat) → cascade dua arah → hook reload ANA.
  function _populateDropdowns(res) {
    // Kontrak fetchWilayahOptions: {data, source} (bentuk lama polos aman).
    const opts = (res && res.data) || res;
    const src = (res && res.source) || 'api';
    _wilayahCache = opts;
    _buildWIdx();
    renderWilayah();
    // Pulihkan wilayah tersimpan (sekali): set nilai yang opsinya ada, lalu
    // renderWilayah() menegakkan scope+cascade (di luar scope dibuang).
    // reload susulan aman di semua state (diantre via _pending bila loading).
    if (_pendingWilayah) {
      const pw = _pendingWilayah; _pendingWilayah = null;
      try {
        const SEL = _wSel();
        let touched = false;
        for (const L of _WLEVELS) {
          const v = pw[L];
          const sel = SEL[L];
          if (!v || !sel || sel.disabled) continue;
          const has = [...sel.options].some(function(o){ return o.value === v; });
          if (has && sel.value !== v) { sel.value = v; touched = true; }
        }
        if (touched) {
          renderWilayah();
          try { const st = collectState(); setBusiness(st.business); setFilters(st.filters); } catch (_) {}
          renderChips();
          try { console.info('[spatial-persist] wilayah pulih', JSON.stringify(pw)); } catch (_) {}
          if (_autoKicked) scheduleReload();
        }
      } catch (_) {}
    }
    _panelReady = true;
    // Titik simpan: opsi siap — persistensikan apa pun yang tampil saat ini
    // (pilihan user yang dibuat sebelum fetch selesai ikut tersimpan).
    try { _savePanelStateGated({ business: bizSel?.value || 'petak', filters: collectState().filters }); } catch (_) {}
    // Sumber tile mengikuti scope terbaru (choropleth/overview bila cocok).
    _scheduleOverview();
    _scheduleLabels();
    // Pesan mis-scope (bila ada) menang atas status sumber.
    if (_wilScopeMsg) _setWilStatus('scope', _wilScopeMsg);
    else _setWilStatus(src);
    try {
      const st = collectState();
      setBusiness(st.business);
      setFilters(st.filters);
    } catch (_) {}
  }
  // Status sumber opsi wilayah: hanya tampil bila BUKAN dari API (cache 24 jam
  // per user / fallback bawaan terbatas / mis-scope), atau pesan override.
  // Klik = coba muat ulang dari server.
  function _setWilStatus(src, msg) {
    try {
      const box = el.querySelector('#spatialWilStatus');
      if (!box) return;
      if (msg) {
        box.hidden = false;
        box.textContent = msg;
      } else if (!src || src === 'api') { box.hidden = true; box.textContent = ''; return; }
      else {
        box.hidden = false;
        box.textContent = src === 'cache'
          ? 'Wilayah: data tersimpan (server tak terjangkau) — klik untuk coba lagi'
          : 'Wilayah: gagal memuat dari server — klik untuk coba lagi';
      }
      if (!box._bound) {
        box._bound = true;
        box.addEventListener('click', function() {
          try {
            box.textContent = 'Memuat wilayah…';
            fetchWilayahOptions(2026).then(function(r2) {
              _populateDropdowns(r2);
              renderChips();
            });
          } catch (_) {}
        });
      }
    } catch (_) {}
  }

  // 1. Ambil opsi wilayah dari server → render sesuai scope login → cascade dua arah.
  // _applyScopeLock/applyUserWilayahFilter lama tetap jalan (kompat), tapi
  // renderWilayah() sudah lebih dulu mengunci DIVRE/KPH dari KODE user.
  fetchWilayahOptions(2026).then(function(opts) {
    _populateDropdowns(opts);

    // 2. Scope lock & auto-filter lama (kompat, no-op bila scope kode sudah pasang)
    try { _applyScopeLock(); } catch (_) {}
    try { applyUserWilayahFilter(); } catch (_) {}
    renderWilayah();

    // 3. Cascade dua arah baru (satu listener per dropdown, guard ganda)
    _attachWilayahCascade();

    renderChips();
  }).catch(function(err) {
    log('error', 'MAP', 'fetchWilayahOptions failed, using defaults: ' + err.message);
    // Fallback: fetchWilayahOptions sudah return defaults di catch, tapi untuk safety
    fetchWilayahOptions(2026).then(_populateDropdowns).then(() => {
      try { _applyScopeLock(); } catch (_) {}
      try { applyUserWilayahFilter(); } catch (_) {}
      renderWilayah();
      _attachWilayahCascade();
      renderChips();
    });
  });

  subscribeSpatial(function(snap){
    try {
      if (bizSel && bizSel.value !== snap.business) { try { console.info('[spatial-persist] subscribe timpa bisnis', bizSel.value, '->', snap.business); } catch (_) {} bizSel.value = snap.business; syncKatVisibility(); updateLegend(snap.business, snap.filters?.kategori || katSel?.value || 'semua'); }
      if (katSel && katSel.value !== snap.filters.kategori) { try { console.info('[spatial-persist] subscribe timpa kategori', katSel.value, '->', snap.filters.kategori); } catch (_) {} katSel.value = snap.filters.kategori; try { updateLegend(snap.business, snap.filters.kategori); } catch(_){} }
      const _pk = String(snap.filters?.pembaharuan_ke ?? '');
      if (fPemKe && fPemKe.value !== _pk && (_pk === '' || ['1','2','3','4'].includes(_pk))) fPemKe.value = _pk;
      updateHead(); renderChips();
    } catch (_) {}
  });
  try {
    bus.on('MODE_CHANGED', function(){ updateHead(); });
    window.addEventListener('ana:mode', function(){ updateHead(); });
  } catch(_){}

  let layers = [];
  const say = function(t){ if(stat) stat.textContent=t; };
  el.querySelector('#mapFit')?.addEventListener('click', () => {
    if (_ctl) _ctl.fit_all();
    else if (layers.length) map.fitBounds(window.L.featureGroup(layers).getBounds().pad(0.05));
    else map.setView(CENTER, 11);
  });
  el.querySelector('#mapSearch')?.addEventListener('keydown', function(e){
    if (e.key !== 'Enter') return;
    const q = e.target.value.trim();
    if (!q) return;
    if (_ctl) {
      const r = _ctl.select_feature(q);
      if (r) log('map', 'MAP', 'petak ' + r);
      else say('petak ' + q + ' tidak ketemu');
      return;
    }
    const hit = layers.find(function(l){ return (l.options.petakNo || '').includes(q); });
    if (hit) { map.fitBounds(hit.getBounds().pad(0.3)); hit.openPopup(); log('map', 'MAP', 'petak ' + hit.options.petakNo); }
    else say('petak ' + q + ' tidak ketemu');
  });

  try { window.__spatialReload = reloadBusiness; window.__spatialCollect = collectState; } catch (_) {}
  // ── ANA full control Toolbar + Filter + Search (via /api/map/command spatial_*) ──
  // State-driven: panel sendiri yang load subset → KPI/legend/insight ikut sinkron.
  // Raw push GeoJSON via set_features dilarang untuk subset (KPI desync + reload wipe).
  try {
    setSpatialHandler(async (op, a) => {
      a = (a && typeof a === 'object') ? a : {};
      if (op === 'spatial_get') {
        let n = -1;
        try { n = _ctl?.get_state?.()?.count || 0; } catch (_) {}
        return { state: collectState(), spatial: getSpatialState(), mapCount: n };
      }
      if (op === 'spatial_search') {
        const q = String(a.q ?? a.query ?? '').trim();
        if (!q) throw new Error('q required');
        const hit = _ctl ? _ctl.select_feature(q) : null;
        if (hit) log('map', 'MAP', 'ANA search petak ' + hit);
        return { q, hit };
      }
      if (op === 'spatial_reload') {
        scheduleReload();
        return { reloading: true, state: collectState() };
      }
      if (op === 'load_viewport') {
        // Viewport-based loading for kph_summary_map at zoom out levels.
        // Receives bounds [west,south,east,north], zoom, page_size, aggregated_level.
        // Updates filters and triggers business data reload with spatial query.
        const f = (a.filters && typeof a.filters === 'object') ? { ...a.filters } : {};
        const viewport = a.viewport || a; // support both {viewport:{bounds,zoom,page_size}} and flat
        if (viewport.bounds && Array.isArray(viewport.bounds) && viewport.bounds.length === 4) {
          f.bounds = viewport.bounds; // [west, south, east, north]
        }
        if (typeof viewport.zoom === 'number') {
          f.zoom = viewport.zoom;
        }
        if (typeof viewport.page_size === 'number') {
          f.page_size = viewport.page_size;
        }
        if (viewport.aggregated_level) {
          f.aggregated_level = String(viewport.aggregated_level);
        }
        // Simpan ke memori — tak ada dropdown DOM untuk kunci ini.
        // collectState() baca _viewportExtra agar bounds sampai ke server.
        for (const _k of ['aggregated_level', 'bounds', 'zoom', 'page_size']) {
          if (f[_k] !== undefined && f[_k] !== null && f[_k] !== '') _viewportExtra[_k] = f[_k];
          else delete _viewportExtra[_k];
        }
        // Merge into spatial_set handler logic
        if (a.business !== undefined && bizSel && bizSel.value !== String(a.business)) { try { console.info('[spatial-persist] ANA timpa bisnis', bizSel.value, '->', String(a.business)); } catch (_) {} bizSel.value = String(a.business); }
        _spatialWarna = String((a.filters && a.filters.warna) || a.warna || '').trim();
        // Apply defaults for empty time filters (same as spatial_set)
        const _defWaktu = { bulan: String(d.getMonth()+1), tahun: '2026', periode: d.getDate()<=15?'1':'2' };
        for (const k of Object.keys(_defWaktu)) {
          if (f[k] === '') f[k] = _defWaktu[k];
        }
        const _map = { bulan: fBulan, tahun: fTahun, periode: fPeriode, divre: fDivre, kph: fKph, bkph: fBkph, rph: fRph, tpg: fTpg, kategori: katSel, pembaharuan_ke: fPemKe, jenis_aktivitas: (typeof fJenisAkt !== 'undefined' ? fJenisAkt : null), sampai_dengan: (typeof fSampai !== 'undefined' ? fSampai : null) };
        for (const k of Object.keys(_map)) {
          const elm = _map[k];
          if (!elm || f[k] === undefined || f[k] === null) continue;
          if (k === 'pembaharuan_ke' && f[k] !== '' && !['1','2','3','4'].includes(String(f[k]))) continue;
          if (k === 'sampai_dengan' && f[k] !== '' && !['ya','tidak'].includes(String(f[k]).toLowerCase())) continue;
          if (k === 'jenis_aktivitas' && f[k] !== '' && !['quare','semprot_cas','kerok','naik_batok','budaya_bersih','pulung'].includes(String(f[k]).toLowerCase())) continue;
          const v = String(f[k]);
          if (k === 'kategori' && v && ![...elm.options].some(o => o.value === v)) {
            try { const o = document.createElement('option'); o.value = v; o.textContent = v; elm.appendChild(o); } catch (_) {}
          }
          elm.value = v;
        }
        // Cascade + scope login ikut nilai ANA (render ulang opsi anak, buang yang di luar scope)
        try { renderWilayah(); } catch (_) {}
        syncKatVisibility(); updateHead(); renderChips();
        try { const st = collectState(); setBusiness(st.business); setFilters(st.filters); } catch (_) {}
        try { updateLegend(bizSel?.value || 'petak', katSel?.value || 'semua'); } catch (_) {}
        // P2-3 hybrid: reset tier saat ganti business/via ANNA (load_viewport)
        _tier = null;
        reloadBusiness();
        return { accepted: true, state: collectState() };
      }
      if (op === 'spatial_set') {
        // Guard anti-loop: bila server echo _spatial_sync dari show_on_map milik
        // reloadBusiness kita sendiri, state sudah identik → jangan reload lagi.
        // Tanpa ini: reload → show_on_map → spatial_set → reload → … polygon
        // tampil-hilang berulang lalu berhenti di state setengah jalan.
        const _next = { business: (a.business !== undefined) ? String(a.business) : (bizSel?.value || 'petak') };
        _next.filters = { ...(collectState().filters || {}), ...((a.filters && typeof a.filters === 'object') ? a.filters : {}) };
        // Normalisasi string: server kirim int (periode 1), DOM baca string ('1').
        // Tanpa ini JSON beda terus → guard tak pernah trip → loop persisten.
        const _canon = o => {
          if (o && typeof o === 'object' && !Array.isArray(o)) {
            return '{' + Object.keys(o).sort().map(k => JSON.stringify(k) + ':' + _canon(o[k])).join(',') + '}';
          }
          return JSON.stringify(String(o ?? ''));
        };
        const _canonState = s => _canon({ business: String(s.business), filters: s.filters });
        try {
          const _cur = collectState();
          if (_canonState(_cur) === _canonState(_next)) {
            return { accepted: true, noop: true, state: _cur };
          }
        } catch (_) {}
        const f = (a.filters && typeof a.filters === 'object') ? a.filters : {};
        if (a.business !== undefined && bizSel && bizSel.value !== String(a.business)) { try { console.info('[spatial-persist] ANA timpa bisnis', bizSel.value, '->', String(a.business)); } catch (_) {} bizSel.value = String(a.business); }
        _spatialWarna = String((a.filters && a.filters.warna) || a.warna || '').trim();
        // Kontrak penuh solusi A: "" = reset eksplisit dari server (bukan skip).
        // Waktu kosong → default panel (bulan berjalan/2026/P berjalan); wilayah
        // kosong → dropdown dikosongkan. Tanpa ini "" menempel di dropdown waktu
        // (blank) dan guard kanonis tak pernah trip → reload tiap perintah sama.
        const _defWaktu = { bulan: String(d.getMonth()+1), tahun: '2026', periode: d.getDate()<=15?'1':'2' };
        for (const k of Object.keys(_defWaktu)) {
          if (f[k] === '') f[k] = _defWaktu[k];
        }
        const _map = { bulan: fBulan, tahun: fTahun, periode: fPeriode, divre: fDivre, kph: fKph, bkph: fBkph, rph: fRph, tpg: fTpg, kategori: katSel, pembaharuan_ke: fPemKe, jenis_aktivitas: (typeof fJenisAkt !== 'undefined' ? fJenisAkt : null), sampai_dengan: (typeof fSampai !== 'undefined' ? fSampai : null) };
        for (const k of Object.keys(_map)) {
          const elm = _map[k];
          if (!elm || f[k] === undefined || f[k] === null) continue;
          if (k === 'pembaharuan_ke' && f[k] !== '' && !['1','2','3','4'].includes(String(f[k]))) continue;
          if (k === 'sampai_dengan' && f[k] !== '' && !['ya','tidak'].includes(String(f[k]).toLowerCase())) continue;
          if (k === 'jenis_aktivitas' && f[k] !== '' && !['quare','semprot_cas','kerok','naik_batok','budaya_bersih','pulung'].includes(String(f[k]).toLowerCase())) continue;
          const v = String(f[k]);
          if (k === 'kategori' && v && ![...elm.options].some(o => o.value === v)) {
            try { const o = document.createElement('option'); o.value = v; o.textContent = v; elm.appendChild(o); } catch (_) {}
          }
          elm.value = v;
        }
        // Cascade + scope login ikut nilai ANA (render ulang opsi anak, buang yang di luar scope)
        try { renderWilayah(); } catch (_) {}
        syncKatVisibility(); updateHead(); renderChips();
        // Viewport dari server (link 4 ANNA→panel): tak ada dropdown DOM,
        // simpan ke _viewportExtra agar collectState teruskan ke adapter.
        // "" = reset eksplisit (kontrak solusi A), bukan skip.
        for (const _k of ['aggregated_level', 'bounds', 'zoom', 'page_size']) {
          if (f[_k] !== undefined && f[_k] !== null && f[_k] !== '') _viewportExtra[_k] = f[_k];
          else delete _viewportExtra[_k];
        }
        try { const st = collectState(); setBusiness(st.business); setFilters(st.filters); } catch (_) {}
        try { updateLegend(bizSel?.value || 'petak', katSel?.value || 'semua'); } catch (_) {}
        // P2-3 hybrid: reset tier saat ganti business/via ANNA
        _tier = null;
        reloadBusiness();
        return { accepted: true, state: collectState() };
      }
      throw new Error('op spatial tidak dikenal: ' + op);
    });
  } catch (_) {}
  // chart + laporan panel di DALAM #mapPanel — ANA full control via session state
  // (/api/spatial/chart dan /api/spatial/report)
  const _tok = document.querySelector('meta[name="ana-token"]')?.content || '';
  try { initSpatialChart({ token: _tok, log }); } catch (_) {}
  // laporan multi halaman siap cetak (Unduh = window.print, Tutup = POST visible:false)
  try { initSpatialReport({ token: _tok, log }); } catch (_) {}
  // arsip chart/laporan per-user + drag panel dalam map (drawer 🗂 di toolbar)
  try { initSpatialArchive({ token: _tok, log }); } catch (_) {}
  updateHead(); renderChips();
  // ── Apply auto-filter wilayah based on user jabatan ──
  // Kompat: nilai wilayah user sekarang dipasang renderWilayah() dari KODE
  // (bukan jabatan). Fungsi lama jadi no-op agar pemanggil lama tak error
  // (dulu manggil _filterCascade yang sudah diganti mesin render).
  function applyUserWilayahFilter() {
    try { renderWilayah(); } catch (_) {}
  }

  // ── single kick: 1x load, watchdog yang retry bila render gagal ──
  let _autoKicked = false;
  function _kickAuto() {
    if (_autoKicked) return;
    _autoKicked = true;
    if (_loading || _awaitingFeatures !== null) return;
    reloadBusiness().catch(() => {});
  }
  const _whenReady = () => {
    const ready = !!(_ctl && _ctl.map && window.L);
    if (ready) { _setProgress(6, 'memuat peta…'); setTimeout(_kickAuto, 360); }
    else setTimeout(_whenReady, 180);
  };
  _whenReady();
  return el;
}
