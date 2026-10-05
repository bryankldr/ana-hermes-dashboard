# SPATIAL MAP — Phase 1 Discovery Report
> Tanggal: 2026-09-29 · Dashboard: ana-hermes-dashboard · Sumber: SPATIAL_MAP.md

## 1. Dashboard application
- Root: `ana-hermes-dashboard/`
- Entry: `server.py` (stdlib `http.server.ThreadedHTTPServer`, tanpa framework)
- Runtime: `runtime.py` → `hermes chat -Q -q --format stream-json --source ana-dashboard`
- Commands: `commands.py` `/new /goal /profile /mode /kanban /background /tools /browser` + `state.json`
- Data panels: `services.py` (scan_projects, avd_status, vault_status, briefing)
- UI: `ui/index.html` + `ui/src/main.js` (vanilla ES modules, no bundler, no React/Vue)
- CSS modular: `ui/styles/{tokens,hud,layout,panels,components,map,workspace}`

## 2. SPATIAL MAP implementation
- File: `ui/src/map.js` 86 lines · `ui/styles/map.css` 17 lines
- Panel: `ensurePanel({id:'mapPanel', title:'SPATIAL MAP', rail:'right'})` → auto `LayoutManager.register()`
- Library: Leaflet 1.9.4 vendored `ui/vendor/leaflet/` (JS+CSS+images), `window.L` global, bukan MapLibre
- Init: `L.map(box).setView([-8.1776,114.1261],11)`, ResizeObserver 120ms `invalidateSize()` pada `#mapBox`
- Tools: input `#mapSearch` cari `petakNo` + button `#mapFit` fitBounds

## 3. Esri basemap integration
- `dark = L.tileLayer('https://server.arcgisonline.com/.../Canvas/World_Dark_Gray_Base/...')` attribution `Esri`
- `sat = L.tileLayer('https://server.arcgisonline.com/.../World_Imagery/...')` + `refLbl` boundaries
- `L.control.layers({Gelap: dark, Satelit: L.layerGroup([sat,refLbl])}, {Petak: petakLayer})`
- Gratis tanpa key, attribution wajib tetap ada bila migrasi ke MapLibre style

## 4. Frontend framework
- Pure browser ES modules via `<script type="module">`
- No build step, no npm deps. xterm.js juga vendored lokal
- Panel factory tunggal: `ui/src/utils/dom.js` → `ensurePanel()`

## 5. State management
- `ui/src/core/bus.js`: `EventBus` minimal + `state = {mode, session, running, bgJobs}`
- Tidak ada store untuk map. Map state (center/zoom/layers/selection) hidup di closure `map.js` saja
- Tidak ada canonical map state, tidak ada two-way sync ANA ↔ Map

## 6. API / WebSocket / event infra
- Server: REST JSON `GET /api/status|voices|mode|missions|vault|avd|layout|projects|sessions|jobs|terminals` + `POST /api/run|mode|layout|terminal|avd|speak|listen`
- Auth: `X-Ana-Token` + Origin `127.0.0.1:8730` + Host check, `RUN_LOCK` serialize `/api/run`
- Stream: NDJSON `/api/run` (hermes stream-json). Tidak ada WebSocket, tidak ada SSE map events
- Frontend bus: `bus.on/emit` tapi tidak dipakai map saat ini; map cuma `log('map',...)` ke event log

## 7. Map abstraction
- Tidak ada. `map.js` langsung panggil `L.*`; tidak ada adapter/interface
- SPATIAL_MAP.md minta semantic interface (`map_get_state`, `map_set_view`, dst) — belum ada celah

## 8. Existing MCP configuration
- `hermes mcp list` → `No MCP servers configured`
- Config: `~/.hermes/config.yaml` (2388 lines), blok `mcp_servers:` masih commented (line 1594)
- Tambah via `hermes mcp add <name> --command <cmd> --args ...` atau `--url`
- Katalog tersedia: `hermes mcp catalog` (airtable, algolia, atlassian, ...)

