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
git checkout v1.0.0   # pin versi — jangan deploy dari main bergerak
```

## 3. Instal
```bash
./install.sh                      # interaktif: tanya proses profile-dist bila TTY
./install.sh --without-profile    # lewati profile-dist (skills/plugins/SOUL)
ANA_PROFILE_DIST=no ./install.sh  # sama via env (untuk CI/non-TTY)
```
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

## 5. Systemd + cron + nginx
```bash
# service (ganti __USER__/__ANA_WORKDIR__ dulu, lihat header file)
sudo sed -e "s|__USER__|$USER|" -e "s|__ANA_WORKDIR__|$PWD|" \
  deploy/simoge-hud.service | sudo tee /etc/systemd/system/simoge-hud.service
sudo systemctl daemon-reload && sudo systemctl enable --now simoge-hud
# cron (ganti __ANA_WORKDIR__): crontab -e, tempel isi deploy/cron-simoge
# nginx (ganti __ANA_WORKDIR__/__ANA_PORT__): lihat header deploy/nginx-simoge.conf
```

## 6. Verifikasi
- `curl -s http://127.0.0.1:8730/login.html | grep -o 'landing.css?v=[^"]*'` → versi kini
- Login via browser → DB OK, peta tampil, insight terisi (bukan "Memuat…" permanen)
- Bila via domain dan 403: cek `ANA_ALLOWED_HOSTS`; bila cookie sesi hilang: cek skema
  http/https vs `ANA_COOKIE_SECURE`.

## 7. Rollback
Tiap rilis = tag git. Mundur: `git checkout <tag-lama> && sudo systemctl restart simoge-hud`.
Backup sebelum upgrade: `.env`, `layout_*.json`, `.ana_insight.json`.
