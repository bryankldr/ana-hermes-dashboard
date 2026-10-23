---
name: ana-bit-builder
category: software-development
description: Build deterministic BIT diagnostics for SIMOGE HUD.
version: 0.1.0
author: bryankldr, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [simoge, bit, diagnostics, metabase]
    related_skills: [simoge-business, ana-bi-workflow, business-diagnostics, maxbi, ana-hud-dashboard]
---

# BIT Builder — SIMOGE HUD

## Mission

Build and maintain the complete Business Investigation Tool (BIT) for pine-resin production target optimization. BIT must help authorized users determine:

1. Where production targets are at risk.
2. The size and urgency of the production gap.
3. Which measurable operational factors contribute to the gap.
4. Which feasible interventions offer realistic target-recovery opportunities.
5. Whether actions produce measurable operational improvement.

BIT is deterministic software. Its core business calculations and investigations must not require an LLM, Anna, Hermes, or external AI inference APIs at runtime. The LLM using this skill may assist software development, but the built BIT itself must operate without an LLM.

Scope excludes financial analysis. Do not calculate profitability, revenue, ROI, cost optimization, or financial recommendations.

## Non-negotiable principles

- **Business truth comes from verified sources:** database and approved operational records are authoritative for current facts; Obsidian and LLM Wiki provide curated domain knowledge, terminology, business rules, metric definitions, SOPs, schema maps, and prior decisions.
- **Retrieve before deciding:** consult relevant Obsidian/LLM Wiki entries before defining a KPI, selecting a table, interpreting a status, choosing a join, asserting a cause, or changing an operational rule.
- **Do not load the entire vault:** use targeted retrieval and progressive disclosure. Follow Wiki links to relevant supporting notes only.
- **Separate knowledge layers:** LLM Wiki explains what is known and why; this skill defines how to work; tools execute actions; the database supplies current records.
- **No fabricated business logic:** do not invent target distributions, status meanings, join keys, thresholds, columns, constraints, or operational rules.
- **Dashboard owns data, Anna owns interpretation:** BIT's deterministic backend owns retrieval, calculations, diagnostics, and evidence; Anna is not a runtime dependency of BIT.
- **Evidence before conclusions:** label findings as observed, calculated, suspected, verified, or inconclusive.
- **Read-only by default:** never automatically alter production, tapping, receipt, drum, transport, or perni records.
- **Least privilege:** enforce the authenticated user's organizational scope on the server for every query, detail view, export, map layer, and action.
- **Non-destructive engineering:** audit first, make the smallest viable change, preserve unrelated behavior, test, and document rollback.
- **Reuse Business Data Engine:** BIT wajib reuse `simoge-business` (`call_simoge_packet`/`call_simoge_tool`) dan `ana-bi-workflow` (`ana_kpi.answer_production`) — jangan bikin query layer baru. BIT adalah orchestrator di atas engine existing.
- **Do not claim tests passed unless they were actually run.**

## Mandatory knowledge retrieval: Obsidian + LLM Wiki

Before business analysis or implementation:

1. Discover the project's configured Obsidian vault, LLM Wiki, knowledge-base retrieval interface, and existing skills/tools. Do not assume a filesystem path or tool name; inspect configuration and available tools. Concrete sources in this repo: `docs/kontek_bisnis.md` + `docs/refaktor/2nd_kontek_bisnis_diperjelas.md` (canonical), `docs/PENGUJIAN/pengujian_anna_02_07_10_2026.md` (18-point checklist), `docs/18_10_2026/anna_spesialis_bisnis.md` (L0-L5 ontology, Q=N×A×F×Y model, H1-H4 matrix, causal 5-criteria, evidence 4-status, Investigation Case Store — architecture, not executable), `brain://` via `mcp__gbrain__search` (fallback ke `read_file` docs bila gbrain unavailable). Condensed mapping in `references/business-reasoning.md`.
2. Retrieve the most relevant notes for the task. Search for terms and synonyms covering:
   - getah pinus / resin production;
   - target production, target distribution, target achievement, cumulative target, production gap;
   - RTT / annual work plan and operational calendar;
   - tapping plans (`getah_rencana_aktivitas`, `rencana_berat`, `tanggal_rencana`, `id_rencana`) and tapping activity (`getah_aktivitas_sadap`, `tgl_pembaharuan`);
   - productive area, petak, and tapping type;
   - penyadap status and organizational hierarchy;
   - receipt, drum, transportation, and perni process;
   - KPI definitions, data dictionary, schema, relationships, and SQL/query conventions;
   - prior BIT, SIMOGE HUD, Business Data Engine, Metabase, map, authorization, and implementation decisions.
