# Business Reasoning — L0-L5, Q-Model, H1-H4, Evidence Mapping

Condensed from `docs/18_10_2026/anna_spesialis_bisnis.md` (272 lines, architecture — not executable). Keep canonical text in docs; this is the on-demand lookup for BIT builds.

## L0-L5 Decomposition (maps to FACT→GAP→DIAGNOSIS→LOCATION→IMPACT→ACTION)

| Level | Question | BIT engine |
|---|---|---|
| L0 Outcome | Apakah target tercapai? | Target Gap Engine (Target vs Rencana vs Actual) |
| L1 Deviation | Seberapa besar selisih? | Gap sizing: plan gap + execution gap |
| L2 Localization | Wilayah/periode/kelompok mana kontribusi? | rencana_aktivitas + laporan_perencanaan per BKPH/RPH/TPG/Mandor |
| L3 Driver | Faktor operasional apa berkaitan? | Productivity, Activity compliance, Capacity utilization |
| L4 Root cause | Mekanisme apa benar-benar menyebabkan? | Hypothesis Tester (H1-H4 below) + Reconciliation |
| L5 Intervention | Tindakan apa berpotensi? | Recovery Opportunity + Action Tracker |

Do not skip L1-L2 — single Target vs Actual is reporting, not investigation.

## Q = N × A × F × Y (illustrative, PROPOSED)

- Q = total produksi (Kg, `berat_penerimaan`)
- N = active productive tappers (`COUNT penyadap aktif`)
- A = avg effective area per unit (`luas_andil / N`)
- F = operation frequency per area (`COUNT aktivitas / A` via `tgl_pembaharuan`)
- Y = yield per area per operation (`Q / (A*F)`)

Status: PROPOSED — validate denominators first (not every ha productive, not every registered tapper active). Factors may not be independent or available. Use to distinguish capacity vs frequency vs yield drops, not as KPI until verified.

## H1-H4 Matrix — IMPLEMENTED in `bit_engine.get_hypothesis` (deterministic, vs prev month same periode + sampai_dengan)

| H | Hypothesis | Test | Required data | Status → rule (implemented) |
|---|---|---|---|---|
| H1 | Kapasitas tenaga kerja menurun | Δ n_penyadap_aktiv cur vs prev | penyadap status, periode aktif, produksi | Didukung if Δ ≤ -5%; Tidak didukung if Δ ≥ 0% (gugur); else Belum teruji |
| H2 | Aktivitas penyadapan berkurang | Δ n_aktivitas + per-jenis quare..pulung | rencana_aktivitas + aktivitas flags + luas | Didukung if Δ ≤ -5%; Tidak didukung if Δ ≥ -2%; else Belum teruji |
| H3 | Produktivitas per aktivitas menurun | Δ yield = actual/n_aktivitas (or actual/pohon_tersentuh when filled) | volume, valid aktivitas count, kondisi petak | Didukung if Δ ≤ -5%; Tidak didukung if Δ ≥ -2% |
| H4 | Masalah pencatatan/integrasi | DATA_QUALITY issues: jml_phn_* all NULL, target_pct 0, orphan petak, rencana>0 aktivitas 0 | timestamp, local_id, sync log | Didukung if any issue; Tidak didukung if none |

Prev = `get_diagnostic(prev_year, prev_month, same_periode, same_sampai_dengan)`; Belum teruji if prev missing. Each `hypotheses[].kondisi_gugur` stores kill condition. Sorted `hypotheses_sorted` by (Didukung > Belum teruji > Tidak didukung) then |Δ|.

Each hypothesis must state what evidence would reject it. Prioritize by test results, not initial guess.

## Causal 5-Criteria (before claiming cause)

1. Temporal precedence — factor precedes outcome per plausible mechanism.
2. Consistent association — stable across comparable strata.
3. Magnitude — explains observed gap size.
4. Confounder-adjusted — survives stratified / before-after / regression / DiD (DiD only if valid comparator exists; v0.1 limit to stratified + before-after).
5. Stronger than alternatives — beats competing H on evidence.

Without adequate identification design, report "faktor berkaitan" not "penyebab terbukti". Guard `_FORBIDDEN_CAUSAL` (`menyebab*`, `disebab*`, `akibat`, `memicu`, `pasti karena`) still applies.

## Evidence — 4 Hypothesis Statuses ↔ 6 Finding Labels

| Hypothesis status (doc) | Meaning | Finding label (skill) | When to use |
|---|---|---|---|
| Terkonfirmasi | Strong evidence, reproducible, alternatives tested | VERIFIED | documented criterion met |
| Didukung | Consistent pattern, some limits/alternatives remain | SUSPECTED | partial evidence |
| Belum teruji | Plausible, insufficient evidence | INCONCLUSIVE | open hypothesis |
| Tidak didukung | Tests weaken/contradict H | INCONCLUSIVE or DATA_QUALITY | negative result (record it) |
| — | directly in source | OBSERVED | row exists in DB |
| — | derived formula | CALCULATED | achievement %, gap |
| — | limited by missing/dupe/stale | DATA_QUALITY | orphan rencana, null rencana_berat |

Never use calibrated scores like "95%" without a calibration method.

## 5 Knowledge Layers (where to store)

- Obsidian: KPI definitions, SOP, ontology, official rules.
- LLM Wiki: curated periodic summaries, business context.
- Business Data Engine: current actuals/transactions (simoge-business templates).
- Investigation Case Store: hypotheses, test results, cases — PROPOSED, design pending after Data Engine audit (table `investigation_cases` vs `brain://` note, TBD).
- Memory/runtime: session interaction history.

## 7 Evaluation KPIs (benchmark suite to build before major changes)

Data accuracy, Diagnostic coverage, Hypothesis quality, Root-cause precision, False conclusion rate, Reproducibility, Business impact, Efficiency (tokens/time/tool calls). Build historical case bank (verified by domain experts, including incomplete/multi-cause/inconclusive cases) and test pre/post changes on same cases.

## Cycle

Deteksi masalah → uraikan deviasi → buat hipotesis alternatif → kumpulkan bukti → uji penyebab → evaluasi ketidakpastian → rekomendasikan tindakan → verifikasi hasil.
