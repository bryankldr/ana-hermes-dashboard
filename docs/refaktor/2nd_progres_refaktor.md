# Progres Refaktor SPATIAL MAP — Profil ANNA (PT Perhutani)

> Panel sasaran: `SPATIAL MAP` saja. Dashboard lain tidak disentuh. Sumber bisnis: `2nd_kontek_bisnis.md` + skill `simoge-business`. Profil Hermes: `anna` (`~/.hermes/profiles/anna`).

---

## 2026-10-01 — Fase 0: Inspect & Planning

### Selesai
- [x] **Inspect struktur project** — `ana-hermes-dashboard`: `server.py`, `map_store.py`, `spatial_intel.py`, `ui/src/map.js`, `ui/src/mapControl.js` (LeafletAdapter), `ui/styles/map.css`, `ui/index.html`, `persona.md`, `.env`, `layout.json`.
- [x] **Inspect SPATIAL MAP existing** — Leaflet Esri (Dark + Satelit Group), `petakLayer` overlay, `createLeafletControl` + queue `map_store` (`/api/map/state`, `/api/map/queue`, `/api/map/command`, `/api/map/result`), `WARNA_STYLE` merah/kuning/hijau + emas sudah ada, `set_features`/`clear_features`/`set_filter` siap.
- [x] **Inspect Business Data Engine** — skill `simoge-business` (`simoge_db.py` 23 template, `ana_simoge_tool.py` `call_simoge_tool` + `show_on_map`). Join `kode_evapot`, periode P1 1-15/P2 16-akhir, target RO/NPS persen × `target_rkap`, definisi bongkor/idle/aktif, warna efektivitas & RKAP. Verifikasi DB live `kph_bwb_sandbox2`: 2025-2026, 810 RTT 2026, BKPH 5, RPH ~10, TPG ~10, `DIVRE=2` & `KPH=31211` single-value.
- [x] **Profil ANNA diverifikasi** — `~/.hermes/profiles/anna` (lowercase), `SOUL.md` = Business Intelligence (dashboard owns data, ANNA owns interpretation), `persona.md` = SIMOGE Business Specialist (mode asisten/coding, bahasa Indonesia). `.env` diperbaiki `HERMES_PROFILE=ANNA → anna` (Linux case-sensitive).
- [x] **Dokumen planning ditulis** — `2nd_planing.md` lengkap: profil ANNA, tujuan, kontek bisnis ringkas, aturan jangan-merusak, arsitektur `DATABASE → Business Data Engine → Processed Data → SpatialMapState → Map → ANA`, mapping template (Petak/Aktivitas/Produksi/Matriks), filter & business selector inside panel, state isolasi `SpatialMapState`, UI/UX compact, file scope ALLOWED/NOT, tahapan Fase 1-4, risiko, kriteria selesai.

---

## 2026-10-01 — Fase 1-4: Implementasi Business Map Workspace

### Selesai

- [x] **Fase 1 — State & Adapter (isolated)**
  - `ui/src/spatialMapState.js` — `SpatialMapState {business, filters{bulan,tahun,periode,divre,kph,bkph,rph,tpg,kategori}, dataset, layers, selection, metrics}`. Emit `SPATIAL_MAP_CHANGED` via `bus.js`, expose `window.__spatialMapState` untuk ANA baca. Tidak menyentuh state panel lain.
  - `ui/src/businessAdapter.js` — facade `DATABASE → Engine → Map`: `resolveTemplate()` mapping business→template (`petak→petak_efektivitas_map`/`petak_bongkor_map`, `produksi→rkap_map`, dll), `loadBusinessData()` POST `/api/simoge/show_on_map`, `fetchWilayahOptions()` via `petak_by_kph`. Tidak ada SQL di frontend.

