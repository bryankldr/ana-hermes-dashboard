// ui/src/businessAdapter.js — facade antara SpatialMapState → Business Data Engine
// DATABASE → Engine (simoge-business) → Processed Data → SpatialMapState → Map → ANA
// Engine di server (skill), bukan di frontend. Adapter hanya fetch ke /api/simoge/*
// dan translate filter bisnis → template+params. Tidak ada SQL di sini.

const TOKEN = () => document.querySelector('meta[name="ana-token"]')?.content || '';

function headers() {
  return { 'X-Ana-Token': TOKEN(), 'Content-Type': 'application/json' };
}

// Mapping business + kategori → template yang punya polygon (untuk peta)
export function resolveTemplate(state) {
  const f = state.filters || {};
  const tahun = parseInt(f.tahun) || new Date().getFullYear();
  const bulan = Math.max(1, Math.min(12, parseInt(f.bulan) || new Date().getMonth() + 1));
  // 0 = bulan penuh (P1+P2) — dipakai ANNA untuk "bulan 5" tanpa menyebut periode
  const _p = parseInt(f.periode);
  const periode = (_p === 0 || _p === 1 || _p === 2) ? _p : 1;
  const limit = 1000;
  const base = { tahun, bulan, periode, limit };
  // Viewport P1: bounds/zoom/page_size dari _viewportExtra via collectState.
  // bounds = [w,s,e,n] (array) atau string "[w,s,e,n]"; zoom int; page_size clamp 50-2000.
  let _zoom = null;
  if (f.zoom !== undefined && f.zoom !== null && String(f.zoom).trim() !== '') {
    const z = parseInt(f.zoom);
    if (Number.isFinite(z)) _zoom = z;
  }
  let _bounds = null;
  if (Array.isArray(f.bounds) && f.bounds.length === 4) _bounds = f.bounds;
  else if (typeof f.bounds === 'string' && f.bounds.trim() !== '' && f.bounds.trim() !== 'null') {
    try { const b = JSON.parse(f.bounds); if (Array.isArray(b) && b.length === 4) _bounds = b; }
    catch (_) { _bounds = f.bounds; }
  }
  let _ps = 1000;
  if (f.page_size !== undefined && f.page_size !== null && String(f.page_size).trim() !== '') {
    const p = parseInt(f.page_size);
    if (Number.isFinite(p)) _ps = Math.max(50, Math.min(2000, p));
  }
  const viewport = { bounds: _bounds, zoom: _zoom, page_size: _ps };

  // wilayah diteruskan dan di-WHERE di DB (simoge_db._wilayah_where, allowlist paramised)
  const wilayah = {};
  if (f.divre) wilayah.kode_divre = f.divre;
  if (f.kph) wilayah.kode_kph = f.kph;
  if (f.bkph) wilayah.kode_bkph = f.bkph;
  if (f.rph) wilayah.kode_rph = f.rph;
  if (f.tpg) wilayah.kode_tpg = f.tpg;
  // tahap pembaharuan (1..4) — hanya relevan untuk biz=aktivitas (konsumennya
  // aktivitas_petak_map + aktivitas_recent). Jangan dimix ke template lain.
  if ((state.business || 'petak') === 'aktivitas'
      && ['1','2','3','4'].includes(String(f.pembaharuan_ke || ''))) {
    wilayah.pembaharuan_ke = String(f.pembaharuan_ke);
  }

  const biz = state.business || 'petak';
  const kat = (f.kategori || 'semua').toLowerCase();
  // filters.warna = subset warna dari ANA via spatial_set. Template yang tak
  // punya kontrol warna (idle_petak_map) perlu ini supaya panel render subset
  // yang sama, bukan seluruh petak — kalau tidak, panel menimpa hasil ANA.
  const warna = (f.warna || '').toLowerCase();

  if (biz === 'petak') {
    // P1 auto-agregat: zoom<=10 → kph_summary_map (centroid+KPI, ringan).
    // aggregated_level awal kode_bkph, server auto-escalate (bkph→kph→divre).
    if (_zoom !== null && _zoom <= 10 && !['ringkasan', 'summary'].includes(kat)) {
      return { template: 'kph_summary_map', params: { tahun, limit, ...wilayah, aggregated_level: 'kode_bkph', ...viewport } };
    }
    if (kat === 'bongkor' || kat === 'tanpa_penyadap') return { template: 'petak_bongkor_map', params: { tahun, limit, ...wilayah, ...viewport } };
    if (kat === 'multi_penyadap') return { template: 'petak_multi_penyadap_map', params: { tahun, limit, ...wilayah, ...viewport } };
    if (kat === 'idle') return { template: 'idle_petak_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, ...(warna ? { warna } : {}) } };
    // subset warna via ANA spatial_set — filter server-side di _simoge_show_on_map (params.warna),
    // bukan client post-filter. KPI/warna_counts dihitung dari subset (sinkron dengan polygon).
    if (kat === 'kurang') return { template: 'petak_efektivitas_map', params: { tahun, limit, ...wilayah, ...viewport, warna: 'kuning' } };
    if (kat === 'ringkasan' || kat === 'summary') {
      // kph_summary_map: aggregated centroid + KPI per KPH/BKPH/DIVRE
      // aggregated_level dikirim dari server via spatial_set (filters.aggregated_level, bounds, zoom)
      return { 
        template: 'kph_summary_map', 
        params: { 
          tahun, 
          limit, 
          ...wilayah, 
          aggregated_level: f.aggregated_level || 'kph',
          ...viewport,
          bounds: _bounds ?? f.bounds ?? null,
          zoom: _zoom ?? f.zoom ?? null,
        } 
      };
    }
    return { template: 'petak_efektivitas_map', params: { tahun, limit, ...wilayah, ...viewport, ...(warna ? { warna } : {}) } };
  }
  if (biz === 'produksi') {
    return { template: 'rkap_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport } };
  }
  if (biz === 'aktivitas') {
    // aktivitas_petak_map: merah=bongkor (tanpa penyadap / >2bln tanpa aktivitas), kuning=idle (cur0 prev>0), hijau=aktif
    if (kat === 'idle') return { template: 'idle_petak_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport } };
    if (kat === 'bongkor') return { template: 'aktivitas_petak_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport } };
    return { template: 'aktivitas_petak_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport } };
  }
  if (biz === 'matriks' || biz === 'matrik') {
    // matriks_map: luas_andil vs pencapaian RKAP, warna merah/oranye/kuning/hijau/emas + bongkor
    return { template: 'matriks_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport } };
  }
  return { template: 'petak_efektivitas_map', params: { tahun, limit, ...wilayah, ...viewport } };
}

// Fallback client-side wilayah filter (server sudah WHERE; ini guard bila template non-map dipakai)
export function filterByWilayah(rows, filters) {
  if (!filters) return rows;
  const keys = ['kode_divre','kode_kph','kode_bkph','kode_rph','kode_tpg'];
  const map = { kode_divre: filters.divre, kode_kph: filters.kph, kode_bkph: filters.bkph, kode_rph: filters.rph, kode_tpg: filters.tpg };
  let out = rows;
  for (const k of keys) {
    const v = String(map[k] || '').trim();
    if (!v) continue;
    out = out.filter(r => String(r[k] ?? r.properties?.[k] ?? '') === v);
  }
  return out;
}

// Satu panggilan: state → template → POST /api/simoge/show_on_map → GeoJSON → map_store
// Robust: timeout 12s, retry 1x, graceful ok:false (map tetap tampil stale, bukan blank)
export async function loadBusinessData(state, { timeoutMs = 12000, retries = 1 } = {}) {
  const { template, params } = resolveTemplate(state);
  let lastErr = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const ctrl = new AbortController();
    const tid = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const res = await fetch('/api/simoge/show_on_map', {
        method: 'POST',
        headers: headers(),
        credentials: 'same-origin',
        // drive:false → pemanggil panel: server tak menyentuh state peta, cuma
        // kembalikan GeoJSON. drive:true (default) dipakai ANA via show_on_map.
        body: JSON.stringify({ template, params, drive: false }),
        signal: ctrl.signal,
      });
      clearTimeout(tid);
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.ok) {
        // jangan retry untuk 4xx (param salah), retry hanya 5xx/network
        if (res.status >= 500 && attempt < retries) { lastErr = data.error || `HTTP ${res.status}`; continue; }
        return { ok: false, error: data.error || `HTTP ${res.status}`, template, params, retriable: res.status >= 500 };
      }
      return { ok: true, ...data, template, params, warna_counts: data.warna_counts || {} };
    } catch (e) {
      clearTimeout(tid);
      lastErr = e?.name === 'AbortError' ? `timeout ${timeoutMs}ms` : (e?.message || String(e));
      if (attempt < retries) continue;
      return { ok: false, error: lastErr, template, params, retriable: true };
    }
  }
  return { ok: false, error: lastErr || 'unknown', template, params, retriable: true };
}

// Query statistik tanpa peta (untuk metric bar / ANNA jelaskan)
export async function queryStats(template, params, { timeoutMs = 10000 } = {}) {
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch('/api/simoge/query', {
      method: 'POST',
      headers: headers(),
      credentials: 'same-origin',
      body: JSON.stringify({ template, params }),
      signal: ctrl.signal,
    });
    clearTimeout(tid);
    const data = await res.json().catch(() => ({}));
    return { ok: !!data.ok, ...data };
  } catch (e) {
    clearTimeout(tid);
    return { ok: false, error: e?.name === 'AbortError' ? `timeout ${timeoutMs}ms` : (e?.message || String(e)) };
  }
}

// Distinct wilayah dengan label manusia (wilayah_labels: DIVRE/KPH/BKPH/RPH/TPG + nama)
// Return {tahun, divre:[{value,label}], kph:[...], bkph:[...], rph:[...], tpg:[...]}
// Each level includes parent_code for cascade filtering
export async function fetchWilayahOptions(tahun) {
  // Sumber: 'api' (segar) | 'cache' (API gagal, tersimpan 24 jam per user) |
  // 'fallback' (bawan kode, TERBATAS — tampilkan status di panel).
  // Kontrak: { data: {...levels}, source }. Pemanggil JANGAN pakai data
  // tanpa cek source untuk status.
  const pack = (data, source) => ({ data, source });
  const defaults = {
    tahun: [2026, 2025],
    divre: [{value:'2', label:'2 — JAWA TIMUR'}],
    kph: [{value:'31211', label:'31211 — BANYUWANGI BARAT', kode_divre: '2'}],
    bkph: ['3121101','3121102','3121103','3121104','3121105'].map(v=>({value:v,label:v, kode_kph: '31211'})),
    rph: ['312110101','312110102','312110201','312110202','312110301','312110302','312110401','312110402','312110403','312110501','312110502'].map(v=>({value:v,label:v, kode_bkph: v.slice(0,8)})),
    tpg: ['31211050101','31211050201','31211040101','31211040106','31211040107','31211040302','31211040301'].map(v=>({value:v,label:v, kode_rph: v.slice(0,10), kode_bkph: v.slice(0,8)})),
  };
  try {
    const res = await fetch('/api/simoge/query', {
      method: 'POST', headers: headers(),
      credentials: 'same-origin',
      body: JSON.stringify({ template: 'wilayah_labels', params: {} }),
    });
    const data = await res.json();
    const r0 = data.rows?.[0];
    if (data.ok && r0) {
      // Peta nama→kode untuk resolusi parent (server kirim NAMA parent, bukan kode:
      // kph.divre, bkph.kph, rph.bkph, tpg.RPH/BKPH). Cascade butuh KODE.
      const _byName = (arr, nk, vk) => {
        const m = {};
        for (const o of (arr || [])) {
          const nm = String(o?.[nk] || '').trim().toUpperCase();
          if (nm && o?.[vk] != null) m[nm] = String(o[vk]);
        }
        return m;
      };
      const _divByName = _byName(r0.divre, 'divre', 'kode_divre');
      const _resDiv = (nm) => _divByName[String(nm || '').trim().toUpperCase()] || '';
      if (Array.isArray(r0.divre) && r0.divre.length) {
        defaults.divre = r0.divre.map(o => ({ value: String(o.kode_divre), label: String(o.kode_divre) + ' — ' + (o.divre||'') }));
      }
      let _kphByName = {};
      if (Array.isArray(r0.kph) && r0.kph.length) {
        defaults.kph = r0.kph.map(o => ({ value: String(o.kode_kph), label: String(o.kode_kph) + ' — ' + (o.kph||''), kode_divre: _resDiv(o.divre) }));
        _kphByName = _byName(defaults.kph.map((k, i) => ({ nm: r0.kph[i]?.kph, kode_kph: k.value })), 'nm', 'kode_kph');
      }
      const _resKph = (nm) => _kphByName[String(nm || '').trim().toUpperCase()] || '';
      let _bkphByName = {};
      if (Array.isArray(r0.bkph) && r0.bkph.length) {
        defaults.bkph = r0.bkph.map(o => ({ value: String(o.kode_bkph), label: String(o.kode_bkph) + ' — ' + (o.bkph||''), kode_kph: _resKph(o.kph) }));
        _bkphByName = _byName(defaults.bkph.map((k, i) => ({ nm: r0.bkph[i]?.bkph, kode_bkph: k.value })), 'nm', 'kode_bkph');
      }
      const _resBkph = (nm) => _bkphByName[String(nm || '').trim().toUpperCase()] || '';
      let _rphByName = {};
      if (Array.isArray(r0.rph) && r0.rph.length) {
        defaults.rph = r0.rph.map(o => ({ value: String(o.kode_rph), label: String(o.kode_rph) + ' — ' + (o.rph||''), kode_bkph: _resBkph(o.bkph) }));
        _rphByName = _byName(defaults.rph.map((k, i) => ({ nm: r0.rph[i]?.rph, kode_rph: k.value })), 'nm', 'kode_rph');
      }
      const _resRph = (nm) => _rphByName[String(nm || '').trim().toUpperCase()] || '';
      // Peta kode→kode dari prefix (fallback typo nama di DB, mis. TPG.RPH='SOKO'
      // padahal RPH='SUKO' untuk kode 312110101): prefix 9 digit = kode_rph,
      // prefix 7 digit = kode_bkph — panjang hirarki baku kode wilayah.
      const _codes = { bkph: new Set(), rph: new Set() };
      try {
        for (const k of (defaults.bkph || [])) _codes.bkph.add(String(k.value));
        for (const k of (defaults.rph || [])) _codes.rph.add(String(k.value));
      } catch (_) {}
      const _byPrefix = (kode, len, set) => {
        const p = String(kode || '').slice(0, len);
        return (p && set.has(p)) ? p : '';
      };
      if (Array.isArray(r0.tpg) && r0.tpg.length) {
        defaults.tpg = r0.tpg
          .filter(o => String(o.kode_tpg||'').trim() !== '')
          .slice(0, 500)
          .map(o => ({ value: String(o.kode_tpg), label: String(o.kode_tpg) + ' — ' + (o.nama_tpg||o.alias||'') + (o.alias?' ('+o.alias+')':'' ), kode_rph: (_resRph(o.RPH || o.rph) || _byPrefix(o.kode_tpg, 9, _codes.rph)), kode_bkph: (_resBkph(o.BKPH || o.bkph) || _byPrefix(o.kode_tpg, 7, _codes.bkph)) }));
      }
      // Bentuk minimal: divre+kph+bkph hidup dari API, atau seluruh respons
      // dianggap gagal (jangan timpa cache bagus dengan gabungan sebagian).
      const _live = ['divre', 'kph', 'bkph'].every(k => Array.isArray(r0[k]) && r0[k].length);
      if (!_live) throw new Error('wilayah_labels tak lengkap');
      _wilCacheSave(defaults);
      return pack(defaults, 'api');
    }
    throw new Error('wilayah_labels kosong');
  } catch (e) {
    try { console.warn('[wilayah] API gagal, fallback:', (e && e.message) || e); } catch (_) {}
    const cached = _wilCacheLoad();
    if (cached) return pack(cached, 'cache');
    return pack(defaults, 'fallback');
  }
}

// Cache opsi terakhir yang bagus: per user (scope beda!), TTL 24 jam.
// Tanpa ini, tiap gagal API = fallback bawaan yang kadaluarsa (RPH hilang).
function _wilUid() {
  try {
    const u = window._authUser || {};
    return String(u.id || u.email || 'anon');
  } catch (_) { return 'anon'; }
}
function _wilCacheLoad() {
  try {
    const raw = localStorage.getItem('ana_wilayah_cache_v1');
    if (!raw) return null;
    const j = JSON.parse(raw);
    if (!j || j.uid !== _wilUid() || !j.data) return null;
    if (Date.now() - (j.at || 0) > 24 * 3600 * 1000) return null;
    return j.data;
  } catch (_) { return null; }
}
function _wilCacheSave(data) {
  try { localStorage.setItem('ana_wilayah_cache_v1', JSON.stringify({ uid: _wilUid(), at: Date.now(), data })); } catch (_) {}
}

// Pin-point aktivitas (titik GPS tiap kejadian sadap): lat/lng/alt/pembaharuan_ke/foto/cuaca/akses_lokasi
// Dipanggil map.js saat biz=aktivitas setelah polygon load. Limit adaptif 600-1200 (ponytail: markerCluster bila >800).
export async function fetchAktivitasPoints(state, { limit, timeoutMs = 10000 } = {}) {
  const f = state.filters || {};
  const tahun = parseInt(f.tahun) || new Date().getFullYear();
  const bulan = Math.max(1, Math.min(12, parseInt(f.bulan) || new Date().getMonth() + 1));
  // 0 = bulan penuh (P1+P2) — dipakai ANNA untuk "bulan 5" tanpa menyebut periode
  const _p = parseInt(f.periode);
  const periode = (_p === 0 || _p === 1 || _p === 2) ? _p : 1;
  const wilayah = {};
  if (f.divre) wilayah.kode_divre = f.divre;
  if (f.kph) wilayah.kode_kph = f.kph;
  if (f.bkph) wilayah.kode_bkph = f.bkph;
  if (f.rph) wilayah.kode_rph = f.rph;
  if (f.tpg) wilayah.kode_tpg = f.tpg;
  // filter tersembunyi: ANNA bisa minta 1 tahap pembaharuan saja (1..4)
  if (['1','2','3','4'].includes(String(f.pembaharuan_ke || ''))) {
    wilayah.pembaharuan_ke = String(f.pembaharuan_ke);
  }
  // adaptif: jika caller tidak tentukan limit, pakai 1000 (cukup untuk 517 petak aktif tanpa truncate 300)
  // map.js boleh override dengan limit = min(1200, max(600, polyFeatures*2))
  const effLimit = Number.isFinite(limit) ? Math.max(50, Math.min(2000, parseInt(limit))) : 1000;
  const params = { limit: effLimit, tahun, bulan, periode, ...wilayah };
  return queryStats('aktivitas_recent', params, { timeoutMs });
}

// Helper: resolve kode -> label (untuk chips/insight)
export function labelWilayah(kode, opts, fallback) {
  if (!kode) return '';
  const s = String(kode);
  const arr = Array.isArray(opts) ? opts : [];
  const hit = arr.find(o => String(o.value||o) === s);
  if (hit) return hit.label || s;
  return fallback ? fallback + ' ' + s : s;
}
