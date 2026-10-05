#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
export ANA_RUNTIME="${ANA_RUNTIME:-auto}"

# Pick the first interpreter that actually has the runtime deps.
# `python3` on PATH is often the system interpreter (no websockets/edge_tts).
pick_python() {
  local c
  for c in "$HOME"/.hermes/tools/python-*/bin/python3 "$(command -v python3 || true)" python3; do
    [ -x "$c" ] || continue
    if "$c" -c "import websockets, edge_tts" >/dev/null 2>&1; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  return 1
}

if ! PY=$(pick_python); then
  cat >&2 <<'EOF'
ANA: no Python interpreter with the required modules (websockets, edge_tts).

Try, in order:
  1) Hermes tools interpreter:
       PY=$(echo ~/.hermes/tools/python-*/bin/python3 | head -1)
       "$PY" -m pip install websockets edge_tts
  2) system interpreter:
       python3 -m pip install --user websockets edge_tts   # add --break-system-packages if PEP 668 blocks it
EOF
  exit 1
fi

# Gateway WS lives in `hermes serve` (dynamic port, per-process token) — NOT port 37521.
# Discover both so ANA brain connects instead of falling back to MOCK.
# ponytail: single serve instance assumed — extend with profile match when multi-serve needed.
if [ -z "${ANA_GATEWAY_URL:-}" ] || [ -z "${ANA_GATEWAY_TOKEN:-}" ]; then
  SPID=$(ss -ltnp 2>/dev/null | grep '"hermes"' | sed 's/.*pid=\([0-9][0-9]*\).*/\1/' | head -1 || true)
  if [ -n "${SPID:-}" ]; then
    SPORT=$(ss -ltnp 2>/dev/null | grep "pid=$SPID" | grep -oE '127\.0\.0\.1:[0-9]+' | head -1 | cut -d: -f2 || true)
    if [ -n "${SPORT:-}" ]; then
      STOK=$(curl -s -m 3 "http://127.0.0.1:$SPORT/" 2>/dev/null | grep -oE '__HERMES_SESSION_TOKEN__="[^"]+"' | head -1 | cut -d'"' -f2 || true)
      if [ -n "${STOK:-}" ]; then
        export ANA_GATEWAY_URL="ws://127.0.0.1:$SPORT/api/ws"
        export ANA_GATEWAY_TOKEN="$STOK"
      fi
    fi
  fi
fi
[ -n "${ANA_GATEWAY_TOKEN:-}" ] ||
  echo "ANA: gateway token not found — start 'hermes serve' first (brain will be MOCK)" >&2

echo "ANA: using $PY" >&2
exec "$PY" server.py