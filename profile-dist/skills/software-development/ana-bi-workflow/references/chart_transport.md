## Chart transport (bukan cara pakai)

Chart state adalah session memory di server: `spatial_chart_store.py` → `POST/GET /api/spatial/chart`,
header `x-ana-token` (UI pakai `X-Ana-Token`), `content-type: application/json`, dan **wajib**
`origin: http://127.0.0.1:8730` — tanpa origin akan kena `request origin rejected`. Frontend
poll tiap 2s, jadi publish terasa instan tanpa reload. ANNA pemilik show/hide.

Cara pakai (intent map, `show_dashboard`, `run_business_review`) ada di
**Chart & Presentasi** di atas — jangan pakai section ini sebagai rujukan tipe, daftarnya
sudah usang. Tipe valid (11, store yang menyaring): `bar, h_bar, line, stacked_bar, bullet,
pareto, waterfall, scatter, doughnut, pie, radar`. Kirim tipe di luar daftar itu dan store
menormalisasi diam-diam ke `bar` — cek `get_spatial_chart()` untuk memastikan tipe yang
benar-benar terpakai.

Pembagian kerja: peta untuk polygon/point, chart untuk agregat/evaluasi, KPI card untuk
satu angka. Angka selalu dari `call_simoge_tool`/`ana_kpi.py`, bukan diketik dari spec chart.

### Verifikasi engine

```bash
cd "$ANA_WORKDIR"  # =.env ANA_WORKDIR di mesin tsb
python3 test_ana_chart.py          # 2 copy sinkron, 6 section, intent map, guard
python3 test_spatial_chart.py      # state shape, alias, grid, clamp, guard tipe
node ui/test/spatial-aktivitas.test.mjs   # guard periode=0 / pembaharuan_ke
python3 smoke.py                   # regresi server
```

`test_ana_chart.py` sengaja membaca kedua copy skill dan gagal kalau tidak sinkron — jalankan
sebelum menyatakan engine selesai. Semua suite tanpa framework (`assert`/`node:assert`), jadi
jalankan langsung dengan `python3`/`node`, bukan `pytest`/`npm test`. Jangan tulis jumlah
check di dokumentasi — angka itu basi begitu ada check baru.
