---
title: Contoh Laporan Tren Bulanan Mei 2026 vs April 2026
created: 2026-10-04
updated: 2026-10-04
type: query
tags: [eksekutif, interpretasi, kph, bkph, petak, produksi, target, aktivitas, dashboard, spasial, komparasi, tren, periode, evidence]
sources: [simoge_db.py, ana_simoge_tool.py]
---

# Contoh Laporan Tren — Mei 2026 vs April 2026 + YoY (Golden Example)

**Fungsi halaman ini:** referensi gaya presentasi tren ANNA. Mendampingi
[[contoh-laporan-eksekutif-kph-barat]] (potret satu bulan): halaman itu
menjawab "kondisi saat ini", halaman ini menjawab "berubah ke mana".
Tiru strukturnya, jangan tiru angkanya (snapshot sandbox 2026-10-04).

**Intent asal:** *"Bagaimana tren produksi Mei dibanding April, dan YoY?"*
→ tool: dua panggilan `produksi_per_wilayah` (bulan 4 dan 5) +
`aktivitas_agregat` (bulan 4 dan 5) + satu panggilan tahun lalu untuk YoY.
Perbandingan antar-periode = COMPARISON; arah gerak + makna = INTERPRETATION
([[klasifikasi-fakta]], [[disiplin-evidence]]).

## 0. Replay (periode + template + param)

| # | Template | Param | Hasil |
|---|---|---|---|
| 1 | `produksi_per_wilayah` | `tahun=2026, bulan=5, periode=0` | 5 baris, total 909.725 kg |
| 2 | `produksi_per_wilayah` | `tahun=2026, bulan=4, periode=0` | 5 baris, total 680.617 kg |
| 3 | `aktivitas_agregat` | `tahun=2026, bulan=5, periode=0, grup_by=aktivitas` | 8.322 kejadian |
| 4 | `aktivitas_agregat` | `tahun=2026, bulan=4, periode=0, grup_by=aktivitas` | 7.765 kejadian |
| 5 | `produksi_per_wilayah` | `tahun=2025, bulan=5, periode=0` | 1 baris NULL, aktual 0,0 kg |
| 6 | `aktivitas_agregat` | `tahun=2025, bulan=5, periode=0, grup_by=aktivitas` | 0 baris |
| 7 | `target_pct` | `tahun=2026, bulan=5, periode=0` → 42,0; bulan=4 → 32,0 | naik 10 poin |
| 8 | `data_freshness` | — | terakhir 2026-09-23 |

Mei 2026 bulan tutup (data final). Panggilan contoh tanpa `kode_kph`
karena sandbox satu KPH; untuk multi-KPH tambah `kode_kph=31211`.

## 1. Executive Summary

