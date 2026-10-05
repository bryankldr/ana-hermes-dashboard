# SPATIAL MAP — Panduan ANA (chat & slash)

Peta hidup di browser (`window.__anaMap`, Leaflet + Esri). ANA kendalikan
lewat antrean, bukan DOM scraping.

## Slash (di chat dashboard)

- `/map state` — posisi, zoom, basemap, layers, selection terakhir
- `/map set_view {"lat":-8.17,"lng":114.12,"zoom":13}` — pindah kamera
- `/map select_feature {"id":"<no petak>"}` — zoom + popup ke petak
- `/map highlight_features {"ids":["A","B"]}` — tandai kuning
- `/map toggle_layer {"id":"Petak"}` — on/off layer
- `/map set_basemap {"id":"Satelit"}` — Gelap ↔ Satelit
- `/map set_filter {"query":"2111"}` — tampilkan yang cocok saja
- `/map fit_all` · `/map reset_view` · `/map clear_selection` · `/map clear_highlights` · `/map clear_filter`
- `/map result <id>` — baca hasil (browser eksekusi ±1.5 dtk)
- `/map queue` — intip antrean

Ops penuh: get_state, set_view, fit_bounds, fit_all, reset_view,
get_layers, set_layer_visibility, toggle_layer, set_basemap,
select_feature, get_selected, clear_selection, highlight_features,
clear_highlights, set_filter, clear_filter.

## HTTP (untuk Hermes/tools luar)

- `POST /api/map/command {"op":"set_view","args":{...}}` → `{"id":"m1"}`
- `GET /api/map/result?id=m1` → `{"ok":true,"data":{...}}`
- `GET /api/map/state` → state terakhir yang di-push browser
- Semua token-gated (`X-Ana-Token` + Origin localhost).

## Batasan jujur

- State segar hanya bila dashboard terbuka di browser (push tiap 4 dtk).
  Tanpa browser: command antre, result pending — `/map state` bilang terus terang.
- Perintah visual-only (zoom/highlight/select): tanpa konfirmasi.
- MCP `maplibre` (11 tools: docs/style/viewport math/Flutter codegen)
  dipakai untuk hitung bounds & validasi style, bukan kontrol live.
  Kontrol live = adapter `ui/src/mapControl.js` + bridge ini.
- Esri attribution wajib tetap ada bila ganti basemap.
