---
title: Uji Ambiguitas Semantik
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, interpretasi, evidence]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Ambiguitas Semantik

Bank uji section 14 test suite. Tujuan: ANNA meminta klarifikasi ketika definisi bisnis tidak cukup jelas.

Menguji: [[interpretasi-status]], [[semantik-ranking]], [[konteks-waktu]], [[penanganan-ambigu]], [[aturan-denominator]].

## Daftar uji (SA001–SA010)

- `SA001` Apa maksud "petak tidak aktif"?
- `SA002` Apa maksud "produksi rendah"?
- `SA003` Apa maksud "penyadap bermasalah"?
- `SA004` Apa maksud "TPG terbaik"?
- `SA005` Apa maksud "wilayah terburuk"?
- `SA006` Jika operator mengatakan "yang paling bagus", KPI apa yang digunakan?
- `SA007` Jika operator mengatakan "yang paling parah", bagaimana menentukan kriterianya?
- `SA008` Jika operator meminta "produktivitas rendah", dibandingkan dengan apa?
- `SA009` Jika operator meminta "produksi turun", dibandingkan terhadap periode apa?
- `SA010` Jika operator meminta "masalah", bagaimana menentukan domain masalah?

## Perilaku yang diharapkan

ANNA tidak boleh membuat definisi sendiri jika konteks tidak cukup — minta klarifikasi dulu.

## Penilaian

SA004/SA005/SA006/SA007 butuh definisi KPI ([[semantik-ranking]]). SA008/SA009 butuh pembanding ([[konteks-waktu]]). Membuat definisi sendiri = FAIL ([[perilaku-terlarang-dan-penilaian]]).
