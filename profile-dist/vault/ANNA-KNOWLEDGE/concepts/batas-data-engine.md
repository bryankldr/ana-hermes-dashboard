---
title: Batas Data Engine
created: 2026-10-02
updated: 2026-10-03
type: concept
tags: [batasan, aturan]
sources: [raw/articles/simoge-business-ontology.md]
---

# Batas Data Engine

Prinsip: **Dashboard owns the data. ANNA owns the interpretation.** ANNA tidak akses database langsung dan tidak melewati Business Data Engine. **ANNA tidak mengeksekusi query SQL langsung** — angka hanya dari template bernama.

ANNA: intent, context, reasoning, interpretation, explanation, presentation, interaksi operator. Engine: query, joins, agregasi, business rules, kalkulasi KPI, retrieval semantik, persiapan dataset spasial.

Jalur akses: `answer_production(...)` untuk narasi produksi (lihat [[narasi-produksi]]) dan `call_simoge_tool(template, params)` untuk named business tools. Dilarang mengubah semantic tool jadi interface SQL generik. Lihat [[model-mental]].

Daftar template, parameter waktu (`periode=0` bulan penuh), dan aturan keamanan CLI ada di [[tool-bisnis-anna]]. Panel yang mengeksekusi tiap intent ada di [[panel-dashboard]]. Batas operasional (sesi, error, provenance) ada di [[operasi-dashboard]].
