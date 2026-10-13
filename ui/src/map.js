// ui/src/map.js — SPATIAL MAP panel (petak KPHBWB). Business Intelligence dashboard.
// HUD = dashboard dev (mode coding). Panel ini = dashboard BI (mode-aware).
// Panel via ensurePanel() -> auto LayoutManager. Leaflet engine via mapControl.js.
import { ensurePanel } from './utils/dom.js';
import { esc } from './utils/helpers.js';
import { bus, state as busState } from './core/bus.js';
import { createLeafletControl } from './mapControl.js';
import {
  BUSINESS_OPTIONS, PETAK_LAYER_OPTIONS,
  getSpatialState, setBusiness, setFilters, setDataset, setMetrics, subscribeSpatial
} from './spatialMapState.js';
import { loadBusinessData, fetchWilayahOptions, fetchAktivitasPoints, resolveTemplate } from './businessAdapter.js';
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
  const katOpts = _opts(PETAK_LAYER_OPTIONS, 'semua');
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
      + '        <div class="spatial-row">'
      + '          <label>Bulan <select id="fBulan" class="spatial-mini">' + _numOpts([1,2,3,4,5,6,7,8,9,10,11,12], d0.getMonth()+1) + '</select></label>'
      + '          <label>Tahun <select id="fTahun" class="spatial-mini"><option value="2026" selected>2026</option><option value="2025">2025</option></select></label>'
      + '          <label>Periode <select id="fPeriode" class="spatial-mini"><option value="0">Penuh (P1+P2)</option><option value="1">P1 (1-15)</option><option value="2">P2 (16-akhir)</option></select></label>'
      + '        </div>'
      + '      </div>'
      + '      <div class="spatial-fgroup">'
      + '        <div class="spatial-fgroup-title">Tahap Pembaharuan <span class="spatial-hint">filter pin + polygon; DB punya 1/2/3</span></div>'
      + '        <div class="spatial-row">'
      + '          <label>Pembaharuan <select id="fPemKe" class="spatial-mini"><option value="">Semua</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option></select></label>'
      + '        </div>'
      + '      </div>'
      + '      <div class="spatial-fgroup">'
      + '        <div class="spatial-fgroup-title">Wilayah <span class="spatial-hint">scoped hanya SPATIAL MAP</span></div>'
      + '        <div class="spatial-row">'
      + '          <label>DIVRE <select id="fDivre" class="spatial-mini"><option value="">Semua</option><option value="2">2</option></select></label>'
      + '          <label>KPH <select id="fKph" class="spatial-mini"><option value="">Semua</option><option value="31211">31211</option></select></label>'
      + '          <label>BKPH <select id="fBkph" class="spatial-mini"><option value="">Semua</option></select></label>'
      + '          <label>RPH <select id="fRph" class="spatial-mini"><option value="">Semua</option></select></label>'
      + '        </div>'
      + '        <div class="spatial-row">'
      + '          <label>TPG <select id="fTpg" class="spatial-mini"><option value="">Semua</option></select></label>'
      + '          <button id="fApply" class="spatial-btn" style="margin-left:auto">Terapkan</button>'
      + '          <button id="fReset" class="spatial-btn ghost">Reset</button>'
      + '        </div>'
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
      + '      <div class="kpi"><div class="kpi-label" id="kpi4Label">Terpenuhi</div><div class="kpi-value ok" id="kpi4">-</div><div class="kpi-sub" id="kpi4Sub">hijau/emas</div></div>'
      + '    </div>'
      + '    <div id="spatialInsight" class="spatial-insight flying"></div>'
      + '    <button id="legendToggle" class="spatial-toggle-btn legend-toggle" title="Legenda" aria-label="Legenda">ⓘ</button>'
      + '    <div class="map-legendbox flying">'
      + '      <div class="map-legend flying legend-collapsed" id="mapLegend"></div>'
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
  const map = window.L.map(box, { zoomControl: false, attributionControl: false }).setView(CENTER, 11);
  const dark = window.L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, attribution: 'Esri' });
  const sat = window.L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, attribution: 'Esri, Maxar, Earthstar Geographics' });
  // Label di pane sendiri: filter redup imagery tak kena teks (cegah halo/bayangan).
  try { map.createPane('labelPane'); const lp = map.getPane('labelPane'); if (lp) { lp.style.zIndex = 250; lp.style.pointerEvents = 'none'; } } catch(_) {}
  const refLbl = window.L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, pane: 'labelPane' });
  const petakLayer = window.L.layerGroup();
  const satGroup = window.L.layerGroup([sat]);
  const darkGroup = window.L.layerGroup([dark]);
  satGroup.addTo(map);
  refLbl.addTo(map); // satu sumber label, default ON — cegah dobel/bayangan
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
      else if (type === 'MAP_LAYER_CHANGED') log('map', 'MAP', 'layer ' + data.id + ' ' + (data.visible ? 'on' : 'off'));
      else if (type === 'MAP_FILTER_CHANGED') log('map', 'MAP', 'filter ' + (data.query || '-') + ' (' + data.shown + ')');
      else if (type === 'MAP_HIGHLIGHT_CHANGED') log('map', 'MAP', 'highlight ' + data.ids.length);
      else if (type === 'MAP_STYLE_CHANGED') log('map', 'MAP', 'basemap ' + _ctl?.get_state().basemap);
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
    const b = bizSel?.value || 'petak';
    if (katSel) katSel.style.display = (b === 'petak' || b === 'aktivitas') ? '' : 'none';
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
    if (biz === 'petak' && k === 'idle') {
      legend.innerHTML = '<span class="lg" title="ada penyadap + aktivitas 2 bln, tapi 0 di periode ini"><i style="background:#EAB308"></i> Idle (kuning)</span><span class="lg"><i style="background:#22C55E"></i> Aktif (hijau)</span>' + _legendAttrib();
    } else if (biz === 'petak' && k === 'multi_penyadap') {
      legend.innerHTML = '<span class="lg"><i style="background:#EAB308"></i> 2 penyadap (kuning)</span><span class="lg"><i style="background:#F97316"></i> 3 (oranye)</span><span class="lg"><i style="background:#22C55E"></i> >3 (hijau)</span>' + _legendAttrib();
    } else if (biz === 'petak') {
      // diperjelas: merah tanpa penyadap, kuning luas_andil<luas_baku, hijau >=
      legend.innerHTML = '<span class="lg" title="tidak ada penyadap"><i style="background:#EF4444"></i> Bongkor (merah)</span><span class="lg" title="luas_andil < luas_baku"><i style="background:#EAB308"></i> Kurang (kuning)</span><span class="lg" title="luas_andil >= luas_baku"><i style="background:#22C55E"></i> Terpenuhi (hijau)</span>' + _legendAttrib();
    } else if (biz === 'produksi') {
      legend.innerHTML = '<span class="lg"><i style="background:#EF4444"></i> 0-25%</span><span class="lg"><i style="background:#F97316"></i> 26-50%</span><span class="lg"><i style="background:#EAB308"></i> 51-75%</span><span class="lg"><i style="background:#22C55E"></i> 76-100%</span><span class="lg"><i style="background:#FFD700"></i> &gt;100%</span>' + _legendAttrib();
    } else if (biz === 'aktivitas' && k === 'idle') {
      legend.innerHTML = '<span class="lg" title="tanpa penyadap atau >2 bln tanpa aktivitas"><i style="background:#EF4444"></i> Bongkor (merah)</span><span class="lg" title="ada penyadap + aktivitas 2 bln, tapi 0 di periode ini"><i style="background:#EAB308"></i> Idle (kuning)</span><span class="lg"><i style="background:#22C55E"></i> Aktif (hijau)</span><span class="lg" title="pin + garis dashed ke pusat petak"><i style="background:#2DF2FF;border:2px solid #fff;border-radius:50%"></i> Pin Pem1 cyan/2 oranye/3 merah</span>' + _legendAttrib();
    } else if (biz === 'aktivitas') {
      // diperjelas: merah bongkor (tanpa penyadap / >2bln tanpa aktivitas), kuning idle (ada penyadap + aktivitas 2bln, tapi 0 di periode ini), hijau aktif (cur>0)
      legend.innerHTML = '<span class="lg" title="tanpa penyadap atau >2 bln tanpa aktivitas"><i style="background:#EF4444"></i> Bongkor (merah)</span><span class="lg" title="ada penyadap + aktivitas 2 bln, tapi 0 di periode ini"><i style="background:#EAB308"></i> Idle (kuning)</span><span class="lg" title="ada aktivitas periode berjalan"><i style="background:#22C55E"></i> Aktif (hijau)</span><span class="lg" title="pin aktivitas + garis dashed ke pusat petak via kode_evapot; GPS bisa melenceng"><i style="background:#2DF2FF;border:2px solid #fff;border-radius:50%"></i> Pin Pem1/2/3 ● foto — garis ke petak</span>' + _legendAttrib();
    } else if (biz === 'matriks' || biz === 'matrik') {
      legend.innerHTML = '<span class="lg"><i style="background:#EF4444"></i> Bongkor (merah)</span><span class="lg"><i style="background:#F97316"></i> Kurang & cap<50% (oranye)</span><span class="lg"><i style="background:#EAB308"></i> Kurang (kuning)</span><span class="lg"><i style="background:#22C55E"></i> Terpenuhi (hijau)</span><span class="lg"><i style="background:#FFD700"></i> &gt;100% (emas)</span>' + _legendAttrib();
    } else {
      legend.innerHTML = '<span class="lg"><i style="background:#2DF2FF"></i> Matriks</span>' + _legendAttrib();
    }
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
        } else if (k==='bkph' && fBkph) fBkph.value='';
        else if (k==='rph' && fRph) fRph.value='';
        else if (k==='tpg' && fTpg) fTpg.value='';
        else if (k==='waktu'){ if(fBulan) fBulan.value=String(d.getMonth()+1); if(fPeriode) fPeriode.value=d.getDate()<=15?'1':'2'; }
        else if (k==='kategori' && katSel) { katSel.value='semua'; _spatialWarna = ''; }
        else if (k==='pemke' && fPemKe) fPemKe.value='';
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
  async function _drainBusinessQueue(mapId, incremental) {
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
            if (cmd.op === 'set_features') await fn.call(_ctl, a.geojson ?? a, { fit: a.fit ?? true, pad: a.pad, ...(incremental || a.full === false ? { full: false } : {}) });
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
    // filter baru harus menang — batalkan tunggu render sebelumnya
    if (_awaitingFeatures !== null) {
      if (_renderWatchdog) { clearTimeout(_renderWatchdog); _renderWatchdog = null; }
      _awaitingFeatures = null; _awaitingSeq = 0;
    }
    _loading = true; _loadSeq++;
    const mySeq = _loadSeq;
    const st = collectState();
    // Retry baru untuk filter baru: kunci ganti = hitungan dari nol.
    try { const _rk = st.business + '|' + _filtKey(st); if (_rk !== _retryKey) { _retryKey = _rk; _retryCount = 0; } } catch (_) {}
    _setProgress(12, 'memuat ' + st.business + ' ' + st.filters.tahun + '-' + String(st.filters.bulan).padStart(2,'0') + (String(st.filters.periode) === '0' ? '-FULL' : '-P' + st.filters.periode) + '…');
    setBusiness(st.business);
    setFilters(st.filters);
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
        renderKPIs(st.business, st.filters.kategori, {}, 0);
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
        renderKPIs(st.business, st.filters.kategori, wc, res.features);
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
          try { await _drainBusinessQueue(res.map_id, _wantIncremental); } catch (_) {}
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
              try {
                const _fk = _filtKey(st);
                if (_fk !== _lastFittedFilt) {
                  _lastFittedFilt = _fk;
                  _suppressVp = true;
                  try { _ctl?.fit_all?.(0.05); } catch (_) {}
                  // moveend dari fit animasi datang async — resync key dulu,
                  // baru buka suppress agar gesture user berikutnya lolos.
                  setTimeout(() => { try { _lastVp = _readVp().key; } catch (_) {} _suppressVp = false; }, 500);
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
            // 809 polygon → 1618 pin; DB punya 2064 Pem1 utuh, jadi cap lama
            // 1200 memotong peta. 4000 masih di bawah cap DB (2000) & Leaflet
            // circleMarker (~4k node). ponytail: markerCluster kalau >4000.
            const pinLimit = Math.max(600, Math.min(4000, (res.features || 0) * 2 || 800));
            const r2 = await fetchAktivitasPoints({ business: st.business, filters: st.filters }, { limit: pinLimit });
            if (r2 && r2.ok && Array.isArray(r2.rows)) {
              _ctl.set_aktivitas_points(r2.rows, { token: _tok });
              // Pin hanya tampil di Z>=12 (aturan zoom user 2026-10-04);
              // di bawah itu data tetap dimuat tapi layer hidden.
              try { _ctl.set_aktivitas_visibility(map.getZoom() >= 12); } catch (_) {}
              const fotoN = r2.rows.filter(function(x){ return x.aktivitas_photo || x.foto_file; }).length;
              if (stat) stat.textContent += ' \u00b7 ' + r2.rows.length + ' aktivitas (' + fotoN + ' foto)';
              // pin siap — polygon sudah confirmed via MAP_FEATURES_LOADED, pin hide terpisah
              if (_awaitingFeatures === null) { _setProgress(96, r2.rows.length + ' pin aktivitas'); _hideProgressSoon(true); }
              else { _setProgress(92, r2.rows.length + ' pin aktivitas — menunggu polygon…'); }
              _firstLoadDone = true;
              log('map', 'MAP', 'aktivitas pin ' + r2.rows.length + ' (' + fotoN + ' foto)');
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
  // K1: klik insight expand/collapse. K3: tombol ⓘ toggle legend.
  insightBox?.addEventListener('click', () => { insightBox.classList.toggle('expanded'); });
  $sel('#legendToggle')?.addEventListener('click', function() {
    const lg = $sel('#mapLegend');
    const box = lg?.closest('.map-legendbox') || lg;
    // Migrasi state awal (inner collapsed = meta saja tampil): klik pertama
    // tampilkan SEMUA (meta + item), klik berikut sembunyikan SEMUA.
    if (lg && lg !== box && lg.classList.contains('legend-collapsed')) {
      lg.classList.remove('legend-collapsed');
      box?.classList.remove('legend-collapsed');
      this.classList.add('active');
    } else {
      box?.classList.toggle('legend-collapsed');
      this.classList.toggle('active', !box?.classList.contains('legend-collapsed'));
    }
  });
  // K4: mobile (≤780px, via device.js) KPI mulai collapse — hemat peta 360px. Desktop tetap tampil.
  try {
    if (_isMobileDevice()) kpiBox?.classList.add('collapsed');
  } catch (_) {
    if (window.matchMedia && window.matchMedia('(max-width: 780px)').matches) {
      kpiBox?.classList.add('collapsed');
    }
  }
  bizSel?.addEventListener('change', () => { syncKatVisibility(); updateLegend(bizSel.value, katSel?.value || 'semua'); updateHead(); renderChips(); scheduleReload(); });
  katSel?.addEventListener('change', () => { updateLegend(bizSel?.value || 'petak', katSel?.value || 'semua'); renderChips(); scheduleReload(); });
  // Waktu + pembaharuan_ke pakai listener generik; wilayah sudah punya cascade-specific
  [fBulan, fTahun, fPeriode, fPemKe].forEach(function(c){ if(c) c.addEventListener('change', function(){ updateHead(); renderChips(); scheduleReload(); }); });
  fApply?.addEventListener('click', reloadBusiness);
  fReset?.addEventListener('click', function(){
    if (fBulan) fBulan.value=String(d.getMonth()+1);
    if (fTahun) fTahun.value='2026';
    if (fPeriode) fPeriode.value=d.getDate()<=15?'1':'2';
    if (fPemKe) fPemKe.value='';
    // Respect scope lock: only reset unlocked dropdowns
    if (fDivre && !fDivre.disabled) fDivre.value='';
    if (fKph && !fKph.disabled) fKph.value='';
    if (fBkph && !fBkph.disabled) fBkph.value='';
    if (fRph && !fRph.disabled) fRph.value='';
    if (fTpg && !fTpg.disabled) fTpg.value='';
    try { renderWilayah(); } catch (_) {} // kembalikan opsi anak penuh sesuai scope
    if (katSel) katSel.value='semua'; if (bizSel) bizSel.value='petak';
    _spatialWarna = '';   // reset filter = buang juga subset warna dari ANA
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
    // PMTiles = base netral (tanpa analisa) untuk semua business di Z<=11.
    const want = z <= 11 ? 'pmtiles' : 'geojson';
    if (want !== _tier) {
      const tok = document.querySelector('meta[name="ana-token"]')?.content || '';
      if (want === 'pmtiles') {
        if (_ctl && typeof _ctl.set_pmtiles === 'function') {
          _ctl.set_pmtiles({ url: '/api/tiles/petak.pmtiles', visible: true, token: tok });
        }
      } else {
        // Aktifkan GeoJSON (warna analisa + popup per-polygon), sembunyikan PMTiles
        if (_ctl && typeof _ctl.set_pmtiles_visibility === 'function') {
          _ctl.set_pmtiles_visibility(false);
        }
      }
      _tier = want;
    }
    // Selalu enforce (bukan hanya saat tier berubah): reload filter me-render
    // ulang polygon dalam keadaan visible, dan tier guard lama return dini
    // sehingga polygon segar tetap tampil menutupi PMTiles di Z rendah.
    try {
      if (_ctl && typeof _ctl.set_petak_polygons_visibility === 'function') {
        _ctl.set_petak_polygons_visibility(want === 'geojson');
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
  // Scope dari KODE user (bukan jabatan): divre/kph/bkph/rph/tpg — SEMUA menang.
  //  - user divre+kph → DIVRE+KPH dikunci (disabled); BKPH/RPH/TPG HANYA
  //    se-KPH login — di luar KPH tak ada di menu (fail-closed: opsi tanpa
  //    rantai terverifikasi ikut dibuang). TPG ikut rantai lewat RPH/BKPH.
  //  - user divre saja → DIVRE dikunci; KPH/BKPH/RPH/TPG se-DIVRE itu.
  //  - user bkph/rph/tpg → levelnya dikunci; anak di bawahnya disaring rantai.
  //  - tanpa kode → semua terbuka.
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
    // Scope dari KODE user login (bukan jabatan): divre/kph/bkph/rph.
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
      const scope = {
        divre: pick(u.kode_divre, 'kode_divre'),
        kph: pick(u.kode_kph, 'kode_kph'),
        bkph: pick(u.kode_bkph, 'kode_bkph'),
        rph: pick(u.kode_rph, 'kode_rph'),
        tpgList: [],
      };
      // User TPG-level: kode_tpg = list M2M [{kode_tpg,...},...] atau mentah.
      try {
        const t = u.kode_tpg;
        if (Array.isArray(t)) for (const e of t) {
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
        else if (L === 'bkph') { const k = P('kode_kph'); if (k) { c.kph = k; Object.assign(c, chain('kph', k)); } }
        else if (L === 'rph') { const b = P('kode_bkph'); if (b) { c.bkph = b; Object.assign(c, chain('bkph', b)); } }
        else if (L === 'tpg') {
          const r = P('kode_rph'); if (r) { c.rph = r; Object.assign(c, chain('rph', r)); }
          if (!c.bkph) { const b = P('kode_bkph'); if (b) c.bkph = b; }
          if (!c.kph && c.bkph) { const up = chain('bkph', c.bkph); if (up.kph) c.kph = up.kph; if (up.divre) c.divre = up.divre; }
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
  }
  let _cascadeAttached = false;
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
        try { const st = collectState(); setFilters(st.filters); } catch (_) {}
        renderChips();
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
  function _populateDropdowns(opts) {
    _wilayahCache = opts;
    _buildWIdx();
    renderWilayah();
    try {
      const st = collectState();
      setBusiness(st.business);
      setFilters(st.filters);
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
      if (bizSel && bizSel.value !== snap.business) { bizSel.value = snap.business; syncKatVisibility(); updateLegend(snap.business, snap.filters?.kategori || katSel?.value || 'semua'); }
      if (katSel && katSel.value !== snap.filters.kategori) { katSel.value = snap.filters.kategori; try { updateLegend(snap.business, snap.filters.kategori); } catch(_){} }
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
        if (a.business !== undefined && bizSel) bizSel.value = String(a.business);
        _spatialWarna = String((a.filters && a.filters.warna) || a.warna || '').trim();
        // Apply defaults for empty time filters (same as spatial_set)
        const _defWaktu = { bulan: String(d.getMonth()+1), tahun: '2026', periode: d.getDate()<=15?'1':'2' };
        for (const k of Object.keys(_defWaktu)) {
          if (f[k] === '') f[k] = _defWaktu[k];
        }
        const _map = { bulan: fBulan, tahun: fTahun, periode: fPeriode, divre: fDivre, kph: fKph, bkph: fBkph, rph: fRph, tpg: fTpg, kategori: katSel, pembaharuan_ke: fPemKe };
        for (const k of Object.keys(_map)) {
          const elm = _map[k];
          if (!elm || f[k] === undefined || f[k] === null) continue;
          if (k === 'pembaharuan_ke' && f[k] !== '' && !['1','2','3','4'].includes(String(f[k]))) continue;
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
        if (a.business !== undefined && bizSel) bizSel.value = String(a.business);
        _spatialWarna = String((a.filters && a.filters.warna) || a.warna || '').trim();
        // Kontrak penuh solusi A: "" = reset eksplisit dari server (bukan skip).
        // Waktu kosong → default panel (bulan berjalan/2026/P berjalan); wilayah
        // kosong → dropdown dikosongkan. Tanpa ini "" menempel di dropdown waktu
        // (blank) dan guard kanonis tak pernah trip → reload tiap perintah sama.
        const _defWaktu = { bulan: String(d.getMonth()+1), tahun: '2026', periode: d.getDate()<=15?'1':'2' };
        for (const k of Object.keys(_defWaktu)) {
          if (f[k] === '') f[k] = _defWaktu[k];
        }
        const _map = { bulan: fBulan, tahun: fTahun, periode: fPeriode, divre: fDivre, kph: fKph, bkph: fBkph, rph: fRph, tpg: fTpg, kategori: katSel, pembaharuan_ke: fPemKe };
        for (const k of Object.keys(_map)) {
          const elm = _map[k];
          if (!elm || f[k] === undefined || f[k] === null) continue;
          if (k === 'pembaharuan_ke' && f[k] !== '' && !['1','2','3','4'].includes(String(f[k]))) continue;
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
