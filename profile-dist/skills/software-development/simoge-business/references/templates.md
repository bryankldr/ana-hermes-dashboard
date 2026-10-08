## Templates (36, verified against live MariaDB)

Map polygon (7): `petak_bongkor_map`, `petak_efektivitas_map`, `petak_multi_penyadap_map`, `rkap_map`, `idle_petak_map`, `aktivitas_petak_map`, `matriks_map`
Point/detail: `aktivitas_recent` (recent GPS lat/lng/alt/pembaharuan_ke/foto scoped tahun/bulan/periode+wilayah), `penyadap_aktivitas` (per-petak 20 terbaru)
Labels: `wilayah_labels` (divre/kph/bkph/rph/tpg + human names)
Per-wilayah aggregates (all 5 levels via `level=` allowlist `kode_divre/kph/bkph/rph/tpg`, with `nama_wilayah` from `getah_petak` — no wilayah-table join needed): `status_petak_per_wilayah` (aktif/idle/bongkor partition-full `aktif+idle+bongkor=total` per grup + `luas_bongkor`, scoped tahun/bulan/periode via `_wilayah_where`), `produksi_per_wilayah` (kumulatif Jan s/d periode: actual + `target_rkap × _target_pct` + `achievement_pct` per wilayah), `bongkor_per_wilayah` (hardened: allowlist + `nama_wilayah`), `petak_by_kph` (hardened: allowlist + `nama_wilayah`)
Scalars: `target_pct` (persen RO kumulatif s/d periode — satu pintu dengan helper `_target_pct`, untuk guard KPI)
Stats/aggregate: `petak_count`, `petak_area`, `petak_with_geometry`, `petak_bongkor`, `petak_effectiveness`, `petak_detail`, `petak_penyadap`, `petak_adjacent`, `petak_multi_penyadap`, `petak_non_rtt`, `idle_petak`, `penyadap_productivity`, `produksi_aktiv`, `produksi_year_to_date`, `rkap_achievement`, `drum_flow`, `petak_tidak_efektif`

`list_templates()` returns names. `petak_by_kph` is **aggregate** (GROUP BY) — no polygon. `aktivitas_recent` is `limit` + optional `tahun/bulan/periode` (WHEN BETWEEN period_bounds) + `_wilayah_where` via JOIN getah_petak.


### Trend (hemat loop)
- `produksi_trend(tahun)` — 1 query 20 baris P1/P2 Jan-Des: bulan,periode,total_kg,n_petak. Packet hitung `growth_pct` + `drops<-30%`. Ganti loop 18x produksi_aktiv/ana_kpi.
- `aktivitas_trend(tahun)` — 1 query 20 baris: n_aktivitas,n_petak_aktif,n_penyadap per P1/P2. Packet untuk korelasi produksi-aktivitas.
