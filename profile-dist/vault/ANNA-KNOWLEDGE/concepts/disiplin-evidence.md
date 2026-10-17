---
title: Disiplin Evidence
created: 2026-10-02
updated: 2026-10-02
type: concept
tags: [evidence, aturan]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Disiplin Evidence

Setiap jawaban faktual harus dapat ditelusuri ke KPI Evidence atau Named Business Tool Result. Tanpa evidence = bukan fakta.

Menghubungkan: [[klasifikasi-fakta]], [[model-evidence]], [[model-hipotesis]], [[data-hilang]], [[kualitas-data]], [[perilaku-terlarang-dan-penilaian]].

## Lima label wajib

- **FACT** — data yang langsung tersedia.
- **DERIVED METRIC** — nilai yang dihitung dari data yang tersedia.
- **COMPARISON** — perbandingan dua atau lebih periode/dimensi.
- **INTERPRETATION** — makna bisnis yang diberikan terhadap fakta.
- **HYPOTHESIS** — kemungkinan penjelasan yang belum terbukti.

## Contoh baku

```text
FACT:
Produksi turun 8%.

DERIVED:
Pencapaian target turun dari 94% menjadi 87%.

COMPARISON:
Penurunan terbesar berasal dari BKPH X.

INTERPRETATION:
Perubahan produksi terkonsentrasi pada wilayah tersebut.

HYPOTHESIS:
Perubahan aktivitas atau produktivitas mungkin berkaitan
dengan penurunan tersebut.

EVIDENCE NEEDED:
Data aktivitas dan produktivitas pada periode pembanding.
```

## Aturan pakai

- Klaim tanpa evidence = FAIL ([[perilaku-terlarang-dan-penilaian]]).
- Data kosong/ragu → nyatakan sebagai [[data-hilang]], jangan diisi nol.
- Angka ekstrem → cek [[kualitas-data]] sebelum jadi FACT.
