# Deskripsi Komponen Panel SPATIAL MAP — ANNA Hermes Dashboard

> Scope: panel `SPATIAL MAP` (`#mapPanel`, `rail: right`) — Business Map Workspace + BI Dashboard + Chart. Tidak ubah panel lain / layout global / Hermes core. Profil `anna` lowercase, `HERMES_PROFILE=anna`, port `8730`.

## 1. Ringkasan Arsitektur

```
DATABASE (kph_bwb_sandbox2 MariaDB, 127.0.0.1:3306)
   ↓ direct SQL read-only
Business Data Engine (skill simoge-business: simoge_db.py 7 _map + ana_simoge_tool.py)
   ↓ POST /api/simoge/show_on_map → GeoJSON + warna_counts + map_store.push_command(set_features)
SpatialMapState (ui/src/spatialMapState.js — isolated store, emit SPATIAL_MAP_CHANGED)
   ↓ subscribeSpatial / bus MODE_CHANGED
Map (ui/src/map.js + mapControl.js LeafletAdapter + map.css full-bleed flying + vendor/leaflet)
   ↓ MAP_FEATURES_LOADED → metric/warna_counts → ANA via /api/map/state + /api/spatial/chart
ANA (profil anna, persona SIMOGE Business Specialist)
```

Cadangan: `ui/data/petak_simple.json` wrapper `{meta, features}` + `snapshots/petak_YYYY-MM-DD.json` via `scripts/refresh_petak_simple.py` (cron `0 6 * * *`, RETAIN 7d/24mo) — ANNA YOY `meta.generated_at`, Business Map tetap DB 100%.

---

## 2. Panel Container

| Nama | File | Fungsi |
|---|---|---|
| `SPATIAL MAP` (`#mapPanel`) | `ui/src/map.js:ensurePanel({id:'mapPanel',rail:'right'})` + `ui/src/utils/dom.js` | Container HUD via `LayoutManager` (`ui/src/core/layout.js`). `z-index:5 !important` — selalu paling bawah (di bawah `.frame z10`, `.top-controls/core z20`). `register`/`measure` override hindari `freeZ++` naikkan layer. `min-height 520px`, `panel-body padding 0` full-bleed. |
| `.map-wrap.map-full` | `map.js` body + `map.css` | Wrapper `position:relative flex1 min-height 460px overflow hidden border 8px #03101f`. `#mapBox` `absolute inset 0` — peta pakai 100% frame. Semua BI flying absolute di atas wrap, tidak geser layout. |

**Cara kerja:** `ensurePanel` buat `div.panel#mapPanel > .panel-title + .panel-body`. `LayoutManager.measure()` hitung rect saat di rail → re-parent ke `.hud absolute left/top width/height`, simpan ke `layout.json` via `POST /api/layout`. Lock toggle `payload locked`. `register(mapPanel)` pakai `z 5 important` — panel lain tetap di atas peta.

---

## 3. Map Engine

