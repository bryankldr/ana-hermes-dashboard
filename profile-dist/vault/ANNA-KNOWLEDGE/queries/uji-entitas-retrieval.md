---
title: Uji Entitas dan Retrieval
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, operasional, wilayah]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Entitas dan Retrieval

Bank uji section 0–1 test suite. Tujuan: pemahaman entitas dasar bisnis + kemampuan mengambil informasi bisnis dasar.

Menguji: [[petak]], [[penyadap]], [[andil]], [[aktivitas-penyadapan]], [[rencana-aktivitas]], [[target]], [[tpg]], [[mandor]], [[distingsi-semantik-kritis]], [[narasi-produksi]].

## Entitas (E001–E015)

- `E001` Apa itu petak?
- `E002` Apa itu penyadap?
- `E003` Apa itu andil?
- `E004` Apa itu aktivitas penyadapan?
- `E005` Apa itu rencana aktivitas?
- `E006` Apa itu target produksi?
- `E007` Apa itu TPG?
- `E008` Apa itu RPH?
- `E009` Apa itu BKPH?
- `E010` Apa itu KPH?
- `E011` Apa hubungan antara penyadap dan andil?
- `E012` Apa hubungan antara andil dan petak?
- `E013` Apa hubungan antara rencana aktivitas dan aktivitas?
- `E014` Siapa yang bertanggung jawab terhadap sebuah TPG?
- `E015` Bagaimana hierarki KPH → BKPH → RPH → TPG?

## Retrieval (R001–R014)

- `R001` Berapa total petak saat ini?
- `R002` Berapa jumlah penyadap aktif?
- `R003` Berapa jumlah TPG?
- `R004` Berapa jumlah petak aktif?
- `R005` Berapa jumlah petak idle?
- `R006` Berapa jumlah petak bongkor?
- `R007` Berapa aktivitas penyadapan pada periode ini?
- `R008` Berapa produksi pada periode ini?
- `R009` Berapa target produksi periode ini?
- `R010` Berapa realisasi produksi periode ini?
- `R011` Berapa luas total petak?
- `R012` Berapa jumlah penyadap pada TPG tertentu?
- `R013` Berapa jumlah petak pada BKPH tertentu?
- `R014` Berapa aktivitas pada RPH tertentu?

## Penilaian

Jawaban faktual wajib ikut [[klasifikasi-fakta]]. Skor dengan [[perilaku-terlarang-dan-penilaian]].
