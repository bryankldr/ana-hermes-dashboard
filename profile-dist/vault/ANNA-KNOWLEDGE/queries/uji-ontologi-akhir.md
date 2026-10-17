---
title: Uji Ontologi Akhir
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, operasional, kpi]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Ontologi Akhir

Bank uji section 21 test suite. Tiga pertanyaan besar yang menguji seluruh model bisnis sekaligus.

Menguji: [[model-mental]], [[pohon-diagnostik]], [[penanganan-ambigu]], [[korelasi-vs-kausasi]], [[klasifikasi-fakta]], [[dimensi-bisnis]].

## ONT001 — Jelaskan model bisnis SIMOGE

Mulai dari struktur wilayah: [[kph]], [[divre]], [[bkph]], [[rph]], [[tpg]], [[penyadap]], [[andil]], [[petak]], [[rencana-aktivitas]], [[aktivitas-penyadapan]], [[target]], [[produksi]], KPI.

Jelaskan: entity, attribute, relationship, dimension, measure, KPI, derived metric. Jangan menyebut nama tabel database kecuali diperlukan.

## ONT002 — "Kenapa produksi KPH ini turun?"

Jelaskan: data apa yang diperlukan, KPI apa yang diperiksa, dimensi apa yang digunakan, hubungan entitas yang relevan, bagaimana drill-down, kapan menggunakan peta, bagaimana membedakan fakta dan hipotesis, bagaimana menghindari kesimpulan kausal yang tidak didukung data.

## ONT003 — "Ada masalah di KPH ini. Cari tahu."

Jika ambigu, jelaskan: apa yang belum diketahui, pertanyaan klarifikasi yang diperlukan, KPI yang mungkin digunakan, bagaimana menentukan scope, bagaimana diagnostic analysis, bagaimana mempresentasikan hasilnya.

## Penilaian

ONT001 memakai [[model-mental]] penuh. ONT002 mengikuti [[pohon-diagnostik]] + [[korelasi-vs-kausasi]]. ONT003 memakai [[penanganan-ambigu]] — klarifikasi dulu, bukan menebak. Skor dengan [[perilaku-terlarang-dan-penilaian]].
