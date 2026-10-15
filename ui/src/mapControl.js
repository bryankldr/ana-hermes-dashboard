// ui/src/mapControl.js — semantic map-control interface (SPATIAL_MAP Fase 3).
//
// ANA dilarang sentuh `map.flyTo` / `document.querySelector` langsung.
// Satu-satunya jalan: interface semantik di file ini.
// Backend hari ini: LeafletAdapter (existing window.L).
// MapLibreAdapter nanti tinggal implementasi method yang sama.
//
// ponytail: polling GET /api/map/state cukup untuk ANA baca state.
// Tambah WebSocket/SSE hanya saat polling terbukti lag di E2E visual.
import { bus } from './core/bus.js';

const HOME = { lat: -8.1915, lng: 114.1491, zoom: 11 };

// URL foto aktivitas langsung ke storage Directus server KPHBWB
// (disinkron aplikasi mobile). Dibaca dari <meta name="ana-directus-url">
// yang disuntik server dari env DIRECTUS_URL. Publik tanpa kredensial —
// hanya host. Validasi id mencegah injeksi path via aktivitas_photo.
function directusAssetUrl(id, width) {
  try {
    const s = String(id || '').trim();
    if (!/^[0-9a-fA-F-]{8,36}$/.test(s)) return '';
    let base = '';
    try { base = (document.querySelector('meta[name="ana-directus-url"]')?.content || '').trim().replace(/\/+$/, ''); } catch (_) {}
    if (!base) base = 'https://sandbox2.kphbwb.web.id';
    const w = Math.max(80, Math.min(1200, parseInt(width) || 560));
    return base + '/assets/' + s + '?width=' + w;
  } catch (_) { return ''; }
}

// Canonical map state — satu sumber, tidak ada duplikat di map.js.
export function createMapState() {
  return {
    center: { ...HOME, zoom: HOME.zoom },
    bounds: null,
    basemap: 'Satelit',
    layers: {},
    selected: null,
    highlighted: [],
    filter: null,
    count: 0,
  };
}

// Jarak meter (perkiraan planar) — hanya untuk klasifikasi jauh/dekat.
function _meters(lat1, lng1, lat2, lng2) {
  const k = Math.cos((lat1 * Math.PI) / 180) * 111320;
  const dy = (lat2 - lat1) * 111320;
  const dx = (lng2 - lng1) * k;
  return Math.sqrt(dx * dx + dy * dy);
}

// Outer ring [[lng,lat], ...] dari sebuah GeoJSON geometry/feature.
// Polygon → ring[0]; MultiPolygon → ring polygon pertama yang punya >=3 titik.
function _outerRing(geom) {
  const g = geom && geom.geometry ? geom.geometry : geom;
  if (!g) return null;
  const c = g.coordinates;
  if (!Array.isArray(c) || !c.length) return null;
  if (g.type === 'MultiPolygon') {
    for (const poly of c) {
      if (Array.isArray(poly) && Array.isArray(poly[0]) && poly[0].length >= 3) return poly[0];
    }
    return null;
  }
  if (g.type === 'Polygon') return Array.isArray(c[0]) && c[0].length >= 3 ? c[0] : null;
  return null;
}

// Ring dari wrapper petak_simple.json: p = [[lng,lat], ...] (sudah outer ring).
function _ringFromFlat(p) {
  if (!Array.isArray(p) || p.length < 3) return null;
  if (Array.isArray(p[0]) && p[0].length >= 2 && typeof p[0][0] === 'number') return p;
  return null;
}

// Leaflet backend. Generic: feature = {id, layer}; bisnis (petak/penyadap)
// tetap milik data layer, bukan file ini.
export class LeafletAdapter {
  constructor(map, opts = {}) {
    this.map = map;
    this.L = window.L;
    this.home = opts.home || HOME;
    this.state = createMapState();
    this.features = new Map(); // id -> layer
    this.layers = new Map();   // layer_id -> L layer
    this.baseLayers = new Map();
    this.aktivitasLayer = null;
    this.aktivitasLines = null;
    this._aktivitasRaw = [];
    this._petakCenterByEvapot = new Map(); // kode_evapot -> L.LatLng center
    this._petakRingByEvapot = new Map();  // kode_evapot -> [[lng,lat], ...] outer ring
    this.aktivitasPoints = new Map(); // id -> marker
    this.pmtilesLayer = null; // P2-3 hybrid vector tier (protomaps-leaflet)
    this.pmtilesUrl = null;
    this._tierMode = null; // 'pmtiles' = polygon GeoJSON hidden (Z<=11), 'geojson'/null = shown
    this._aktivitasSig = null; // signature rows terakhir (skip rebuild bila data sama)
    this._penyadapDetailByEvapot = new Map(); // kode_evapot -> [{n,l,p}] cache L+P
    this.highlightStyle = opts.highlightStyle || {
      color: '#FFD23F', weight: 2, opacity: 1,
      fillColor: '#FFD23F', fillOpacity: 0.3,
    };
    this.baseStyle = opts.baseStyle || null;
    this._onEvent = opts.onEvent || (() => {});
    map.on('moveend', () => this._syncCamera('MAP_MOVED'));
    map.on('zoomend', () => this._syncCamera('MAP_ZOOM_CHANGED'));
    map.on('click', e => this._emit('MAP_CLICK', { lat: e.latlng.lat, lng: e.latlng.lng }));
    // popupopen WAJIB di level map, bukan per-layer: set_features bikin
    // L.geoJSON GROUP (bukan single layer) — handler popupopen di group tak
    // pernah fire. Baca kode_evapot dari [data-pemdetail] di konten popup.
    // getElement() tak selalu ada (versi Leaflet) — fallback query dokumen.
    map.on('popupopen', (e) => {
      try {
        let key = null;
        try {
          const el = e && e.popup && e.popup.getElement ? e.popup.getElement() : null;
          const det = el && el.querySelector ? el.querySelector('[data-pemdetail]') : null;
          if (det) key = det.getAttribute('data-pemdetail');
        } catch (_) {}
        if (!key) {
          try {
            const det = document.querySelector('.leaflet-popup-content [data-pemdetail]');
            if (det) key = det.getAttribute('data-pemdetail');
          } catch (_) {}
        }
        if (key) this._fillPenyadapDetail(key, e && e.popup);
      } catch (_) {}
    });
  }

  _emit(type, data = {}) {
    this._onEvent(type, data);
    try { bus.emit(type, data); } catch (_) {}
    try { bus.emit('MAP_VIEW_CHANGED', this.get_state()); } catch (_) {}
  }

  _syncCamera(type) {
    const c = this.map.getCenter();
    const b = this.map.getBounds();
    this.state.center = {
      lat: +c.lat.toFixed(6), lng: +c.lng.toFixed(6), zoom: this.map.getZoom(),
    };
    this.state.bounds = {
      south: +b.getSouth().toFixed(6), west: +b.getWest().toFixed(6),
      north: +b.getNorth().toFixed(6), east: +b.getEast().toFixed(6),
    };
    this._emit(type, { ...this.state.center });
  }

  registerBase(id, layer, active = false) {
    this.baseLayers.set(id, layer);
    if (active) this.state.basemap = id;
  }

  registerLayer(id, layer, visible = true) {
    this.layers.set(id, layer);
    this.state.layers[id] = visible;
  }

  registerFeature(id, layer) {
    this.features.set(String(id), layer);
    this.state.count = this.features.size;
  }

  // ── semantic controls ──
  get_state() {
    this._syncCameraSilent();
    return JSON.parse(JSON.stringify(this.state));
  }

  _syncCameraSilent() {
    try {
      const c = this.map.getCenter();
      const b = this.map.getBounds();
      this.state.center = {
        lat: +c.lat.toFixed(6), lng: +c.lng.toFixed(6), zoom: this.map.getZoom(),
      };
      this.state.bounds = {
        south: +b.getSouth().toFixed(6), west: +b.getWest().toFixed(6),
        north: +b.getNorth().toFixed(6), east: +b.getEast().toFixed(6),
      };
    } catch (_) {}
  }

  set_view({ lat, lng, zoom, bearing, pitch } = {}) {
    void bearing; void pitch; // Leaflet 2D: bearing/pitch dicatat tapi diabaikan
    const c = this.state.center;
    this.map.setView(
      [lat ?? c.lat, lng ?? c.lng],
      zoom ?? c.zoom,
    );
    this._syncCamera('MAP_VIEW_CHANGED');
    return this.get_state();
  }

  fit_bounds(bounds) {
    // bounds: {south,west,north,east} atau [[s,w],[n,e]]
    const b = Array.isArray(bounds)
      ? bounds
      : [[bounds.south, bounds.west], [bounds.north, bounds.east]];
    this.map.fitBounds(b, { padding: [20, 20] });
    this._syncCamera('MAP_VIEW_CHANGED');
    return this.get_state();
  }

  fit_all(pad = 0.05) {
    const layers = [...this.features.values()];
    if (!layers.length) return this.reset_view();
    this.map.fitBounds(this.L.featureGroup(layers).getBounds().pad(pad));
    this._syncCamera('MAP_VIEW_CHANGED');
    return this.get_state();
  }

  reset_view() {
    this.map.setView([this.home.lat, this.home.lng], this.home.zoom);
    this._syncCamera('MAP_VIEW_CHANGED');
    return this.get_state();
  }

  get_layers() {
    return Object.entries(this.state.layers).map(([id, visible]) => ({ id, visible }));
  }

  set_layer_visibility(id, visible) {
    const layer = this.layers.get(id);
    if (!layer) throw new Error('layer tidak dikenal: ' + id);
    // Tier guard (aturan zoom user 2026-10-04): Z<=11 polygon saja (PMTiles),
    // Z>=12 analisa + pin. Panel / ANA bridge set_layer_visibility tak boleh
    // menimpa tier — kalau tidak, operasikan panel atas / filter membuat
    // analisa + pin bocor di Z11/10/9.
    try {
      const z = this.map ? this.map.getZoom() : 12;
      if (id === 'Aktivitas' && visible && z < 12) {
        if (this.aktivitasLayer && this.map.hasLayer(this.aktivitasLayer)) this.map.removeLayer(this.aktivitasLayer);
        if (this.aktivitasLines && this.map.hasLayer(this.aktivitasLines)) this.map.removeLayer(this.aktivitasLines);
        this.state.layers[id] = false;
        this._emit('MAP_LAYER_CHANGED', { id, visible: false, tierEnforced: true });
        return { id, visible: false, tierEnforced: true };
      }
    } catch (_) {}
    if (visible) { if (!this.map.hasLayer(layer)) layer.addTo(this.map); }
    else { if (this.map.hasLayer(layer)) this.map.removeLayer(layer); }
    this.state.layers[id] = !!visible;
    // Petak host dinyalakan di mode PMTiles (Z<=11): polygon GeoJSON harus
    // tetap hidden — enforce ulang agar analisa tak ikut muncul.
    try {
      if (id === 'Petak' && visible && this._tierMode === 'pmtiles'
          && typeof this.set_petak_polygons_visibility === 'function') {
        this.set_petak_polygons_visibility(false);
      }
    } catch (_) {}
    this._emit('MAP_LAYER_CHANGED', { id, visible: !!visible });
    return { id, visible: !!visible };
  }

  toggle_layer(id) {
    return this.set_layer_visibility(id, !this.state.layers[id]);
  }

  // P2-3 fix: sembunyikan/tampilkan polygon GeoJSON per-fitur TANPA menyentuh
  // layer 'Petak' (analisa/popup terikat tiap polygon) maupun 'Aktivitas' (pin GPS).
  // _maybeSwitchTier pakai ini, bukan set_layer_visibility('Petak', ...).
  set_petak_polygons_visibility(visible) {
    const host = this._overlayHost();
    // catat mode tier agar set_layer_visibility('Petak',true) tak bisa
    // menyalakan ulang analisa di Z<=11 (PMTiles).
    try { this._tierMode = visible ? 'geojson' : 'pmtiles'; } catch (_) {}
    let n = 0;
    for (const [, layer] of this.features) {
      try {
        if (visible) { if (!this.map.hasLayer(layer)) layer.addTo(host); }
        else { if (this.map.hasLayer(layer)) this.map.removeLayer(layer); }
        n++;
      } catch (_) {}
    }
    return { visible: !!visible, features: n };
  }

  set_basemap(id) {
    const next = this.baseLayers.get(id);
    if (!next) throw new Error('basemap tidak dikenal: ' + id);
    for (const [, layer] of this.baseLayers) {
      if (this.map.hasLayer(layer)) this.map.removeLayer(layer);
    }
    // Satelit disimpan sebagai LayerGroup([sat, refLbl]); addTo tetap satu call.
    next.addTo(this.map);
    // Petak overlay harus tetap di atas raster basemap.
    for (const [lid, layer] of this.layers) {
      if (this.state.layers[lid] && !this.map.hasLayer(layer)) layer.addTo(this.map);
    }
    this.state.basemap = id;
    this._syncCamera('MAP_STYLE_CHANGED');
    return id;
  }

  select_feature(id) {
    const layer = this.features.get(String(id));
    if (!layer) return null;
    this.clear_highlights(true);
    this.state.selected = String(id);
    try {
      this.map.fitBounds(layer.getBounds().pad(0.3));
      layer.openPopup();
    } catch (_) {}
    this._emit('MAP_FEATURE_SELECTED', { id: String(id) });
    return String(id);
  }

  get_selected() { return this.state.selected; }

  clear_selection(silent = false) {
    this.state.selected = null;
    if (!silent) this._emit('MAP_FEATURE_SELECTED', { id: null });
    return null;
  }

