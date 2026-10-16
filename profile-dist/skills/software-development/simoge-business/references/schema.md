# Database Schema — kph_bwb_sandbox2 (verified)

## Tables

### geteh_petak (Master RTT petak) — 810 rows (2026)
```
id, user_created, user_updated
jenis_sadap, luas_baku, rencana_luas, jumlah_pohon, tahun_tanam
target_rkap, target_semangat, jarak_petak, tipe_jarak
nomor_petak, date_created, date_updated
nama_tpg, tahun_rtt (2025|2026), status, divre, kph, bkph, rph
kode_divre, kode_kph, kode_bkph, kode_rph, kode_data, kode_evapot, kode_tpg, tpg
```
**Joins**: `kode_evapot` ↔ `petak_polygon.kode_evapot`  
**Note**: `kode_petak` is NULL — use `kode_evapot`.

### petak_polygon (Geometry + metadata)
```
id, status, sort, user_created, kode_data, phw
polygon (longtext GeoJSON), luas_ha, luas_baku, fungsi_hutan
jenis_tanaman, tahun_tanam, umur, kelas_perusahaan, bagian_hutan
kelas_hutan, no_spk, sdp_pinus, anak_petak
kode_kph, kode_bkph, kode_rph, kode_divre, kode_tpg, kode_evapot, tpg
```

### geteh_daftar_tpg
```
id, nama_tpg, npk_online (DEPRECATED), alias, jarak_pgt
kode_kph, kode_bkph, kode_rph, kode_divre, status, kode_tpg
```

### geteh_andil (Penyadap → Petak assignment)
```
id, id_penyadap, kode_evapot, luas_andil (decimal)
nama_penyadap, nomor_petak, kode_kph, kode_bkph, kode_rph, kode_tpg
```
**Joins**: `id_penyadap` → `geteh_penyadap.id`, `kode_evapot` → `geteh_petak.kode_evapot`

### geteh_penyadap
```
id, nomor_penyadap, nama_penyadap, KTP, telpon, alamat, status
id_tpg, nama_tpg, kode_kph, kode_bkph, kode_rph, kode_tpg
```

### geteh_aktivitas_sadap (Tapping execution)
```
id, id_penyadap, id_andil, id_rencana
tgl_pembaharuan (date!), tgl_aktivitas, latitude, longitude, cuaca
akses_lokasi, quare, semprot_cas, budaya_bersih, kerok, naik_batok, pulung
jml_phn_quare, jml_phn_semprot_cas, jml_phn_bdy_bersih, jml_phn_kerok, jml_phn_naik_batok, jml_phn_pulung
local_id, aktivitas_photo, kode_evapot, kode_kph, kode_bkph, kode_rph
```
**Date field**: `tgl_pembaharuan` (not `tanggal`), `tgl_aktivitas` (aktivitas date)

### geteh_aktivitas_penerimaan (Collection receipts)
```
id, nomor_penerimaan, id_penyadap, berat_penerimaan (decimal)
nomor_drum, id_andil, tanggal (date!), kode_evapot, kode_kph, kode_bkph
```
**Joins**: `id_penyadap` → `geteh_penyadap.id`, `nomor_drum` → `geteh_drum.nomor_drum`

### geteth_drum (Drum tracking)
```
id, status_drum, tanggal (date!), kapasitas
berat_penerimaan, berat_tpg, berat_pgt, nomor_drum, nomor_pengangkutan
nomor_perni, id_mutu_tpg, id_mutu_pgt, id_penyadap, ka, kk, local_id
kode_kph, kode_bkph, kode_rph, kode_tpg
```
**Note**: `status_drum` (not `status`), `tanggal` (not `tahun`/`bulan`)

### geteth_target_ro_nps (Monthly targets)
```
id, tahun, bulan (1-12), ro, nps
ro_periode_1, ro_periode_2, nps_periode_1, nps_periode_2
kode_kph, kode_divre
```
**Note**: No `kode_evapot`. Target per petak = `target_rkap` × (`ro_periode_X` / 100).

### geteth_laporan_petak
```
kode_evapot, tahun, bulan, periode, produksi
```

## Null / Gotchas
- `kode_petak` NULL in `getah_petak` + `petak_polygon` — use `kode_evapot`
- `polygon` is GeoJSON text — parse with `json.loads()` on read
- `npk_online` in `geteh_daftar_tpg` is deprecated — use `directus_users.npk`
- `geteh_aktivitas_sadap.tgl_pembaharuan` = date (not `tanggal`)
- `geteth_drum.status_drum` (not `status`), `tanggal` (not `tahun`/`bulan`)
