---
title: Panel Dashboard
created: 2026-10-03
updated: 2026-10-03
type: entity
tags: [dashboard, intent]
sources: [raw/articles/simoge-business-ontology.md]
---

# Panel Dashboard

Panel HUD `ana-hermes-dashboard` (port 8730) yang relevan bagi kerja ANNA.
Daftar panel lengkap di `ui/src/main.js` (map judul) — di sini hanya yang
menyentuh alur bisnis.

## Panel inti bisnis

- **INTELLIGENCE SURFACE** — terminal chat ANNA. Combo **SESI** (Indonesia:
  `HARI INI / KEMARIN / MINGGU LALU / LAMA`, tombol `+ BARU`) untuk pindah
  sesi; TTL sesi sliding 1 jam, persist file `.ana_session` + localStorage.
  Lihat [[operasi-dashboard]].
- **SPATIAL MAP** — peta Leaflet + box chart `#spatialChartWrap` (multi-chart,
  baris KPI, narasi) + badge provenance (`data 2026-09-23 · 8 hari lalu`).
  Target semua visual: `show_on_map` dan `show_for_intent`.
  Inventaris lengkap 13 komponen + tabel op di [[panel-spatial-map]].
  Lihat juga [[presentasi-spasial]], [[presentasi-chart]].
- **RESPONSE** — kartu jawaban teks/suara ANNA.
- **CHAT** — bar input operator (`modeBtn` CODING, tombol kirim + mic).
- **PROACTIVE BRIEFING** — ringkasan proaktif dari wiki + engine.
- **VAULT STATUS** — status vault `anna_brain`.
- **EVENT STREAM** — log kejadian dashboard (bukan pengganti evidence).

## Intent → panel

| Operator bilang | Panel + aksi |
|---|---|
| "tampilkan petak licin / bongkor di Glenmore" | filter → **SPATIAL MAP** via `show_on_map` |
| "bandingkan / tren / ranking ..." | **SPATIAL MAP** chart via `show_for_intent` |
| "buatkan review bulan X" | 6 section via `run_business_review`, siar per section |
| "berapa / siapa / kenapa ..." | **RESPONSE** via `answer_question`, satu visual |

Aturan intent lengkap di [[semantik-dashboard]]; konteks wajib
dipertahankan lintas giliran ([[preservasi-konteks]]). Angka selalu dari
Business Data Engine ([[batas-data-engine]]), ANNA hanya interpretasi.
