---
title: Uji Drill Down Multidimensi
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, wilayah, operasional, dashboard]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Drill Down Multidimensi

Bank uji section 11 test suite. Tujuan: kemampuan berpindah antar level ontology.

Menguji: [[drill-down-wilayah]], [[drill-down-operasional]], [[preservasi-konteks]], [[gap-produksi]], [[penyadap]], [[aktivitas-penyadapan]], [[semantik-dashboard]].

## Daftar uji (MD001–MD010)

- `MD001` Tampilkan kondisi KPH secara keseluruhan.
- `MD002` Drill-down KPH → BKPH → RPH → TPG.
- `MD003` Dari KPH dengan produksi terendah, cari BKPH yang paling berkontribusi terhadap gap.
- `MD004` Dari BKPH tersebut, cari RPH yang paling berkontribusi.
- `MD005` Dari RPH tersebut, cari TPG yang relevan.
- `MD006` Tampilkan petak bermasalah dari TPG tersebut.
- `MD007` Berapa penyadap yang terkait dengan petak tersebut?
- `MD008` Bagaimana aktivitas penyadap tersebut pada periode ini?
- `MD009` Bagaimana kontribusinya terhadap produksi?
- `MD010` Tampilkan seluruh rantai analisis tersebut di dashboard.

## Penilaian

Rantai MD003→MD006 wajib bawa konteks wilayah ([[preservasi-konteks]]). "Berkontribusi terhadap gap" = kontribusi absolut, bukan ranking ([[drill-down-wilayah]]). MD007→MD009 pindah level wilayah→operasional ([[drill-down-operasional]]). Skor dengan [[perilaku-terlarang-dan-penilaian]].
