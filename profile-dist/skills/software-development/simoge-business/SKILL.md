---
name: simoge-business
category: software-development
description: Use for SIMOGE queries (petak, penyadap, produksi) or map display. Knowledge base from docs/kontek_bisnis.md.
version: 1.3.0
metadata:
  hermes:
    tags: [simoge, business, map, maria, kph-bwb]
    related_skills: [ana-hud-dashboard]
---

## Source of Truth
`docs/kontek_bisnis.md` + `docs/refaktor/2nd_kontek_bisnis_diperjelas.md` — hubungan tabel, periode P1/P2, 4 domain spasial, bongkor/idle/aktif, warna polygon. Bila ragu baca file langsung.

## When to Use
- SIMOGE: petak RTT, penyadap, andil, produksi, target RKAP, drum
- "tampilkan di peta" → **wajib** `show_on_map`, jangan docker/mysql/manual SQL
- Temporal (periode/tahun/bulan) atau geografis (KPH/BKPH/RPH/TPG)

## CRITICAL — One Call Does Everything
DB access **and** map display in one function. Never `docker exec`/`mysql`/hand-SQL. Never hand-build GeoJSON + `/api/map/command set_features` untuk subset — panel auto `reloadBusiness()` akan wipe push manual.

**Statistics only (no map) — WAJIB Packet (hemat, anti-halusinasi):**
```python
from ana_simoge_tool import call_simoge_packet
from ana_chart_tool import show_for_intent_packet
pkt = call_simoge_packet("petak_count", {"tahun": 2026, "bulan": 6, "periode": 0})
# pkt = {intent, period, scope:{text}, kpi:{...}, evidence:[{statement,source}]} — TANPA rows
show_for_intent_packet(pkt)
# Jawab HANYA dari pkt["kpi"]/pkt["evidence"], jangan karang angka
```
Larangan: untuk KPI terdefinisi JANGAN `skill_view`/`read_file`/`search_files`/`_q()`/`ana_kpi.get_production_kpi` loop per periode — packet/batch cukup. `call_simoge_tool` hanya debug mentah. `search_files ana_kpi` + `read_file ana_kpi.py` = boros — SKILL ini sudah cukup.
**HEMAT MUTLAK — JANGAN JUGA:** `search_files ana_mode_tool|set_mode|show_spatial` / `terminal ls scripts` / `terminal .venv/bin/python` / `which python3` / `inspect.getsource(show_dashboard)` — semua path sudah di SKILL, langsung `sys.path.insert(0, ".../scripts")` + `call_simoge_packet`. `.venv` tidak ada, pakai `python3` Hermes. Detail CLI aman & pitfalls → `references/troubleshooting.md`.

**Trend/penurunan/korelasi + chart — FIX IDEAL HEMAT (COPY-PASTE 3 CALL, jangan loop 18×, jangan hardcode):**
```python
# CALL 1 — eskalasi (wajib jika prompt ada kata chart/grafik)
from ana_mode_tool import set_mode; set_mode("coding")
# CALL 2 — 2 packet + 1 dashboard dalam 1 execute_code (hemat 11→3 call). Data dari packet, JANGAN hardcode labels=["P1 Jan",...]
from ana_simoge_tool import call_simoge_packet
from ana_chart_tool import show_dashboard
pkt_prod = call_simoge_packet("produksi_trend", {"tahun": 2026})   # kpi: breakdown[16-20], drops[<-30%], growth_pct server-side
pkt_akt  = call_simoge_packet("aktivitas_trend", {"tahun": 2026})  # kpi: breakdown n_petak_aktif/n_penyadap
# pkt["kpi"]["drops"] -> FACT penurunan; pkt["kpi"]["breakdown"] -> chart (jangan loop ana_kpi, jangan hardcode)
show_dashboard(charts=[
  {"title":"Produksi per periode 2026 (kg)","type":"bar","labels":[x["label"] for x in pkt_prod["kpi"]["breakdown"]],"datasets":[{"label":"Produksi kg","data":[x["total_kg"] for x in pkt_prod["kpi"]["breakdown"]]}]},
  {"title":"Aktivitas & Penyadap 2026","type":"line","labels":[x["label"] for x in pkt_akt["kpi"]["breakdown"]],"datasets":[{"label":"Petak aktif","data":[x["n_petak_aktif"] for x in pkt_akt["kpi"]["breakdown"]]}]},
])
# CALL 3 — balik TTS sebelum jawab
from ana_mode_tool import set_mode; set_mode("asisten")
```
Aturan keras: 1× `show_dashboard(charts=[2 chart])` saja — JANGAN `show_spatial_chart` lalu `show_dashboard` (overwrite, boros 1 call). JANGAN `labels=["P1 Jan","P2 Jan",...]` hardcode — ambil dari `pkt["kpi"]["breakdown"]`. Detail per wilayah bila butuh LOCATION: `call_simoge_packet("produksi_per_wilayah", {"tahun":2026,"bulan":6,"periode":0,"level":"kode_bkph"})` # breakdown 5 BKPH


