#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
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
PY=$(echo ~/.hermes/tools/python-*/bin/python3 | head -1); [ -x "$PY" ] || PY=python3
"$PY" -c "import websockets, edge_tts, pymysql, pandas" 2>/dev/null || "$PY" -m pip install --user websockets edge_tts pymysql pandas

DIST="$PWD/profile-dist"
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

chmod +x start.sh install.sh
echo "ANA: siap. jalan: ./start.sh (port ${ANA_PORT:-8730})"
exec ./start.sh
