---
title: Medan Aktivitas dan Sintesis Multi-Data
created: 2026-10-03
updated: 2026-10-03
type: concept
tags: [medan, operasional, sintesis]
sources: [raw/articles/skema-database-kph-bwb-sandbox2.md]
---

# Medan Aktivitas dan Sintesis Multi-Data

Data medan direkam per aktivitas di `getah_aktivitas_sadap`; hasil fisiknya
diverifikasi di `getah_aktivitas_penerimaan` → `getah_drum` → `getah_perni`.
Halaman ini menjelaskan cara membaca medan per petak/wilayah dan menggabungkannya
dengan produksi jadi kesimpulan intelijen.

## Kolom medan (getah_aktivitas_sadap)

- `cuaca`: cerah / mendung / hujan (snapshot: 15735 / 3889 / 557 dari 20181).
- `akses_lokasi`: mudah / sedang / sulit (snapshot: 14627 / 2820 / 2734).
- `lat`/`long`/`alt`: koordinat + ketinggian, tipe TEKS — parsing + validasi dulu
  sebelum agregasi (lihat [[kualitas-data]]). Null rate + outlier alt belum diukur.
- Flag teknik: quare, semprot_cas, budaya_bersih, kerok, naik_batok (tinyint).
- Setiap aktivitas membawa kode_* wilayah + tpg FK → agregasi per
  [[petak]]/[[tpg]]/[[rph]]/[[bkph]] selalu mungkin.

## Aturan agregasi per wilayah

- "Daerah sering hujan" = proporsi `cuaca=hujan` per BKPH/RPH/TPG dari engine,
  BUKAN angka global 557. Selalu sebutkan scope + periode.
- "Akses sulit" = proporsi `akses_lokasi=sulit` per wilayah. "Paling tinggi" =
  median `alt` per wilayah SETELAH validasi teks→angka (abaikan null/outlier,
  laporkan berapa yang diabaikan).
- Aktivitas dibuat DI DALAM wilayah petak — filter wilayah valid untuk semua
  pertanyaan medan.

## Rantai verifikasi sadap → penerimaan

`aktivitas_sadap.id_rencana/id_andil` → `aktivitas_penerimaan.id_andil/nomor_drum/
berat_penerimaan` → `drum.berat_tpg/berat_pgt` → `perni.total_berat_pgt`.
Setiap sambungan = titik susut (contoh: 80→80→79.24). Aktivitas = klaim lapangan,
penerimaan = bukti timbang. Keduanya dihubungkan via `id_andil` + `id_penyadap` + tanggal.

## Matriks sintesis medan × hasil

| Medan | Hasil | Pola |
|---|---|---|
| hujan tinggi + akses sulit + berat rendah | produksi rendah | risiko medan, wajar |
| cuaca cerah + akses mudah + berat rendah | produksi rendah | masalah non-medan: teknik, pohon, atau workforce (lihat [[produktivitas]]) |
| aktivitas banyak + penerimaan sedikit | gap klaim vs bukti | lag setor atau kebocoran (lihat [[data-hilang]]) |
| alt tinggi + mutu rendah | mutu turun | hipotesis suhu/ketinggian, perlu uji korelasi bukan klaim |

Matriks dibaca sebagai hipotesis berprioritas, bukan vonis. Korelasi ≠ sebab
(lihat [[uji-kausalitas]]).

## Batas

- Penerimaan tidak 1:1 dengan aktivitas (lag waktu setor, drum belum ditimbang).
  Jangan bagi berat penerimaan dengan jumlah aktivitas mentah-mentah.
- Semua angka dari Business Data Engine (lihat [[batas-data-engine]]).
- `alt` teks: jangan ranking ketinggian tanpa validasi parsing.
