// ui/src/spatialMapState.js — isolated BI state for SPATIAL MAP (Business Map Workspace)
// HUD utama = dashboard dev (coding). Panel ini = dashboard BI (mode-aware via MODE_CHANGED).
// Tidak menyentuh state global core/bus lainnya. Satu sumber untuk business+filters
// yang hanya mempengaruhi SPATIAL MAP. Emit bus SPATIAL_MAP_CHANGED agar map.js
// dan adapter bisa subscribe tanpa coupling ke panel lain.

import { bus } from './core/bus.js';

export const BUSINESS_OPTIONS = [
  { value: 'petak',     label: 'Evaluasi Petak',     desc: 'coverage penyadap · luas andil vs luas baku' },
  { value: 'aktivitas', label: 'Evaluasi Aktivitas', desc: 'AKTIV / IDLE / BONGKOR · P1/P2' },
  { value: 'produksi',  label: 'Evaluasi Produksi',  desc: 'target RO/NPS vs aktual · RO/NPS' },
  { value: 'matriks',   label: 'Evaluasi Matriks',   desc: 'luas · pohon · penyadap · aktivitas · produksi' },
];

export const PETAK_LAYER_OPTIONS = [
  { value: 'semua',        label: 'Semua Petak' },
  { value: 'bongkor',      label: 'Bongkor' },
  { value: 'idle',         label: 'Idle' },
  { value: 'tanpa_penyadap', label: 'Tanpa Penyadap' },
  { value: 'multi_penyadap', label: 'Multi Penyadap' },
];

// Menu kategori per bisnis (cascade: bisnis → kategori). Slug stabil dipakai
// resolveTemplate → filter warna server-side. Slug lama (idle/tanpa_penyadap/
// multi_penyadap/ringkasan) tetap diterima adapter (kompat perintah ANA).
export const KATEGORI_OPTIONS = {
  petak: [
    { value: 'semua',     label: 'Semua' },
    { value: 'bongkor',   label: 'Bongkor' },
    { value: 'kurang',    label: 'Kurang' },
    { value: 'terpenuhi', label: 'Terpenuhi' },
  ],
  aktivitas: [
    { value: 'semua',   label: 'Semua' },
    { value: 'bongkor', label: 'Bongkor' },
    { value: 'idle',    label: 'Idle' },
    { value: 'aktif',   label: 'Aktif' },
  ],
  produksi: [
    { value: 'semua',       label: 'Semua' },
    { value: 'sangat_buruk', label: 'Sangat buruk (0-25%)' },
    { value: 'buruk',       label: 'Buruk (26-50%)' },
    { value: 'kurang',      label: 'Kurang (51-75%)' },
    { value: 'baik',        label: 'Baik (76-100%)' },
    { value: 'sangat_baik', label: 'Sangat baik (>100%)' },
  ],
  matriks: [
    { value: 'semua',        label: 'Semua' },
    { value: 'bongkor',      label: 'Bongkor' },
    { value: 'kurang_cap50', label: 'Kurang & cap<50%' },
    { value: 'kurang',       label: 'Kurang' },
    { value: 'terpenuhi',    label: 'Terpenuhi' },
    { value: 'sangat_baik',  label: 'Sangat baik' },
  ],
};

export function katOptionsFor(business) {
  return KATEGORI_OPTIONS[business] || KATEGORI_OPTIONS.petak;
}

const now = new Date();
const CUR_TAHUN = now.getFullYear();
const CUR_BULAN = now.getMonth() + 1;
const CUR_PERIODE = now.getDate() <= 15 ? 1 : 2;