## 9. Hermes configuration
- `hermes config show` → model `hermes_combo` provider `custom` base `http://localhost:20128/v1`
- Tools enabled: web, browser, terminal, file, code_execution, vision, tts/stt, skills/todo/kanban/memory, dll
- Workdir `~/PROYEK_2026`, timezone `Asia/Jakarta`

## 10. Data
- `ui/data/petak_simple.json`: 2273 features, schema `{n: "petak_no", p: [[[lon,lat],...]]}` lon 114.06-114.12 lat -8.26 - -8.18 area KPHBWB
- Render: `L.polygon(latlngs, {color:'#2DF2FF', fillOpacity:0.12, petakNo})` + popup `Petak n`

## 11. MapLibre MCP (CodeStorm-Hub/maplibre_mcp)
- Repo: https://github.com/CodeStorm-Hub/maplibre_mcp (Node, npx, MIT, 1 star, 2026-07-25)
- Tools aktual: Layer1 docs search (`search_maplibre_docs` 43 repos), style validator/spec, offline BBox math, Martin/PostGIS/MVT scaffolder, PMTiles/MBTiles loader — Layer2 Flutter/Dart generators
- Tidak menyediakan live control `set_view/select_feature/highlight` terhadap peta dashboard yang sedang tampil. Ini MCP codegen/dokumentasi, bukan bridge runtime
- Risiko arsitektur: bila dianggap sebagai controller langsung, integrasi gagal. Perlu adapter sendiri di dashboard

## 12. Constraints & decisions
- Jangan hapus Esri — bungkus sebagai MapLibre raster source saat migrasi
- Jangan sebar MCP logic ke komponen UI — isolasi di `mapControl.js` (LeafletAdapter sekarang, MapLibreAdapter berdampingan nanti)
- Data ≠ rendering: `petak_simple.json` / GeoJSON / vector tiles tetap di data layer
- Visual-only ops (zoom/highlight) tanpa konfirmasi; destruktif persisten perlu konfirmasi
- Regression guard: Layout/HUD/chat/Esri tidak boleh rusak; fallback manual bila MCP mati

## 13. Phase 1 verdict
Discovery selesai. Blocker nol. Next Phase 2: install `maplibre_mcp` via `hermes mcp add`, verifikasi tools, pakai hanya untuk docs/style/math, sambil bangun adapter lokal untuk semantic control yang SPATIAL_MAP.md minta.

## 14. Sources inspected
`SPATIAL_MAP.md`, `server.py`, `runtime.py`, `commands.py`, `services.py`, `ui/src/map.js`, `ui/src/main.js` (1-500), `ui/src/core/{bus,api,layout}.js`, `ui/src/utils/dom.js`, `ui/styles/map.css`, `ui/index.html`, `ui/data/petak_simple.json` (header), `state.json`, `layout.json`, `.env.example`, `hermes mcp list / config show / tools list`, `~/.hermes/config.yaml` grep mcp

## 15. Progress log
- [x] Phase 1 discovery + report
- [x] Phase 2 MCP install + verify (2026-09-29)
  - Clone https://github.com/CodeStorm-Hub/maplibre_mcp ke /home/bryankldr/PROYEK_2026/maplibre_mcp
  - `npm install` (104 packages) — dist butuh node_modules, tanpa itu MODULE_NOT_FOUND
  - `hermes mcp add maplibre --connect-timeout 30 --command node --args .../dist/index.js` — 11 tools, enabled
  - `hermes mcp test maplibre` → Connected 672ms, 11 tools
  - Probe stdio read-only `calc_map_viewport` [[114.06,-8.26],[114.12,-8.18]] pad 0.05 → center [114.09,-8.22], zoom 14 OK
  - Konfirmasi: MCP ini codegen/docs, bukan live controller peta — adapter sendiri tetap dibutuhkan (Fase 3)
  - Config Hermes: `mcp_servers.maplibre` command node + connect_timeout 30, enabled true
  - `test_services.py` → all checks passed (dashboard tidak terpengaruh)
