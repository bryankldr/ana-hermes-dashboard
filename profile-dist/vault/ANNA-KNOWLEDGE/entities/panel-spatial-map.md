---
title: Panel SPATIAL MAP
created: 2026-10-03
updated: 2026-10-04
type: entity
tags: [dashboard, spasial, peta, intent]
sources: [raw/articles/simoge-business-ontology.md]
---

# Panel SPATIAL MAP

Panel peta bisnis di HUD `ana-hermes-dashboard` (`#mapPanel`, rail kanan,
port 8730). Satu-satunya panel yang ANNA kendalikan penuh isinya: polygon,
viewport, filter, pencarian, dan chart di dalamnya. Frontend hanya render;
state milik server (`map_store.py`, `spatial_chart_store.py`, session memory).

## Inventaris komponen (13)

| # | Komponen | Selector | Fungsi |
|---|---|---|---|
| 1 | Container | `#mapPanel` | Wadah HUD via `LayoutManager`; `z-index` paling bawah. Posisi/ukuran milik operator, bukan ANNA |
| 2 | Header BI | `.map-fly-head` | Judul `BUSINESS INTELLIGENCE` + badge periode (`YYYY-MM-P1/P2`) + badge mode CODING/ASISTEN |
| 3 | Peta | `#mapBox` (Leaflet) | Tile Satelit/Gelap + skala; center awal `[-8.1776,114.1261]` zoom 11; `petakLayer` + pin aktivitas |
| 3b | Tombol pengaturan tiles | `#spatialTilesBtn` (⚙) + modal `#spatialTilesModal` | Rebuild manual (`GET /api/tiles/rebuild`) + cron harian (`POST /api/tiles/cron` status/enable/disable, marker `ana-pmtiles-daily`, default `10 6 * * *`); status modal = PMTiles bytes/mtime + NDJSON baris + baris cron + log tail (`GET /api/tiles/status`) |
| 4 | Toolbar bisnis | `.map-fly-top` (`spatialBiz`) | Dropdown EVALUASI: petak / aktivitas / produksi / matriks |
| 5 | Layer petak | `spatialKat` | Kategori layer petak; hanya tampil untuk bisnis petak/aktivitas |
| 6 | Panel Filter | `#spatialFilters` | Waktu (bulan/tahun/periode) + wilayah (DIVRE/KPH/BKPH/RPH/TPG) + tahap pembaharuan + Terapkan/Reset |
| 7 | Chips filter | `spatialChips` | Filter aktif, hapus per chip atau semua |
| 8 | Pencarian petak | `mapSearch` + `mapFit` | Cari nomor petak (Enter = `select_feature`), tombol fit ◎ |
| 9 | Strip KPI | `#spatialKpi` | 4 kartu: Total petak, Bongkor, Perlu perhatian, Terpenuhi |
| 10 | Insight | `#spatialInsight` | Narasi ANNA (mode asisten) atau `template·feat·warna` (mode coding) |
| 11 | Meta | `#mapMetric + #mapStat` | Metric polygon baru/total + status template |
| 12 | Legend | `#mapLegend` | Warna status per domain + atribusi Esri/Maxar |
| 13 | Progress | `#spatialProgress` | Bar muat; sumber kebenaran `MAP_FEATURES_LOADED`, watchdog 3 dtk |
| — | Chart box | `#spatialChartWrap` | Modal tengah: multi-chart + KPI + narasi; ANNA kontrol 100% via `/api/spatial/chart` |
| — | Laporan box | `#spatialReportWrap` | Dokumen N halaman siap cetak: `Unduh` = `window.print()`, `Tutup` = POST `visible:false`; ANNA kontrol 100% via `/api/spatial/report` |

## Op vs komponen (kendali langsung ANNA)

Whitelist `map_store.py` `ALLOWED_OPS`; op `spatial_*` di-intercept handler `map.js`, bukan method Leaflet langsung (ANNA dilarang sentuh `map.flyTo` / `querySelector`).

