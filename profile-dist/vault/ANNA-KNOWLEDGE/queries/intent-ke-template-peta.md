---
title: Intent ke Template Peta
created: 2026-10-03
updated: 2026-10-04
type: query
tags: [intent, template, map, spatial, rogojampi, licin, glenmore, jatim, jateng, jabar]
sources: [simoge_db.py, ana_simoge_tool.py, server.py _TEMPLATE_SPATIAL]
---

# Intent ke Template Peta — Mapping Wajib ANNA

**Aturan:** ANNA HARUS pakai mapping ini untuk `show_on_map`. Jangan tebak template/param. Semua parameter `kode_*` pakai **kode numerik** (bukan nama). Alias wilayah lihat `[[bkph]]`, `[[kph]]`, `[[divre]]`.

## 1. Petak per wilayah (efektivitas/bongkor/multi-penyadap/idle)

| Intent user | Template | Param wajib | Catatan |
|---|---|---|---|
| "tampilkan polygon petak **rogojampi**" / "petak daerah rogojampi" | `petak_efektivitas_map` | `tahun`, `kode_bkph=3121102` | Efektivitas (bongkor/kurang/terpenuhi). Default tahun=2026. |
| "tampilkan polygon petak **licin**" / "petak daerah licin" | `petak_efektivitas_map` | `tahun`, `kode_bkph=3121101` | LICIN = 3121101 |
| "tampilkan polygon petak **glenmore**" | `petak_efektivitas_map` | `tahun`, `kode_bkph=3121104` | GLENMORE = 3121104 |
| "petak bongkor **rogojampi**" | `petak_bongkor_map` | `tahun`, `kode_bkph=3121102` | Hanya kategori bongkor |
| "petak multi penyadap **licin**" | `petak_multi_penyadap_map` | `tahun`, `kode_bkph=3121101` | |
| "petak idle **glenmore**" | `idle_petak_map` | `tahun`, `kode_bkph=3121104` | Warna kuning = idle |

## 2. Petak level KPH / DIVRE (tanpa BKPH)

| Intent user | Template | Param wajib | Catatan |
|---|---|---|---|
| "petak **KPH Banyuwangi Barat**" | `petak_efektivitas_map` | `tahun`, `kode_kph=31211` | Semua BKPH di bawahnya |
| "petak **DIVRE Jawa Timur**" | `petak_efektivitas_map` | `tahun`, `kode_divre=2` | JATIM = 2 |
| "petak **DIVRE Jawa Tengah**" | `petak_efektivitas_map` | `tahun`, `kode_divre=1` | JATENG = 1 |
| "petak **DIVRE Jawa Barat**" | `petak_efektivitas_map` | `tahun`, `kode_divre=...` | Cek `[[divre]]` — JABAR belum ada di sandbox |

## 2b. Ringkasan KPI per Wilayah (zoom out / agregat DIVRE/KPH/BKPH) — **BARU P0**

| Intent user | Template | Param wajib | Catatan |
|---|---|---|---|
| "ringkasan **KPH** seluruh DIVRE" / "summary KPH" | `kph_summary_map` | `tahun`, `aggregated_level=kode_kph` | Centroid + KPI per KPH (bongkor/kurang/terpenuhi/eff) |
| "ringkasan **DIVRE** Jawa Timur" | `kph_summary_map` | `tahun`, `aggregated_level=kode_divre`, `kode_divre=2` | 1 baris per DIVRE |
| "ringkasan **BKPH** KPH Barat" | `kph_summary_map` | `tahun`, `aggregated_level=kode_bkph`, `kode_kph=31211` | 5 baris BKPH |
| "overview peta seluruh DIVRE" | `kph_summary_map` | `tahun`, `zoom=9` | Auto-escalate ke DIVRE (zoom<11) |

**Catatan teknis `kph_summary_map`:**
- `aggregated_level`: `kode_divre` | `kode_kph` | `kode_bkph` (default `kode_kph`)
- `bounds`: `[west, south, east, north]` — filter viewport via spatial index (geom)
- `zoom`: level zoom — server auto-naikkan aggregated_level kalau zoom < 11
- Return: `centroid` (Point GeoJSON), `total_petak`, `total_luas_ha`, `bongkor`, `kurang`, `terpenuhi`, `avg_efektivitas_pct`
- Cocok untuk zoom out (peta seluruh DIVRE/KPH) — payload < 500 KB, query < 500ms

