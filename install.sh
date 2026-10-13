#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
need="0.21.5"
HERMES_INSTALL_URL="https://hermes-agent.nousresearch.com/install.sh"
if command -v hermes >/dev/null 2>&1; then
  ver=$(hermes --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)
  if [ -n "$ver" ] && [ "$(printf '%s\n%s' "$need" "$ver" | sort -V | head -1)" != "$need" ]; then
    echo "ANA: hermes $ver < $need, update manual dulu" >&2; exit 1
  fi
else
  echo "ANA: hermes tak ketemu." >&2
  # Interaktif: tawarkan pasang otomatis (default bila TTY); non-TTY/CI
  # tidak pernah curl|bash diam-diam. HERMES_AUTO_INSTALL=yes|no memaksa.
  _install_hermes=0
  case "${HERMES_AUTO_INSTALL:-ask}" in
    [Yy]*|1|[Tt]rue) _install_hermes=1 ;;
    [Nn]*|0|[Ff]alse) _install_hermes=0 ;;
    *)
      if [ -t 0 ]; then
        printf 'ANA: pasang hermes otomatis dari %s? [Y]a/[n] manual: ' "$HERMES_INSTALL_URL" >&2
        IFS= read -r _ans < /dev/tty 2>/dev/null || IFS= read -r _ans || _ans=""
        case "$_ans" in [Nn]*) _install_hermes=0 ;; *) _install_hermes=1 ;; esac
      else
        _install_hermes=0
      fi
      ;;
  esac
  if [ "$_install_hermes" = "1" ]; then
    echo "ANA: menginstal hermes..." >&2
    curl -fsSL "$HERMES_INSTALL_URL" | bash >&2 || { echo "ANA: instalasi hermes gagal" >&2; exit 1; }
    command -v hermes >/dev/null 2>&1 || { echo "ANA: hermes tetap tak ketemu setelah instal (cek PATH di shell baru), lalu ulangi ./install.sh" >&2; exit 1; }
  else
    echo "ANA: pasang manual: curl -fsSL $HERMES_INSTALL_URL | bash, lalu ulangi ./install.sh" >&2
    exit 1
  fi
fi
if [ ! -f .env ]; then cp .env.example .env; echo "ANA: .env dibuat dari example, isi SIMOGE_DB_PASSWORD dulu bila kosong"; fi
# hermes session injects PYTHONPATH -> bocorin site-packages (numpy c-ext mismatch). isolate.
unset PYTHONPATH
# ── per-project venv (isolated, reproducible). fallback ke hermes tools bila venv belum ada.
# venv harus satu minor dengan hermes python (3.14) agar numpy c-ext tidak mismatch.
_hermes_py=$(echo "$HOME/.hermes/tools/python-"*/bin/python3 2>/dev/null | tr ' ' '\n' | head -1)
[ -x "$_hermes_py" ] || _hermes_py=$(command -v python3)
if [ -x .venv/bin/python3 ] && .venv/bin/python3 -c "import websockets, edge_tts, pymysql, pandas, argon2" >/dev/null 2>&1; then
  PY=.venv/bin/python3
  echo "ANA: venv .venv OK ($PY)" >&2
else
  if [ ! -x .venv/bin/python3 ]; then
    echo "ANA: buat .venv per-project ($_hermes_py)..." >&2
    "$_hermes_py" -m venv .venv 2>&1 || python3 -m venv .venv 2>&1 || { echo "ANA: venv gagal — butuh python3-venv" >&2; PY="$_hermes_py"; }
  fi
  if [ -x .venv/bin/python3 ]; then
    PY=.venv/bin/python3
    echo "ANA: install deps ke .venv ($PY)..." >&2
    "$PY" -m pip install -q -r requirements.txt 2>&1 || "$PY" -m pip install -q -r requirements.txt --break-system-packages 2>&1 || {
      echo "ANA: pip install gagal" >&2; exit 1
    }
    "$PY" -c "import websockets, edge_tts, pymysql, pandas, argon2" 2>/dev/null || { echo "ANA: deps .venv belum lengkap" >&2; exit 1; }
  else
    PY="$_hermes_py"; [ -x "$PY" ] || PY=$(command -v python3)
    "$PY" -c "import websockets, edge_tts, pymysql, pandas, argon2" 2>/dev/null || "$PY" -m pip install --user -q -r requirements.txt 2>&1 || "$PY" -m pip install --user -q -r requirements.txt --break-system-packages 2>&1 || true
  fi
fi

