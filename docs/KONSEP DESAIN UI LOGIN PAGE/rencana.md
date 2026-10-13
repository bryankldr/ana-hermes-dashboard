# Rencana Implementasi — Konsep Desain UI Login Page

**Sumber konsep:** `konsep_landing_page.md` v1.0 + mockup `SIMOGE HUD Forest Dashboard Login.png`
**Kode kini:** `ui/login.html` + `ui/login.css?v=20261012a` + `ui/login.js?v=20261011a`
**Status:** RENCANA — belum ada kode diubah. Dokumen ini konsep + tahapan saja.

**DUA ATURAN KERAS USER (mengikat semua tahap, tak bisa ditawar):**
1. **Metode login NOL ubah** — `login.js` + endpoint `/api/auth/*` + sesi + OTP/QR/enroll +
   evict + device header + redirect `next` tetap byte-per-beda-perilaku. Yang boleh
   ditambah di kulit: toggle lihat password (murni DOM `type`), ingat-email
   (localStorage, bukan password/token), indikator loading (sudah ada pola
   `MEMPROSES…`). Tanpa backend auth baru, tanpa endpoint reset/SSO aktif.
2. **Semua yang tampil di landing = DATA NYATA dari `kph_bwb_sandbox2`, bukan karangan.**
   Inventaris nyata (2026-10-12): `getah_petak` 1608, `getah_aktivitas_sadap` 20184,
   `getah_daftar_tpg` 42, `bkph` 5, `rph` 11, `kph` 2, `divre` 2, `directus_users` 113.
   Konsekuensi: TAK ADA JSON kurasi manual, TAK ADA label "contoh", TAK ADA angka
   hardcode. Slot kosong/datanya belum ada = kartu DISEMBUNYIKAN, bukan diisi dummy.
   Setiap angka tampil WAJIB bawa `periode + sumber tabel + waktu query`.
   Berita/feed editorial (START/NEWS/FEED/...) dari mockup DITUNDA sampai ada tabel
   sumber nyata — navigasi tampil HANYA untuk kanal yang datanya ada, sisanya tak
   dirender sama sekali (bukan disabled pajangan).
**Batasan ruang lingkup (dari §Batasan dokumen konsep):** gaya Modern Editorial × Forest-Tech
HANYA untuk halaman pra-login. Dashboard, Anna, Spatial Map, panel internal TIDAK tersentuh.

---

## 1. Ringkasan konsep (apa yang diminta dokumen)

- **Gaya:** Modern Editorial × Forest-Tech — terang (Warm White), bukan Command Center gelap.
- **Layout:** split 2 kolom — kiri showcase (branding + headline + nav editorial + 3 kartu
  insight + quick access), kanan kartu login kaca (glassmorphism putih).
- **Auth card:** username/email + password + show/hide + ingat saya + lupa password +
  tombol Masuk gradien hijau + divider + SSO Perhutani + indikator proses + pesan jelas.
- **Insight:** data aktual dari sumber sah; kosong = sembunyi; tiap angka bawa
  periode + sumber + waktu query. Aturan user: tanpa dummy, tanpa hardcode.
- **Nav editorial:** START, NEWS, FEED, FOR YOU, FOLLOWING, CHANNELS, PUBLISHER.
- **Motion:** parallax subtil, gradient atmosferik, reveal, micro-interaction;
  `transform`/`opacity` saja, hormati `prefers-reduced-motion`.
- **Audio:** MP3 64 kbps, background download prioritas rendah, Cache Storage,
  attempted autoplay, tombol ON/OFF, gagal audio tak ganggu bisnis.
- **Aset audio kini:** `ui/assets/backsound/` (10 file MP3, relatif — sudah benar,
  tanpa path absolut).

## 2. Kondisi kode kini (fakta, bukan opini)

