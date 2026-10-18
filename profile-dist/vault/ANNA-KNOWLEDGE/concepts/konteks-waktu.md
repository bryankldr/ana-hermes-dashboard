---
title: Konteks Waktu
created: 2026-10-02
updated: 2026-10-18
type: concept
tags: [periode, konteks-waktu, interpretasi]
sources: [raw/articles/simoge-business-ontology.md, simoge_db.py]
---

# Konteks Waktu

Setiap pertanyaan bisnis dianalisis terhadap: tanggal, bulan, tahun, [[periode]], dan `sampai dengan` (Ya/Tidak), serta comparison period.

- `Sampai dengan Ya` = kumulatif `Jan 1 s/d akhir periode terpilih` (lihat [[periode]] tabel kanonik Februari).
- `Sampai dengan Tidak` = hanya periode/bulan terpilih (`Penuh` = 1..akhir bulan, `P1` = 1..15).

"Produksi turun" → turun dibanding kapan? (periode/bulan/tahun sebelumnya, [[target]], rata-rata, dan dengan `sampai dengan` yang sama.) Bila comparison tidak jelas dan konteks dashboard tidak menjawab, minta klarifikasi. Lihat [[penanganan-ambigu]] dan [[pencapaian-target]].

BIT dan Business Data Engine memakai `simoge_db._range_bounds` + `_target_pct_sd` sebagai satu pintu untuk rentang dan persen — jangan hitung manual.
