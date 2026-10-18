---
title: Aktivitas Penyadapan
created: 2026-10-02
updated: 2026-10-18
type: entity
tags: [aktivitas, operasional, penyadap]
sources: [raw/articles/simoge-business-ontology.md, raw/articles/skema-database-kph-bwb-sandbox2.md, bit_engine.py]
---

# Aktivitas Penyadapan

Realisasi kegiatan lapangan. Info: [[penyadap]], [[rencana-aktivitas]], waktu, lokasi, koordinat, [[periode]], pembaharuan, info produksi sesuai konteks.

Aktivitas aktual wajib dibedakan dari [[rencana-aktivitas|rencana]]. Jumlah aktivitas ≠ jumlah penyadap. Lihat [[metrik-aktivitas]] dan [[distingsi-semantik-kritis]].

Data medan per aktivitas (cuaca, akses, ketinggian) + rantai verifikasi ke penerimaan dan matriks sintesis ada di [[medan-aktivitas]].

## Jenis aktivitas (6 flag + pohon per jenis)

Setiap baris `getah_aktivitas_sadap` dapat memiliki 1..n flag `1`:

| Flag | Kolom | `jml_phn_*` | Arti (operasional) |
|---|---|---|---|
| Quare | `quare` | `jml_phn_quare` | Melukai batang pinus membuka jalur getah keluar |
| Semprot CAS | `semprot_cas` | `jml_phn_semprot_cas` | Penyemprotan stimulan merangsang getah keluar |
| Budaya Bersih | `budaya_bersih` | `jml_phn_bdy_bersih` | Kebersihan area sadapan untuk mutu getah baik |
| Kerok | `kerok` | `jml_phn_kerok` | Pemanenan getah beku di jalur sadapan / pengumpulan getah beku |
| Naik Batok | `naik_batok` | `jml_phn_naik_batok` | Menaikkan ketinggian batok/wadah per SOP, minimalisir pembekuan di jalur |
| Pulung | `pulung` | `jml_phn_pulung` | Pengumpulan getah cair (baru, ikut `AKTIVITAS_FLAGS`) |

Setiap jenis dicatat **jumlah pohonnya** (`jml_phn_*` varchar/int, pohon tersentuh per jenis per baris). Interpretasi: **coverage** = `MAX(jml_phn_*) / jumlah_pohon` (pohon unik tersentuh, tidak dobel hitung bila 1 pohon dikerjakan pembaharuan 1..4), semua jenis = rata-rata coverage jenis berdata saja; **intensitas** = `SUM(jml_phn_*)` terpisah sebagai usaha/pengulangan.

## Pembaharuan

`pembaharuan_ke` = 1, 2, 3 (4 ada tapi belum berdata). Produktifitas bervariasi per pembaharuan: ke-1 rendah, ke-3 optimal, ke-4 menurun. Setiap pembaharuan memiliki kombinasi 6 aktivitas di atas.

## Kualitas data snapshot 2026-10-03

`jml_phn_*` = 100% NULL (`20184/20184` kosong) — pohon per jenis belum diisi di sandbox, sehingga metrik pohon belum bisa dihitung. Flag `1/0` tetap terisi (Quare 19580, Semprot CAS 17432, Budaya 11341, Kerok 2821, Naik Batok 7073, Pulung 0). BIT wajib laporkan limitation bila pohon diminta. Filter periode wajib `tgl_pembaharuan` (tanggal kerja pelapor, dipakai engine untuk P1/P2), bukan `tgl_aktivitas`.

## Agregasi

`aktivitas_agregat(grup_by=aktivitas|penyadap|pembaharuan)` dan `aktivitas_top_petak` dari Business Data Engine. Period bounds ikut `sampai_dengan` Ya/Tidak (lihat [[periode]]). Diagonal `Q = N × A × F × Y` (pohon × aktivitas × frekuensi × yield) dibaca sebagai hipotesis, bukan vonis.

## Robust (BIT v0.3)

BIT discover `AKTIVITAS_FLAGS` dari `simoge_db.AKTIVITAS_FLAGS` + `AKTIVITAS_LABEL` dan cek `information_schema.COLUMNS` — hanya kolom flag yang ada di DB yang di-`SUM`. `jml_phn_*` null-safe via `COALESCE(SUM(CAST(NULLIF(col,'') AS UNSIGNED)),0)` (varchar `''`/NULL sekarang, int nanti). `pohon_tersentuh_total==0` → `limitation DATA_QUALITY`; bila terisi, `Q` auto pakai `Y=actual/pohon_tersentuh` tanpa ubah kode (`ponytail:` di `bit_engine.py`). Tambah jenis baru cukup tambah kolom flag + `jml_phn_*` di DB dan 1 baris di `AKTIVITAS_FLAGS` (single source); BIT ikut tanpa bongkar drawer/engine.
