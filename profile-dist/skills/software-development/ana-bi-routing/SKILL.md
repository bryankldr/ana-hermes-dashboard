---
name: ana-bi-routing
version: "1.0.0"
author: ANNA
license: MIT
metadata:
  hermes:
    tags: [business-intelligence, simoge, bit, routing]
    related_skills: [ana-bit-builder, ana-bi-workflow, simoge-business]
description: Use when user asks complex getah production questions (mengapa/penurunan/kesimpulan tahun). Route to BIT + ana-bi-workflow and answer with evidence-labeled investigation.
---

## When to Use

- Complex business questions about getah production where the user wants **why / how / what-happened / conclusion**, e.g.:
  - `mengapa produksi tidak stabil?`
  - `mengapa penurunan produksi terjadi?`
  - `apa kesimpulanmu mengenai produksi tahun ini?`
  - `apa penyebab kekurangan produksi bulan ini?`
  - `tahun ini potensi produksi berapa?` (combination: conclusion + KPI)
- NOT needed for simple monthly totals / target achievement (`berapa total produksi bulan ini?`) — handle those directly via `ana-bi-workflow` KPI layer. If a follow-up asks "mengapa" after a KPI fact, escalate to this skill's BIT pipeline.
- Load this skill at session start when a complex BI question arrives.

## Routing — classify the question FIRST (before any engine call)

Do this in order; routing decides the pipeline, engines never bypass the classify step:

1. **Period:** explicit `tahun/bulan`? Resolve `periode` (1=P1, 2=P2). If a generic question names a month, probe backwards (P1→P2 prev month) until `production.actual_kg is not None` before concluding "belum tersedia" — the latest calendar period is often empty while an earlier one is the last complete (ana-bi-workflow §3).
2. **Scope:** operator language (Licin / Glenmore / Banyuwangi Barat / TPG) → resolve to official `kode_divre/kph/bkph/rph/tpg` via `wilayah_labels` first.
3. **Classify type:**
   - **KPI only** ("berapa total/apa realisasi/target bulan ini") → `ana-bi-workflow` `answer_production` (KPI layer).
   - **Complex investigation** ("mengapa/mengapa tidak/penurunan/penyebab/kekurangan/apa yang terjadi/kesimpulan") → BIT pipeline below.
   - **Mixed** (question contains a conclusion word AND a fact, e.g. "apa kesimpulan produksi tahun ini") → run BOTH KPI (`answer_production`) + BIT (`target_gap`/`diagnostic`) and synthesize with the FACT→GAP→DIAGNOSIS→LOCATION→IMPACT→ACTION workflow.
   - **Follow-up** ("mengapa" after a KPI answer) → escalate to BIT pipeline for that period.
4. **Integrity:** never fabricate. Missing data → explicit "belum tersedia", never zero; correlation only, never causal ("bergerak bersamaan", not "menyebabkan").

## Execution Pipeline (stage-based, deterministic BIT, 0 LLM in calculation)

Follow these stages in order; each stage is mandatory:

- **Stage 0 — classify** (Routing above).
- **Stage 1 — retrieve context (read-only):** ANNA Wiki first (free lookup), then vault only for schema/detail via `search_files`/`read_file`. Do not open `ana_journal`.
- **Stage 2 — contracts:** confirm the rencana contract / formulir and template availability for the period before building engines.
- **Stage 3 — build minimal slice:** KPI via `answer_production` + BIT engines (`target_gap`, `diagnostic`, `hypothesis`, `sebaran`, `analisis`) — deterministic, no hand-written SQL.
- **Stage 4 — investigate:** run BIT deterministic engines and read their structured outputs (not re-derive numbers by hand):
  - `target_gap`: target vs actual vs plan coverage (`plan_coverage`, `rencana vs target_expected`).
  - `diagnostic`: H1–H4 falsifiable drivers, per-level sebaran.
  - `hypothesis`: H1–H4 hypotheses with certainty labels.
  - `sebaran`: where the gap lives (per wilayah level DIVRE→KPH→BKPH→RPH→TPG→petak).
  - `analisis` / `rekomendasi`: trends, contribution, recommendations.
- **Stage 5 — findings & certainty:** state the strongest hypothesis, evidence strength, and certainty label.
- **Stage 6 — prioritize:** pick the actionable driver/action per FACT→GAP→DIAGNOSIS→LOCATION→IMPACT→ACTION.
- **Stage 7 — test & verify:** run the actual CLI/tests (see Quick Reference); if data is missing/stale, report "belum tersedia, bukan nol" with provenance, do not fabricate trend.
- **Stage 8 — document, release, learn:** keep factual sentences traceable to KPI evidence or template result.