### Mode switch aman + CHART WAJIB saat diminta
Default `asisten` (TTS 1-2 kalimat). ATURAN KERAS: jika prompt mengandung kata `chart`/`grafik`/`visual`/`preview`/`tampilkan dalam chart`/`tampilkan chartnya` → JANGAN jawab TTS-only. WAJIB `set_mode("coding")` dulu, lalu `call_simoge_packet` + `show_dashboard` (atau `show_for_intent_packet`), baru `set_mode("asisten")` sebelum delta. TTS tanpa chart saat diminta = gagal. Server overlay juga memaksa hal sama.
```python
from ana_mode_tool import set_mode
set_mode("coding")       # sebelum render berat — WAJIB jika user minta chart
# ... call_simoge_packet + show_dashboard ...
set_mode("asisten")      # WAJIB sebelum delta final (server juga auto-restore)
```
`set_mode` POST `/api/mode` (butuh `x-ana-token`+`Host`/`Origin` 127.0.0.1:8730). Fallback `.ana_mode`. UI sinkron `t:mode`+poll 3s.

**Analytical batch — Pandas owns processing:**
```python
from ana_pandas_tool import call_pandas_tool
r = call_pandas_tool(template="produksi_per_wilayah", params={"tahun":2026,"bulan":5,"periode":0,"level":"kode_bkph"},
                     operations=[{"type":"sort","by":"achievement_pct"},{"type":"limit","n":5}])
# r["analytical"]={facts,result:[5 rows],truncated} — 1 call N ops
# ops: filter|group_by|aggregate|sort|rank|pivot|percentage_change|compare_period|statistics|anomaly|describe|limit
# ponytail: dataset_id session belum — add when reuse dataset iteratif
```

**Chart anti-overwrite:** `show_spatial_chart` replace — jangan panggil 2× berurutan untuk 2 chart. Untuk 2 chart pakai `show_dashboard(charts=[...])` atau `show_for_intent_packet` 1× per turn (user toggle). `show_for_intent_packet(pkt)` auto `h_bar` dari `kpi.breakdown` — jangan hardcode `labels=["P1 Jan",...] + data=[...]`.

**Show on map (query+render+auto-fit+warna in one call):**
```python
from ana_simoge_tool import show_on_map
show_on_map("petak_efektivitas_map", tahun=2026, limit=1000)          # merah/kuning/hijau
show_on_map("petak_bongkor_map", tahun=2026, limit=1000)               # merah saja
show_on_map("rkap_map", tahun=2026, bulan=9, periode=1, limit=1000)    # RKAP
show_on_map("petak_with_geometry", tahun=2026, limit=810)              # polos
# → {"ok": True, "features": 809, "delivery": "state", "spatial_id": "m2"} (panel yang render, no geojson balik)
```

