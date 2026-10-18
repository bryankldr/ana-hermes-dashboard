#!/bin/bash
# Rebuild harian PMTiles petak (P2-4). Dijadwalkan via cron 06:10 WIB —
# 10 menit setelah refresh_petak_simple.py (06:00) menulis petak_simple.json.
# Cron dikelola dari UI via POST /api/tiles/cron (marker: ana-pmtiles-daily).
# Manual: bash scripts/rebuild_tiles_daily.sh
set -u
cd "$(dirname "$0")/.." || exit 1
# Pakai .venv bila ada (modul build mapbox-vector-tile + pmtiles hanya di sana).
# Tanpa ini cron 06:10 gagal ModuleNotFoundError dan pmtiles basi lagi.
PYBIN="python3"
[ -x .venv/bin/python ] && PYBIN=".venv/bin/python"

# Gunakan tahun berjalan nyata dari sistem
TAHUN=$(date '+%Y')

# 1. Export semua KPH sebagai PMTiles terpisah (untuk skalabilitas DIREKSI/ADMINISTRATOR)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Memulai export per-KPH PMTiles untuk tahun $TAHUN..."
"$PYBIN" scripts/export_all_kph.py --tahun "$TAHUN"
ALL_KPH_STATUS=$?

# 2. Export single PMTiles (fallback/compatibility untuk user scope kecil)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Export single PMTiles (fallback) untuk tahun $TAHUN..."
"$PYBIN" scripts/export_petak.py --tahun "$TAHUN" --out tiles/petak.ndjson && \
"$PYBIN" scripts/build_pmtiles.py
SINGLE_STATUS=$?

# 3. Cleanup NDJSON intermediate files (hemat storage)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cleanup NDJSON intermediate files..."
rm -f tiles/petak.ndjson
rm -f tiles/kph_*.ndjson
rm -f tiles/kph_*_*.ndjson
CLEANUP_STATUS=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Rebuild selesai. Tahun: $TAHUN, All-KPH: $ALL_KPH_STATUS, Single: $SINGLE_STATUS, Cleanup: $CLEANUP_STATUS"
