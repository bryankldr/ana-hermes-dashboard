---
title: Operator Lapangan (directus_users)
created: 2026-10-03
updated: 2026-10-03
type: entity
tags: [operator, wilayah]
sources: [raw/articles/skema-database-kph-bwb-sandbox2.md]
---

# Operator Lapangan (directus_users)

Pengguna aplikasi di lapangan. Setiap baris = satu akun operator dengan cakupan wilayah
(kode_divre/kph/bkph/rph) + peran (`role` → Directus role, `jabatan` → tabel jabatan, `bidang`).

## Skema (32 kolom)

Identitas/auth standar Directus: `id` char(36) PK, first_name, last_name, email, password,
status (`active`/`archived`), token, last_access, last_page. Kolom SIMOGE: `role` char(36) FK
ke directus_roles, `kode_divre/kode_kph/kode_bkph/kode_rph` int unsigned (cakupan wilayah),
`jabatan` int FK ke tabel [[peran-jabatan]], `bidang` int FK (1=SADAPAN, 2=TEBANGAN).

## Fakta snapshot 2026-10-03 (113 users)

- Role dominan: Mandor Sadap 1 (27), KTS 1 (18), Administrator (4), Admin (3), KTS 2 (2),
  KRPH/Mantri + Mandor Sadap 3 + KTS 3 (masing-masing 1). 56 users role NULL.
- Jabatan dominan: M1 MANDOR 1 (27), K1 KTS 1 (18); ADM dan KSS 0 users di snapshot.
- Bidang: 49 SADAPAN, 64 NULL. Status: mayoritas active, sebagian archived.
- Cakupan contoh: Mandor Sadap 1 SUROSO → divre 1, kph 1, bkph 7, rph 5 (kode internal,
  bukan kode_divre publik — interpretasi kode internal butuh engine).

## Relasi TPG

`junction_directus_users_getah_daftar_tpg` (directus_users_id ↔ getah_daftar_tpg_id)
menghubungkan operator ke [[tpg]] yang dikelolanya. `getah_mandor.id_user` menunjuk
ke operator yang bertugas sebagai [[mandor]] di BKPH/RPH tertentu.

## Peringatan

- Kolom `npk` TIDAK ADA di `directus_users` pada snapshot ini. Verifikasi NPK butuh
  kolom yang belum ada di sandbox — jangan asumsikan ada (lihat [[kualitas-data]]).
- `getah_daftar_tpg.npk_online` deprecated, jangan dipakai sebagai identitas operator.
- ANNA tidak query tabel ini langsung; identitas/cakupan operator dibaca via
  Business Data Engine (lihat [[batas-data-engine]]). Halaman ini untuk interpretasi:
  siapa membuat/mengupdate data di wilayah mana (lihat [[peran-jabatan]]).
