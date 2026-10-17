---
title: Skala Multi-DIVRE
created: 2026-10-04
updated: 2026-10-04
type: query
tags: [spasial, peta, divre, kph, petak, dashboard, konteks-percakapan, batasan]
sources: [simoge_db.py, ana_simoge_tool.py, server.py _TEMPLATE_SPATIAL, ui/src/map.js]
---

# Skala Multi-DIVRE — Template Selection Tree + Viewport + Fallback

Aturan pemilihan template saat scope membesar (1 KPH → 20+ KPH per DIVRE).
Mapping intent dasar tetap di [[intent-ke-template-peta]]; halaman ini khusus
keputusan skala. Arsitektur di baliknya: [[arsitektur-skala-peta]].
Batas umum: ANNA tak boleh SQL langsung ([[batas-data-engine]]), angka hanya
dari template di [[tool-bisnis-anna]].

## 1. Decision tree

```
intent "tampilkan di peta ..."
│
├─ sebut "seluruh DIVRE" / "overview" / "ringkasan" / zoom < 11
│  → kph_summary_map (centroid + KPI per wilayah, payload < 500 KB)
│     aggregated_level: kode_divre (1 baris/DIVRE) | kode_kph | kode_bkph
│
├─ sebut BKPH/RPH/TPG spesifik ATAU zoom ≥ 12 (detail petak + analisa + pin)
│  → petak_efektivitas_map + tahun + kode_* + bounds viewport
│     (polygon per petak, LIMIT via page_size, max 2000)
│
├─ zoom ≤ 11, business petak, tanpa filter BKPH
│  → PMTiles overview otomatis (panel, bukan show_on_map):
│     panel aktifkan /api/tiles/petak.pmtiles, sembunyikan layer GeoJSON
│
└─ aktivitas / produksi / RKAP / matriks
   → template masing-masing (aktivitas_petak_map, rkap_map, matriks_map);
      JANGAN paksa ke kph_summary_map (skema kolom beda)
```

Contoh gagal yang dihindari: `show_on_map(petak_efektivitas_map,
tahun=2026, kode_divre=2)` tanpa bounds → 16.000 polygon ~40 MB → panel
freeze. Yang benar: `kph_summary_map(tahun=2026, kode_divre=2,
aggregated_level=kode_kph)` → 5 baris KPH + centroid → instan; user zoom in
→ panel kirim viewport query detail.

## 2. Parameter viewport (wajib untuk query detail skala besar)

| Param | Format | Aturan |
|---|---|---|
| `bounds` | `[west, south, east, north]` float derajat | invalid/kosong = tanpa filter; lintang −90..90, bujur −180..180, west<east, south<north |
| `zoom` | int level zoom Leaflet | `< 11` → server auto-naikkan `aggregated_level` satu tingkat (bkph→kph→divre) |
| `page_size` | int | clamp 50–2000; default = `limit` template (1000) |
| `aggregated_level` | allowlist `kode_divre \| kode_kph \| kode_bkph` | nilai lain → error `bad level`; GROUP BY dari allowlist saja (anti-injeksi) |

Alur panel: `_readVp()` baca `map.getBounds()` + `getZoom()` → `_pushViewport()`
debounce 600 ms → `_viewportExtra` → `collectState()` → `scheduleReload()` →
server filter via spatial index. Batas filter wilayah juga diteruskan
(`_SPATIAL_FILTER_KEYS`: bulan, tahun, periode, divre, kph, bkph, rph, tpg,
pembaharuan_ke, aggregated_level, bounds, zoom, page_size).

## 3. Yang BELUM didukung — jangan karang

- `kode_divre` / `kode_kph` array (multi-value): `_wilayah_where` hanya terima
  **satu nilai digit** per kolom; `kode_divre=[1,2]` diabaikan diam-diam.
- `exclude_kph` / pola negasi: tidak ada; jangan kirim.
- `aggregated=true` flag generik: tidak ada; agregasi hanya via template
  `kph_summary_map` + `aggregated_level`.
- Viewport untuk template non-spasial: hanya template `_TEMPLATE_SPATIAL`
  (petak_*, aktivitas_*, rkap_map, matriks_map, kph_summary_map) yang diteruskan
  ke panel; template lain = jawaban teks saja.

## 4. Fallback chain (timeout / payload besar)

1. Timeout atau `row_count` ≈ `page_size` (tanda terpotong) → katakan parsial,
   tawarkan `kph_summary_map` agregat.
2. Masih berat → persempit: tambah `bounds` viewport saat ini, atau turunkan
   `page_size`, atau naikkan `aggregated_level` (bkph→kph→divre).
3. Retry dengan zoom out (zoom ≤ 11 = tier PMTiles statis, tanpa query DB).
4. Jangan retry buta query yang sama — ubah dulu level agregat atau bounds.

Cache server `_SHOW_CACHE` TTL 3 detik, key = `[template, warna_only,
drive_panel, params]` — params termasuk bounds, jadi tiap geser viewport =
key baru (cache hanya anti reload-loop, bukan cache data). Lihat
[[panel-spatial-map]] untuk guard anti-loop dan [[penalaran-spasial]] untuk
alur KPI ↓ Wilayah ↓ Petak ↓ Lokasi.