- [x] **Fase 2 — UI SPATIAL MAP (inside panel only)**
  - `ui/src/map.js` — extend body `#mapPanel`: toolbar kompak (`spatialBiz` Evaluasi Petak/Aktivitas/Produksi/Matriks + `spatialKat` Semua/Bongkor/Idle/Tanpa Penyadap/MultiPenyadap) + tombol `⚙ Filter ▾` collapsible + `↻` refresh. Filter strip: Bulan/Tahun/Periode | DIVRE/KPH/BKPH/RPH | TPG (scoped, hanya pengaruhi SPATIAL MAP). Metric bar + legenda di bawah `#mapBox`, sebelum `#mapStat`. Reuse `tokens.css` + `map.css`, tidak perbesar panel, semua event scoped.
  - `ui/styles/map.css` — tambah `.spatial-toolbar`, `.spatial-select/.spatial-mini`, `.spatial-btn`, `.spatial-filters(.collapsed)`, `.spatial-row`, `.spatial-hint`, `.map-metric`, `.map-legend .lg`.

- [x] **Fase 3 — Data → Map (wiring)**
  - `map.js` wiring: `collectState() → setBusiness/setFilters → loadBusinessData → server _simoge_show_on_map → map_store.pushCommand(set_features) → LeafletAdapter _resolveStyle WARNA_STYLE` + auto-fit. Kategori `bongkor` → `petak_bongkor_map` merah, else `petak_efektivitas_map` merah/kuning/hijau, `produksi→rkap_map` 5 warna. Wilayah passed as `params` dan di-WHERE di DB. `fetchWilayahOptions` isi BKPH/RPH/TPG async. `window.__spatialReload/__spatialCollect` untuk ANA/command. Auto-load 900ms setelah panel build.

- [x] **Fase 4 — Verifikasi & Regression**
  - Fix `HERMES_PROFILE=ANNA→anna`, install `pymysql` di hermes env, restart server → `profile: anna` **verified**. `pymysql 2.2.8` verified.
  - `POST /api/simoge/show_on_map` untuk `petak_bongkor_map`, `petak_efektivitas_map`, `rkap_map` semua `ok: true` **verified** (features 2-3 per test, warna merah/kuning/hijau/oranye/hijau sesuai business rule).
  - Static served `src/spatialMapState.js`, `businessAdapter.js`, `map.js`, `map.css` via `lstrip(ui/)` **verified**.
  - `node --check` 3 file **verified**.
  - `smoke.py` — **PASS 121 checks** (GET, token/origin gate, static, NDJSON, terminal lifecycle, malformed input, liveness).
  - Panel lain: `PERFORMANCE BRIEFING, MISSION KANBAN, VAULT STATUS, ACTIVE REPOSITORIES, EVENT STREAM, INTELLIGENCE SURFACE, SYSTEM MATRIX, AGENT PIPELINE, ANDROID AVD, CHAT/COMMAND` tetap — `mapPanel` dynamic via `ensurePanel`, tidak ada static break **verified**.

---

## 2026-10-02 — Lanjutan: Filter Wilayah Server-Side (DB WHERE)

### Selesai

- [x] **Skill `simoge-business` patch** — `~/.hermes/skills/software-development/simoge-business/scripts/simoge_db.py`:
  - Tambah helper `_wilayah_where(kw)` allowlist `kode_divre,kode_kph,kode_bkph,kode_rph,kode_tpg` → `p.col = %s` paramised, `isdigit` guard (anti-injection), return `(frag, vals)`.
  - Patch `petak_bongkor_map`, `petak_efektivitas_map` → `WHERE p.tahun_rtt=%s{w}` + `tuple([tahun]+wv+[limit])`.
  - Patch `rkap_map` → tambah `p.kode_kph,kode_bkph,kode_rph,kode_tpg` ke SELECT + `WHERE ...{w}` + `tuple([d0,dlast,tahun]+wv+[limit])`. `py_compile` ok.
- [x] **Verifikasi DB langsung** — `simoge_db.run()` tanpa server:
  - `petak_efektivitas_map tahun=2026 limit=5 kode_bkph=3121101` → 5 rows semua `kode_bkph=3121101`, warna `kuning/merah` benar.
  - `petak_bongkor_map ... kode_bkph=3121102` → 5 rows semua `3121102`, kategori `bongkor` merah.
  - `rkap_map ... kode_bkph=3121101` → 5 rows semua `3121101`, warna `merah/hijau/oranye`, `kode_*` kolom hadir.
  - `rkap_map ... kode_rph=312110201` → 3 rows semua `312110201`, pencapaian `90.97% hijau` verified.