**Filtered subset — state-driven, never client post-filter:**
```python
show_on_map("petak_efektivitas_map", tahun=2026, limit=1000, warna="kuning")  # 51 features, warna_counts dari subset
```
`params.warna` di-pop server sebelum template, rows difilter sebelum GeoJSON, `warna_counts`/KPI dari subset. `delivery:"state"` = panel reload; tanpa `spatial_id` = template non-spatial, cek nama.

**Verify the call:** `r=show_on_map(...); print(r.get("features"), r.get("spatial_id"))` — `None`/falsy = broken, stop jangan fallback chart. `row_count` vs `features` beda 1 wajar (petak tanpa polygon). Detail → `references/troubleshooting.md`.

Requires `polygon` column. Map-capable: `petak_with_geometry`, `petak_bongkor_map`, `petak_efektivitas_map`, `rkap_map` (+ `petak_detail` single).

### Q&A bisnis — router, bukan laporan
| | `run_business_review` | `answer_question` |
|---|---|---|
| dipicu | "buatkan presentasi", "review Juni" | "berapa petak X?" |
| hasil | 6 section, 11 chart | 1 hal, 1 visual (packet kpi+evidence) |
| narasi | laporan terstruktur | kalimat jawab pertanyaan |
| template | 4 template tetap | 37 template via router |

`answer_question(q, tahun=, bulan=, kode=, level=)` → router `QA_INTENT` + chart + narasi dari kolom asli template. 1 call ~0.0-0.2s. CLI: `ana_chart_tool.py ask q="berapa petak ada" tahun=2026 bulan=5`
Syarat: urutan `QA_INTENT` specific→umum, `_NEEDS_CODE` minta `kode_evapot`, luar domain → hint, kosong → jujur, satuan ragu → "(satuan sesuai DB)", `__freshness__/__review__` sebelum DB. Test: `test_ana_qa.py` (21 kasus).

### Retrieval — jangan bawa 38 template ke prompt
`simoge_db.describe(template)` → `{template,doc,params,tool}` tanpa registry. `list_templates()` daftar nama. Polygon(7) vs agregat vs scalars vs stats — detail `references/templates.md`.

## Chart & Presentasi
`ana_chart_tool.py` 2 lapis. Jangan bikin spec manual — pakai intent atau review. Detail lengkap → `references/chart_guide.md`.

**Intent → visual:** `target_comparison`/`achievement`→bullet, `trend`→line, `ranking`/`region`→h_bar, `composition`/`status`→stacked_bar, `pareto`→pareto, `gap`→waterfall, `location`→peta, `kpi`→card. `show_for_intent(intent,**kw)` — full mapping di chart_guide.

**Multi-chart:** `show_dashboard()` grid 2–3 kolom, max 6 chart+8 KPI. `chart` alias `charts[0]`.
**Laporan:** `show_report()` N halaman A4, block `para`/`note`/`list`/`kpi`/`table` — bukan canvas. `get_report()` dulu bila user minta tampilkan; jika visible true → `hide_report()` dulu baru `show_report()`.
**Presentation:** `run_business_review(tahun,bulan,periode)` susun 6 section, tampil per `present_section(rv,"petak",with_map=True)`. Scope `level="kode_bkph"` default.
**T3 atomik (2-4 calls bukan 14):** `review` (1 call 6 section) → `laporan act=show` (1 call). Rows di engine, model cuma `kpis`+`narrative`+`evidence`. Target T3 80-200K.

6 section: `ringkasan` status+produksi · `petak` bongkor · `aktivitas` agregat · `produksi` produksi_per_wilayah · `cross` aktivitas_petak_map · `kesimpulan` narasi. Scatter=pola bukan sebab, P4 kosong sebutkan, `_fmt_num` untuk angka.

