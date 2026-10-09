---
name: ana-bi-workflow
version: "1.0.0"
author: ANNA
license: MIT
metadata:
  hermes:
    tags: [business-intelligence, simoge, kpi, production]
    related_skills: [simoge-business, ana-chart, ana-hud]
description: Answer BI questions for ANNA. KPI workflow, charts, context.
---

## When to Use

- Any business intelligence question about getah production (produksi, target, realisasi, achievement)
- Need to generate charts, dashboards, or spatial visualizations for production data
- Need business context: entities (petak, andil, penyadap, TPG, KPH, BKPH), concepts (alias wilayah, status petak), query patterns
- Diagnostic analysis: why/how production missed target (FACT→GAP→DIAGNOSIS→LOCATION→IMPACT→ACTION)

# ANNA Business Intelligence Workflow Skill

> Single source of truth for how ANNA answers business questions. Load this skill at session start.

## 1. Data Access — KPI Layer (THE ONLY PATH)

**Module:** `ana_kpi.py` (inside skill `simoge-business/scripts/`)

**Entry point:**
```python
from ana_kpi import answer_production
answer_production(tahun=2026, bulan=2, periode=1, mode="asisten", **wilayah)
# Returns: {kpi, narrative, narrative_short}
```

**Parameters:**
- `tahun`, `bulan`, `periode` (1=P1, 2=P2) — wajib
- `mode`: "asisten" (TTS short) | "coding" (full 6-section narrative)
- `**wilayah`: filter kode_divre, kode_kph, kode_bkph, kode_rph, kode_tpg (string)

**Output KPI object (§3 contract):**
- `production.actual_kg` + `actual_str` (ton)
- `trend.growth_pct` vs periode sebelumnya
- `achievement.pct` vs target RKAP
- `petak.n_active`, `penyadap.n_active`
- `evidence` trace per metric (template + params)
- `limitations` array (missing data, not zero-filled)
- `sources` with row_count, elapsed_ms

**Forbidden:** Direct SQL, `simoge_db.q`, docker/mysql, hand-written SELECT.

## 2. Business Engine — Named Templates Only

**Skill:** `simoge-business` → `call_simoge_tool(template, params)`

**Templates used by `answer_production`:**
| Template | Purpose |
|---|---|
| `produksi_aktiv` | Actual production totals (SUM berat_penerimaan) |
| `rkap_map` | Target & achievement aggregation |
| `wilayah_labels` | Resolve kode → human names |
| `status_petak_per_wilayah` | Petak universe counts |
| `penyadap_aktiv` | Active tapper counts |
| `andil_aktiv` | Andil (garapan) counts |

**Guard:** Anti-distorsi target — Σ target_periode ≈ Σ target_rkap × persen skalar (join ganda pernah gandakan target 40.9% palsu).

## 3. Execution Pattern

**Only via `terminal` with absolute PYTHONPATH — never `execute_code`:**
```bash
# terminal tool, workdir = ANA_WORKDIR (ana-hermes-dashboard)
PYTHONPATH=/home/bryankldr/PROYEK_2026/ana-hermes-dashboard/profile-dist/skills/software-development/simoge-business/scripts:$PYTHONPATH \
  python3 /home/bryankldr/.hermes/profiles/anna/skills/software-development/ana-bi-workflow/scripts/ana_kpi.py tahun=2026 bulan=2 periode=1 mode=asisten
# For batch probe (find latest complete period) loop P1/P2 backwards; parse JSON with python3 -c "import json,sys; d=json.load(sys.stdin); print(d['kpi']['production']['actual_kg'])"
# Pipes into another interpreter are blocked in some panels — redirect to /tmp/*.json then read_file if needed.
```
**Pitfalls:**
- `from hermes_tools import tool_call` / `call_simoge_tool` inside `execute_code` fails with `ImportError: cannot import name 'tool_call'` — use `terminal` above, not `execute_code`.
- `simoge_db` resolves only when PYTHONPATH includes `simoge-business/scripts`; without it `ModuleNotFoundError: No module named 'simoge_db'` — always set absolute PYTHONPATH as shown and set `workdir` to ANA_WORKDIR.
- Generic "berikan analitik" without explicit period → probe backwards from requested month (P1→P2 prev month) until `production.actual_kg is not None` before concluding "belum tersedia"; latest calendar period (e.g. P1 Oktober 2026) is often empty while P2 Agustus 2026 is last complete — reporting only the empty period misleads the operator.
- `ana_chart_tool.py` lives only under `simoge-business/scripts` (`profile-dist/skills/software-development/simoge-business/scripts/ana_chart_tool.py`); `ana-bi-workflow/scripts/ana_chart_tool.py` does not exist — verify `pathlib.Path.exists()` before invoking and set PYTHONPATH to `simoge-business/scripts`.
- Data Sep-Okt 2026 often not yet ingested (`data_freshness` tgl 2026-09-23, stale 16 hari) — surface `provenance` badge and state "belum tersedia, bukan nol" instead of reporting zero or fabricating trend.
- Voice name is ANNA (Gadis=ANNA, Ardi=MAX via `voice.agent_name()`) — never utter another name when asked; TTS must use human wilayah names (BKPH LICIN/GLENMORE, KPH Banyuwangi Barat) never raw `kode_*` or numeric codes (31211, 3121101).

