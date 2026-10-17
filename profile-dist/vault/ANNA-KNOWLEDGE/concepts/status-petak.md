---
title: Status Petak
created: 2026-10-02
updated: 2026-10-02
type: concept
tags: [petak, interpretasi]
sources: [raw/articles/simoge-business-ontology.md]
---

# Status Petak

Konsep evaluasi kondisi [[petak]]. Status utama: `AKTIF`, `IDLE`, `BONGKOR`.

- **Aktif** — kondisi operasional aktif sesuai business rule berlaku.
- **Idle** — tidak aktif pada periode/kriteria tertentu, belum bongkor.
- **Bongkor** — tidak aktif lebih lama sesuai threshold business rule.

Jangan samakan tanpa cek rule+periode — lihat [[interpretasi-status]] dan [[konteks-waktu]].
