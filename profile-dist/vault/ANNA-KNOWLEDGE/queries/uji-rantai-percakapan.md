---
title: Uji Rantai Percakapan
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, konteks-percakapan, diagnostik]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Rantai Percakapan

Bank uji section 20 test suite. Tujuan: ANNA mempertahankan konteks lintas giliran — pronomina, elipsis, dan akumulasi scope.

Menguji: [[pronomina-kontekstual]], [[preservasi-konteks]], [[pohon-diagnostik]], [[model-hipotesis]], [[presentasi-spasial]], [[aturan-summary-eksekutif]].

## Chain A — Petak (CH001–CH010)

- `CH001` Tampilkan petak bongkor.
- `CH002` Berapa jumlahnya? (→ jumlah petak bongkor CH001)
- `CH003` Di mana paling banyak? (→ distribusi wilayah petak bongkor)
- `CH004` Drill-down. (→ turun satu level dari konteks CH003)
- `CH005` Cari wilayah penyumbang terbesar.
- `CH006` Tampilkan di peta.
- `CH007` Apa indikator lain yang perlu diperiksa?
- `CH008` Apakah data menunjukkan penyebabnya?
- `CH009` Jika belum, apa hipotesisnya?
- `CH010` Data apa yang diperlukan untuk menguji hipotesis tersebut?

## Chain B — Produksi (CH011–CH020)

- `CH011` Bagaimana produksi bulan ini?
- `CH012` Bandingkan dengan bulan lalu.
- `CH013` Kenapa berubah? (→ diagnostik, bukan verdict)
- `CH014` Cek aktivitas.
- `CH015` Cek penyadap.
- `CH016` Cek produktivitas.
- `CH017` Cek wilayah.
- `CH018` Drill-down ke TPG.
- `CH019` Tampilkan wilayah terkait di peta.
- `CH020` Buat ringkasan analisis.

## Chain C — Eksekutif (CH021–CH030)

- `CH021` Anna, laporkan kondisi KPH saat ini.
- `CH022` Apa masalah utamanya?
- `CH023` Apa buktinya?
- `CH024` Tampilkan di peta.
- `CH025` Drill-down sampai TPG.
- `CH026` Apa yang berubah dibanding periode sebelumnya?
- `CH027` Apa yang membaik?
- `CH028` Apa yang memburuk?
- `CH029` Apa yang belum kita ketahui?
- `CH030` Apa analisis berikutnya yang perlu dilakukan?

## Penilaian

Setiap langkah tanpa subjek eksplisit merujuk ke konteks sebelumnya ([[pronomina-kontekstual]]). CH008/CH009: bedakan fakta vs [[model-hipotesis]]. CH029 wajib dijawab ([[data-hilang]]). Skor dengan [[perilaku-terlarang-dan-penilaian]].