  highlight_features(ids, silent = false) {
    this.clear_highlights(true);
    const list = (Array.isArray(ids) ? ids : [ids]).map(String);
    for (const id of list) {
      const layer = this.features.get(id);
      if (!layer) continue;
      if (!layer.options._origStyle && this.baseStyle) layer.options._origStyle = { ...this.baseStyle };
      try { layer.setStyle(this.highlightStyle); } catch (_) {}
      this.state.highlighted.push(id);
    }
    if (!silent) this._emit('MAP_HIGHLIGHT_CHANGED', { ids: [...this.state.highlighted] });
    return [...this.state.highlighted];
  }

  clear_highlights(silent = false) {
    for (const id of this.state.highlighted) {
      const layer = this.features.get(id);
      const orig = layer?.options?._origStyle || this.baseStyle;
      if (layer && orig) { try { layer.setStyle(orig); } catch (_) {} }
    }
    this.state.highlighted = [];
    if (!silent) this._emit('MAP_HIGHLIGHT_CHANGED', { ids: [] });
    return [];
  }

  // Filter semantik sederhana: substring pada feature id.
  // Render (hide/show) pisah dari data — data tidak dimutasi.
  set_filter(query) {
    const q = String(query ?? '').trim();
    this.state.filter = q || null;
    let shown = 0;
    for (const [id, layer] of this.features) {
      const hit = !q || id.includes(q);
      try {
        if (hit) { if (!this.map.hasLayer(layer)) layer.addTo(this._overlayHost()); shown++; }
        else { if (this.map.hasLayer(layer)) this.map.removeLayer(layer); }
      } catch (_) {}
    }
    this._emit('MAP_FILTER_CHANGED', { query: this.state.filter, shown });
    return { query: this.state.filter, shown };
  }

  clear_filter() { return this.set_filter(''); }

  // ── business color mapping (kontek_bisnis.md) ──
  // efektivitas: merah=bongkor(no penyadap), kuning=luas_andil<luas_baku, hijau=terpenuhi
  // rkap: merah ≤25, oranye (25,50], kuning (50,75], hijau (75,100], biru >100 (kunci data: emas)
  static WARNA_STYLE = {
    merah:  { color: '#EF4444', fillColor: '#EF4444', fillOpacity: 0.38, weight: 1.2, opacity: 0.9 },
    oranye: { color: '#F97316', fillColor: '#F97316', fillOpacity: 0.38, weight: 1.2, opacity: 0.9 },
    kuning: { color: '#EAB308', fillColor: '#EAB308', fillOpacity: 0.35, weight: 1.2, opacity: 0.9 },
    hijau:  { color: '#22C55E', fillColor: '#22C55E', fillOpacity: 0.32, weight: 1.2, opacity: 0.9 },
    emas:   { color: '#3B82F6', fillColor: '#3B82F6', fillOpacity: 0.40, weight: 1.4, opacity: 1 },
  };

  _resolveStyle(feature, opts = {}) {
    // 1) style_expression: {field: 'warna', mapping: {merah: {...}, ...}} or {field, colors}
    const expr = opts.style_expression || opts.styleExpression;
    if (expr && expr.field) {
      const key = String(feature.properties?.[expr.field] || '').toLowerCase();
      const m = expr.mapping || expr.colors;
      if (m && m[key]) return { ...(this.baseStyle||{}), ...m[key] };
      // fallback to WARNA_STYLE if mapping not supplied but field is warna/kategori
      if (LeafletAdapter.WARNA_STYLE[key]) return { ...(this.baseStyle||{}), ...LeafletAdapter.WARNA_STYLE[key] };
    }
    // 2) auto: properties.warna -> business color (no opts needed)
    const w = String(feature.properties?.warna || '').toLowerCase();
    if (w && LeafletAdapter.WARNA_STYLE[w]) {
      return { ...(this.baseStyle||{}), ...LeafletAdapter.WARNA_STYLE[w] };
    }
    // 3) kategori fallback (bongkor->merah)
    const kat = String(feature.properties?.kategori || '').toLowerCase();
    if (kat === 'bongkor' && LeafletAdapter.WARNA_STYLE.merah) {
      return { ...(this.baseStyle||{}), ...LeafletAdapter.WARNA_STYLE.merah };
    }
    // 4) uniform fallback
    return { ...(this.baseStyle || {}), ...(opts.style || {}) };
  }

  // ── runtime feature injection (ANA → peta) ──
  // GeoJSON FeatureCollection dari /api/simoge/query (DB 100% — 7 _map),
  // atau array {n, p} dari petak_simple.json wrapper {meta,features} (cadangan harian, bukan sumber Business Map). Render on-demand: panel kosong
  // sampai ANA memanggil ini.
  // Mendukung pewarnaan bisnis per-feature via properties.warna atau style_expression.
  //
  // ponytail: polygon + Point centroid (kph_summary_map zoom<=10).
  // Line/MultiLine butuh styling terpisah — tambahkan saat ANA push garis.
  // Detail L+P per penyadap untuk popup petak (lazy-load + cache).
  // rows: {nama_penyadap, luas_andil, jml_pohon} dari petak_penyadap.
  // Render ulang daftar: nama + "L x.xx ha · P nnn" di kanan tiap baris.
  async _fillPenyadapDetail(evapotKey, popup) {
    try {
      if (!evapotKey) return;
      let rows = this._penyadapDetailByEvapot.get(evapotKey);
      if (!rows) {
        const tok = (document.querySelector('meta[name="ana-token"]') || {}).content || '';
        const res = await fetch('/api/simoge/query', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-Ana-Token': tok },
          body: JSON.stringify({ template: 'petak_penyadap', params: { kode_evapot: evapotKey } }),
        });
        if (!res.ok) throw new Error('http ' + res.status);
        const data = await res.json();
        rows = (data.rows || []).map(r => ({
          n: String(r.nama_penyadap || '').trim(),
          l: r.luas_andil != null ? Number(r.luas_andil) : null,
          p: r.jml_pohon != null ? Number(r.jml_pohon) : null,
        })).filter(r => r.n);
        this._penyadapDetailByEvapot.set(evapotKey, rows);
      }
      if (!rows.length) return;
      const byName = new Map(rows.map(r => [r.n.toLowerCase(), r]));
      const escH = (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
      const paint = (root) => {
        try {
          // Cari via loop + getAttribute, BUKAN selector "[data-pemlist=key]":
          // kode_evapot diawali angka ("2111…") bikin CSS.escape + querySelector
          // gagal diam-diam (paint return false, popup tetap "memuat L·P…").
          const lists = root && root.querySelectorAll ? [...root.querySelectorAll('[data-pemlist]')] : [];
          const list = lists.find(el => el.getAttribute('data-pemlist') === evapotKey);
          if (!list) return false;
          const items = [...list.children];
          for (const div of items) {
            const nm = (div.textContent || '').replace(/^•\s*/, '').trim().toLowerCase();
            const d = byName.get(nm);
            if (!d) continue;
            const lp = (d.l != null && Number.isFinite(d.l) ? `L ${d.l.toFixed(1)} ha` : 'L -')
              + ' · ' + (d.p != null && Number.isFinite(d.p) ? `P ${d.p}` : 'P -');
            // Aman XSS: nama + L/P lewat escH() dulu (L/P angka via toFixed).
            div.innerHTML = `<span>• ${escH(div.textContent.replace(/^•\s*/, '').trim())}</span> <span style="opacity:.65;font-size:11px;float:right">${escH(lp)}</span>`;
          }
          const dets = root.querySelectorAll ? [...root.querySelectorAll('[data-pemdetail]')] : [];
          const det = dets.find(el => el.getAttribute('data-pemdetail') === evapotKey);
          if (det) { det.style.display = 'none'; det.textContent = ''; }
          return true;
        } catch (_) { return false; }
      };
      // Popup Leaflet: konten di DOM popup (bila masih terbuka) + pesan update
      // agar render saat fetch selesai walau user sudah buka duluan.
      let done = false;
      try {
        const el = popup && popup.getElement ? popup.getElement() : null;
        if (el && paint(el)) done = true;
      } catch (_) {}
      if (!done) {
        try {
          const popups = document.querySelectorAll('.leaflet-popup-content');
          for (const pc of popups) { if (paint(pc)) { done = true; break; } }
        } catch (_) {}
      }
      // JANGAN panggil popup.update() sesudah edit DOM langsung — update()
      // me-render ulang konten dari string asli dan MENGHAPUS hasil paint
      // (itu sebabnya popup stuck "memuat L·P…" walau fetch 200 + paint jalan).
    } catch (_) {
      // gagal = biarkan nama saja; jangan rusak popup
      try {
        const dets = [...document.querySelectorAll('.leaflet-popup-content [data-pemdetail]')];
        const det = dets.find(el => el.getAttribute('data-pemdetail') === evapotKey);
        if (det) det.textContent = '';
      } catch (_) {}
    }
  }