- [x] **Verifikasi via HTTP** — restart `server.py` `HERMES_PROFILE=anna` → `profile: anna` **verified**. `POST /api/simoge/show_on_map` dengan `kode_bkph/kode_rph`:
  - `petak_efektivitas_map kode_bkph=3121101` → `ok:true features:3`, GeoJSON `properties.kode_bkph=3121101` benar, queue `set_features` push verified.
  - `petak_bongkor_map kode_bkph=3121102` → `ok:true`, sample `kode_evapot 21112050160500_16E luas 27.39` merah bongkor.
  - `rkap_map kode_bkph=3121101` → `ok:true`, sample `nomor_petak 23A-3 pencapaian 0.0 merah`.
  - `rkap_map kode_rph=312110201` → `ok:true`, sample `13A pencapaian 90.97 hijau` benar.
  - No-filter sanity `limit=3` → `ok:true` tetap.
  - `smoke.py` re-run → **PASS 121** (regression panel lain tetap, no breaking).
- [x] **Frontend adapter update** — `ui/src/businessAdapter.js` comment `ponytail tambah WHERE` → `di-WHERE di DB (_wilayah_where, allowlist paramised)`, fallback comment update. `node --check` 3 file ok, static served verified.
- [x] **Wilayah options live** — `petak_by_kph level=kode_bkph` → `[3121104,3121103,3121101,3121102,3121105]`, `kode_rph` → 5 RPH, `kode_tpg` → `[31211020201,...]` verified; `fetchWilayahOptions` pakai itu untuk isi dropdown BKPH/RPH/TPG.

### Catatan Teknis
- `_wilayah_where` numeric `int(s)` — kolom DB `int(11)`; `tpg` juga `int` di `getah_petak`; aman. Non-digit diabaikan (guard).
- `rkap_map` sebelumnya tidak return `kode_*` → frontend tidak bisa post-filter; sekarang SELECT sudah lengkap, ANNA bisa baca `properties.kode_*` + `warna/pencapaian_pct`.
- `petak_simple.json` tetap cadangan, bukan sumber business — sumber `kph_bwb_sandbox2` via skill; panel isi setelah `reloadBusiness()` auto-load.
- Semua perubahan scoped ke `SPATIAL MAP` + skill `simoge-business`; chat/voice/terminal/layout/memory tidak disentuh. Server port 8730 `profile anna`.

### Next (opsional — di luar scope lanjut)
- Idle/matriks `*_map` polygon bila ANNA butuh story luas idle vs aktif (template `idle_petak` belum polygon).
- `clear_features` debounce sebelum `set_features` baru bila operator spam filter (belum perlu, queue sudah lock).

---

## 2026-10-02 — Lanjutan 2: Idle & Aktivitas Polygon (Business Map lengkap)

### Selesai
- [x] **Skill `simoge_db.py` 2 template map baru** — total `_map` = 5:
  - `idle_petak_map(tahun,bulan,periode,limit)` — idle=kuning / aktif=hijau per `period_bounds` P1/P2, join `getah_aktivitas_sadap.tgl_pembaharuan` via `getah_andil.kode_evapot`, `pp.polygon`, `WHERE tahun_rtt + _wilayah_where`, order `cur.cnt IS NULL DESC`. Warna bisnis kuning/hijau, kategori `idle/aktif`, kolom `aktivitas_periode_ini/lalu`.
  - `aktivitas_petak_map(tahun,bulan,periode,limit)` — aktivitas tapping periode ini: 0=merah `tanpa_aktivitas`, 1-2=kuning `rendah`, ≥3=hijau `aktif`. Same join + `WHERE`, order `act.cnt DESC`.
  - Kedua template support `kode_divre/kph/bkph/rph/tpg` via `_wilayah_where` (allowlist paramised). `py_compile` ok. Verified `templates map = [aktivitas_petak_map, idle_petak_map, petak_bongkor_map, petak_efektivitas_map, rkap_map]`.