| Komponen | File | Nama & Fungsi |
|---|---|---|
| `Leaflet` | `ui/vendor/leaflet/leaflet.js` + `map.css` | Engine peta 2D. Tile `World_Dark_Gray_Base` + `World_Imagery + World_Boundaries_and_Places`. `L.map(#mapBox, zoomControl true).setView(CENTER [-8.1776,114.1261], 11)`, `L.layerGroup petakLayer`, `satGroup addTo`, `L.control.layers` Satelit/Gelap, `L.control.scale bottomleft`. `L.featureGroup(polygon) getBounds pad 0.05` untuk `fit_all`. |
| `LeafletAdapter` | `ui/src/mapControl.js` | Semantic interface ANA dilarang sentuh `map.flyTo`/`querySelector`. Implements `get_state/set_view/fit_bounds/fit_all/reset_view, get_layers/set_layer_visibility/toggle_layer/set_basemap, select_feature/get_selected/clear_selection, highlight_features/clear_highlights, set_filter/clear_filter, set_features/clear_features`. Canonical `state {center{lat,lng,zoom}, bounds{south,west,north,east}, basemap, layers{}, selected, highlighted[], filter, count}`. `features Map id→layer`, `layers Map id→L layer`, `baseLayers`. Emit bus `MAP_*` + `MAP_VIEW_CHANGED`. `baseStyle #2DF2FF` + `WARNA_STYLE merah #EF4444/oranye #F97316/kuning #EAB308/hijau #22C55E/emas #FFD700`. |
| `Business Data Bridge` | `ui/src/map.js:startMapBridge({token,log})` | Poll `GET /api/map/queue` + `POST /api/map/result` + `POST /api/map/state` via `X-Ana-Token`. `MAP_BRIDGE_MS 400ms`. `poll` iterasi `commands[]` → `_ctl[op].apply` → `POST result {id,ok,data/error}`. `pushState` throttle 4000ms `POST state {state: _ctl.get_state()}` untuk `GET /api/map/state` ANA baca. |
| `Spatial Chart` | `ui/src/spatialChart.js` + `ui/vendor/chart.js` + `server.py:spatial_chart_store` | Panel chart flying center `left 50% top 50% translate -50% 560px z400 blur 12px` di `.map-wrap`. ANA full control via `POST /api/spatial/chart {visible,chart{type bar/h_bar/line/doughnut/pie, title, labels, datasets, options},meta}` + `GET`. Poll 2s. `ensureDom` host `.map-wrap`. |

**Cara kerja:** `main.js` `initMapPanel({log})` buat panel+map → `startMapBridge({token: ANA_TOKEN})` mulai poll. `server.py:_simoge_show_on_map(template,params)` push `map_store.push_command(set_features,{geojson FeatureCollection,fit true})` → `GET /api/map/queue` drain → `_drainBusinessQueue(map_id)` drain langsung tanpa tunggu interval → `LeafletAdapter.set_features` resolve `WARNA_STYLE` per `properties.warna` → `MAP_FEATURES_LOADED {added,total}` → `metric + legend`.

---

## 4. Flying Overlays (di atas peta)

Semua `position:absolute z 315-450 backdrop-filter blur 8-10px rgba(2,15,42,.8-.92) box-shadow` — tidak geser peta.

