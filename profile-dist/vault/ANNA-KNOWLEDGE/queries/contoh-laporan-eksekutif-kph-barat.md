---
title: Contoh Laporan Eksekutif KPH Banyuwangi Barat
created: 2026-10-04
updated: 2026-10-04
type: query
tags: [eksekutif, interpretasi, kph, bkph, petak, produksi, target, aktivitas, dashboard, spasial, komparasi, tren, periode, evidence]
sources: [simoge_db.py, ana_simoge_tool.py]
---

# Contoh Laporan Eksekutif — KPH Banyuwangi Barat (Golden Example)

**Fungsi halaman ini:** referensi gaya presentasi ANNA. Satu laporan lengkap
end-to-end: intent → template → angka → narasi → visual. Tiru strukturnya,
jangan tiru angkanya (angka = snapshot sandbox 2026-10-04).

**Intent asal:** *"Buatkan laporan eksekutif KPH Banyuwangi Barat."*
→ tool: `run_business_review` + `present_section` per section
(disela operator tanpa restart). Struktur 13 section ikut
[[struktur-laporan-eksekutif]]; aturan summary ikut
[[aturan-summary-eksekutif]]; rantai insight ikut [[model-insight-bisnis]].

## 0. Replay (periode + template + param)

| # | Template | Param | Hasil |
|---|---|---|---|
| 1 | `kph_summary_map` | `tahun=2026, aggregated_level=kode_bkph, kode_kph=31211` | 5 baris BKPH |
| 2 | `produksi_per_wilayah` | `tahun=2026, bulan=9, periode=0` | 5 baris aktual vs target |
| 3 | `aktivitas_agregat` | `tahun=2026, bulan=9, periode=0, grup_by=aktivitas` | 5 jenis aktivitas |
| 4 | `produksi_year_to_date` | `tahun=2026` | YTD 1,20 jt kg |
| 5 | `data_freshness` | — | terakhir 2026-09-23 |
| 6 | `bongkor_per_wilayah` | `tahun=2026, kode_kph=31211` | 267 petak tanpa andil |

Periode data: September 2026 penuh (`periode=0`, bukan P1+P2 manual).
Tanggal laporan: 2026-10-04. Data terakhir 11 hari lalu → badge `basi`,
katakan tanggalnya, jangan janji "hari ini".

## 1. Executive Summary

