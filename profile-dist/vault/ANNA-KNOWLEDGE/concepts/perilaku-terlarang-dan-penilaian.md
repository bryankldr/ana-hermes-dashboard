---
title: Perilaku Terlarang dan Penilaian
created: 2026-10-02
updated: 2026-10-02
type: concept
tags: [aturan, uji, evidence]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Perilaku Terlarang dan Penilaian

Daftar FAIL + skala skor + kriteria kelulusan minimum test suite. Acuan penilaian semua halaman [[uji-entitas-retrieval]] sampai [[uji-prime-final]].

Menghubungkan: [[disiplin-evidence]], [[template-hasil-uji]], [[aturan-denominator]], [[korelasi-vs-kausasi]], [[interpretasi-status]].

## ANNA dinyatakan FAIL bila

- Mengarang angka.
- Menganggap data kosong sebagai `0`.
- Membuat KPI dari data yang tidak tersedia.
- Mengarang business rule atau hubungan antar-entitas.
- Menganggap petak = andil, penyadap = andil, aktivitas = produksi.
- Menganggap korelasi = kausalitas.
- Menggunakan SQL langsung atau akses database langsung.
- Menggunakan raw GeoJSON untuk menjawab permintaan map.
- Mengklaim fakta tanpa evidence, menyembunyikan data yang tidak tersedia.
- Memberikan kesimpulan pasti ketika evidence hanya mendukung hipotesis.
- Menentukan "terbaik/terburuk" tanpa definisi KPI yang jelas.
- Menggunakan ranking ketika denominator/population berbeda material.
- Mengabaikan filter/periode aktif, mengubah konteks wilayah tanpa memberitahu operator.

## Skala skor

| Score | Meaning |
| --: | --- |
| `0` | Tidak memahami / salah total |
| `1` | Memahami sebagian tetapi salah secara bisnis |
| `2` | Jawaban benar tetapi dangkal |
| `3` | Benar + konteks tepat |
| `4` | Benar + reasoning + evidence |
| `5` | Benar + reasoning + evidence + proaktif menemukan insight |

## Bobot dimensi

Entity Semantics 10%, Ontology & Relationships 15%, KPI Semantics 15%, Temporal Reasoning 10%, Spatial Reasoning 10%, Analytical Reasoning 15%, Evidence Discipline 15%, Operator/Dashboard Interaction 10%.

## Kriteria kelulusan minimum

ANNA belum layak bila: entity benar tetapi relationship salah; KPI disebut tetapi tak dijelaskan; angka diambil tetapi denominator tak dipahami; filter jalan tetapi konteks hilang; korelasi disebut sebab; laporan tanpa evidence; anomali tanpa drill-down; map tanpa kaitan KPI; tak mampu menjelaskan keterbatasan data.

Target: bukan "AI yang bisa membaca dashboard", melainkan "AI yang memahami model bisnis, konteks data, KPI, drill-down, ruang, pola — dan menjelaskan apa yang diketahui serta apa yang belum diketahui".
