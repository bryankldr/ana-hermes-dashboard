---
title: Metrik Aktivitas
created: 2026-10-02
updated: 2026-10-18
type: concept
tags: [aktivitas, kpi]
sources: [raw/articles/simoge-business-ontology.md, raw/articles/skema-database-kph-bwb-sandbox2.md]
---

# Metrik Aktivitas

[[aktivitas-penyadapan|Aktivitas]] dianalisis per: jumlah, [[penyadap]], [[periode]], wilayah, [[petak]], [[rencana-aktivitas|rencana]], status, dan **jenis aktivitas × pohon**.

## Jenis × pohon

Setiap aktivitas membawa 6 flag (`quare`, `semprot_cas`, `budaya_bersih`, `kerok`, `naik_batok`, `pulung`) dan 6 kolom `jml_phn_*` (pohon tersentuh per jenis per baris). Lihat [[aktivitas-penyadapan]] tabel arti. Agregat per jenis: `COUNT(*) WHERE flag=1` = frekuensi jenis; `SUM/MAX(jml_phn_*)` = pohon tersentuh (coverage vs intensitas). Snapshot 2026-10-03: `jml_phn_*` 100% NULL — laporkan `DATA_QUALITY` bila diminta, jangan fabrikasi.

## Level agregasi

- **Aktivitas count** = baris `getah_aktivitas_sadap` pada `tgl_pembaharuan BETWEEN _range_bounds(sampai_dengan)`.
- **Per jenis** = `aktivitas_agregat(grup_by=aktivitas)` — Quare, Semprot CAS, dst, terurut count desc.
- **Per penyadap / petak / pembaharuan** = `aktivitas_agregat` / `aktivitas_top_petak`.
- **Rencana vs Aktivitas vs Penerimaan** = L3 Diagnostic (`bit_engine.get_diagnostic`): Target → Rencana (berat) → Aktivitas (count + per jenis + pohon) → Penerimaan (berat, `Q=N×A×F×Y`). Gap dipecah per wilayah/petak.

Jumlah aktivitas ≠ jumlah penyadap. Lihat [[distingsi-semantik-kritis]] dan [[gap-produksi]].