3. Read linked notes only when they are needed to resolve a definition or relationship.
4. Record a compact **Business Context Brief** for the current task containing:
   - relevant Wiki note titles/paths or stable references;
   - verified business definitions;
   - approved formulas and statuses;
   - verified source tables and join relationships;
   - effective dates/version and known caveats;
   - conflicts or missing definitions.
5. Compare Wiki knowledge against the current schema, code, and authoritative operational data where appropriate. Wiki documentation does not override newer verified source-of-truth records; database structure alone does not define the business meaning of a field.
6. If sources conflict, do not silently choose. Report the conflict, identify which source is authoritative for that specific question, and request a business decision only when the conflict blocks safe implementation.
7. Do not copy the entire Wiki into this skill or embed large vault excerpts into prompts. Keep reusable business definitions in the Wiki and reusable execution procedure here.
8. If Wiki retrieval is unavailable, state that limitation. Continue only with work that can be done safely; do not make business-rule-dependent changes based on assumptions.

Use the project's established retrieval interface and conventions. If `ana-self-dev` governs self-development, follow it for any skill/tool changes: Detect → Retrieve context → Plan → isolated Build/Test → Approve → Release → Record. Do not bypass approval requirements or modify active production files before the required audit and approval.

## Required operating workflow

### Stage 0 — Classify the request

Determine whether the task is:
- repository audit;
- business-context or metric-definition work;
- new BIT module;
- existing BIT bug fix;
- query/performance optimization;
- UI integration;
- Metabase integration;
- data-quality investigation;
- test/release/documentation work.

Retrieve only the relevant Wiki context and skill references for the task.

### Stage 1 — Read-only repository and runtime audit

Before editing, inspect:
- repository structure and current branch/status;
- frontend routes, shared layouts, component library, design tokens, and chart/report/map panels;
- backend entry points, framework, services, repositories, query layer, API conventions, and error handling;
- authentication, session management, roles, and organizational-scope enforcement;
- Business Data Engine or existing calculation/query services;
- MariaDB schema, migrations, indexes, and verified relationships;
- Metabase connection, saved questions, metrics, dashboards, API/embed patterns, and access controls;
- current tests, test fixtures, logging, job execution, and deployment conventions;
- existing map/MapLibre implementation and spatial-data delivery if relevant.

Never assume the old repository name is the current product name. Treat `ana-hermes-dashboard` as a legacy repository/directory name and SIMOGE HUD as the current project name unless repository evidence says otherwise.

Produce an audit summary before a risky or broad implementation:
- existing reusable modules;
- verified source-of-truth paths;
- existing metric implementations;
- gaps;
- authorization risks;
- minimal proposed changes;
- tests and rollback strategy.

Do not create a parallel application, new service, duplicate query layer, or new infrastructure before verifying that the existing architecture cannot support the requirement.

### Stage 2 — Establish business and data contracts

For every metric or rule, verify and document:
- stable identifier and business name;
- definition and formula;
- unit and aggregation grain;
- source table/view/question/service;
- correct event date and period semantics;
- filters and authorized scope;
- join keys and cardinality;
- null, zero, duplicate, and late-arriving record behavior;
- data freshness and cutoff;
- baseline/target semantics;
- limitations and validation examples.

Do not treat record creation time as event time unless verified. Do not assume every hectare is productive, every registered tapper performed work, or every upstream event must have an immediate downstream record.

