name: ana-bit-builder
category: software-development
description: Use when building BIT target-gap diagnostics in SIMOGE HUD. Deterministic production investigation without LLM runtime.
version: 0.1.0
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

1. Discover the project's configured Obsidian vault, LLM Wiki, knowledge-base retrieval interface, and existing skills/tools. Do not assume a filesystem path or tool name; inspect configuration and available tools. Concrete sources in this repo: `docs/kontek_bisnis.md` + `docs/refaktor/2nd_kontek_bisnis_diperjelas.md` (canonical), `docs/PENGUJIAN/pengujian_anna_02_07_10_2026.md` (18-point checklist), `brain://` via `mcp__gbrain__search` (fallback ke `read_file` docs bila gbrain unavailable).
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
