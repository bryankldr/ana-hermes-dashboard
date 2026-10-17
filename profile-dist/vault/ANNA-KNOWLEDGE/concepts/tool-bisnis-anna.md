---
title: Tool Bisnis ANNA
created: 2026-10-03
updated: 2026-10-03
type: concept
tags: [dashboard, intent, batasan]
sources: [raw/articles/simoge-business-ontology.md]
---

# Tool Bisnis ANNA

Dua script di skill `simoge-business` — satu-satunya jalur ANNA ke data.
**Larangan: ANNA tidak mengeksekusi query SQL langsung.**
Angka hanya dari template bernama di bawah; SQL mentah (`q`) sengaja tidak
diekspos ke ANNA.

## 1. `ana_simoge_tool.py` — query + peta

- `call_simoge_tool(template, params)` → `{ok, columns, rows, row_count,
  explanation}`. Output `explanation` siap pakai untuk jawaban.
- `show_on_map(template, **params)` — query + push polygon ke **SPATIAL MAP**
  + auto-fit, satu panggilan. Untuk "tampilkan di peta ...".
- CLI: `ana_simoge_tool.py <template> k=v...` (nilai digit auto-int).
- 38 template (2026-10-04), mis. `petak_count`, `petak_bongkor`,
  `petak_with_geometry`, `bongkor_per_wilayah`, `status_petak_per_wilayah`,
  `aktivitas_agregat` (`grup_by`: penyadap/aktivitas/pembaharuan),
  `aktivitas_top_petak`, `aktivitas_petak_map`, `penyadap_productivity`,
  `produksi_aktiv`, `produksi_per_wilayah`, `produksi_year_to_date`,
  `rkap_achievement`, `target_pct`, `data_freshness`, `data_identity`,
  `drum_flow`, `rkap_map`, `matriks_map`, **`kph_summary_map`** (P0: centroid + KPI per KPH/BKPH/DIVRE, viewport query `bounds`+`zoom`).

Parameter waktu baku: `tahun`, `bulan`, `periode` dengan `1` = tgl 1–15,
`2` = 16–akhir, **`0` = bulan penuh**. "Bulan 5" tanpa periode → `periode=0`,
jangan tambah P1+P2 manual. Filter tahap: `pembaharuan_ke` `"1".."4"` /
`"semua"` — DB live hanya tahap 1/2/3; tahap 4 = 0 baris (katakan, jangan
karang). Satuan belum terverifikasi: sebut mentah, jangan konversi sendiri.

Keamanan CLI: jalankan lewat file script langsung, bukan `python3 -c "..."`
(scanner memblokir badan inline: `Nested executable body could not be
resolved`). `workdir` absolut `/home/bryankldr/PROYEK_2026/ana-hermes-dashboard`.

## 2. `ana_chart_tool.py` — review + chart

- `run_business_review(tahun, bulan, periode)` — susun 6 section
  (`ringkasan→petak→aktivitas→produksi→cross→kesimpulan`) TANPA tampil;
  cache sendiri ±1,3 dtk, invalidasi saat penyadap baru mengisi.
- `present_section(rv, section, with_map)` — siar per section; operator bisa
  menyela tanpa restart. **"Buatkan review" → ini; "berapa/kenapa" →
  `answer_question`** (satu jawaban satu visual).
- `show_for_intent(intent, **kw)` — `target_comparison`→bullet,
  `trend`→line, `ranking`/`region`→h_bar, `composition`/`status`→stacked_bar,
  `relationship`→scatter, `pareto`→pareto, `gap`→waterfall, `kpi`→kartu saja.
- `parse_periode("mei")` → `(2026, 5, 0)` — jangan tebak angka bulan.
- `provenance()` — badge kesegaran: `segar/kemarin/basi/kosong`.
  Bukan `segar` → katakan tanggal data terakhir, tawarkan data terakhir;
  input operator ramai 12.00–15.00, pagi minim — jangan janji "hari ini".
- Efisiensi: 1 pertanyaan = 1–3 tool call; path script literal, jangan
  `find`/`search_files`.

## Berhubungan dengan

[[panel-dashboard]], [[panel-spatial-map]], [[batas-data-engine]], [[narasi-produksi]],
[[semantik-dashboard]], [[presentasi-chart]], [[presentasi-spasial]],
[[model-inteligensi]].