Known project context can help guide searches but is not a substitute for verification. Candidate SIMOGE entities may include `getah_petak`, `getah_andil`, `getah_penyadap`, `getah_rencana_aktivitas` (rencana berat per penyadap/andil), `getah_aktivitas_sadap` (aktivitas lapangan), `getah_aktivitas_penerimaan` (realisasi timbang), `getah_target_ro_nps` (persen target per periode), `petak_polygon`, and related drum/angkut/perni tables. Confirm actual schema and relationship keys before using them. In particular, do not infer joins from similarly named fields; confirm the established relationship for each operational stage.

**Rencana contract (getah_rencana_aktivitas):**
- Grain: one row = one rencana per `id_rencana` (UNI) / `local_id` (offline sync UNI); `id_andil` + `id_penyadap` + `kode_evapot` + `tanggal_rencana`.
- Key joins: `getah_rencana_aktivitas --id_rencana--> getah_aktivitas_sadap --id_penyadap--> getah_penyadap / getah_aktivitas_penerimaan`; `getah_rencana_aktivitas --kode_evapot + tahun_rtt--> getah_petak` (laporan per TPG); `getah_rencana_aktivitas --user_created--> directus_users --jabatan--> jabatan (M1-M5 Mandor, K1-K5 KTS)`.
- Event date: `tanggal_rencana` (filter `BETWEEN period_bounds(tahun,bulan,periode)`, P1=1-15, P2=16-akhir) — never `date_created`. Compare `rencana_berat` (Kg) vs `target_rkap * _target_pct/100` (target kumulatif) and vs `berat_penerimaan` (realisasi).
- Verified templates to reuse (do not hand-SQL): `rencana_aktivitas(tahun,bulan,periode)` scalar `SUM(rencana_berat)`, and `laporan_perencanaan_target_setor_vs_ro_nps(tahun,bulan,periode)` per Mandor×TPG with dedup `GROUP BY user_created,kode_tpg,kode_evapot` + `SUM(DISTINCT target_rkap)` — without dedup target inflates 2-5×.
- Pitfall: `laporan_perencanaan_*` returning 0 rows ≠ no rencana — cross-check scalar `rencana_aktivitas` (can be 100+ ton while laporan 0 due to `r.kode_evapot=pt.kode_evapot AND pt.tahun_rtt` mismatch). Report as "laporan belum tersedia" not "nol".
- Null/zero: `rencana_berat` NULL = treat 0 with DATA_QUALITY flag; missing `kode_evapot` = orphan rencana, excluded from laporan join — count separately.

### Stage 3 — Build the smallest vertical slice

Implement one end-to-end capability at a time, including:
1. business definition from Wiki;
2. verified data source;
3. backend calculation/query;
4. authorization;
5. API contract;
6. UI view;
7. evidence/provenance;
8. tests;
9. documentation.

**v0.1 scope:** ship Target Gap Engine (Target vs Rencana vs Actual + plan coverage/execution gap) only as first vertical slice — requires `getah_rencana_aktivitas` + `getah_target_ro_nps` + `getah_aktivitas_penerimaan`. Other engines (productivity, reconciliation, spatial, root-cause, recovery) PROPOSED. Then expand into productivity, activity compliance, reconciliation, root-cause diagnostics, recovery prioritization, and follow-up.

### Stage 4 — Implement deterministic investigation engines

Use explicit business rules, parameterized queries, and suitable statistical algorithms. Do not rely on generative text to compute or validate results.

Potential engines:
- Target Achievement and Gap;
- Productivity and Baseline Comparison;
- Planned-versus-Actual Tapping Activity;
- Productive Capacity Utilization;
- Production Flow Reconciliation;
- Spatial Performance;
- Root-Cause Hypothesis Testing;
- Recovery Opportunity and Action Tracking;
- Investigation Audit and Reporting.

These are logical capabilities, not an instruction to create a separate microservice or file for every engine. Follow the existing architecture.

### Stage 5 — Findings and certainty labels

Each finding must distinguish:
- **OBSERVED:** directly present in verified source data.
- **CALCULATED:** derived from a documented formula.
- **SUSPECTED:** plausible explanation supported by partial evidence, not confirmed.
- **VERIFIED:** meets an explicitly documented verification criterion.
- **INCONCLUSIVE:** evidence is insufficient or conflicting.
- **DATA_QUALITY:** result is limited by missing, stale, duplicated, inconsistent, or unreconciled data.

