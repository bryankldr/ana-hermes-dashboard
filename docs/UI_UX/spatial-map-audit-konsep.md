# SPATIAL MAP — Audit UI + Konsep (2026-10-10)

Status: KONSEP — belum eksekusi. Tunggu persetujuan user.

## 1. Struktur sekarang (audit baca kode)

File: `ui/src/map.js` 1292 baris · `map.css` 498 · `mapControl.js` 862 ·
`spatialChart.js` 399 · `spatialReport.js` 273 · `spatialMapState.js` 142 ·
`businessAdapter.js` 254.

Panel `#mapPanel` full-body absolute (`top:48px bottom:0`, z11). Tanpa
resize/drag — sudah sesuai aturan user. Lapisan dalam `.map-wrap`:

| Lapisan | Posisi | z |
|---|---|---|
| `#mapBox` Leaflet | inset:0 | 0 |
| `.map-fly-top` toolbar + filter + search | kiri-atas | 420–432 |
| `#spatialProgress` pill | bawah-tengah | 450 |
| `.map-bottom-bar` KPI + insight + meta + legend | bawah, max-height 46% | 315–318 |
| `.spatial-chart` modal | tengah | 400 |
| `.spatial-report` A4 | tengah | 410 |
| `#spatialTilesModal` | atas-tengah | 440 |
| Header panel: SPATIAL MAP + BUSINESS INTELLIGENCE + badge periode/mode | — | — |

Toolbar: biz select · kat select · filter · KPI toggle · refresh · tiles ⚙.
Filter: Waktu (bulan/tahun/periode) · Pembaharuan · Wilayah
(divre/kph/bkph/rph/tpg) + Terapkan/Reset + chips.
Bottom: 4 KPI · insight strip · meta (metric+stat) · legend.
Leaflet: basemap Satelit/Gelap · layer Petak · zoom kanan · zoom-badge
`Z+tier` · skala · search no-petak + fit ◎.

Logika bisnis tak disentuh audit ini (reloadBusiness, tier PMTiles/GeoJSON,
pin aktivitas, bridge ANA, chart/report ANA-control — semua jalan).

## 2. Temuan (masalah UI/UX)

1. **Bottom-bar sesak.** 4 penghuni (KPI+insight+meta+legend) rebut 46%
   bawah peta. Insight pill `font 8px, single-line ellipsis` — tak terbaca.
2. **Meta bar disembunyikan CSS** (`display:none`), padahal isinya
   (`N polygon · template`) satu-satunya angka mentah. Progress label
   cuma transient. User tak lihat count stabil.
3. **Legend makan tempat** kanan-bawah 30% lebar walau jarang dibaca.
4. **Filter terbuka tutupi kiri peta** (560px, 58vh) — wajar untuk modal,
   tapi tak ada tombol tutup eksplisit selain ikon filter lagi.
5. **Chart modal tengah** (560–980px) blokir interaksi peta saat terbuka.
6. **Mobile 360px:** toolbar `nowrap` 560px meluber; KPI 2×2 (sudah ada
   di ≤560px) OK; insight 8px tak terbaca; bottom-bar wrap makan >50% peta.
7. **Zoom-badge + tiles ⚙** — badge bagus (audit tier), tombol tiles
   campur urusan ops (rebuild/cron) di toolbar bisnis. Bukan bug, tapi
   salah tempat secara hirarki.

## 3. Konsep (diusulkan, belum eksekusi)

Prinsip: peta isi utama; BI diakses lewat toggle, bukan menutupi peta.
Bisnis logic nol ubah. Hanya CSS + sedikit JS toggle.

- **K1 — Insight jadi expandable.** Default 1 baris (sekarang) + klik
  untuk expand max-height 120px scroll. Font naik 8px → 11px.
  Tap lagi collapse. Tanpa ubah renderInsight.
- **K2 — Meta hidup lagi sebagai chip count.** Hapus `display:none`
  meta, tampilkan ringkas `N polygon · template` (font 10px, pill kecil
  di samping legend). Metric/stat tetap update seperti sekarang.
- **K3 — Legend collapsible.** Default ciut jadi tombol `ⓘ` 30×30
  kanan-bawah; klik expand. Pola sama kayak `spatialToolsToggle`.
- **K4 — KPI default collapse di mobile.** `≤780px` kpiBox mulai
  `collapsed`; tombol KPI tetap toggle. Desktop tak berubah.
- **K5 — Toolbar mobile ikon rapat.** `≤560px`: select biz/kat
  `max-width 40vw`, padding 5px 8px; tombol tetap 30px. Tak ada
  perubahan struktur.
- **K6 — Tiles ⚙ pindah ke header panel** (sebelah badge mode), keluar
  dari toolbar bisnis. Modal tetap sama. Ops terpisah dari BI.
- **K7 — Chart/report tak disentuh.** Milik ANA full-control; modal
  tengah tetap.

Urutan eksekusi (setelah setuju): K1+K2+K3 (satu patch CSS+JS kecil) →
K4+K5 (media query saja) → K6 (pindah tombol). Verifikasi: screenshot
CDP desktop 1440 + mobile 390 sebelum/sesudah.

## 4. Bukan bagian konsep ini

- Engine peta (Leaflet→MapLibre), template bisnis, tier PMTiles,
  pin aktivitas, bridge ANA — tak disentuh.
- Panel lain HUD — tak disentuh.
