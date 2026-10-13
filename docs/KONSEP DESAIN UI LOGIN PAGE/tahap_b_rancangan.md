# Tahap B — Rancangan Insight Engine Landing Page

Status: RANCANGAN (belum ada kode). Acuan: Tahap A + `promt_landingpage.md` §6–§11.

## B1. Arsitektur final (adaptasi stack nyata)

```
cron/thread 15 mnt ──▶ insight_build.py ──▶ run() template simoge_db ──▶ validasi
                                                              │
                                    atomic write ▼ (gagal = snapshot lama utuh)
                              .ana_insight.json (git-ignored)
                                                              │
GET /api/landing/insight ──▶ baca file (TANPA query) ──▶ 3 kartu
     │ kompat: bentuk lama {petak,aktivitas,series,wilayah} TETAP
     │ baru: cards[3] {domain, title, metric_label, value, unit,
     │       change_percent, summary, period, calculated_at,
     │       freshness, status, metric_version}
```

Keputusan arsitektur (menyimpang dari prompt, beralasan):
1. **Tanpa Query Planner/Executor baru.** `simoge_db.q()` sudah: read-only guard
   (regex FORBIDDEN + SELECT-only), parameterized, timeout via pymysql
   (`connect_timeout=10`, `read_timeout=60`), `period_bounds()` P1/P2,
   `DictCursor`, `elapsed_ms` per query. Planner = pilihan template eksplisit
   per domain di `insight_build.py` (dict, bukan AI). Executor = `run()`.
   Membuat planner kedua = duplikasi yang prompt §5 sendiri larang.
2. **Tanpa tabel snapshot baru.** Prompt §9 izinkan "mekanisme cache sesuai
   infrastruktur". File JSON atomik (`tmp+rename`) cukup: single-proses,
   single-writer, restart = baca file lama (stale tapi valid) — tanpa migrasi DB.
3. **Scheduler = thread di proses server** (interval config `ANA_INSIGHT_MIN=15`),
   file-lock anti-bersamaan, gagal satu domain ≠ gagal semua. Tanpa asumsi
   multi-worker (server single-proses; cron sistem opsional Tahap C).
4. **API tetap 1 endpoint lama** + field `cards` ditambah. Frontend lama baca
   field lama (kompat), frontend baru baca `cards`. Tanpa putus yang jalan.

## B2. Katalog metrik awal (1 per domain, lolos Tahap A)

| # | metric_key v1 | domain | definisi | template | satuan | freshness_rule |
|---|---|---|---|---|---|---|
| 1 | `prod_ytd_kg` | production | Σ berat_penerimaan Jan–sekarang | `produksi_year_to_date` | kg | stale bila MAX(tanggal) > 21 hari |
| 2 | `aktiv_cur_prev` | field_ops | COUNT sadap periode berjalan vs lalu + distinct petak/penyadap | `aktivitas_trend` (baris 2 periode) + `aktivitas_agregat` | aktivitas | stale bila MAX(tgl) > 14 hari |
| 3 | `supply_recon` | supply | Σ perni vs Σ angkut YTD + n dokumen | query baru (lihat B3) | kg | stale bila keduanya > 21 hari |

`metric_version`: `"v1-20261013"`.

Yang SENGAJA nonaktif di v1 (gap jujur, bukan tebakan):
- `prod_vs_target_pct` — `rkap_achievement` ada tapi definisi % kumulatif per
  divre/kph belum disepakati; butuh validasi bisnis dulu.
- Ranking 5 KPH (`card_insight.md`) — agregat per-wilayah pra-login butuh
  keputusan klasifikasi (lihat B5-Q3).

## B3. Query baru (1 saja, sisanya pakai ulang)

`supply_recon`: 3 SELECT ringan, tanpa join berisiko ganda:
```sql
SELECT COALESCE(SUM(total_berat_pgt),0) AS s, COUNT(*) AS n, MAX(tanggal) AS mx
FROM getah_perni WHERE YEAR(tanggal)=%s
-- sama untuk getah_pengangkutan
```
Selisih = angkut − perni (tanda + aturan bisnis: positif = di jalan/belum
terima). **Anti double-count**: tiap tabel di agregat sendiri-sendiri,
tanpa join (prompt §4 ingatkan join 1-ke-banyak).

## B4. Ranking v1 (minimal, deterministik)

Hard eligibility (gagal satu = kandidat gugur → fallback):
data cukup · freshness lolos · denominator valid (prev>0 untuk %) ·
definisi tervalidasi · klasifikasi publik.

