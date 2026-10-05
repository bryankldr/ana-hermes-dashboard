# 2nd Planning — Refaktor Panel SPATIAL MAP (Profil ANNA — PT Perhutani)

> **Scope TERBATAS:** hanya panel `SPATIAL MAP`. JANGA N ubah panel lain, layout global, framework, atau Hermes core. Extend existing, bukan rebuild dashboard.

---

## 1. Profil ANNA

**Identitas:** `~/.hermes/profiles/anna` (folder lowercase, env `HERMES_PROFILE=anna` — Linux case-sensitive).

**SOUL (`~/.hermes/profiles/anna/SOUL.md`):**

> ANNA = business intelligence assistant — **dashboard owns data, ANNA owns interpretation**. Bantu operator paham data, eksplor dashboard, kontrol filter/visualisasi, analisis pola/anomali. Bedakan fakta / analisis / asumsi / hipotesis. Jangan karang data/rule. Paham 4 domain: Evaluasi Petak, Aktivitas, Produksi, Matriks. Prime directive: *paham yang operator lihat → paham yang ingin diketahui/diubah → bantu paham makna data.*

**Persona dashboard (`persona.md`):** `SIMOGE Business Specialist` — mode `asisten` (TTS 1-2 kalimat) & `coding` (markdown, path exact). Bahasa utama Indonesia.

**Perusahaan:** PT Perhutani — industri produksi getah pinus. ANNA = asisten perusahaan, spesialis RTT, penyadap, andil, target RKAP RO/NPS, drum.

---

## 2. Tujuan Refaktor

`SPATIAL MAP` jadi **Business Map Workspace** yang tetap terlihat sama, tapi pintar:

1. Pilih business category (Petak / Aktivitas / Produksi / Matriks) di dalam panel.
2. Filter khusus panel: Bulan, Tahun, Periode (P1 1-15 / P2 16-akhir), DIVRE, KPH, BKPH, RPH, TPG — hanya pengaruhi SPATIAL MAP, bukan global.
3. Polygon diwarnai & difilter berdasarkan business state (efektivitas, RKAP, idle/bongkor).
4. Terima perintah natural language via ANNA, dan beri context balik agar ANNA bisa jelaskan data yang tampil.

---

## 3. Kontek Bisnis (ringkas — sumber: `2nd_kontek_bisnis.md` + `simoge-business` skill)

**Join kunci:**
- `getah_penyadap ↔ getah_andil` via `id_penyadap`
- `getah_andil ↔ getah_petak` & `petak_polygon` via `kode_evapot` (`kode_petak` NULL)
- Semua tabel punya `kode_divre, kode_kph, kode_bkph, kode_rph, kode_tpg`
- `getah_rencana_aktivitas ↔ getah_aktivitas_sadap` via `id_rencana`; ke `getah_penyadap` & `getah_aktivitas_penerimaan` via `id_penyadap`
- `getah_drum` **jangan** pakai `id_penyadap` — via `nomor_drum` ke `getah_aktivitas_penerimaan`; via `nomor_pengangkutan` ke `getah_pengangkutan`; via `nomor_perni` ke `getah_perni`; via `id_mutu` ke `getah_mutu`
- `getah_target_ro_nps.tahun` seperti `getah_petak.tahun_rtt`; `bulan` 1-12; `ro_periode_1/2, nps_periode_1/2` = persen per periode × `target_rkap` (contoh: 697,6 kg × 3,5% = 24,4 kg)

**Periode:** P1=1-15, P2=16-akhir. "P1 saat ini"=P1 bulan ini tahun ini. "P1 sampai P2"=akumulasi bulan 1 s/d bulan ini. "sampai dengan"=1 s/d hari ini.

**Definisi:**
- Petak **bongkor** = tanpa penyadap sama sekali (`NOT EXISTS getah_andil`). Andil bongkor = tanpa aktivitas 2+ bulan.
- **Idle** = ada aktivitas periode lalu, tak ada periode ini. **Aktif** = ada aktivitas periode ini.
- **Efektivitas:** merah=bongkor, kuning=`SUM(luas_andil) < luas_baku`, hijau=≥ luas_baku.
- **RKAP:** merah 0-25%, oranye 26-50%, kuning 51-75%, hijau 76-100%, emas >100%.
- Penyadap kurang produktif = aktif tapi `berat_penerimaan < target` (target prorata `luas_andil/luas_baku` × target periode).

