---
title: Arsitektur Skala Peta
created: 2026-10-04
updated: 2026-10-04
type: concept
tags: [spasial, peta, polygon, dashboard, kph, divre, petak, integritas-data]
sources: [simoge_db.py, server.py _serve_pmtiles, ui/src/map.js, scripts/build_pmtiles.py]
---

# Arsitektur Skala Peta — Tile vs GeoJSON, Clustering, Pagination, Cache

Mengapa 1 KPH (809 petak) lancar tapi 20+ KPH per DIVRE (16.000+ petak)
macet, dan bagaimana arsitekturnya menanganinya. Keputusan query di
[[skala-multi-divre]]; inventaris panel di [[panel-spatial-map]].

## 1. Tiga jalur render (hybrid tier)

| Jalur | Kapan | Payload | Query DB |
|---|---|---|---|
| PMTiles statis (`/api/tiles/petak.pmtiles`, z8–15, GZIP ~855 KB) | business petak, zoom ≤ 11 | tile MVT per viewport (~10–17 KB) | tidak ada — file statis + `?z/x/y` extract |
| GeoJSON viewport (template `_TEMPLATE_SPATIAL`) | zoom ≥ 12 (detail + analisa + pin) | ≤ `page_size` polygon (clamp 50–2000) | ya — filter `bounds` via spatial index |
| Centroid agregat (`kph_summary_map`) | zoom < 11 / "seluruh DIVRE" | 1 baris per wilayah (< 500 KB) | ya — GROUP BY allowlist + auto-escalate level |

Panel (`ui/src/map.js`) switch otomatis: `_maybeSwitchTier(zoom)` —
PMTiles ≤ 11 (polygon saja, tanpa analisa/pin), GeoJSON ≥ 12 (analisa +
pin); `_pushViewport()` debounce 600 ms kirim
bounds+zoom tiap geser. Tanpa ini: 16.000 polygon ~40 MB → browser OOM,
timeout 30 s, Leaflet freeze 3–5 detik main thread.

## 2. Spatial index (mengapa viewport cepat)

- `petak_polygon.geom` geometry + `SPATIAL INDEX idx_geom` (1003 rows).
- `_bbox_sql(bounds)`: dua tahap — `MBRContains` (pakai index, ~50 rows)
  lalu `ST_Intersects` exact. `ST_Intersects` saja = full scan (~945 rows).
- Index pendukung: `getah_petak.idx_tahun_kph (tahun_rtt, kode_kph)`,
  `petak_polygon.idx_evapot (kode_evapot)` untuk JOIN polygon.
- Aturan: selalu kirim `bounds` untuk query detail skala besar; tanpa bounds
  = full scan + LIMIT mentah (data terpotong diam-diam saat > `page_size`).

## 3. Freshness PMTiles vs live DB

PMTiles dibangun dari `tiles/petak.ndjson` via `scripts/build_pmtiles.py`
(`GET /api/tiles/rebuild`), refresh harian cron 06:00
(`scripts/refresh_petak_simple.py`). Konsekuensi: tile bisa basi ≤ 24 jam
sementara GeoJSON selalu live. Bila operator tanya "data hari ini" → jawab
dari template GeoJSON + sebut tanggal (`provenance`), jangan dari tile.
Setelah rebuild, `verify_pmtiles.py` pastikan header center/bounds/zoom
sinkron dengan `HOME`/`CENTER` panel (meleset 2,5 km pernah bikin Z12 kosong).

## 4. Pagination jujur + cache

- `page_size` clamp 50–2000, default 1000. `row_count` ≈ `page_size` =
  sinyal hasil terpotong → katakan parsial, tawarkan agregat atau persempit
  bounds (lihat fallback di [[skala-multi-divre]]).
- Streaming/progressive-load dan cursor `load_more` **belum ada**
  (`map_store.py` queue tak support) — jangan janjikan "scroll untuk
  lanjutkan".
- `_SHOW_CACHE` server TTL 3 detik, key mencakup full params (bounds ikut)
  → tiap viewport baru = cache miss. Fungsinya anti reload-loop panel,
  bukan cache data. Klaim "sudah di-cache" untuk viewport lama = salah.

## 5. Batas yang masih berlaku

Tanpa migrasi PostGIS (keputusan: tetap MariaDB). Clustering centroid
hanya via `kph_summary_map` — tidak ada cluster engine generik.
`bounds` string `"[w,s,e,n]"` juga diterima (via `spatial_set` str()).
Detail panel: [[panel-spatial-map]]; alur nalar: [[penalaran-spasial]];
batas engine: [[batas-data-engine]].

## 6. Operasional PMTiles (cron + rebuild + status)

PMTiles snapshot diregenerasi harian setelah refresh DB. Rantai penuh
di `scripts/rebuild_tiles_daily.sh`: `export_petak.py` (NDJSON dari DB)
→ `build_pmtiles.py` (z8–15, GZIP). Bila export DB gagal, build dari
NDJSON kemarin (tile basi > 404).

- Cron dikelola dari UI: tombol ⚙ `#spatialTilesBtn` → modal
  `#spatialTilesModal` → `POST /api/tiles/cron` action
  `status|enable|disable` + input jadwal (default `10 6 * * *` = 06:10
  WIB, 10 menit setelah `refresh_petak_simple.py` 06:00). Baris cron
  ditandai `# ana-pmtiles-daily` — enable/disable hanya sentuh baris
  marker, cron lain milik user tak diganggu.
- Rebuild manual dari modal: `GET /api/tiles/rebuild` (1–2 menit).
- Status read-only modal: `GET /api/tiles/status` → PMTiles bytes/mtime,
  NDJSON baris, baris cron, log tail `logs/refresh_petak.log`.
- Token via `meta[name=ana-token]` + header `X-Ana-Token` (POST wajib
  `Origin` cocok port).
- Verifikasi: disable harus hapus hanya baris marker (total non-marker
  tetap); enable tulis ulang 1 baris marker.
