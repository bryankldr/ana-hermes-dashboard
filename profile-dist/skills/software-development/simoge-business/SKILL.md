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

**Distribusi-portable & hemat token (upgrade path):**
- `ANA_WORKDIR` (`.env`) = path absolut dashboard di mesin tsb — jangan hardcode `/home/bryankldr/...` di kode/SKILL. Semua `sys.path.insert` pakai `pathlib.Path(__file__).resolve().parents[2]` atau `ANA_WORKDIR` env, bukan `ls -R`/`cat .env`/`read simoge_db.py` (hemat 8-12 exec, cache 300K+ → ~20K). `ponytail:` `references/` lazy-load on-demand — preload semua tiap turn hanya bila prompt butuh map/laporan.
- Prompt `sekarang`/`hari ini` → interpretasi = periode latest dengan data (`freshness()`/`provenance()`), label eksplisit `data terakhir tersedia September P0 (1-30 Sep)` bila fallback, bukan Oktober. Jika `produksi_aktiv.total_kg is None` tapi `status_petak_per_wilayah.aktif>0` → suffix TTS `"(aktivitas tanpa penerimaan — penerimaan belum masuk)"` untuk hindari misread 0 kg vs 7 aktif.
- **Bulan berjalan kosong — 3 cek dulu, jangan langsung jawab 0:** (1) `call_simoge_tool("produksi_trend",{"tahun":Y})` → baris (bulan,periode) yang muncul = bulan yang punya penerimaan; bulan tanpa baris = belum ada penerimaan sama sekali. (2) `call_simoge_tool("data_freshness",{})` → `tgl_terakhir`/`hari_ini`/`tujuh_hari` untuk aktivitas. (3) `aktivitas_agregat` bulan berjalan → `rows=[]` = input stop. Laporkan bulan terakhir berdata dengan label eksplisit, lalu pisahkan DUA sebab: produksi riil turun (n_penerimaan/n_petak menurun berbulan-bulan) vs input berhenti (`rows=[]` + `tgl_terakhir` basi) — jangan digabung jadi satu diagnosis, karena yang kedua belum tentu produksi nol.
- `ponytail:` cache `757K>356K` mahal — upgrade lazy-load refs bila `cache_read >500K` persisten; bila `300K` masih acceptable skip.


## When to Use
- SIMOGE: petak RTT, penyadap, andil, produksi, target RKAP, drum
- "tampilkan di peta" → **wajib** `show_on_map`, jangan docker/mysql/manual SQL
- Temporal (periode/tahun/bulan) atau geografis (KPH/BKPH/RPH/TPG)

## CRITICAL — One Call Does Everything
DB access **and** map display in one function. Never `docker exec`/`mysql`/hand-SQL. DB mati = `(2003, "Can't connect to MySQL server on '127.0.0.1' ([Errno 111] Connection refused)")` → nyalakan Docker Desktop unit user (`systemctl --user start docker-desktop`, tunggu ±25 s sampai `docker ps` lihat `mariadb`) lalu ulangi call yang sama — bukan alasan pindah ke SQL mentah. Never hand-build GeoJSON + `/api/map/command set_features` untuk subset — panel auto `reloadBusiness()` akan wipe push manual.

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
**HEMAT MUTLAK — JANGAN JUGA:** `read_file`/`search_files`/`skill_view` untuk chart/packet/pandas/ana_chart_tool/ana_simoge_tool/ana_pandas_tool — SKILL ini sudah cukup, JANGAN baca file lagi. Juga `search_files ana_mode_tool|set_mode|show_spatial` / `terminal ls scripts` / `terminal .venv/bin/python` / `which python3` / `inspect.getsource(show_dashboard)` — semua path sudah di SKILL, langsung `sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))` atau `os.getenv("ANA_WORKDIR")+"/profile-dist/.../scripts"` + `call_simoge_packet` — jangan hardcode user home. `.venv` tidak ada, pakai `python3` Hermes. Detail CLI aman & pitfalls → `references/troubleshooting.md`.