  set_features(geojson, opts = {}) {
    const host = this._overlayHost();
    const feats = Array.isArray(geojson) ? geojson : (geojson?.features || []);
    // Incremental (pan/zoom): full:false → hanya tambah id baru + prune jauh
    // di luar viewport+buffer. full/undefined → ganti penuh (ganti filter).
    const incremental = opts.full === false;
    const seen = new Set();
    let added = 0;
    for (const f of feats) {
      const id = String(f.id ?? f.properties?.id ?? f.properties?.nomor_petak ?? f.n ?? added);
      seen.add(id);
      if (this.features.has(id)) continue;
      let layer;
      const featStyle = this._resolveStyle(f, opts);
      if (f.type === 'Feature' && f.geometry) {
        if (f.geometry.type === 'Point') {
          // P1 centroid (kph_summary_map zoom<=10): lingkaran + popup sama.
          const c = f.geometry.coordinates || [];
          layer = this.L.circleMarker([c[1], c[0]], { ...featStyle, radius: 9 });
        } else {
          layer = this.L.geoJSON(f, { style: () => featStyle });
        }
      } else if (f.p?.length) {
        // petak_simple.json wrapper {meta,features} → p:[[lon,lat]] (flatten MultiPolygon) → leaflet [lat,lon]
        const latlngs = f.p.map(ring => ring.map(c => [c[1], c[0]]));
        layer = this.L.polygon(latlngs, featStyle);
      } else continue;
      const p = f.properties || {};
      try {
        const escH = (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        const nomor = escH(p.nomor_petak || id);
        const wkey = String(p.warna || '').toLowerCase();
        const wcol = (LeafletAdapter.WARNA_STYLE[wkey] || {}).fillColor || '#2DF2FF';
        const wtxt = p.warna ? `<span style="color:${wcol}">●</span> ${escH(p.warna)}` + (p.kategori ? ` (${escH(p.kategori)})` : (p.status ? ` (${escH(p.status)})` : '')) : '';
        // Wilayah: label + nama DB polos ("BKPH : GLENMORE"). DB tak simpan
        // prefix (cek: getah_petak.bkph='GLENMORE'), kode wilayah (kode_bkph/
        // kode_rph/kode_tpg) sengaja tak tampil — permintaan user.
        const wilayahRows = [p.bkph_nama && `<span style="opacity:.75">BKPH</span><span>: ${escH(p.bkph_nama)}</span>`, p.rph_nama && `<span style="opacity:.75">RPH</span><span>: ${escH(p.rph_nama)}</span>`, p.tpg_nama && `<span style="opacity:.75">TPG</span><span>: ${escH(p.tpg_nama)}</span>`].filter(Boolean).join('');
        const wilayahLine = wilayahRows ? `<div style="display:grid;grid-template-columns:auto 1fr;gap:3px 8px;font-size:13px;margin-top:4px">${wilayahRows}</div>` : '';
        // Penyadap: nama langsung (GROUP_CONCAT), L+P lazy-load per popup.
        // Payload 809 fitur tak dibawa (hemat), fetch petak_penyadap saat
        // popupopen via kode_evapot — cache _penyadapDetailByEvapot.
        const penyadapList = p.penyadap_nama ? String(p.penyadap_nama).split(',').map(s => s.trim()).filter(Boolean) : [];
        const evapotKey = String(p.kode_evapot || '').trim();
        // Tombol Perbesar + daftar penyadap HANYA untuk bisnis yang kolomnya
        // ada (petak efektivitas + matriks bawa penyadap_nama). Produksi
        // (rkap_map) dan aktivitas tak punya kolom itu — tanpa gate, modal
        // detail andil/mandor campur ke bisnis yang tak relevan.
        const penyadapLine = penyadapList.length
          ? `<div style="margin-top:6px;border-top:1px solid rgba(45,242,255,.18);padding-top:6px"><div style="font-size:11px;opacity:.6;margin-bottom:3px">Penyadap (${penyadapList.length})</div><div data-pemlist="${escH(evapotKey)}" style="font-size:12px;line-height:1.5;max-height:${penyadapList.length > 6 ? '108px' : 'none'};overflow-y:${penyadapList.length > 6 ? 'auto' : 'visible'};padding-right:4px">${penyadapList.map(n => `<div>• ${escH(n)}</div>`).join('')}</div><div style="font-size:10px;opacity:.5;margin-top:2px" data-pemdetail="${escH(evapotKey)}">memuat L·P…</div></div>`
          : '';
        let extraRows = '';
        if (p.pencapaian_pct !== undefined && (p.target_periode !== undefined || p.realisasi !== undefined)) {
          const pct = p.pencapaian_pct != null ? escH(String(p.pencapaian_pct)) + '%' : '-';
          const tgt = p.target_periode != null ? escH(String(p.target_periode)) : '-';
          const rea = p.realisasi != null ? escH(String(p.realisasi)) : '-';
          const eff = (p.kategori_efektivitas || p.kategori) ? escH(String(p.kategori_efektivitas || p.kategori)) : '';
          // Gap = target − realisasi (kurang berapa kg lagi). Konteks bisnis produksi.
          const _t = Number(p.target_periode), _r = Number(p.realisasi);
          const gap = (Number.isFinite(_t) && Number.isFinite(_r))
            ? (_t - _r > 0 ? `kurang ${(_t - _r).toFixed(1)} kg` : `lampaui ${(_r - _t).toFixed(1)} kg`) : '-';
          // Tombol Perbesar produksi: modal setoran + tren + mandor/KTS.
          const prodBtn = evapotKey ? `<button data-prodopen="${escH(evapotKey)}" data-kodetpg="${escH(String(p.kode_tpg || ''))}" style="margin-top:8px;width:100%;padding:8px;border-radius:8px;border:1px solid rgba(45,242,255,.5);background:rgba(45,242,255,.1);color:#fff;font-size:13px;font-weight:700;cursor:pointer" onclick="window.__anaProduksiOpen && window.__anaProduksiOpen(this.dataset.prodopen, this.dataset.kodetpg ? Number(this.dataset.kodetpg) : null)">⤢ Perbesar — detail produksi</button>` : '';
          extraRows += `<div style="display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:12px;margin-top:6px;border-top:1px solid rgba(45,242,255,.18);padding-top:6px">`
            + (eff ? `<span style="opacity:.6">Efektivitas</span><span>${eff}</span>` : '')
            + `<span style="opacity:.6">Target periode</span><span>${tgt} kg</span>`
            + `<span style="opacity:.6">Realisasi</span><span>${rea} kg</span>`
            + `<span style="opacity:.6">Pencapaian</span><b>${pct}</b>`
            + `<span style="opacity:.6">Gap</span><span>${escH(gap)}</span>`
            + (p.jumlah_pohon_petak != null ? `<span style="opacity:.6">Pohon petak/andil</span><span>${escH(String(p.jumlah_pohon_petak))} / ${escH(String(p.jml_pohon_andil ?? p.jml_pohon ?? '-'))} ${p.pohon_pct != null ? '('+escH(String(p.pohon_pct))+'%)' : ''}</span>` : '')
            + `</div>${prodBtn}`;
        } else if (p.jumlah_aktivitas !== undefined || p.aktivitas_prev !== undefined || p.aktivitas_2bulan !== undefined || p.andil_aktif !== undefined) {
          const ak = p.jumlah_aktivitas ?? p.aktivitas_periode_ini ?? '-';
          const ap = p.aktivitas_prev ?? p.aktivitas_periode_lalu ?? '-';
          const a2 = p.aktivitas_2bulan ?? '-';
          const jp = p.jumlah_penyadap ?? '-';
          const ja = p.jumlah_andil ?? '-';
          const aa = p.andil_aktif ?? '-';
          const ai = p.andil_idle ?? '-';
          const ab = p.andil_bongkor ?? '-';
          const inconsistent = (Number(p.jumlah_aktivitas ?? p.aktivitas_periode_ini ?? 0) > 0 && Number(p.jumlah_penyadap ?? 0) === 0) || (Number(p.jumlah_aktivitas ?? 0) > 0 && Number(p.jumlah_andil ?? 0) === 0);
          const warnHtml = inconsistent ? `<div style="margin-top:6px;padding:5px 7px;border:1px solid rgba(239,68,68,.55);background:rgba(239,68,68,.12);border-radius:6px;font-size:9px;line-height:1.35"><b style="color:#FCA5A5">⚠ Data inkonsisten</b> — ada ${escH(String(p.jumlah_aktivitas ?? p.aktivitas_periode_ini ?? '?'))} aktivitas pada periode ini tapi <b>tanpa penyadap/andil terdaftar</b> untuk petak ini. Perlu cek ulang <code>getah_andil</code> / mutasi penyadap.</div>` : '';
          const q = p.status || p.kategori ? `<span style="opacity:.6">Status</span><span>${escH(String(p.status || p.kategori))}</span>` : '';
          // Tren: berjalan vs lalu (naik/turun) — konteks bisnis aktivitas.
          const _ak = Number(p.jumlah_aktivitas ?? p.aktivitas_periode_ini ?? NaN);
          const _ap = Number(p.aktivitas_prev ?? p.aktivitas_periode_lalu ?? NaN);
          const tren = (Number.isFinite(_ak) && Number.isFinite(_ap))
            ? (_ak > _ap ? ` <b style="color:#86EFAC">▲ naik</b>` : _ak < _ap ? ` <b style="color:#FCA5A5">▼ turun</b>` : ` <span style="opacity:.6">— stabil</span>`) : '';
          // Tombol Perbesar aktivitas: modal detail pelaku + mandor/KTS.
          // Periode dibaca dari window.__spatialMapState saat modal dibuka
          // (bukan saat popup dibangun) agar selalu periode tampil.
          const aktBtn = evapotKey ? `<button data-aktopen="${escH(evapotKey)}" data-kodetpg="${escH(String(p.kode_tpg || ''))}" style="margin-top:8px;width:100%;padding:8px;border-radius:8px;border:1px solid rgba(45,242,255,.5);background:rgba(45,242,255,.1);color:#fff;font-size:13px;font-weight:700;cursor:pointer" onclick="window.__anaAktivitasOpen && window.__anaAktivitasOpen(this.dataset.aktopen, this.dataset.kodetpg ? Number(this.dataset.kodetpg) : null)">⤢ Perbesar — detail aktivitas</button>` : '';
          extraRows += `<div style="display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:12px;margin-top:6px;border-top:1px solid rgba(45,242,255,.18);padding-top:6px">`
            + q
            + `<span style="opacity:.6">Penyadap</span><span>${escH(String(jp))}</span>`
            + `<span style="opacity:.6">Andil</span><span>${escH(String(ja))} (aktif ${escH(String(aa))} &middot; idle ${escH(String(ai))} &middot; bongkor ${escH(String(ab))})</span>`
            + `<span style="opacity:.6">Aktivitas berjalan</span><b>${escH(String(ak))}${tren}</b>`
            + `<span style="opacity:.6">Aktivitas lalu</span><span>${escH(String(ap))}</span>`
            + `<span style="opacity:.6">Aktivitas 2 bln</span><span>${escH(String(a2))}</span>`
            + `</div>` + warnHtml + `<div style="font-size:11px;opacity:.55;margin-top:4px">Petak BONGKOR &ne; Andil BONGKOR &middot; andil bongkor &gt;2 bln tanpa aktivitas</div>${aktBtn}`;
        } else {
          const la = p.luas_andil ?? '-';
          const lb = p.luas_baku ?? '-';
          const cov = (p.luas_andil != null && p.luas_baku) ? (Number(p.luas_andil)/Number(p.luas_baku)*100).toFixed(1)+'%' : '';
          const jp = p.jumlah_penyadap ?? '-';
          const gap = (p.luas_andil != null && p.luas_baku) ? (Number(p.luas_baku)-Number(p.luas_andil)).toFixed(2) : '';
          extraRows += `<div style="display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:12px;margin-top:6px;border-top:1px solid rgba(45,242,255,.18);padding-top:6px">`
            + `<span style="opacity:.6">Penyadap</span><span>${escH(String(jp))}</span>`
            + `<span style="opacity:.6">Luas baku</span><span>${escH(String(lb))} ha</span>`
            + `<span style="opacity:.6">Luas andil</span><span>${escH(String(la))} ha ${cov ? '('+cov+')' : ''}</span>`
            + (gap ? `<span style="opacity:.6">Gap</span><span>${escH(gap)} ha</span>` : '')
            + `</div>`;
        }
        const luasLine = p.luas_baku ? `Luas ${escH(p.luas_baku)} ha` + (p.target_rkap ? ` &middot; RKAP ${escH(p.target_rkap)} kg` : '') : (p.target_rkap ? `RKAP ${escH(p.target_rkap)} kg` : '');
        const rows = [
          `<div style="font-weight:700;font-size:15px">Petak ${nomor}</div>`,
          wilayahLine || '',
          luasLine ? `<div style="font-size:12px;opacity:.8;margin-top:2px">${luasLine}</div>` : '',
          `<div style="font-size:13px;margin-top:5px">${wtxt}${p.pencapaian_pct ? ` &mdash; ${escH(p.pencapaian_pct)}%` : ''}</div>`,
          extraRows,
          penyadapLine || '',
          // Tombol Perbesar ikut gate yang sama: tanpa penyadap_nama berarti
          // bisnis produksi/aktivitas — modal andil/mandor tak relevan.
          (penyadapList.length && evapotKey ? `<button data-petakopen="${escH(evapotKey)}" data-kodetpg="${escH(String(p.kode_tpg || ''))}" style="margin-top:8px;width:100%;padding:8px;border-radius:8px;border:1px solid rgba(45,242,255,.5);background:rgba(45,242,255,.1);color:#fff;font-size:13px;font-weight:700;cursor:pointer" onclick="window.__anaPetakOpen && window.__anaPetakOpen(this.dataset.petakopen, this.dataset.kodetpg ? Number(this.dataset.kodetpg) : null)">⤢ Perbesar — info lengkap</button>` : ''),
          `<div style="font-size:10px;opacity:.45;margin-top:5px">${escH(p.kode_evapot||'')}</div>`,
        ].filter(Boolean).join('');
        layer.bindPopup(`<div style="font-family:var(--font-mono,monospace);font-size:13px;line-height:1.45;min-width:240px;max-width:320px">${rows}</div>`);
        // Hover = nomor petak saja (identitas cepat). Detail di klik (popup).
        try { layer.bindTooltip('Petak ' + nomor, { sticky: true, direction: 'top', offset: [0, -4] }); } catch (_) {}
        // Lazy-load L+P ditangani listener popupopen level map (constructor)
        // — handler per-layer tak fire untuk L.geoJSON GROUP.
      } catch (_) {}
      layer.on('click', () => { this.select_feature(id); });
      layer.addTo(host);
      this.features.set(id, layer);
      // index center + ring untuk garis aktivitas (kode_evapot -> center / outer ring)
      try {
        const ev = String(p.kode_evapot || '').trim();
        if (ev) {
          const b = layer.getBounds && layer.getBounds();
          const c = b && b.isValid && b.isValid() ? b.getCenter() : null;
          if (c) this._petakCenterByEvapot.set(ev, c);
          // ring datang dari f.geometry, atau f.p (wrapper petak_simple.json: [[lng,lat],...])
          const ring = _outerRing(f.geometry) || _ringFromFlat(f.p);
          if (ring && ring.length >= 3) this._petakRingByEvapot.set(ev, ring);
        }
      } catch (_) {}
      added++;
    }
    // Full replace (ganti filter): hapus id lama yang tak ada di respons.
    // Incremental (pan/zoom, full:false): JANGAN prune by seen-set — server
    // mengembalikan rows viewport-limited, jadi prune by seen menghapus cache
    // yang baru dibangun dan pan-balik flicker. Tanpa prune, cache terbatas
    // total dataset (filter ganti selalu clear penuh di map.js).
    // ponytail: prune jauh di luar viewport+buffer saat >5000 fitur (20 KPH).
    if (!incremental) {
      for (const [id, layer] of this.features) {
        if (seen.has(id)) continue;
        try { if (this.map.hasLayer(layer)) this.map.removeLayer(layer); } catch (_) {}
        this.features.delete(id);
      }
    }
    this.state.count = this.features.size;
    this._emit('MAP_FEATURES_LOADED', { added, total: this.features.size });
    if (opts.fit !== false && this.features.size) this.fit_all(opts.pad ?? 0.05);
    // jika pin aktivitas sudah ada, rebuild garis penghubung (GPS drift disclaimer)
    if (this._aktivitasRaw?.length) { try { this._rebuildAktivitasLines(); } catch (_) {} }
    return { added, total: this.features.size };
  }

  clear_features() {
    const host = this._overlayHost();
    for (const [, layer] of this.features) {
      try { if (this.map.hasLayer(layer)) this.map.removeLayer(layer); } catch (_) {}
    }
    this.features.clear();
    this._petakCenterByEvapot.clear();
    this._petakRingByEvapot.clear();
    try { if (this._pinGeoCache) this._pinGeoCache.clear(); } catch (_) {} // ring basi ikut dibuang
    // garis ikut hilang saat polygon di-clear (filter ganti), rebuild setelah set_features lagi
    if (this.aktivitasLines) { try { this.aktivitasLines.clearLayers(); } catch (_) {} }
    this.state.count = 0;
    this.state.highlighted = [];
    this.state.selected = null;
    this._emit('MAP_FEATURES_LOADED', { added: 0, total: 0 });
    return { total: 0 };
  }

// ── aktivitas pin-point layer (Business Intelligence — aktivitas evaluation) ──
// points: [{id, latitude, longitude, altitude, pembaharuan_ke, aktivitas_photo, foto_file, cuaca, akses_lokasi, quare, tgl_pembaharuan, nomor_petak, nama_penyadap, kode_evapot}]
// token: ANA token for <img src=/api/aktivitas/photo/<id>?token=>
// Each marker = L.circleMarker (lightweight, no clustering yet — ponytail: markerCluster when >500)

// Group marker + garis penghubung. Dipisah dari set_aktivitas_points karena
// garis harus bisa dibangun ulang tanpa fetch ulang (polygon baru dimuat).
// Tanpa method ini set_aktivitas_points() melempar TypeError di baris pertama
// dan tidak ada pin sama sekali yang muncul.
_ensureAktivitasLines() {
  if (!this.aktivitasLayer) {
    this.aktivitasLayer = this.L.layerGroup();
    try { this.aktivitasLayer.addTo(this.map); } catch (_) {}
    try { this.layers.set('Aktivitas', this.aktivitasLayer); this.state.layers['Aktivitas'] = true; } catch (_) {}
  }
  if (!this.aktivitasLines) {
    this.aktivitasLines = this.L.layerGroup();
    try { this.aktivitasLines.addTo(this.map); } catch (_) {}
  }
  return this.aktivitasLines;
}

// Garis pin → polygon HANYA kalau pin jatuh di luar petaknya.
//
// Perlu point-in-polygon, bukan ambang radius tetap: petak ratusan meter,
// penyadap sadap di luar batas petak itu NORMAL (jalan, sawah seberang). Ambang
// 28m salah dua arah — garis untuk pin yang masih di dalam petak, dan tak ada
// garis untuk pin 300m di luar yang justru butuh penanda.
//
// Kalau polygon belum termuat (filter limit < total petak) → perlakukan sebagai
// luar, garis tetap tampil. Lebih baik garis excess daripada pin yatim.
_rebuildAktivitasLines() {
  const grp = this._ensureAktivitasLines();
  try { grp.clearLayers(); } catch (_) {}
  const raw = this._aktivitasRaw;
  if (!Array.isArray(raw) || !raw.length) return { lines: 0, inside: 0, outside: 0 };

  let drawn = 0, inside = 0, outside = 0;
  for (const r of raw) {
    const lat = parseFloat(r.latitude ?? r.lat);
    const lng = parseFloat(r.longitude ?? r.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) continue;
    if (lat === 0 && lng === 0) continue;  // GPS null — tak ada pola
    const ev = String(r.kode_evapot || '').trim();
    if (!ev) continue;

    // 1) pin di dalam polygon petaknya → tak perlu garis
    if (this._pinInsidePolygon(ev, lat, lng)) { inside++; continue; }

    // 2) pin di luar → garis ke titik terdekat di tepi polygon
    const target = this._nearestOnPolygon(ev, lat, lng);
    if (!target) continue;   // polygon tak termuat (mis. limit 800 < 1003)
    const far = _meters(lat, lng, target.lat, target.lng) > 28;
    outside++;
    try {
      grp.addLayer(this.L.polyline([[lat, lng], [target.lat, target.lng]], {
        // Garis penghubung pin→petak WAJIB mencolok (keluhan: tak terlihat).
        // Jauh (>28m) = oranye tebal putus-putus; dekat = cyan tebal solid.
        // interactive:true + tooltip jarak agar garis bisa di-hover infonya.
        color: far ? '#F97316' : '#2DF2FF',
        weight: far ? 3.5 : 3,
        opacity: far ? 0.95 : 0.9,
        dashArray: far ? '7,5' : null,
        interactive: true,
        lineCap: 'round',
      }).bindTooltip(Math.round(_meters(lat, lng, target.lat, target.lng)) + ' m ke petak', { sticky: true, direction: 'top', offset: [0, -4] }));
      drawn++;
    } catch (_) {}
  }
  return { lines: drawn, inside, outside };
}

// Ray-casting ke ring polygon kode_evapot. Butuh poligon termuat; kalau belum
// (polygon belum di-set atau lewat limit) return false → treated sebagai luar →
// garis digambar ke center, sama seperti perilaku sebelumnya.
// Memo: hasil per (evapot, koordinat) di-cache — rebuild garis (tiap toggle
// zoom/visibility) tak mengulang ray-casting O(ring) ribuan kali. Cache
// dibuang di clear_features (ring ikut di-clear di sana).
_pinInsidePolygon(ev, lat, lng) {
  try {
    const c = (this._pinGeoCache || (this._pinGeoCache = new Map()));
    const k = 'i|' + ev + '|' + Number(lat).toFixed(6) + '|' + Number(lng).toFixed(6);
    if (c.has(k)) return c.get(k);
    const r = this._pinInsidePolygonRaw(ev, lat, lng);
    if (c.size > 20000) c.clear();
    c.set(k, r);
    return r;
  } catch (_) {
    return this._pinInsidePolygonRaw(ev, lat, lng);
  }
}
_pinInsidePolygonRaw(ev, lat, lng) {
  const ring = this._petakRingByEvapot && this._petakRingByEvapot.get(ev);
  if (!ring || ring.length < 3) return false;
  let c = false;
  const n = ring.length;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    if ((yi > lat) !== (yj > lat)) {
      const xint = xi + ((lat - yi) * (xj - xi)) / (yj - yi);
      if (lng < xint) c = !c;
    }
  }
  return c;
}

// Titik terdekat pada ring ke (lat,lng) — projeksi orthogonal per segment
// dalam meter-lokal. Dipakai sebagai ujung garis, bukan center polygon: center
// bisa jauh dari tepi sehingga garis terlihat "menembus" petak.
// Memo seperti _pinInsidePolygon (lihat atas).
_nearestOnPolygon(ev, lat, lng) {
  try {
    const c = (this._pinGeoCache || (this._pinGeoCache = new Map()));
    const k = 'n|' + ev + '|' + Number(lat).toFixed(6) + '|' + Number(lng).toFixed(6);
    if (c.has(k)) return c.get(k);
    const r = this._nearestOnPolygonRaw(ev, lat, lng);
    if (c.size > 20000) c.clear();
    c.set(k, r);
    return r;
  } catch (_) {
    return this._nearestOnPolygonRaw(ev, lat, lng);
  }
}
_nearestOnPolygonRaw(ev, lat, lng) {
  const ring = this._petakRingByEvapot && this._petakRingByEvapot.get(ev);
  const c = this._petakCenterByEvapot && this._petakCenterByEvapot.get(ev);
  if (!ring || ring.length < 2) return c ? { lat: c.lat, lng: c.lng } : null;
  const cosf = Math.cos((lat * Math.PI) / 180);
  let best = null, bestD = Infinity;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const ax = (ring[j][0] - lng) * 111320 * cosf, ay = (ring[j][1] - lat) * 111320;
    const bx = (ring[i][0] - lng) * 111320 * cosf, by = (ring[i][1] - lat) * 111320;
    const dx = bx - ax, dy = by - ay;
    const len2 = dx * dx + dy * dy;
    let t = len2 > 0 ? -(ax * dx + ay * dy) / len2 : 0;
    t = Math.max(0, Math.min(1, t));
    const qx = ax + t * dx, qy = ay + t * dy;
    const d2 = qx * qx + qy * qy;
    if (d2 < bestD) {
      bestD = d2;
      best = { lng: lng + qx / (111320 * cosf), lat: lat + qy / 111320 };
    }
  }
  return best;
}
set_aktivitas_points(points, opts = {}) {
  const token = opts.token || document.querySelector('meta[name="ana-token"]')?.content || '';
  this._ensureAktivitasLines();
  // Dedup: data sama (reload ganda filter+viewport overlap) → skip rebuild,
  // hanya enforce visibility. Tanpa ini clear+rebuild tiap respons membuat
  // pin flicker / sebagian hilang di Z13/14 lalu muncul lagi di Z12.
  // Sidik kuat: panjang + id/tgl baris pertama-terakhir + hash FNV atas
  // identitas penuh (id, evapot, tanggal, pembaharuan, lat, lng) tiap baris
  // ke-3. Sidik lama (panjang string saja) bisa kolisi antar filter beda
  // dengan jumlah sama → pin basi dipertahankan (filter tak cocok).
  try {
    const rows = Array.isArray(points) ? points : [];
    let h = rows.length + '|';
    if (rows.length) {
      const a = rows[0], b = rows[rows.length - 1];
      h += String(a.id ?? a.kode_evapot) + ',' + String(a.tgl_pembaharuan ?? '') + ',' + String(a.latitude ?? a.lat) + '|'
         + String(b.id ?? b.kode_evapot) + ',' + String(b.tgl_pembaharuan ?? '') + ',' + String(b.latitude ?? b.lat) + '|';
      let s = 2166136261;
      for (let i = 0; i < rows.length; i += 3) {
        const r = rows[i];
        const key = String(r.id ?? '') + '~' + String(r.kode_evapot ?? '') + '~' + String(r.tgl_pembaharuan ?? '') + '~' + String(r.pembaharuan_ke ?? '') + '~' + String(r.latitude ?? r.lat ?? '') + '~' + String(r.longitude ?? r.lng ?? '');
        for (let j = 0; j < key.length; j++) { s ^= key.charCodeAt(j); s = Math.imul(s, 16777619); }
      }
      h += (s >>> 0).toString(36);
    }
    if (h === this._aktivitasSig && this.aktivitasPoints.size > 0) {
      try {
        const z = this.map ? this.map.getZoom() : 12;
        const want = (this.state.layers['Aktivitas'] !== false) && z >= 12;
        if (want) { if (!this.map.hasLayer(this.aktivitasLayer)) this.aktivitasLayer.addTo(this.map); if (this.aktivitasLines && !this.map.hasLayer(this.aktivitasLines)) this.aktivitasLines.addTo(this.map); }
        else { if (this.map.hasLayer(this.aktivitasLayer)) this.map.removeLayer(this.aktivitasLayer); if (this.aktivitasLines && this.map.hasLayer(this.aktivitasLines)) this.map.removeLayer(this.aktivitasLines); }
      } catch (_) {}
      return { count: this.aktivitasPoints.size, skipped: 0, dedup: true };
    }
    this._aktivitasSig = h;
  } catch (_) {}
  this.clear_aktivitas_points(true);
  this._aktivitasRaw = Array.isArray(points) ? points.slice() : [];
  if (!Array.isArray(points) || !points.length) {
    this._emit('MAP_AKTIVITAS_POINTS', { count: 0 });
    return { count: 0 };
  }
  const escH = (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  let added = 0, skipped = 0;
  for (const r of points) {
    const lat = parseFloat(r.latitude ?? r.lat);
    const lng = parseFloat(r.longitude ?? r.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) { skipped++; continue; }
    // GPS nol = sensor gagal (selaras definisi _no_coord server + garis):
    // jangan jadi pin yatim di (0,0). Baris ini tetap dihitung skipped.
    if (lat === 0 || lng === 0) { skipped++; continue; }
    // hard clamp BWB + small buffer (GPS drift) — keep all valid, skip obvious garbage
    if (lat < -9.5 || lat > -6.5 || lng < 112.5 || lng > 115.5) {
      // still show but dim — don't skip, just count (audit). Only skip NaN.
    }
    const id = String(r.id ?? r.kode_evapot + '_' + added);
    const pem = String(r.pembaharuan_ke ?? '-');
    const q = r.quare;
    const cuaca = String(r.cuaca || '-');
    const akses = String(r.akses_lokasi || '-');
    const alt = r.altitude != null && String(r.altitude).trim() !== '' ? escH(String(r.altitude).trim()) : '-';
    const tgl = r.tgl_pembaharuan ? escH(String(r.tgl_pembaharuan).slice(0, 10)) : '-';
    // Jam input dari date_created server (server kirim HH:MM via jam_input).
    // DB tak punya kolom jam sendiri — tgl_pembaharuan hanya date.
    const jamTxt = r.jam_input ? escH(String(r.jam_input).slice(0, 5)) : '-';
    const nomor = escH(r.nomor_petak || r.kode_evapot || id);
    const penyadap = r.nama_penyadap ? escH(String(r.nama_penyadap).slice(0, 60)) : '';
    // user_created -> directus_users.first_name/last_name, jabatan -> jabatan.nama_jabatan
    const userNama = [r.user_first, r.user_last].filter(Boolean).join(' ');
    const userTxt = userNama ? escH(userNama.slice(0, 60)) : '-';
    const jabatanTxt = r.nama_jabatan ? escH(String(r.nama_jabatan).slice(0, 60)) : '-';
    // 5 kolom cekbox dari DB (tinyint 0/1). 1 = dicentang, 0/-null = tidak.
    const JENIS = [
      ['quare', 'Quare'], ['semprot_cas', 'Semprot'], ['kerok', 'Kerok'],
      ['budaya_bersih', 'Budaya Bersih'], ['naik_batok', 'Naik Batok'],
    ];
    const cekHtml = JENIS.map(([key, label]) => {
      const on = Number(r[key]) === 1;
      const box = on
        ? '<span style="display:inline-block;width:11px;height:11px;border:1px solid #22C55E;background:#22C55E;color:#03101f;font-size:9px;line-height:11px;text-align:center;border-radius:2px;font-weight:700">&#10003;</span>'
        : '<span style="display:inline-block;width:11px;height:11px;border:1px solid rgba(160,175,195,.45);background:transparent;border-radius:2px"></span>';
      return `<span style="display:inline-flex;align-items:center;gap:3px;opacity:${on ? 1 : .45}">${box}${escH(label)}</span>`;
    }).join('');
    const jmlJenis = JENIS.filter(([k]) => Number(r[k]) === 1).length;
    const fotoId = r.aktivitas_photo || '';
    // color by pembaharuan_ke: 1=cyan 2=orange 3=red, else by quare
    let fill = '#2DF2FF';
    if (pem === '1') fill = '#2DF2FF';
    else if (pem === '2') fill = '#F97316';
    else if (pem === '3') fill = '#EF4444';
    else if (String(q) === '1') fill = '#22C55E';
    else if (String(q) === '0') fill = '#EF4444';
    const hasFoto = !!(fotoId && String(fotoId).trim());
    const stroke = hasFoto ? '#ffffff' : fill;
    const marker = this.L.circleMarker([lat, lng], {
      radius: hasFoto ? 7 : 5,
      color: stroke, weight: 1.5, opacity: 0.95,
      fillColor: fill, fillOpacity: hasFoto ? 0.92 : 0.65,
    });
    const fotoSrc = hasFoto ? directusAssetUrl(String(fotoId).trim(), 560) : '';
    const fotoFull = hasFoto ? directusAssetUrl(String(fotoId).trim(), 1200) : '';
    // Portrait 3:4 contain (foto HP tegak, bukan landscape crop) + klik =
    // lightbox full. Lightbox satu per halaman (id tetap), isi diganti tiap
    // klik — tanpa ini tiap popup bikin overlay sendiri dan menumpuk.
    const fotoHtml = hasFoto
      ? `<img src="${fotoSrc}" data-full="${fotoFull}" alt="foto aktivitas (klik perbesar)" title="Klik untuk perbesar" style="width:100%;aspect-ratio:3/4;object-fit:contain;border-radius:6px;border:1px solid rgba(45,242,255,.25);background:#010813;cursor:zoom-in" loading="lazy" onclick="window.__anaFotoOpen && window.__anaFotoOpen(this.dataset.full)" onerror="this.style.display='none';this.nextElementSibling.style.display='block'"><div style="display:none;font-size:10px;opacity:.6;padding:8px 0">foto tidak termuat — tablet perlu internet ke server KPHBWB</div>`
      : `<div style="font-size:10px;opacity:.55;padding:6px 0;border:1px dashed rgba(45,242,255,.2);border-radius:6px;text-align:center">tidak ada foto</div>`;
    const html = `<div style="font-family:var(--font-mono,monospace);font-size:13px;line-height:1.45;min-width:230px;max-width:290px">`
      + `<div style="font-weight:700;font-size:14px;color:var(--neon,#2DF2FF)">Aktivitas · Petak ${nomor}</div>`
      + (penyadap ? `<div style="opacity:.85;font-size:12px">${penyadap}</div>` : '')
      + `<div style="display:flex;flex-wrap:wrap;gap:5px 10px;margin:6px 0 4px 0;padding:6px;background:rgba(45,242,255,.06);border:1px solid rgba(45,242,255,.18);border-radius:5px;font-size:12px">${cekHtml}</div>`
      + `<div style="font-size:11px;opacity:.55;margin-bottom:4px">${jmlJenis} jenis aktivitas · ⚠ koordinat GPS bisa melenceng · pin terikat ke petak via kode_evapot</div>`
      + `<div style="margin:6px 0">${fotoHtml}</div>`
      + `<div style="display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:12px">`
      + `<span style="opacity:.6">Pembaharuan ke</span><b>${escH(pem)}</b>`
      + `<span style="opacity:.6">User create</span><span>${userTxt}</span>`
      + `<span style="opacity:.6">Jabatan</span><span>${jabatanTxt}</span>`
      + `<span style="opacity:.6">Cuaca</span><span>${escH(cuaca)}</span>`
      + `<span style="opacity:.6">Akses</span><span>${escH(akses)}</span>`
      + `<span style="opacity:.6">Alt</span><span>${alt} m</span>`
      + `<span style="opacity:.6">Koordinat</span><span>${lat.toFixed(6)}, ${lng.toFixed(6)}</span>`
      + `<span style="opacity:.6">Tanggal</span><span>${tgl} · ${jamTxt} WIB</span>`
      + `</div>`
      + `<div style="margin-top:5px;font-size:10px;opacity:.5">${escH(r.kode_evapot || '')}</div>`
      + `</div>`;
    // popup pin = detail aktivitas (bukan identitas petak) — bedakan dari popup polygon
    // cegah bubble ke polygon di bawahnya
    try { marker.on('click', (e) => { try { e.originalEvent && e.originalEvent.stopPropagation && e.originalEvent.stopPropagation(); } catch (_) {} if (window.L && window.L.DomEvent) try { window.L.DomEvent.stopPropagation(e); } catch (_) {} }); } catch (_) {}
    marker.bindPopup(html, { maxWidth: 280, minWidth: 220 });
    // Hover polygon/pin = nomor petak saja (keluhan: perlu identitas cepat).
    // Info panjang tetap di klik (popup). Tooltip pin ringkas: nomor + jarak
    // GPS ke petak bila melenceng (tanpa ini tooltip 3 info, terlalu ramai).
    let _tipTxt = 'Petak ' + nomor;
    try {
      const _ev = String(r.kode_evapot || '').trim();
      if (_ev && !this._pinInsidePolygon(_ev, lat, lng)) {
        const _t = this._nearestOnPolygon(_ev, lat, lng);
        if (_t) _tipTxt += ' · ' + Math.round(_meters(lat, lng, _t.lat, _t.lng)) + ' m';
      }
    } catch (_) {}
    marker.bindTooltip(_tipTxt, { direction: 'top', offset: [0, -6] });
    marker.addTo(this.aktivitasLayer);
    this.aktivitasPoints.set(id, marker);
    added++;
  }
  // garis penghubung pin → pusat polygon (kode_evapot sama) untuk klarifikasi GPS drift
  try { this._rebuildAktivitasLines(); } catch (_) {}
  // garis ikut visibility layer Aktivitas (di bawah pin)
  try {
    const vis = this.state.layers['Aktivitas'] !== false;
    if (vis && this.aktivitasLines && !this.map.hasLayer(this.aktivitasLines)) this.aktivitasLines.addTo(this.map);
    if (!vis && this.aktivitasLines && this.map.hasLayer(this.aktivitasLines)) this.map.removeLayer(this.aktivitasLines);
  } catch (_) {}
  this._emit('MAP_AKTIVITAS_POINTS', { count: added, skipped });
  return { count: added, skipped };
}

clear_aktivitas_points(silent = false) {
  if (this.aktivitasLayer) { try { this.aktivitasLayer.clearLayers(); } catch (_) {} }
  if (this.aktivitasLines) { try { this.aktivitasLines.clearLayers(); } catch (_) {} }
  const n = this.aktivitasPoints.size;
  this.aktivitasPoints.clear();
  if (silent) return { cleared: n };
  this._aktivitasRaw = [];
  this._emit('MAP_AKTIVITAS_POINTS', { count: 0, cleared: n });
  return { cleared: n };
}

set_aktivitas_visibility(visible) {
  if (!this.aktivitasLayer) this._ensureAktivitasLines();
  if (!this.aktivitasLayer) return { visible: false };
  const v = !!visible;
  if (v) { if (!this.map.hasLayer(this.aktivitasLayer)) this.aktivitasLayer.addTo(this.map); if (this.aktivitasLines && !this.map.hasLayer(this.aktivitasLines)) this.aktivitasLines.addTo(this.map); try { this._rebuildAktivitasLines(); } catch (_) {} try { this.aktivitasLayer.bringToFront(); } catch (_) {} }
  else { if (this.map.hasLayer(this.aktivitasLayer)) this.map.removeLayer(this.aktivitasLayer); if (this.aktivitasLines && this.map.hasLayer(this.aktivitasLines)) this.map.removeLayer(this.aktivitasLines); }
  this.state.layers['Aktivitas'] = v;
  this._emit('MAP_LAYER_CHANGED', { id: 'Aktivitas', visible: v });
  return { id: 'Aktivitas', visible: v };
}

  _overlayHost() {
    // host default: layer overlay pertama yang terdaftar
    const first = [...this.layers.values()][0];
    return first || this.map;
  }

  // ── Multi-source PMTiles ter-scope (kph_* + bounds_*) ──
  // Satu layer per URL, reconcile per grup: tambah yang kurang, buang yang
  // keluar scope. Grup 'petak' (polygon per-KPH) dan 'bounds' (outline KPH
  // untuk choropleth/overview) visibilitasnya independen. paintRules dinamis
  // per sumber (warna choropleth dari agregat live) atau default statis.
  _pmGroup(gid) {
    try {
      this._pmGroups = this._pmGroups || {};
      if (!this._pmGroups[gid]) this._pmGroups[gid] = new Map();
      return this._pmGroups[gid];
    } catch (_) { return new Map(); }
  }
  _mkPolySym(fill, op, width, stroke) {
    // stroke default = warna fill yang sama (bentuk kecil terbaca 1 warna
    // jelas dari zoom jauh; batas detail muncul di GeoJSON zoom besar).
    return new window.protomapsL.PolygonSymbolizer({
      fill, opacity: op ?? 0.38, stroke: stroke ?? fill, width: width ?? 1, strokeOpacity: 0.9,
    });
  }
  _petakRules() {
    const _mkSym = (fill, op) => this._mkPolySym(fill, op);
    const _wf = w => (z, f) => String((f && f.props && f.props.warna) || '').toLowerCase() === w;
    return [
      { dataLayer: 'petak', symbolizer: _mkSym('#EF4444'), filter: _wf('merah') },
      { dataLayer: 'petak', symbolizer: _mkSym('#F97316'), filter: _wf('oranye') },
      { dataLayer: 'petak', symbolizer: _mkSym('#EAB308', 0.35), filter: _wf('kuning') },
      { dataLayer: 'petak', symbolizer: _mkSym('#22C55E', 0.32), filter: _wf('hijau') },
      { dataLayer: 'petak', symbolizer: _mkSym('#3B82F6', 0.40), filter: _wf('emas') },
      { dataLayer: 'petak', symbolizer: _mkSym('#22C55E', 0.28) },
    ];
  }
  set_pmtiles_sources(gid, sources = [], { token = '' } = {}) {
    // sources: [{url, kind:'petak'|'kph', rules?, maxDataZoom?}]
    if (!window.protomapsL) return { ok: false, error: 'protomapsL tidak tersedia' };
    const grp = this._pmGroup(gid);
    const want = new Map();
    for (const s of (sources || [])) {
      if (!s || !s.url) continue;
      const tileUrl = token ? (s.url + '?token=' + encodeURIComponent(token)) : s.url;
      want.set(tileUrl, s);
    }
    // buang yang keluar scope/daftar
    for (const [url, layer] of [...grp.entries()]) {
      if (!want.has(url)) {
        try { if (this.map.hasLayer(layer)) this.map.removeLayer(layer); } catch (_) {}
        grp.delete(url);
      }
    }
    let added = 0, reused = 0;
    const errors = [];
    for (const [tileUrl, s] of want.entries()) {
      if (grp.has(tileUrl)) {
        try { if (!this.map.hasLayer(grp.get(tileUrl))) grp.get(tileUrl).addTo(this.map); } catch (_) {}
        reused++;
        continue;
      }
      try {
        const rules = Array.isArray(s.rules) ? s.rules : (s.kind === 'kph' ? [] : this._petakRules());
        const layer = window.protomapsL.leafletLayer({
          url: tileUrl, paintRules: rules, labelRules: [],
          maxDataZoom: s.maxDataZoom || (s.kind === 'kph' ? 10 : 15),
        });
        layer.addTo(this.map);
        try { layer.bringToFront(); } catch (_) {}
        grp.set(tileUrl, layer);
        added++;
      } catch (e) { errors.push(String((e && e.message) || e).slice(0, 120)); }
    }
    try {
      const anyOn = [...grp.values()].some(l => { try { return this.map.hasLayer(l); } catch (_) { return false; } });
      this.state.layers[gid === 'bounds' ? 'KphBounds' : 'PMTilesPetak'] = anyOn;
    } catch (_) {}
    this._emit('MAP_LAYER_CHANGED', { id: gid === 'bounds' ? 'KphBounds' : 'PMTilesPetak', visible: true, multi: true });
    return { ok: errors.length === 0, active: [...grp.keys()], added, reused, errors };
  }
  set_pmtiles_group_visible(gid, visible) {
    const grp = this._pmGroup(gid);
    const v = !!visible;
    for (const [, layer] of grp) {
      try {
        if (v) { if (!this.map.hasLayer(layer)) layer.addTo(this.map); }
        else if (this.map.hasLayer(layer)) this.map.removeLayer(layer);
      } catch (_) {}
    }
    try { this.state.layers[gid === 'bounds' ? 'KphBounds' : 'PMTilesPetak'] = v; } catch (_) {}
    this._emit('MAP_LAYER_CHANGED', { id: gid === 'bounds' ? 'KphBounds' : 'PMTilesPetak', visible: v });
    return { visible: v, layers: grp.size };
  }
  // Aturan choropleth KPH dari agregat live {kode: hex}: satu rule per KPH +
  // fallback netral. Netral (ADM konteks tetangga): satu rule outline transparan.
  kph_bounds_rules(colorByKode, { neutral = false } = {}) {
    const mk = (fill, op, w) => this._mkPolySym(fill, op, w);
    const rules = [];
    if (!neutral) {
      for (const kode of Object.keys(colorByKode || {})) {
        const k = String(kode);
        rules.push({
          dataLayer: 'kph',
          symbolizer: mk(String(colorByKode[kode]), 0.45, 1.5),
          filter: (z, f) => String((f && f.props && (f.props.kode_kph ?? f.props.kode)) || '') === k,
        });
      }
    }
    // fallback/jaring pengaman: outline putih transparan (tile tanpa warna)
    rules.push({ dataLayer: 'kph', symbolizer: mk('#FFFFFF', neutral ? 0.0 : 0.08, 1.5) });
    return rules;
  }
  // ── P2-3 hybrid vector tier (protomaps-leaflet) ──
  // Geometri via PMTiles Range 206, atribut via viewport GeoJSON.
  // Dipanggil dari map.js saat business='petak' & zoom cocok.
  // token: untuk query param URL tile (protomaps-leaflet pakai browser fetch, tak bisa set header).
  set_pmtiles(opts = {}) {
    const { url, visible = true, token = '' } = opts;
    if (!window.protomapsL) {
      // vendor dimuat via <script> di index.html — seharusnya ada sebelum initMapPanel
      console.warn('[LeafletAdapter] protomapsL belum dimuat');
      return { ok: false, error: 'protomapsL tidak tersedia' };
    }
    const tileUrl = token ? (url + '?token=' + encodeURIComponent(token)) : url;
    if (!visible) {
      this.pmtilesUrl = null;
      try { this.set_pmtiles_group_visible('petak', false); } catch (_) {}
      return { ok: true, visible: false };
    }
    // Guard rebuild (Z11 goyang): sumber sama + hidup = cukup tampilkan.
    const r = this.set_pmtiles_sources('petak', [{ url, kind: 'petak' }], { token });
    try {
      const first = [...this._pmGroup('petak').values()][0] || null;
      this.pmtilesLayer = first;
    } catch (_) {}
    this.pmtilesUrl = tileUrl;
    return { ok: !!r.ok, visible: true, url: tileUrl, active: r.active || [], errors: r.errors || [] };
  }

  set_pmtiles_visibility(visible) {
    // Grup petak (multi-source ter-scope). Kompat: return bentuk lama.
    try {
      const r = this.set_pmtiles_group_visible('petak', !!visible);
      try { if (!visible) this.pmtilesUrl = null; } catch (_) {}
      return { id: 'PMTilesPetak', visible: !!visible, layers: r.layers };
    } catch (_) {
      return { id: 'PMTilesPetak', visible: !!visible };
    }
  }
}

