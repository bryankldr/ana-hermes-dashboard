## Business Rules — dari kontek_bisnis.md (jangan dilanggar)

### Join Keys (pastikan kolom benar)

- `getah_penyadap ↔ getah_andil` via `id_penyadap`
- `getah_andil ↔ getah_petak` dan `getah_andil ↔ petak_polygon` via `kode_evapot` (`kode_petak` is NULL)
- Semua tabel punya `kode_divre, kode_kph, kode_bkph, kode_rph, kode_tpg` untuk filter wilayah
- `getah_rencana_aktivitas ↔ getah_aktivitas_sadap` via `id_rencana`; `getah_aktivitas_sadap ↔ getah_penyadap` dan `getah_aktivitas_sadap ↔ getah_aktivitas_penerimaan` via `id_penyadap`
- `getah_drum` **jangan** pakai `id_penyadap` — join ke `getah_aktivitas_penerimaan` via `nomor_drum`; ke `getah_pengangkutan` via `nomor_pengangkutan`; ke `getah_perni` via `nomor_perni`; ke `getah_mutu` via `id_mutu`
- `getah_target_ro_nps.tahun` filter seperti `getah_petak.tahun_rtt`; kolom `bulan` 1=Januari...12; `ro_periode_1, ro_periode_2, nps_periode_1, nps_periode_2` = persen per periode

### Periode

- **Periode 1** = tanggal 1–15; **Periode 2** = 16–akhir bulan
- "P1 saat ini" = periode 1 bulan ini tahun ini; "P1 sampai dengan P2" = akumulasi P1 bulan 1 s/d P2 bulan ini; "sampai dengan" saja = tanggal 1 s/d hari ini — jumlahkan semua `ro/nps_periode_*` yang terlewati
- Target RO/NPS per petak = `target_rkap * (sum persen periode terlewati / 100)` — contoh: petak 28 C3 `target_rkap=697.6`, RO P1 Jan 3.5% → `697.6*3.5/100=24.4 kg`

### 4 Domain Evaluasi Spasial (2nd_kontek_bisnis_diperjelas.md)

Setiap polygon harus menjawab 1 pertanyaan bisnis — jangan campur indikator:
- **Evaluasi Petak** — Apakah coverage memadai? `luas_andil` vs `luas_baku` + jumlah penyadap. Warna merah bongkor (tanpa penyadap) / kuning luas_andil<luas_baku / hijau >=.
- **Evaluasi Aktivitas** — Apakah sadap berlangsung? Lihat apakah aktivitas benar-benar terjadi pada andil yang dialokasikan. AKTIF ada periode berjalan, IDLE sebelumnya ada berjalan tidak ada, BONGKOR tanpa penyadap atau >2 bulan tanpa aktivitas (61-hari window sebelum periode berjalan). Petak BONGKOR ≠ Andil BONGKOR.
- **Evaluasi Produksi** — Target RO/NPS vs aktual (`getah_target_ro_nps` persen × `target_rkap` × `luas_andil/luas_baku` untuk andil). Warna 0–25 merah / 26–50 oranye / 51–75 kuning / 76–100 hijau / >100 emas.
- **Evaluasi Matriks** — Keseimbangan luas/pohon/andil/penyadap/aktivitas/produksi. `luas_baku vs SUM(luas_andil)` + `jumlah_pohon vs SUM(jml_pohon)` sebagai pemeriksaan kedua.

### Bongkor / Idle / Aktif (Aktivitas — diperjelas)

- **Petak bongkor** = tidak ada penyadap sama sekali (`COUNT(DISTINCT id_penyadap)=0` di `getah_andil` untuk `kode_evapot` itu) **ATAU** >2 bulan tanpa aktivitas (`COUNT aktivitas 61 hari sebelum periode berjalan =0` dan `cur=0`)
- **Andil bongkor** = andil tanpa aktivitas 2+ bulan — hitung per-andil `NOT EXISTS (aktivitas untuk id_penyadap+kode_evapot BETWEEN window)` bukan per-petak count.
- **IDLE** = punya penyadap + ada aktivitas di window 61 hari, tapi `cur=0` — kuning. **jangan** gate IDLE pada `prev>0`: `prev` cuma satu periode, dan periode yang datanya belum masuk akan terbaca 0 untuk semua petak (2026-10 P1 = 0 untuk 809 petak), sehingga yang sebenarnya hidup jatuh ke merah.
- **AKTIF** = `cur>0` — hijau; tanpa penyadap + cur 0 → merah (bongkor)
- Prioritas CASE: `cur>0` hijau → `penyadap=0 ATAU two=0` merah → **ELSE idle** kuning. Jangan pakai `ELSE 'bongkor'` sebagai catch-all — itu mewarnai merah setiap petak yang punya penyadap dan aktivitas dalam 2 bulan tapi tidak di periode itu (114 dari 809 pada 2026-10 P1; idle benar 120, bukan 6). Template yang harus berbagi aturan ini: `idle_petak`, `idle_petak_map`, `aktivitas_petak_map`.
- **Petak vs andil counts**: `jumlah_penyadap/jumlah_andil` dari `getah_andil GROUP BY kode_evapot`; `andil_aktif` = andil dengan EXISTS aktivitas periode berjalan; `andil_bongkor` = andil tanpa aktivitas 61 hari; `andil_idle` = sisa. Simpan sebagai kolom untuk popup "Andil: 12 (aktif 10 · idle 1 · bongkor 1)".
- **Hitung aktivitas per petak** = `COUNT(*) FROM getah_aktivitas_sadap WHERE tgl_pembaharuan BETWEEN d0 AND d1 GROUP BY kode_evapot` (loose). Jangan `JOIN getah_andil ON id_penyadap AND kode_evapot` — petak bongkor punya 0 andil tapi bisa punya aktivitas; strict join hilangkan ~74% aktivitas dan bikin polygon merah padahal pin ada. Warna aktivitas lama `merah 0 / kuning 1-2 / hijau >=3` diganti `merah bongkor / kuning idle / hijau aktif` sesuai diperjelas; hitungan loose harus sama antara polygon `aktivitas_petak_map` dan pin `aktivitas_recent`.

