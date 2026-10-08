---
name: ana-hud-dashboard
category: software-development
description: Use when working on ANA HUD Dashboard project.
---

# ANA HUD Dashboard - Project Skill

## Project Location
**Fixed path:** `<dashboard-repo>`

> ⚠️ **CRITICAL**: Always use absolute path `<dashboard-repo>`
> NEVER use `./<path>/...` (leading dot breaks cd)

## Quick Commands
```bash
cd <dashboard-repo>
python3 server.py          # Start server on 127.0.0.1:8730
python3 smoke.py           # Run 121 E2E checks
python3 test_services.py   # Run 24 service assertions
node --check ui/src/main.js # Validate JS syntax
```

## Server Management
```bash
# Check if running
ps aux | grep -E "server.py|python.*8730" | grep -v grep

# Kill if stuck
pkill -f "python3 server.py"

# Restart clean
cd <dashboard-repo> && ANA_OPEN=0 exec python3 server.py
```

## Project Structure
```
ana-hermes-dashboard/
├── server.py          # HTTP orchestrator (port 8730)
├── services.py        # Panel data sources (no HTTP)
├── terminal.py        # PTY backend
├── commands.py        # Slash commands
├── runtime.py         # Runtime/subprocess
├── voice.py           # Voice backend
├── smoke.py           # 121 E2E/security checks
├── test_services.py   # 24 service tests
├── layout.json        # Local only (gitignored)
├── state.json         # Local only (gitignored)
├── .ana_token         # Local only (gitignored)
├── .ana_mode          # Local only (gitignored)
├── .gitignore         # Excludes local artifacts
├── ui/
│   ├── index.html     # FUI markup
│   ├── src/main.js    # UI orchestration
│   ├── src/core/      # LayoutManager, API client, bus
│   ├── src/utils/     # DOM helpers, escaping
│   ├── src/terminal.js # PTY UI module
│   ├── styles/        # hud.css, layout.css, tokens.css
│   └── vendor/        # xterm.js (vendored offline)
```

## Common Pitfalls (DOCUMENTED TO PREVENT REPEAT)

| Pitfall | Cause | Fix |
|---------|-------|-----|
| `cd: ./home/... No such file` | Leading dot in path | Use `/home/...` not `./home/...` |
| Port 8730 in use | Old server not killed | `pkill -f "python3 server.py"` then restart |
| Token 401 | `.ana_token` not sent | Include `x-ana-token` header |
| Equalizer not animating | `.speaking` class missing | Call `startEqualizer()` + `els.hud.classList.add('speaking')` |
| Panel options empty | `loadVoices()` not awaited | `await Promise.allSettled([loadVoices(), ...])` before `initPanelOptions` |
| `ensurePanel` replaces content | Returns early if exists | Updated to update `.panel-body` in place |
| Voice preview 401 | Missing auth header | Use `api.headers({...})` which includes token |

## Git Workflow
```bash
cd <dashboard-repo>
git add -A
git commit -m "type(scope): description"
git push origin main
```

## Test Verification Checklist
- [ ] `python3 smoke.py` → `PASS 121 checks`
- [ ] `python3 test_services.py` → `all checks passed`
- [ ] `node --check ui/src/main.js ui/src/terminal.js` → `JS OK`
- [ ] Browser: `http://127.0.0.1:8730/` loads without console errors
- [ ] Voice preview plays audio + equalizer animates
- [ ] Terminal opens/closes correctly
- [ ] Panel options toggles work & persist in layout.json

## Key Files to Reference
- `server.py:14` — `baseUrl` from `API_BASE_URL` env
- `ui/src/main.js` — Main UI logic, `loadVoices()`, `previewVoice()`
- `ui/src/utils/dom.js` — `ensurePanel()` (updates body in place)
- `ui/src/core/layout.js` — `LayoutManager` with `setPanelEnabled()`
- `ui/styles/hud.css` — `.panel-options-menu`, `.speaking` styles
- `smoke.py` — Canonical E2E test (read for API contracts)

## Current State (as of last commit)
- 15 content panels in Options menu (14 + TERMINAL)
- All toggles persist to `layout.json`
- Equalizer: only animates during `.speaking`
- Voice preview: ElevenLabs → browser fallback
- Vertical overflow: expected (unlock/drag/save to reposition)
- Horizontal overflow: FIXED (0)
- All tests passing: 121/121 smoke, 24/24 services