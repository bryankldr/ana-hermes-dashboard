---
source: manual (snapshot DB read-only)
ingested: 2026-10-03
sha256: 98e7c82a0e4d2952c85ef5386664ff26ee8cfa9478b3d2e4b4b0bce94a87a7d3
---

# Skema Database kph_bwb_sandbox2 — Snapshot 2026-10-03

> Diekstrak read-only via DESCRIBE + SELECT DISTINCT/COUNT (tanpa modifikasi data).
> Tujuan: pengetahuan deskriptif untuk ANNA — ANNA dilarang eksekusi SQL langsung,
> angka tetap dari Business Data Engine. Skema di sini untuk interpretasi + resolusi intent.

## Ringkasan

- Total tabel: 69 (30 tabel `directus_*` = CMS/auth, 39 tabel domain/aplikasi).
- Fokus SIMOGE getah: 4 master wilayah + 16 tabel operasional getah + 1 tabel polygon + 1 evapot (kosong).
- Tata usaha drum: drum, penerimaan, pengangkutan, perni, pembayaran, bon, rangking.
- Tabel non-getah kosong (0 baris): bidang isi 2 baris definisi saja; daftar_tpk, kayu_klem, koordinat_aktivitas, lmdh, pesanggem, pks, spk, transaksi, ubinan, invoice, office, getah_laporan_petak, getah_rangking, evapot.
- Rentang data: rencana 2025-06-08..2026-10-07; aktivitas 2025-06-12..2026-09-23; drum 2024-01-14..2026-09-24.

## Jumlah baris per tabel domain (2026-10-03)

divre=2, kph=2, bkph=5, rph=11, tpg=42, petak=1608, penyadap=2058, andil=1506,
mandor=32, rencana=14594, aktivitas=20181, target_ro=36, mutu=8, tarif=3,
polygon=1003, drum=35604, penerimaan=24796, angkut=1471, perni=10330,
bayar_drum=10, pembayaran=6, bon=1, pelunasan=2, rangking=0, lap_petak=0, evapot=0.

## Konvensi kolom

- Kunci hierarki: `kode_divre` (int) → `kode_kph` (int) → `kode_bkph` (int) → `kode_rph` (varchar di rph, int di tabel lain — inkonsisten tipe, join hati-hati) → `kode_tpg` (bigint).
- FK aplikasi: kolom `tpg` int(10) unsigned MUL di banyak tabel menunjuk id internal TPG.
- Sinkronisasi offline: `local_id` varchar UNI di rencana/aktivitas/drum/penerimaan/pengangkutan/perni.
- Audit Directus: `user_created/user_updated` char(36), `date_created/date_updated` timestamp, `status` varchar (draft) di tabel master.
- Flag aktif non-getah: `status` tinyint(1) di tpg (1=aktif 37, 0=nonaktif 5), penyadap (1=aktif 1899, 0=159), mandor semua 1.
- Kolom `npk` TIDAK ADA di `directus_users` pada snapshot ini (kolom: id, first_name, last_name, email, password, status, role, token, kode_divre/kph/bkph/rph, jabatan, bidang, ...). Verifikasi NPK via field `npk` butuh kolom yang belum ada di sandbox — jangan asumsikan ada.

## Master wilayah nyata (sandbox)

DIVRE (kode_divre): 1 = JAWA TENGAH, 2 = JAWA TIMUR. Sandbox hanya berisi data DIVRE 2.
KPH (kode_kph): 31210 = BANYUWANGI SELATAN, 31211 = BANYUWANGI BARAT. Data operasional hanya di 31211.
BKPH (kode_bkph): 3121101 LICIN, 3121102 ROGOJAMPI, 3121103 KALISETAIL, 3121104 GLENMORE, 3121105 KALIBARU (semua di KPH 31211).
RPH (kode_rph): 312110101 SUKO, 312110102 LICIN, 312110201 SROYO, 312110202 BAYU, 312110301 SIDOMULYO, 312110302 PURWODADI, 312110401 SUMBERMANGGIS, 312110402 GUNUNGSARI, 312110403 WONOASIH, 312110501 KALIBARU MANIS, 312110502 KRIKILAN.
TPG: 42 baris (39 operasional + 3 dummy "Test TPG" kode 992/993/999 tanpa wilayah). Setiap TPG punya `alias` pendek (contoh: sm1=SUMBERMULYO 1, lc=LICIN, co=CURAH OMBO, sry1=SROYO 1). Daftar lengkap 39 TPG di lampiran bawah.