- [ ] Phase 3 map adapter
- [x] Phase 3 map adapter + Phase 4 canonical state (2026-09-29)
  - Baru `ui/src/mapControl.js`: `createMapState` + `LeafletAdapter` + factory. 16 method semantik (get_state/set_view/fit_bounds/fit_all/reset_view/get_layers/set_visibility/toggle/set_basemap/select/get_selected/clear_selection/highlight/clear_highlights/set_filter/clear_filter)
  - `ui/src/map.js`: wiring saja — registerBase Gelap/Satelit, registerLayer Petak, registerFeature per petak; search/fit/click lewat adapter; render & Esri tidak berubah
  - Generic: adapter tidak kenal `petakNo`/`Petak`; bisnis tetap di data layer
  - Baru `test_map_control.py` → all map control checks passed; `test_services.py` → all checks passed
- [ ] Phase 5 semantic controls
- [x] Phase 5 semantic controls + bridge ANA↔peta (2026-09-29)
  - Baru `map_store.py`: antrean command + cache state + hasil, thread-safe, whitelist 16 op cocok kontrak adapter
  - `server.py`: GET /api/map/state|queue|result + POST /api/map/command|state|result, token-gated pola sama seperti endpoint lain
  - `ui/src/map.js`: `startMapBridge()` poll 1.5s, unpack args object→positional, push state throttled 4s; `ui/src/main.js` auto-start; `api.js`: mapState/mapCommand/mapResult
  - Baru `test_map_bridge.py` (unit, 30 checks) + `test_map_endpoints.py` (HTTP vs server hidup, 17 checks)
  - `smoke.py` vs server 8731 → PASS 121 checks (FAIL 43/98 sebelumnya karena token salah — server 8730 tulis .ana_token miliknya sendiri, harness baca file yang sama tapi server target beda; bukan regresi)
- [x] Phase 6 dashboard integration: bridge auto-start di init, layout/Esri/chat tidak tersentuh
- [x] Chat wiring (2026-09-29): `/map` slash di `commands.py` (state/queue/result/<op> + help), `/commands` list update, `docs/SPATIAL_MAP_USAGE.md`. `test_map_command.py` → passed
- [x] Business spatial intel — directive #1-20 (2026-09-29)
  - Baru `spatial_intel.py`: semantic ops atas `ui/data/petak_simple.json` (2273 petak) — resolve_entity/find_petak/get_feature_context/get_polygon + spatial ops (point_in_petak/neighbors/radius/in_bounds/prefix/stats). Tak pernah tebak koordinat; ID hanya resolve exact.
  - `server.py`: POST /api/spatial/resolve|context|query (token-gated, pola sama). GET map/state|queue|result sudah ada.
  - `commands.py`: slash `/petak` — stats/info/fokus/tetangga/grup/sekitar/apa_ini + bare ref (pakai selected/highlighted dari map state, prioritas directive #9). `/petak fokus` enqueue select_feature via map_store. `/commands` list update.
  - Verifikasi: /petak stats/info/tetangga/grup/sekitar/apa_ini/exact/ambiguous/fokus + full suite (services/map_control/map_bridge/map_command) passed
- [ ] Phase 7 E2E visual agent tests (butuh browser hidup + dashboard jalan — belum bisa dari sesi ini)

---

## Addendum 2026-10-01 — petak_simple.json selaras bisnis
- `ui/data/petak_simple.json` lama 2273 `{n,p}` → kini **1004 features** wrapper `{meta,features}` harian dari `kph_bwb_sandbox2` (petak_polygon 1003 + enrich `tahun_rtt/kode_*/luas_baku/target_rkap`). Generate WIB `scripts/refresh_petak_simple.py` (cron 06:00), arsip `ui/data/snapshots/petak_YYYY-MM-DD.json` untuk YOY. `spatial_intel.py` toleran wrapper/array lama + `stats()` expose `meta` + mtime invalidate. Business Map tetap **DB 100%** via 7 `_map` — cadangan hanya identitas & fallback YOY.
