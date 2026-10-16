#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"
if [ -z "${ANA_PORT:-}" ] && [ -f .env ]; then
  ANA_PORT=$(grep -E '^[[:space:]]*ANA_PORT=' .env 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d ' "' | tr -d "'")
fi
export ANA_PORT="${ANA_PORT:-8730}"

export PATH="/usr/local/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"
# hermes session injects PYTHONPATH pointing to its own venv (3.14 site-packages).
# itu bocorin numpy c-ext ke .venv bila minor version beda -> ImportError _multiarray_umath.
# isolate: .venv harus murni.
unset PYTHONPATH
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
# Prioritas: .venv per-project (isolated, reproducible) > hermes tools > system python3.
pick_python() {
  local c
  # 1) per-project venv — paling deterministik
  if [ -x "$ROOT/.venv/bin/python3" ]; then
    if "$ROOT/.venv/bin/python3" -c "import websockets, edge_tts, pymysql, pandas, argon2" >/dev/null 2>&1; then
      printf '%s\n' "$ROOT/.venv/bin/python3"
      return 0
    fi
  fi
  # 2) hermes tools + system fallback
  for c in "$HOME/.hermes/tools/python-*/bin/python3" "$(command -v python3 || true)" python3; do
    [ -x "$c" ] || continue
    if "$c" -c "import websockets, edge_tts, pymysql, pandas, argon2" >/dev/null 2>&1; then
      printf '%s\n' "$c"
      return 0
    fi
  done
  return 1
}

if ! PY=$(pick_python); then
  cat >&2 <<'EOF'
ANA: no Python interpreter with the required modules (websockets, edge_tts, pymysql, pandas, argon2).

Setup per-project (recommended):
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt

Fallback global (hermes tools):
  PY=$(echo ~/.hermes/tools/python-*/bin/python3 | head -1)
  "$PY" -m pip install -r requirements.txt   # atau: pip install websockets edge_tts pymysql pandas argon2-cffi
EOF
  exit 1
fi

# Gateway WS lives in `hermes serve` (dynamic port, per-process token) — NOT port 37521.
# start.sh WAJIB dapat serve: pakai yang hidup, atau start sendiri lalu
# discovery ulang. Tanpa URL+token valid -> abort, jangan jalan MOCK diam-diam.
# ponytail: single serve instance assumed — extend with profile match when multi-serve needed.
# Deteksi BERLAPIS (bukan nama proses saja): biner `hermes` maupun
# `python3 -m hermes_cli.main ... serve` (comm=python3!) dikenali lewat
# cmdline, lalu dipastikan via /api/health khas hermes. Tanpa ini instalasi
# server (python3) luput dari regex '"hermes"' lama.
_hermes_listen_ports() {
  ss -ltnp 2>/dev/null | while IFS= read -r line; do
    case "$line" in *127.0.0.1:*pid=*) ;; *) continue ;; esac
    pid=$(printf '%s' "$line" | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2)
    port=$(printf '%s' "$line" | grep -oE '127\.0\.0\.1:[0-9]+' | head -1 | cut -d: -f2)
    [ -n "$pid" ] && [ -n "$port" ] || continue
    if printf '%s' "$line" | grep -q '"hermes"'; then
      echo "$port"
    elif tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -qi hermes; then
      # verifikasi perilaku agar tak salah menunjuk proses python lain
      if curl -s -m 3 "http://127.0.0.1:$port/api/health" 2>/dev/null | grep -q 'displayVersion'; then
        echo "$port"
      fi
    fi
  done
}
# Ambil token sesi serve (rotasi tiap restart serve — jangan cache antar-boot).
_hermes_token_for() {
  curl -s -m 3 "http://127.0.0.1:$1/" 2>/dev/null | grep -oE '__HERMES_SESSION_TOKEN__="[^"]+"' | head -1 | cut -d'"' -f2 || true
}
# Pastikan ada serve yang jawab /api/health. Hidup -> pakai. Mati/tak ada ->
# start `hermes serve --port 0` sendiri (detached), lalu discovery ulang.
# Return: SPORT terisi bila sukses.
_ensure_hermes_serve() {
  SPORT=$(_hermes_listen_ports | head -1 || true)
  if [ -n "${SPORT:-}" ]; then
    if curl -s -m 3 "http://127.0.0.1:$SPORT/api/health" 2>/dev/null | grep -q 'displayVersion'; then
      return 0
    fi
    SPORT=""
  fi
  [ "${ANA_NO_SERVE_AUTOSTART:-0}" = "1" ] && return 1
  echo "ANA: hermes serve tidak ditemukan — menjalankan 'hermes serve --port 0' ..." >&2
  # shellcheck disable=SC2094
  nohup hermes serve --port 0 --host 127.0.0.1 --skip-build >/dev/null 2>&1 &
  local n=0
  while [ $n -lt 30 ]; do
    sleep 1; n=$((n+1))
    SPORT=$(_hermes_listen_ports | head -1 || true)
    if [ -n "${SPORT:-}" ]; then
      if curl -s -m 3 "http://127.0.0.1:$SPORT/api/health" 2>/dev/null | grep -q 'displayVersion'; then
        echo "ANA: hermes serve hidup di port $SPORT" >&2
        return 0
      fi
      SPORT=""
    fi
  done
  return 1
}
if [ -z "${ANA_GATEWAY_URL:-}" ] || [ -z "${ANA_GATEWAY_TOKEN:-}" ]; then
  if _ensure_hermes_serve; then
    STOK=$(_hermes_token_for "$SPORT")
    if [ -n "${STOK:-}" ]; then
      export ANA_GATEWAY_URL="ws://127.0.0.1:$SPORT/api/ws"
      export ANA_GATEWAY_TOKEN="$STOK"
    else
      unset ANA_GATEWAY_URL ANA_GATEWAY_TOKEN
    fi
  else
    unset ANA_GATEWAY_URL ANA_GATEWAY_TOKEN
  fi