A statistical outlier or correlation is not automatically a root cause. Show alternative hypotheses and the evidence required to distinguish them.

### Stage 6 — Prioritize operational recovery

Prioritize investigation and actions using transparent, configurable factors such as:
- target-gap magnitude and urgency;
- measurable contribution to the gap;
- recoverable production estimate;
- productive days remaining;
- feasibility and dependencies;
- evidence strength;
- technical, environmental, and sustainability constraints.

Do not invent official thresholds or weights. If no approved policy exists, label the initial scoring as proposed/configurable and document the approval needed. Estimated recovery is not guaranteed output.

### Stage 7 — Test and verify

Run applicable:
- unit tests for formulas, boundaries, null handling, and denominators;
- integration tests for source queries and API contracts;
- authorization tests across hierarchy levels;
- data-quality and join-cardinality tests;
- UI and API regression tests;
- reproducibility tests using the same source snapshot and rule version;
- performance checks for representative data volume.

Independently verify key calculations against known records or a separately computed reference. Do not report a test as passing if it was not executed.

### Stage 8 — Document, release, and learn

For each phase, record:
- files created and modified;
- Wiki references consulted;
- business definitions and data sources used;
- migrations and deployment steps;
- tests executed and actual outcomes;
- known limitations and unresolved questions;
- rollback procedure;
- acceptance criteria status.

Follow existing project release conventions and `ana-self-dev` approval gates. Do not release to production or modify active production files without required authorization.

## Business investigation principles

### A. Target Gap Engine

Minimum concepts:
- approved total target (`SUM target_rkap * 100%`);
- planned weight (`SUM getah_rencana_aktivitas.rencana_berat` per `tanggal_rencana`);
- actual valid production through a specified cutoff (`SUM getah_aktivitas_penerimaan.berat_penerimaan`);
- expected cumulative target as of that cutoff (`SUM target_rkap * _target_pct(tahun,bulan,periode)/100`);
- achievement percentage (actual / expected cumulative);
- plan coverage (rencana / expected cumulative) — distinguishes planning shortfall from execution shortfall;
- current gap = expected cumulative target − actual cumulative production;
- plan gap = expected cumulative target − planned weight;
- execution gap = planned weight − actual cumulative production;
- final gap = total target − actual cumulative production;
- remaining requirement;
- productive operating days remaining;
- required production rate;
- projected final production and forecast reliability.
- v0.1 must render Target vs Rencana vs Actual in one view; a single Target vs Actual comparison is reporting, not investigation.

Use approved target distribution and the operating calendar. Do not divide annual target evenly by calendar days unless the approved business rule explicitly says so. Handle zero targets, incomplete periods, missing targets, and insufficient forecast history explicitly.

### B. Productivity

Possible metrics, only when denominators are verified:
- production per active productive tapper;
- production per productive hectare;
- production per tapping activity;
- production per productive day;
- production by petak and organizational unit.

Compare like with like: period, tapping type, productive area, season, operating conditions, and data completeness. A metric difference alone does not prove poor technique or worker negligence.

### C. Activity compliance

Compare planned and actual tapping at the correct grain: `getah_rencana_aktivitas` (plan, key `id_rencana`) vs `getah_aktivitas_sadap` (actual, `tgl_pembaharuan` as period filter) vs `getah_aktivitas_penerimaan` (weighed actual). One rencana may map 0..1 aktivitas via `id_rencana`; do not assume 1:1. Explain whether a missing activity is truly absent, delayed, not synced, orphan (`kode_evapot` mismatch), or excluded by business rules. Report `Target Coverage = Rencana/Target`, `Plan Achievement = Penerimaan/Rencana`, `Activity Completion = COUNT aktivitas / COUNT rencana`. Do not equate an active account (`directus_users.status=active`) with productive activity.

### D. Reconciliation