## 4. Visualization / Chart

**Skill:** `ana-chart` → `show_spatial_chart(type, title, labels, datasets)`
**Skill:** `simoge-business` → `call_simoge_packet` + `show_dashboard`

**Auto-escalation rule (voice mode — HUD-dependent):** Legacy HUD: User says "chart", "grafik", "visual", "dashboard", "peta" → MUST `set_mode("coding")`, render via `call_simoge_packet`+`show_dashboard`, then `set_mode("asisten")`. Current HUD (2026-10-09, `[MODE: asisten]` injection): chart/peta/pandas adalah TOOL BIASA — eksekusi langsung di `asisten` via `terminal`/`execute_code` tanpa `set_mode`; TTS-only saat visual diminta eksplisit = GAGAL. Deteksi HUD dari prefix prompt dan ikuti aturannya.

**Business indicator palette (wajib):** Merah `#EF4444`=bad/bongkor/gagal target <60%, Kuning `#FACC15`=warn/idle/kurang, Hijau `#22C55E`=good/aktif/terpenuhi/capai target, Biru `#3B82F6`=info/multi-penyadap/tren. `spatialChart.js` PALETTE `[merah,kuning,hijau,biru,…]` dan `STATUS_TONE` {Bongkor:merah, Idle:kuning, Aktif:hijau, Multi penyadap:biru}; `ana_chart_tool.py` bullet tone `#22C55E`/`#EF4444`/`#FACC15`. Kirim `colors` eksplisit bila kategori punya makna bisnis tetap — jangan biarkan fallback acak.

**Pandas + Chart combo (zero-token planning):** Wiki map intent→template (gratis) → `call_simoge_packet`/`analyze_template(operations=[groupby_agg,pivot,pct_change,contribution])` → feed `labels`/`datasets` ke `show_spatial_chart`/`show_dashboard` (grid: `charts[]+kpis[]+narration+evidence`) dalam SATU `execute_code`/`terminal`. `spatial_chart_store.py` `visible/layout=kpis/charts/narration/evidence` dipoll frontend 2 detik.

## 5. Business Context — ANNA Wiki

**Source:** `profile-dist/skills/software-development/simoge-business/references/`

**Key files:**
- `entities.md` — 18 entities (petak, andil, penyadap, tpg, kph, bkph, rph, divre, mandor, target, rencana_aktivitas, aktivitas_penyadapan, produksi, operator_lapangan, panel_dashboard, panel_spatial_map, peran_jabatan, petak_polygon)
- `concepts.md` — 56 concepts (alias_wilayah, status_petak, batas_data_engine, penanganan_ambigu, etc.)
- `queries.md` — 26 query patterns

**Load:** `skill_view(name='simoge-business', file_path='references/entities.md')`

**Alias wilayah (critical):** Resolve operator language → official filter BEFORE calling engine. See `alias_wilayah` concept.

**Vault = `~/anna_brain/Anna's brain/` (118 .md, ANNA-KNOWLEDGE/entities,concepts,queries,raw/articles) — jangan pernah buka `ana_journal`.** Direct file access via `search_files(target='content', pattern, path=vault)` → `read_file`; jangan pakai Obsidian REST API/connector. Detail strategi, struktur, key files, anti-pattern di `references/vault_access.md`.

**ANNA Wiki (system prompt) = LLM Wiki (Karpathy pattern) — sudah loaded, zero-token lookup.** Workflow token-efisien: ① cek ANNA Wiki dulu (gratis) ② butuh detail/schema → `search_files`/`read_file` vault (tool-call only) ③ kirim ke LLM hanya extracted fact (1–2 kalimat), bukan full file. Wiki = compiled knowledge (cross-ref, contradictions flagged); vault = source of truth untuk konfirmasi dan update.

## 6. Diagnostic Workflow (FACT→GAP→DIAGNOSIS→LOCATION→IMPACT→ACTION)

**Required for every why/how analysis** (per `docs/PENGUJIAN/pengujian_anna_02_07_10_2026.md`):
1. FACT — observed numbers from KPI
2. GAP — delta vs target/prev/benchmark
3. DIAGNOSIS — driver (petak/andil/penyadap/spasial/contribution)
4. LOCATION — specific BKPH/RPH/TPG/petak
5. IMPACT — volume & financial implication
6. ACTION — concrete next step

**Chart sequence:** Target vs Realisasi → Plan vs Actual → Petak/Andil shortfall → Penyadap → Spasial → Contribution → State limitations.

