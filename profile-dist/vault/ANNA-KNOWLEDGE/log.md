# Wiki Log

> Chronological record of all wiki actions. Append-only.
> Format: `## [YYYY-MM-DD] action | subject`
> Actions: ingest, update, query, lint, create, archive, delete

## [2026-10-02] create | Wiki initialized
- Domain: SIMOGE business intelligence (penyadapan getah pinus)
- Structure: SCHEMA.md, index.md, log.md, raw/articles/, entities/, concepts/, comparisons/, queries/
- WIKI_PATH set di profil anna .env + dashboard .env

## [2026-10-02] ingest | simoge-business-ontology.md
- Raw: raw/articles/simoge-business-ontology.md (frontmatter source/ingested/sha256 ditambah)
- Pages: 14 entities + 46 concepts + 1 comparison (semua link ≥2 wikilinks)
- Index: 61 halaman wiki terkatalog (14 entities + 46 concepts + 1 comparison) + 2 raw

## [2026-10-02] lint | wiki health-check
- Broken links: 1 diperbaiki (petak.md: `evaluasi-petaks` → [[inteligensi-spasial]])
- Orphan: 1 diperbaiki (bank-uji-semantik ← klasifikasi-pertanyaan)
- Tag taxonomy: `operasional` ditambah ke SCHEMA.md
- Hasil: broken 0, orphans 0, bad_tags 0, missing_index 0

## [2026-10-03] ingest | bi-semantic-test-suite.md
- Raw: raw/articles/bi-semantic-test-suite.md (23 section, 1177 baris)
- Pages: 22 queries (E/R/F/O/K/T/TM/C/D/RC/S/MD/EX/A/SA/DI/KD/AR/CA/BR/CH/ONT/PI/FINAL) + 4 concepts (model-inteligensi, disiplin-evidence, perilaku-terlarang-dan-penilaian, template-hasil-uji)
- Hub: bank-uji-semantik ditulis ulang sebagai hub 22 queries + 4 concepts
- Index: 87 halaman wiki (14 entities + 50 concepts + 1 comparison + 22 queries) + 2 raw
- Tag taxonomy: `uji` ditambah ke SCHEMA.md

## [2026-10-03] ingest | skema-database-kph-bwb-sandbox2.md
- Raw: raw/articles/skema-database-kph-bwb-sandbox2.md (69 tabel, counts, master wilayah, TPG, mutu, tarif, jabatan)
- Pages: entities/operator-lapangan, entities/peran-jabatan, concepts/alias-wilayah; update raw (section operator+jabatan), divre (master+alias), bkph (master+licin/glenmore), mandor (link balik)
- Tag taxonomy: `operator`, `peran` ditambah ke SCHEMA.md
- Index: 90 halaman wiki (16 entities + 51 concepts + 1 comparison + 22 queries) + 2 raw

## [2026-10-03] update | master wilayah nyata kph/rph/tpg
- Update: kph (2 KPH), rph (11 RPH + catatan SUKO/SOKO), tpg (39 operasional + 3 dummy + jarak_pgt + status)
- Index: alias-wilayah pindah ke section Concepts (urut abjad); totals dikoreksi

## [2026-10-03] ingest | medan-aktivitas + rantai penerimaan
- Pages: concepts/medan-aktivitas (kolom medan, agregasi per wilayah, rantai sadap→penerimaan→drum→perni, matriks sintesis, batas alt teks + non-1:1)
- Update: aktivitas-penyadapan (link balik); index totals
- Fix: peran-jabatan `integritas-data|uji-integritas-data` → `uji-integritas-data`; log `evaluasi-petaks` di-inline-code; SCHEMA tag `medan, sintesis`
- Lint: BROKEN 0, ORPHANS 0, MISSING_INDEX 0
- Index: 92 halaman wiki (16 entities + 52 concepts + 1 comparison + 22 queries) + 3 raw

## [2026-10-03] create | entities/panel-spatial-map
- Pages: entities/panel-spatial-map (inventaris 13 komponen + chart box, tabel op vs komponen dari map_store ALLOWED_OPS + handler map.js, tak-langsung KPI/Legend/Insight/Meta/Progress, guard anti-loop spatial_set, 4 domain evaluasi)
- Update: panel-dashboard (link balik + bump), tool-bisnis-anna (link balik), inteligensi-spasial + presentasi-spasial (link balik + bump)
- Index: 96 halaman wiki (18 entities + 54 concepts + 1 comparison + 22 queries) + 3 raw

