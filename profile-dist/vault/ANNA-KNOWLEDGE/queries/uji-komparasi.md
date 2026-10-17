---
title: Uji Komparasi
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, komparasi, wilayah]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Komparasi

Bank uji section 7 test suite. Tujuan: perbandingan antar dimensi bisnis.

Menguji: [[absolut-vs-relatif]], [[semantik-ranking]], [[population-awareness]], [[aturan-denominator]], [[pencapaian-target]], [[produktivitas]], [[drill-down-wilayah]].

## Daftar uji (C001–C010)

- `C001` Bandingkan seluruh BKPH berdasarkan produksi.
- `C002` Bandingkan seluruh TPG berdasarkan produktivitas.
- `C003` Bandingkan dua KPH.
- `C004` Bandingkan kondisi petak dua BKPH.
- `C005` Wilayah mana yang memiliki proporsi petak bongkor paling tinggi?
- `C006` Wilayah mana yang memiliki pencapaian target paling rendah?
- `C007` TPG mana yang memiliki produktivitas tinggi tetapi jumlah penyadap rendah?
- `C008` TPG mana yang memiliki banyak penyadap tetapi produktivitas rendah?
- `C009` Apakah wilayah dengan penyadap terbanyak juga menghasilkan produksi terbesar?
- `C010` Apakah wilayah dengan petak aktif terbanyak juga memiliki produktivitas tertinggi?

## Penilaian

C005 pakai proporsi, bukan count ([[absolut-vs-relatif]]). "Terbaik/terburuk" wajib definisi KPI ([[semantik-ranking]]). Populasi berbeda material → ranking tidak valid ([[population-awareness]]). Skor dengan [[perilaku-terlarang-dan-penilaian]].
