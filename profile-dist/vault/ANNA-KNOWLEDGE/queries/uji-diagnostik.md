---
title: Uji Diagnostik BI
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, diagnostik]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Diagnostik BI

Bank uji section 8 test suite. Tujuan: kemampuan mencari indikator yang relevan ketika terjadi perubahan KPI.

Menguji: [[framework-diagnostik]], [[pohon-diagnostik]], [[narasi-produksi]], [[pola-nalar-bisnis]], [[model-insight-bisnis]], [[produktivitas]], [[status-petak]].

## Daftar uji (D001–D012)

- `D001` Produksi turun. Apa yang perlu saya periksa?
- `D002` Target tercapai tetapi produksi turun. Bagaimana mungkin?
- `D003` Produksi turun tetapi aktivitas naik. Apa yang perlu diperiksa?
- `D004` Penyadap naik tetapi produksi turun. Apa yang perlu diperiksa?
- `D005` Petak aktif meningkat tetapi produktivitas menurun. Apa artinya?
- `D006` Petak bongkor meningkat. KPI apa yang perlu dilihat?
- `D007` Banyak petak tanpa penyadap. Apa dampaknya?
- `D008` TPG memiliki banyak penyadap tetapi produksi rendah. Apa yang perlu dianalisis?
- `D009` TPG memiliki sedikit penyadap tetapi produksi tinggi. Apa yang perlu diperiksa?
- `D010` Mengapa BKPH dapat memiliki produksi tinggi tetapi pencapaian target rendah?
- `D011` Mengapa BKPH dapat memiliki produksi rendah tetapi pencapaian target tinggi?
- `D012` Indikator apa yang mungkin berkaitan dengan penurunan produktivitas?

## Penilaian

Jawaban berupa indikator yang perlu diperiksa, bukan penyebab pasti ([[framework-diagnostik]]). D002/D010/D011 memakai [[konteks-target]]. Bahasa korelasi, bukan kausal ([[korelasi-vs-kausasi]]). Skor dengan [[perilaku-terlarang-dan-penilaian]].