**Trend/penurunan/korelasi + chart — FIX IDEAL HEMAT (COPY-PASTE 1 CALL, jangan loop 18×, jangan hardcode, TETAP DI ASISTEN):**
```python
# 1 CALL = 2 packet + 1 dashboard (hemat 11→1 call, tanpa set_mode). Chart adalah tool biasa — jalan di asisten. Data dari packet, JANGAN hardcode labels=["P1 Jan",...]
from ana_simoge_tool import call_simoge_packet
from ana_chart_tool import show_dashboard
pkt_prod = call_simoge_packet("produksi_trend", {"tahun": 2026})   # kpi: breakdown[16-20], drops[<-30%], growth_pct server-side
pkt_akt  = call_simoge_packet("aktivitas_trend", {"tahun": 2026})  # kpi: breakdown n_petak_aktif/n_penyadap
# pkt["kpi"]["drops"] -> FACT penurunan; pkt["kpi"]["breakdown"] -> chart (jangan loop ana_kpi, jangan hardcode)
show_dashboard(charts=[
  {"title":"Produksi per periode 2026 (kg)","type":"bar","labels":[x["label"] for x in pkt_prod["kpi"]["breakdown"]],"datasets":[{"label":"Produksi kg","data":[x["total_kg"] for x in pkt_prod["kpi"]["breakdown"]]}]},
  {"title":"Aktivitas & Penyadap 2026","type":"line","labels":[x["label"] for x in pkt_akt["kpi"]["breakdown"]],"datasets":[{"label":"Petak aktif","data":[x["n_petak_aktif"] for x in pkt_akt["kpi"]["breakdown"]]}]},
])
# Tidak perlu set_mode — chart jalan di asisten. Jawab TTS 1-2 kalimat setelah dashboard.
```
Aturan keras: 1× `show_dashboard(charts=[2 chart])` saja — JANGAN `show_spatial_chart` lalu `show_dashboard` (overwrite, boros 1 call). JANGAN `labels=["P1 Jan","P2 Jan",...]` hardcode — ambil dari `pkt["kpi"]["breakdown"]`. Detail per wilayah bila butuh LOCATION: `call_simoge_packet("produksi_per_wilayah", {"tahun":2026,"bulan":6,"periode":0,"level":"kode_bkph"})` # breakdown 5 BKPH


### Mode & Chart — CHART/PANDAS ADALAH TOOL DI ASISTEN (TIDAK PERLU CODING UNTUK BISNIS)
Default `asisten` untuk SEMUA pertanyaan bisnis. **Tool bisnis tidak perlu `coding`.** `call_simoge_packet` / `call_pandas_tool` / `show_dashboard` / `show_for_intent_packet` / `show_on_map` adalah tool biasa — jalan langsung di `asisten` via **satu** `execute_code`, tanpa `set_mode`. Aturan keras:
- SEMUA pertanyaan bisnis (statistik, tren, korelasi, ranking, chart, pandas analytical) → **TETAP di `asisten`**. Langsung `execute_code` FIX IDEAL (1-2 packet + 1 dashboard) atau `call_pandas_tool` 1-CALL. Jangan `set_mode(coding)`, jangan `read_file`/`search_files`/`skill_view` untuk cari cara — SKILL ini sudah lengkap.
- `coding` HANYA bila user eksplisit minta artifact kode (`tampilkan code`, `buatkan file .py`, `tampilkan diff`) — bukan untuk chart/peta/tabel bisnis. Chart 1-2 visual, peta, atau tabel KPI bukan alasan coding.
- Jawab TTS singkat (1-2 kalimat) + visual ter-render (chart/peta). TTS-only saat diminta chart/peta = gagal.
- Selama eksekusi tool (packet/KPI/chart) JANGAN keluarkan narasi progres per langkah ("menarik data...", "cek bulan...", "render sekarang") — tiap kalimat interim bocor ke panel response dan dibacakan TTS. Kerjakan tool calls diam-diam, hanya jawaban final + visual yang tampil.
- Server overlay sama: business tool di asisten. `set_mode` tidak dibutuhkan untuk bisnis; UI tetap `asisten`.

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