### Pewarnaan Polygon (diperjelas.md — 4 mode)

- **Evaluasi Petak (efektivitas)**: merah = tidak ada penyadap (bongkor); kuning = `SUM(luas_andil) < luas_baku`; hijau = `luas_andil` >= `luas_baku` (coverage sesuai/lebih)
- **Evaluasi Aktivitas**: merah = bongkor (`penyadap=0` atau `two=0`); kuning = idle (punya penyadap + aktivitas 2 bln, `cur=0`); hijau = aktif (`cur>0`). Popup harus tampilkan `penyadap 8 · andil 12 (aktif 10 · idle 1 · bongkor 1) · aktivitas berjalan 86 / lalu 91` — fakta/indikator/interpretasi dipisah.
- **Evaluasi Produksi (pencapaian RKAP)**: merah 0–25%, oranye 26–50%, kuning 51–75%, hijau 76–100%, emas >100% (target_periode = `target_rkap * sum persen RO/NPS terlewati /100`)
- **Evaluasi Matriks**: merah = bongkor; oranye = kurang & cap<50; kuning = kurang; hijau = terpenuhi 0–100; emas = >100. Tambahkan matrik pohon `jumlah_pohon vs SUM(jml_pohon)` dan `pohon_pct` untuk diagnosis kedua.

### Penyadap Kurang Produktif & Analisa Efektivitas

- Kurang produktif = penyadap aktif, banyak aktivitas tapi `berat_penerimaan < target` (target = `target_rkap * persen RO/NPS periode * (luas_andil/luas_baku)`)
- Analisa efektivitas 1: `luas_baku` vs `SUM(luas_andil)` → butuh penyadap/tidak
- Analisa efektivitas 2: matrik `luas_andil, jml_pohon` (getah_andil) vs `luas_baku, jumlah_pohon` (getah_petak)

### Rencana Aktivitas — getah_rencana_aktivitas (planning vs execution gate)

- Tabel `getah_rencana_aktivitas` (14.594 baris snapshot 2026-10-03): `tanggal_rencana, id_penyadap, rencana_berat, id_rencana UNI, local_id UNI, id_andil, keterangan, kode_* wilayah, tpg FK, user_created` (mandor/KTS pembuat rencana). Bukan target — target di `getah_petak.target_rkap × getah_target_ro_nps` persen kumulatif.
- Join terverifikasi: `rencana → aktivitas` via `id_rencana`; `rencana → petak` via `kode_evapot AND tahun_rtt`; `rencana → penyadap/andil` via `id_penyadap`; `rencana → mandor/KTS` via `user_created → directus_users → jabatan (M1-M5/K1-K5)`. Jangan join rencana ke drum/penerimaan langsung — lewat aktivitas.
- 2 template terverifikasi: scalar `rencana_aktivitas(tahun,bulan,periode)` = `SUM(rencana_berat) WHERE tanggal_rencana BETWEEN period_bounds` (satu pintu untuk Target Coverage); `laporan_perencanaan_target_setor_vs_ro_nps` = per Mandor×TPG dengan dedup `GROUP BY user_created,kode_tpg,kode_evapot` lalu `MAX(target_rkap)` sebelum `SUM` — tanpa dedup target terdistorsi 2-5× karena satu petak bisa punya beberapa rencana.
- Period selalu `tanggal_rencana`, bukan `date_created`. P1=1-15, P2=16-akhir bulan. Laporan judul `LAPORAN PERENCANAAN TARGET SETOR VS TARGET RO/NPS (DD MMMM YYYY)` dengan `DD=e1` dari `period_bounds`.
- Pitfall: `laporan_perencanaan...` dapat 0 rows padahal scalar `rencana_aktivitas` 100+ ton — penyebab `JOIN r.kode_evapot=pt.kode_evapot AND pt.tahun_rtt` mismatch; cek scalar dulu, laporkan template-empty sebagai "laporan belum tersedia, bukan nol". Untuk GAP diagnosis bedakan `Rencana < Target` (planning failure) vs `Rencana > Target` tapi `Realisasi < Rencana` (execution failure); buffer `Rencana > Target` memang disengaja untuk serap andil shortfall.