**Data live 2026:** RTT 810 petak 2026 (798 thn 2025) di `kph_bwb_sandbox2`; `petak_polygon` 1003 polygon; `petak_simple.json` kini **999 features (deduped dari 1003 raw rows → 999 distinct kode_evapot)** wrapper `{meta,features}` harian selaras DB (generate WIB `scripts/refresh_petak_simple.py`, arsip `ui/data/snapshots/petak_YYYY-MM-DD.json` untuk YOY). `DIVRE=2` satu nilai, `KPH=31211` satu nilai (Banyuwangi Barat), `BKPH` 5, `RPH` ~10, `TPG` ~10. Business Map tetap sumber DB 100% — cadangan hanya identitas & fallback YOY.

---

## 4. Aturan Paling Penting — Jangan Merusak

- Jangan ubah/rename/pindah/resize SPATIAL MAP keluar batasnya.
- Panel lain HARUS tetap: PERFORMANCE BRIEFING, MISSION KANBAN, VAULT STATUS, ACTIVE REPOSITORIES, EVENT STREAM, INTELLIGENCE SURFACE, SYSTEM MATRIX, AGENT PIPELINE, ANDROID AVD, CHAT/COMMAND, HUD lain.
- Jangan global refactor, ganti framework/layout system, atau tambah halaman/dashboard baru.
- Jangan ubah fungsi Hermes (chat, voice, terminal, tools, memory, repo, agent).
- Incremental: `EXTEND SPATIAL MAP` saja. Jika butuh ubah di luar scope → STOP, jelaskan file/risiko dulu.

---

## 5. Arsitektur Business Data (wajib)

```
DATABASE (MariaDB getah_*)
    ↓
BUSINESS DATA ENGINE (skill simoge-business: simoge_db.py + ana_simoge_tool.py)
  query/join/aggregation/rule/calc/geospatial — Hermes owns SQL
    ↓
PROCESSED BUSINESS DATA (rows + polygon GeoJSON + warna bisnis)
    ↓
SPATIAL MAP STATE (filters + business → params → template)
    ↓
MAP / POLYGON (LeafletAdapter di mapControl.js + map.js, Esri Dark/Satelit tetap)
    ↓
ANA (profile anna — interpretasi, ubah state via action, jelaskan)
```

ANNA **TIDAK** query DB langsung. Satu panggilan `show_on_map(template, params)` atau `call_simoge_tool` via skill; dashboard yang POST GeoJSON ke `map_store`.

**Template yang dipakai:**
- Evaluasi Petak → `petak_efektivitas_map` (merah/kuning/hijau), `petak_bongkor_map` (merah), `idle_petak`, `petak_multi_penyadap`
- Evaluasi Aktivitas → `penyadap_aktivitas`, `petak_penyadap`, `produksi_aktiv`
- Evaluasi Produksi → `rkap_map` / `rkap_achievement` (merah/oranye/kuning/hijau/emas), `produksi_year_to_date`, `penyadap_productivity`
- Evaluasi Matriks → kombinasi (luas_andil vs luas_baku, target vs aktual, aktivitas vs produksi) — hanya dari data yang tersedia

Warna otomatis: `LeafletAdapter.WARNA_STYLE` + `_resolveStyle(properties.warna)` — template `*_map` sudah kirim `warna/kategori/pencapaian_pct`.

---

## 6. Filter & Business Category — Inside SPATIAL MAP Only

**Filter strip (collapsible, scoped):** Bulan | Tahun | Periode (P1/P2) | DIVRE | KPH | BKPH | RPH | TPG.
- Default: Tahun 2026, Bulan ini, P1/P2 sesuai tanggal, wilayah kosong (= semua).
- Perubahan hanya fetch ulang template SPATIAL MAP, tidak sentuh panel lain. State terisolasi.

