---
title: Uji Kausalitas Bisnis
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, interpretasi, evidence]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Kausalitas Bisnis

Bank uji section 18 test suite. Tujuan: membedakan korelasi dari sebab-akibat.

Menguji: [[korelasi-vs-kausasi]], [[model-hipotesis]], [[model-evidence]], [[klasifikasi-fakta]].

## Daftar uji (CA001–CA006)

- `CA001` Aktivitas meningkat dan produksi meningkat. Apakah aktivitas menyebabkan produksi meningkat?
- `CA002` Penyadap meningkat dan produksi meningkat. Apakah penambahan penyadap menyebabkan peningkatan produksi?
- `CA003` Bongkor turun dan produksi naik. Apakah penurunan bongkor menyebabkan produksi naik?
- `CA004` Produktivitas turun setelah jumlah petak bertambah. Apakah penambahan petak menyebabkan produktivitas turun?
- `CA005` Jika dua KPI bergerak bersama, apa yang dapat disimpulkan?
- `CA006` Apa bukti tambahan yang diperlukan untuk menyatakan hubungan sebab-akibat?

## Prinsip

> Correlation is not causation.

Bahasa yang diizinkan: "bergerak bersamaan", "berkorelasi secara observasional", "perlu diperiksa lebih lanjut", "belum cukup bukti untuk menyimpulkan sebab-akibat".

## Penilaian

Setiap klaim sebab = FAIL kecuali ada evidence ([[perilaku-terlarang-dan-penilaian]]). CA005 jawaban benar: hanya korelasi observasional. CA006 memakai [[model-evidence]].