- [x] **Verifikasi DB langsung 11 case** — semua `polygon=True`, wilayah filter benar:
  - `bongkor{code_bkph=3121102}` 3 rows merah, `efektivitas{code_bkph=3121101}` 3 rows kuning/merah, `rkap{code_bkph=3121101}` 3 rows merah, `idle_petak_map` 5 rows kuning, `idle{code_bkph=3121101}` 5 rows kuning, `aktivitas` 5 rows hijau, `aktivitas{code_rph=312110201}` 5 rows merah (wilayah benar, warna sesuai count).
- [x] **Adapter `businessAdapter.js` wiring lengkap** — `resolveTemplate`:
  - `petak idle → idle_petak_map(bulan,periode)`, else `petak sem/bongkor/multi` tetap.
  - `aktivitas idle → idle_petak_map`, else `aktivitas → aktivitas_petak_map(bulan,periode)` (merah 0/kuning 1-2/hijau ≥3). `matriks` tetap efektivitas fallback (ponytail tambah bila butuh). Comment ponytail updated.
- [x] **Map UI `map.js` update**
  - `syncKatVisibility`: show `katSel` untuk `petak || aktivitas` (sebelum hanya petak).
  - `updateLegend(biz,kat)`: petak idle=kuning/hijau, petak normal bongkor/kurang/terpenuhi, produksi 5 step, aktivitas idle=kuning/hijau, aktivitas normal merah/kuning/hijau (tanpa/rendah/aktif), matriks fallback. Calls updated: init, biz change, kat change, `MAP_FEATURES_LOADED`, `subscribeSpatial` (kategori sync).
  - `kat change → updateLegend + scheduleReload`, `reloadBusiness → _ctl.clear_features()` sebelum `loadBusinessData` (anti stack polygon spam filter), `subscribeSpatial` sync kategori + legend.
  - `node --check` map/adapter/state ok.
- [x] **HTTP verification 6 template** — restart `profile: anna` verified. `POST /api/simoge/show_on_map` 5+1 case:
  - `petak_bongkor 3121101` queue warna merah, `efektivitas` kuning, `rkap 3121101` merah (pencapaian 0%), `idle 3121101` kuning, `aktivitas 3121101` hijau (≥3 aktivitas Sep P2), `aktivitas kode_rph=312110201` 3 feat merah verified. Queue `set_features` push verified per call.
- [x] **Regression** — `smoke.py PASS 121` (GET, token/origin, static, NDJSON, terminal, liveness), static `map.js/adapter` served verified, panel lain tetap via `ensurePanel`.

### Catatan
- Aktivitas data Sep 2026 tipis (P1=2, P2=16 rows) — aktivitas map tetap valid, warna merah dominan bila periode tanpa aktivitas; hijau bila ada hit. Idle map Periode 2 Sep: banyak `idle=kuning` (periode ini 0, lalu ada) verified.
- `petak_simple.json` tetap cadangan; sumber `kph_bwb_sandbox2` 810 petak 2026 + 1003 polygon + 764 aktivitas×polygon coverage verified.
- Scope tetap SPATIAL MAP + skill; chat/voice/terminal/layout/memory tidak disentuh.


---

## 2026-10-02 — Lanjutan 3: Matriks Polygon (6-template Business Map lengkap)