**Business selector (compact dropdown di header panel):**
- Evaluasi Petak — layer: Semua / Bongkor / Idle / Tanpa Penyadap / Multi Penyadap (filter via `set_filter` + warna)
- Evaluasi Aktivitas — state dari Business Data Engine yang tersedia
- Evaluasi Produksi — target / aktual / gap / pencapaian
- Evaluasi Matriks — hubungan antar dimensi (petak vs penyadap, target vs aktual, luas vs produksi)

Semua kontrol pakai komponen/style existing (`tokens.css` neon/border, `map.css`).

---

## 7. Dashboard State — Isolasi

```js
// ui/src/spatialMapState.js — NEW, isolated
SpatialMapState {
  business: 'petak' | 'aktivitas' | 'produksi' | 'matriks'
  filters: { bulan, tahun, periode, divre, kph, bkph, rph, tpg }
  dataset: { template, params, rows, row_count }
  layers: { kategori: visible }   // subset polygon visible
  selection: id | null
  metrics: { shown, total, luas, warna_counts }
}
```

- Satu sumber, emit `SPATIAL_MAP_CHANGED` via `bus.js`. `mapControl.js` hanya baca, tidak duplikat.
- `map.js` wiring: `SpatialMapState → businessAdapter → /api/simoge/show_on_map → set_features`.
- Tidak boleh trigger re-render panel lain.

**Interaksi ANNA:** baca `GET /api/map/state` + metrics; ubah via `POST /api/map/command` atau `show_on_map`. Contoh: "Tampilkan petak bongkor" → `business=petak, filter=kategori:bongkor` → `petak_bongkor_map`. "Berapa luas bongkor tampil?" → baca `metrics.luas` — jika tak ada, jawab jujur tanpa karang.

---

## 8. UI/UX

- Visual tetap HUD existing (neon cyan, border, font mono/tech, radius 6-8). Reuse `map-tools` pattern.
- Ruang terbatas → dropdown, popover, compact toolbar, collapsible filter, overlay, metric bar tipis di bawah map. Jangan perbesar `#mapPanel` mengorbankan panel lain.
- Pertahankan: search `cari no petak...`, zoom control, layer control (Satelit/Gelap + Petak), polygon visualization, stats.

---

## 9. File Scope

**ALLOWED (minimal):**
- `ui/src/spatialMapState.js` — NEW
- `ui/src/businessAdapter.js` — NEW (facade `/api/simoge/*`, filter→params, template mapping)
- `ui/src/map.js` — patch body + wiring (reuse `createLeafletControl`) — **Business Map pakai DB 100%** via `show_on_map`; tidak baca petak_simple untuk warna bisnis
- `ui/styles/map.css` — tambah `.spatial-toolbar`, `.spatial-filters`, `.metric-bar`
- `server.py` — tambah `GET /api/spatial/filters` (distinct wilayah) bila perlu; else reuse template
- `mapControl.js` — hanya tambah helper `applyBusinessStyle` jika dibutuhkan
- `spatial_intel.py` — toleran wrapper `{meta, features}` + `stats()` kembalikan meta (backward compat array lama)
- `scripts/refresh_petak_simple.py` — NEW generator harian `kph_bwb_sandbox2 → petak_simple.json` (WIB), arsip `ui/data/snapshots/petak_YYYY-MM-DD.json`
- `ui/data/petak_simple.json` — override harian jadi `{meta, features}` (identitas periode); `snapshots/` untuk YOY ANNA

**NOT ALLOWED:** redesign dashboard/HUD, ubah panel lain, layout global, chat/voice UI, Hermes core, memory/repo/terminal, unrelated business logic. Jangan ubah `map.js` bisnis jadi baca petak_simple — tetap DB 100%.

---

## 10. Tahapan Implementasi

**Fase 0 — Inspect (DONE):** struktur project, SPATIAL MAP existing (Leaflet Esri, `mapStore` queue), Business Data Engine (`simoge-business` 23 template), polygon flow, API `/api/simoge/*` & `/api/map/*`. Fix `HERMES_PROFILE=ANNA→anna`.

**Fase 1 — State & Adapter:** buat `spatialMapState.js` + `businessAdapter.js`, unit assert kecil.

**Fase 2 — UI SPATIAL MAP:** patch `map.js` toolbar+filters collapsible, `map.css` compact — tetap di dalam panel, style existing.