| Op | Komponen yang dikendalikan |
|---|---|
| `set_view`, `fit_bounds`, `fit_all`, `reset_view` | 3 Peta (viewport) |
| `set_basemap` | 3 (Satelit/Gelap) |
| `set_layer_visibility`, `toggle_layer`, `get_layers` | 3, 5 (layer) |
| `select_feature`, `get_selected`, `clear_selection` | 8 (hasil pencarian + seleksi) |
| `highlight_features`, `clear_highlights` | 3 (sorot polygon) |
| `set_filter`, `clear_filter` | 6, 7 (filter visual) |
| `set_features`, `clear_features` | 3 (dataset polygon + auto-fit) |
| `spatial_set {business, filters, warna, template}` | 4, 5, 6, 7 (toolbar + drawer + template eksplisit) |
| `spatial_reload` | = tombol Muat: jadwalkan `reloadBusiness` |
| `spatial_get` | baca: `collectState()` + spatial state + jumlah polygon |
| `spatial_search {q}` | 8 (cari petak → seleksi) |
| `POST /api/spatial/chart` | Chart box: `visible`, `title`, `kpis[]`, `charts[]`, `narration`, `evidence` |
| `POST /api/spatial/report` | Laporan box: `visible`, `title`, `subtitle`, `pages[]{title,subtitle,blocks[]}`, `evidence[]`, `meta{}` |

Jalur cepat: `show_on_map(template, params)` = query + `set_features` + auto-fit satu panggilan; `show_for_intent(intent, kw)` = chart sesuai intent; `present_section(rv, section, with_map)` = siar review per section. Lihat [[tool-bisnis-anna]].

## Tak langsung (turunan dataset, bukan ditulis ANNA)

Komponen 9 KPI, 10 Insight, 11 Meta, 12 Legend, 13 Progress dihitung frontend dari dataset yang ANNA dorong (`renderKPIs`, `updateLegend`, `renderInsight`, `MAP_FEATURES_LOADED`). ANNA mengendalikan lewat hulu — pilihan template + filter — bukan menulis angkanya langsung. Komponen 1 posisi/ukuran milik operator via `LayoutManager`.

## Guard anti-loop `spatial_set`

Server meng-echo `show_on_map` milik `reloadBusiness` sendiri sebagai `spatial_set`. Tanpa guard: reload → show → set → reload berulang, polygon tampil-hilang lalu berhenti setengah jalan. Handler membandingkan state kanonis (business + filters, int/str dinormalisasi jadi string) dan bila identik mengembalikan `{accepted, noop}` tanpa reload. Konsekuensi: bila ANNA mengirim state sama dengan yang tampil, hasilnya noop — itu benar, bukan bug.

## Domain evaluasi (4 template `_map`)

Petak (`petak_bongkor_map`, merah/kuning/hijau), Aktivitas (`aktivitas_petak_map`, hijau/kuning/merah + pin Pem1 cyan/Pem2 oranye/Pem3 merah), Produksi (`rkap_map`, merah→emas per pencapaian), Matriks (`matriks_map`, coverage·pohon·andil·produksi). Filter wilayah allowlist server-side; periode P1 = tgl 1–15, P2 = 16–akhir. Detail warna di Legend panel, bukan dihafal di sini.

## Tier zoom render (aturan 2026-10-04)

`_maybeSwitchTier(zoom)` di `ui/src/map.js`: Z ≤ 11 = PMTiles polygon
saja (tanpa analisa/pin, base netral semua business); Z ≥ 12 = GeoJSON
analisa + pin. Badge panel `Z{n}·PMTiles/GeoJSON`. Pin aktivitas selalu
hidden di Z < 12 meski data tetap dimuat. Enforce berjalan untuk SEMUA
business tanpa return dini — polygon business non-petak menutupi PMTiles
di Z rendah bila return dini (`biz!=='petak'`). Lihat
[[arsitektur-skala-peta]].

## Berhubungan dengan

[[panel-dashboard]], [[tool-bisnis-anna]], [[operasi-dashboard]], [[presentasi-spasial]], [[inteligensi-spasial]], [[semantik-dashboard]], [[drill-down-wilayah]].