## [2026-10-03] create | queries/intent-ke-template-peta
- Pages: queries/intent-ke-template-peta (mapping wajib ANNA intent→template+param untuk 5 kategori: petak wilayah, petak KPH/DIVRE, aktivitas, produksi/RKAP, matriks; + section 2b ringkasan KPI kph_summary_map; kode wilayah cepat; parameter waktu baku; anti-pattern)
- Update: index.md (+bullet, total 97)
- Index: 97 halaman wiki (18 entities + 54 concepts + 1 comparison + 23 queries) + 3 raw

## [2026-10-03] update | P0 skala multi-DIVRE: spatial index + kph_summary_map + viewport query
- DB: petak_polygon.geom geometry column + idx_geom SPATIAL INDEX (1003 rows, 0 null). MBRContains uses index (rows~50), ST_Intersects full scan (rows=945) — dua tahap confirmed.
- Added getah_petak.idx_tahun_kph (tahun_rtt, kode_kph), petak_polygon.idx_evapot (kode_evapot).
- simoge_db.py: template kph_summary_map (centroid + KPI per KPH/BKPH/DIVRE) + bounds filter via MBRContains + auto-escalate aggregated_level via zoom.
- server.py: _TEMPLATE_SPATIAL add kph_summary_map, _SPATIAL_FILTER_KEYS add aggregated_level/bounds/zoom.
- businessAdapter.js: kat 'ringkasan'/'summary' → kph_summary_map, forward aggregated_level/bounds/zoom.
- ana_simoge_tool.py: explanation formatter for kph_summary_map.
- tool-bisnis-anna.md: 38 template (incl. kph_summary_map).
- intent-ke-template-peta.md: section 2b ringkasan KPI mapping.
- Tested: kph_summary_map returns 1 KPH (809 petak, eff 68.64%), zoom=10 auto-escalate to DIVRE works.
- Index: 97 halaman (18 entities + 54 concepts + 1 comparison + 23 queries + 3 raw)
- Lint: BROKEN 0, ORPHANS 0, MISSING_INDEX 0

## [2026-10-04] create | P2-4 wiki skala: skala-multi-divre + arsitektur-skala-peta
- Pages: queries/skala-multi-divre (decision tree template, param viewport bounds/zoom/page_size/aggregated_level, batas multi-value/exclude/flag generik, fallback chain), concepts/arsitektur-skala-peta (3 jalur hybrid tier, spatial index MBRContains+Intersect, freshness PMTiles vs live DB, pagination jujur + cache TTL 3s).
- Update: intent-ke-template-peta (link balik ganti spatial-sync-kontrak → skala-multi-divre + arsitektur-skala-peta, bump updated); index.md (2 bullet baru, header 2026-10-04, duplikat tool-bisnis-anna dirapikan).
- Diverifikasi: show_on_map kph_summary_map zoom=10 auto-escalate DIVRE (1 baris, 809 petak, eff 68.64%); petak_efektivitas_map + bounds viewport 116 baris; panel _pushViewport debounce 600ms + _maybeSwitchTier Z≤11 PMTiles/Z≥12 GeoJSON (aturan final user 2026-10-04 — threshold ≤12/>12 di entri ini dikoreksi entri P2-4 berikutnya); PMTiles 855 KB z8-15 GZIP valid.
- Index: 99 halaman (18 entities + 55 concepts + 1 comparison + 24 queries + 3 raw)
- Lint: BROKEN 0, ORPHANS 0, MISSING_INDEX 0

## [2026-10-04] update | P2-4 cron rebuild + tombol ⚙ + threshold Z final
- Server: `_tiles_cron` + `_cron_read/_cron_write` (marker `ana-pmtiles-daily`, hanya baris marker disentuh, validasi jadwal 5 field) + `POST /api/tiles/cron` status|enable|disable; `_tiles_status` + `GET /api/tiles/status` (PMTiles bytes/mtime, NDJSON baris, baris cron, log tail); `scripts/rebuild_tiles_daily.sh` (export NDJSON dari DB → build z8–15, fallback NDJSON kemarin bila export gagal).
- UI: tombol ⚙ `#spatialTilesBtn` + modal `#spatialTilesModal` (status, input jadwal default `10 6 * * *`, rebuild manual, cron on/off; token via `meta ana-token` + `X-Ana-Token`, POST wajib Origin cocok port).
- Threshold Z final (aturan user): Z≤11 PMTiles polygon saja (tanpa analisa/pin, base netral semua business, enforce tanpa return dini), Z≥12 GeoJSON analisa + pin; badge `Z{n}·PMTiles/GeoJSON`.
- Wiki: `arsitektur-skala-peta` +section 6 operasional PMTiles (cron/rebuild/status/verifikasi); `panel-spatial-map` bump updated (komponen 3b tombol ⚙ + section tier sudah ada); `skala-multi-divre` sudah benar (≤11/≥12) tanpa ubahan.
- Diverifikasi: cron status enabled=true, 1 baris marker, total non-marker tetap; `/api/tiles/status` ok (pmtiles 855584 B, ndjson 804 baris); `verify_pmtiles.py` header GZIP min8 max15, 255 entries, 804 fitur; tile z12 200/10939 B, z11 200/17144 B; badge `z<=11 PMTiles / GeoJSON`; enforce polygon semua business (`map.js:996-1037`, `mapControl.js` 6 def visibilitas).
- Index: 99 halaman (18 entities + 55 concepts + 1 comparison + 24 queries + 3 raw)
- Lint: BROKEN 0, ORPHANS 0, MISSING_INDEX 0

