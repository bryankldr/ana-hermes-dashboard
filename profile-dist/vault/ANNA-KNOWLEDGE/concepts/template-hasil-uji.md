---
title: Template Hasil Uji
created: 2026-10-02
updated: 2026-10-02
type: concept
tags: [uji, aturan]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Template Hasil Uji

Format pencatatan baku setiap test yang dijalankan terhadap ANNA. Dipakai bersama [[perilaku-terlarang-dan-penilaian]].

Menghubungkan: [[bank-uji-semantik]], [[disiplin-evidence]], [[klasifikasi-fakta]].

## Template

```text
Test ID:

Question:

Expected Intent:

Expected Entities:

Expected Filters:

Expected KPI:

Expected Tool:

Expected Map Action:

Expected Evidence:

Expected Reasoning:

ANNA Response:

Score:
0 / 1 / 2 / 3 / 4 / 5

Failure Type:

Notes:
```

## Aturan pakai

- Expected Evidence wajib diisi sebelum test dijalankan — tanpa itu skor tak bermakna ([[disiplin-evidence]]).
- Failure Type merujuk ke daftar FAIL di [[perilaku-terlarang-dan-penilaian]].
- Hasil test yang gagal menjadi umpan balik compounding: perbaiki halaman wiki terkait, catat di `log.md`.
