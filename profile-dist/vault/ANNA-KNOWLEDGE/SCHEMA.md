# Wiki Schema

## Domain
SIMOGE business intelligence — evaluasi penyadapan getah pinus (petak, penyadap, aktivitas, target, produksi, wilayah, spasial). Dialek: Indonesia.

## Conventions
- File names: lowercase, hyphens, no spaces (e.g., `target-achievement.md`)
- Setiap halaman wiki diawali YAML frontmatter
- Gunakan `[[wikilinks]]` antar halaman (minimum 2 outbound links per halaman)
- Saat update halaman, bump tanggal `updated`
- Setiap halaman baru wajib masuk `index.md` di section yang benar
- Setiap aksi wajib append ke `log.md`
- Bahasa isi: Indonesia

## Frontmatter
```yaml
---
title: Judul Halaman
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: entity | concept | comparison | query | summary
tags: [dari taksonomi]
sources: [raw/articles/nama-file.md]
---
```

## Tag Taxonomy
- Org/wilayah: divre, kph, bkph, rph, tpg, wilayah, operator, peran
- Operasional: operasional, penyadap, mandor, andil, petak, aktivitas, rencana, target, produksi
- Spasial: spasial, polygon, peta
- Analitik: kpi, dimensi, measure, interpretasi, diagnostik, eksekutif, tren, komparasi
- Data: integritas-data, evidence, periode, konteks-waktu
- Interaksi: dashboard, chart, intent, konteks-percakapan
- Intent/peta: template, map, spatial, rogojampi, licin, glenmore, jatim, jateng, jabar
- Medan: medan, sintesis
- Evaluasi: uji
- Meta: aturan, pola-nalar, batasan

Rule: setiap tag di halaman harus ada di taksonomi ini. Tag baru → tambah di sini dulu.

## Page Thresholds
- **Buat halaman** bila entitas/konsep muncul di 2+ sumber ATAU sentral di satu sumber
- **Tambah ke halaman lama** bila sumber menyebut hal yang sudah tercakup
- **Jangan buat halaman** untuk singgungan sekali lewat di luar domain
- **Split halaman** bila >200 baris
- **Arsipkan** bila isi sepenuhnya digantikan — pindah ke `_archive/`, hapus dari index

## Entity Pages
Satu halaman per entitas: definisi, atribut konseptual, relasi (`[[wikilinks]]`), dimensi, sumber.

## Concept Pages
Satu halaman per konsep: definisi, aturan pakai, jebakan semantik, konsep terkait (`[[wikilinks]]`).

## Update Policy
Info baru konflik dengan isi lama:
1. Cek tanggal — sumber baru umumnya menggantikan yang lama
2. Bila benar kontradiktif, catat kedua posisi + tanggal + sumber
3. Tandai frontmatter: `contradictions: [nama-halaman]`
4. Flag ke user saat lint
