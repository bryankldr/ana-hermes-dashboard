---
title: Uji Inteligensi Spasial
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, spasial, dashboard]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Inteligensi Spasial

Bank uji section 10 test suite. Tujuan: hubungan antara data numerik dan konteks geografis.

Menguji: [[inteligensi-spasial]], [[penalaran-spasial]], [[presentasi-spasial]], [[petak-polygon]], [[status-petak]], [[semantik-dashboard]].

## Daftar uji (S001–S013)

- `S001` Tampilkan seluruh petak bongkor di peta.
- `S002` Tampilkan petak idle di BKPH tertentu.
- `S003` Tampilkan petak tanpa penyadap.
- `S004` Tampilkan petak dengan lebih dari satu penyadap.
- `S005` Tampilkan petak dengan produktivitas rendah.
- `S006` Wilayah mana yang memiliki konsentrasi petak bongkor tertinggi?
- `S007` Apakah petak bongkor terkonsentrasi pada RPH tertentu?
- `S008` Tampilkan wilayah dengan produksi rendah dan bongkor tinggi.
- `S009` Tampilkan petak dengan aktivitas rendah tetapi target tinggi.
- `S010` Tampilkan TPG dengan pencapaian target rendah di peta.
- `S011` Fokuskan peta pada wilayah yang sedang dianalisis.
- `S012` Jelaskan apa yang terlihat pada peta setelah filter diterapkan.
- `S013` Hubungkan kondisi geografis dengan KPI yang sedang dibahas.

## Penilaian

"Tampilkan di peta" = aksi map tool, bukan angka ([[inteligensi-spasial]]). S005/S009 gabungkan dua dimensi sebelum filter peta ([[penalaran-spasial]]). S012/S013 interpretasi visual → bahasa bisnis ([[presentasi-spasial]]). Skor dengan [[perilaku-terlarang-dan-penilaian]].