// Lightbox foto aktivitas: overlay tetap satu per halaman, klik foto/bidang
// gelap/✕/Escape = tutup. Pasang sekali (guard id) walau adapter dibuat ulang.
// Zoom: tombol +/−/reset + pinch (touch) + scroll (desktop) + dobel-klik.
// Transform di img (scale + translate), reset tiap ganti foto / tutup.
function _ensureFotoLightbox() {
  try {
    if (document.getElementById('anaFotoBox')) return;
    const box = document.createElement('div');
    box.id = 'anaFotoBox';
    box.style.cssText = 'position:fixed;inset:0;z-index:99999;display:none;align-items:center;justify-content:center;background:rgba(1,6,16,.92);padding:12px';
    box.innerHTML = '<img id="anaFotoImg" alt="foto aktivitas penuh" style="max-width:min(94vw,720px);max-height:92vh;object-fit:contain;border-radius:8px;border:1px solid rgba(45,242,255,.35);background:#010813;touch-action:none">'
      + '<div id="anaFotoZoom" style="position:absolute;bottom:16px;left:50%;transform:translateX(-50%);display:flex;gap:8px;align-items:center;background:rgba(2,15,42,.9);border:1px solid rgba(45,242,255,.35);border-radius:20px;padding:6px 10px">'
      + '<button data-z="out" aria-label="Perkecil" style="width:32px;height:32px;border-radius:50%;border:1px solid rgba(45,242,255,.5);background:transparent;color:#fff;font-size:18px;cursor:pointer">−</button>'
      + '<span id="anaFotoPct" style="min-width:48px;text-align:center;font-size:12px;color:#fff">100%</span>'
      + '<button data-z="in" aria-label="Perbesar" style="width:32px;height:32px;border-radius:50%;border:1px solid rgba(45,242,255,.5);background:transparent;color:#fff;font-size:18px;cursor:pointer">+</button>'
      + '<button data-z="reset" aria-label="Ukuran awal" style="height:32px;border-radius:16px;border:1px solid rgba(45,242,255,.5);background:transparent;color:#fff;font-size:11px;padding:0 12px;cursor:pointer">1:1</button>'
      + '</div>'
      + '<button id="anaFotoX" aria-label="Tutup" style="position:absolute;top:14px;right:16px;width:38px;height:38px;border-radius:50%;border:1px solid rgba(45,242,255,.5);background:rgba(2,15,42,.9);color:#fff;font-size:18px;cursor:pointer">✕</button>';
    document.body.appendChild(box);
    const img = document.getElementById('anaFotoImg');
    let _z = 1, _x = 0, _y = 0;
    const apply = () => {
      try {
        img.style.transform = 'scale(' + _z + ') translate(' + _x + 'px,' + _y + 'px)';
        const p = document.getElementById('anaFotoPct');
        if (p) p.textContent = Math.round(_z * 100) + '%';
        img.style.cursor = _z > 1 ? 'grab' : '';
      } catch (_) {}
    };
    const reset = () => { _z = 1; _x = 0; _y = 0; apply(); };
    const close = () => { box.style.display = 'none'; reset(); try { img.removeAttribute('src'); } catch (_) {} };
    box.addEventListener('click', (e) => { if (e.target === box || e.target.id === 'anaFotoX') close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && box.style.display !== 'none') close(); });
    try {
      box.querySelector('#anaFotoZoom').addEventListener('click', (e) => {
        const b = e.target && e.target.closest ? e.target.closest('[data-z]') : null;
        if (!b) return;
        e.stopPropagation();
        const k = b.getAttribute('data-z');
        if (k === 'in') _z = Math.min(5, _z * 1.4);
        else if (k === 'out') { _z = Math.max(1, _z / 1.4); if (_z === 1) { _x = 0; _y = 0; } }
        else reset();
        apply();
      });
    } catch (_) {}
    // Scroll desktop = zoom di titik kursor. Pinch tablet = jarak dua jari.
    try {
      img.addEventListener('wheel', (e) => {
        e.preventDefault();
        _z = Math.max(1, Math.min(5, _z * (e.deltaY < 0 ? 1.2 : 1 / 1.2)));
        if (_z === 1) { _x = 0; _y = 0; }
        apply();
      }, { passive: false });
    } catch (_) {}
    try {
      let _pinch = 0;
      img.addEventListener('touchstart', (e) => {
        if (e.touches && e.touches.length === 2) {
          const a = e.touches[0], b = e.touches[1];
          _pinch = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
        }
      }, { passive: true });
      img.addEventListener('touchmove', (e) => {
        if (e.touches && e.touches.length === 2 && _pinch > 0) {
          e.preventDefault();
          const a = e.touches[0], b = e.touches[1];
          const d = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
          _z = Math.max(1, Math.min(5, _z * d / _pinch));
          _pinch = d;
          if (_z === 1) { _x = 0; _y = 0; }
          apply();
        }
      }, { passive: false });
      img.addEventListener('touchend', () => { _pinch = 0; });
    } catch (_) {}
    // Seret saat zoom >100% (mouse + satu jari). Dobel-klik = toggle 1x/2.5x.
    try {
      let _drag = null;
      img.addEventListener('pointerdown', (e) => {
        if (_z <= 1) return;
        _drag = { x: e.clientX, y: e.clientY, ox: _x, oy: _y };
        try { img.setPointerCapture(e.pointerId); } catch (_) {}
      });
      img.addEventListener('pointermove', (e) => {
        if (!_drag) return;
        _x = _drag.ox + (e.clientX - _drag.x) / _z;
        _y = _drag.oy + (e.clientY - _drag.y) / _z;
        apply();
      });
      const _end = () => { _drag = null; };
      img.addEventListener('pointerup', _end);
      img.addEventListener('pointercancel', _end);
      img.addEventListener('dblclick', (e) => {
        e.preventDefault();
        _z = _z > 1 ? 1 : 2.5; _x = 0; _y = 0;
        apply();
      });
    } catch (_) {}
    window.__anaFotoOpen = (src) => {
      if (!src) return;
      try {
        reset();
        img.src = src;
        box.style.display = 'flex';
      } catch (_) {}
    };
  } catch (_) {}
}

