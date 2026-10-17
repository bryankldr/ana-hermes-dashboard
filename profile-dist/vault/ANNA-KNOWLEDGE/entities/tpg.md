---
title: TPG
created: 2026-10-02
updated: 2026-10-02
type: entity
tags: [tpg, wilayah]
sources: [raw/articles/simoge-business-ontology.md]
---

# TPG

Unit operasional lapangan tempat aktivitas penyadapan dikelola. Berada di bawah [[rph]].

## Master nyata (sandbox 2026-10-03)

39 TPG operasional + 3 dummy ("Test TPG" kode 992/993/999, tanpa wilayah — abaikan
di analisis). Setiap TPG punya `alias` pendek (kolom `alias`, contoh sm1, lc, co).
Daftar lengkap 39 TPG per BKPH→RPH ada di raw `skema-database-kph-bwb-sandbox2.md`
(lampiran). Contoh resolusi: "SROYO 1" → kode_tpg 31211020102, alias sry1, RPH SROYO,
BKPH ROGOJAMPI. Lihat [[alias-wilayah]] untuk aturan alias.

Kolom `jarak_pgt` (decimal) = jarak ke PGT, nyambung ke tarif pikul via tipe_jarak
(raw: `getah_tarif_pikul`: A Rp250, B Rp200, C Rp150).
`status` 1=aktif (37), 0=nonaktif (5). `npk_online` deprecated — jangan dipakai
(lihat [[operator-lapangan]]).

## Berhubungan dengan
[[mandor]], [[penyadap]], [[petak]], [[andil]], [[aktivitas-penyadapan]], [[target]], [[produksi]].

## Dimensi
`TPG`.

## Catatan
TPG adalah titik temu hierarki wilayah dan operasional — awal dari drill-down operasional di [[drill-down-operasional]].