## [2026-10-04] create | Golden example laporan eksekutif + tren
- `queries/contoh-laporan-eksekutif-kph-barat.md`: laporan 13-section September 2026 KPH Barat (snapshot sandbox 2026-10-04), tiap angka berlabel FACT/DERIVED/COMPARISON/INTERPRETATION/HYPOTHESIS sesuai `klasifikasi-fakta` + `disiplin-evidence`.
- `queries/contoh-laporan-tren-bulanan.md`: tren Mei vs April 2026 (produksi 680.617 -> 909.725 kg +33,7%, aktivitas 7.765 -> 8.322 +7,2%, achievement 57,80% -> 58,86%) + YoY 2025 eksplisit ditolak (produksi NULL 0,0 kg, aktivitas 0 baris — sandbox hanya data 2026, 0 kg bukan baseline).
- Index: header koreksi 101 -> 103 (18 entities + 55 concepts + 1 comparison + 26 queries + 3 raw); kedua halaman masuk section Queries.
- Lint: kedua halaman outbound 30/25, BROKEN 0; in-index True.

## [2026-10-04] create | LAPORAN BISNIS — dokumen N halaman siap cetak
- Backend: `spatial_report_store.py` 152 baris (state `{visible,title,subtitle,pages[],evidence[],meta,updated}`, block `para|kpi|table|list|note`, session memory, validator; `set_report→(ok,err)`, `get_state`); `server.py` import + allowlist POST + `GET /api/spatial/report` + `POST /api/spatial/report` (auth `_token_ok`+Origin, body must be object), routes terpisah GET:1162/POST:1642 (dua method, bukan duplikat).
- Frontend: `ui/src/spatialReport.js` 153 baris — flying di `.map-wrap`, poll 2s `GET`, render `pages[]` sebagai `.rpt-page` (kpi/table/para/list/note), tombol `Unduh`=`window.print()`+`body.rpt-printing` (transient 1.2s + `afterprint`), `Tutup`=POST `visible:false`; `ui/styles/map.css` bump `v=20261004d` — `.spatial-report.flying` z410, `@media print` `#hud> *:not(#mapPanel)` + `.map-wrap > *:not(#spatialReportWrap)` hidden, `.rpt-page` putih-hitam `break-after: page`, tombol hidden saat print.
- Wiring: `ui/src/map.js` `const _tok` dikeluarkan dari blok `try` pertama (fix ReferenceError yang menelan `initSpatialReport`), `initSpatialChart`+`initSpatialReport` berdampingan; `ui/index.html` bump `main.js?v=20261004f` + `map.css?v=20261004d`.
- ANNA: `~/.hermes/profiles/anna/.../scripts/ana_chart_tool.py` — `_report_post`, `show_report(title,subtitle,pages,evidence,meta)`, `hide_report()`, `get_report()` + alias `hide_laporan`; CLI `laporan act=show|hide|status` (`_val` JSON parse untuk `pages/evidence/meta`); `SKILL.md` +section LAPORAN BISNIS (kontrak state, block types, alur tutup-lalu-buka wajib, tombol, batasan).
- Alur wajib buka/tutup (aturan user): tampilkan → `get_report()` cek `visible`; jika true `hide_report()` dulu baru `show_report(isi_baru)`, jika false langsung `show_report`; `show_report` selalu menimpa seluruh state.
- Wiki: `entities/panel-spatial-map.md` tambah baris Laporan box + baris `POST /api/spatial/report`; `concepts/laporan-bisnis.md` baru (kontrak, block, kenapa bukan chart, alur tutup-lalu-buka, tombol, batasan); `index.md` 104 halaman (18 entities + 56 concepts + 1 comparison + 26 queries + 3 raw).
- Diverifikasi: POST show/hide/status via curl + `ana_chart_tool.py laporan` (2 halaman KPI+para+note+table→list+kpi), browser `spatialReportWrap` `visible/hidden` toggle benar, Unduh menyembunyikan peta/chart/progress/bottomBar/mapFly + `.rpt-page` putih-hitam, state `visible:false` tercatat di server setelah klik Tutup.