Skor = 100·signifikansi(|%|) + 50·kebaruan + 50·keandalan − 200·(1−confidence).
Satu pemenang per domain. Fallback: ringkasan kondisi ("Produksi YTD …,
data per …") atau "Data … belum diperbarui" — tanpa karangan.

Template teks (id, tanpa narasi bebas):
- naik/turun signifikan (|%|≥10): `"{label} {meningkat|menurun} {x}%"`
- stabil: `"Kondisi {label} relatif stabil"`
- stale: `"Data {label} belum diperbarui (terakhir {tgl})"`

## B5. Tiga keputusan untuk user

- **Q1 — Nama tabel di JSON publik?** Aturan #2 (sumber tampil) vs prompt §11
  (jangan ungkap tabel). Usul: JSON = label ramah (`"DB operasional SIMOGE"`)
  + `metric_version`; nama tabel detail hanya di log server. Frontend kini
  tampilkan `sumber: getah_petak` — diubah ke label ramah.
- **Q2 — Endpoint**: tambah field `cards` di endpoint lama (kompat, usul saya)
  vs endpoint baru `/api/public/landing-insights` ala prompt (frontend lama mati).
- **Q3 — Ranking KPH** (`card_insight.md`): label+angka agregat wilayah di
  kartu publik boleh? (saya condong boleh — agregat BKPH/RPH/TPG sudah tampil
  kini; angka per-penyadap tetap dilarang).

## B6. Rencana Tahap C (setelah Q1–Q3 dijawab)

Keputusan user (clarify 2026-10-13): Q1 label ramah + versi · Q2 endpoint baru
· Q3 ranking wilayah boleh (agregat saja).

## B7. Hasil Tahap C+D+E (SELESAI 2026-10-13)

- `insight_build.py` (baru): katalog v1 3 metrik → run() template simoge_db
  (tanpa query mentah sendiri kecuali 2 agregat supply anti-join-ganda) →
  eligibility (freshness 21/14/21 hari) → ranking → template teks →
  snapshot atomik `.ana_insight.json` (git-ignored). Tanpa LLM.
- `server.py`: `import insight_build` + scheduler thread 15 mnt
  (`ANA_INSIGHT_MIN`, file-lock, gagal = warn + snapshot lama) +
  `GET /api/public/landing-insights` (publik, rate-limit ikut landing,
  baca file tanpa query, kosong = 503). Endpoint lama utuh (kompat).
- Frontend: kartu 2 = produksi (judul + badge + summary + ranking BKPH 5 +
  ver-tag), kartu 3 = supply (judul + badge kg + summary perni vs angkut +
  ver-tag), info lapangan disisip di kartu produksi. XSS: textContent +
  createElement (tanpa innerHTML data).
- Hasil nyata: produksi STALE (terakhir 2026-08-27, YTD 1.200.516 kg) ·
  lapangan STALE (2026-09-27, 0 aktivitas) · supply VALID
  (perni 961.331 vs angkut 1.033.053, selisih 71.722). Ranking: GLENMORE
  468.643 … LICIN 89.949. Angka = query manual SAMA.
- Uji §14: pct-nol → None · fresh batas benar · 4 pola template benar ·
  publish atomik · deterministik (2x build identik) · auth regresi 401 ·
  smoke 4 gagal bawaan · screenshot 1440 penuh terisi.
- `v=20261013f`, cache `ana-v10-insight-c`.
- Keterbatasan jujur: definisi target-% per periode belum disepakati
  (rkap_achievement ada tapi % kumulatif butuh validasi bisnis) · indeks
  `tanggal` 3 tabel supply belum ada (full scan 25rb, lolos via cache) ·
  read-only DB user belum ada · ranking KPH diganti BKPH (KPH cuma 1 baris).

## B8. v3 — cron 06:00 + chart + rotasi mendalam (SELESAI 2026-10-13)

- Kalkulasi: cron `0 6 * * *` (`scripts/rebuild_insight_daily.sh`,
  marker `ana-insight-daily`, AKTIF via `/api/insight/cron`) → snapshot;
  thread = fallback 6 jam bila cron off.
- Produksi: capaian % vs target kumulatif (34,2% = 1.200.516/3.514.400) +
  ranking + tren + efisiensi; supply: terima→perni→angkut + efisiensi
  (cabang stale ikut sertakan angka — cacat "0 terima" diperbaiki);
  news = optimasi bongkor dinamis (267 petak; GROUP BY naik divre otomatis);
  strip bawah = tren produksi seluruh KPH 12 bulan (fallback 1 KPH).
- Chart SVG tanpa dependensi (line/bar/hbar/donut + palet 9 warna);
  kartu fixed 340px + fade 0,45 dtk + dots; teks pendek (headline ≤48,
  sub ≤110); tiap card + snapshot bawa data_terbaru; live refresh 60 dtk
  (ganti DOM hanya bila generated_at berubah).
- Pandas untuk MA + anomali (fallback Python murni).
+- `v=20261013i`, cache `ana-v13-insight-v3`. Verifikasi: PY/JS/SW/BRACES OK,
+  served=disk, auth 401, smoke 4 bawaan, screenshot 1440 penuh terisi.
+
+## B9. v4 — komposisi 50/50 + peta nyata + rencana + korelasi (SELESAI 2026-10-13)
+
+- Komposisi tiap slide: 50% chart kiri + 50% teks kanan (grid 2 kolom;
+  <480px menumpuk). Tiap card ≥5 slides, tiap slide wajib bawa chart.
+  Teks dipadatkan (headline ≤40, sub ≤90); ranking ≤3 + "+N wilayah lain".
+- Bar optimalisasi: label nilai di ujung bar + grid tipis + sumbu dasar.
+- News: foto diganti PETA SCATTER nyata 266 titik (centroid polygon
+  dihitung cron, snapshot +44KB, hover = nama + luas). Ringan, tanpa foto.
+- Supply: tren bulanan 3-seri (terima/perni/angkut) + efisiensi ber-chart.
+  Domain RENCANA digabung ke kartu ALIRAN (switch otomatis via rotasi):
+  rencana_berat vs target per periode + realisasi rencana→aktivitas 97%.
+- Strip bawah: switch otomatis tren ⇄ korelasi tiap 12 dtk. Korelasi
+  Pearson rencana→aktivitas→penerimaan: 0,98 / 0,96 / 0,96 (selaras kuat).
+- Akurasi skema terverifikasi: RO persen = bobot kumulatif 115/107
+  (bukan target kg); id_rencana cocok 97%; polygon join 809/810;
+  bongkor 267; target via _target_pct skalar (tanpa ganda polygon).
+- `v=20261013j`, cache `ana-v14-insight-v4`. Verifikasi: PY/JS/SW/BRACES OK,
+  5 kartu × ≥5 slides semua ber-chart, DOM 266 circle, screenshot 2 waktu
+  (slide peta + slide ranking/korelasi), auth 401, smoke 4 bawaan.
+
+## B10. v4.1 — chart atas / teks bawah + tanpa angka ganda (SELESAI 2026-10-13)
+
+- Layout slide: chart ATAS (150px) + teks BAWAH, flex kolom 50:50.
+- Slide ranking: headline tanpa angka ("GLENMORE memimpin"), detail di
+  chart (label nilai "468,6 rb" di ujung bar hbar). Slide pencapaian pun
+  diringkas ("Target tercapai — angka di chart").
+- Bar hbar: 82% area + label nilai pendek (jt/rb) agar seimbang vs teks.
+- Domain bersih: teks lapangan `insFieldExtra` yang nyasar di kartu
+  produksi dicabut total (variabel `fld` dibuang).
+- `v=20261013k`, cache `ana-v15-insight-v41`. Screenshot: komposisi
+  atas-bawah benar, bar proporsional, teks nyasar hilang.
+
+## B11. v4.4 — bar chart bermakna + koreksi bisnis (SELESAI 2026-10-13)
+
+- Batang penuh: kolom label 30% ramping + 95% sisa untuk bar; batang
+  tebal (82% slot, min 5px); label nilai dijepit dalam viewBox.
+- Satu warna hijau konsisten (#059669); emas (#D97706) hanya untuk
+  peringkat 1 / sorotan; abu (#CBD5E1) untuk sisa/susut. Pelangi dibuang.
+- Semua chart pemeringkatan sudah urut besar→kecil dari engine (spots,
+  ranking, korelasi); skala = max aktual.
+- Koreksi bisnis: angkut (1,03jt) > perni (961rb) karena tarik stok
+  antar-periode (Jan–Feb) — teks "menyusut wajar" diganti; rasio
+  perni→angkut 107,5% dijelaskan jujur; headline puncak "['05']" → "05".
+- `v=20261013o`, cache `ana-v19-insight-v45`. Screenshot: bar penuh,
+  satu warna + sorotan, label di dalam kotak.
+
+## B12. v5 — warna ambang capaian bisnis (SELESAI 2026-10-13)
+
+- Aturan warna: merah 0–50 · kuning 51–75 · oranye 76–99 ·
+  hijau 100–110 · biru ≥111. Berlaku di chart capaian (hbar ranking,
+  bar capaian, line rencana) + badge + headline teks.
+- Terrealisasi: bar Realisasi MERAH (34,2%), headline "Belum tercapai"
+  merah; ranking 3 wilayah merah; rencana 35,2% merah; 266 titik peta
+  merah + legenda 5 ambang di dalam bingkai.
+- Netral dipertahankan di tempat yang bukan capaian: sisa/susut abu,
+  alur volume + korelasi hijau, komposisi/donut pelangi kategori.
+- Koreksi bisnis terverifikasi: stok TPG 239.185 kg; angkut > perni
+  (+71.722) = tarik stok — bukan "mengurangi persediaan".
+- `v=20261013q`, cache `ana-v21-insight-v5b`. Screenshot: bar merah
+  + headline merah + peta merah + legenda tampil; auth 401, smoke bawaan.
+
+## B13. v5.1 — header + logo form + backsound hening (SELESAI 2026-10-13)
+
+- Header: span teks "Perhutani" HTML dibuang (logo gambar utuh tak
+  disentuh — tanpa crop). Form login: logo.png → simoge_hero_2.png
+  (64px, contain, radius 10).
+- Backsound gagal (file hilang/offline/ditolak) = hening total: tanpa
+  pesan error di form login, toggle ikut OFF + persist ana_sound=0.
+  Autoplay-diblokir tetap tunggu gestur pertama (bukan error).
+- `v=20261013s`, cache `ana-v22-ui-sound`. Screenshot: header logo
+  utuh, form logo hero_2, form bersih; JS/CSS served=disk, auth 401.
+
+## B14. v5.2 — logo hero_1 + tren jujur (SELESAI 2026-10-13)
+
+- Form login: simoge_hero_2 → simoge_hero_1, 64→76px (max 260px).
+- Audit tren PRODUKSI: klaim "Tren stabil" SALAH — data Jan 226rb →
+  Agu 18rb → Sep-Des NOL (std 91rb). Penyebab: "tanpa anomali 2-sigma"
+  disamakan "stabil" padahal ambang tak tersentuh saat seri ikut jatuh.
+- Perbaikan: arah tren = rata-rata 3 bln akhir berisi data vs 3 bln awal;
+  kini "Tren turun 46,0%" + sub "Ekor nol = data tertunda". Klaim
+  "stabil" lain di snapshot = nihil. Variabel anomali tak terpakai dibuang.
+- `v=20261013t`, cache `ana-v23-logo-tren`. Screenshot: logo besar,
+  tren turun sesuai chart; smoke bawaan, auth 401.
+
+## B15. v5.3 — papan skor hero + ikon app + backsound tahan-gagal (SELESAI 2026-10-13)
+
+- Scoreboard GLOBAL di hero kanan (cron, bukan live-query): YTD +
+  P1/P2 + HARI INI. Nilai Ton 2 desimal dominan 19px tabular center;
+  header ringkas YTD/P1/P2/HARI INI; tint opaque rata 1:1 ambang engine
+  (alpha di atas bg gelap = kartu gelap tak terbaca, diperbaiki).
+- Nol = "tertunda + terbaru 2026-08-27" (jujur, bukan 0 produksi).
+  Periode/half/tahun dari snapshot aktual (tanpa hardcode tahun).
+- Mobile: skor vertikal penuh + login langsung di bawah hero
+  (#kphStrip order 5, quick 6). Typo VERIVIKASI → VERIFIKASI.
+- Ikon aplikasi = SIMOGE_HUD_1 (ffmpeg 10 file: 16–512 + maskable +
+  favicon.ico); ICON-OK tersaji.
+- Backsound: default ON dipertahankan saat gagal — backoff 30 dtk→10 mnt
+  (bukan auto-OFF); OFF hanya via toggle manual. failCount dideklarasikan.
+- `v=20261013y`, cache `ana-v28-score-1to1`. Scoreboard 1:1 referensi:
+  dark glass card (white/3% + blur 24px + border white/6% + radius 16px
+  + padding 20px), grid 3 kolom gap 16px max-width 520px.
+  Value 36px bold white tabular-nums, header 11px uppercase tracking-wider
+  white/60, subtext 12px white/50.
+  Border-top accent dinamis: YTD #DC2626 (capaian_color), P1 #CA8A04,
+  HARI INI #059669. Mobile stack vertikal full-width di bawah hero.
+  Screenshot desktop lolos; PY/JS/SW/BRACES OK, served=disk, auth 401,
+  smoke bawaan.

1. `insight_build.py` (katalog + kandidat + ranking + template + snapshot atomik).
2. Wire scheduler thread + endpoint baca-snapshot (field lama kompat).
3. Frontend: peta `cards` → 2 kartu + skeleton per-card + `metric_version` kecil.
4. Uji §14 prompt (nol, kosong, denominator-nol, duplikat join, stale, ranking).
5. Indeks `tanggal` 3 tabel supply (sebelum klaim produksi) + dokumentasi.
