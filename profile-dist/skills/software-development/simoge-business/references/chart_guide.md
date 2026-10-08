# Chart Guide — detail `ana_chart_tool.py` (dipindah dari SKILL core)

## Satu box bisa beberapa chart
`layout` `single`=1 chart, `grid`=2+ chart grid 2–3 kolom (`--ana-cols` 3 kolom kalau >3 chart), KPI di atas narasi di bawah. `MAX_CHARTS=6` + 8 KPI. `chart` alias `charts[0]` back-compat.

## Mapping intent → visual (`docs/refaktor/anna_chart.md`)
| Intent | Chart | Intent | Chart |
|---|---|---|---|
| `target_comparison`/`achievement` | bullet | `distribution` | bar |
| `trend` | line | `relationship`/`correlation` | scatter |
| `ranking`/`region` | h_bar | `intensity` | stacked_bar |
| `composition`/`status` | stacked_bar | `contribution` | doughnut |
| `pareto` | pareto | `gap`/`change_to_target` | waterfall |
| `location` | peta | `kpi`/`current` | KPI card |

## Lebih dari 1 chart — show_dashboard
```bash
python3 .../ana_chart_tool.py show title="..." charts='[{"type":"stacked_bar","title":"Status","labels":["A"],"datasets":[{"label":"aktif","data":[1]}]}]' kpis='[{"label":"AKTIF","value":"9.821"}]' narration="..."
```

## Laporan multi-halaman show_report
Satu `pages[]` = 1 halaman A4. Block: `para`,`note`,`list`,`kpi`,`table`.
```bash
P='[{"title":"RINGKASAN","blocks":[{"type":"kpi","items":[{"label":"PRODUKSI","value":"909.725"}]},{"type":"para","text":"..."}]}]'
python3 .../ana_chart_tool.py laporan act=show title="LAPORAN" pages="$P"
python3 .../ana_chart_tool.py laporan act=hide
```
`get_report()` dulu bila user minta tampilkan — jika visible true, `hide_report()` dulu baru `show_report()`.

## Presentation engine
`run_business_review(tahun, bulan, periode)` susun 6 section tapi tidak tampil sekaligus. `present_section(rv,"petak",with_map=True)` tampil per section. Scope default `level="kode_bkph"`.

## T3 atomik — review + show_report sekali (2-4 calls bukan 14)
Jalur wajib: `review` (1 call 6 section) → `laporan act=show` (1 call). `sections_full` punya `kpis`+`narrative` → `pages=[{"title":s["title"],"blocks":[{"type":"kpi","items":s["kpis"]},...]}]`. Rows tetap di engine.

## 6 section + template asal
`ringkasan` status_petak_per_wilayah+produksi_per_wilayah · `petak` bongkor_per_wilayah · `aktivitas` aktivitas_agregat · `produksi` produksi_per_wilayah · `cross` aktivitas_petak_map · `kesimpulan` narasi.

## Kewajiban kejujuran
- Scatter = pola, bukan sebab.
- P4 kosong → sebutkan.
- Data tak cukup → "belum cukup untuk menentukan penyebab".
- Angka `_fmt_num` (ribuan `.` desimal `,`).
