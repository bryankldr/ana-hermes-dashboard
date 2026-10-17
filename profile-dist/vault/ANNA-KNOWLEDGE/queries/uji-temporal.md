---
title: Uji Temporal
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, konteks-waktu, tren]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Temporal

Bank uji section 6 test suite. Tujuan: pemahaman periode, tren, dan perubahan waktu.

Menguji: [[konteks-waktu]], [[periode]], [[growth-produksi]], [[pencapaian-target]], [[kualitas-data]].

## Daftar uji (TM001–TM012)

- `TM001` Bagaimana produksi bulan ini dibanding bulan lalu?
- `TM002` Bagaimana kondisi petak dibanding periode sebelumnya?
- `TM003` Apakah jumlah petak bongkor meningkat atau menurun?
- `TM004` Bagaimana tren aktivitas tiga bulan terakhir?
- `TM005` Apakah produktivitas meningkat sejak awal tahun?
- `TM006` Kapan terjadi perubahan terbesar?
- `TM007` Pada periode mana pencapaian target paling rendah?
- `TM008` Apakah penurunan produksi merupakan perubahan sementara atau bagian dari tren?
- `TM009` Apakah aktivitas bergerak searah dengan produksi?
- `TM010` Apakah peningkatan penyadap diikuti peningkatan produksi?
- `TM011` Periode mana yang menunjukkan anomali?
- `TM012` Apa perubahan KPI terbesar dibanding periode sebelumnya?

## Penilaian

Setiap perbandingan wajib tahu comparison period ([[konteks-waktu]]). "Bergerak searah" ≠ sebab-akibat ([[korelasi-vs-kausasi]]). Anomali angka ekstrem cek [[kualitas-data]] dulu. Skor dengan [[perilaku-terlarang-dan-penilaian]].