DIST="$PWD/profile-dist"
# ── profile-dist: interaktif (default tanya bila TTY) ──
#   ANA_PROFILE_DIST=yes  → proses tanpa tanya
#   ANA_PROFILE_DIST=no   → lewati total (deploy tanpa skills/plugins/SOUL)
#   ANA_PROFILE_DIST=ask  → tanya bila interaktif, proses bila non-TTY (CI aman)
#   Flag CLI: ./install.sh --with-profile | --without-profile (menang atas env)
for _arg in "$@"; do
  case "$_arg" in
    --with-profile) ANA_PROFILE_DIST=yes ;;
    --without-profile) ANA_PROFILE_DIST=no ;;
  esac
done
ANA_PROFILE_DIST="${ANA_PROFILE_DIST:-ask}"
_process_profile=1
case "$ANA_PROFILE_DIST" in
  [Nn][Oo]|[Ff]alse|0) _process_profile=0 ;;
  [Yy][Ee][Ss]|[Tt]rue|1) _process_profile=1 ;;
  *)
    if [ -t 0 ]; then
      printf 'ANA: proses profile-dist (skills/plugins/SOUL, ~5MB) ke profil anna? [Y]a/[n] lewati: ' >&2
      IFS= read -r _ans < /dev/tty 2>/dev/null || IFS= read -r _ans || _ans=""
      case "$_ans" in
        [Nn]*) _process_profile=0 ;;
        *) _process_profile=1 ;;
      esac
    else
      _process_profile=1
    fi
    ;;
esac
if [ "$_process_profile" = "0" ]; then
  echo "ANA: profile-dist DILEWATI (ANA_PROFILE_DIST=no) — lanjut tanpa skills/plugins" >&2
else
# fresh install atau update (distribution_owned: SOUL.md, skills, plugins)
if ! hermes profile list 2>/dev/null | grep -qE '^anna([[:space:]]|$)'; then
  echo "ANA: install profil anna"
  hermes profile install "$DIST" -y || hermes profile install ./profile-dist -y
else
  echo "ANA: profil anna ada — update"
  # coba update via recorded source; bila bukan distribusi, fallback ke install --force
  if ! hermes profile update anna -y 2>/dev/null; then
    hermes profile install "$DIST" --force -y 2>/dev/null || hermes profile install ./profile-dist --force -y 2>/dev/null || true
  fi
  # fallback copy bila update gagal total (mis. anna lama tanpa manifest) — timpa owned saja
  if [ -d "$DIST/skills" ]; then
    for d in "$DIST"/skills/*/; do [ -d "$d" ] || continue; n=$(basename "$d"); rm -rf "$HOME/.hermes/profiles/anna/skills/$n"; cp -r "$d" "$HOME/.hermes/profiles/anna/skills/"; done
    if [ -d "$DIST/skills/software-development" ]; then
      mkdir -p "$HOME/.hermes/profiles/anna/skills/software-development"
      for d in "$DIST"/skills/software-development/*/; do [ -d "$d" ] || continue; n=$(basename "$d"); rm -rf "$HOME/.hermes/profiles/anna/skills/software-development/$n"; cp -r "$d" "$HOME/.hermes/profiles/anna/skills/software-development/"; done
    fi
  fi
  [ -d "$DIST/plugins" ] && for d in "$DIST"/plugins/*/; do [ -d "$d" ] || continue; n=$(basename "$d"); rm -rf "$HOME/.hermes/profiles/anna/plugins/$n"; cp -r "$d" "$HOME/.hermes/profiles/anna/plugins/"; done
  [ -f "$DIST/SOUL.md" ] && cp "$DIST/SOUL.md" "$HOME/.hermes/profiles/anna/SOUL.md"
fi

# seed memories (USER_OWNED_EXCLUDE — tidak ikut hermes install/update, seed bila kosong)
if [ -d "$DIST/memories" ]; then
  mkdir -p "$HOME/.hermes/profiles/anna/memories"
  for f in MEMORY.md USER.md; do
    if [ -f "$DIST/memories/$f" ] && [ ! -s "$HOME/.hermes/profiles/anna/memories/$f" ]; then
      cp "$DIST/memories/$f" "$HOME/.hermes/profiles/anna/memories/$f"
      echo "ANA: seed memories/$f"
    fi
  done
fi
fi # _process_profile

chmod +x start.sh install.sh
echo "ANA: siap. jalan: ./start.sh (port ${ANA_PORT:-8730})"
exec ./start.sh