| Nama | Selector | Posisi & Ukuran | Fungsi |
|---|---|---|---|
| `BI Header` | `.map-fly-head` | `top 8px left/right 8px pill 3px 8px 9px` | Judul `BUSINESS INTELLIGENCE` + badge `shPeriode YYYY-MM-P1/P2` + `shMode CODING/ASISTEN` (via `data-ana-mode` / `busState.mode`). `updateHead()` tiap `collectState()` / `MODE_CHANGED`. |
| `Filter Bar` | `.map-fly-top` | `top 44px left/right 8px max-height calc(100%-148px)` | Toolbar `spatialBiz` (4 bisnis) + `spatialKat` (petak kategori) + `Filter` + `KPI` + `Muat`. `syncKatVisibility()` (`petak/aktivitas` show `kat`, lain hide). Filters drawer `spatialFilters flying 46vh scroll` + chips `spatialChips` + `map-tools flying` search `mapSearch Enter select_feature` + `mapFit fit_all`. `Filter → collapsed`, `KPI → collapsed`. |
| `Filter Drawer` | `#spatialFilters .spatial-filters.flying` | `46vh scroll` | Waktu `fBulan fTahun fPeriode` + Wilayah `fDivre fKph fBkph fRph fTpg` + `Terapkan/Reset` + `chips`. Wilayah options `fetchWilayahOptions(2026)` → `/api/simoge/query wilayah_labels` → human label `kode — nama`. Chip `x` hapus per filter + `hapus semua`. |
| `KPI` | `#spatialKpi.spatial-kpi.flying` | `left 8px bottom 8px width min(500px,60%-6px) 56px grid 4 gap4` | 4 card: Total petak (`kpiTotal/features`), Bongkor (`merah`), Perlu perhatian (`kuning+oranye`), Terpenuhi (`hijau+emas`) — mapping per bisnis `renderKPIs(biz,kat,warna_counts,total)`. `collapsed → none`. Toggle `spatialKpiBtn`. |
| `Legend` | `#mapLegend.map-legend.flying` | `right 8px bottom 8px width min(340px,40%-6px) 56px 9px` | Warna bisnis `updateLegend(biz,kat)`: petak `Bongkor merah/Kurang kuning/Terpenuhi hijau`; aktivitas `Bongkor mercury/Idle kuning/Aktif hijau + Pin`; produksi `0-25 merah…>100 emas`; matriks `Bongkor…emas`. Satu baris dengan KPI. |
| `Insight` | `#spatialInsight.spatial-insight.flying` | `left/right 8px bottom 92px max-height 64px 9px` | Narasi `renderInsight(biz,explanation,features,warna_counts)` — asisten: ringkasan ANNA `Bongkor x (y%)…`, coding: `template·feat·warna json`. `empty → none`. `data-ana-mode` toggle `dev`. |
| `Meta` | `.map-meta.flying` (`#mapMetric + #mapStat`) | `right 8px bottom 70px pill 8px` | Metric `added baru·total total · msg` (dari `MAP_FEATURES_LOADED`) + Stat `features polygon · template / memuat… / gagal — klik Muat`. |
| `Progress` | `#spatialProgress.spatial-progress.flying` | `left 8px bottom 162px width 168px 42% pill 8px 200→168` | Bar `6→4px gradient neon→#39F5A6` + label `memuat… / merender N… / menunggu render N… / polygon tampil — N feat / render terlambat (cur/N)`. Sumber kebenaran `MAP_FEATURES_LOADED total >= awaiting`, bukan `fetch ok`. `hidden` idle, `pointer-events none`, watchdog 3s warn + 3s fail `render gagal — klik Muat`. |

**Cara kerja:** `collectState() → {business, filters{bulan,tahun,periode,divre,kph,bkph,rph,tpg,kategori}}`. `reloadBusiness()` → `_setProgress 12→28→42→58→64→96`, `setBusiness/setFilters` → `updateHead/renderChips`, `clear_features` sebelum `loadBusinessData` anti balapan, `_drainBusinessQueue(map_id)` drain langsung, `setDataset/setMetrics` → `renderKPIs/renderInsight`. `scheduleReload 420ms` debounce `change` event. `ResizeObserver 120ms map.invalidateSize()`. Responsive `<=560px KPI 2x2, legend static, wrap padding-bottom 92px`.

---

## 5. Business Logic — 4 Domain Evaluasi Spasial

Sumber: `docs/refaktor/2nd_kontek_bisnis_diperjelas.md` + `simoge-business/simoge_db.py`.

| Domain | Template `_map` | Join | Indikator & Warna |
|---|---|---|---|
| **Evaluasi Petak** | `petak_bongkor_map`, `petak_efektivitas_map` (`getah_petak→petak_polygon via kode_evapot`) | `luas_andil` (SUM andil per evapot) vs `luas_baku` | `Bongkor merah` tanpa penyadap, `Kuning` `luas_andil<luas_baku`, `Hijau` `≥`. Efektivitas pool `petak_efektivitas_map`. |
| **Evaluasi Aktivitas** | `aktivitas_petak_map`, `idle_petak_map` (loose `GROUP BY kode_evapot` tgl `period_bounds P1 1-15 P2 16-akhir` vs strict `getah_andil` fix) | `cur` berjalan, `prev` sebelumnya, `aktivitas_2bulan 61-hari`, `andil aa EXISTS sadap BETWEEN d0-e1` | `AKTIF hijau cur>0`, `IDLE kuning cur0 prev>0`, `BONGKOR merah` tanpa penyadap OR `>2 bln` tanpa aktivitas. *Petak BONGKOR ≠ Andil BONGKOR*, `andil_idle≈jumlah_andil-aktif-bongkor`. |
| **Evaluasi Produksi** | `rkap_map` (+ `getah_target_ro_nps tahun_rtt+100` GR null) | `target_periode_RO=round(target_periode*(1-0.16)/25.5)` vs `realisasi` | `pencapaian%` emas `>100+5%`, hijau `±5%`, kuning `-5..-25%`, oranye `<-25%`, merah `0`. Warna sinkron KPI/Legend. |
| **Evaluasi Matriks** | `matriks_map` (`jml_pohon_andil/jumlah_pohon_petak/pohon_pct SUM(jml_pohon)`) | `luas+pohon+penyadap+aktivitas+produksi` | Merah/oranye/kuning/hijau/emas berdasarkan `coverage·pohon·andil·produksi` (mis. `50D-4 430/0 0%`). |