// Modal detail petak (tombol Perbesar di popup): info lengkap tanpa beban
// payload 809 fitur — fetch 3 template saat dibuka (petak_detail +
// petak_penyadap + petak_mandor_kts), paralel. Singleton seperti lightbox.
function _ensurePetakModal() {
  try {
    if (document.getElementById('anaPetakBox')) return;
    const box = document.createElement('div');
    box.id = 'anaPetakBox';
    box.style.cssText = 'position:fixed;inset:0;z-index:99999;display:none;align-items:center;justify-content:center;background:rgba(1,6,16,.94);padding:12px';
    box.innerHTML = '<div id="anaPetakCard" style="width:min(96vw,1050px);max-height:94vh;overflow-y:auto;background:#03101f;border:1px solid rgba(45,242,255,.4);border-radius:12px;padding:20px 22px;font-family:var(--font-mono,monospace);font-size:15px;line-height:1.6;color:#e8f4ff">'
      + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px"><b id="anaPetakTitle" style="font-size:20px;letter-spacing:.02em">Petak</b>'
      + '<button id="anaPetakX" aria-label="Tutup" style="margin-left:auto;width:38px;height:38px;border-radius:50%;border:1px solid rgba(45,242,255,.5);background:rgba(2,15,42,.9);color:#fff;font-size:18px;cursor:pointer">✕</button></div>'
      + '<div id="anaPetakBody">memuat…</div></div>';
    document.body.appendChild(box);
    const close = () => { box.style.display = 'none'; };
    box.addEventListener('click', (e) => { if (e.target === box || e.target.id === 'anaPetakX') close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && box.style.display !== 'none') close(); });
    const escH = (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    const num = (v, d=1) => (v != null && Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '-');
    window.__anaPetakOpen = async (evapot, kodeTpg) => {
      try {
        document.getElementById('anaPetakTitle').textContent = 'Kode Evapot ' + (evapot || '');
        document.getElementById('anaPetakBody').textContent = 'memuat…';
        box.style.display = 'flex';
        const tok = (document.querySelector('meta[name="ana-token"]') || {}).content || '';
        const q = async (template, params) => {
          const r = await fetch('/api/simoge/query', { method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-Ana-Token': tok },
            body: JSON.stringify({ template, params }) });
          if (!r.ok) throw new Error('http ' + r.status);
          return r.json();
        };
        // Serial, BUKAN Promise.all: koneksi DB dishare antar thread server —
        // query paralel bikin "Packet sequence number wrong / Lost connection".
        // 3x ~12ms tetap cepat, tanpa ubah server.
        const det = await q('petak_detail', { kode_evapot: evapot }).catch(() => ({ rows: [] }));
        const pem = await q('petak_penyadap', { kode_evapot: evapot }).catch(() => ({ rows: [] }));
        const mk = kodeTpg ? await q('petak_mandor_kts', { kode_tpg: kodeTpg }).catch(() => ({ rows: [] })) : { rows: [] };
        const d = (det.rows || [])[0] || {};
        const lb = d.luas_baku != null ? Number(d.luas_baku) : null;
        const jp = d.jumlah_pohon != null ? Number(d.jumlah_pohon) : null;
        const pct = (v, base) => (v != null && base ? (Number(v) / base * 100).toFixed(1) + '%' : '-');
        const pctNum = (v, base) => (v != null && base ? (Number(v) / base * 100) : null);
        const rows = (pem.rows || []).map(r => ({
          n: String(r.nama_penyadap || '').trim(),
          no: String(r.nomor_penyadap || '-'),
          l: r.luas_andil != null ? Number(r.luas_andil) : null,
          p: r.jml_pohon != null ? Number(r.jml_pohon) : null,
          tel: String(r.telpon || '').trim(), al: String(r.alamat || '').trim(),
        })).filter(r => r.n);
        const contact = (r) => [r.tel, r.al].filter(Boolean).join(' · ');
        const totL = rows.reduce((a, r) => a + (r.l || 0), 0);
        const totP = rows.reduce((a, r) => a + (r.p || 0), 0);
        // Sisa baku: clamp -0.0 (artefak pembulatan 74.2 vs 74.24) jadi 0.0
        const sisaBaku = lb != null ? Math.max(0, lb - totL).toFixed(1) + ' ha' : '-';
        const sec = (t, inner) => `<div style="margin-top:16px;border-top:1px solid rgba(45,242,255,.2);padding-top:14px"><div style="font-size:13px;opacity:.6;margin-bottom:8px;letter-spacing:.08em;font-weight:700">${escH(t)}</div>${inner}</div>`;
        // Info petak: 2 kolom horizontal agar manfaatkan lebar 900px
        const infoPairs = [
          ['Nomor', escH(d.nomor_petak || evapot)],
          ['Kode Evapot', `<span style="font-size:12px;opacity:.9">${escH(d.kode_evapot || evapot)}</span>`],
          ['BKPH', escH(d.bkph_nama || '-')],
          ['RPH', escH(d.rph_nama || '-')],
          ['TPG', escH(d.tpg_nama || '-') + (d.kode_tpg ? ` <span style="opacity:.5;font-size:12px">(${escH(String(d.kode_tpg))})</span>` : '')],
          ['KPH', escH(d.kph_nama || '-')],
          ['Luas baku', lb != null ? `<b style="font-size:16px">${lb.toFixed(2)} ha</b>` : '-'],
          ['Rencana luas', d.rencana_luas != null ? Number(d.rencana_luas).toFixed(2) + ' ha' : '-'],
          ['Jenis sadap', escH(d.jenis_sadap || '-')],
          ['RKAP', d.target_rkap != null ? `<b style="font-size:16px">${Number(d.target_rkap).toFixed(1)} kg</b>` : '-'],
          ['Pohon petak', jp != null ? `<b style="font-size:16px">${jp.toLocaleString('id-ID')}</b> pohon` : '-'],
          ['Tahun tanam / RTT', escH((d.tahun_tanam || '-') + ' / ' + (d.tahun_rtt || '-'))],
        ];
        // 2 blok: kiri info petak + mandor + ringkasan, kanan tabel penyadap.
        // <760px menumpuk vertikal (responsif).
        let html = `<style>#anaPetakCols{display:grid;grid-template-columns:340px minmax(0,1fr);gap:20px;align-items:start}#anaPetakCols>div+div{border-left:1px solid rgba(45,242,255,.45);padding-left:20px}@media (max-width:760px){#anaPetakCols{grid-template-columns:1fr}#anaPetakCols>div+div{border-left:none;padding-left:0;border-top:1px solid rgba(45,242,255,.45);padding-top:16px}}</style><div id="anaPetakCols"><div>`
          + `<div style="display:grid;grid-template-columns:1fr;gap:10px">`
          + infoPairs.filter(([, v]) => v !== '-').map(([k, v]) => `<div style="display:flex;flex-direction:column;gap:2px;padding:8px 10px;background:rgba(45,242,255,.06);border:1px solid rgba(45,242,255,.12);border-radius:8px"><span style="font-size:12px;opacity:.6;letter-spacing:.04em">${escH(k)}</span><span style="font-size:15px">${v}</span></div>`).join('')
          + `</div>`;
        let mkHtml = '';
        const mkRows = (mk.rows || []);
        if (!mkRows.length) {
          mkHtml = '<div style="opacity:.6;padding:10px;text-align:center">tidak ada user Mandor/KTS terhubung ke TPG ini</div>';
        } else {
          mkHtml = `<div style="display:grid;grid-template-columns:1fr;gap:12px">`
            + mkRows.map(r => {
              const isMandor = String(r.peran || '').toLowerCase().includes('mandor');
              const badge = isMandor ? 'MANDOR' : 'KTS';
              const badgeCol = isMandor ? 'rgba(34,197,94,.18);border-color:rgba(34,197,94,.4);color:#86EFAC' : 'rgba(45,242,255,.14);border-color:rgba(45,242,255,.35);color:#7DD3FC';
              return `<div style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:rgba(255,255,255,.04);border:1px solid rgba(45,242,255,.14);border-radius:10px">`
                + `<span style="font-size:11px;font-weight:800;letter-spacing:.08em;padding:4px 8px;border-radius:6px;border:1px solid ${badgeCol}">${escH(badge)}</span>`
                + `<span><b style="font-size:15px">${escH(r.nama)}</b><br><span style="opacity:.6;font-size:12px">${escH(r.kode_jabatan)} · ${escH(r.nama_jabatan)}</span></span>`
                + `</div>`;
            }).join('')
            + `</div>`;
        }
        html += sec('MANDOR / KTS', mkHtml);
        // Ringkasan tutup blok kiri, lalu blok kanan = tabel penyadap
        html += `<div style="margin-top:16px;padding:12px;background:rgba(45,242,255,.08);border:1px solid rgba(45,242,255,.18);border-radius:8px;font-size:14px;line-height:1.7">`
          + `<div>Total andil: <b>L ${totL.toFixed(1)} ha (${pct(totL, lb)})</b></div>`
          + `<div><b>P ${totP.toLocaleString('id-ID')} pohon (${pct(totP, jp)})</b></div>`
          + `<div style="opacity:.7">${rows.length} penyadap · Sisa luas baku: ${sisaBaku}</div>`
          + `</div></div><div>`;
        // Tabel penyadap: manfaatkan lebar — kolom L/P + % berdampingan, kontak di kanan
        const th = `font-size:12px;opacity:.6;padding:8px 10px;text-align:left;border-bottom:1px solid rgba(45,242,255,.2);border-left:1px solid rgba(45,242,255,.18);white-space:nowrap`;
        const td = `font-size:14px;padding:9px 10px;border-bottom:1px solid rgba(45,242,255,.08);border-left:1px solid rgba(45,242,255,.14);vertical-align:top`;
        const tdR = td + `;text-align:right;white-space:nowrap`;
        const bar = (pctVal) => {
          const v = pctVal != null ? Math.max(0, Math.min(100, pctVal)) : 0;
          const col = v >= 6 ? '#22C55E' : v >= 3 ? '#F59E0B' : '#EF4444';
          return `<div style="width:56px;height:6px;background:rgba(255,255,255,.12);border-radius:3px;overflow:hidden;display:inline-block;vertical-align:middle;margin-left:6px"><div style="width:${v > 10 ? 100 : v*10}%;max-width:100%;height:100%;background:${col}"></div></div>`;
        };
        let pemHtml = '';
        if (!rows.length) {
          pemHtml = '<div style="opacity:.6;padding:12px;text-align:center">tidak ada andil terdaftar</div>';
        } else {
          // Kolom Kontak tampil HANYA bila ≥1 andil punya kontak — tanpa ini
          // kolom '-' penuh makan ~180px sia-sia (temuan audit visual).
          const hasContact = rows.some(r => contact(r));
          pemHtml = `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;min-width:${hasContact ? '640px' : '520px'}">`
            + `<thead><tr>`
            + `<th style="${th};width:32px">#</th><th style="${th}">Nama — Nomor</th><th style="${th}">Luas andil</th><th style="${th}">% thd luas baku</th><th style="${th}">Pohon Andil</th><th style="${th}">% thd Pohon Petak</th>${hasContact ? `<th style="${th}">Kontak</th>` : ''}`
            + `</tr></thead><tbody>`
            + rows.map((r, i) => {
              const pL = pctNum(r.l, lb);
              const pP = pctNum(r.p, jp);
              return `<tr>`
                + `<td style="${td};opacity:.5">${i + 1}</td>`
                + `<td style="${td}"><b>${escH(r.n)}</b><br><span style="opacity:.55;font-size:12px">${escH(r.no)}</span></td>`
                + `<td style="${tdR}">${r.l != null ? r.l.toFixed(1) + ' ha' : '-'}</td>`
                + `<td style="${tdR}">${pct(r.l, lb)}${pL != null ? bar(pL) : ''}</td>`
                + `<td style="${tdR}">${r.p != null ? r.p.toLocaleString('id-ID') : '-'}</td>`
                + `<td style="${tdR}">${pct(r.p, jp)}${pP != null ? bar(pP) : ''}</td>`
                + (hasContact ? `<td style="${td};font-size:12px;opacity:.75;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escH(contact(r))}">${contact(r) ? escH(contact(r)) : '<span style="opacity:.4">-</span>'}</td>` : '')
                + `</tr>`;
            }).join('')
            + `</tbody></table></div>`;
        }
        html += sec(`PENYADAP — ${rows.length} andil (persentase terhadap luas baku ${lb != null ? lb.toFixed(2) + ' ha' : '-'} & pohon ${jp != null ? jp.toLocaleString('id-ID') : '-'})`, pemHtml)
          + `</div></div>`;
        document.getElementById('anaPetakBody').innerHTML = html;
        // Aman XSS: semua nilai DB lewat escH()/num()/toFixed(); innerHTML
        // hanya untuk struktur statis + nilai yang sudah di-escape.
      } catch (_) {
        try { document.getElementById('anaPetakBody').textContent = 'gagal memuat detail — coba lagi'; } catch (_) {}
      }
    };
  } catch (_) {}
}