fi
if [ -z "${ANA_GATEWAY_URL:-}" ] || [ -z "${ANA_GATEWAY_TOKEN:-}" ]; then
  cat >&2 <<'EOF'
ANA: FATAL — hermes serve tidak tersedia dan autostart gagal.
  Cek:  hermes serve --status
  Atasi: hermes serve --port 0 --host 127.0.0.1 --skip-build
  Lalu: ./start.sh
  (Lewati dengan ANA_NO_SERVE_AUTOSTART=1 bila ingin MOCK sadar, bukan diam-diam.)
EOF
  [ "${ANA_NO_SERVE_AUTOSTART:-0}" = "1" ] || exit 1
  echo "ANA: lanjut MOCK (ANA_NO_SERVE_AUTOSTART=1) — brain tidak tersambung" >&2
fi

echo "ANA: using $PY" >&2
# ── diagnostics (selalu tampil, anti-gagal: set -e jangan gugur di sini)
(
  set +e
  _ev() { grep -E "^[[:space:]]*$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | sed "s/ #.*//;s/^[ '\"]*//;s/[ '\"]*//" | cut -c1-24; }
  echo "ANA: ANA_MODE=$(_ev ANA_MODE) ANA_DEBUG_MAP=$(_ev ANA_DEBUG_MAP) ANA_HOST=$(_ev ANA_HOST) ANA_PORT=$ANA_PORT" >&2
  timeout 4 "$PY" <<'PYEOF' >&2 || echo "ANA: DB check skip/timeout" >&2
import auth_local
try:
    kw=auth_local._db_kwargs()
    print(f"ANA: DB {kw['host']}:{kw['port']}/{kw['database']} user={kw['user']} pw_len={len(kw['password'])}", flush=True)
    row=auth_local.get_user_by_email("bryankldr@gmail.com")
    if row:
        print(f"ANA: DB OK sample={row['email']} 2fa={row.get('2fa')} hud={row.get('hud_access')} status={row.get('status')} pw={row.get('password','')[:18]}", flush=True)
    else:
        import pymysql
        c=pymysql.connect(**kw); cur=c.cursor(); cur.execute("SELECT COUNT(*) FROM directus_users"); print(f"ANA: DB OK count={cur.fetchone()[0]} tapi bryankldr@gmail.com tidak ditemukan", flush=True); c.close()
except Exception as e:
    print(f"ANA: DB FAIL {type(e).__name__}: {str(e)[:220]}", flush=True)
PYEOF
  echo "ANA: tips — POST /api/auth/login butuh password+otp bila 2fa=1. 401 otp_required = NORMAL, isi OTP 6-digit. Lihat [auth] di log." >&2
  echo "ANA: logs  — logs/server.log | tail -f logs/server.log" >&2
) || true
exec "$PY" server.py