Validate each process relationship and its cardinality before aggregation. Avoid fan-out joins and double-counting. Apply approved timing windows and legitimate exceptions. Quantify the effect of data discrepancies on reported production, if possible.

### E. Spatial investigation

Reuse existing SIMOGE HUD map infrastructure and authorized geographic filters. Use server-side filtering and suitable spatial delivery for large datasets. Do not load every polygon or all operational records into the browser.

### F. Action evaluation

Capture the baseline, action, responsible person, period, expected measurable outcome, actual outcome, and limitations. Do not claim causality when seasonality, weather, staffing, or other concurrent changes could explain the result.

## Metabase integration policy

Audit existing Metabase assets before creating new metrics or dashboards.

Use Metabase for existing dashboards, visual exploration, saved questions, and reusable analytical assets where appropriate. Keep investigation orchestration, rule execution, evidence validation, priority scoring, and action tracking in the existing SIMOGE HUD backend/Business Data Engine.

Choose between existing backend query services, verified SQL definitions, and the Metabase API based on the actual architecture. Never expose Metabase admin credentials in the browser. Do not assume Metabase questions enforce SIMOGE HUD's per-user organizational permissions.

## Security and data integrity

- All data access must use the authenticated identity and server-enforced authorized scope.
- Apply scope restrictions to aggregates, detail rows, evidence, exports, map features, cached results, and action history.
- Do not trust frontend-provided organization identifiers.
- Use parameterized queries and bounded execution.
- Never expose arbitrary SQL execution to ordinary users.
- Do not automatically edit operational records.
- Audit sensitive investigation access and action updates according to existing policy.
- Cache only when tenant/area scope, period, data freshness, and rule version are part of cache validity.
- Prevent duplicate runs or duplicate actions on retries where relevant.

## Pitfalls