Produksi KPH naik 680.617 kg (April) → 909.725 kg (Mei): +229.108 kg
(+33,7%) [COMPARISON #1+#2]. Achievement ikut naik 57,80% → 58,86%
(+1,06 poin) [DERIVED]. Kenaikan merata di 5 BKPH — terbesar relatif di
Licin (+46,4%) [COMPARISON]. Aktivitas naik 7.765 → 8.322 (+7,2%)
[COMPARISON #3+#4] — produksi tumbuh lebih cepat dari aktivitas, selisih
yang layak dicatat, bukan disimpulkan [INTERPRETATION batas — lihat
[[korelasi-vs-kausasi]]]. YoY tidak dapat dihitung: data 2025 kosong
(section 9).

## 2. KPI Tren

| KPI | Apr 2026 | Mei 2026 | Δ |
|---|---|---|---|
| Produksi total | 680.617 kg | 909.725 kg | +229.108 (+33,7%) |
| Achievement | 57,80% | 58,86% | +1,06 poin |
| Aktivitas total | 7.765 | 8.322 | +557 (+7,2%) |
| Indikator `target_pct` | 32,0 | 42,0 | +10 poin |
| BKPH naik (aktual) | — | 5 dari 5 | merata |

Achievement KPH = total aktual / total target se-BKPH, bukan rata-rata
persen [DERIVED — denominator eksplisit, [[aturan-denominator]]].

## 3. Produksi per BKPH (April → Mei)

| BKPH | Apr aktual | Mei aktual | Δ kg (Δ %) | Apr ach | Mei ach (Δ pp) |
|---|---|---|---|---|---|
| GLENMORE | 252.256 | 340.456 | +88.200 (+35,0%) | 56,20 | 57,79 (+1,59) |
| KALISETAIL | 197.276 | 260.843 | +63.567 (+32,2%) | 60,80 | 61,25 (+0,45) |
| KALIBARU | 97.912 | 126.080 | +28.168 (+28,8%) | 75,18 | 73,76 (−1,42) |
| ROGOJAMPI | 80.699 | 105.502 | +24.803 (+30,7%) | 58,71 | 58,48 (−0,23) |
| LICIN | 52.474 | 76.844 | +24.370 (+46,4%) | 38,41 | 42,86 (+4,45) |

Dua BKPH (Kalibaru, Rogojampi): volume naik tapi achievement turun —
target tumbuh lebih cepat dari aktual. Itu bukan penurunan kinerja,
itu denominator bergerak [INTERPRETATION, [[aturan-denominator]]].
Visual: `show_spatial_chart` tipe trend per BKPH (April→Mei) +
`show_on_map("produksi_per_wilayah" ...)` per bulan
([[presentasi-chart]], [[presentasi-spasial]]).

## 4. Aktivitas per Jenis (April → Mei)

| Aktivitas | Apr | Mei | Δ | Petak Apr → Mei |
|---|---|---|---|---|
| Quare | 2.654 | 2.851 | +197 (+7,4%) | 607 → 669 |
| Semprot CAS | 2.371 | 2.505 | +134 (+5,7%) | 576 → 600 |
| Budaya Bersih | 1.474 | 1.712 | +238 (+16,1%) | 379 → 433 |
| Naik Batok | 979 | 954 | −25 (−2,6%) | 297 → 296 |
| Kerok | 287 | 300 | +13 (+4,5%) | 135 → 136 |

Budaya Bersih tumbuh paling cepat (+16,1%) [COMPARISON]. Naik Batok
satu-satunya turun — kecil (−2,6%), catat saja, jangan dramatisasi.
Satu aktivitas ≠ satu petak ([[metrik-aktivitas]]).

## 5. Ranking Berubah

Achievement April: Kalibaru > Kalisetail > Rogojampi > Glenmore > Licin.
Achievement Mei: Kalibaru > Kalisetail > Rogojampi > Glenmore > Licin —
urutan sama, jarak berubah: Licin memangkas gap ke rata-rata KPH dari
−19,4 poin menjadi −16,0 poin [COMPARISON]. Ranking tak bergerak tapi
cerita bergerak — tren ada di delta, bukan di posisi
([[semantik-ranking]]).

## 6. Spatial Findings

Peta Mei vs April: `show_on_map("kph_summary_map", tahun=2026,
aggregated_level=kode_bkph, kode_kph=31211)` — struktur petak
tahun-based, identik kedua bulan; yang berubah angka produksinya.
Untuk narasi tren di peta: screenshot/GIF dua bulan berdampingan, bukan
satu peta (satu peta = satu periode — [[presentasi-spasial]],
[[konteks-waktu]]).

## 7. Anomaly / Variance

- Licin: pertumbuhan relatif tertinggi (+46,4%) dari basis terendah —
  efek basis kecil, bukan keajaiban. Sampaikan keduanya
  ([[absolut-vs-relatif]]).
- Kalibaru: achievement turun 1,42 poin meski volume +28,8% —
  anomali semu (denominator target), jelaskan, jangan sembunyikan.
- Produksi (+33,7%) tumbuh ±4,7× aktivitas (+7,2%) — selisih dicatat
  sebagai HYPOTHESIS yang butuh uji (rendemen? pencatatan?),
  bukan kesimpulan.

## 8. Interpretation

Kenaikan Mei merata lintas BKPH + didukung kenaikan aktivitas: pola
KPH, bukan satu wilayah [INTERPRETATION dari #1–#4]. Kalimat yang
dilarang: "kenaikan aktivitas menyebabkan produksi naik" — dua deret
bergerak searah ≠ sebab-akibat ([[model-hipotesis]]: tulis Hypothesis /
Supporting / Missing / How To Test bila diajukan).

## 9. Data Limitation

- YoY tidak dapat dihitung: `produksi_per_wilayah(tahun=2025, bulan=5)`
  = 1 baris NULL aktual 0,0 kg; `aktivitas_agregat(tahun=2025, bulan=5)`
  = 0 baris [FACT #5–#6]. Sandbox hanya berisi data 2026. Bila user
  meminta YoY: katakan "data 2025 kosong, YoY tidak tersedia", jangan
  hitung dari nol (0 kg bukan baseline — [[data-hilang]]).
  Bila data 2025 tersedia nanti, rumusnya identik section 2–3 dengan
  `tahun=2025` sebagai kolom pembanding.
- Mei bulan tutup → angka final; jangan campur dengan bulan berjalan.
- Struktur petak (`kph_summary_map`) tahun-based: sama untuk April dan
  Mei, bukan data bulanan.
- `target_pct` (32,0 → 42,0) indikator template tersendiri, bukan
  achievement produksi — jangan dijumlah-silangkan.
- Section penyadap tidak ditarik; pengisinya
  `penyadap_productivity(tahun=2026, bulan=5, periode=0)`.

## 10. Suggested Next Analysis

1. Tarik `penyadap_productivity` April vs Mei — uji HYPOTHESIS selisih
   tumbuh produksi vs aktivitas.
2. Lanjut deret ke Juni–September: apakah kenaikan Mei awal tren atau
   puncak musiman ([[konteks-waktu]]).
3. Drill-down Licin: basis kecil + gap terbesar — pantau dua bulan
   ke depan sebelum simpulkan perbaikan.

## Link Balik

[[contoh-laporan-eksekutif-kph-barat]], [[struktur-laporan-eksekutif]],
[[aturan-summary-eksekutif]], [[model-insight-bisnis]],
[[klasifikasi-fakta]], [[disiplin-evidence]], [[tool-bisnis-anna]],
[[presentasi-chart]], [[presentasi-spasial]], [[konteks-waktu]],
[[periode]], [[population-awareness]], [[kph]], [[bkph]]
