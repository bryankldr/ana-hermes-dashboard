---
name: business-diagnostics
description: Use when diagnosing why/how business metrics miss target.
---

# Business Diagnostics — FACT → ACTION

Class-level workflow for every evaluative question (`mengapa` / `bagaimana` / `analisis` / `penyebab` / `tidak stabil` / `tidak tercapai`) across all domains (petak, aktivitas, produksi, target) and periods. Not limited to May or production decline.

## When to Use
Trigger: user asks evaluative why/how/analysis on any KPH/BKPH/RPH/TPG scope or period. Do not answer with a single Target vs Realisasi comparison — run the full workflow.

## Source of Truth
- `docs/PENGUJIAN/pengujian_anna_02_07_10_2026.md` — 18-point checklist and 6-section narrative structure (condensed here; read full file when checklist detail needed).
- `docs/kontek_bisnis.md` + `docs/refaktor/2nd_kontek_bisnis_diperjelas.md` — semantics (petak vs andil, bongkor definitions, 4 spatial domains).
- Numbers only from Business Data Engine: `ana_kpi.answer_production` (`kpi.evidence`) or `ana_simoge_tool.call_simoge_tool` / `call_simoge_packet`. Wiki/ontology never supplies numbers.

## Procedure — FACT → GAP → DIAGNOSIS → LOCATION → IMPACT → ACTION

1. **FACT — Target vs Actual**: `Achievement = Actual/Target*100%`, `Gap = Actual-Target`, `Gap% = (Actual-Target)/Target*100%`. Report one consistent figure per scope/period (never a range like "800–907 ton" without labeling which scope).
2. **GAP — Plan vs Actual**: distinguish `Target (getah_petak.target_rkap × persen RO/NPS kumulatif) → Rencana (getah_rencana_aktivitas.rencana_berat, WHERE tanggal_rencana BETWEEN period_bounds) → Aktivitas Aktual (getah_aktivitas_sadap, filter tgl_pembaharuan) → Penerimaan Aktual (getah_aktivitas_penerimaan.berat_penerimaan)`. Compute `Target Coverage = SUM(rencana_berat)/Target_kumulatif`, `Plan Achievement = Penerimaan/Rencana`, `Activity Completion = Aktivitas Aktual / Aktivitas Rencana`. Scalar `rencana_aktivitas(tahun,bulan,periode)` is single source for Coverage; `laporan_perencanaan_target_setor_vs_ro_nps` only for per-Mandor×TPG drilldown — it can return 0 rows while scalar shows 100+ ton due to `r.kode_evapot=pt.kode_evapot AND pt.tahun_rtt` join; cross-check scalar first and report template-empty as "laporan belum tersedia, bukan nol". `Rencana < Target` = planning failure; `Rencana > Target` but `Realisasi < Rencana` = execution failure; `Rencana > Target` is intentional buffer to absorb andil shortfall — evaluate buffer effectiveness, do not blame the buffer.
3. **DIAGNOSIS — Drill to petak/andil**: `TPG → RPH → BKPH → PETAK → ANDIL → PENYADAP`. Rank by contribution to gap (largest shortfall contributors), not object count. Surface achievement-low, productivity-low, bongkor/idle petak.
4. **LOCATION — Concentration**: find spatial concentration per BKPH/RPH/TPG. With Spatial Map: zoom + highlight shortfall petak, keep chart↔map in sync via `show_on_map` state-driven filter.
5. **IMPACT — Penyadap & productivity**: `rencana vs aktual vs achievement vs kg/ha and kg/penyadap`. Label `underperform`/`shortfall`/`indikator yang perlu diperiksa` until evidence supports stronger claim. Never equate bongkor count with cause — first compute `ha → estimated ton potential → Z% of gap` if data supports it.
6. **ACTION — Diagnosis + recommendation**: state what must be checked next. If data insufficient, say which piece is missing — never invent numbers.

## Language Guard — Anti-Causality
Forbidden without evidence (guarded in `ana_kpi.py: _FORBIDDEN_CAUSAL`, AssertionError): `menyebab*`, `disebab*`, `akibat`, `memicu`, `dipicu`, `pasti karena`, `kemungkinan besar`. Replace with `bergerak bersamaan`, `berkontribusi terhadap shortfall`, `indikator yang perlu diperiksa`, `faktor yang berkaitan`, `terkonsentrasi pada`, `berdasarkan data`. Correlation is not causation.

## Chart Priority (1–5, only when data supports)
1. Target vs Actual (gap magnitude) 2. Plan vs Actual (planning vs execution) 3. Shortfall contribution per wilayah/petak/andil (largest source) 4. Trend (one-off vs recurring). Do not create multiple charts without supporting evidence.

## Answer Structure
1. Brief conclusion 2. Primary chart 3. Diagnosis 4. Largest factor 5. Location of source 6. Impact 7. Recommendation / next investigation.

## Definition of Done
Can answer: How large is the gap? Planning vs execution vs productivity vs penerimaan failure? Which petak/andil/penyadap are top contributors? Which wilayah concentrates the gap? What is the impact on target? What must be checked next? If any question cannot be answered, explicitly state the data limitation.

## Pitfalls
- Running a single `Target vs Realisasi` chart and stopping — fails the 18-point checklist and the DOD above.
- Treating inactive-petuk count as proven cause without impact quantification.
- Mixing scopes/periods in one figure without labeling (e.g. P1 ton vs P2 ton as if same scope). Use `periode=0` (full month) consistently for monthly MoM trends.
- Reading Sep/Okt 0 kg / 0 aktivitas as real zero when `data_freshness.tgl_terakhir` is stale — label 'belum ada input' with `t_last`+`stale_hari`; compute Pearson `r` only on populated months (Jan–Agu) and phrase as 'bergerak bersamaan', never 'menyebabkan'.
- Building numbers from raw `rows` instead of `kpi.evidence` / packet `kpi` — hallucinates business rules.
- Looping `get_production_kpi`/`answer_production` per P1/P2 (9 queries × 16 periode = 144 queries, ~11 detik, data 2025 flat 0/798 tak terlihat) for tren/penurunan/korelasi — use 2 packet calls `produksi_trend` + `aktivitas_trend` which already return `breakdown[16]` + `drops` + `growth_pct`; looping wastes quota and hides staleness.
- Delivering TTS-only answer when prompt contains `chart`/`grafik`/`visual`/`tampilkan dalam chart` — must `set_mode("coding")` before `show_dashboard` (2 charts: produksi vs petak aktif + bongkor/idle vs penyadap) then `set_mode("asisten")` before final delta; TTS without chart = failed request.
