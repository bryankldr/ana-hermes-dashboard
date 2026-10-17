---
title: Uji Root Cause
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, diagnostik, evidence]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Root Cause

Bank uji section 9 test suite. Tujuan: kemampuan membangun diagnostic tree tanpa mengarang causal relationship.

Menguji: [[pohon-diagnostik]], [[framework-diagnostik]], [[klasifikasi-fakta]], [[model-hipotesis]], [[model-evidence]], [[korelasi-vs-kausasi]], [[drill-down-wilayah]].

## Daftar uji (RC001–RC010)

- `RC001` Produksi turun 15%. Bantu saya mencari kemungkinan penyebabnya.
- `RC002` Mulai dari KPI utama, indikator apa yang harus diperiksa?
- `RC003` Apakah penurunan produksi terkonsentrasi pada wilayah tertentu?
- `RC004` Apakah penurunan berasal dari jumlah penyadap atau produktivitas?
- `RC005` Apakah aktivitas penyadapan ikut berubah?
- `RC006` Apakah perubahan terjadi pada petak aktif, idle, atau bongkor?
- `RC007` Apakah ada TPG yang menyumbang sebagian besar penurunan?
- `RC008` Apakah penurunan terjadi merata atau hanya pada wilayah tertentu?
- `RC009` Buat diagnostic tree untuk penurunan produksi.
- `RC010` Pisahkan mana fakta dan mana hipotesis.

## Penilaian

"Kemungkinan penyebab" = hipotesis, bukan verdict ([[model-hipotesis]]). RC009 mengikuti struktur [[pohon-diagnostik]]. RC010 memakai [[klasifikasi-fakta]]. Dilarang menyatakan sebab tanpa evidence ([[perilaku-terlarang-dan-penilaian]]).
