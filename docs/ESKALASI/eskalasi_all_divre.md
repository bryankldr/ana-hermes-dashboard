Tidak ideal, tidak siap. Arsitektur skala 1 KPH (809 petak) ≠ arsitektur 20+ KPH per DIVRE (16.000+ petak).

1. Arsitektur Dashboard — Lubang Skala
Komponen
Skala Sekarang (1 KPH)       |      Skala Target (20 KPH × 5 DIVRE)              |   Blokir
GeoJSON payload	               809 features ~2 MB	16.000+ features ~40+ MB	    Browser OOM, timeout 30s,Leaflet freeze

Query petak_efektivitas_map	1 JOIN, 809 baris < 500ms	16.000+ baris, spatial join multi-KPH > 10s	MariaDB tanpa spatial index, full scan

Panel render	set_features 809 polygon langsung	16.000 polygon = 3-5 detik main thread blocked	Tidak ada clustering, simplifikasi, tiling

Cache	_SHOW_CACHE 3 detik per spatial_id	16.000 features unik per viewport → cache miss 99%	Cache key tidak pakai viewport/bounds
A
nna tool-call	show_on_map kembalikan features: 809	features: 16000 → tool result > context window	Payload strip sudah benar, tapi panel minta ulang full



Yang HARUS berubah sebelum skala:

Vector tiles (PMtiles / MVT) — bukan GeoJSON mentah. Server generate tile pyramid, panel request via XYZ. mapControl.js sudah support set_basemap tapi tidak ada tile server.
Viewport query — spatial_set kirim bounds + zoom, server return hanya petak di viewport (LIMIT + spatial index). Sekarang limit=1000 hardcode.
Spatial index DB — MariaDB SPATIAL INDEX pada geometry + WHERE MBRContains(...). Atau migrasi ke PostGIS (lebih cepat spatial join).
Aggregation tier — Zoom < 11: server return centroid/cluster (KPI per BKPH), bukan polygon per petak. Panel renderKPIs sudah ada, butuh data source baru.
Streaming / pagination — map_store.py queue tidak support progressive load. Butuh spatial_set op load_more + cursor.
2. Pengetahuan ANNA — Belum Robust
Yang sudah ada (baru ditulis):

intent-ke-template-peta → mapping intent → template + param wajib ✓
Yang HILANG untuk skala multi-DIVRE:

Domain
Yang Dibutuhkan
Status
Template selection skala	"petak seluruh DIVRE Jatim" → petak_efektivitas_map + kode_divre=2 + flag aggregated=true → server return cluster/KPI, bukan polygon	❌
Parameter pagination	viewport: {west,south,east,north}, zoom, page_size	❌
Performance hint	ANNA tahu kapan pakai petak_efektivitas_map (detail) vs kph_summary_map (ringkasan)	❌
Multi-DIVRE query pattern	kode_divre array, kode_kph array, exclude_kph	❌
Tile-based flow	ANNA arahkan panel ke set_basemap + tile URL, bukan set_features GeoJSON	❌
Error handling skala	Timeout → fallback ke aggregated view, partial load, retry dengan zoom out	❌
Business Data Engine template	Template baru: kph_summary_map, divre_heatmap, cluster_petak_map dengan aggregation_level param	❌
Contoh kasus gagal nanti:

User: "tampilkan efektivitas petak seluruh DIVRE Jawa Timur"
ANNA sekarang: show_on_map("petak_efektivitas_map", tahun=2026, kode_divre=2) → server query 16.000 petak → GeoJSON 40 MB → panel freeze → user marah.

Seharusnya:

ANNA: detek "seluruh DIVRE" + zoom level rendah → show_on_map("kph_summary_map", tahun=2026, kode_divre=2) → server return 5 KPH centroid + KPI → panel render instan. User zoom in → panel request tile / viewport query detail.

3. Rencana Minimal Sebelum Multi-DIVRE
Prioritas
Tindakan
File/Tempat
P0	Tambah aggregated flag di _TEMPLATE_SPATIAL + template kph_summary_map (return centroid + KPI per KPH/BKPH)	simoge_db.py, server.py
P0	Spatial index MariaDB: ALTER TABLE petak_efektivitas_map ADD SPATIAL INDEX(geometry) + WHERE MBRContains di _wilayah_where	simoge_db.py:_wilayah_where
P1	spatial_set op load_viewport kirim bounds, zoom; server return LIMIT 500 di bbox	map.js:spatial_set, map_store.py, server.py:_spatial_sync
P1	PMtiles generator script (tippecanoe / pg2mvt) + tile server (Martin / TileServer-GL)	Infra baru, mapControl.js:set_basemap
P2	Wiki ANNA: queries/skala-multi-divre.md — template selection tree, viewport params, fallback chain	ANNA-KNOWLEDGE/queries/
P2	Wiki ANNA: concepts/arsitektur-skala-peta.md — tile vs geojson, clustering, pagination, cache strategy	ANNA-KNOWLEDGE/concepts/
4. Keputusan Saat Ini
Jangan bangun multi-DIVRE di atas arsitektur GeoJSON mentah. Akan macet di 3-4 KPH.

Lakukan dulu (urutan):

Spatial index + viewport query (2-3 hari) — query cepat, payload kecil.
Template aggregated kph_summary_map (1 hari) — ANNA pakai untuk zoom out / "seluruh DIVRE".
PMtiles pipeline (1 minggu) — production ready.
Wiki ANNA skala (parallel) — biar dia tahu pilih mana.
Mau saya mulai P0: spatial index + template kph_summary_map + viewport param? Bisa selesai hari ini.