**Param `bulan`/`periode` tidak selalu dihormati template agregat:** `produksi_per_wilayah` mengembalikan `actual_kg` identik untuk dua bulan berbeda (kumulatif, param diabaikan). Sebelum melaporkan angka bulanan dari template agregat, panggil dua bulan berdekatan — hasil identik = template mengabaikan param; ganti sumber ke `produksi_trend` (fakta per bulan) atau `answer_production` (KPI + evidence).

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
**Laporan:** `show_report(title, subtitle, pages=[{title, blocks}])` — panggil dengan keyword `pages`, bukan `blocks` langsung. Block KPI pakai key `items` (`{"type":"kpi","items":[{"label","value"}]}`), bukan `data`. Salah bentuk = return `visible:false` diam-diam; cek `ok`/`visible` sebelum klaim tampil.
**Arsip (simpan/tampilkan/hapus milik user):** `from ana_chart_tool import archive_save, archive_list, archive_show, archive_delete` — server-side per-user, survive restart, maks 20/user. User bilang "simpan chart/laporan ini" → `archive_save("chart")` / `archive_save("report")` (snapshot live saat itu). "Tampilkan arsip X" → `archive_list()` cari judul → `archive_show(id)`. "Hapus arsip X" → `archive_list()` → `archive_delete(id)`. User juga bisa via ikon 🗂 + 💾 di panel (tanpa ANNA). JANGAN klaim "sudah tampil" tanpa cek return `ok: True`; JANGAN klaim "tersimpan" tanpa cek `saved.id`.
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

**Sampai dengan Ya/Tidak (param resmi `sampai_dengan`):** Ya = kumulatif Jan-01 s/d akhir periode; Tidak = periode berjalan saja; Penuh + Ya = Jan s/d bulan itu P1+P2. Produksi/matriks default kumulatif (preserve perilaku lama), aktivitas default snapshot. Helpers: `_sampai_dengan(kw)`, `_range_bounds(tahun,bulan,periode,kw,default_kumulatif)`, `_target_pct_sd(...)` (target persen periode-berjalan vs kumulatif). Template map (`rkap_map`, `matriks_map`, `aktivitas_petak_map`, `idle_*`, `status_petak_per_wilayah`) + agregat KPH (`aktivitas_per_kph`, `produksi_per_kph`, `produksi_per_wilayah`) WAJIB baca param ini — jangan hardcode `period_bounds` untuk `cur`/realisasi bila template mendukung kumulatif. `prev`/`two` (logika idle/bongkor) tetap jendela relatif, bukan akumulasi.

```python
show_on_map("aktivitas_top_petak", tahun=2026, bulan=5, periode=0, limit=10)  # per petak + polygon
call_simoge_tool("aktivitas_agregat", {"tahun":2026,"bulan":5,"periode":0,"grup_by":"pembaharuan"})  # per tahap
call_simoge_tool("aktivitas_agregat", {"tahun":2026,"bulan":5,"periode":0,"grup_by":"aktivitas"})    # per jenis
call_simoge_tool("aktivitas_agregat", {"tahun":2026,"bulan":5,"periode":0,"grup_by":"penyadap", "limit":20})  # per penyadap
show_on_map("aktivitas_per_penyadap_petak", tahun=2026, bulan=5, periode=0, id_penyadap=3590, limit=50)
```
`aktivitas_petak_map` + `pembaharuan_ke` = polygon+pin; `aktivitas_top_petak` = push mentah `delivery:"push"` tanpa pin.

**Filter jenis aktivitas (param resmi `jenis_aktivitas`):** quare/semprot_cas/kerok/naik_batok/budaya_bersih/pulung — saring baris aktivitas ke satu jenis flag (`AND s.<flag>=1`). Terapkan HANYA ke hitungan `cur` (periode berjalan) dan breakdown andil (`aa`/`ab`); `prev`/`two` (jendela logika idle/bongkor) tetap penuh — kalau ikut difilter, definisi idle/bongkor rusak. Helper `_jenis_aktivitas_where(kw, alias)` ikut pola `_pembaharuan_where`; kolom baru yang belum ada di DB live = `AND 1=0` via cek `information_schema` (bukan error 1054). Terima label manusia juga ("semprot cas", "naik batok", "budaya bersih").
- Uji filter JENIS hanya di periode yang berdata (cek `MAX(tgl_pembaharuan)` dulu) — hasil identik di semua opsi artinya periode kosong, bukan filter rusak. Jangan nyatakan filter broken sebelum verifikasi ini.

