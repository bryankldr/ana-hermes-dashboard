---
title: Uji Integritas Data
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, integritas-data, evidence]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Integritas Data

Bank uji section 15 test suite. Tujuan: mendeteksi data yang tidak layak langsung disimpulkan.

Menguji: [[kualitas-data]], [[data-hilang]], [[model-evidence]], [[klasifikasi-fakta]].

## Daftar uji (DI001–DI012)

- `DI001` Jumlah petak tiba-tiba turun 30%. Apakah berarti petak hilang?
- `DI002` Jumlah penyadap tiba-tiba naik dua kali lipat. Apa yang harus diperiksa?
- `DI003` Produksi menjadi nol. Apakah benar produksi nol?
- `DI004` Aktivitas menjadi nol. Apa kemungkinan penyebabnya?
- `DI005` Target menjadi nol. Apakah berarti tidak ada target?
- `DI006` Ada petak tanpa koordinat. Apa dampaknya terhadap analisis peta?
- `DI007` Ada penyadap tanpa andil. Apa yang harus diperiksa?
- `DI008` Ada andil tanpa petak. Apa artinya?
- `DI009` Ada aktivitas tanpa rencana. Apa yang harus diperiksa?
- `DI010` Ada data duplikat. Apakah KPI masih dapat dipercaya?
- `DI011` Data periode sebelumnya berubah setelah sinkronisasi. Bagaimana memperlakukannya?
- `DI012` Apakah data saat ini cukup lengkap untuk membuat kesimpulan?

## Penilaian

Angka ekstrem pertama dicurigai sebagai masalah data, bukan fakta bisnis ([[kualitas-data]]). Data kosong ≠ nol ([[data-hilang]]). DI012 wajib dijawab eksplisit sebelum kesimpulan. Skor dengan [[perilaku-terlarang-dan-penilaian]].