### Selesai
- [x] **Skill `simoge_db.py` `matriks_map(tahun,bulan,periode,limit)`** — hubungan `luas_andil vs pencapaian RKAP` per petak + polygon. Kolom: `luas_andil, jumlah_penyadap, realisasi, target_periode, pencapaian_pct, kategori_efektivitas(bongkor/kurang/terpenuhi), kategori/warna` (merah bongkor / oranye kurang+cap<50 / kuning kurang / hijau terpenuhi 0-100 / emas >100). Join `getah_andil` + `getah_aktivitas_penerimaan(BETWEEN d0,dlast)` + `getah_target_ro_nps(tahun)` + `petak_polygon`, `WHERE tahun_rtt + _wilayah_where`, `GROUP BY kode_evapot`, order `luas_andil/luas_baku`. `py_compile` ok. Verified 6 map templates total.
- [x] **Verifikasi DB 3 case** — `matriks_map 2026/9/2 limit3` 3 rows `bongkor merah 0.00%` (tanpa andil/realisasi), `kode_bkph=3121101` 3 rows merah, `kode_rph=312110201` 3 rows merah — `kode_bkph` filter benar, polygon True, order stable.
- [x] **Adapter `businessAdapter.js`** — `matriks → matriks_map(tahun,bulan,periode,limit,wilayah)` (sebelum fallback efektivitas). `node --check` ok.
- [x] **Map UI `map.js`** — legenda `matriks: Bongkor/orange Kurang+cap<50/Kurang/Terpenuhi/>100%` 5 step. `node --check` ok.
- [x] **Skill `ana_simoge_tool.py` `_explain`** — 6 cabang baru: `petak_bongkor_map, petak_efektivitas_map, rkap_map, idle_petak_map, aktivitas_petak_map, matriks_map` dengan `warna/kategori/status` counts + threshold legend. `py_compile` ok. Verified `explanation` per template: Bongkor `merah=3`, Efektivitas `kurang=1,bongkor=2`, RKAP `merah=3`, Idle `idle=3`, Aktivitas `aktif=3`, Matriks `merah=3`.
- [x] **HTTP verification restart `profile: anna`** — `POST /api/simoge/show_on_map` 6 template `ok:true features:3` + `explanation` benar, `matriks kode_rph=312110201` `ok:true features:3` verified. `smoke.py PASS 121` regression tetap. Static `map.js/adapter` served verified.

### Catatan
- Matriks menggabungkan efektivitas (andil) × pencapaian (RO/NPS%) — satu warna mewakili 2 dimensi; ANNA bisa jelaskan gap `luas_andil vs realisasi`. Data Sep 2026 tipis → dominan merah bongkor, oranye/kuning muncul bila ada andil tapi cap rendah.
- 6 `_map` polygon semua support `kode_divre/kph/bkph/rph/tpg` via `_wilayah_where`; `matriks_map` return `kode_*` lengkap untuk ANNA `properties.kode_*` + `warna/kategori/pencapaian_pct`.
- Scope tetap SPATIAL MAP + skill 2 file; `server.py` sudah handle via `_simoge_show_on_map` generic (no patch), chat/voice/terminal/layout/memory tidak disentuh.


---

## 2026-10-02 — Lanjutan 4: Polish (kode_divre + Multi-Penyadap + 8-filter + Regression)

### Selesai
- [x] **Skill `simoge_db.py` polish** — `kode_divre` ditambahkan ke SELECT semua 7 `_map` (bongkor/efektivitas/multi/rkap/idle/aktivitas/matriks). Header `p.target_rkap, p.kode_kph` → `p.target_rkap, p.kode_divre, p.kode_kph` (allowlist `_WILAYAH_COLS` sudah include `kode_divre`). Verified `kode_divre` ada di semua rows, `DESCRIBE getah_petak` `kode_divre int(11)` + `kode_tpg bigint` konsisten, `T` map templates = 7.
- [x] **Template baru `petak_multi_penyadap_map(tahun,limit,wilayah)`** — `JOIN (SELECT kode_evapot HAVING COUNT(DISTINCT id_penyadap)>1)` → hanya petak multi, warna `kuning 2 / oranye 3 / hijau >3`, kategori `multi`, order `penyadap DESC, luas_andil DESC`, `WHERE p.tahun_rtt + _wilayah_where`. Verified `efektivitas limit1000 multi=279` contoh `23E-3 2 penyadap`, `multi_map` `BKPH=3121101` 3 rows hijau, `RPH=312110102` 2 rows kuning, `DIVRE=2` 2 feat ok, `DIVRE=99` 0 feat `ok:false no geometry` benar (no karangan).
- [x] **Adapter `businessAdapter.js`** — `multi_penyadap → petak_multi_penyadap_map` (replace fallback `petak_efektivitas_map postFilter:multi` yang tidak pernah filter client). `node --check` ok.
- [x] **Map UI `map.js`** — legenda `petak multi_penyadap: 2 kuning / 3 oranye / >3 hijau` branch sebelum produksi. `node --check` ok. Static served verified.
- [x] **Skill `ana_simoge_tool.py` `_explain`** — cabang `petak_multi_penyadap_map` `kuning 2/oranye 3/hijau >3`. `py_compile` ok. Verified 7 `explanation`: bongkor merah, efektivitas kurang/bongkor, multi hijau, rkap merah, idle idle, aktivitas aktif, matriks merah.
- [x] **8-filter wilayah full scan** — `petak_efektivitas_map tahun=2026 limit2` per `kode_divre=2` ok `2 feat`, `kode_kph=31211` ok, `kode_bkph=3121103` ok, `kode_rph=312110301` ok, `kode_tpg=31211030101` ok — semua `ok=True` dan `kode_*` match, polygon True. `matriks kode_bkph=9999999` → `ok:false no geometry` (jujur tidak karang). Filter Tahun/Bulan/Periode sudah via `tahun,bulan,periode` param (P1/P2 `period_bounds`).
- [x] **HTTP 7-template verification** — restart `profile: anna` verified. `POST /api/simoge/show_on_map` 7 case `ok:true feat 2` semua warna benar: bongkor merah, efektivitas kurang/bongkor, multi hijau, rkap merah (P2 9/2026), idle kuning, aktivitas hijau, matriks merah. `DIVRE=2` 2 feat, `DIVRE=99` `ok:false`. `smoke.py PASS 121` regression tetap, static `map.js/adapter/state/css` served, panel lain `PERFORMANCE BRIEFING…SPATIAL MAP` via `ensurePanel` tetap, chat/voice/terminal/layout/memory tidak disentuh.