// Modal detail aktivitas (tombol Perbesar di popup aktivitas): status +
// tren + pelaku per penyadap + mandor/KTS. Periode dibaca dari
// window.__spatialMapState saat dibuka (selalu periode tampil). Fetch
// serial seperti modal petak (koneksi DB dishare). Singleton.
function _ensureAktivitasModal() {
  try {
    if (document.getElementById('anaAktBox')) return;
    const box = document.createElement('div');
    box.id = 'anaAktBox';
    box.style.cssText = 'position:fixed;inset:0;z-index:99999;display:none;align-items:center;justify-content:center;background:rgba(1,6,16,.94);padding:12px';
    box.innerHTML = '<div id="anaAktCard" style="width:min(96vw,900px);max-height:94vh;overflow-y:auto;background:#03101f;border:1px solid rgba(45,242,255,.4);border-radius:12px;padding:20px 22px;font-family:var(--font-mono,monospace);font-size:15px;line-height:1.6;color:#e8f4ff">'
      + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px"><b id="anaAktTitle" style="font-size:20px;letter-spacing:.02em">Aktivitas</b>'
      + '<button id="anaAktX" aria-label="Tutup" style="margin-left:auto;width:38px;height:38px;border-radius:50%;border:1px solid rgba(45,242,255,.5);background:rgba(2,15,42,.9);color:#fff;font-size:18px;cursor:pointer">✕</button></div>'
      + '<div id="anaAktBody">memuat…</div></div>';
    document.body.appendChild(box);
    const close = () => { box.style.display = 'none'; };
    box.addEventListener('click', (e) => { if (e.target === box || e.target.id === 'anaAktX') close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && box.style.display !== 'none') close(); });
    const escH = (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    const NAMA_BULAN = ['','Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'];
    window.__anaAktivitasOpen = async (evapot, kodeTpg) => {
      try {
        // Periode tampil saat modal dibuka (bukan saat popup dibangun).
        let Y = new Date().getFullYear(), B = new Date().getMonth() + 1, P = 1;
        try {
          const st = window.__spatialMapState || {};
          const f = st.filters || {};
          if (Number.isFinite(parseInt(f.tahun))) Y = parseInt(f.tahun);
          if (f.bulan >= 1 && f.bulan <= 12) B = parseInt(f.bulan);
          if ([0, 1, 2].includes(parseInt(f.periode))) P = parseInt(f.periode);
        } catch (_) {}
        const perLabel = P === 0 ? 'Penuh' : 'P' + P;
        document.getElementById('anaAktTitle').textContent = 'Aktivitas · ' + (NAMA_BULAN[B] || B) + ' ' + perLabel + ' ' + Y;
        document.getElementById('anaAktBody').textContent = 'memuat…';
        box.style.display = 'flex';
        const tok = (document.querySelector('meta[name="ana-token"]') || {}).content || '';
        const q = async (template, params) => {
          const r = await fetch('/api/simoge/query', { method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-Ana-Token': tok },
            body: JSON.stringify({ template, params }) });
          if (!r.ok) throw new Error('http ' + r.status);
          return r.json();
        };
        const det = await q('petak_detail', { kode_evapot: evapot }).catch(() => ({ rows: [] }));
        const pel = await q('aktivitas_penyadap_petak', { kode_evapot: evapot, tahun: Y, bulan: B, periode: P }).catch(() => ({ rows: [] }));
        const mk = kodeTpg ? await q('petak_mandor_kts', { kode_tpg: kodeTpg }).catch(() => ({ rows: [] })) : { rows: [] };
        const d = (det.rows || [])[0] || {};
        const sec = (t, inner) => `<div style="margin-top:16px;border-top:1px solid rgba(45,242,255,.2);padding-top:14px"><div style="font-size:13px;opacity:.6;margin-bottom:8px;letter-spacing:.08em;font-weight:700">${escH(t)}</div>${inner}</div>`;
        let html = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px 28px;background-image:linear-gradient(rgba(45,242,255,.45),rgba(45,242,255,.45));background-size:1px 100%;background-position:center;background-repeat:no-repeat">`
          + [['Petak', escH(d.nomor_petak || evapot)],
             ['Kode Evapot', `<span style="font-size:12px;opacity:.9">${escH(d.kode_evapot || evapot)}</span>`],
             ['Wilayah', escH([d.bkph_nama, d.rph_nama, d.tpg_nama].filter(Boolean).join(' · ') || '-')],
             ['Periode', escH((NAMA_BULAN[B] || B) + ' ' + perLabel + ' ' + Y)],
            ].filter(([, v]) => v !== '-').map(([k, v]) => `<div style="display:flex;flex-direction:column;gap:2px;padding:8px 10px;background:rgba(45,242,255,.06);border:1px solid rgba(45,242,255,.12);border-radius:8px"><span style="font-size:12px;opacity:.6;letter-spacing:.04em">${escH(k)}</span><span style="font-size:15px">${v}</span></div>`).join('')
          + `</div>`;
        // Pelaku: siapa mengerjakan apa (dari baris aktivitas, bukan andil —
        // petak tanpa andil seperti 11B-1 tetap tampil pelakunya).
        const JENIS = [['quare','Q'],['semprot_cas','S'],['kerok','K'],['budaya_bersih','B'],['naik_batok','N']];
        const rows = (pel.rows || []);
        const totAkt = rows.reduce((a, r) => a + (Number(r.n_aktivitas) || 0), 0);
        let pelHtml = '';
        if (!rows.length) {
          pelHtml = '<div style="opacity:.6;padding:12px;text-align:center">tidak ada aktivitas pada periode ini</div>';
        } else {
          const th = `font-size:12px;opacity:.6;padding:8px 10px;text-align:left;border-bottom:1px solid rgba(45,242,255,.2);border-left:1px solid rgba(45,242,255,.18);white-space:nowrap`;
          const td = `font-size:14px;padding:9px 10px;border-bottom:1px solid rgba(45,242,255,.08);border-left:1px solid rgba(45,242,255,.14);vertical-align:top`;
          const tdR = td + `;text-align:right;white-space:nowrap`;
          pelHtml = `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;min-width:520px">`
            + `<thead><tr><th style="${th};width:32px">#</th><th style="${th}">Penyadap</th><th style="${th}">Aktivitas</th><th style="${th}">Jenis (Q/S/K/B/N)</th><th style="${th}">Tahap</th><th style="${th}">Terakhir</th></tr></thead><tbody>`
            + rows.map((r, i) => {
              const jenis = JENIS.map(([k, lbl]) => {
                const v = Number(r[k]) || 0;
                return v > 0 ? `<b style="color:#86EFAC">${lbl}${v}</b>` : `<span style="opacity:.3">${lbl}-</span>`;
              }).join(' ');
              return `<tr>`
                + `<td style="${td};opacity:.5">${i + 1}</td>`
                + `<td style="${td}"><b>${escH(r.nama_penyadap || '-')}</b></td>`
                + `<td style="${tdR}"><b>${escH(String(r.n_aktivitas ?? '-'))}x</b></td>`
                + `<td style="${td};font-size:13px">${jenis}</td>`
                + `<td style="${tdR}">P${escH(String(r.pembaharuan_dominan ?? '-'))}</td>`
                + `<td style="${tdR};font-size:12px;opacity:.8">${escH(String(r.tgl_terakhir || '-').slice(0, 10))}</td>`
                + `</tr>`;
            }).join('')
            + `</tbody></table></div>`
            + `<div style="margin-top:10px;padding:10px 12px;background:rgba(45,242,255,.08);border:1px solid rgba(45,242,255,.18);border-radius:8px;font-size:14px">`
            + `Total: <b>${totAkt} aktivitas</b> oleh <b>${rows.length} penyadap</b></div>`;
        }
        html += sec(`PELAKU — ${rows.length} penyadap beraktivitas (${perLabel})`, pelHtml);
        let mkHtml = '';
        const mkRows = (mk.rows || []);
        if (!mkRows.length) {
          mkHtml = '<div style="opacity:.6;padding:10px;text-align:center">tidak ada user Mandor/KTS terhubung ke TPG ini</div>';
        } else {
          mkHtml = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;background-image:linear-gradient(rgba(45,242,255,.45),rgba(45,242,255,.45));background-size:1px 100%;background-position:center;background-repeat:no-repeat">`
            + mkRows.map(r => {
              const isMandor = String(r.peran || '').toLowerCase().includes('mandor');
              const badge = isMandor ? 'MANDOR' : 'KTS';
              const badgeCol = isMandor ? 'rgba(34,197,94,.18);border-color:rgba(34,197,94,.4);color:#86EFAC' : 'rgba(45,242,255,.14);border-color:rgba(45,242,255,.35);color:#7DD3FC';
              return `<div style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:rgba(255,255,255,.04);border:1px solid rgba(45,242,255,.14);border-radius:10px">`
                + `<span style="font-size:11px;font-weight:800;letter-spacing:.08em;padding:4px 8px;border-radius:6px;border:1px solid ${badgeCol}">${escH(badge)}</span>`
                + `<span><b style="font-size:15px">${escH(r.nama)}</b><br><span style="opacity:.6;font-size:12px">${escH(r.kode_jabatan)} · ${escH(r.nama_jabatan)}</span></span>`
                + `</div>`;
            }).join('')
            + `</div>`;
        }
        html += sec('MANDOR / KTS', mkHtml);
        document.getElementById('anaAktBody').innerHTML = html;
        // Aman XSS: semua nilai DB lewat escH(); innerHTML hanya struktur
        // statis + nilai yang sudah di-escape.
      } catch (_) {
        try { document.getElementById('anaAktBody').textContent = 'gagal memuat detail — coba lagi'; } catch (_) {}
      }
    };
  } catch (_) {}
}