export function createSpatialMapState(overrides = {}) {
  return {
    business: overrides.business || 'petak',
    // filter khusus SPATIAL MAP — scoped, bukan global
    filters: {
      bulan: overrides.bulan ?? CUR_BULAN,
      tahun: overrides.tahun ?? CUR_TAHUN,
      periode: overrides.periode ?? CUR_PERIODE,
      divre: overrides.divre ?? '',
      kph: overrides.kph ?? '',
      bkph: overrides.bkph ?? '',
      rph: overrides.rph ?? '',
      tpg: overrides.tpg ?? '',
      // kategori layer khusus Evaluasi Petak
      kategori: overrides.kategori ?? 'semua',
      ...overrides.filters,
    },
    // dataset terakhir dari Business Data Engine
    dataset: {
      template: null,
      params: null,
      rows: [],
      row_count: 0,
      features: 0,
      at: 0,
    },
    // layer visibility per kategori (untuk filter polygon visible)
    layers: {},
    selection: null,
    metrics: {
      shown: 0,
      total: 0,
      luas: null,
      warna_counts: {},
      at: 0,
    },
    _rev: 0,
  };
}

// Single store instance — isolated, tidak dipersist ke layout.json / state.json
let _store = createSpatialMapState();
let _subs = new Set();

export function getSpatialState() {
  return JSON.parse(JSON.stringify(_store));
}

export function setBusiness(business) {
  if (!BUSINESS_OPTIONS.some(o => o.value === business) && business !== 'matrik') return _store;
  _store.business = business === 'matrik' ? 'matriks' : business;
  _store._rev++;
  _emit();
  return getSpatialState();
}

export function setFilters(patch) {
  if (!patch || typeof patch !== 'object') return getSpatialState();
  const allowed = ['bulan','tahun','periode','divre','kph','bkph','rph','tpg','kategori','pembaharuan_ke','sampai_dengan','jenis_aktivitas','bounds','zoom','page_size','aggregated_level'];
  for (const k of allowed) if (patch[k] !== undefined) _store.filters[k] = patch[k];
  // clamp
  _store.filters.bulan = Math.max(1, Math.min(12, parseInt(_store.filters.bulan) || CUR_BULAN));
  _store.filters.tahun = parseInt(_store.filters.tahun) || CUR_TAHUN;
  // 0 = bulan penuh (P1+P2) — dipakai ANNA untuk "bulan 5" tanpa menyebut periode
  const p = parseInt(_store.filters.periode);
  _store.filters.periode = (p === 0 || p === 1 || p === 2) ? p : 1;
  const pk = String(_store.filters.pembaharuan_ke ?? '');
  _store.filters.pembaharuan_ke = ['1','2','3','4'].includes(pk) ? pk : '';
  const sd = String(_store.filters.sampai_dengan ?? '').toLowerCase();
  _store.filters.sampai_dengan = ['ya','tidak'].includes(sd) ? sd : '';
  const ja = String(_store.filters.jenis_aktivitas ?? '').toLowerCase();
  _store.filters.jenis_aktivitas = ['quare','semprot_cas','kerok','naik_batok','budaya_bersih','pulung'].includes(ja) ? ja : '';
  _store._rev++;
  _emit();
  return getSpatialState();
}

export function setDataset(dataset) {
  _store.dataset = { ..._store.dataset, ...dataset, at: Date.now() };
  _store.metrics.total = dataset.row_count ?? dataset.features ?? 0;
  _store.metrics.at = Date.now();
  _store._rev++;
  _emit();
  return getSpatialState();
}

export function setMetrics(metrics) {
  _store.metrics = { ..._store.metrics, ...metrics, at: Date.now() };
  _store._rev++;
  _emit();
  return getSpatialState();
}

export function setSelection(id) {
  _store.selection = id ? String(id) : null;
  _store._rev++;
  _emit();
  return getSpatialState();
}

export function resetSpatialState() {
  _store = createSpatialMapState();
  _emit();
  return getSpatialState();
}

export function subscribeSpatial(fn) {
  _subs.add(fn);
  return () => _subs.delete(fn);
}

function _emit() {
  const snap = getSpatialState();
  try { bus.emit('SPATIAL_MAP_CHANGED', snap); } catch (_) {}
  for (const fn of _subs) try { fn(snap); } catch (_) {}
  // expose for ANA reading via window (debug + /api/map/state companion)
  try { window.__spatialMapState = snap; } catch (_) {}
}