### Catatan
- `kode_divre` single-value `2` di DB 2026 — dropdown tetap tampil, filter `DIVRE=2` return 2 feat, `DIVRE=99` 0 feat handled tanpa error (ANNA jawab jujur). `kode_tpg bigint` via `isdigit→int(s)` tetap aman (fit dalam Python int).
- `petak_multi_penyadap_map` jumlah 278-279 petak multi (tahun 2026) — contoh `20 D1 n_penyadap 32` total_andil=luas_baku (terpenuhi). Map warna hijau dominan bila >3, kuning bila tepat 2.
- 7 `_map` semua support 8 filter (tahun+bulan+periode+5 wilayah via `_wilayah_where` allowlist paramised). Frontend `resolveTemplate` 4 business: petak(5 kategori) → 4 template, aktivitas(2) → idle/aktivitas, produksi → rkap, matriks → matriks. `clear_features()` sebelum `loadBusinessData` anti stack.
- Next opsional: `periode` clamp guard bila bulan Feb `period_bounds` last day, `limit` slider bila operator butuh 2000 polygon (ponytail tambah).

---

## 2026-10-01 — Lanjutan 5: Cadangan Evaluasi Harian petak_simple.json selaras bisnis (DB 100% tetap)

### Selesai
- [x] **Amanat `petak_simple.json selaras bisnis` masuk rencana** — `2nd_planing.md` §9 File Scope + §10 Fase 5 + §13 Cadangan Harian ditambah; `2nd_refaktor_fungsi_panel_map_dan arsitektur.md` append `PETAK_SIMPLE.JSON — CADANGAN EVALUASI BISNIS HARIAN` (meta, arsip, DB 100% map.js). Scope tetap SPATIAL MAP — `map.js` Business Map tidak baca cadangan untuk polygon bisnis.
- [x] **`spatial_intel.py` toleran wrapper `{meta,features}`** — `_raw_list_and_meta()` baca `{meta,features}` baru maupun array lama `[{n,p}]`; `_load()` normalisasi MultiPolygon `[[[lon,lat]]]` → flatten rings; `get_polygon()` normalisasi sama; `_cache.meta` ditambah; `stats()` kembalikan `meta + generated_at/tahun_rtt/periode/counts/source_db` + fallback bila cache kosong; `get_meta()` baru untuk YOY ANNA (jangan karang — sebut `generated_at`). Backward compat verified: array lama 1 fitur ok, wrapper baru 1004 ok (sebelum dedupe; final 999). `py_compile` ok. `count 1004→999` (dedupe 5 `kode_evapot` duplikat, 999 distinct).
- [x] **`scripts/refresh_petak_simple.py` generator harian (WIB)** — `kph_bwb_sandbox2 → {meta,features}`: `petak_polygon LEFT JOIN getah_petak latest tahun_rtt per kode_evapot`, `polygon JSON type Polygon/MultiPolygon → p [[lon,lat]] flatten`, per fitur enrich `tahun_rtt/nomor_petak/kode_divre/kph/bkph/rph/tpg/luas_baku/target_rkap`, `meta{generated_at WIB ISO, source kph_bwb_sandbox2, tahun_rtt 2026, periode 2026-10-P1, counts{total 999, raw_polygon_rows 1003, distinct_evapot 999, orphan_no_rtt 195, rtt 810/798, join 809}, generator, version 2}`. Override atomik `ui/data/petak_simple.json` + arsip `ui/data/snapshots/petak_YYYY-MM-DD.json` untuk YOY. `--dry-run` ok. Id `kode_evapot` (join kunci) — `n` lama 14-digit tidak match; baru langsung join.
- [x] **Generate & verifikasi** — `refresh --dry-run` + live: `1004→999 features` `1.7M` verified (dedupe 5 duplikat); `ui/data/snapshots/petak_2026-10-01.json` 1.7M archived; `spatial_intel.stats count 1004 (sebelum dedupe; terkoreksi jadi 999 di Lanjutan 7) tahun 2026 periode 2026-10-P1` via `python direct` + via `POST /api/spatial/query q:stats` **verified**; `find_petak` + `get_polygon` + `neighbors 2` ok; old array compat `count 1 meta false` ok.
- [x] **Business Map tetap DB 100%** — `map.js → businessAdapter → /api/simoge/show_on_map → simoge_db 7 _map → map_store → Leaflet WARNA_STYLE`; cadangan tidak dipakai untuk warna/filter. Restart `profile: anna` verified; `POST show_on_map` 7 template `ok:true feat 2` (bongkor/efektivitas/multi/rkap/idle/aktivitas/matriks) **verified**; `smoke.py PASS 121` regression tetap; panel lain tetap via `ensurePanel`.