## Distribusi nilai penting

- getah_petak.jenis_sadap: LANJUT 774, BUKA 7, MATI 17, NULL 810. Kolom `status` (tinyint) semua NULL — status AKTIF/IDLE/BONGKOR tidak tersimpan per baris, dihitung engine.
- 798 dari 1608 petak punya bkph/rph/kph/divre NULL (petak yatim, tak terhubung hierarki). Per BKPH: GLENMORE 289, KALISETAIL 284, LICIN 106, ROGOJAMPI 84, KALIBARU 47.
- getah_mutu (8): PREMIUM 5380, SUPER PREMIUM 5680, MUTU I 5000, MUTU I A 4900, MUTU I B 4500, MUTU II 4000, MUTU II A 4000, MUTU II B 3750 (Rp, kolom harga; komponen alat/penguji/angkutan/insentif per mutu).
- getah_tarif_pikul (3): A (43–60) Rp250, B (26–40) Rp200, C (0–25) Rp150. `tipe_jarak` nyambung ke getah_petak.tipe_jarak + jarak_petak.
- aktivitas: cuaca cerah 15735 / mendung 3889 / hujan 557; akses mudah 14627 / sedang 2820 / sulit 2734. Kolom teknik: quare, semprot_cas, budaya_bersih, kerok, naik_batok, pulung (6 flag tinyint; pulung = baru). Kuantitas pohon per jenis: jml_phn_quare, jml_phn_semprot_cas, jml_phn_bdy_bersih, jml_phn_kerok, jml_phn_naik_batok, jml_phn_pulung (int, pohon tersentuh per jenis per baris aktivitas). Tanggal: tgl_pembaharuan = tanggal kerja pelapor (filter periode P1/P2, dipakai engine), tgl_aktivitas = tanggal aktivitas lapangan (kolom baru, backfill bertahap).
- jabatan (14): ADM, ASPER, MANTRI, KSS PRODUKSI, M1–M5 (MANDOR 1–5), K1–K5 (KTS/PEMBANTU MANDOR 1–5).
- getah_mandor: 32 baris, kolom BKPH/RPH teks bebas + jabatan teks + npk_online + id_user. BUKAN tabel users.
- getah_target_ro_nps: 36 baris = 12 bulan × 3 tahun (2024–2026) untuk KPH 31211; kolom ro, nps, ro_periode_1/2, nps_periode_1/2.
- getah_drum.status_drum: semua NULL (35604). Alur drum dibaca dari nomor_perni + nomor_pengangkutan, bukan flag.
- Drum contoh: nomor_drum 39JAN1241, berat_penerimaan vs berat_tpg vs berat_pgt (susut TPG→PGT, contoh 80→80→79.24).
- Perni contoh: PRNJAN1241, total_berat_pgt; pengangkutan contoh: AKTsm145671 + nopol + skshhbk.

## Skema per tabel (kolom domain, tanpa audit)

