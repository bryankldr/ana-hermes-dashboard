// ui/src/businessAdapter.js — facade antara SpatialMapState → Business Data Engine
// DATABASE → Engine (simoge-business) → Processed Data → SpatialMapState → Map → ANA
// Engine di server (skill), bukan di frontend. Adapter hanya fetch ke /api/simoge/*
// dan translate filter bisnis → template+params. Tidak ada SQL di sini.

import { isLowEndDevice, isMobile } from './core/device.js';

const TOKEN = () => '' || '';

function headers() {
  return { 'X-Ana-Token': TOKEN(), 'Content-Type': 'application/json' };
}

// Device-based limit untuk skalabilitas: low-end=2000, mobile=5000, desktop=10000
function getDeviceLimit() {
  if (isLowEndDevice()) return 2000;
  if (isMobile()) return 5000;
  return 10000;
}

// Device-based page_size clamp untuk viewport filtering
function getDevicePageSize(userValue) {
  const p = parseInt(userValue);
  if (!Number.isFinite(p)) return getDeviceLimit();
  const max = getDeviceLimit();
  return Math.max(50, Math.min(max, p));
}

// Mapping business + kategori → template yang punya polygon (untuk peta)
export function resolveTemplate(state) {
  const f = state.filters || {};
  const tahun = parseInt(f.tahun) || new Date().getFullYear();
  const bulan = Math.max(1, Math.min(12, parseInt(f.bulan) || new Date().getMonth() + 1));
  // 0 = bulan penuh (P1+P2) — dipakai ANNA untuk "bulan 5" tanpa menyebut periode
  const _p = parseInt(f.periode);
  const periode = (_p === 0 || _p === 1 || _p === 2) ? _p : 1;
  const limit = getDeviceLimit();
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
  let _ps = getDevicePageSize(f.page_size);
  const viewport = { bounds: _bounds, zoom: _zoom, page_size: _ps };

  // wilayah diteruskan dan di-WHERE di DB (simoge_db._wilayah_where, allowlist paramised)
  const wilayah = {};
  if (f.divre) wilayah.kode_divre = f.divre;
  if (f.kph) wilayah.kode_kph = f.kph;
  if (f.bkph) wilayah.kode_bkph = f.bkph;
  if (f.rph) wilayah.kode_rph = f.rph;
  if (f.tpg) wilayah.kode_tpg = f.tpg;
  // tahap pembaharuan (1..4) — relevan untuk biz=aktivitas/keaktifan
  // (konsumennya aktivitas_petak_map/keaktifan_petak_map + aktivitas_recent).
  // Jangan dimix ke template lain.
  if ((state.business === 'aktivitas' || state.business === 'keaktifan' || (state.business || 'petak') === 'aktivitas')
      && ['1','2','3','4'].includes(String(f.pembaharuan_ke || ''))) {
    wilayah.pembaharuan_ke = String(f.pembaharuan_ke);
  }
  // Jenis aktivitas — HANYA biz=aktivitas (sebaran kerja). Keaktifan
  // status struktural, sengaja tak kenal filter jenis.
  // Sampai dengan Ya/Tidak — berlaku aktivitas/keaktifan/produksi/matriks.
  if (state.business === 'aktivitas'
      && ['quare','semprot_cas','kerok','naik_batok','budaya_bersih','pulung'].includes(String(f.jenis_aktivitas || '').toLowerCase())) {
    wilayah.jenis_aktivitas = String(f.jenis_aktivitas).toLowerCase();
  }
  if (['ya','tidak'].includes(String(f.sampai_dengan || '').toLowerCase())) {
    wilayah.sampai_dengan = String(f.sampai_dengan).toLowerCase();
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
    if (kat === 'terpenuhi') return { template: 'petak_efektivitas_map', params: { tahun, limit, ...wilayah, ...viewport, warna: 'hijau' } };
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
    // Kategori = pita pencapaian (kontigu, tanpa celah): merah ≤25, oranye
    // (25,50], kuning (50,75], hijau (75,100], emas >100. Kunci data tetap
    // 'emas' (tampil biru di peta). Pilihan eksplisit menang atas subset ANA.
    const _pw = { sangat_buruk: 'merah', buruk: 'oranye', kurang: 'kuning', baik: 'hijau', sangat_baik: 'emas' }[kat] || '';
    return { template: 'rkap_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, ...((_pw || warna) ? { warna: _pw || warna } : {}) } };
  }
  if (biz === 'keaktifan') {
    // keaktifan_petak_map: status struktural aktif/idle/bongkor.
    // SENGAJA tanpa filter jenis — wilayah sudah dibersihkan dari
    // jenis_aktivitas di atas (backend juga pop defensif).
    if (kat === 'idle') return { template: 'idle_petak_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, ...(warna ? { warna } : {}) } };
    if (kat === 'bongkor') return { template: 'keaktifan_petak_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, warna: 'merah' } };
    if (kat === 'aktif') return { template: 'keaktifan_petak_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, warna: 'hijau' } };
    return { template: 'keaktifan_petak_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, ...(warna ? { warna } : {}) } };
  }
  if (biz === 'aktivitas') {
    // aktivitas_kerja_map: sebaran kerja sadap per jenis + pin poin.
    // Hormati jenis_aktivitas + sampai_dengan + pembaharuan_ke.
    if (kat === 'idle') return { template: 'idle_petak_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, ...(warna ? { warna } : {}) } };
    if (kat === 'bongkor') return { template: 'aktivitas_kerja_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, warna: 'merah' } };
    if (kat === 'aktif') return { template: 'aktivitas_kerja_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, warna: 'hijau' } };
    return { template: 'aktivitas_kerja_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, ...(warna ? { warna } : {}) } };
  }
  if (biz === 'matriks' || biz === 'matrik') {
    // matriks_map: luas_andil vs pencapaian RKAP, warna merah/oranye/kuning/hijau/emas + bongkor
    const _mw = { bongkor: 'merah', kurang_cap50: 'oranye', kurang: 'kuning', terpenuhi: 'hijau', sangat_baik: 'emas' }[kat] || '';
    return { template: 'matriks_map', params: { tahun, bulan, periode, limit, ...wilayah, ...viewport, ...((_mw || warna) ? { warna: _mw || warna } : {}) } };
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

// Distinct wilayah murni dari DB via template wilayah_labels (kode + nama +
// rantai kode parent). Kontrak: { data: {tahun,divre,kph,bkph,rph,tpg}, source }.
// - value = KODE (string), label = NAMA saja (bukan kode).
// - parent (kode_divre/kode_kph/kode_bkph/kode_rph) dibaca langsung dari kolom
//   kode server — tanpa tebak nama/slice. Fallback pencocokan nama hanya bila
//   kolom kode parent kosong (kompat data lama).
// - Gagal API + tanpa cache → level kosong (jujur, bukan daftar hardcode basi).
// Each level includes parent_code for cascade filtering
export async function fetchWilayahOptions(tahun) {
  // Sumber: 'api' (segar) | 'cache' (API gagal, tersimpan 24 jam per user) |
  // 'fallback' (kosong — server tak terjangkau & tanpa cache; panel tampilkan status).
  // Kontrak: { data: {...levels}, source }. Pemanggil JANGAN pakai data
  // tanpa cek source untuk status.
  const pack = (data, source) => ({ data, source });
  const _str = (v) => (v == null ? '' : String(v).trim());
  const defaults = {
    tahun: [2026, 2025],
    divre: [], kph: [], bkph: [], rph: [], tpg: [],
  };
  try {
    // Timeout eksplisit: tanpa ini fetch gantung = _populateDropdowns tak
    // pernah jalan = menu wilayah kosong + persistensi mati selamanya.
    let _sig = undefined;
    try { if (typeof AbortSignal !== 'undefined' && AbortSignal.timeout) _sig = AbortSignal.timeout(15000); } catch (_) {}
    const res = await fetch('/api/simoge/query', {
      method: 'POST', headers: headers(),
      credentials: 'same-origin',
      body: JSON.stringify({ template: 'wilayah_labels', params: {} }),
      ...(_sig ? { signal: _sig } : {}),
    });
    const data = await res.json();
    const r0 = data.rows?.[0];
    if (data.ok && r0) {
      // Parent dibaca dari kolom KODE (sumber kebenaran). Peta nama→kode hanya
      // fallback bila kolom kode parent kosong (data lama / typo nama diabaikan
      // bila kode ada — mis. TPG.RPH='SOKO' vs RPH='SUKO').
      const _byName = (arr, nk, vk) => {
        const m = {};
        for (const o of (arr || [])) {
          const nm = _str(o?.[nk]).toUpperCase();
          if (nm && o?.[vk] != null && _str(o[vk]) !== '') m[nm] = _str(o[vk]);
        }
        return m;
      };
      const _divByName = _byName(r0.divre, 'divre', 'kode_divre');
      if (Array.isArray(r0.divre) && r0.divre.length) {
        defaults.divre = r0.divre
          .filter(o => _str(o.kode_divre) !== '')
          .map(o => ({ value: _str(o.kode_divre), label: _str(o.divre) || _str(o.kode_divre) }));
      }
      const _kphByName = _byName(r0.kph, 'kph', 'kode_kph');
      if (Array.isArray(r0.kph) && r0.kph.length) {
        defaults.kph = r0.kph
          .filter(o => _str(o.kode_kph) !== '')
          .map(o => ({ value: _str(o.kode_kph), label: _str(o.kph) || _str(o.kode_kph), kode_divre: _str(o.kode_divre) || (_divByName[_str(o.divre).toUpperCase()] || '') }));
      }
      const _bkphByName = _byName(r0.bkph, 'bkph', 'kode_bkph');
      if (Array.isArray(r0.bkph) && r0.bkph.length) {
        defaults.bkph = r0.bkph
          .filter(o => _str(o.kode_bkph) !== '')
          .map(o => ({ value: _str(o.kode_bkph), label: _str(o.bkph) || _str(o.kode_bkph), kode_kph: _str(o.kode_kph) || (_kphByName[_str(o.kph).toUpperCase()] || ''), kode_divre: _str(o.kode_divre) || '' }));
      }
      const _rphByName = _byName(r0.rph, 'rph', 'kode_rph');
      if (Array.isArray(r0.rph) && r0.rph.length) {
        defaults.rph = r0.rph
          .filter(o => _str(o.kode_rph) !== '')
          .map(o => ({ value: _str(o.kode_rph), label: _str(o.rph) || _str(o.kode_rph), kode_bkph: _str(o.kode_bkph) || (_bkphByName[_str(o.bkph).toUpperCase()] || ''), kode_kph: _str(o.kode_kph) || '', kode_divre: _str(o.kode_divre) || '' }));
      }
      if (Array.isArray(r0.tpg) && r0.tpg.length) {
        defaults.tpg = r0.tpg
          .filter(o => _str(o.kode_tpg) !== '')
          .slice(0, 500)
          .map(o => {
            const nm = _str(o.nama_tpg) || _str(o.alias) || _str(o.kode_tpg);
            const al = _str(o.alias);
            return { value: _str(o.kode_tpg), label: al && al.toUpperCase() !== nm.toUpperCase() ? (nm + ' (' + al + ')') : nm, kode_rph: _str(o.kode_rph) || (_rphByName[_str(o.RPH || o.rph).toUpperCase()] || ''), kode_bkph: _str(o.kode_bkph) || (_bkphByName[_str(o.BKPH || o.bkph).toUpperCase()] || ''), kode_kph: _str(o.kode_kph) || '', kode_divre: _str(o.kode_divre) || '' };
          });
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
  // Kategori petak → filter pin (selaras polygon): aktif = pin periode ini;
  // idle = pin PERIODE LALU pada petak kini-idle (bukti); bongkor = kosong
  // (definisi: tanpa aktivitas periode berjalan). Selain itu = semua pin.
  const _kk = String(f.kategori || '').toLowerCase();
  if (['aktif','idle','bongkor'].includes(_kk)) wilayah.kategori = _kk;
  if (['quare','semprot_cas','kerok','naik_batok','budaya_bersih','pulung'].includes(String(f.jenis_aktivitas || '').toLowerCase())) {
    wilayah.jenis_aktivitas = String(f.jenis_aktivitas).toLowerCase();
  }
  if (['ya','tidak'].includes(String(f.sampai_dengan || '').toLowerCase())) {
    wilayah.sampai_dengan = String(f.sampai_dengan).toLowerCase();
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