## Execution Commands (terminal only — never `execute_code` for engine calls)

workdir = `ana-hermes-dashboard` (`ANA_WORKDIR`); set absolute `PYTHONPATH`.

**KPI layer** (simoge-business/scripts + ana-bi-workflow scripts):
```bash
PYTHONPATH=/home/bryankldr/PROYEK_2026/ana-hermes-dashboard/profile-dist/skills/software-development/simoge-business/scripts:$PYTHONPATH \
  python3 /home/bryankldr/.hermes/profiles/anna/skills/software-development/ana-bi-workflow/scripts/ana_kpi.py \
  tahun=2026 bulan=2 periode=2 mode=asisten
```

**BIT layer** (ana-bit-builder wrapper + simoge_db via .venv python):
```bash
PYTHONPATH=/home/bryankldr/PROYEK_2026/ana-hermes-dashboard/profile-dist/skills/software-development/ana-bit-builder/scripts:/home/bryankldr/PROYEK_2026/ana-hermes-dashboard/profile-dist/skills/software-development/simoge-business/scripts:$PYTHONPATH \
  /home/bryankldr/PROYEK_2026/ana-hermes-dashboard/.venv/bin/python3 -c "from ana_bit_tool import call_bit_tool; print(call_bit_tool('target_gap', {tahun:2026,bulan:2,periode:2,sampai_dengan:'ya',include_breakdown:True,kode_bkph:'3121101'}))"
```
BIT pitfalls (from ana-bit-builder): server must run with `.venv/bin/python` for argon2/pymysql; `simoge_db` resolves only when PYTHONPATH includes `simoge-business/scripts`; shell-loop must split tahun/bulan/periode into separate vars (`tahun=$Y bulan=$B periode=$P`); raw rows return `Decimal` — normalize with `float(x) if isinstance(x, Decimal)` before JSON/chart.

## Answer Format (required)

- **Structure:** Context → Repository findings → Plan → Changes → Validation → Limitations → Next phase.
- **Diagnostic workflow (FACT→GAP→DIAGNOSIS→LOCATION→IMPACT→ACTION)** for every why/how analysis — do not skip; continue through Plan vs Actual, petak/andil shortfall, penyadap, spasial, contribution, and state data limitations.
- **Chart sequence:** Target vs Realisasi → Plan vs Actual → Petak/Andil shortfall → Penyadap → Spasial → Contribution → State limitations.
- **Evidence labels:** every factual sentence → traceable to KPI `evidence` or template result; distinguish SOURCE / DERIVED / COMPARATIVE / INTERPRETATION.
- **Correlation, never causation**; missing data → explicit "belum tersedia" (never zero).
- **TTS/Voice (asisten mode):** never utter code names — use human wilayah names (`BKPH Licin`, `KPH Banyuwangi Barat`, `TPG…`) never raw `kode_*` or numeric codes. Resolve via `wilayah_labels` before narration. Keep TTS 3–5 informative sentences.

## Quick Reference — Common Calls

```python
# Production KPI (via ana-bi-workflow ana_kpi.py)
answer_production(tahun, bulan, periode, mode, kode_bkph="3121101")

# BIT engines (via ana_bit_tool.call_bit_tool)
call_bit_tool("target_gap", {tahun, bulan, periode, sampai_dengan="ya", include_breakdown=True, kode_bkph="3121101"})
call_bit_tool("diagnostic", {tahun, bulan, periode, sampai_dengan="ya"})
call_bit_tool("hypothesis", {tahun, bulan, periode, sampai_dengan="ya"})
call_bit_tool("sebaran", {tahun, bulan, periode, sampai_dengan="ya"})
call_bit_tool("analisis", {tahun, bulan, periode, sampai_dengan="ya"})

# Spatial chart (via ana-bi-workflow/ana-chart)
show_spatial_chart(type="bar", title="Produksi per BKPH", labels=[...], datasets=[{"label":"Ton","data":[...],"color":[...],"colors":[...]}])
```

## Related References

- `simoge-business/references/` — entities, concepts, queries, aliases, rules
- `ana-bit-builder` — BIT engines (bit_engine.py, ana_bit_tool.py)
- `ana-bi-workflow` — KPI layer, chart, integrity rules
- `simoge-business/scripts/` — `ana_kpi.py`, `ana_chart_tool.py`
