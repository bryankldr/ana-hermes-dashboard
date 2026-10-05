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
    this.highlightStyle = opts.highlightStyle || {
      color: '#FFD23F', weight: 2, opacity: 1,
      fillColor: '#FFD23F', fillOpacity: 0.3,
    };
    this.baseStyle = opts.baseStyle || null;
    this._onEvent = opts.onEvent || (() => {});
    map.on('moveend', () => this._syncCamera('MAP_MOVED'));
    map.on('zoomend', () => this._syncCamera('MAP_ZOOM_CHANGED'));
    map.on('click', e => this._emit('MAP_CLICK', { lat: e.latlng.lat, lng: e.latlng.lng }));
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
  // rkap: merah 0-25, oranye 26-50, kuning 51-75, hijau 76-100, emas >100
  static WARNA_STYLE = {
    merah:  { color: '#EF4444', fillColor: '#EF4444', fillOpacity: 0.38, weight: 1.2, opacity: 0.9 },
    oranye: { color: '#F97316', fillColor: '#F97316', fillOpacity: 0.38, weight: 1.2, opacity: 0.9 },
    kuning: { color: '#EAB308', fillColor: '#EAB308', fillOpacity: 0.35, weight: 1.2, opacity: 0.9 },
    hijau:  { color: '#22C55E', fillColor: '#22C55E', fillOpacity: 0.32, weight: 1.2, opacity: 0.9 },
    emas:   { color: '#FFD700', fillColor: '#FFD700', fillOpacity: 0.40, weight: 1.4, opacity: 1 },
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
        const wilayahLine = [p.bkph_nama && `BKPH ${escH(p.bkph_nama)}`, p.rph_nama && `RPH ${escH(p.rph_nama)}`, p.tpg_nama && `TPG ${escH(p.tpg_nama)}`].filter(Boolean).join(' · ');
        const kodeLine = [p.kode_bkph && `BKPH ${escH(p.kode_bkph)}`, p.kode_rph && `RPH ${escH(p.kode_rph)}`, p.kode_tpg && `TPG ${escH(p.kode_tpg)}`].filter(Boolean).join(' · ');
        const penyadapLine = p.penyadap_nama ? `Penyadap: ${escH(String(p.penyadap_nama).slice(0, 90))}${String(p.penyadap_nama).length>90?'…':''}` : '';
        let extraRows = '';
        if (p.pencapaian_pct !== undefined && (p.target_periode !== undefined || p.realisasi !== undefined)) {
          const pct = p.pencapaian_pct != null ? escH(String(p.pencapaian_pct)) + '%' : '-';
          const tgt = p.target_periode != null ? escH(String(p.target_periode)) : '-';
          const rea = p.realisasi != null ? escH(String(p.realisasi)) : '-';
          const eff = (p.kategori_efektivitas || p.kategori) ? escH(String(p.kategori_efektivitas || p.kategori)) : '';
          extraRows += `<div style="display:grid;grid-template-columns:auto 1fr;gap:2px 8px;font-size:10px;margin-top:6px;border-top:1px solid rgba(45,242,255,.18);padding-top:6px">`
            + (eff ? `<span style="opacity:.6">Efektivitas</span><span>${eff}</span>` : '')
            + `<span style="opacity:.6">Target periode</span><span>${tgt} kg</span>`
            + `<span style="opacity:.6">Realisasi</span><span>${rea} kg</span>`
            + `<span style="opacity:.6">Pencapaian</span><b>${pct}</b>`
            + (p.jumlah_pohon_petak != null ? `<span style="opacity:.6">Pohon petak/andil</span><span>${escH(String(p.jumlah_pohon_petak))} / ${escH(String(p.jml_pohon_andil ?? p.jml_pohon ?? '-'))} ${p.pohon_pct != null ? '('+escH(String(p.pohon_pct))+'%)' : ''}</span>` : '')
            + `</div>`;
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
          extraRows += `<div style="display:grid;grid-template-columns:auto 1fr;gap:2px 8px;font-size:10px;margin-top:6px;border-top:1px solid rgba(45,242,255,.18);padding-top:6px">`
            + q
            + `<span style="opacity:.6">Penyadap</span><span>${escH(String(jp))}</span>`
            + `<span style="opacity:.6">Andil</span><span>${escH(String(ja))} (aktif ${escH(String(aa))} &middot; idle ${escH(String(ai))} &middot; bongkor ${escH(String(ab))})</span>`
            + `<span style="opacity:.6">Aktivitas berjalan</span><b>${escH(String(ak))}</b>`
            + `<span style="opacity:.6">Aktivitas lalu</span><span>${escH(String(ap))}</span>`
            + `<span style="opacity:.6">Aktivitas 2 bln</span><span>${escH(String(a2))}</span>`
            + `</div>` + warnHtml + `<div style="font-size:9px;opacity:.5;margin-top:4px">Petak BONGKOR &ne; Andil BONGKOR &middot; andil bongkor &gt;2 bln tanpa aktivitas</div>`;
        } else {
          const la = p.luas_andil ?? '-';
          const lb = p.luas_baku ?? '-';
          const cov = (p.luas_andil != null && p.luas_baku) ? (Number(p.luas_andil)/Number(p.luas_baku)*100).toFixed(1)+'%' : '';
          const jp = p.jumlah_penyadap ?? '-';
          const gap = (p.luas_andil != null && p.luas_baku) ? (Number(p.luas_baku)-Number(p.luas_andil)).toFixed(2) : '';
          extraRows += `<div style="display:grid;grid-template-columns:auto 1fr;gap:2px 8px;font-size:10px;margin-top:6px;border-top:1px solid rgba(45,242,255,.18);padding-top:6px">`
            + `<span style="opacity:.6">Penyadap</span><span>${escH(String(jp))}</span>`
            + `<span style="opacity:.6">Luas baku</span><span>${escH(String(lb))} ha</span>`
            + `<span style="opacity:.6">Luas andil</span><span>${escH(String(la))} ha ${cov ? '('+cov+')' : ''}</span>`
            + (gap ? `<span style="opacity:.6">Gap</span><span>${escH(gap)} ha</span>` : '')
            + `</div>`;
        }
        const luasLine = p.luas_baku ? `Luas ${escH(p.luas_baku)} ha` + (p.target_rkap ? ` &middot; RKAP ${escH(p.target_rkap)} kg` : '') : (p.target_rkap ? `RKAP ${escH(p.target_rkap)} kg` : '');
        const rows = [
          `<div style="font-weight:600">Petak ${nomor}</div>`,
          wilayahLine ? `<div style="opacity:.9">${wilayahLine}</div>` : '',
          kodeLine ? `<div style="font-size:10px;opacity:.6">${kodeLine}</div>` : '',
          luasLine ? `<div style="font-size:10px;opacity:.75">${luasLine}</div>` : '',
          penyadapLine ? `<div style="font-size:10px;opacity:.75">${penyadapLine}</div>` : '',
          `<div style="margin-top:4px">${wtxt}${p.pencapaian_pct ? ` &mdash; ${escH(p.pencapaian_pct)}%` : ''}</div>`,
          extraRows,
          `<div style="font-size:9px;opacity:.45;margin-top:4px">${escH(p.kode_evapot||'')}</div>`,
        ].filter(Boolean).join('');
        layer.bindPopup(`<div style="font-family:var(--font-mono,monospace);font-size:11px;line-height:1.35;min-width:220px;max-width:300px">${rows}</div>`);
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
        color: far ? '#F97316' : '#2DF2FF',
        weight: far ? 1 : 1.2,
        opacity: far ? 0.5 : 0.7,
        dashArray: far ? '3,4' : null,
        interactive: false,
        lineCap: 'round',
      }));
      drawn++;
    } catch (_) {}
  }
  return { lines: drawn, inside, outside };
}