**Kolom aktivitas baru** — `tgl_aktivitas` (date aktivitas, beda dari `tgl_pembaharuan` = update date), `pulung` (flag aktivitas), dan `jml_phn_*` (jumlah pohon per jenis). `pulung` otomatis ikut `grup_by:"aktivitas"` via `AKTIVITAS_FLAGS` di `scripts/simoge_db.py`. Selalu filter periode pakai `tgl_pembaharuan`, bukan `tgl_aktivitas`. Schema-evolution checklist (skip satu = knowledge drift): patch `references/schema.md` + `scripts/simoge_db.py` + vault `ANNA-KNOWLEDGE/raw/articles/skema-database-kph-bwb-sandbox2.md` + ontology `SIMOGE Business Knowledge & Ontology.md` #5.12 + `rsync` ke `profile-dist/skills/software-development/<skill>/` (`diff -q --exclude=__pycache__` must be 0) + `git commit` — vault/wiki bukan di `profile-dist`, update manual tiap skema berubah.

**Kolom tanggal filter (aturan umum):** filter periode WAJIB pakai tanggal kerja yang ditulis pelapor (`tgl_pembaharuan` untuk aktivitas, `tanggal` untuk penerimaan) — JANGAN `date_created` (tanggal baris masuk server; lag upload nyata hingga 41 hari di aktivitas dan ratusan ribu hari di penerimaan karena input tahun 33/1932, laporan telat unggah jatuh ke periode salah). Migrasi ke kolom tanggal baru (`tgl_aktivitas` masih 0/20184) hanya setelah backfill massal, kalau tidak histori hilang dari filter. Tanggal sampah = masalah input lapangan: tahan sebagai catatan kanban + guard tahun wajar (`BETWEEN '2020-01-01' AND CURDATE()` atau filter lag) sebelum agregat produksi, jangan diam-diam ikut hitungan. Validasi lag via `DATEDIFF(date_created, tgl_pembaharuan)` untuk bedakan telat upload vs salah input.

**Efektivitas pohon (coverage vs usaha):** skor per jenis = `MAX(NULLIF(jml_phn_<jenis>,0)) / jumlah_pohon` — satu pohon yang diulang 1-4 pembaharuan tetap 1 pohon tersentuh, jadi petak 1x vs 4x pembaharuan dengan cakupan sama dapat skor sama. Semua jenis = rata-rata rasio dari jenis berdata saja. `SUM` disimpan terpisah sebagai kolom `intensitas` (usaha/pengulangan), jangan pernah dilipat ke skor — SUM menggelembungkan skor dan selalu memenangkan frekuensi atas cakupan.

## Templates / Production KPI / Business Rules / Map / Transport
- Templates (36 verified) — `describe()` / `list_templates()` ; detail `references/templates.md`
- Production KPI `answer_production(tahun,bulan,periode,mode,**wilayah)` 1 call — `references/production_period_params.md (bulan penuh = periode:0), references/production_kpi.md`
- Business Rules `kode_evapot`, periode, warna merah/kuning/hijau, target RO/NPS — `references/business_rules.md`
- Map ops `set_features`/`spatial_set` via `/api/map/command` — `references/map_ops.md`
- Chart transport `spatial_chart_store POST/GET /api/spatial/chart` — `references/chart_transport.md`
- Troubleshooting CLI/patch/verify — `references/troubleshooting.md`
- Chart detail multi/laporan/presentation — `references/chart_guide.md`

## Credentials / Token sync / Geography
Read `.env` (server load, inherit). Never hardcode `SIMOGE_DB_PASSWORD`.
Token: per-boot `BOOT_ID`, 401 `{"error":"unauthorized","boot":BOOT_ID}`, `GET /api/token-status` no auth, `bootGuard.js` poll 5s reload. `show_on_map` resolve token fresh + retry 1x 401. Debug: `/api/token-status` → 401 boot → `.ana_token` mtime → hard refresh.
Geography: 810 petak RTT 2026 `kode_kph=31211` Banyuwangi Barat. Default `CURRENT_YEAR` 2026.

