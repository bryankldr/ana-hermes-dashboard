---
title: Uji Jebakan KPI
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, kpi, interpretasi]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Jebakan KPI

Bank uji section 5 test suite. Tujuan: ANNA memahami KPI secara benar, tidak menyamakan perubahan satu metrik dengan performa keseluruhan.

Menguji: [[aturan-interpretasi-kpi]], [[absolut-vs-relatif]], [[konteks-target]], [[growth-produksi]], [[pencapaian-target]], [[produktivitas]].

## Daftar uji (T001–T013)

- `T001` Jika realisasi naik 10%, apakah performa otomatis membaik?
- `T002` Jika penyadap naik 20% tetapi produksi hanya naik 5%, apa yang terjadi pada produktivitas per penyadap?
- `T003` Jika produksi naik tetapi target naik lebih besar, bagaimana pencapaian target berubah?
- `T004` Jika petak aktif naik tetapi produksi turun, apakah itu kontradiksi?
- `T005` Jika petak bongkor turun, apakah produksi pasti naik?
- `T006` Jika aktivitas meningkat, apakah produksi pasti meningkat?
- `T007` Jika penyadap turun tetapi produksi tetap, bagaimana produktivitas berubah?
- `T008` Jika target turun tetapi realisasi tetap, bagaimana pencapaian target berubah?
- `T009` Apakah pencapaian target dapat meningkat ketika produksi sebenarnya turun?
- `T010` Apa perbedaan growth produksi dengan pencapaian target?
- `T011` Apa perbedaan produktivitas dengan total produksi?
- `T012` Mengapa rata-rata produksi bisa naik sementara total produksi turun?
- `T013` Mengapa total produksi bisa naik sementara produktivitas turun?

## Penilaian

Jawaban benar memakai [[aturan-interpretasi-kpi]] dan membedakan [[absolut-vs-relatif]]. Klaim "pasti" tanpa evidence = FAIL — lihat [[perilaku-terlarang-dan-penilaian]].
