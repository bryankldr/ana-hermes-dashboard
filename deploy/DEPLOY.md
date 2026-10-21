# Deploy SIMOGE HUD ke Server Linux Lain

Panduan ini untuk server target baru (Ubuntu 24.04 disarankan — butuh Python ≥ 3.12
untuk `requirements.txt`). Server ini (dev) tetap berjalan; jangan otak-atik `.env` dev.

## 1. Siapkan server target
- Python 3.12+, `python3-venv`, `pip`, `git`, `ss`/`lsof`, `nginx` (opsional, untuk reverse-proxy).
- MariaDB/MySQL terjangkau (lokal atau via SSH tunnel — lihat `ANA_DB_SOURCE`).
- (Disarankan) `hermes` CLI ≥ 0.21.5 bila ingin brain non-MOCK + profil `anna`.
  Bila belum ada, `install.sh` menawari pemasangan otomatis (jawab `n` untuk
  pasang manual). Tanpa hermes, instalasi tetap jalan (fallback `.venv` sistem).

## 2. Ambil kode (tag rilis, BUKAN branch kerja)
```bash
git clone <repo> /opt/simoge-dashboard && cd /opt/simoge-dashboard
git checkout "$(git tag -l 'v*' --sort=-v:refname | head -1)"   # pin tag rilis terbaru
# jangan deploy dari main yang bergerak
```

## 3. Instal
```bash
./install.sh                      # interaktif: tanya proses profile-dist bila TTY
./install.sh --without-profile    # lewati profile-dist (skills/plugins/SOUL)
ANA_PROFILE_DIST=no ./install.sh  # sama via env (untuk CI/non-TTY)
ANA_UI_BUILD=no ./install.sh      # lewati build bundel UI (npm tak tersedia/offline)
```
`install.sh` ikut membangun bundel UI bila `npm` ada (`npm ci` + `node
scripts/build_ui.mjs` → `ui/dist/app.min.js`). Gagal build bukan blocker: server
tetap menyajikan `ui/src/`.
Lalu isi rahasia (TIDAK ikut repo):
```bash
cp .env.example .env   # bila belum ada (install.sh sudah buatkan)
nano .env              # wajib: DB_PASSWORD/REMOTE_DB_*, ANA_DEVICE_SALT,
                       # ANA_ALLOWED_HOSTS (bila via domain), ANA_PORT
```

## 4. Artefak runtime (dibangun, bukan disalin)
| Artefak | Cara bangun | Kapan |
|---|---|---|
| `.venv` | otomatis oleh `install.sh` | sekali |
| `.ana_insight.json` | `bash scripts/rebuild_insight_daily.sh` atau tunggu cron 06:00 | setelah DB OK |
| `tiles/*.pmtiles`, `petak_simple.json` | `bash scripts/rebuild_tiles_daily.sh` | setelah DB OK |
| `layout.json` | otomatis default saat boot pertama | — |
| `ui/dist/app.min.js` | `npm ci && npm run build:ui` (install.sh sudah coba otomatis) | setiap rilis UI |

Bundel UI hanya dipakai bila `ANA_UI_BUNDLE=1` di `.env`; default `0` = sumber
`ui/src/` apa adanya (mudah di-debug). Tanpa bundel, aplikasi tetap jalan penuh.

## 5. Systemd + cron
```bash
# service (ganti __USER__/__ANA_WORKDIR__ dulu, lihat header file)
sudo sed -e "s|__USER__|$USER|" -e "s|__ANA_WORKDIR__|$PWD|" \
  deploy/simoge-hud.service | sudo tee /etc/systemd/system/simoge-hud.service
sudo systemctl daemon-reload && sudo systemctl enable --now simoge-hud
# cron (ganti __ANA_WORKDIR__): crontab -e, tempel isi deploy/cron-simoge
# reverse proxy (nginx/Apache + domain): lihat §6
```

## 6. Reverse proxy: nginx atau Apache (+ Cloudflare Tunnel)

nginx: lihat header `deploy/nginx-simoge.conf`.

Apache (LAMPP/XAMPP Linux). Kalau tunnel Cloudflare sudah menargetkan
`http://127.0.0.1:443`, **jangan** pakai SSL di origin: TLS berakhir di edge, dan
Apache yang memasang `SSLEngine on` di 443 akan menjawab `400 Bad Request` untuk
setiap request HTTP polos dari `cloudflared` ("plain HTTP request sent to HTTPS port").
Karena itu 443 dibuat sebagai listener HTTP biasa:

```apache
# /opt/lampp/etc/extra/httpd-hud.conf
Listen 443

<VirtualHost *:443>
    ServerName hud.kphbwb.web.id
    ProxyPreserveHost On
    ProxyRequests Off
    RequestHeader set X-Forwarded-Proto "https"   # memicu cookie Secure
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule /(.*) ws://127.0.0.1:8730/$1 [P,L]
    ProxyPass        /  http://127.0.0.1:8730/ timeout=600 flushpackets=on retry=0
    ProxyPassReverse /  http://127.0.0.1:8730/
</VirtualHost>
```