- divre: kode_divre UNI int, divre varchar. kph: +kode_kph UNI, divre, kph. bkph: +kode_bkph UNI, divre, kph, bkph. rph: kode_rph varchar UNI, divre, kph, bkph, rph UNI.
- getah_daftar_tpg: kode_tpg bigint UNI, nama_tpg, alias(10), BKPH, RPH, divre/kph teks + kode_*, jarak_pgt decimal, status tinyint, npk_online (deprecated, jangan dipakai).
- getah_petak: nomor_petak, nama_tpg, divre/kph/bkph/rph teks + kode_*, jenis_sadap, luas_baku, rencana_luas, jumlah_pohon, tahun_tanam, target_rkap, target_semangat, jarak_petak, tipe_jarak, tahun_rtt, status NULL, kode_data, kode_evapot, kode_tpg, kode_petak, tpg FK.
- getah_penyadap: nomor_penyadap UNI, KTP, nama_penyadap, tgl_lahir, telpon, alamat, status, id_tpg FK, nama_tpg, wilayah teks+kode_*, tpg FK.
- getah_andil: id_penyadap, nama_penyadap, nama_tpg, nomor_petak, jml_pohon, luas_andil, wilayah teks+kode_*, kode_data/evapot/tpg/petak, tpg FK.
- getah_mandor: npk_online, email, nama, tempat/tanggal_lahir, pensiun, golongan, pangkat, tmt_golongan, stat_job, jabatan, BKPH, RPH, status, id_user.
- getah_rencana_aktivitas: tanggal_rencana, id_penyadap, rencana_berat, local_id UNI, id_rencana UNI, id_andil, keterangan, kode_* wilayah, tpg FK.
- getah_aktivitas_sadap: id_penyadap, pembaharuan_ke, tgl_pembaharuan, tgl_aktivitas, quare/semprot_cas/budaya_bersih/kerok/naik_batok/pulung (6 flag), jml_phn_quare/jml_phn_semprot_cas/jml_phn_bdy_bersih/jml_phn_kerok/jml_phn_naik_batok/jml_phn_pulung (pohon per jenis), lat/long/alt teks, cuaca, akses_lokasi, aktivitas_photo FK, local_id UNI, id_rencana, id_andil, kode_* wilayah, tpg FK, status default 'plan'. Filter periode pakai tgl_pembaharuan (bukan tgl_aktivitas); coverage = MAX(jml_phn_*)/jumlah_pohon, intensitas = SUM(jml_phn_*) terpisah.
- getah_target_ro_nps: bulan, tahun, nps, ro, ro/nps_periode_1/2, kode_divre/kph, divre/kph teks.
- getah_mutu: mutu UNI, harga, alat, penguji, angkutan, insentif.
- getah_tarif_pikul: tipe_jarak UNI, minimum, maximum, tarif.
- petak_polygon (49 kolom,104000+? 1003 baris): kode_data MUL, phw, divre/kph/kp/klmpkhutan/bh/bkph MUL/rph MUL/lmdh/desa/kecamatan/kabupaten/provinsi/das/subdas, petak, luas_ha, polygon longtext, kelas_perusahaan, bagian_hutan, anak_petak, luas_baku, fungsi_hutan, jenis_tanaman, penjelasan, tahun_tanam, umur, bonita, kbd, dkn, kelas_hutan, no_spk, sdp_pinus, kode_* wilayah, kode_tpg/evapot/petak, tpg FK.
- evapot (43 kolom, 0 baris): kode_evapot, kode_data/petak/anak_petak, wilayah teks+kode_*, kelas_perusahaan, kelompok_hutan, bagian_hutan, lmdh/desa/kecamatan/kabupaten/provinsi, petak, anak_petak, luas_baku, fungsi_hutan, jenis_tanaman, umur, n_ha, bonita, kbd, dkn, kelas_hutan, x/y/pht/khdpk koordinat.
- getah_drum: id_penyadap, tanggal, kapasitas, berat_penerimaan/tpg/pgt, status_drum, ka, kk, local_id, nomor_drum, id_mutu_tpg/pgt FK, nomor_perni, nomor_pengangkutan, kode_* wilayah, tpg FK.
- getah_drum_3: seperti drum + id_tpg/id_petak (arsip/varian, 0 baris? berisi? — cek ulang saat pakai).
- getah_drum_getah_mutu: junction getah_drum_id ↔ getah_mutu_id.
- getah_aktivitas_penerimaan: nomor_penerimaan, id_penyadap, berat_penerimaan, local_id, nomor_drum, id_andil, tanggal, kode_* wilayah + evapot, tpg FK.
- getah_pengangkutan: nomor_pengangkutan, tanggal, nopol, total_berat_tpg/pgt, local_id, skshhbk, kode_* wilayah, tpg FK.
- getah_perni: nomor_perni, total_berat_pgt, local_id, nomor_pengangkutan, tanggal, kode_* wilayah, tpg FK.
- getah_bayar_drum2: kode_bayar_drum, total_bayar_drum, kode_pembayaran, id_pembayaran/drum/tpg, nomor_drum.
- getah_pembayaran2: kode_pembayaran, id_perni, tanggal_pembayaran, total_berat_pgt, total_pembayaran.
- getah_bon_penyadap: id_tpg, id_penyadap, tanggal, jumlah, catatan. getah_bon_pelunasan: id_bon, tanggal, jumlah, sumber, nomor_drum, catatan.
- getah_rangking (0 baris): id_tpg, total_penerimaan/re_armasi teks, nama_tpg, mandor_kts.
- bidang: SADAPAN, TB (TEBANGAN). jabatan: 14 kode (detail di bawah + [[peran-jabatan]]).
- directus_users: 113 akun operator lapangan (detail di bawah + [[operator-lapangan]]).

