#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# one-click: hermes >=0.21.5, profil anna, deps python, .env
need="0.21.5"
if command -v hermes >/dev/null 2>&1; then
  ver=$(hermes --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  if [ -n "$ver" ] && [ "$(printf '%s\n%s' "$need" "$ver" | sort -V | head -1)" != "$need" ]; then
    echo "ANA: hermes $ver < $need, update dulu" >&2; exit 1
  fi
else
  echo "ANA: hermes tak ketemu. pasang: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash" >&2; exit 1
fi
if [ ! -f .env ]; then cp .env.example .env; echo "ANA: .env dibuat dari example, isi SIMOGE_DB_PASSWORD dulu bila kosong"; fi
# deps python (interpreter hermes dulu, fallback python3)
PY=$(echo ~/.hermes/tools/python-*/bin/python3 | head -1); [ -x "$PY" ] || PY=python3
"$PY" -c "import websockets, edge_tts, pymysql, pandas" 2>/dev/null || "$PY" -m pip install --user websockets edge_tts pymysql pandas
# profil anna dari profile-dist (user data aman, owned ditimpa)
if ! hermes profile list 2>/dev/null | grep -qE '^anna([[:space:]]|$)'; then
  hermes profile install ./profile-dist -y || hermes profile install "$PWD/profile-dist" -y
else
  echo "ANA: profil anna ada, lewati install (pakai: hermes profile update anna bila perlu)"
fi
chmod +x start.sh install.sh
echo "ANA: siap. jalan: ./start.sh (port ${ANA_PORT:-8730})"
exec ./start.sh