## Cache / Provenance / Freshness
Fingerprint=`tgl_terakhir|n_penyadap|penyadap_hari_ini` hash 8c → key `{tahun}-{bulan}-P{periode}__{level}__<fp>` TTL 6h `ANA_CACHE_DIR`. Cold 1.3s warm 0.02s. `use_cache=False` paksa baru. CLI `cache [stats|key|clear]`.
`provenance()` → `{tgl,jam,fase,status,stale_hari,n_petak,hot,kalimat}` ditempel `ringkasan` sebagai KPI DATA + badge. `freshness()` → `{tgl,jam,fase,status}` segar/kemarin/basi/kosong — `ringkasan` auto KPI DATA TERAKHIR bila bukan segar. Input operator 12.00–15.00, `SPOIL_HOUR=15`. Detail → `references/chart_guide.md`.

## Cara CEPAT (1-3 call bukan 17)
```python
from ana_chart_tool import parse_periode, cli_review, present_section
y,b,p = parse_periode("mei")              # "mei"/"bulan ini"/"mei lalu"/"20xx"
rv = cli_review(y,b,p, play="ringkasan")  # 1.3s 6 section
present_section(rv, "produksi", with_map=True)
```
`parse_periode` butuh workdir absolut. Satu review >5s = salah (find/query per template/periode salah). Cek `rv["warnings"]`.

Kontrak hide: `{"visible":false}` hide, `{"charts":null}` hide, `{"charts":[]}` NO-OP (kesimpulan tanpa visual). Guard `_busy`+`_lastUpdated`+canvas wrapper jangan dihapus.

## Aktivitas — 4 template, jangan rangkai sendiri
`periode=0`/`"full"` = bulan penuh (P1+P2), `periode=1` 1–15, `periode=2` 16–akhir. `pembaharuan_ke` "1".."4"/"semua" (4 sah tapi DB 2026-10 cuma 1/2/3).

```python
show_on_map("aktivitas_top_petak", tahun=2026, bulan=5, periode=0, limit=10)  # per petak + polygon
call_simoge_tool("aktivitas_agregat", {"tahun":2026,"bulan":5,"periode":0,"grup_by":"pembaharuan"})  # per tahap
call_simoge_tool("aktivitas_agregat", {"tahun":2026,"bulan":5,"periode":0,"grup_by":"aktivitas"})    # per jenis
call_simoge_tool("aktivitas_agregat", {"tahun":2026,"bulan":5,"periode":0,"grup_by":"penyadap", "limit":20})  # per penyadap
show_on_map("aktivitas_per_penyadap_petak", tahun=2026, bulan=5, periode=0, id_penyadap=3590, limit=50)
```
`aktivitas_petak_map` + `pembaharuan_ke` = polygon+pin; `aktivitas_top_petak` = push mentah `delivery:"push"` tanpa pin.

## Templates / Production KPI / Business Rules / Map / Transport
- Templates (36 verified) — `describe()` / `list_templates()` ; detail `references/templates.md`
- Production KPI `answer_production(tahun,bulan,periode,mode,**wilayah)` 1 call — `references/production_kpi.md`
- Business Rules `kode_evapot`, periode, warna merah/kuning/hijau, target RO/NPS — `references/business_rules.md`
- Map ops `set_features`/`spatial_set` via `/api/map/command` — `references/map_ops.md`
- Chart transport `spatial_chart_store POST/GET /api/spatial/chart` — `references/chart_transport.md`
- Troubleshooting CLI/patch/verify — `references/troubleshooting.md`
- Chart detail multi/laporan/presentation — `references/chart_guide.md`

## Credentials / Token sync / Geography
Read `.env` (server load, inherit). Never hardcode `SIMOGE_DB_PASSWORD`.
Token: per-boot `BOOT_ID`, 401 `{"error":"unauthorized","boot":BOOT_ID}`, `GET /api/token-status` no auth, `bootGuard.js` poll 5s reload. `show_on_map` resolve token fresh + retry 1x 401. Debug: `/api/token-status` → 401 boot → `.ana_token` mtime → hard refresh.
Geography: 810 petak RTT 2026 `kode_kph=31211` Banyuwangi Barat. Default `CURRENT_YEAR` 2026.