## Operator lapangan — directus_users (32 kolom)

Identitas/auth standar Directus: `id` char(36) PK, first_name, last_name, email, password,
status (`active`/`archived`), token, last_access, last_page. Kolom SIMOGE: `role` char(36) FK
ke directus_roles (20 role), `kode_divre/kode_kph/kode_bkph/kode_rph` int unsigned (cakupan
wilayah akun), `jabatan` int FK ke tabel jabatan, `bidang` int FK (1=SADAPAN, 2=TEBANGAN).
Junction `junction_directus_users_getah_daftar_tpg` (directus_users_id ↔ getah_daftar_tpg_id)
menghubungkan operator ke TPG yang dikelolanya. `getah_mandor.id_user` menunjuk operator
yang bertugas sebagai mandor di BKPH/RPH tertentu.

Snapshot 2026-10-03: role dominan Mandor Sadap 1 (27), KTS 1 (18), Administrator (4),
Admin (3), KTS 2 (2), KRPH/Mantri + Mandor Sadap 3 + KTS 3 (@1); 56 users role NULL.
Bidang 49 SADAPAN / 64 NULL. KRITIS: kolom `npk` TIDAK ADA di snapshot ini — verifikasi
NPK butuh kolom yang belum ada di sandbox, jangan asumsikan ada.

## Jabatan + hierarki peran (14 kode + 20 Directus roles)

Tabel jabatan: 1 ADM, 2 ASPER, 3 MANTRI, 4 KSSPRODUKSI, 5–9 M1–M5 (MANDOR 1–5),
10–14 K1–K5 (KTS/PEMBANTU MANDOR 1–5). Directus roles: Mandor Sadap 1–5, KTS 1–5,
KRPH/Mantri, KBKPH/Asper, KAUR TK, KKPH, KPH, KSS, DIVRE, KANPUS, Administrator, Admin.
Mapping users: M1↔Mandor Sadap 1 (27), K1↔KTS 1 (18), K2↔KTS 2 (2), M3/K3/Mantri/Asper (@1);
M2/M4/M5, K4/K5, ADM, KSS: 0 users. Hierarki operasional: ADM pimpin KPH → Asper pimpin
BKPH (dibantu KAUR TK) → Mantri awasi RPH → Mandor 1–5 + KTS buat/update data operasional
sesuai cakupan wilayah → KSS Produksi staf KPH. Aturan: Mandor/KTS input hanya dalam
cakupan wilayah akunnya; Mantri/Asper/ADM pengawas/pimpinan, bukan workforce sadap.

## Lampiran: 39 TPG operasional (BKPH → RPH → kode_tpg → nama [alias])

LICIN → SUKO(SOKO di data): 31211010101 PALPAKIS[pp], 31211010102 TELEMUNG[ttl], 31211010103 SUKO[tsk]; → LICIN: 31211010201 LICIN[lc].
ROGOJAMPI → SROYO: 31211020102 SROYO 1[sry1], 31211020103 SROYO 2[sry2]; → BAYU: 31211020201 BAYU[by].
KALISETAIL → SIDOMULYO: WATU GEDEK[wg], BAMBUSA[bs], PARAS TEMBOK[pt], AIR TERJUN[at], SELING[slg], LATENG[lt], GUBUK PAYUNG[gp] (31211030101–07); → PURWODADI: LIDER[ldr], WATU TULIS I[wt1], SURAU[su], SRAGI II[sr2], TOJO[tj], SRAGI I[sr1], WATU TULIS II[wt2] (31211030201–07).
GLENMORE → SUMBERMANGGIS: 45 SUMBERMULYO 1[sm1], 31211040101 SUMBERMULYO[SM], PANGGUNG REJO 1[pg1], COKLAK[ck], KALONGAN[kl], PANGGUNG REJO 2[pg2], SUMBERMULYO 2[sm2], TEMPUSARI[ttp] (31211040101–07); → GUNUNGSARI: CURAH OMBO[co], CURAH LANDAK[cl], KUCUR[ku], BENDOGROWONG[bg]; → WONOASIH: GUMUK KANCIL[gk], DURENAN[dr], ONTOBUGO[ob], SENDANG GAPIT[sg].
KALIBARU → KALIBARU MANIS: 31211050101 BERINGIN[br]; → KRIKILAN: 31211050201 RAUNG[rg].
