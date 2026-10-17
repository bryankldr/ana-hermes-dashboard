---
title: Uji Laporan Bisnis
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, eksekutif, evidence]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Laporan Bisnis

Bank uji section 19 test suite. Tujuan: kemampuan menghasilkan laporan bisnis lengkap.

Menguji: [[struktur-laporan-eksekutif]], [[aturan-summary-eksekutif]], [[model-insight-bisnis]], [[klasifikasi-fakta]], [[konteks-waktu]], [[presentasi-spasial]].

## Daftar uji (BR001–BR015)

- `BR001` Laporkan kondisi bisnis saat ini.
- `BR002` Laporkan kondisi periode berjalan.
- `BR003` Laporkan kondisi KPH tertentu.
- `BR004` Laporkan kondisi BKPH tertentu.
- `BR005` Laporkan kondisi RPH tertentu.
- `BR006` Laporkan kondisi TPG tertentu.
- `BR007` Buat laporan produksi.
- `BR008` Buat laporan kondisi petak.
- `BR009` Buat laporan aktivitas penyadapan.
- `BR010` Buat laporan produktivitas.
- `BR011` Buat laporan pencapaian target.
- `BR012` Buat laporan dengan peta sebagai pendukung.
- `BR013` Buat laporan lengkap beserta perubahan terhadap periode sebelumnya.
- `BR014` Buat laporan lengkap beserta anomali.
- `BR015` Buat laporan lengkap beserta rekomendasi analisis lanjutan.

## Penilaian

Ikuti [[struktur-laporan-eksekutif]]: ringkasan → KPI → perubahan → perhatian → evidence → batas. BR013 wajib comparison period ([[konteks-waktu]]). BR015 rekomendasi = hipotesis + evidence needed, bukan perintah aksi. Skor dengan [[perilaku-terlarang-dan-penilaian]].