Wajib: `Include etc/extra/httpd-ssl.conf` di `httpd.conf` **di-comment** (kalau tidak
ada dua `Listen 443` dan vhost SSL default menangkap Host HUD). Modul yang harus
aktif: `proxy`, `proxy_http`, `proxy_wstunnel`, `rewrite`, `headers`.
Bila reload memunculkan `AH00819 Could not allocate shared memory segment for shmcb`
/ `AH02312 Fatal error initialising mod_ssl`, modul SSL masih mencoba membuat session
cache: nonaktifkan `LoadModule ssl_module` sama sekali (TLS di Cloudflare) lalu
**start penuh** (`apachectl -k start`), bukan `graceful` — graceful pada kondisi itu
mematikan Apache termasuk port 80.

- `flushpackets=on` wajib: `/api/run` mengalirkan NDJSON bertahap (tanpa ini jawaban tertahan).
- `RewriteRule` WebSocket wajib: `/api/terminal-stream` dan stream run memakai upgrade.
- `ANA_ALLOWED_HOSTS` **wajib** diisi domain publik; tanpa itu Host/Origin publik → 403.
- Jangan tambahkan `Access-Control-Allow-Origin` di proxy: UI dan API satu origin, CORS tak dibutuhkan.
- Cloudflare: aktifkan *Always Use HTTPS*; **bypass cache untuk `/api/*`** (kalau tidak, rebuild
  tiles/insight harian tampak tidak berubah). Koneksi idle diputus di 100 detik (524).
- `img-src`/`connect-src` CSP diturunkan dari `DIRECTUS_URL` (foto penyadap diambil dari
  `https://sandbox2.kphbwb.web.id/assets/<id>`). Tanpa itu foto diblokir CSP.

## 7. Verifikasi
- `curl -s http://127.0.0.1:8730/login.html | grep -o 'landing.css?v=[^"]*'` → versi kini
- Login via browser → DB OK, peta tampil, insight terisi (bukan "Memuat…" permanen)
- Bila via domain dan 403: cek `ANA_ALLOWED_HOSTS`; bila cookie sesi hilang: cek skema
  http/https vs `ANA_COOKIE_SECURE` (cookie otomatis `Secure` bila proxy kirim
  `X-Forwarded-Proto: https`).
- Keamanan klien: `curl -s http://127.0.0.1:8730/ | grep -c ana-token` harus **0**
  (master token tidak boleh ada di HTML). Auth browser = cookie sesi `HttpOnly`.
- Versi: `curl -s http://127.0.0.1:8730/api/status | grep -o '"version":[^,]*'`.

## 8. Rollback
Tiap rilis = tag git. Mundur: `git checkout <tag-lama> && sudo systemctl restart simoge-hud`.
Backup sebelum upgrade: `.env`, `layout_*.json`, `.ana_insight.json`.

## 9. Catatan lapangan: KPHBWB (LAMPP, 2026-10-21, v1.1.3 → 1.1.4)

Kondisi nyata server: Ubuntu 22.04, LAMPP di `/opt/lampp` (Apache 2.4.58, MariaDB 10.4),
`cloudflared` di host, tunnel `hud.kphbwb.web.id` → `http://127.0.0.1:443`, tanpa systemd
unit untuk HUD, venv dibangun pakai Anaconda Python 3.12 (`/home/bryan/anaconda3/bin/python3`)
karena `python3` sistem 3.10 tidak memenuhi `pandas==3.0.6`.

```bash
# kode
rsync -a --exclude .venv --exclude node_modules --exclude ui/dist --exclude logs \
      --exclude .env --exclude '.ana_*' ./ bryan@host:ana-hermes-dashboard/
# runtime
~/anaconda3/bin/python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
npm ci --no-audit --no-fund && node scripts/build_ui.mjs     # ui/dist/app.min.js, ANA_UI_BUNDLE=1
```

Launcher yang benar adalah `start.sh`, **bukan** `python server.py` langsung:
`start.sh` menemukan/menjalankan `hermes serve` lalu mengekspor `ANA_GATEWAY_URL` +
`ANA_GATEWAY_TOKEN`. Tanpa itu `/api/status` melaporkan `"runtime": "mock"` dan
`brain MOCK — Hermes CLI not reachable` walau CLI `hermes` sehat.

`~/run-hud.sh` (dipakai `crontab @reboot`):
```bash
#!/usr/bin/env bash
cd /home/bryan/ana-hermes-dashboard || exit 1
export PATH=/home/bryan/.local/bin:/usr/local/bin:/usr/bin:/bin
mkdir -p logs
exec ./start.sh >> logs/server.log 2>&1
```

Prosedur ganti versi di server: sisihkan direktori lama (`mv`), `rsync` tag baru,
`pip install -r requirements.txt` (hanya bila berubah), `npm run build:ui`, lalu
`kill $(lsof -ti:8730)` + jalankan `~/run-hud.sh`. Jangan `pkill -f "server.py"` dari
sesi SSH yang teks perintahnya sendiri memuat `server.py` — pola itu membunuh sesi itu sendiri.

Langkah yang butuh `sudo` (password diminta di console server, jangan lewat chat):
`/opt/lampp/etc` root-owned, Apache master berjalan sebagai root untuk bind 443.