KPH Banyuwangi Barat (809 petak, 5.918 ha, 5 BKPH): efektivitas andil
68,64% [FACT #1], produksi September 1,20 jt kg = 38,6% target bulanan
[DERIVED #2+#5: 1.201.219 / 3.109.600]. Kesenjangan terbesar di BKPH Licin
(achievement 24,9% vs rata-rata KPH 38,6%) [COMPARISON]. Fokus analisis
lanjutan: Licin — efektivitas andil 46,29% + achievement terendah, dua
sinyal independen menunjuk wilayah yang sama [INTERPRETATION, bukan klaim
sebab — lihat [[korelasi-vs-kausasi]]].

## 2. KPI Utama

| KPI | Angka | Sumber |
|---|---|---|
| Total petak / luas baku | 809 / 5.918,37 ha | FACT #1 |
| Efektivitas andil rata-rata | 68,64% | FACT #1 |
| Produksi Sept 2026 | 1.201.219 kg | DERIVED sum #2 |
| Achievement vs target Sept | 38,6% | DERIVED #2 |
| Produksi YTD 2026 | 1.200.516 kg / 10.323 aktivitas / 743 petak | FACT #4 |
| Petak tanpa andil (bongkor andil) | 267 | FACT #6 |

## 3. Kondisi Petak (efektivitas andil per BKPH)

| BKPH | Petak | Bongkor | Kurang | Terpenuhi | Eff |
|---|---|---|---|---|---|
| KALISETAIL | 284 | 34 | 15 | 235 | 88,64% |
| GLENMORE | 291 | 114 | 3 | 174 | 66,66% |
| ROGOJAMPI | 83 | 26 | 20 | 37 | 62,67% |
| LICIN | 105 | 55 | 13 | 37 | 46,29% |
| KALIBARU | 46 | 37 | 0 | 9 | 19,57% |

266 + 51 + 492 = 809 ✓ (cek konsistensi sebelum presentasi —
lihat [[aturan-denominator]]). Visual: `show_on_map("petak_efektivitas_map",
tahun=2026, kode_kph=31211)` + zoom Z≥12 untuk analisa per petak
(aturan tier: Z≤11 polygon saja — [[arsitektur-skala-peta]]).

## 4. Kondisi Penyadap

Tidak ditarik dalam laporan ini. Panggilan pengisinya:
`penyadap_productivity(tahun=2026, kode_kph=31211)`. Jangan simpulkan
"kekurangan penyadap" dari petak bongkor tanpa data ini
([[distingsi-semantik-kritis]]: petak ≠ penyadap).

## 5. Aktivitas (September 2026)

Budaya Bersih 12 · Semprot CAS 11 · Quare 8 · Kerok 8 · Naik Batok 4 —
total 43 aktivitas, semua berfoto, terakhir 2026-09-23 [FACT #3].
Volume aktivitas kecil vs 809 petak: wajar, satu aktivitas ≠ satu petak
([[metrik-aktivitas]]). Visual: `show_on_map("aktivitas_petak_map",
tahun=2026, bulan=9, periode=0, kode_kph=31211)`.

## 6. Produksi (September 2026, per BKPH)

| BKPH | Aktual (kg) | Target (kg) | Achievement |
|---|---|---|---|
| KALIBARU | 153.358 | 343.895 | 44,59% |
| KALISETAIL | 343.739 | 856.785 | 40,12% |
| ROGOJAMPI | 145.530 | 362.955 | 40,10% |
| GLENMORE | 468.643 | 1.185.257 | 39,54% |
| LICIN | 89.949 | 360.708 | 24,94% |

Glenmore penyumbang volume terbesar (468.643 kg, 39% total KPH)
tapi achievement tengah — volume besar ≠ kinerja terbaik
([[absolut-vs-relatif]]).

## 7. Target & Achievement

Achievement KPH 38,6% = total aktual / total target se-BKPH, bukan
rata-rata persen BKPH [DERIVED — denominator eksplisit]. Semua BKPH di
bawah 50%: ini pola KPH, bukan satu BKPH bermasalah [COMPARISON].
Target bulanan dari RKAP; `rkap_achievement` per petak hanya 1 baris
valid di Sept (sampel tipis — jangan generalisasi ke KPH).

## 8. Analisis Wilayah

Ranking achievement: Kalibaru > Kalisetail ≈ Rogojampi ≈ Glenmore >>
Licin. Ranking efektivitas andil: Kalisetail >> Glenmore > Rogojampi >
Licin > Kalibaru. Dua ranking beda susunan — wajar, denominator beda
(produksi/target vs andil/luas baku). Jangan campur [[population-awareness]].

## 9. Spatial Findings

Overview: `show_on_map("kph_summary_map", tahun=2026,
aggregated_level=kode_bkph, kode_kph=31211)` — 5 centroid + KPI,
payload <500 KB. Detail: zoom ke Licin
(`bounds` viewport Licin, Z≥12) untuk polygon + analisa + pin aktivitas
([[skala-multi-divre]], [[presentasi-spasial]]). Konsentrasi bongkor
andil Glenmore–Licin terlihat di peta, bukan hanya di tabel.

## 10. Anomaly / Variance

- Licin: achievement 24,9%, terpaut −13,7 poin dari rata-rata KPH —
  variance negatif terbesar [COMPARISON].
- Kalibaru: efektivitas andil terendah (19,57%) tapi achievement
  tertinggi (44,59%) — anomali semu: dua metric beda denominator,
  bukan kontradiksi. Jelaskan, jangan disembunyikan (golden rule 9).
- Kalisetail: 88,64% efektivitas + 40,12% achievement — kandidat
  praktik baik, verifikasi lapangan dulu sebelum direplikasi
  (HYPOTHESIS, bukan rekomendasi).

## 11. Interpretation

Penurunan/ketertinggalan terkonsentrasi di Licin (dua sinyal independen:
andil + produksi) [INTERPRETATION dari FACT #1 + DERIVED #2].
Kalimat yang dilarang: "Licin menyebabkan produksi turun" (klaim kausal
tanpa evidence — [[model-hipotesis]]: tulis Hypothesis / Supporting /
Missing / How To Test bila diajukan).

## 12. Data Limitation

- Kesegaran: aktivitas terakhir 2026-09-23 (11 hari lalu); pagi minim
  input 12.00–15.00 ramai — angka Sept bisa bergerak.
- Definisi "bongkor" beda antar template: `kph_summary_map` = tanpa
  andil (266), `bongkor_per_wilayah` = NOT EXISTS andil (267),
  `status_petak_per_wilayah` = tanpa aktivitas periode berjalan (804).
  Jangan bandingkan ketiganya langsung.
- YTD (1.200.516 kg, tabel penerimaan) vs agregat Sept per wilayah
  (1.201.219 kg, tabel produksi) — template beda, jangan dijumlah-silangkan.
- Section 4 (penyadap) kosong — lihat panggilan pengisinya di atas.

## 13. Suggested Next Analysis

1. Drill-down Licin: `petak_efektivitas_map(kode_bkph=3121101)` +
   `penyadap_productivity(kode_bkph=3121101)` — isi section 4.
2. Cek medan Licin vs Kalisetail ([[medan-aktivitas]]): cuaca/akses/
   ketinggian sebagai HYPOTHESIS teruji, bukan penjelasan jadi.
3. Pantau aktivitas Oktober: data Sept basi 11 hari, refresh dulu
   (`provenance()` harus `segar` sebelum klaim tren).

## Link Balik

[[struktur-laporan-eksekutif]], [[aturan-summary-eksekutif]],
[[model-insight-bisnis]], [[klasifikasi-fakta]], [[tool-bisnis-anna]],
[[intent-ke-template-peta]], [[skala-multi-divre]],
[[arsitektur-skala-peta]], [[presentasi-spasial]], [[kph]], [[bkph]]
