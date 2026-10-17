---
title: Operasi Dashboard
created: 2026-10-03
updated: 2026-10-03
type: concept
tags: [dashboard, intent, batasan]
sources: [raw/articles/simoge-business-ontology.md]
---

# Operasi Dashboard

Pengetahuan operasional `ana-hermes-dashboard` agar ANNA bisa menjelaskan
kondisinya sendiri ke operator. Bukan KPI — ini tentang "apakah alatku hidup".

## Sesi (combo SESI, berbahasa Indonesia)

- Grup: `HARI INI / KEMARIN / MINGGU LALU / LAMA`; tombol `+ BARU`;
  waktu relatif Indonesia (`mnt lalu / jam lalu / baru saja`).
- TTL sliding 1 jam: tiap run selesai me-refresh; idle >1 jam = expired.
  Persist ganda: file `.ana_session` (server) + localStorage (browser).
- Ganti sesi → riwayat dimuat dari export sesi (`user/assistant` saja,
  maks 20). Layar kosong setelah pindah = bug, laporkan.

## Profil

Dashboard jalan di profil Hermes `anna` (vault `anna_brain`) — sesi panel
ini milik profil `anna`, tidak campur profil `ana`. Flag profil harus di
depan subcommand (`hermes --profile anna chat ...`); di belakang = error
`unrecognized arguments: --profile anna` (insiden 2026-10-03, diperbaiki di
`runtime.py`: satu sumber flag di `_hermes_base()`).

## Error umum + cara pulih

| Gejala | Arti | Pulih |
|---|---|---|
| Chat balas usage help (`--continue ... --profile ... unrecognized`) | argumen CLI salah rakit | restart server setelah patch `runtime.py` |
| Panel sesi kosong | store sesi profil tak terbaca | cek `/api/sessions`, restart bila perlu |
| Angka "hari ini" diminta pagi hari | data belum masuk (ramai 12.00–15.00) | jawab via `provenance()`, tawarkan data terakhir |
| Permintaan tahap Pembaharuan 4 | tak ada di DB (hanya 1/2/3) | katakan 0 baris, jangan karang |
| Di luar jangkauan (cuaca, harga pasar) | bukan domain engine | katakan tak bisa, tawarkan yang bisa |

## Batas yang tak bisa ditawar

Tanpa SQL langsung (lihat [[tool-bisnis-anna]]); tanpa karang angka, satuan,
atau sebab-akibat (lihat [[disiplin-evidence]], [[korelasi-vs-kausasi]]).
Data tak cukup → kalimat baku: *"Data yang tersedia belum cukup untuk
menentukan penyebab kondisi tersebut."*

## Berhubungan dengan

[[panel-dashboard]], [[tool-bisnis-anna]], [[batas-data-engine]],
[[preservasi-konteks]], [[semantik-dashboard]].
