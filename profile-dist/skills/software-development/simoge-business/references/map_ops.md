## Map Command Ops & Styling

`map_store.ALLOWED_OPS` includes `set_features`, `clear_features`, `set_basemap`,
`fit_bounds`, `select_feature`, `highlight_features`, `set_filter`, plus the
ANA panel-control ops `spatial_set`, `spatial_get`, `spatial_search`, `spatial_reload`
(intercepted by `ui/src/map.js`, not `LeafletAdapter` methods).

**ANA full control of Toolbar / Filter / Search (via `/api/map/command`):**
- `spatial_set {business, filters}` — set dropdown + filter controls, panel reloads
  itself so KPI/legend/insight/progress follow (e.g. `{business:"petak",
  filters:{kategori:"kurang"}}` shows only yellow via the `warna` mapping).
- `spatial_get {}` — read back effective `{state, spatial, mapCount}`.
- `spatial_search {q}` — focus a petak via `select_feature`.
- `spatial_reload {}` — schedule a debounced reload.
Post the op, then poll `GET /api/map/result?id=<id>` for the handler outcome —
`take_pending()` drains the queue, so a result fetched once is gone on the next read.

Any drain path that executes queue commands outside the poll loop must replicate
the loop's side effects: POST `/api/map/result` AND push `/api/map/state` — the
poll's `pushState` is throttled and never fires for drain-executed commands, so
`/api/map/state` stays stale (count 0) even though the polygons rendered.

**Warna bisnis otomatis**: template `*_map` mengembalikan kolom `warna` (+ `kategori`,
`pencapaian_pct`). `ui/src/mapControl.js: LeafletAdapter.WARNA_STYLE` memetakan
`warna` ke Leaflet style; `_resolveStyle(feature, opts)` cek `properties.warna`
tanpa perlu argumen tambahan. Popup menampilkan `warna (kategori)` dan `%` RKAP.

Override eksplisit (jarang perlu):
```python
# via server bridge: set_features with style_expression
# mapControl: set_features(geojson, {style_expression: {field: 'warna', mapping: {...}}})
```

GET `/api/map/state` to confirm `basemap` (Satelit default) dan `count`.
