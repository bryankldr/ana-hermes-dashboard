#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"
if [ -z "${ANA_PORT:-}" ] && [ -f .env ]; then
  ANA_PORT=$(grep -E '^[[:space:]]*ANA_PORT=' .env 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d ' "' | tr -d "'")
fi
export ANA_PORT="${ANA_PORT:-8730}"

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
export ANA_RUNTIME="${ANA_RUNTIME:-auto}"

# Restart aman: cek + matikan instance dashboard lama (port yg sama / dir ini)
# sebelum start, agar tidak tabrakan EADDRINUSE di port guard server.py.
# Proses asing pemegang port TIDAK dimatikan otomatis — abort dgn pesan jelas.
# Lewati dgn ANA_NO_KILL=1 bila ingin inspeksi manual.
_port_busy() {
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | grep -qE '[:.]'"$ANA_PORT"'([[:space:]]|$)'
  elif command -v lsof >/dev/null 2>&1; then
    lsof -ti:"$ANA_PORT" >/dev/null 2>&1
  else
    (echo > "/dev/tcp/127.0.0.1/${ANA_PORT}") >/dev/null 2>&1
  fi
}

stop_stale_dashboard() {
  [ "${ANA_NO_KILL:-0}" = "1" ] && return 0
  local pids="" pid info cwd cmd victim="" dead=0
  if command -v ss >/dev/null 2>&1; then
    pids=$(ss -ltnp 2>/dev/null | grep -E '[:.]'"$ANA_PORT"'([[:space:]]|$)' | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -un || true)
  elif command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti:"$ANA_PORT" 2>/dev/null | sort -un || true)
  fi
  if command -v pgrep >/dev/null 2>&1; then
    for pid in $(pgrep -f "[s]erver\\.py" 2>/dev/null || true); do
      [ -z "$pid" ] && continue
      [ "$pid" = "$$" ] && continue
      info=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || ps -o command= -p "$pid" 2>/dev/null || true)
      cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
      case "$info $cwd" in
        *"$ROOT"*) pids="$pids $pid" ;;
      esac
    done
  fi
  # dedupe: ss + pgrep bisa laporkan PID yg sama 2x
  # shellcheck disable=SC2086
  pids=$(printf '%s\n' $pids | sort -un | tr '\n' ' ')
  for pid in $pids; do
    [ -z "$pid" ] && continue
    [ "$pid" = "$$" ] && continue
    kill -0 "$pid" 2>/dev/null || continue # sudah mati (kill iterasi sblmnya) -> skip
    cmd=$(ps -o command= -p "$pid" 2>/dev/null || echo "?")
    case "$cmd" in
      *server.py*)
        echo "ANA: stopping old dashboard (PID $pid)" >&2
        kill "$pid" 2>/dev/null || true
        victim="$victim $pid"
        ;;
      *) echo "ANA: port $ANA_PORT dipakai proses lain (PID $pid: $cmd) — tidak dimatikan otomatis" >&2 ;;
    esac
  done
  if [ -n "$victim" ]; then
    while [ $dead -lt 25 ] && _port_busy; do sleep 0.2; dead=$((dead+1)); done
    if _port_busy; then
      for pid in $victim; do kill -9 "$pid" 2>/dev/null || true; done
      sleep 1
    fi
  fi
  if _port_busy; then
    echo "ANA: port $ANA_PORT masih dipakai — matikan manual (lsof -ti:$ANA_PORT | xargs kill) atau pakai ANA_PORT lain" >&2
    return 1
  fi
  [ -z "$victim" ] || echo "ANA: port $ANA_PORT bebas" >&2
}

stop_stale_dashboard

# Pick the first interpreter that actually has the runtime deps.
# `python3` on PATH is often the system interpreter (no websockets/edge_tts).
pick_python() {
  local c
  for c in "$HOME"/.hermes/tools/python-*/bin/python3 "$(command -v python3 || true)" python3; do
    [ -x "$c" ] || continue
    if "$c" -c "import websockets, edge_tts, pymysql, pandas" >/dev/null 2>&1; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  return 1
}

if ! PY=$(pick_python); then
  cat >&2 <<'EOF'
ANA: no Python interpreter with the required modules (websockets, edge_tts, pymysql, pandas).

Try, in order:
  1) Hermes tools interpreter:
       PY=$(echo ~/.hermes/tools/python-*/bin/python3 | head -1)
       "$PY" -m pip install websockets edge_tts pymysql pandas
  2) system interpreter:
       python3 -m pip install --user websockets edge_tts pymysql pandas   # add --break-system-packages if PEP 668 blocks it
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