### Catatan
- `n` sekarang `kode_evapot` (mis. `21111010200200_20B`) — `spatial_intel` resolve `exact`/`unique-substring` tetap, `get_polygon` return `polygons: p` flat rings. MultiPolygon 3 kasus (mis. `44A-1` 3 poly) flatten jadi rings list — `_load` area/centroid hitung benar setelah normalize (fix `TypeError int+list`).
- Cron harian: `0 6 * * * cd ... && python3 scripts/refresh_petak_simple.py >> logs/refresh_petak.log 2>&1` (WIB 06:00, periode P1/P2 sesuai tgl). Re-run hari sama overwrite `petak_YYYY-MM-DD.json` idempoten.
- ANNA YOY: baca `stats.meta` / file wrapper + sebut `generated_at` & `tahun_rtt` — bila DB lambat, fallback cadangan jujur; bila tanya `tahun lalu vs tahun ini`, bandingkan `snapshots/petak_YYYY-MM-DD.json` vs live counts (YOY tanpa karang).
- Next: tidak ada — cadangan kecil, reversible, no redesign.

---

## 2026-10-01 — Lanjutan 6: Penyempurnaan sisa (cache, cron, 2273→999, polish)

### Selesai
- [x] **`spatial_intel.py` cache mtime** — `_cache.mtime` + `_load()` cek `DATA.stat().st_mtime` sebelum pakai cache; update `mtime=mt` saat rebuild. Fix stale setelah `refresh_petak_simple.py` override `petak_simple.json` tanpa restart server (sebelumnya cache selamanya).
- [x] **`2nd_planing.md` §3 & §13** — `2273` → `999 features wrapper {meta,features} harian selaras DB` + risiko mark `selesai — lama 2273 → kini 999` (YOY pakai `meta.generated_at`).
- [x] **`2nd_refaktor_fungsi_panel_map_dan arsitektur.md` risiko** — mark `selesai: lama 2273 → 999 deduped wrapper (1004→999) harian` + arsip YOY, DB 100% tetap.
- [x] **`docs/SPATIAL_MAP_PHASE1_REPORT.md` Addendum 2026-10-01** — 2273 → 999 deduped wrapper (1004→999), generate WIB cron 06:00, toleran wrapper/array, `stats() meta + mtime`.
- [x] **`test_map_command.py` mock clarify** — `count 2273  # mock map_store state, bukan petak_simple count (kini 999 wrapper)` anti bingung.
- [x] **`persona.md` rewrite UTF-8** — ensure valid UTF-8 (locale C `cat -A` sebelumnya tampil `M-b` artefak `e2 80 94` → `—`).
- [x] **`.gitignore` + `logs/`** — `ui/data/snapshots/` + `logs/` diignore (bloat harian bila commit); `logs/.gitkeep` dibuat.
- [x] **`ui/src/mapControl.js` header** — `GeoJSON ... (DB 100% — 7 _map)` + `petak_simple.json wrapper {meta,features} (cadangan harian, bukan sumber Business Map)` + flatten MultiPolygon comment.
- [x] **Cron harian** — `crontab 0 6 * * * cd ... && python3 scripts/refresh_petak_simple.py >> logs/refresh_petak.log 2>&1` terpasang (Asia/Jakarta 06:00, P1/P2 sesuai tgl).
- [x] **Verifikasi akhir** — `profile anna` + `POST /api/spatial/query q:stats count 999 tahun 2026 periode 2026-10-P1 meta True` + `POST /api/simoge/show_on_map` **7 template `ok:true feat 2`** (bongkor/efektivitas/multi/rkap/idle/aktivitas/matriks) + `smoke.py PASS 121` + `py_compile spatial` ok.

