#!/bin/bash
# Kalkulasi insight landing harian 06:00 WIB (marker: ana-insight-daily).
# Output: .ana_insight.json (atomik) → live card baca file, tanpa query/request.
# Cron dikelola dari UI via POST /api/insight/cron (marker: ana-insight-daily).
# Manual: bash scripts/rebuild_insight_daily.sh [--force]
set -u
cd "$(dirname "$0")/.." || exit 1
# Pakai .venv bila ada (pandas hanya di sana; fallback Python murni bila tak ada).
PYBIN="python3"
[ -x .venv/bin/python ] && PYBIN=".venv/bin/python"
"$PYBIN" insight_build.py --force >> logs/insight.log 2>&1