// Ray-casting ke ring polygon kode_evapot. Butuh poligon termuat; kalau belum
// (polygon belum di-set atau lewat limit) return false → treated sebagai luar →
// garis digambar ke center, sama seperti perilaku sebelumnya.
_pinInsidePolygon(ev, lat, lng) {
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
_nearestOnPolygon(ev, lat, lng) {
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
  try {
    const rows = Array.isArray(points) ? points : [];
    let h = rows.length + '|';
    if (rows.length) {
      const a = rows[0], b = rows[rows.length - 1];
      h += String(a.id ?? a.kode_evapot) + ',' + String(a.latitude ?? a.lat) + '|'
         + String(b.id ?? b.kode_evapot) + ',' + String(b.latitude ?? b.lat) + '|';
      let s = 0;
      for (let i = 0; i < rows.length; i += 7) { const r = rows[i]; s = (s * 31 + String(r.id ?? '').length + String(r.kode_evapot ?? '').length) | 0; }
      h += s;
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
    const fotoSrc = hasFoto ? `/api/aktivitas/photo/${escH(fotoId)}?token=${encodeURIComponent(token)}` : '';
    const fotoHtml = hasFoto
      ? `<img src="${fotoSrc}" alt="foto aktivitas" style="width:100%;height:140px;object-fit:cover;border-radius:6px;border:1px solid rgba(45,242,255,.25);background:#03101f" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='block'"><div style="display:none;font-size:10px;opacity:.6;padding:8px 0">foto tidak tersedia (sandbox)</div>`
      : `<div style="font-size:10px;opacity:.55;padding:6px 0;border:1px dashed rgba(45,242,255,.2);border-radius:6px;text-align:center">tidak ada foto</div>`;
    const html = `<div style="font-family:var(--font-mono,monospace);font-size:11px;line-height:1.4;min-width:210px;max-width:270px">`
      + `<div style="font-weight:700;font-size:12px;color:var(--neon,#2DF2FF)">Aktivitas · Petak ${nomor}</div>`
      + (penyadap ? `<div style="opacity:.85;font-size:10px">${penyadap}</div>` : '')
      + `<div style="display:flex;flex-wrap:wrap;gap:4px 10px;margin:6px 0 4px 0;padding:5px 6px;background:rgba(45,242,255,.06);border:1px solid rgba(45,242,255,.18);border-radius:5px">${cekHtml}</div>`
      + `<div style="font-size:9px;opacity:.55;margin-bottom:4px">${jmlJenis} jenis aktivitas · ⚠ koordinat GPS bisa melenceng · pin terikat ke petak via kode_evapot</div>`
      + `<div style="margin:6px 0">${fotoHtml}</div>`
      + `<div style="display:grid;grid-template-columns:auto 1fr;gap:2px 8px;font-size:10px">`
      + `<span style="opacity:.6">Pembaharuan ke</span><b>${escH(pem)}</b>`
      + `<span style="opacity:.6">User create</span><span>${userTxt}</span>`
      + `<span style="opacity:.6">Jabatan</span><span>${jabatanTxt}</span>`
      + `<span style="opacity:.6">Cuaca</span><span>${escH(cuaca)}</span>`
      + `<span style="opacity:.6">Akses</span><span>${escH(akses)}</span>`
      + `<span style="opacity:.6">Alt</span><span>${alt} m</span>`
      + `<span style="opacity:.6">Koordinat</span><span>${lat.toFixed(6)}, ${lng.toFixed(6)}</span>`
      + `<span style="opacity:.6">Tanggal</span><span>${tgl}</span>`
      + `</div>`
      + `<div style="margin-top:6px;font-size:9px;opacity:.5">${escH(r.kode_evapot || '')}</div>`
      + `</div>`;
    // popup pin = detail aktivitas (bukan identitas petak) — bedakan dari popup polygon
    // cegah bubble ke polygon di bawahnya
    try { marker.on('click', (e) => { try { e.originalEvent && e.originalEvent.stopPropagation && e.originalEvent.stopPropagation(); } catch (_) {} if (window.L && window.L.DomEvent) try { window.L.DomEvent.stopPropagation(e); } catch (_) {} }); } catch (_) {}
    marker.bindPopup(html, { maxWidth: 280, minWidth: 220 });
    marker.bindTooltip(`Petak ${nomor} · ${penyadap || '-'} · ${jmlJenis} jenis`, { direction: 'top', offset: [0, -6] });
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
    // hapus layer lama bila ada
    if (this.pmtilesLayer && this.map.hasLayer(this.pmtilesLayer)) {
      try { this.map.removeLayer(this.pmtilesLayer); } catch (_) {}
      this.pmtilesLayer = null;
    }
    if (!visible) {
      this.pmtilesUrl = null;
      this._emit('MAP_LAYER_CHANGED', { id: 'PMTilesPetak', visible: false });
      return { ok: true, visible: false };
    }
    const tileUrl = token ? (url + '?token=' + encodeURIComponent(token)) : url;
    this.pmtilesUrl = tileUrl;

    // Satu warna netral: PMTiles hanya untuk Z<=11 (polygon saja, tanpa analisa).
    // Warna analisa (merah/kuning/hijau) ikut layer GeoJSON yang tampil di Z>=12.
    // protomapsL.PolygonSymbolizer terima: fill, opacity, stroke, width, strokeOpacity
    const sym = new window.protomapsL.PolygonSymbolizer({
      fill: '#22C55E',           // hijau utama petak (consisten legend)
      opacity: 0.28,
      stroke: '#FFFFFF',
      width: 1,
      strokeOpacity: 0.9,
    });

    // paintRules: dataLayer 'petak' (nama layer di MVT build_pmtiles.py)
    const paintRules = [{
      dataLayer: 'petak',
      symbolizer: sym,
    }];

    // labelRules kosong — label di level zoom tinggi saja (ponytail)
    const labelRules = [];

    try {
      this.pmtilesLayer = window.protomapsL.leafletLayer({
        url: tileUrl,
        paintRules: paintRules,
        labelRules: labelRules,
        maxDataZoom: 15, // sinkron build_pmtiles --max-zoom 15; tanpa ini View pakai default tapi eksplisit aman
      });
      this.pmtilesLayer.addTo(this.map);
      // overlayPane sudah di atas tilePane; jangan bringToBack agar tidak tenggelam di bawah basemap gelap
      try { this.pmtilesLayer.bringToFront(); } catch (_) {}
      this.layers.set('PMTilesPetak', this.pmtilesLayer);
      this.state.layers['PMTilesPetak'] = true;
      this._emit('MAP_LAYER_CHANGED', { id: 'PMTilesPetak', visible: true });
      return { ok: true, visible: true, url: tileUrl };
    } catch (e) {
      return { ok: false, error: String(e?.message || e).slice(0, 200) };
    }
  }

  set_pmtiles_visibility(visible) {
    if (!this.pmtilesLayer) return { visible: false };
    const v = !!visible;
    if (v) { if (!this.map.hasLayer(this.pmtilesLayer)) this.pmtilesLayer.addTo(this.map); }
    else { if (this.map.hasLayer(this.pmtilesLayer)) this.map.removeLayer(this.pmtilesLayer); }
    this.state.layers['PMTilesPetak'] = v;
    this._emit('MAP_LAYER_CHANGED', { id: 'PMTilesPetak', visible: v });
    return { id: 'PMTilesPetak', visible: v };
  }
}

// Factory: satu pintu buat map.js dan (nanti) MapLibreAdapter.
export function createLeafletControl(map, opts = {}) {
  return new LeafletAdapter(map, opts);
}