### Catatan
- `petak_simple.json` grep `2273` kini hanya di history (lama) + live sudah 999 — tidak ada sumber bisnis pakai 2273 lagi.
- `locale en_US.UTF-8` — `cat -A` Mojibake `M-b` hanya rendering C locale, bukan korupsi file; sudah normalize UTF-8 write.

---

## 2026-10-01 — Lanjutan 7: Dedupe + nomor_petak + mtime + YOY polish (final)

### Selesai
- [x] **`refresh_petak_simple.py` dedupe** — `petak_polygon` 1003 rows → **999 distinct `kode_evapot`** (5 duplikat: `21A-1×2` dll), keep polygon terpanjang. `meta.counts{total 999, deduped 999, raw_polygon_rows 1003, distinct_evapot 999, orphan_no_rtt 195, rtt_2026 810, rtt_2025 798, join_2026 809}`. File 999 features (was 1004 with dups), dups 0, orphan 195 (polygon ada tapi belum RTT 2026 — expected, bukan error). Re-run live 999 verified.
- [x] **`spatial_intel.py` nomor_petak** — `rec{nomor_petak,tahun_rtt}` + `find_by_prefix` & `resolve_entity` substring match `kode_evapot` OR `nomor_petak` (mis. `20B` → 2 ids, `21A-1` → unique). Verified `find_by_prefix 20B count 2`, `resolve 21A-1 unique`, `find_petak 21A-1 nomor 21A-1` ok.
- [x] **mtime invalidate verified** — touch `generated_at 2026-10-01→2026-10-02` tanpa restart → `stats()` reload via `DATA.stat().st_mtime`, restore ok. `point_in_petak` centroid hit True, `neighbors 2` ok.
- [x] **Verifikasi akhir** — `profile anna` + `q:stats count 999 tahun 2026 periode 2026-10-P1 orphan 195 meta True` + **7 template `ok:true feat 2`** (bongkor/efektivitas/multi/rkap/idle/aktivitas/matriks) + `smoke PASS 121` + planing `999 deduped` + arsitektur `999 deduped`.

### Catatan
- Orphan 195 = polygon valid tapi belum ada `getah_petak` 2026 (mungkin 2025 atau belum RTT) — tetap di cadangan untuk geometri, tidak dipakai Business Map (DB WHERE `tahun_rtt=2026`).
- `n = kode_evapot` (join kunci `getah_petak/petak_polygon`), `p = rings [[lon,lat]]` flatten MultiPolygon, enrich `luas_baku/target_rkap/kode_*` untuk YOY fallback; Business Map tetap DB 100% tidak baca file untuk warna.
