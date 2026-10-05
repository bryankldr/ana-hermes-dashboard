#!/bin/bash
# Rebuild harian PMTiles petak (P2-4). Dijadwalkan via cron 06:10 WIB —
# 10 menit setelah refresh_petak_simple.py (06:00) menulis petak_simple.json.
# Cron dikelola dari UI via POST /api/tiles/cron (marker: ana-pmtiles-daily).
# Manual: bash scripts/rebuild_tiles_daily.sh
set -u
cd "$(dirname "$0")/.." || exit 1
python3 scripts/export_petak.py --tahun 2026 --out tiles/petak.ndjson && \
python3 scripts/build_pmtiles.py
