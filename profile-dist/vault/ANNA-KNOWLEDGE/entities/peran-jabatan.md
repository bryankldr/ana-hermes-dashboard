---
title: Peran dan Jabatan Operasional
created: 2026-10-03
updated: 2026-10-03
type: entity
tags: [peran, wilayah]
sources: [raw/articles/skema-database-kph-bwb-sandbox2.md]
---

# Peran dan Jabatan Operasional

Hierarki peran manusia di organisasi lapangan, dari pimpinan KPH sampai pelaksana.
Dua sistem kode paralel: tabel `jabatan` (14 kode, dipakai kolom `jabatan` di
[[operator-lapangan]]) dan Directus roles (20 role nama panjang, dipakai kolom `role`).

## Hierarki + cakupan (definisi operasional)

- **ADM** (Administratur) — pemimpin [[kph]]. Level tertinggi di lapangan.
- **ASPER** — pemimpin [[bkph]]. **KAUR TK** adalah asisten Asper (role ada, 0 users di snapshot).
- **MANTRI / KRPH** — pengawas di wilayah cakupannya (RPH). Tidak input data harian,
  fungsi kontrol.
- **MANDOR 1–5** (M1–M5) — membuat dan mengupdate data operasional sesuai wilayah
  cakupannya (lihat [[mandor]]). M1 dominan di snapshot (27 users).
- **KTS 1–5** (K1–K5, Pembantu Mandor) — membantu mandor, input/update data di cakupan
  yang sama. K1 dominan (18 users).
- **KSS PRODUKSI** — staf Seksi Produksi tingkat KPH (0 users di snapshot).
- Role tambahan: KKPH, KPH, DIVRE, KANPUS (struktural atas, 0 users), Administrator/Admin (IT).

## Mapping kode jabatan → role (snapshot)

M1↔Mandor Sadap 1 (27), M3↔Mandor Sadap 3 (1), K1↔KTS 1 (18), K2↔KTS 2 (2),
K3↔KTS 3 (1), MANTRI↔KRPH/Mantri (1), ASPER↔KBKPH/Asper (1 user di jabatan, 0 di role —
inkonsistensi minor, lihat [[kualitas-data]]). M2/M4/M5, K4/K5, ADM, KSS: 0 users.

## Aturan pakai

- Data operasional (rencana, aktivitas, drum, penerimaan) dibuat/diupdate oleh
  Mandor/KTS **hanya dalam cakupan wilayahnya** (kode_divre/kph/bkph/rph di akun).
  Anomali input di luar cakupan = sinyal [[uji-integritas-data]].
- Mantri/Asper/ADM membaca dan mengawasi, bukan pelaksana input — jangan hitung
  mereka sebagai workforce penyadapan (lihat [[population-awareness]]).
- Semua angka aktivitas tetap dari Business Data Engine (lihat [[batas-data-engine]]);
  halaman ini untuk menafsirkan *siapa* di balik data.
