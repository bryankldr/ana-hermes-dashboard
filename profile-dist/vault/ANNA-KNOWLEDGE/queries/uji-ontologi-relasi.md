---
title: Uji Ontologi dan Relasi
created: 2026-10-02
updated: 2026-10-02
type: query
tags: [uji, operasional]
sources: [raw/articles/bi-semantic-test-suite.md]
---

# Uji Ontologi dan Relasi

Bank uji section 3 test suite. Tujuan: pemahaman hubungan antar-entitas, bukan sekadar nama data.

Menguji: [[penyadap]], [[andil]], [[petak]], [[aktivitas-penyadapan]], [[rencana-aktivitas]], [[distingsi-semantik-kritis]], [[model-mental]].

## Daftar uji (O001–O015)

- `O001` Jika satu penyadap memiliki beberapa andil, bagaimana hubungan datanya?
- `O002` Jika satu petak memiliki beberapa andil, apa artinya?
- `O003` Jika satu petak memiliki dua penyadap, apakah berarti ada dua petak?
- `O004` Jika seorang penyadap memiliki tiga andil pada petak berbeda, bagaimana menghitung jumlah petaknya?
- `O005` Apa perbedaan jumlah penyadap dengan jumlah andil?
- `O006` Apa perbedaan jumlah andil dengan jumlah petak?
- `O007` Jika jumlah andil lebih besar daripada jumlah petak, apakah itu otomatis masalah?
- `O008` Jika sebuah petak tidak memiliki penyadap tetapi memiliki andil, apa yang perlu diperiksa?
- `O009` Jika penyadap tidak memiliki aktivitas pada periode ini, apakah otomatis tidak aktif?
- `O010` Apakah petak bongkor berarti tidak memiliki penyadap?
- `O011` Apakah petak yang memiliki penyadap pasti memiliki aktivitas?
- `O012` Apakah satu aktivitas berarti satu penyadap?
- `O013` Apakah satu rencana aktivitas dapat memiliki lebih dari satu aktivitas?
- `O014` Mengapa jumlah aktivitas tidak selalu sama dengan jumlah penyadap?
- `O015` Jika jumlah penyadap naik tetapi jumlah petak aktif tetap, apa kemungkinan penjelasannya?

## Penilaian

Kunci: jangan samakan entity berbeda ([[distingsi-semantik-kritis]]). O015 dan jawaban "kemungkinan" adalah hipotesis, bukan fakta — lihat [[model-hipotesis]]. Skor dengan [[perilaku-terlarang-dan-penilaian]].