Filter `_wilayah_where(kw)` allowlist `kode_divre/kph/bkph/rph/tpg isdigit→int` paramised `p.kode_* = %s`, server-side `WHERE`. `AktivitasRecent` scoped `tahun/bulan/periode BETWEEN + wilayah JOIN getah_petak` + pin `set_aktivitas_points(circleMarker Pem1 cyan #2DF2FF Pem2 #F97316 Pem3 #EF4444, foto 140px, cuaca cerah/hujan/mendung, akses mudah/sedang/sulit, garis pin→center kode_evapot skip 28m weight1.8 dash7 5 warna Pem)`.

---

## 6. Data State

| Store | File | Bentuk | Emit |
|---|---|---|---|
| `SpatialMapState` | `spatialMapState.js` | `{business:'petak', filters{bulan,tahun,periode,divre,kph,bkph,rph,tpg,kategori:'semua'}, dataset{template,params,row_count,features,at}, layers{}, selection, metrics{shown,total,warna_counts,at}, _rev}` | `bus SPATIAL_MAP_CHANGED` + `window.__spatialMapState`. `createSpatialMapState(overrides)` + `setBusiness/setFilters/setDataset/setMetrics/setSelection/resetSpatialState/subscribeSpatial`. |
| `Map Bridge` | `map_store.py` | `ALLOWED_OPS {get_state,set_view,fit_bounds,fit_all,reset_view,get_layers,set_layer_visibility,toggle_layer,set_basemap,select_feature,get_selected,clear_selection,clear_filter,clear_highlights,highlight_features,set_filter,set_features,clear_features}` + `RESULT_TTL 300s` | `push_command(op,args)→(cmd_id,err)` → `take_pending()` → `put_result/get_result`. |
| `Spatial Intel` | `spatial_intel.py` | Wrapper `petak_simple.json {meta{generated_at WIB ISO, source kph_bwb_sandbox2, tahun_rtt, periode YYYY-MM-P1/P2, counts{total,with_polygon,rtt_2026,orphan_no_rtt}}, features[{n,p,tahun_rtt,kode_*,luas_baku,target_rkap}]}` + `snapshots/ + manifest` | `GET /api/spatial/query|history|periods|diff` → ANA YOY jujur `generated_at`. |
| `Spatial Chart` | `spatial_chart_store.py` | `{visible,bool, chart{type bar/h_bar/line/doughnut/pie, title, labels[], datasets[], options}, meta, updated}` | `GET/POST /api/spatial/chart` token-gated, session. |

---

## 7. Alur Pemuatan (Progress Aktual)

```
_user Buka → _whenReady(CTL+map+Leaflet) → _kickAuto single 360ms → reloadBusiness
  6% memuat peta… → 12% memuat biz tahun-bulan-P → 28% memuat polygon… → clear_features
  42% menghubungi server… → POST /api/simoge/show_on_map {template,params}
  58% merender N polygon… → 64% menunggu render N… → await _drainBusinessQueue(map_id)
  → count>=N ? 96% polygon tampil — N feat → hide 900ms : 68-90% merender cur/N
  → watchdog 3s warn render terlambat (cur/N) → 3s fail render gagal — klik Muat
_filter change → collectState → setBusiness/setFilters → updateHead/renderChips → scheduleReload 420ms → cancel awaiting lama
_pin Aktivitas → fetchAktivitasPoints adaptif limit 600-1200 (features*2 || 800, default 1000) → set_aktivitas_points+_rebuildAktivitasLines → stat + aktivitas (fotoN)
```