## 7. Mode Control (HUD)

```python
from ana_mode_tool import set_mode
set_mode("coding")   # before heavy render (legacy HUD only)
# ... render chart/dashboard ...
set_mode("asisten")  # before final TTS delta
```

Server auto-restores `coding→asisten` after `t:complete` if forgotten. Pada HUD `[MODE: asisten]` terbaru, skip `set_mode` — render langsung di `asisten` (lihat §4).

## 8. Integrity Rules

- Every factual sentence → traceable to `kpi.evidence` or template result
- Distinguish: SOURCE (direct), DERIVED (calculated), COMPARATIVE (delta), INTERPRETATION (business meaning)
- Correlation language only ("bergerak bersamaan"), never causal ("menyebabkan")
- Missing data → explicit "belum tersedia", never report as zero
- `petak_simple.json` = dimension + freshness stamp ONLY, not KPI source

## 9. TTS/Voice Output Rules (asisten mode)

**JANGAN PERNAH sebut kode teknis di TTS:**
- ❌ `kode_divre`, `kode_kph`, `kode_bkph`, `kode_rph`, `kode_tpg`
- ❌ `31211`, `3121101`, `3121104`, dll
- ✅ Gunakan nama manusia: "Divre Jawa Timur", "KPH Banyuwangi Barat", "BKPH Licin", "BKPH Glenmore", "RPH...", "TPG..."
- ✅ Scope: "seluruh petak RTT KPH Banyuwangi Barat" atau "area BKPH Licin"

**Panjang TTS:** Cukup untuk menjelaskan konteks, fakta kunci, dan implikasi — 3-5 kalimat informatif. Tidak terlalu singkat (1-2 kalimat) sampai tidak jelas, tidak terlalu panjang sampai membosankan. Fokus: apa angkanya, artinya apa, apa yang perlu diperhatikan.

**Resolver:** `wilayah_labels` template → human names. Selalu panggil sebelum narasi TTS.

## 9. Quick Reference — Common Calls

```python
# Production KPI
answer_production(tahun, bulan, periode, mode, kode_bkph="3121101")

# Fuzzy (natural language wilayah)
answer_production_fuzzy(tahun, bulan, periode, wilayah_nama="Licin", mode)

# Spatial chart
show_spatial_chart(type="bar", title="Produksi per BKPH", labels=["LICIN","GLENMORE"], datasets=[{"label":"Ton","data":[118,95]}])

# Map display
call_simoge_tool("show_on_map", {"geojson": ..., "style": {...}})
```

## 10. Scalability Notes (multi-Divre, hundreds of KPH, thousands of TPG)

- `run_kpi.py` = thin CLI wrapper, zero scaling concern — just passes params to `answer_production()`
- `answer_production()` calls 9 named templates via `call_simoge_tool()` — **server-side filtering** on `_WILAYAH_KEYS` (kode_divre/kph/bkph/rph/tpg) in WHERE clause
- Templates `produksi_aktiv`, `rkap_map`, `wilayah_labels`, etc. already accept filter params — **no code change needed** for new wilayah
- Database: MariaDB + indexes on wilayah columns — standard RDBMS scaling

**Known scaling pressure points & mitigations:**
| Area | Risk | Mitigation |
|---|---|---|
| `rkap_map` `limit=2000` | May truncate if scope >2000 rows | Add pagination `offset` param to template |
| `petak_simple.json` | Dimension file grows (thousands of petak) | Freshness stamp exists; consider PMTiles/tileserver for map |
| `show_spatial_chart` | Thousands of BKPH/TPG labels unreadable | Pre-aggregate in template (SUM per BKPH) before chart |
| `wilayah_labels` | Resolve names for thousands of codes | Cache lookup / materialized view |

**Rule:** Template params handle scope; never hardcode wilayah in Python. Add filters to template, not to wrapper.

## 8. Quick Reference Files

| File | Purpose |
|---|---|
| `references/pandas_usage.md` | **Pandas engine cheat sheet** — operations, templates, CLI test, integration pattern |
| `references/vault_access.md` | **Vault access best practice** — search strategy, tools, key files, anti-patterns |
| `QUICK_REF.md` | One-page CLI + TTS rules |
| `references/templates.md` | All 42+ SIMOGE templates |
| `references/entities.md` | Business entities (petak, penyadap, andil, TPG, KPH, dll) |
| `references/concepts.md` | Business concepts (kondisi, status, produktivitas, dll) |
| `references/rules.md` | Diagnostic workflow, evidence rules, chart sequence |
| `references/charts.md` | Chart types, spatial chart, dashboard panels |
| `references/maps.md` | Spatial map components, show_on_map |
| `references/queries.md` | Common query patterns |
| `references/aliases.md` | Wilayah aliases (Licin, Glenmore, dll) |
| `references/geo.md` | Geometry, PMTiles, spatial index |
