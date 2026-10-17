---
title: Alias Wilayah dan Bahasa Operator
created: 2026-10-03
updated: 2026-10-03
type: concept
tags: [wilayah, intent]
sources: [raw/articles/skema-database-kph-bwb-sandbox2.md]
---

# Alias Wilayah dan Bahasa Operator

Tabel resolusi bahasa operator → filter wilayah resmi. Dipakai SEBELUM memanggil
Business Data Engine (lihat [[batas-data-engine]]) agar intent geografis tidak salah filter.

## Alias Divre

| Ucapan operator | Filter resmi      | kode_divre publik |
| --------------- | ----------------- | ----------------- |
| jatim           | DIVRE JAWA TIMUR  | 2                 |
| jateng          | DIVRE JAWA TENGAH | 1                 |
| jabar           | DIVRE JAWA BARAT  | 3                 |

PERHATIAN: kode wilayah di akun operator (`kode_divre/kph/bkph/rph` di
[[operator-lapangan]]) teramati bernilai kecil (contoh 1, 7, 5, 10) yang TIDAK
cocok dengan kode master publik (31211, 3121101, ...). Jangan samakan langsung —
resolusi kode akun → wilayah resmi lewat Business Data Engine, bukan hafalan.

## Alias BKPH (KPH 31211)

| Ucapan | BKPH resmi |
|---|---|
| licin, daerah licin | LICIN (3121101) |
| glenmore | GLENMORE (3121104) |

"Petak licin" = petak + filter BKPH=LICIN, BUKAN status/kondisi petak
(lihat [[status-petak]]). "Aktivitas di Glenmore" = aktivitas + filter BKPH=GLENMORE.

## Alias TPG

Setiap [[tpg]] punya alias pendek di kolom `alias` (sm1, pg1, co, sry1, ...).
Operator boleh menyebut alias; resolve ke kode_tpg via engine.

## Aturan

- Alias tak dikenal → klarifikasi, jangan tebak (lihat [[penanganan-ambigu]]).
- "Jabar" tidak ada di database ini → beri tahu cakupan data (Jatim + Jateng),
  tawarkan ganti scope.
- Selalu sebutkan scope yang dipakai saat menjawab ("data BKPH LICIN, ...").