// Modal detail produksi (tombol Perbesar di popup produksi/matriks):
// target vs realisasi + gap + tren vs periode lalu + setoran per penyadap
// + mandor/KTS. Periode dari window.__spatialMapState saat dibuka. Fetch
// serial (koneksi DB dishare). Singleton.
function _ensureProduksiModal() {
  try {
    if (document.getElementById('anaProdBox')) return;
    const box = document.createElement('div');
    box.id = 'anaProdBox';
    box.style.cssText = 'position:fixed;inset:0;z-index:99999;display:none;align-items:center;justify-content:center;background:rgba(1,6,16,.94);padding:12px';
    box.innerHTML = '<div id="anaProdCard" style="width:min(96vw,900px);max-height:94vh;overflow-y:auto;background:#03101f;border:1px solid rgba(45,242,255,.4);border-radius:12px;padding:20px 22px;font-family:var(--font-mono,monospace);font-size:15px;line-height:1.6;color:#e8f4ff">'
      + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px"><b id="anaProdTitle" style="font-size:20px;letter-spacing:.02em">Produksi</b>'
      + '<button id="anaProdX" aria-label="Tutup" style="margin-left:auto;width:38px;height:38px;border-radius:50%;border:1px solid rgba(45,242,255,.5);background:rgba(2,15,42,.9);color:#fff;font-size:18px;cursor:pointer">✕</button></div>'
      + '<div id="anaProdBody">memuat…</div></div>';
    document.body.appendChild(box);
    const close = () => { box.style.display = 'none'; };
    box.addEventListener('click', (e) => { if (e.target === box || e.target.id === 'anaProdX') close(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && box.style.display !== 'none') close(); });
    const escH = (s) => String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    const NAMA_BULAN = ['','Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'];
    // Periode lalu untuk tren: P2→P1 bulan sama, P1→P2 bulan lalu, Penuh→Penuh bulan lalu.
    const prevPer = (y, b, p) => {
      if (p === 2) return [y, b, 1];
      if (p === 1) { const pb = b > 1 ? b - 1 : 12, py = b > 1 ? y : y - 1; return [py, pb, 2]; }
      const pb = b > 1 ? b - 1 : 12, py = b > 1 ? y : y - 1; return [py, pb, 0];
    };
    window.__anaProduksiOpen = async (evapot, kodeTpg) => {
      try {
        let Y = new Date().getFullYear(), B = new Date().getMonth() + 1, P = 1;
        try {
          const st = window.__spatialMapState || {};
          const f = st.filters || {};
          if (Number.isFinite(parseInt(f.tahun))) Y = parseInt(f.tahun);
          if (f.bulan >= 1 && f.bulan <= 12) B = parseInt(f.bulan);
          if ([0, 1, 2].includes(parseInt(f.periode))) P = parseInt(f.periode);
        } catch (_) {}
        const perLabel = P === 0 ? 'Penuh' : 'P' + P;
        document.getElementById('anaProdTitle').textContent = 'Produksi · ' + (NAMA_BULAN[B] || B) + ' ' + perLabel + ' ' + Y;
        document.getElementById('anaProdBody').textContent = 'memuat…';
        box.style.display = 'flex';
        const tok = (document.querySelector('meta[name="ana-token"]') || {}).content || '';
        const q = async (template, params) => {
          const r = await fetch('/api/simoge/query', { method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-Ana-Token': tok },
            body: JSON.stringify({ template, params }) });
          if (!r.ok) throw new Error('http ' + r.status);
          return r.json();
        };
        // rkap_map per petak tak ada (agregat per wilayah) — hitung dari
        // penerimaan langsung + target RO via target_pct. Serial (DB share).
        const det = await q('petak_detail', { kode_evapot: evapot }).catch(() => ({ rows: [] }));
        const [py, pb, pp] = prevPer(Y, B, P);
        // Tren lalu dari produksi_penyadap_petak (per petak), BUKAN
        // produksi_aktiv (agregat global — pakai itu trennya milik semua petak).
        const now = await q('produksi_penyadap_petak', { kode_evapot: evapot, tahun: Y, bulan: B, periode: P }).catch(() => ({ rows: [] }));
        const laluRows = await q('produksi_penyadap_petak', { kode_evapot: evapot, tahun: py, bulan: pb, periode: pp }).catch(() => ({ rows: [] }));
        const tp = await q('target_pct', { tahun: Y, bulan: B, periode: P }).catch(() => ({ rows: [] }));
        const mk = kodeTpg ? await q('petak_mandor_kts', { kode_tpg: kodeTpg }).catch(() => ({ rows: [] })) : { rows: [] };
        const d = (det.rows || [])[0] || {};
        const rk = d.target_rkap != null ? Number(d.target_rkap) : null;
        const pctRO = (tp.rows || [])[0] ? Number(tp.rows[0].pct) : null;
        const tgt = (rk != null && pctRO != null) ? rk * pctRO / 100 : null;
        const rows = (now.rows || []);
        const totKg = rows.reduce((a, r) => a + (Number(r.kg) || 0), 0);
        const cap = (tgt && tgt > 0) ? totKg / tgt * 100 : null;
        const laluKg = (laluRows.rows || []).reduce((a, r) => a + (Number(r.kg) || 0), 0);
        const trenTxt = totKg > laluKg ? ` <b style="color:#86EFAC">▲ naik ${totKg && laluKg ? '+' + ((totKg - laluKg) / laluKg * 100).toFixed(1) + '%' : ''}</b>`
          : totKg < laluKg ? ` <b style="color:#FCA5A5">▼ turun</b>` : ` <span style="opacity:.6">— stabil</span>`;
        const barW = cap != null ? Math.max(0, Math.min(100, cap)) : 0;
        const barCol = cap == null ? '#666' : cap < 25 ? '#EF4444' : cap < 50 ? '#F97316' : cap < 75 ? '#EAB308' : '#22C55E';
        const sec = (t, inner) => `<div style="margin-top:16px;border-top:1px solid rgba(45,242,255,.2);padding-top:14px"><div style="font-size:13px;opacity:.6;margin-bottom:8px;letter-spacing:.08em;font-weight:700">${escH(t)}</div>${inner}</div>`;
        let html = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px 28px;background-image:linear-gradient(rgba(45,242,255,.45),rgba(45,242,255,.45));background-size:1px 100%;background-position:center;background-repeat:no-repeat">`
          + [['Petak', escH(d.nomor_petak || evapot)],
             ['Kode Evapot', `<span style="font-size:12px;opacity:.9">${escH(d.kode_evapot || evapot)}</span>`],
             ['Wilayah', escH([d.bkph_nama, d.rph_nama, d.tpg_nama].filter(Boolean).join(' · ') || '-')],
             ['Periode', escH((NAMA_BULAN[B] || B) + ' ' + perLabel + ' ' + Y)],
             ['Target RKAP', rk != null ? `<b style="font-size:16px">${rk.toFixed(1)} kg</b>` : '-'],
             ['Target RO periode', (pctRO != null ? pctRO.toFixed(1) + '% → <b style="font-size:16px">' + (tgt != null ? tgt.toFixed(1) : '-') + ' kg</b>' : '-')],
             ['Realisasi', `<b style="font-size:16px">${totKg.toFixed(1)} kg</b>${trenTxt}`],
             ['Pencapaian', cap != null ? `<b style="font-size:16px">${cap.toFixed(1)}%</b>` : '-'],
            ].filter(([, v]) => v !== '-').map(([k, v]) => `<div style="display:flex;flex-direction:column;gap:2px;padding:8px 10px;background:rgba(45,242,255,.06);border:1px solid rgba(45,242,255,.12);border-radius:8px"><span style="font-size:12px;opacity:.6;letter-spacing:.04em">${escH(k)}</span><span style="font-size:15px">${v}</span></div>`).join('')
          + `</div>`
          + `<div style="margin-top:12px"><div style="height:10px;background:rgba(255,255,255,.1);border-radius:5px;overflow:hidden"><div style="width:${barW}%;height:100%;background:${barCol}"></div></div>`
          + `<div style="font-size:12px;opacity:.65;margin-top:4px">vs periode lalu: ${laluKg.toFixed(1)} kg (${NAMA_BULAN[pb] || pb} ${pp === 0 ? 'Penuh' : 'P' + pp}) · Gap: ${tgt != null ? (tgt - totKg > 0 ? 'kurang ' + (tgt - totKg).toFixed(1) + ' kg' : 'lampaui ' + (totKg - tgt).toFixed(1) + ' kg') : '-'}</div></div>`;
        let setHtml = '';
        if (!rows.length) {
          setHtml = '<div style="opacity:.6;padding:12px;text-align:center">belum ada setoran pada periode ini</div>';
        } else {
          const th = `font-size:12px;opacity:.6;padding:8px 10px;text-align:left;border-bottom:1px solid rgba(45,242,255,.2);border-left:1px solid rgba(45,242,255,.18);white-space:nowrap`;
          const td = `font-size:14px;padding:9px 10px;border-bottom:1px solid rgba(45,242,255,.08);border-left:1px solid rgba(45,242,255,.14);vertical-align:top`;
          const tdR = td + `;text-align:right;white-space:nowrap`;
          setHtml = `<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;min-width:480px">`
            + `<thead><tr><th style="${th};width:32px">#</th><th style="${th}">Penyadap</th><th style="${th}">Setoran</th><th style="${th}">Terima</th><th style="${th}">Terakhir</th></tr></thead><tbody>`
            + rows.map((r, i) => {
              const kg = Number(r.kg) || 0;
              const share = totKg > 0 ? (kg / totKg * 100).toFixed(1) + '%' : '-';
              return `<tr>`
                + `<td style="${td};opacity:.5">${i + 1}</td>`
                + `<td style="${td}"><b>${escH(r.nama_penyadap || '-')}</b></td>`
                + `<td style="${tdR}"><b>${kg.toFixed(1)} kg</b> <span style="opacity:.6;font-size:12px">(${share})</span></td>`
                + `<td style="${tdR}">${escH(String(r.n_terima ?? '-'))}x</td>`
                + `<td style="${tdR};font-size:12px;opacity:.8">${escH(String(r.tgl_terakhir || '-').slice(0, 10))}</td>`
                + `</tr>`;
            }).join('')
            + `</tbody></table></div>`;
        }
        html += sec(`SETORAN — ${rows.length} penyadap setor (${perLabel})`, setHtml);
        let mkHtml = '';
        const mkRows = (mk.rows || []);
        if (!mkRows.length) {
          mkHtml = '<div style="opacity:.6;padding:10px;text-align:center">tidak ada user Mandor/KTS terhubung ke TPG ini</div>';
        } else {
          mkHtml = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;background-image:linear-gradient(rgba(45,242,255,.45),rgba(45,242,255,.45));background-size:1px 100%;background-position:center;background-repeat:no-repeat">`
            + mkRows.map(r => {
              const isMandor = String(r.peran || '').toLowerCase().includes('mandor');
              const badge = isMandor ? 'MANDOR' : 'KTS';
              const badgeCol = isMandor ? 'rgba(34,197,94,.18);border-color:rgba(34,197,94,.4);color:#86EFAC' : 'rgba(45,242,255,.14);border-color:rgba(45,242,255,.35);color:#7DD3FC';
              return `<div style="display:flex;align-items:center;gap:12px;padding:12px 14px;background:rgba(255,255,255,.04);border:1px solid rgba(45,242,255,.14);border-radius:10px">`
                + `<span style="font-size:11px;font-weight:800;letter-spacing:.08em;padding:4px 8px;border-radius:6px;border:1px solid ${badgeCol}">${escH(badge)}</span>`
                + `<span><b style="font-size:15px">${escH(r.nama)}</b><br><span style="opacity:.6;font-size:12px">${escH(r.kode_jabatan)} · ${escH(r.nama_jabatan)}</span></span>`
                + `</div>`;
            }).join('')
            + `</div>`;
        }
        html += sec('MANDOR / KTS', mkHtml);
        document.getElementById('anaProdBody').innerHTML = html;
        // Aman XSS: semua nilai DB lewat escH()/toFixed(); innerHTML hanya
        // struktur statis + nilai yang sudah di-escape.
      } catch (_) {
        try { document.getElementById('anaProdBody').textContent = 'gagal memuat detail — coba lagi'; } catch (_) {}
      }
    };
  } catch (_) {}
}

// Factory: satu pintu buat map.js dan (nanti) MapLibreAdapter.
export function createLeafletControl(map, opts = {}) {
  try { _ensureFotoLightbox(); } catch (_) {}
  try { _ensurePetakModal(); } catch (_) {}
  try { _ensureAktivitasModal(); } catch (_) {}
  try { _ensureProduksiModal(); } catch (_) {}
  return new LeafletAdapter(map, opts);
}
