---
title: LAPORAN BISNIS (dokumen multi halaman)
created: 2026-10-04
updated: 2026-10-04
type: concept
tags: [dashboard, spasial, laporan, presentasi, evidence, cetak, periode]
sources: [entities/panel-spatial-map.md, concepts/presentasi-chart.md, concepts/struktur-laporan-eksekutif.md]
---

# LAPORAN BISNIS — dokumen multi halaman siap cetak

Panel `#spatialReportWrap` di dalam `#mapPanel` (tambahan di
[panel-spatial-map](panel-spatial-map.md)). Berbeda dari chart box: chart = satu box
visual, laporan = N halaman dokumen layak cetak. ANNA kontrol penuh lewat session state
`/api/spatial/report`.

[[presentasi-chart]] untuk grafik satu pertanyaan. Laporan dipakai saat user minta
dokumen: 13-section eksekutif, tren bulanan, perbandingan wilayah. Lihat
[[struktur-laporan-eksekutif]] untuk isi 13 section, dan
[[contoh-laporan-eksekutif-kph-barat]] + [[contoh-laporan-tren-bulanan]] sebagai
golden example isi.

## Aturan nama (jangan pakai "canvas")

Pakai **LAPORAN**. "Canvas" sudah dipakai Chart.js `<canvas>` di chart panel — operator
dan intent router akan mencampur "canvas laporan" dengan "chart canvas".

## Kontrak state

```
{ visible, title, subtitle,
  pages: [ { title, subtitle, blocks: [...] } ],   # satu item = satu halaman A4
  evidence: [ { statement, source, value } ],
  meta: { periode, source },
  updated: epoch }
```

Block type yang sah: `para`, `note`, `list`, `kpi`, `table`.

| Block | Isi | Untuk |
|---|---|---|
| `para` | `text` | interpretasi dan narasi |
| `note` | `text` | batasan data, sumber, catatan kejujuran |
| `list` | `items[]` | rencana aksi atau temuan |
| `kpi` | `items[]{label,value,unit,sub,tone}` | angka utama; `tone` good/warn/bad |
| `table` | `title`, `columns[]`, `rows[][]` | detail per wilayah atau per periode |

## Kenapa tidak chart di dalam laporan

Chart.js menggambar ke `<canvas>`. Canvas tidak tercetak rapi ke PDF: bitmap tanpa teks
yang bisa diseleksi, dan satu halaman bisa terpotong antar halaman. Jadi angka laporan
wajib lewat `kpi` dan `table`. Kalau butuh visual, taruh chart di chart panel lalu rujuk
nilainya di paragraf laporan sebagai FACT.

## Alur buka/tutup (wajib, aturan user 2026-10-04)

User minta tampilkan laporan:

1. `get_report()` — cek `visible`.
2. `visible == true` → `hide_report()` dulu (tutup bersih), lalu `show_report(isi_baru)`.
3. `visible == false` → langsung `show_report(isi_baru)`.
4. `show_report()` selalu menimpa seluruh state, bukan menambah halaman.

`show_report()` tanpa `hide_report()` juga aman secara visual, tapi user meminta eksplisit
tutup-lalu-buka supaya tidak tampak bertumpuk — ikuti urutan di atas.

## Tombol di panel

| Tombol | Aksi | Konsekuensi ke state |
|---|---|---|
| `Unduh` | `window.print()` + `body.rpt-printing` | state tidak berubah; PDF keluar lewat dialog browser |
| `Tutup` | `POST {visible:false, pages:[]}` | `get_report()` berikutnya melaporkan `visible:false` |

CSS `@media print`: `#hud > *:not(#mapPanel)` dan saudara lain disembunyikan, `.rpt-page`
jadi putih-hitam dengan `break-after: page`. Jadi seluruh panel tidak ikut tercetak walau
user menekan Ctrl+P langsung.

## Batasan

- Session memory, tidak persist. Restart server → isi hilang (sama seperti chart box).
- Tanpa asset gambar. Kalau butuh logo KPH, catat di `meta`, jangan sisipkan path gambar.
- Halaman panjang tetap bisa di-scroll di layar; pemecahan halaman hanya berlaku saat
  `@media print`.