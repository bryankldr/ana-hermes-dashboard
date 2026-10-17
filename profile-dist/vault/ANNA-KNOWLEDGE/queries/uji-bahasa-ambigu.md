---
title: Uji Bahasa Ambigu
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, intent, konteks-percakapan]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Bahasa Ambigu

Bank uji section 13 test suite. Tujuan: memahami bahasa operator yang tidak formal.

Menguji: [[penanganan-ambigu]], [[klasifikasi-pertanyaan]], [[pronomina-kontekstual]], [[interpretasi-status]].

## Daftar uji (A001–A015)

- `A001` Gimana kondisi petak sekarang?
- `A002` Ada masalah di mana?
- `A003` Yang merah mana?
- `A004` Coba lihat yang bermasalah.
- `A005` Mana yang perlu diperhatikan?
- `A006` Produksi kita gimana?
- `A007` Kok turun?
- `A008` Yang paling parah di mana?
- `A009` TPG mana yang perlu dicek?
- `A010` Coba bandingkan dengan sebelumnya.
- `A011` Tunjukkan yang aneh.
- `A012` Cari yang tidak normal.
- `A013` Ada yang janggal?
- `A014` Fokus yang produktivitasnya rendah.
- `A015` Coba bedah KPH ini.

## Penilaian

Petakan ke intent dulu sebelum jawab ([[penanganan-ambigu]]). "Kok turun" tanpa anteseden = minta klarifikasi ([[pronomina-kontekstual]]). "Parah/aneh/janggal" wajib definisi KPI ([[interpretasi-status]]). Skor dengan [[perilaku-terlarang-dan-penilaian]].