Sumber kebenaran `MAP_FEATURES_LOADED`, `mySeq===_loadSeq` anti race, `_pending queue` + `_loadSeq` + `Muat disabled 0<pct<100`.

---

## 8. File Map

| File | Peran |
|---|---|
| `ui/src/map.js` (719 line) | Panel + flying body + Leaflet init + BI wiring + reloadBusiness + progress + Wilayah options + spatialChart init |
| `ui/src/mapControl.js` (536 line) | LeafletAdapter semantic control + WARNA_STYLE + aktivitasLayer/lines + popup konteks-aware |
| `ui/src/businessAdapter.js` | `resolveTemplate` + `loadBusinessData 12s retry1 503` + `queryStats` + `fetchWilayahOptions/wilayah_labels` + `fetchAktivitasPoints adaptif 1000` |
| `ui/src/spatialMapState.js` | Isolated BI store |
| `ui/src/spatialChart.js` | Flying chart center `560px z400` |
| `ui/styles/map.css` (13628→14934) | Full-bleed + flying + responsive |
| `ui/src/core/layout.js` | Drag/resize/lock/persist — patched `mapPanel z 5 important` |
| `server.py:_simoge_*` | `show_on_map → map_store.set_features + warna_counts`, `query, /api/spatial/*, /api/aktivitas/photo/<uuid>?token, /api/spatial/chart, /api/map/*` |
| `~/.hermes/.../simoge_db.py` | 7 `_map` + `wilayah_labels` + `aktivitas_recent/penyadap_aktivitas` |
| `ui/vendor/leaflet/*`, `ui/vendor/chart.js` | Vendored |

## 9. Posisi Flying Saat Ini

```
.map-wrap.map-full (relative flex1 460px)
  #mapBox (absolute inset 0 — 100% frame, di bawah frame HUD z10)
  .map-fly-head (absolute top8 pill — BI header)
  .map-fly-top (absolute top44 — toolbar + filters drawer 46vh + search + chips)
  KPI (absolute left8 bottom8 60% 56px) | Legend (absolute right8 bottom8 40% 56px) — satu baris 8px
  Meta pill (right8 bottom70) + Insight (left/right8 bottom92 64px) + Progress pill (left8 bottom162 168px z450)
  Chart (absolute center 560px z400) — ANA controlled
  Leaflet controls: .leaflet-top 112px .leaflet-bottom 78px (hindari fly top)
```

> Token: `X-Ana-Token` dari `meta[name=ana-token]` (`__ANA_TOKEN__` → `API_TOKEN`). Host `127.0.0.1:8730` via `HERMES_PROFILE=anna`.




Header panel (BUSINESS INTELLIGENCE, badge periode YYYY-MM-P, badge mode CODING/ASISTEN)
Peta (#mapBox Leaflet + kontrol layer Satelit/Gelap + skala)
Toolbar atas — dropdown EVALUASI Bisnis (spatialBiz), Layer Petak (spatialKat), tombol Filter, KPI, Muat
Panel Filter (Waktu: bulan/tahun/periode; Wilayah: DIVRE/KPH/BKPH/RPH/TPG + Terapkan/Reset)
Chips filter aktif (spatialChips)
Pencarian petak (cari no petak + tombol fit ◎)
Strip KPI — 4 kartu: Total petak, Bongkor, Perlu perhatian, Terpenuhi
Insight (spatialInsight ringkasan ANNA)
Meta (baru/total polygon + status)
Legend (warna status + atribusi Esri/Maxar)
Progress (muncul hanya saat muat)
Chart (modal tengah, muncul hanya saat ANA tampilkan)
