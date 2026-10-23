# Produksi: bulanan vs periode (setengah bulan)

Template produksi punya parameter `periode` yang menentukan rentang tanggal.
Default `periode: 1` — artinya HANYA tanggal 1–15, bukan sebulan penuh.

## Aturan

Pertanyaan "produksi bulan X" SELALU butuh `periode: 0` (bulan penuh).
Tanpa `periode`, angka yang keluar kira-kira separuh realisasi dan gampang
salah dibaca sebagai penurunan drastis.

```python
call_simoge_tool("produksi_aktiv", {"bulan": 7, "tahun": 2026, "periode": 0})
# -> rows[0]: total_kg, n_terima, n_petak  (bulan penuh)
```

`periode: 1` = tanggal 1–15, `periode: 2` = tanggal 16–akhir, `periode: 0` = penuh.
Verifikasi cepat: `total_kg(periode 0) == total_kg(periode 1) + total_kg(periode 2)`.
Jika tidak sama, parameter tidak dipakai template itu — cek `sql` di respons.

## Cek konsistensi sebelum menyimpulkan tren

1. `produksi_trend {tahun}` mengembalikan baris per `bulan` × `periode`.
   Jumlahkan P1+P2 per bulan; satu baris saja = setengah bulan.
2. `produksi_year_to_date {bulan, tahun}` = kumulatif s/d akhir bulan itu.
   Cocokkan dengan penjumlahan trend; selisih kecil wajar karena batas tanggal
   antar tabel (penerimaan vs pembaharuan sadap).
3. `produksi_per_wilayah {bulan, tahun, level}` = kumulatif YTD per wilayah +
   `target_kg` + `achievement_pct`; `level` = `kode_kph` / `kode_bkph`.
   `bulan` di sini berarti "s/d bulan", bukan bulan tunggal.
4. Target bulanan = `target_kg` tahunan / 12; persen bulanan = total bulan /
   target bulanan × 100.

## Pitfall: penurunan palsu karena data belum masuk

Sebelum menyebut "produksi turun X persen", cek `data_freshness`
(`tgl_terakhir`, `total_baris`, `hari_ini`, `tujuh_hari`) dan bandingkan
jumlah `n_terima` antar bulan di `produksi_trend`. Bulan terakhir yang
`n_terima`-nya jauh lebih kecil dari bulan sebelumnya biasanya rekaman belum
lengkap (sinkronisasi seret), bukan realisasi jatuh. Selalu sebut caveat ini
1 kalimat dan tawarkan verifikasi per BKPH/petak.

## Format jawaban (preferensi user)

Tonase + persentase, desimal 1 angka, format Indonesia (`63.833,0 kg`, `69,4 persen`).
Sebut scope (`KPH 31211 Banyuwangi Barat`) di kalimat pertama. Tutup dengan
satu tawaran lanjut (per BKPH / per petak / per penyadap).