**Fase 3 — Data → Map:** wiring adapter → `show_on_map` → `set_features` + `WARNA_STYLE`, metric bar, legenda. ANNA baca state & jelaskan.

**Fase 4 — Verifikasi & Regression:** semua panel tampil, chat/voice ok, search/zoom/layer/polygon tetap, no console error, no layout shift panel lain. Jika perubahan berisiko → revert.

**Fase 5 — Cadangan Evaluasi Harian (petak_simple.json selaras bisnis):** wrapper `{meta, features}` harian dari DB (WIB `generated_at`, `tahun_rtt`, `periode P1/P2`, `counts`), `spatial_intel` toleran, `scripts/refresh_petak_simple.py` + arsip `snapshots/petak_YYYY-MM-DD.json` untuk YOY ANNA. Business Map tetap DB 100% (map.js tidak baca cadangan untuk polygon bisnis).

---

## 11. Risiko & Mitigasi

- Filter wilayah single-value (DIVRE/KPH) → tampilkan tetap, disable yang tak relevan, jangan hardcode.
- `periode` salah hitung → pakai `period_bounds` skill, jangan reinvent.
- Race `set_features` dobel → debounce + `clear_features` sebelum push baru.
- ANNA karang data → kontrak: jika metric tak ada, jawab "data tidak tersedia".

---

## 12. Kriteria Selesai

Dashboard terlihat sama; bedanya SPATIAL MAP bisa: pilih business, pakai 8 filter, polygon sesuai business state + warna benar, terima perintah ANNA, beri context untuk ANNA jelaskan.

## 13. Cadangan Evaluasi Harian — petak_simple.json selaras bisnis (amanat baru)

**Risiko (selesai — lama 2273 → kini 999 deduped):** `petak_simple.json` lama `{n,p}` tidak sama dengan kondisi `kph_bwb_sandbox2` (810 RTT 2026, 1003 polygon, + andil/aktivitas/realisasi/target) — fix: wrapper `{meta,features}` **999 distinct `kode_evapot`** harian selaras DB (deduped dari 1003 raw rows, 195 orphan tanpa RTT 2026, WIB `scripts/refresh_petak_simple.py`, arsip `snapshots/petak_YYYY-MM-DD.json`). ANNA YOY kini jujur pakai `meta.generated_at` + `counts.orphan_no_rtt`.

**Aturan:**
1. **Format baru `{meta, features}`** — `meta{generated_at WIB ISO, source:"kph_bwb_sandbox2", tahun_rtt, periode "YYYY-MM-P1/P2", counts{total,with_polygon,rtt_2026,rtt_2025}, generator, version}` + `features[{n,p,tahun_rtt,kode_divre/kph/bkph/rph/tpg,luas_baku,target_rkap}, …]`. Loader toleran: array lama `[{n,p}]` tetap kebaca (wrapper otomatis).
2. **Update HARIAN** — tiap hari override `ui/data/petak_simple.json` dengan snapshot evaluasi hari ini (periode = tgl hari ini P1 1-15 / P2 16-akhir). Snapshot lama diarsip `ui/data/snapshots/petak_YYYY-MM-DD.json` untuk YOY.
3. **Business Map pakai DB 100%** — `map.js → businessAdapter → /api/simoge/show_on_map → simoge_db 7 _map → map_store → Leaflet WARNA_STYLE`. Cadangan tidak dipakai untuk warna/filter bisnis, hanya cadangan.
4. **ANNA YOY** — bila tanya "tahun lalu vs tahun ini" atau DB lambat, ANNA baca `meta+features` via `/api/spatial/stats` & file wrapper dan sebut `generated_at` + `tahun_rtt` jujur (jangan karang).
5. **Scope terbatas** — hanya `petak_simple.json` + `spatial_intel.py` + generator `scripts/refresh_petak_simple.py`. `map.js` bisnis tetap DB 100%.

**Prinsip akhir:** DO NOT REBUILD, DO NOT REDESIGN, DO NOT REFACTOR UNRELATED — EXTEND ONLY SPATIAL MAP, PRESERVE ALL EXISTING. Cadangan harian kecil, aman, reversible.