- Draft `docs/*.md` copied from LLM generators often contains trailing Python (`write_text`, `zip_path`, `root / "SKILL.md"`, `build-checklist`) after the real Markdown — strip everything after the last valid `##` section and verify `wc -l` before installing, or the skill loads as broken code.
- `laporan_perencanaan_target_setor_vs_ro_nps` returning 0 rows does not mean no rencana — scalar `rencana_aktivitas` can still show 100+ ton; report as "laporan belum tersedia" and suspect `r.kode_evapot=pt.kode_evapot AND pt.tahun_rtt` join, not zero planning.
- Evidence labels collide: doc uses 4 hypothesis statuses (Terkonfirmasi/Didukung/Belum teruji/Tidak didukung), skill uses 6 finding labels (OBSERVED/CALCULATED/SUSPECTED/VERIFIED/INCONCLUSIVE/DATA_QUALITY) — map them in `references/business-reasoning.md`, do not invent a third taxonomy.
- Do not load entire `brain://` vault — targeted `mcp__gbrain__search` + `docs/kontek_bisnis.md` only; full-vault loads waste 300K+ tokens.
- `HERMES_HOME` in agent sessions may already be the profile dir — naively joining `profiles/anna/...` doubles the path and breaks `simoge_db` import; resolve via candidate list (explicit `ANA_SIMOGE_SCRIPTS`, then `ROOT/profile-dist/.../scripts`, then `HERMES_HOME` stripped to real home, then `~/.hermes/profiles/anna/...`) and try each.
- Plan/achievement gaps must use matching windows — `plan_gap = target_expected − rencana_ytd` and `execution_gap = rencana_ytd − actual_ytd` (both YTD); mixing period `rencana` with YTD target breaks the invariant by hundreds of tons.
- BIT is one engine with two consumers — `bit_engine.get_target_gap()` owns all math and cache (TTL 300s, key `scope+periode+rule_version`); `/api/bit/target_gap` and `ana_bit_tool.call_bit_tool("target_gap", …)` are thin wrappers that must not duplicate SQL or re-derive `_target_pct`.
- `Decimal` from `ROUND()`/`SUM()` is not JSON-serializable — convert breakdown rows to `float` and add a `Decimal` handler in `server.py:_json` default, or `/api/bit/*` will 500 on `include_breakdown`.
- Cache key must include `include_breakdown` (and any scope-altering flag) — otherwise a non-breakdown hit shadows the 43-row breakdown with an empty array.
- `simoge_db._conn` is a single shared `pymysql` connection with no lock — `ThreadingHTTPServer` concurrent `q()` calls interleave packets and raise `InternalError: Packet sequence number wrong - got 1 expected 18`. Guard `q()` with a `threading.Lock` or retry with `reset_conn()` on that error.
- Always start `server.py` with `.venv/bin/python`, not the Hermes interpreter — Hermes env lacks `argon2-cffi`/`pymysql` and every login fails `VerifyMismatch` even with the correct password (`<PASSWORD_REDACTED>` matches only under `.venv`).
- HUD layouts are per-user `layout_<uid>.json` (`desktop.layouts`) plus fallback `layout.json`; patching only the global file still hides the panel for logged-in users. Patch both and bump `src/main.js?v=` to bust the `immutable` cache.
- Cloud browser `use_real_profile` must match the drive mode — `use_real_profile true` with cloud browser (or `local:true` with it off) blocks `capture_screenshot` on the profile lock; toggle to match before visual tests.
- Freeze `metabase.py` until explicitly requested — BIT v0.1 ships without Metabase; audit existing cards before reusing via proxy.
- BIT drawer lives inside `mapPanel .map-wrap` (not a free `ensurePanel`/`layout.json` panel) — `position:absolute left:50% top:52px transform:translateX(-50%) width:min(520px,calc(100% - 24px)) z-index:335 max-height:min(56vh,520px) overflow:auto` between `mapBox` z0 and toolbar z440; every line of the HTML body in `ui/src/map.js` must be `+ '...'` (missing `+ '` = `SyntaxError: '' string literal contains an unescaped line break` and `mapPanel` never mounts); bump `ui/index.html` `map.css?v=` and `main.js?v=` on every CSS/JS change or `immutable` cache hides the fix; server must run with `.venv/bin/python` (argon2), not the Hermes interpreter.
- Keep BIT drawer `collapsed` by default — `dragging` switches from centered `transform` to `left/top` absolute via `headEl` `pointerdown/move/up` clamped to `.map-wrap`; resize via `bitResize` handle `nwse-resize` clamped to remaining width/height; both persist only in DOM (no layout.json entry).
- `sampai dengan` is the canonical window and must be threaded end-to-end: `Ya` = kumulatif `Jan 1 .. akhir periode` (`_range_bounds` + `_target_pct_sd` with `sampai_dengan=ya`; Penuh `0` = `Jan 1 .. akhir bulan`), `Tidak` = periode saja (`period_bounds`: P1 `1-15`, P2 `16-akhir`, Penuh `0` = `1-akhir bulan`; `_target_pct_sd` `tidak` gives `Penuh 9% = p1+p2 bulan saja`); canonical Feb 2026: `Ya Penuh 16% (7 Jan+9 Feb) 01-01..02-28 588800 kg` vs `Tidak Penuh 9% 02-01..02-28 331200 kg` vs `Ya P1 11.5%` vs `Tidak P1 4.5%`. `_target_pct` must handle `periode=0` as `SUM 1..bulan` (not P1-only) or `Ya Penuh` undercounts by one month (`11.5%` vs correct `16%`). `bit_engine.get_target_gap(..., sampai_dengan)` + `get_diagnostic` + `ana_bit_tool` + `POST /api/bit/{target_gap,diagnostic,hypothesis} {sampai_dengan}` + `_cache_key(..., sampai_dengan)` + drawer `bitSampai` `Ya(default)/Tidak` only (no `Ikut Map`) must agree — verify with the 4-row Feb table before shipping.
- Never hardcode 6 `jml_phn_*` SUMs — discover `AKTIVITAS_FLAGS`/`AKTIVITAS_LABEL` from `simoge_db` + `information_schema.COLUMNS`, build SELECT only for existing flag columns, and use `COALESCE(SUM(CAST(NULLIF(col,'') AS UNSIGNED)),0)` so varchar `''`/NULL today and int tomorrow both work; `pohon_tersentuh_total==0` must emit `DATA_QUALITY` limitation, and `Q=N×A×F×Y` must auto-switch `Y=actual/pohon_tersentuh` when filled else `Y=actual/n_aktivitas` via `_y_note` — otherwise adding one new aktivitas jenis requires rebuilding BIT.
- Global scope is `DIVRE→KPH→BKPH→RPH→TPG→petak` via `_WILAYAH_COLS` allowlist; every BIT query must go through `_wilayah_where(scope)` + `_enforce_wilayah_scope` (server-enforced per jabatan) and `N=SUM(jumlah_pohon)` must be scoped the same way — hardcoding `kode_kph=31211` breaks the day `31210` or a new DIVRE gets data. `kode_tpg_list` (M2M TPG-level user) is not handled by `simoge_db._wilayah_where` — BIT must wrap it in a helper `_wilayah_where(scope, alias, sdb)` that calls `sdb._wilayah_where` for single cols plus `AND alias.kode_tpg IN (%s,…)` for the list (digits-only, paramised); `get_sebaran` `_scope_without` must not drop `kode_tpg_list` or the breakdown becomes unscoped.
- Drawer business language is Indonesian — header `BISNIS — KESENJANGAN TARGET`, cards `Target/Realisasi/Cakupan Rencana/Kekurangan vs Target`, bar `Target YTD vs Rencana YTD vs Realisasi YTD` with dynamic `YTD` suffix (checked=show, unchecked=hide), `Telusur Rantai`, `Jenis Kegiatan/Keterangan`, `Uji Hipotesis Penyebab (H1–H4)`; never ship English `TARGET YTD/PLAN COVERAGE/ACHIEVEMENT/GAP` to users.
- YTD checkbox is the primary temporal control — drawer `YTD` defaults checked (`sampai_dengan=ya`, `Jan 1 s/d today`, disables Tahun/Bulan/Periode/Sampai dgn), persists `ana_bit_drawer_v1.ytd` in localStorage, resets to today on every `Tampilkan` while checked; unchecked re-enables manual filters and removes `YTD` from every label (`Target` not `Target YTD (kumulatif)`).
- Bar spec is exact: header `Target YTD vs Rencana YTD vs Realisasi YTD` (dynamic `YTD` suffix per `_ytdOn`), three rows `Target YTD |bar| kg`, `Rencana YTD |bar| kg | plan_coverage%`, `Realisasi YTD |bar| kg | achievement%`, then `Kekurangan | kg | 100-achievement%` — derive `_rencanaVal/_actualVal` from `rencana_main_kg/actual_main_kg` per `sampai_dengan Ya/Tidak`, not from hard-coded `rencana_ytd_kg`.
- BIT drawer is 4-tab (`Ringkasan` KPI+bar+Mandor×TPG, `Sebaran` L2 per `DIVRE→KPH→BKPH→RPH→TPG` via `get_sebaran` 1 level deeper than deepest scope, `Telusur` L3 Q-chain + jenis×pohon, `Dugaan` H1-H4 falsifiable) — HTML injected in `ui/src/map.js` `.bit-tabs/.bit-tab-pane`, CSS in `ui/styles/map.css`, tab persist `ana_bit_drawer_v1.tab`, fetch `/api/bit/hypothesis` then parallel `/api/bit/sebaran` (fallback `diagnostic→target_gap`), render via `renderSebaran/renderDiagnostic/renderHypothesis` in `ui/src/bitPanel.js`; bump `map.css?v=` + `main.js?v=` on every tab/CSS change.
- L2 `get_sebaran` must derive breakdown level from deepest scope (`global→BKPH, KPH→BKPH, BKPH→RPH, RPH→TPG, TPG→petak via aktivitas_top_petak`) and aggregate `target_rkap→target_expected`, `rencana_berat`, `berat_penerimaan` GROUP BY that level with LEFT JOIN for human names (`bkph.bkph/rph.rph` etc) — never hardcode `kode_kph=31211`.
- Never shadow outer `gap` (the `get_target_gap` dict) or `k/kpi` with `for k in ...` / `for gap in ...` loop vars inside `get_diagnostic`/`get_sebaran` — after that loop `gap.get("evidence")` becomes `float.get` and `500`s; name loop vars `ak`, `_gap_kg`, `kode` etc and shadowing breaks `evidence`/`limitations` merge.
- `get_sebaran` petak-deepest (`b_level=petak` when scope already `kode_tpg`) must aggregate per `kode_evapot` (`target_rkap→target_expected`, `rencana_berat`, `berat_penerimaan` GROUP BY evapot) with the same `kode_tpg_list`-aware `_wilayah_where` — returning `rows=[]` plus `top_petak` proxy loses gap ranking at the mandor/TPG level; rank 12 petak by `gap_kg` with `share_gap_pct`.
- Only `get_target_gap` is TTL-cached (`_CACHE` key `scope+periode+sampai_dengan+rule_version`); `get_diagnostic`/`get_hypothesis`/`get_sebaran` call it plus live DB — do not add a second cache without a `sampai_dengan`-aware key or stale `Ya` shadows `Tidak`.
- Vendor `//# sourceMappingURL=*.map` must be stripped when vendoring — the file is not shipped and every page logs `Source map error 404` that hides the real `Uncaught SyntaxError` in the next console block.
- Syntax audit must check served files, not just local: `curl -s http://127.0.0.1:8730/src/map.js > /tmp/c.js && node --check /tmp/c.js` — `node --check ui/src/map.js` alone can pass while a broken `+ '` concatenation still ships as 500/501 via `BaseHTTP` `HEAD`.
- Every line of `ui/src/map.js` drawer HTML must be `+ '...'` — one missing `+ '` between two `data-tab` buttons creates `'' string literal contains an unescaped line break` and `mapPanel` never mounts (drawer shows `loading tanpa henti` while `BIT` debug stays silent).
- Never reuse outer `k`/`gap`/`scope` as loop vars inside `get_diagnostic`/`get_sebaran` — `for ak in list(af.keys()): ... if ak.startswith` not `k.startswith`, or `NameError` falls into the except and diagnostic returns `n_aktivitas 0` while raw query shows `6659`.
- BIT terminal debug is `_blog(msg, level)` in `server.py` — `level="info"` only when `ANA_MODE=develop`/`ANA_DEBUG_MAP=1`, `level="error"` always to `logs/server.log` + stderr; log `target_gap/diagnostic/sebaran/hypothesis` with `tahun-bulan P periode s/d scope -> target/rencana/ach gap cached` and `limitations` so `tail -f logs/server.log | grep BIT` reveals why drawer is empty without opening the browser.
- Investigation Case Store (§G) is `data/bit_cases.json` JSON capped at 500 with `_clean(Decimal)` + atomic `.tmp` replace — snapshot auto-captures `kpi+aktivitas+hypotheses+sebaran_top2+query_ids` for reproducibility; `false_rate = Didukung/ Terkonfirmasi but gagal / closed` is the benchmark that prevents repeating a refuted hypothesis.

## Definition of done

A BIT capability is complete only when:
- its business meaning is grounded in relevant Obsidian/LLM Wiki sources;
- its source schema and relationships are verified;
- calculations are reproducible and tested;
- authorization is enforced server-side;
- evidence and limitations are visible;
- existing SIMOGE HUD functionality remains intact;
- tests actually run and results are documented;
- the feature has been integrated into the real application, not merely mocked in the UI;
- operational deployment and rollback instructions exist where applicable.

## When information is missing

Do not guess. Identify the exact missing item, its impact, and the safest next step. Continue independent work that does not depend on the missing decision. Ask for business-owner approval only when a definition, threshold, or operational policy materially blocks safe implementation.

## Default response format for build tasks

1. **Context retrieved:** Wiki references and verified definitions.
2. **Repository findings:** existing files/services to reuse.
3. **Plan:** smallest scoped implementation.
4. **Changes:** files and behavior implemented.
5. **Validation:** commands/tests actually run and outcomes.
6. **Limitations:** unresolved business/data/security risks.
7. **Next phase:** concrete next implementation step.
