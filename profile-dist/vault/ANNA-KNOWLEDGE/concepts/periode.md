---
title: Periode
created: 2026-10-02
updated: 2026-10-18
type: concept
tags: [periode, konteks-waktu, aturan]
sources: [raw/articles/simoge-business-ontology.md, bit_engine.py, simoge_db.py]
---

# Periode

Periode operasional SIMOGE: `P1` (tanggal 1–15), `P2` (16–akhir bulan), `Penuh (0)` (tanggal 1–akhir bulan = P1+P2). Analisis juga bisa memakai hari, minggu, bulan, tahun, YTD, periode pembanding.

## Sampai dengan — kumulatif vs periode saja

`Sampai dengan` menentukan apakah angka dihitung **kumulatif sejak awal tahun** atau **hanya pada periode/bulan terpilih**. Diterjemahkan oleh `simoge_db._sampai_dengan`, `_range_bounds`, dan `_target_pct_sd`.

- **Ya** = kumulatif `2026-01-01 s/d akhir periode terpilih`. Contoh: Februari Penuh Ya = `2026-01-01..2026-02-28`, Februari P1 Ya = `2026-01-01..2026-02-15`.
- **Tidak** = periode/bulan saja. Contoh: Februari P1 Tidak = `2026-02-01..2026-02-15`, Februari Penuh Tidak = `2026-02-01..2026-02-28` (P1+P2 Februari saja).

## Kombinasi kanonik (contoh Februari 2026)

| Sampai dengan | Periode | Rentang hitung | Target % (RO) | period_bounds / _range_bounds |
|---|---|---|---|---|
| Ya | Penuh (0) | `2026-01-01 .. 2026-02-28` | 16.0% (7.0 Jan + 9.0 Feb) | `_range_bounds(kw=Ya)` |
| Ya | P1 | `2026-01-01 .. 2026-02-15` | 11.5% (7.0 Jan + 4.5 Feb P1) | `Jan..cutoff P1` |
| Tidak | P1 | `2026-02-01 .. 2026-02-15` | 4.5% (Feb P1 saja) | `period_bounds(2026,2,1)` |
| Tidak | Penuh (0) | `2026-02-01 .. 2026-02-28` | 9.0% (4.5+4.5 Feb) | `period_bounds(2026,2,0)` |

Semua KPI BIT (`Target`, `Rencana`, `Realisasi`, `Gap`, `Achievement`) wajib memakai rentang dan persen yang sama — `Ya` pakai `_target_pct_sd(kw=Ya)` + `_range_bounds(kw=Ya)`, `Tidak` pakai versi `Tidak`. BIT (`bit_engine.py`) menyimpan kedua rentang sebagai `period_bounds` (main) + `ytd_bounds` + `period_only_bounds` untuk audit.

ANNA wajib tahu **time scope** sebelum memberi KPI. Lihat [[konteks-waktu]], [[measures]], dan [[gap-produksi]].
