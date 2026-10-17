---
title: Uji Filter dan Konteks
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, dashboard, intent]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Filter dan Konteks

Bank uji section 2 test suite. Tujuan: kemampuan menerjemahkan bahasa operator menjadi filter dashboard.

Menguji: [[semantik-dashboard]], [[status-petak]], [[preservasi-konteks]], [[periode]], [[presentasi-spasial]], [[inteligensi-spasial]].

## Daftar uji (F001–F017)

- `F001` Tampilkan petak bongkor.
- `F002` Tampilkan petak idle.
- `F003` Tampilkan petak aktif.
- `F004` Tampilkan petak bongkor di KPH tertentu.
- `F005` Berapa petak idle di BKPH tertentu?
- `F006` Berapa penyadap aktif di RPH tertentu?
- `F007` Bagaimana kondisi petak di TPG tertentu?
- `F008` Tampilkan aktivitas penyadapan bulan ini.
- `F009` Tampilkan aktivitas penyadapan bulan lalu.
- `F010` Bandingkan kondisi petak P1 dan P2.
- `F011` Tampilkan petak yang belum memiliki penyadap.
- `F012` Tampilkan petak yang memiliki lebih dari satu penyadap.
- `F013` Tampilkan petak yang memiliki andil tetapi belum memiliki aktivitas.
- `F014` Tampilkan petak bongkor beserta lokasinya.
- `F015` Fokuskan peta pada BKPH tertentu.
- `F016` Hilangkan filter wilayah.
- `F017` Tampilkan seluruh KPH.

## Penilaian

"Menampilkan" = aksi dashboard, bukan sekadar angka — lihat [[semantik-dashboard]]. Konteks wilayah/periode wajib dipertahankan ([[preservasi-konteks]]). Skor dengan [[perilaku-terlarang-dan-penilaian]].