## 3. Aktivitas / Penyadap

| Intent user | Template | Param wajib | Catatan |
|---|---|---|---|
| "aktivitas di **glenmore**" / "aktivitas **Glenmore**" | `aktivitas_petak_map` | `tahun`, `bulan`, `periode`, `kode_bkph=3121104` | Default periode=0 (bulan penuh). `pembaharuan_ke` opsional 1-4. |
| "aktivitas **Jatim**" / "aktivitas **Jawa Timur**" | `aktivitas_petak_map` | `tahun`, `bulan`, `periode`, `kode_divre=2` | |
| "aktivitas **Jateng**" / "aktivitas **Jawa Tengah**" | `aktivitas_petak_map` | `tahun`, `bulan`, `periode`, `kode_divre=1` | |
| "top petak aktivitas **rogojampi**" | `aktivitas_top_petak` | `tahun`, `bulan`, `periode`, `kode_bkph=3121102` | Limit default 1000 |

## 4. Produksi / RKAP

| Intent user | Template | Param wajib | Catatan |
|---|---|---|---|
| "petak produksi tidak target **bulan 2 tahun ini**" / "pencapaian rkap **februari**" | `rkap_map` | `tahun`, `bulan`, `periode=0` | `periode=0` = bulan penuh (P1+P2). Tanpa filter wilayah = seluruh KPH. |
| "produksi **rogojampi** bulan 5" | `produksi_per_wilayah` | `tahun`, `bulan`, `periode`, `kode_bkph=3121102` | Hanya tabel, tidak ada polygon. Gunakan `rkap_map` untuk peta. |

## 5. Matriks

| Intent user | Template | Param wajib |
|---|---|---|
| "matriks petak **licin**" | `matriks_map` | `tahun`, `kode_bkph=3121101` |

## Kode Wilayah Cepat (Sandbox 2026)

| Nama | Kode | Level |
|---|---|---|
| DIVRE Jawa Tengah | `1` | divre |
| DIVRE Jawa Timur | `2` | divre |
| KPH Banyuwangi Selatan | `31210` | kph |
| KPH Banyuwangi Barat | `31211` | kph |
| BKPH Licin | `3121101` | bkph |
| BKPH Rogojampi | `3121102` | bkph |
| BKPH Kalisetail | `3121103` | bkph |
| BKPH Glenmore | `3121104` | bkph |
| BKPH Kalibaru | `3121105` | bkph |

## Parameter Waktu Baku

- `tahun`: 2026 (default sandbox)
- `bulan`: 1–12
- `periode`: `1` (1–15), `2` (16–akhir), **`0` = bulan penuh** — "bulan 5" → `periode=0`, bukan `periode=1` + `periode=2` manual.
- `pembaharuan_ke`: `"1".."4"` / `"semua"` — hanya untuk `biz=aktivitas`.

## Contoh Panggilan Benar

```python
# Petak Rogojampi (yg user tanya tadi)
show_on_map("petak_efektivitas_map", tahun=2026, kode_bkph=3121102)

# Aktivitas Glenmore bulan 2 penuh
show_on_map("aktivitas_petak_map", tahun=2026, bulan=2, periode=0, kode_bkph=3121104)

# RKAP Februari 2026 seluruh KPH
show_on_map("rkap_map", tahun=2026, bulan=2, periode=0)

# Petak DIVRE Jawa Timur
show_on_map("petak_efektivitas_map", tahun=2026, kode_divre=2)
```

## Anti-Pattern (Yang ANNA Lakukan Sebelumnya — SALAH)

- `petak_with_geometry` tanpa filter → 809 petak, bukan rogojampi.
- `show_on_map` CLI positional arg salah → error.
- `tool_call` ke skill non-existent → error.
- Tebak kode wilayah (mis. "rogojampi" string) → server skip filter diam-diam → 809 petak, ANNA jawab seolah rogojampi.

## Link Balik

[[tool-bisnis-anna]], [[bkph]], [[divre]], [[panel-spatial-map]], [[skala-multi-divre]], [[arsitektur-skala-peta]]