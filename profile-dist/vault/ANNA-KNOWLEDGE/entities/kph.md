---
title: KPH
created: 2026-10-02
updated: 2026-10-02
type: entity
tags: [kph, wilayah]
sources: [raw/articles/simoge-business-ontology.md]
---

# KPH

Unit organisasi pengelolaan hutan di bawah [[divre]]. KPH adalah scope analisis utama dashboard SIMOGE.

## Master nyata (sandbox 2026-10-03)

| kode_kph | Nama | Divre |
|---|---|---|
| 31210 | BANYUWANGI SELATAN | 2 JAWA TIMUR |
| 31211 | BANYUWANGI BARAT | 2 JAWA TIMUR |

Data operasional (petak, aktivitas, drum) hanya ada di 31211 BANYUWANGI BARAT.
Dipimpin ADM (lihat [[peran-jabatan]]).

## Memiliki
Wilayah, [[bkph]], [[rph]], [[tpg]], [[petak]], [[penyadap]], [[aktivitas-penyadapan]], [[target]], [[produksi]].

## Dimensi
`KPH` — dipakai untuk slicing dan drill-down.

## Drill-down
`DIVRE ↓ KPH ↓ [[bkph]] ↓ [[rph]] ↓ [[tpg]]` (lihat [[drill-down-wilayah]]).
