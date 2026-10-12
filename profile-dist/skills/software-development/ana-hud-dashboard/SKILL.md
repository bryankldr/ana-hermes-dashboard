---
name: ana-hud-dashboard
category: software-development
description: Use when working on ANA HUD Dashboard project.
version: 1.1.0
author: bryankldr
license: MIT
metadata:
  hermes:
    tags: [ANA, HUD, Dashboard, Flutter, Hermes]
    related_skills: [simoge-business, maplibre-running-evals]
---

# ANA HUD Dashboard - Project Skill

## Project Location
**Portable root** — gunakan `$ANA_WORKDIR` (set via `.env` di tiap mesin) atau fallback `$HOME/ana-hermes-dashboard`.

> ⚠️ **CRITICAL**: Jangan hardcode `/home/bryankldr/...` di skill/config/script. Resolve via `ANA_WORKDIR` env atau `Path(__file__).resolve().parents`.

## Quick Commands
```bash
cd "$ANA_WORKDIR"
./start.sh                 # Start server on 0.0.0.0:8730 (picks interpreter with websockets/edge_tts + discovers hermes serve WS)
python3 smoke.py           # Run 121 E2E checks
python3 test_services.py   # Run 24 service assertions
node --check ui/src/main.js # Validate JS syntax
```

## Key Files
- `server.py` — FastAPI dashboard (port 8730), SSE + WS, serves `ui/` static, `api/` endpoints
- `start.sh` — bootstrap: venv, deps, python `server.py`
- `ui/` — Flutter web build output (`index.html`, `main.dart.js`, assets)
- `profile-dist/` — **distributable skill package** untuk deploy ke mesin lain (copy ke `~/.hermes/profiles/anna/skills/`)
- `.env` — `ANA_PORT=8730`, `ANA_TOKEN=...`, `ANA_WORKDIR=/abs/path/ana-hermes-dashboard`
- `smoke.py` / `test_services.py` — E2E regression

## Environment (`.env`)
```
ANA_PORT=8730
ANA_TOKEN=<generate via: openssl rand -hex 32>
ANA_WORKDIR=/abs/path/to/ana-hermes-dashboard  # override bila bukan $HOME/ana-hermes-dashboard/
```

## Git Workflow
```bash
cd "$ANA_WORKDIR"
git add -A
git commit -m "type(scope): description"
git push origin main
```

## Architecture
```
Flutter web (ui/)  <--WS/SSE-->  FastAPI server.py:8730  <--skills/tools-->  ANNA profile
    ^                                                         |
    |-- static files (index.html, main.dart.js, assets)       |-- simoge-business (SIMOGE BI)
                                                              |-- maplibre-* (spatial eval)
                                                              |-- ana-hud (this skill)
```

## Dev Loop
1. Edit `server.py` / `ui/` → rebuild flutter (`flutter build web --release`)
2. `./start.sh` restarts server (auto-reload via `watchfiles`)
3. `python3 smoke.py` verifies 121 checks (< 30s)

## Deploy to New Machine
```bash
git clone <repo> "$ANA_WORKDIR"
cp .env.example .env  # edit ANA_TOKEN, ANA_WORKDIR, ANA_PORT
./start.sh            # server up on 0.0.0.0:8730
cp -r profile-dist/skills/software-development/* ~/.hermes/profiles/anna/skills/software-development/
```

## Related Skills
- `simoge-business` — SIMOGE BI engine (petak, penyadap, produksi, drum)
- `maplibre-running-evals` — spatial map eval procedure
- `ana-briefing` — daily briefing from vault
- `zk-vault-ops` — Obsidian ZK + Hermes sync