| Aspek | Kini | Catatan |
|---|---|---|
| Layout | Kartu gelap centered 420px, navy + neon cyan (Command Center) | Berlawanan arah visual konsep (terang editorial) — ini gap terbesar |
| Branding | Avatar `anna_forest.png` + "ANA HUD" + badge host sandbox | Mockup minta logo Perhutani + "SIMOGE HUD" + tagline operasional |
| Form | email + password + OTP/TOTP + enroll QR + evict handling | Fungsional dan BENAR — jangan rombak logika, hanya kulit + tambah kecil |
| Show/hide password | TIDAK ADA | Tambah mudah, tanpa backend |
| Ingat saya | TIDAK ADA | Backend sesi HttpOnly TTL; boleh ingat *email* saja di localStorage, jangan password/token |
| Lupa password | TIDAK ADA endpoint reset | Mockup ada link — jadikan "Hubungi admin" (jangan fake reset) |
| SSO Perhutani | TIDAK ADA backend | SEMBUNYIKAN total sampai backend siap (aturan keras #1) |
| Nav editorial / news / feed | TIDAK ADA (backend maupun file) | DITUNDA sampai ada tabel sumber — tanpa JSON kurasi |
| Insight bisnis | TIDAK ADA di login | Butuh endpoint publik agregat non-sensitif + label sumber/periode; gagal = sembunyi, bukan angka bohong |
| Motion | statis; drawer + flags device sudah ada | Tambah reveal/parallax ringan + `prefers-reduced-motion` |
| Audio | Aset ada, player BELUM ADA | Implementasi sesuai §5 dokumen (prioritas paling rendah) |
| A11y/responsive | Viewport-fit + safe-area + tier phone/tablet/desktop + coarse 40px sudah OK | Pertahankan semua; uji ulang pasca-skin |
| PWA/sw.js | Cache login.css/login.js + versi `?v=` | Setiap file baru (landing.css, gambar, audio) WAJIB masuk daftar cache + naik versi |
| Aset gambar | `anna_forest.png`, `SIMOGE_HUD_2.png`, `SIMOG_ HUD_1 .png` (nama ber-spasi — rapikan saat pakai) | Dua SIMOGE_*.png TIDAK cocok jadi background (objek tengah ramai, ada teks) — pakai sebagai ilustrasi samping/hero; background butuh foto hutan gelap-blur ber-overlay (aset belum ada) |
| Theme-color | `#020F2A` (navy) | Ganti ke forest saat skin terang agar chrome HP selaras |

## 3. Keputusan konsep (adaptasi, bukan jiplak mentah)

1. **Tetap satu file `login.html` yang membesar** (bukan route baru). Alasan: alur
   `/` → auth gate → `login.html?next=` sudah benar; route baru = kerja server +
   risiko redirect loop. Showcase + form satu halaman, form terlihat tanpa scroll
   pada 900px+ (split), menumpuk vertikal di tablet/phone.
2. **Kulit terang terisolasi:** file baru `ui/landing.css` khusus login; `tokens.css`
   global hanya tambah token forest bila perlu, JANGAN ubah token navy dashboard.
3. **Logika auth NOL ubah (aturan keras #1):** `login.js` + endpoint + sesi + OTP +
   enroll + evict + device header + redirect `next` tetap. Tambah kulit saja:
   toggle lihat password (DOM `type`), ingat-email (localStorage), loading
   (pola `MEMPROSES…` yang sudah ada). Lupa-password = link "Hubungi admin"
   (tanpa endpoint reset). SSO = SEMBUNYIKAN total sampai backend siap
   (bukan disabled pajangan).
4. **Konten editorial DITUNDA (aturan keras #2):** tanpa tabel sumber di DB =
   tanpa pill nav, tanpa JSON kurasi, tanpa label "contoh". Tampil hanya yang
   datanya ADA (aturan di header dokumen).
5. **Insight = agregat nyata saja (aturan keras #2):** 3 indeks terdefinisi di
   Tahap 4 (petak aktif, aktivitas + tren, cakupan wilayah). Respons bawa
   `{periode, sumber, generated_at}`; gagal = sembunyi, bukan 0. Pra-login tak
   ada scope user — data per-user/wilayah sensitif DILARANG tampil.
6. **Audio paling akhir**, gagal total tak boleh blokir login (fetch + decode di
   try/catch, default OFF bila autoplay ditolak dan jangan spam retry).

## 4. Tahapan (urut, satu tahap = satu verifikasi)

### Tahap 0 — Persiapan aset (tanpa sentuh halaman)
- Pilih/rapikan gambar: rename `SIMOG_ HUD_1 .png` (spasi = URL rapuh), kompres
  background forest bila ada (target <300 KB, blur via CSS bukan file ganda).
- Daftarkan SEMUA file baru ke `sw.js` + siapkan nomor `?v=` berikutnya.
- Verifikasi: `ls` aset, tak ada referensi kode berubah.
- Rollback: tak perlu (belum ada perubahan kode).

### Tahap 1 — Foundation terang (`landing.css` + token)
- Token forest (green/teal/sage/warm-white/charcoal) di `tokens.css` TANPA ubah
  token navy lama; `login.css` import `landing.css` baru.
- Tipografi headline + spacing editorial + focus-visible keyboard jelas.
- Verifikasi: `node --check login.js` (tak berubah), screenshot 390/820/1440 vs kini —
  struktur sama, warna mulai terang. `?v=` naik.
- Rollback: kembalikan `?v=` + hapus import (satu baris).

### Tahap 2 — Split layout + auth card baru (tanpa ubah logika)
- `login.html`: kolom kiri showcase (logo, headline 2-warna, sub, pill nav STATIS
  tahap ini, 3 kartu insight sebagai slot kosong berlabel), kanan form (id/class/input
  untuk `login.js` TETAP: `loginForm/email/password/otp/btnLogin/...`).
- Tambah: toggle lihat password, checkbox ingat-email (localStorage), link lupa → admin,
  tombol SSO disabled + tooltip alasan.
- Tablet/phone: menumpuk (form dulu, showcase ringkas di bawah), header showcase ciut.
- Verifikasi: login sukses + OTP + enroll QR + evict + redirect `next` tetap hijau
  (uji ulang penuh — markup form berubah); screenshot 3 tier; keyboard-only full flow.
- Rollback: revert `login.html`+css (`login.js` tak tersentuh).

### Tahap 3 — Navigasi editorial DITUNDA (data nyata belum ada) — DINGIN
- Status: TIDAK dikerjakan sampai ada tabel sumber konten di DB. Pill nav mockup
  (START/NEWS/FEED/...) tak dirender — bukan JSON kurasi, bukan disabled.
- Bila kelak ada tabel (mis. pengumuman operasional): endpoint GET publik agregat,
  item tampil hanya bila baris ADA; kosong = pill hilang total.
- Verifikasi: tak ada request konten, tak ada kode mati.

### Tahap 4 — Insight agregat nyata (3 indeks terdefinisi, query langsung)
- Indeks (nama, query, satuan — DITULIS dulu, baru kode):
  1. **Total petak aktif** — `COUNT(DISTINCT kode_evapot) FROM getah_petak
     WHERE tahun_rtt=<berjalan>` + label `sumber: getah_petak · <waktu>`.
  2. **Aktivitas periode berjalan** — `COUNT(*) FROM getah_aktivitas_sadap
     WHERE tgl BETWEEN <P1/P2 berjalan>` + tren vs periode lalu (`±x%`,
     dihitung DUA query, bukan karangan).
  3. **Cakupan wilayah** — `COUNT bkph/rph/tpg` dari tabel wilayah
     (`5 BKPH · 11 RPH · 42 TPG`) + label sumber.
- Endpoint GET publik BARU, rate-limited, agregat saja (tanpa baris per-user,
  tanpa data wilayah sensitif — pra-login tak ada scope). Respons SELALU bawa
  `{periode, sumber, generated_at}`; query gagal = kartu SEMBUNYI (bukan 0 bohong).
- Mini chart tren: SVG ringan dari deret agregat nyata (mis. aktivitas 6 periode
  terakhir, 6 query COUNT) — tanpa dependensi baru.
- Verifikasi: angka di layar = hasil query manual SAMA (bandingkan via mysql);
  matikan DB → kartu hilang, login tetap OK.
- Rollback: hapus section (auth tak tergantung endpoint ini).

### Tahap 5 — Motion ringan + a11y pass
- Reveal on scroll (IntersectionObserver), parallax hero `transform` saja,
  `prefers-reduced-motion` mematikan semua; kontras teks minimal 4.5:1; fokus jelas.
- Verifikasi: tab background tak makan CPU (profil 10 dtk), keyboard penuh, screenshot.

### Tahap 6 — Audio cache (prioritas terakhir)
- Fetch MP3 latar (prioritas rendah, setelah `load`), Cache Storage berversi,
  attempted autoplay → fallback tombol ON/OFF; OFF sesi ini = tak coba lagi.
- Verifikasi: blokir file audio (offline) → login 100% normal; hapus cache → unduh ulang.
- Rollback: hapus script audio (satu file + satu tombol).

### Tahap 7 — Validasi akhir
- Matriks: 390/820/1180/1440 + rotasi + keyboard tablet + coarse-touch 40px.
- Auth regresi penuh (login/OTP/enroll/evict/rate-limit 429).
- Smoke 122 (4 gagal bawaan yang sudah diketahui, bukan regresi).
- Kriteria §10 dokumen konsep dicentang satu per satu di sini.

## 5. Risiko + mitigasi

| Risiko | Mitigasi |
|---|---|
| Skin terang merusak dashboard | CSS terisolasi `landing.css`; token navy tak diubah; kriteria §Batasan ruang lingkup dicek per tahap |
| ID form berubah → `login.js` mati | ID auth dikunci (daftar di Tahap 2); uji auth tiap tahap, bukan akhir |
| Insight publik bocorkan data sensitif | Agregat non-sensitif + label sumber; review query sebelum serve |
| SSO/lupa-password jadi tombol mati | Placeholder jujur (disabled + alasan / link admin) |
| Gambar 1–2 MB perlambat login | Kompres + lazy + tak blokir render; audio setelah `load` |
| Cache basi (SW cache-first) | `?v=` naik tiap tahap + nama CACHE SW baru; verifikasi served=disk via curl |
| Mockup terang vs brand navy ANA | Disengaja per dokumen v1.0; theme-color + badge host menjaga identitas |

## 6. Kriteria selesai (salin dari §10 + §4 ruang lingkup, centang saat eksekusi)

**Status eksekusi 2026-10-13 (SELESAI — replika 1:1 dark, tanpa SSO):**
- Struktur: header brand + sound toggle · hero + LIVE badge · 7 tab pills ·
  3 kartu (berita statis + tren nyata + wilayah nyata) · quick-access + motto ·
  kartu login putih · footer status. ID auth 10/10 ada, SSO nol di HTML+JS.
- Tahap 5: reveal `.ref-reveal` + parallax rAF-throttle + reduced-motion.
- Tahap 6: backsound lokal `assets/backsound/35433346-promo-logo-152894.mp3`
  (414 KB, serve 200 audio/mpeg), toggle header default MATI, precache SW.
  Gagal audio = pesan, login tetap jalan.
- Tahap 7: smoke 118/122 (4 gagal bawaan: voices keys + 3 open-tanpa-token 401 —
  server auth tak tersentuh rangkaian ini). Screenshot 1440/820/390 OK.
  Regresi login salah-pwd → 401 "email atau password salah". Served=disk.
  Cache `ana-v6-dark-motion-audio`, `landing.css?v=20261013c`,
  `login.js?v=20261013b`, `sw.js?v=20261013b`.
- Sisa 2026-10-13: theme-color → `#080F0C` (selaras dark); rate-limit 30/mnt
  teruji (ke-33 → 429 jujur); reveal `.ref-reveal` + parallax rAF;
  matriks 1180 = 2 kolom lega; diff di luar login = kerja sesi lain
  (responsif tablet + drawer, tak tersentuh rangkaian ini).
- Posisi 2026-10-13: `.ref-main/header/footer` max-width 1440 + padding 48px
  + gap 48px (napas tepi desktop); mobile/tablet `order:-1` form login di
  atas semua kartu; grid QA phone ikut 3-kolom (hapus override 5-kolom).
  `landing.css?v=20261013d`.
- Urutan mobile/tablet 2026-10-13: hero → login → tabs → kartu → note →
  quick-access (`.ref-left{display:contents}` + order). `v=20261013e`.
- Backsound 2026-10-13: default ON (`aria-pressed=true` + `ana_sound` 1/0 persist);
  shuffle tas-acak 14 lagu `assets/backsound/lo/` (48kbps mono, 45M→8.6M) via
  `playlist.json` (tanpa hardcode); jeda acak 90–180 dtk antar lagu; autoplay
  diblokir = tunggu gestur pertama (toggle tetap ON); wave = sedang bunyi;
  pause saat tab hidden; OFF = src dikosongkan. Cache permanen: SW iris
  Range 206 dari cache (kunci URL polos) — sekali unduh per lagu, nol byte
  server selamanya. `login.js?v=20261013d`, `sw.js?v=20261013d`, cache `ana-v8-sound-on-cache`.
- Ratusan user 2026-10-13: playlist 14→5 terpanjang (8.6M→4.4M lifetime);
  original 46MB pindah `assets_src/` (git-ignored, serve 404); jitter 0–20 dtk
  pecah herd; Save-Data = default OFF; `deploy/nginx-simoge.conf` siap
  (static sendfile + immutable, Python hanya /api/* — belum dipasang, nginx
  tak ada di mesin ini). `v=20261013e`, cache `ana-v9-sound-herd`.
- Tahap 0: rename `SIMOG_ HUD_1 .png`→`simoge_hero_1.png`, `SIMOGE_HUD_2.png`→`simoge_hero_2.png`
  (nol referensi kode); sw.js `ana-v3-landing` + precache landing.css + 2 hero.
- Tahap 1: token forest di `tokens.css` (navy utuh) + `landing.css` baru + focus-visible.
- Tahap 2: split `login.html` (ID auth DIKUNCI, verifikasi: semua ID ada) + toggle 👁 +
  ingat-email (localStorage) + lupa→admin + reveal + `prefers-reduced-motion`.
  Cacat screenshot diperbaiki: `.center` fixed dimatikan, body scroll, fokus ganda dibuang.
- Tahap 4: `landing_insight.py` (petak 809 · aktivitas P1 0 vs 19 ▼100% · 5·11·42 ·
  series 6 periode) + `GET /api/landing/insight` publik (rate-limit 30/mnt, cache 60 dtk,
  gagal=503) + 3 kartu + sparkline SVG + label sumber/periode/waktu. Screenshot
  full-page: semua tampil. Verifikasi angka = mysql SAMA (809, P1=0).
- Smoke 118/122 (4 gagal bawaan: voices keys + open-tanpa-token 401 — server auth
  tak tersentuh rangkaian ini). Served=disk: landing.css + login.js OK.

- [x] Gaya Modern Editorial × Forest-Tech hanya di login (dashboard utuh).
- [ ] Split hero + card login proporsional di 390/820/1180/1440.
- [ ] Auth penuh hijau TANPA ubah metode: login, OTP, enroll QR, evict, redirect `next`, rate-limit (aturan keras #1).
- [ ] Show/hide password, ingat-email, lupa→admin; SSO SEMBUNYI sampai backend siap.
- [ ] Nav editorial DITUNDA — tak ada pill tanpa sumber DB (aturan keras #2).
- [ ] Insight = 3 indeks nyata + periode + sumber + waktu query; angka = query manual; gagal = sembunyi.
- [ ] TANPA angka hardcode, TANPA JSON kurasi, TANPA label "contoh" di mana pun.
- [ ] Motion ringan + `prefers-reduced-motion`; kontras + keyboard lolos.
- [ ] Audio: download latar, cache berversi, ON/OFF, gagal tak ganggu login.
- [ ] Tanpa path absolut; aset di sw.js; `?v=` naik tiap tahap.
- [ ] Post-login masuk dashboard lama tanpa perubahan visual/fungsi.
