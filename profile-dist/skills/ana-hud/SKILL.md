---
name: ana-hud
description: Use when customizing ANA HUD dashboard or persona modes.
version: 1.0.0
---

# ANA HUD

ANA Live HUD at `~/ana-hermes-dashboard` (canonical; legacy `~/PROYEK_2026/ana-hermes-dashboard`) — formerly `jarvis-hermes-dashboard`. Hermes Agent face on port 8730, profile `anna`, workdir `$ANA_WORKDIR`, permission `normal`. Inherits Hermes tools/skills/memory/browser/MCP/connectors via `hermes chat -Q -q`.

## When to Use

- Working on the ANA HUD dashboard: adding/changing panels, styles, endpoints, or wiring in `$ANA_WORKDIR` (default `~/ana-hermes-dashboard`).
- Switching persona mode (asisten ↔ coding), voice, or session for the HUD.
- Debugging a HUD symptom: stuck `RUNNING`, empty `HTTP 200`, clipped or invisible panels, lost session, silent voice.
- Committing, renaming, or pushing the dashboard repo.
- Before any layout edit, read `references/fui-layout.md`; before committing or pushing, read `references/git-workflow.md`.

## Invariants

- Profile ID is `anna`, never `ANA`/`default` — `HERMES_PROFILE` must be `anna`; `ANA` is only display name. Setting it to `ANA` causes `profile ANA not found` on `hermes chat -q`.
- Env prefix is `ANA_*` (`ANA_PORT`, `ANA_WORKDIR`, `ANA_TOKEN`/`X-Ana-Token`, `ANA_PERMISSION`, `ANA_TIMEOUT`, `ANA_MODE`), not `JARVIS_*`.
- Token rotates per page load via `__ANA_TOKEN__` in `ui/index.html` — refresh page after server restart.
- Every HUD input (chat bar, Transmit, voice) hits `POST /api/run` with `X-Ana-Token` + `Origin`/`Host` checks — same Hermes session (`SESSION["id"]`) so vault and memory stay consistent.

## Persona: Bi-Modal

`persona.md` has two modes injected by `server.py:get_mode()` as `[MODE: asisten]` / `[MODE: coding]` overlay:

- **asisten** (VOICE/TTS — for ears): 1-2 sentences, no markdown/code/tables/bold/emoji, spoken aloud.
- **coding** (chat tulis — for screen): Ana Agent MAX Technology verbatim — direct, no filler, prefer verified facts, inspect → smallest safe change, report `Changed/Verified/Remaining`. Markdown/code/tables/paths allowed. Still Indonesian by default.

`server.py` reads `persona.md` on every `persona()` call, so editing it is live without restart. Mode persists in `ROOT/.ana_mode` (file) with `ANA_MODE` env fallback.

### Menyusun jawaban voice (komposisi, bukan style)

Aturan persona mengatur **bentuk** jawaban; ini mengatur **cara jawaban itu dirakit** sebelum masuk jalur TTS. Semua kalimat voice dibacakan karakter demi karakter, jadi satu token asing = satu kata aneh yang terdengar.

- **Rakit kalimat dari ringkasan kecil yang sudah dicetak, bukan dari output mentah alat.** Cetak total + top-N ke terminal dulu, baru tulis kalimat dari angka itu. Menyalin output mentah membuat TTS membaca sisa nama kolom, `None`, atau ID terpotong.
- **Ejaan kalimat literal sebelum dikirim.** Salah ketik jatuh persis ke audio. Tulis angka seperti yang diucapkan: "seratus", "13,5 persen", "1.007,98 hectare" — bukan "Hundred", bukan angka nol depan yang bukan gaya Indonesia.
- **Jawab intent yang ditanya, bukan intent giliran sebelumnya.** Kalimat sisa dari giliran lain yang bocor ke jawaban (mis. pertanyaan nama dijawab dengan status peta) adalah bug, bukan pilihan gaya. Isi jawaban harus dibangun ulang tiap giliran, tidak pernah memakai blok teks yang sudah jadi.
- **State aktif dasbor tidak bocor ke kalimat.** Template peta atau grafik yang sedang tampil hanya relevan kalau pertanyaan menyangkut peta atau grafik.
- **Panjang 1–2 kalimat; detail ada di grafik.** Kalau detail butuh lebih dari dua kalimat, buka chart dan sebut trend utamanya saja.

Skrip query data + jebakan engine ada di skill terpisah `simoge-business`; skill itu user-owned, jadi aturan komposisi ini disimpan di sini.

### Laporan bisnis efektivitas (panel laporan)

Bangun laporan dengan urutan tetap: query agregat, turunkan top-N, tulis file, tampil, verifikasi.

1. Query agregat via CLI langsung (satu template satu call, `workdir` dashboard): `petak_effectiveness tahun=2026` untuk partisi bongkor/kurang/terpenuhi, `petak_count` + `petak_area` untuk total/ha/rasio, `bongkor_per_wilayah level=kode_bkph` untuk fokus wilayah, `produksi_year_to_date` untuk YTD. Output besar selalu redirect ke `/tmp/*.json` baru dibaca — terminal memotong JSON panjang.
2. Turunkan top-N di Python dengan sort eksplisit: terpenuhi urut `luas_andil` desc, bongkor urut `luas_baku` desc — jangan andalkan urutan template karena template agregat tak menjanjikan sort bisnis.
3. Susun `pages` via `write_file /tmp/*.py` yang memanggil `show_report(title, subtitle, pages, evidence, meta)` — jangan rangkai JSON `pages` multi-halaman lewat argumen CLI `pages="$P"`, quoting shell rapuh dan pecah di tengah.
4. `show_report` langsung menimpa seluruh state — jangan `hide_report` dulu walau `visible:true`; `laporan` (status) hanya untuk verifikasi sesudah tampil, bukan syarat sebelum tampil.
5. Verifikasi `ana_chart_tool.py laporan` harus `visible:true` + `n_pages` sesuai sebelum menjawab; klaim "tampil" tanpa ini adalah dusta.
6. Blok laporan hanya `para` + `kpi` + `table` + `note` (+ `evidence` terpisah berisi statement/source/value) — chart canvas tak tercetak rapi ke PDF.

## Mode Switching — 3 Paths (all must stay in sync)

1. **HUD button** `modeBtn` beside `💬 Chat` ↔ `VOICE` in missionbar — `GET /api/mode` on boot, `POST /api/mode {mode}` on click, toggles `coding`/`asisten`, persists to `.ana_mode`.
2. **Slash** `/mode [asisten|coding|status]` in `commands.py` (`_CMD` regex + handler) — resolves the **live** module via `sys.modules.get("server") or sys.modules.get("__main__")` and calls its `set_mode()`. Never a bare `import server`: under `python3 server.py` that loads a second copy whose `MODE` dict is a different object, so the command reports success and nothing changes.
3. **Natural language** in `server.py:_stream_run` before command matrix — matches `mode asisten|coding` or `ganti.*mode|ubah.*mode|switch.*mode`, sets mode and returns NDJSON directly without calling Hermes.

Verify after change: `curl -s http://127.0.0.1:8730/api/status` and HUD button label.

## Chat in RESPONSE

- Input lives in `#responseWrap .chatbar` (`#chatInput` + `#chatSend`), not in left uplink. `Enter` sends, `Shift+Enter` newline, auto-resize 36–120px.
- Shares `armed` payload (`#input.dataset.cmd`) with Command Matrix — e.g. `/goal` stays armed for next chat turn.
- Logs as `SEND transmit (chat): ...` and streams deltas to `#response` + TTS same as Transmit.
- `💬 Chat` button focuses `#chatInput` and scrolls `#responseWrap` into view.

## FUI HUD — 1128×622 Pixel-Faithful Composition

Rewritten from 3-column grid to cinematic FUI command-center layout per `Autonomous_AI_Assistant_HUD_Skill` spec:

```
ui/
├── index.html              # FUI shell — all panels inline, mounts src/main.js
├── backup/                 # pre-refactor app.js/index.html/styles.css (gitignored)
├── styles/                 # Fase A CSS split — all six files are linked from index.html
│   ├── tokens.css          # design tokens (:root custom properties)
│   ├── layout.css          # rails, columns, frame
│   ├── hud.css             # core FUI styles — panels, dials, telemetry, core
│   ├── components.css      # buttons, chips, rows
│   ├── panels.css          # response, missionbar, voice, log panels
│   ├── workspace.css       # workspace grid
│   └── responsive.css      # ≤1200 / ≤900 / ≤600 breakpoints
└── src/
    ├── main.js             # boot + agent state + panel wiring (still the fat file, ~1030 lines)
    ├── terminal.js         # pty terminal, own DOM + session maps + stream reader
    ├── core/
    │   ├── bus.js          # shared `state` only — the `bus` EventBus has zero callers
    │   ├── api.js          # ApiClient — all fetch wrappers
    │   └── layout.js       # LayoutManager — drag/resize/lock, persists via /api/layout
    ├── utils/
    │   ├── dom.js          # ensurePanel() — the ONLY way to build a panel
    │   └── helpers.js      # now/rid/esc/cleanForSpeech
```

`components/` and `services/pipeline.js` were deleted — all pre-FUI dead code with zero imports.
`ui/vendor/` holds vendored xterm (see `## Vendored Assets`).

Python side: `server.py` (HTTP transport only), `services.py` (panel data sources), `test_services.py`, `smoke.py` (end-to-end checks against a live server, run as `ANA_TOKEN=<token> python3 smoke.py`), plus `runtime.py`, `commands.py`, `voice.py`, `terminal.py` (PTY, dependency-free). Per-file ownership table lives in `## UI Architecture` below.

### FUI Layout Zones

Top dials band (8 instruments) over three columns — left rail 220px, central core 470×370px
octagonal, right rail 240px — then a bottom telemetry band (CPU/RAM/equalizer). Rails scroll.

Component mount table, design tokens, the `setAgentState()` state-machine table, and the catalogue
of user-flagged layout regressions: `references/fui-layout.md`.

### ANA Live — Real-time Interaktif (Fase A-D)

Empat panel yang hilangkan "nunggu buta" — dipasang bersama saat user bilang `semua`:

- **Fase A Live Progress** — `ui/src/main.js: ensureProgressPanel/progressReset/progressStep/progressDone` + `ui/styles/hud.css #progressPanel`. `transmit()` panggil `progressReset(msg)`, `handle()` panggil `progressStep()` di `status`/`tool use|result`/`delta`/`latency` dan `progressDone(ok)` di `complete`/`error`, `setAgentState()` sinkron pipeline+matrix. Bar `.progress-bar` + `.progress-steps` (ETA 400ms tick, cancel `Esc` via `POST /api/cancel`).
- **Fase B Code Diff Viewer** — `showCodeDiff(title,diff)` buka `#codeViewer.live` saat `tool result` berisi `diff --git`/`+++ ` atau `name ~ write_file|patch|edit`. Highlight `+` hijau / `-` merah, tombol Apply/Dismiss. Wajib cek `out.length` truncate 6k.
- **Fase C Mission Kanban** — `refreshKanban()` → `GET /api/missions` (`commands.load()` → `{tasks,missions,goal}`) render `#missionKanban #kanbanGrid` 2 kolom OPEN/DONE, klik card → `transmit(title)`. Register `LayoutManager.register('missionKanban')`, polling 6s + refresh on `complete`.
- **Fase D Vault + AVD** — `refreshVault()` → `GET /api/vault` (vault path, daily_count, `SKILL/skill_note.md` exists+preview), `refreshAvd()` → `GET /api/avd` (avd list, `adb devices`, `sys.boot_completed`) + `POST /api/avd {start|stop}` (`~/Android/Sdk/emulator/emulator -avd Pixel_9 -gpu host -no-snapshot-load` / `adb -s emulator-5554 emu kill`). Panel `#vaultPanel`/`#avdPanel`, polling 7s, register layout.
- **Server** — `server.py: _vault_status()`, `_avd_status()`, `GET /api/vault|/api/avd|/api/missions`, `POST /api/avd`. `GET /api/missions` auth sama dengan `/api/vault`.
- **ApiClient** — `api.js: getVault()`, `getAvd()`, `avdAction(action)`, `getMissions()` (semua `X-Ana-Token`).
- Verify HUD interaktif: `python3 -m py_compile server.py && node --check ui/src/main.js`, `curl -s http://127.0.0.1:8730/` cek `ana-token`, hard refresh `Ctrl+Shift+R` untuk `main.js`/`hud.css` cache.

## Mission Control — Projects & Briefing

- `GET /api/projects` scans `runtime.WORKDIR` for `.git` dirs, returns `{projects:[{name,path,branch,last_commit,dirty,dirty_files}], workdir}`. `GET /api/briefing` reads vault `OBSIDIAN_VAULT_PATH/10 Daily/*.md` latest note and extracts `## Briefing` section. Both require `X-Ana-Token`.
- HUD left column has project cards (`#projectList`, click → `sendPrompt('Periksa status repo …')`) and briefing (`#briefingContent`). Connected Tools chips (`#toolsList`) below. Logic in `ui/src/main.js:refreshProjects()`/`refreshBriefing()` called at boot.
- Git repos without initial commit return `fatal: your current branch 'main' does not have any commits yet` on `git log` — map to `"git error"` (`fatal:`/`error:` substring check) instead of leaking raw stderr to HUD.

## Cron — Proactive Briefing

- `ana-morning-briefing` (`7fc97b2659e4`) `0 8 * * *` `deliver=all` via skill `ana-briefing` — saved to `10 Daily/YYYY-MM-DD.md` as `## Briefing`. CLI-created crons default `deliver=local` (no notification); update to `deliver=all` after create. Worker needs `ruamel.yaml` in system python3.12 (`/usr/bin/python3 -m pip install ruamel.yaml --break-system-packages`) or `ModuleNotFoundError: No module named 'ruamel'` blocks dispatch.

## Voice — Indonesian Naturalness

- Default ElevenLabs voice is Rachel `21m00Tcm4TlvDq8ikWAM` with `ELEVENLABS_MODEL=eleven_multilingual_v2` — `eleven_turbo_v2_5` is English-only and makes Indonesian flat. Indonesian prosody settings: `stability 0.36`, `similarity_boost 0.78`, `style 0.32`.
- STT (`scribe_v1`) must send `language_code=id` in the multipart body — without it Scribe auto-detects `en` and mangles Indonesian. STT still requires `ELEVENLABS_API_KEY`; there is no free STT.
- Free TTS (no key): `edge-tts` via Microsoft (`id-ID-GadisNeural` female, `id-ID-ArdiNeural` male) — installed in both hermes python (`~/.hermes/tools/python-3.14.7+*/bin/python3 -m pip install edge-tts`) and the project venv. `voice.py:available()` is always `True`, `voice_id()` falls back to `FREE_DEFAULT`, `speak()`/`speak_with_voice()` use `async edge_tts.Communicate(...).save(tmp)` → mp3 bytes. Switching voices via `POST /api/voice` is audible even without a key. Keep ElevenLabs config in `.env` so adding `ELEVENLABS_API_KEY` upgrades to 13 curated voices without code change.
- Browser fallback is only for `SpeechRecognition` (`lang='id-ID'`) and last-resort preview — `SpeechSynthesisUtterance.lang='id-ID'` `rate 1.0`/`pitch 1.0` via `getVoices()` + `onvoiceschanged`. Do not rely on browser TTS for main voice; `edge-tts` is the free fix.

## Voice Picker — Hybrid (Free edge-tts vs ElevenLabs)

- `voice.py` holds two sets: `FREE_VOICES` (`id-ID-GadisNeural` female, `id-ID-ArdiNeural` male via `edge-tts`) and `CURATED_ID_VOICES` (13 Indonesian ElevenLabs: Sikedewi `yLyL4E4r0QfLyYpCwPir` paling natural neutral 30-35th, Arunika `o5s6XRBkPSTD4syv6mZg`, Zaak, Livna, Aita, Putri Maharani, Meraki, Mizani, Mahaputra, Pratama, Ganesh, Youvandra, Zephlyn + Rachel fallback). `curated_voices()` returns free set when `ELEVENLABS_API_KEY` empty, curated when present. Adding the key upgrades from 2 → 13 without code change.
- `GET /api/voices` returns `{current, model, available, voices}` where `available` is always `true` (edge-tts) — do not gate UI on it for TTS. `POST /api/voice {voice_id}` validates against union of free + curated + Rachel (`^[A-Za-z0-9_\-]{8,60}$`), persists to `.env` `ELEVENLABS_VOICE_ID=`, updates `os.environ` live. `POST /api/voice-preview {voice_id, text}` calls `voice.speak_with_voice()` — free IDs use `edge-tts` mp3, ElevenLabs IDs use API if key present else fall back to mapped free voice. Always returns `audio/mpeg` when edge-tts is installed; no 500 when key is missing.
- HUD `voicePanel` in `ui/index.html` right column (above Action Log) — `#voiceSelect` dropdown, `#voicePreview` / `#voiceApply` buttons, `#voiceDesc` + `#voiceMode` badge. `main.js:loadVoices()` fetches `/api/voices` 800ms after boot, inserts Rachel first then curated/free, shows `mode` badge as model name. `previewVoice()` tries `/api/voice-preview` then falls back to `speechSynthesis id-ID` if server returns error. `applyVoice()` posts `/api/voice` and reloads list.

## Desktop Icons

Generate three `.desktop` files — validate with `desktop-file-validate`:

- `~/Desktop/ANA HUD.desktop` + `~/.local/share/applications/ana-hud.desktop` + `~/.config/autostart/ana-hud.desktop`
- `Exec` must be direct path `~/ana-hermes-dashboard/start.sh` (legacy `~/PROYEK_2026/ana-hermes-dashboard` kept for compat) — `bash -c '...'` with quotes fails validation (reserved `'`).
- `start.sh` does `exec python3 server.py`; autostart uses `X-GNOME-Autostart-enabled=true`.

## Session Selector — Grouped Dropdown

- `GET /api/sessions` returns `{groups: {today, yesterday, last_week, older}, current}` — runs `hermes sessions list` subprocess, parses output, groups by `last_active` field.
- `POST /api/session {session_id}` sets `SESSION["id"]` (or `null` for new session) — next `/api/run` uses selected session.
- UI: `#sessionSelect` dropdown with `<optgroup>` labels, `#sessionNew` button (clears session), `#sessionRefresh` button. `refreshSessionSelector()` in `main.js` populates grouped options.
- **Parser pitfall:** `hermes sessions list` outputs `last_active` as `"13m ago"`, `"2h ago"`, `"3d ago"`, `"just now"`. Parse with substring checks (`"m ago"`, `"h ago"`, `"d ago"`); `int("13m")` raises `ValueError` and falls through to `"older"`.
- **Grouping bug that shipped and was only caught by the test suite:** the old grouper scanned tokens with `.isdigit()`, but `"1d ago".split()` is `["1d","ago"]` and `"1d".isdigit()` is `False`, so `days` stayed `0` and the `yesterday` bucket could never fill. `services._age_days()` now regexes `^(\d+)\s*d` and returns `None` when there is no day count. This means the documented "1d ago → yesterday" rule had never actually worked before 2026-09-29.
- **Grouping rules:** `just now` / `Nm ago` / `Nh ago` → today; `1d ago` → yesterday; `2-7d ago` → last_week; else → older.

## Session Persistence — `hermes chat --resume`

ACP (Agent Context Protocol) is for editors (VS Code/Zed/JetBrains) via stdio — NOT for web dashboards. The correct approach for a web HUD is subprocess `hermes chat --resume <session_id>`.

**Root cause of "new session every message":** `runtime.py` only set `emitted_session` from stderr parsing. If stderr buffering races or session_id appears in stdout, the ID is lost → `SESSION["id"]` stays `None` → next run starts fresh.

**Fix (3 files):**

1. `runtime.py` — yield `dict(t="session", session_id=candidate)` when session_id detected (stdout + stderr paths)
2. `server.py` — save `SESSION["id"]` immediately on `t="session"` event (not only on `t="complete"`)
3. `ui/src/main.js` — handle `t="session"` event → update `stSess` + `intelLog()` + `log()`

**Type annotation:** `SESSION: dict[str, str | None] = {"id": None}` — Pyright rejects `str` assigned to `None` without explicit union type.

**Verify:** Run two messages in HUD — second should show same session_id in Intelligence Surface (`🔗 SESSION: ...`). `/new` clears → next run = new session.

## Pitfalls

- Rename JARVIS→ANA with case-sensitive replace across `server.py`, `runtime.py`, `commands.py`, `voice.py`, `ui/*`, `install.sh`, `start.sh`, `.env` — then `rm -rf __pycache__` and verify `grep -r JARVIS` is 0.
- `server.py:MODE` defs must appear before `persona()` — otherwise `get_mode()` is undefined at import.
- `persona.md` Format section must be split per mode — a blanket `No markdown` breaks coding agent output.
- Killing old server needs `pgrep -f "[s]erver\\.py"` + `kill <PID>` (never `pkill -f server.py` — kills own SSH) + `fuser -k 8730/tcp` — stale PID leaves port busy.
- Commands that answer locally (`/mode`, `/commands`, `/status`) must emit `delta`+`complete` NDJSON without Hermes call — otherwise mode switch waits for model.
- `server.py:_stream_run` must not call `send_response(200)` before checking natural-language mode switch — double header causes empty `HTTP 200` body and HUD hangs on `RUNNING`. Check `_low`/`_m` first, then send single header per branch.
- `server.py` `POST /api/voice` and `/api/voice-preview` handlers mutate `.env` and call ElevenLabs — use `re.match` for voice_id so `import re` must be at top of `server.py`.
- `/api/voices` is a `GET` endpoint without host token gate in current impl — HUD `main.js` sends `X-Ana-Token` anyway; verify with `curl -H "X-Ana-Token: $TOKEN"` or fix gate if 403 appears after restart.
- Empty `HTTP 200` with zero NDJSON body (HUD stuck on RUNNING, `curl /api/run` returns `''`) means `server.py:_stream_run` sent headers twice or `hermes chat` subprocess never yielded — inspect `/tmp/ana.log` for traceback, verify `commands.handle` returns a local `delta`+`complete` without Hermes, and ensure `import re` exists if any handler uses `re.match`.
- Multiple `python3 server.py` PIDs can hold `127.0.0.1:8730` after directory move — `ss -tlnp | grep 8730` may still show old PID after `fuser -k`; loop `kill -9 <old>` + `fuser -k 8730/tcp` + `sleep 1` until empty before relaunch. Background exits with `SIGKILL (-9)` are expected during move, not errors.
- Raw `re.search` with `\\s` in a triple-quoted helper injected via `write_file` can split across lines — produces `SyntaxError: unterminated string literal`. Use single-line `r"##\\s*Briefing\\s*\\n(.*?)(?=\\n##\\s|\\Z)"` and `py_compile` before restart.
- **TOOLS row removed from AGENT STATUS** — user explicitly asked to drop it. Keep it out of `index.html` stat-rows, the `stTools` ref in the `main.js` els object, and `loadStatus()`. Tools still shown in Connected Tools (`#toolsPanel`).
- FUI layout regressions (rail scroll, minimum type size, 1.5x/0.75x font scaling ratio, interactive-not-decorative panels, event-log header, browser-cache diagnosis) are catalogued in `references/fui-layout.md` — read it before any layout change.
- ACP (Agent Context Protocol) is for editors via stdio, NOT web dashboards. For web HUD session persistence, use `hermes chat --resume <id>` subprocess. If user asks about ACP, explain the distinction and use subprocess approach.
- Session persistence fix requires 3-file coordination: `runtime.py` yields `t="session"` event, `server.py` saves on that event (not only on `complete`), `main.js` handles it. Fixing only one file = session still lost.
- `SESSION` dict needs explicit type annotation `dict[str, str | None]` — Pyright rejects `str` assigned to `None` value without union type.

## Version Control

Repo: `git` at `~/ana-hermes-dashboard` (legacy `~/PROYEK_2026/ana-hermes-dashboard`), branch `main`. Always-on rules:

- **Split commits by intent, not by file type.** Pure refactor (module/CSS split, zero behavior change) in its own commit; features in the next. One giant commit over weeks of mixed work cannot be reverted granularly.
- **Check `git config user.name` / `user.email` before the first commit** — unset identity aborts the commit with no partial state, but it wastes a full `git add` cycle.
- **Scan for secrets before staging**: `git ls-files --error-unmatch .env` must fail (proves `.env` untracked) and a grep for `sk_live|sk-|ghp_|gho_|xox[bpsr]-|AIza…|eyJ…` over the new paths must return nothing. `ui/index.html` carries a `__ANA_TOKEN__` placeholder, never a live token.
- **Ignore local state, keep the repo lean**: `layout.json` (LayoutManager geometry), `state.json`, `.ana_mode`, `ui/backup/`, screenshots, and any vendored spec folder go in `.gitignore` — the user asked for these to stay local.
- **Brand rename is not done until comments are renamed too.** `git grep -ril <oldname>` after the file-level sweep; stale brand strings hide in `// comments` and CSS section headers where nobody looks. Then `node --check` the touched JS.
- `git push --dry-run` with `GIT_TERMINAL_PROMPT=0` detects auth state without hanging on a username prompt. Push is blocked until the user supplies credentials — never ask for a token in chat, hand them the setup recipe instead (see `references/git-workflow.md`).
- **`404` from the GitHub REST API is not proof a repo is missing** — unauthenticated requests get `404` (not `403`) for private repos. Confirm with `git ls-remote origin`, which uses your credentials and is the only authoritative read.
- **Retargeting `origin` to a different repo leaves a stale `refs/remotes/origin/main`** pointing at the old repo's SHA — phantom ahead/behind, and `--force-with-lease` computes its lease against a foreign commit. `git update-ref -d refs/remotes/origin/main && git fetch origin` before any rewrite.
- **Squashing to a clean single commit: `git reset --soft <root>~1` cannot work when `<root>` has no parent** — a root commit is the usual foundation of a repo you forked or renamed, so verify with `git rev-list --parents -n 1 <commit> | wc -w` (returns `1` = root) and use `git checkout --orphan` + `git reset` + `git add -A` instead. A repo created via the GitHub web UI also ships an auto-generated `Initial commit` README, so the first push there needs `--force-with-lease`.
- **Adding an SSH key is a user-side step.** Generate the key, print the pubkey, wait. The headless browser is not logged into GitHub and you must never log in as the user.
- **`ls-remote` matching your local SHA proves a ref, not the tree.** When the claim matters (brand removed, file excluded), `git clone --depth 1` into scratch and grep the actual content.

Dead-file pitfall: creating `ui/src/**/*.js` support files without adding the matching `import` in `main.js` leaves them unreferenced. After any module split, verify each new file is actually imported — `grep -rn "<name>.js" ui/index.html ui/src/main.js`.

## Dashboard Location

- Canonical: `~/ana-hermes-dashboard` (legacy `~/PROYEK_2026/ana-hermes-dashboard`). `ANA_WORKDIR=~/ana-hermes-dashboard`, `ANA_PERMISSION=normal`. Fase 3 integrations (himalaya, google-workspace) are on-demand.
- GitHub: `git@github.com:bryankldr/ana-hermes-dashboard.git` (private, SSH auth, `git user.name=bryankldr` / `user.email=bryankldr@gmail.com`). Squashed to one clean commit — history contains no JARVIS.

## Server Architecture (post-refactor, 2026-09-29)

`server.py` (561 lines) = HTTP transport only. `services.py` (207 lines) = panel data sources, HTTP-free and import-safe so it can be unit tested without booting a server. `test_services.py` (114 lines) = 24 assert-based checks, no framework — run `python3 test_services.py`.

- `services.py` owns: `scan_projects`, `list_sessions`, `load_briefing`, `vault_status`, `avd_status`, `avd_action`
- `avd_action(action)` returns `(ok, body)` where `ok is None` means bad action → HTTP 400
- `docs/REFACTOR_PLAN.md` is a **stale DRAFT** — never approved, and its 3-column target predates the FUI rewrite. Do not follow it literally; it also proposed moving runtime/voice/commands into `app/services/`, which is pure file-move churn since those are already separate top-level modules.
- Refactor rule that paid off: extract *panel data sources* out of the handler class, not files into folders. Testability is the payoff, not tidiness.

## UI Architecture (post-refactor, 2026-09-29)

`main.js` (~1030 lines) = boot + agent state + panel wiring. Modules:

| File | Lines | Owns |
|---|---|---|
| `ui/src/main.js` | 1000 | init, transmit/handle, agent state machine, progress, intel surface, panels |
| `ui/src/terminal.js` | 133 | pty terminal: own DOM + session maps + stream reader, binds Ctrl+` |
| `ui/src/core/api.js` | 126 | every fetch wrapper |
| `ui/src/core/layout.js` | 244 | LayoutManager drag/resize/lock |
| `ui/src/core/bus.js` | 25 | `state` only — the `bus` EventBus has zero callers |
| `ui/src/utils/dom.js` | 51 | `ensurePanel()` |
| `ui/src/utils/helpers.js` | 11 | `now`/`rid`/`esc`/`cleanForSpeech` |

## Panel Options Menu (added 2026-09-29)

`initPanelOptions(layout)` in `main.js` builds a dropdown from every `LayoutManager.items` key plus `termPanel` and `voicePicker`. Each panel gets a checkbox; unchecking hides the panel via `style.display = 'none'` and persists the disabled list to `layout.json` (`disabled: []`). The Options button (`⚙`) sits in `topControls` between Terminal and Lock/Unlock.

**Timing bug fixed:** `initPanelOptions` was originally called before the `topControls` block created `optBtn`, so `document.getElementById('optBtn')` returned null and the menu never built. Fix: moved the call to the end of `init()`, after the `topControls` block, wrapped in `requestAnimationFrame(() => initPanelOptions(layout))` so the DOM is fully ready.

**Panel titles map** in `initPanelOptions` must include every dynamic panel created via `ensurePanel()`: `voicePicker`, `briefingPanel`, `projectList`, `missionKanban`, `vaultPanel`, `avdPanel`, plus the static panels from `index.html` and `termPanel` from `terminal.js`. Missing entries show raw IDs instead of labels.

**Content vs structural panels:** Only content panels (those with `.panel` class and intrinsic dimensions) should appear in Options. Structural panels (`eventLog`, `codeViewer`, `response`, `chatBar`, `core`, `topControls`, `bottomTelemetry`) are tracked by LayoutManager for position persist but cannot be toggled — they have no intrinsic size and `display: none` collapses them to 0×0. `initPanelOptions` now uses an explicit `contentPanelIds` whitelist instead of all `layout.items` keys.

**Terminal auto-registration:** `terminal.js:createTerminal()` injects `TERMINAL` into the panel-options-list at runtime if the menu already exists. This ensures the terminal appears in Options only after it's first opened, without requiring a full rebuild of the menu.

**Dropdown positioning:** Added `left: auto` to `.panel-options-menu` to prevent the dropdown from rendering off-screen when the Options button is near the right viewport edge. Without it, `right: 0` alone left the menu's left edge unconstrained and it could escape the viewport horizontally.

**Vertical overflow is expected FUI density:** 15 content panels stack to ~1333px in a 577px viewport. Panels below the fold are NOT broken — they exist, toggle correctly, and persist. User must unlock → drag → save to bring them into view. Do not add `overflow-y: auto` to `.hud` — it scrolls `topControls` and breaks the core centering transform.

## Equalizer (fixed 2026-09-29)

Equalizer canvas (`#equalizer` in `#equalizerWrap`, `tele-center`) must ONLY animate when voice is playing — not continuously.

**Fix applied:**
- `startEqualizer()` / `stopEqualizer()` exposed on `window` so `previewVoice()` and `speak()` can call them.
- Animation loop checks `.hud.classList.contains('speaking')` on every frame — auto-stops and clears canvas when class removed.
- Visual upgrade: 16 bars (was 12), smooth sine wave + organic noise, cyan→blue-green hue shift by height, subtle glow on bars >12px.
- All TTS paths call `startEqualizer()` + add `.speaking` class, then `stopEqualizer()` + remove class on end/error: server TTS (`/api/speak`), browser `speechSynthesis`, voice preview (`/api/voice-preview`), and all error branches.
- `initEqualizer()` removed from boot — equalizer stays idle until first voice event.

**Pitfall:** ES module scope hides functions from inline handlers. Without `window.startEqualizer = startEqualizer`, the functions are unavailable to `previewVoice()` which runs in the same module but via event handler closure. Always expose animation controllers on `window` when they need to be called from multiple call sites.

- `ensurePanel({id, title, body, rail})` is the ONLY way to build a panel: createElement + id + innerHTML + append to rail + `LayoutManager.register()`. Because it registers on creation, `init()` no longer needs per-panel `.then(register)` bookkeeping — that was 9 lines that had to be hand-synced and were silently dropped whenever a panel was added.
- `renderTools()` / `renderSystemTelemetry()` are pure renderers. `loadStatus()` does ONE `/api/status` fetch and feeds Agent Status + tools chips + system telemetry from it. Do not re-add separate `refreshTools`/`refreshSystemTelemetry` fetchers.
- `createTerminal({api, token, log, hud, isOpen})` is a factory, not a module-level singleton — main.js passes its own `log` and token. **Auto-registers in Options:** on creation, it injects `TERMINAL` into `#panelOptionsList` if the menu exists, and registers itself with `LayoutManager` (`dataset.rail='right'`).

## Viewport Overflow (LayoutManager, fixed 2026-09-29)

Three separate off-screen bugs, all producing panels the user then could not drag back — a panel outside the viewport cannot be grabbed to move it in. Check all three after any change to `layout.js`.

1. `layout.json` holds geometry captured on some other viewport. `applyCfg()` must reject any config whose `x+w` or `y+h` exceeds the current `.hud` — a panel recorded at `x=1636` was being re-applied on a 1280px window. It is also the *single* place a saved config is applied; `loadConfig()` and `register()` had duplicated that logic.
2. `measure()` must read every rect while the panel is still inside its rail and only then detach, because a re-parented panel fills the full `.hud` width instead of `.left-rail`'s 220px, and `.matrix-cell{aspect-ratio:1}` then inflates `statusMatrix` to 1725px tall. Appending mid-measure is equally wrong in the other direction: it reflows the rail and shifts every unmeasured sibling to the rail top, so all panels report the same `y`.
3. `register()` runs after `measure()` has emptied the rails, so dynamic panels need the per-rail stacking cursor in `this.railCursor`, seeded from the panels `measure()` just placed. Tag each panel with `dataset.rail` before the detach; leave non-rail children (`.core`, `.topControls`, `.eventLog`, `.response`, `.chatBar`) with an empty value or they pollute the cursor.

- **Measure horizontal overflow as "elements whose `getBoundingClientRect().right` exceeds `clientWidth`"**, not `scrollWidth > clientWidth`. `html,body{overflow:hidden}` pins `scrollWidth` to the viewport no matter how far content escapes, so the document-level number reads clean while hundreds of elements sit off-screen. A stale `layout.json` produced 268 overflowing elements with `scrollWidth === clientWidth === 1280`.
- **When measuring overflow, first check `location.href`.** `browser_console` evaluations run against `about:blank` if the page context was lost — the expression returns a perfectly clean `{count: 0}` for a page that actually has 268 overflowing elements. Re-`browser_navigate` before trusting any overflow number.
- `.session-select` needs `min-width: 0` — flex items default to `min-width: auto` and refuse to shrink below their widest option, so `Loading sessions...` pushed the intel panel's controls past the right edge. Same trap applies to any `flex: 1` select or input.
- **Do not add `overflow-y: auto` to `.hud` to reach panels below the fold.** It works (scrollHeight 1440 vs clientHeight 577) but it scrolls `topControls` and the core dial along with it, and `position: fixed` does not rescue `.core` because it already carries `transform: translate(-50%,-50%)`, which pins the transform origin and breaks the centering. The rail is 457px tall at a 577px viewport and holds ~1277px of panels — that density gap is a design problem, not a CSS one.
- Panels below the fold are still reachable: unlock the layout, drag the panel into view, `save()` persists it. Verified with `avdPanel` at `top: 1333px`.
- **Structural panels are not content panels.** `eventLog`, `codeViewer`, `response`, `chatBar`, `core`, `topControls`, `bottomTelemetry` lack `.panel` class and intrinsic dimensions. Hiding them with `display: none` collapses to 0×0 and they never restore. They must be excluded from any UI that toggles visibility (Options menu, etc.).
- **Equalizer must be idle until voice plays.** Continuous animation wastes CPU and looks wrong. Guard every frame with `.hud.speaking` check; expose `startEqualizer()`/`stopEqualizer()` on `window` so all TTS paths (server, browser, preview) can call them. `initEqualizer()` at boot was the bug — remove it.

## Pitfalls

- **Refactoring the HUD needs a DOM-count baseline, not just `node --check`.** Before touching UI code, capture per-selector counts from the live page via `browser_console`: dials, matrix cells, pipe nodes, ws items, cmd buttons, quick buttons, event entries, radial ticks, orbital circles, octagon points, voice/session options, panel count, proj cards, tool chips, avd buttons, vault stats, tele items, `LayoutManager.items` keys. Compare the same numbers after. Every count must be identical and `js_errors` must stay 0.
- **`browser_click` returns `success: true` even when the element is outside the viewport** — the click is dispatched at coordinates the page cannot hit, so nothing happens and the tool reports no error. Before trusting any interaction test, assert the target's rect is on-screen (`getBoundingClientRect()` within `clientWidth`/`clientHeight`); drive off-screen elements with `document.getElementById(id).click()` inside `browser_console` instead. An off-screen interactive control is itself a bug, not just a test problem.
- **Verify the pty round-trip in-browser, not just from curl.** Create the panel, `POST /api/terminal {action:input, data:'echo ...\n'}`, then read `document.querySelectorAll('.xterm-rows > div')` textContent to confirm the output actually painted. Also confirm `/api/terminals` count returns to 0 after closing, which proves the server session was released.
- **Pre-FUI leftovers in `ui/src/components/` were all dead** — `CentralReticle`/`CodeViewer`/`AudioSpectrum` had zero references AND referenced CSS classes (`.reticle-core`, `.code-editor`, `.spectrumCanvas`) that do not exist in `ui/styles/`. Before assuming a component is live, grep for both its class name in main.js and in the CSS.
- `ui/src/services/pipeline.js` (`createPipeline`) was written but never imported; `setAgentState` in main.js does the same work inline. Dead modularisation is worse than none — it invites the next reader to wire up two competing implementations.
- **Git:** remote is `git@github.com:bryankldr/ana-hermes-dashboard.git` over SSH (`~/.ssh/id_ed25519`, no passphrase — add an agent entry or a passphrase if the machine is shared). History is a single squashed root commit `b9f13ab`; the pre-rename JARVIS commits exist nowhere in this repo. The only surviving copy of the original upstream is `https://github.com/Itsme23476/jarvis-hermes-dashboard`.
- **Refactor workflow that worked:** snapshot every endpoint's JSON shape to `/tmp` BEFORE touching code, then diff after. Comparing whole strings gives false positives from live data (`git dirty` count, new Hermes sessions); compare **key sets and field types per record** instead. Then exercise the real flows: PTY create→input→stream→resize→close, voice id validation, static path traversal, NDJSON `/api/run` line types, and the 401 guards on all 8 token-gated GET endpoints.
- `/api/run` verification: `types=[...]` must be all valid JSON with no `NON-JSON` line — a stray one means headers were sent twice, the failure mode that hangs the HUD on RUNNING.

## Server Request Handling (fixed 2026-09-29, smoke.py section 7b)

`BaseHTTPRequestHandler.handle_one_request` only catches `TimeoutError`. Any other exception kills the per-request thread, and the client sees a **closed socket with no status line at all** — in the HUD that is a fetch that rejects with no error text anywhere. `ThreadingHTTPServer` keeps running, so the process looks healthy while every bad request silently dies.

1. **Parse JSON once, in `do_POST`, and type-check it there.** Valid JSON that is not an object — a bare string, number, list, `null` — passed the `except json.JSONDecodeError` guard, then had `.get()` called on it *outside* the try. Reproduced on `/api/session`, `/api/run`, `/api/avd`, `/api/terminal`, `/api/mode`. `do_POST` now parses into `body` and returns 400 for a non-dict; `_stream_run(payload)` takes the parsed dict rather than re-reading `raw`.
2. **`int()` on a JSON value raises.** Terminal `cols`/`rows` arrive as JSON and can be a string, a list or null. `_clamp(value, lo, hi, default)` in `server.py` falls back to the caller's default instead of raising.
3. **Never `import server` from `commands.py`.** Under `python3 server.py` the live module is `__main__`, so `import server` loads a *second* copy with its own `MODE` dict. `/mode asisten` answered "mode changed" and nothing changed. Use `sys.modules.get("server") or sys.modules.get("__main__")`, falling back to a plain import only outside the server.
4. **`state.json` is user-editable, so normalise it on the way in.** `_load_unlocked` assumed a dict and its `except` did not cover `TypeError`, so a truncated file made every run and `context_block()` die. It now checks `isinstance(d, dict)`, coerces list fields, and `setdefault`s `text`/`done` on task entries (a task without `text` raised `KeyError` in the kanban builder).
5. **`pty.openpty()` returns two descriptors and `Popen` takes one.** If `Popen` failed (bad `ANA_SHELL`, fd table full) the `_Terminal` was never registered and nothing closed them — two fds leaked per attempt. Both are closed in an `except BaseException` before re-raising.
6. **Static file check must use `relative_to()`, not `startswith()`.** `str(f).startswith(str(UI.resolve()))` passes for `../ui_secret` and `../uix/secret.txt` because there is no separator. Latent only because neither directory exists, but `server.py`, `.env` and `state.json` are all one `..` away.
7. **`Handler.timeout = 30`.** With `protocol_version = "HTTP/1.1"` and no timeout, a client that opened a connection and went quiet pinned a thread for the life of the process, and there is no thread ceiling.

`smoke.py` section 7b is the regression net: 25 of its checks fail on the old code with "Remote end closed connection without response". `rawreq()` returns status `0` for a dropped connection instead of raising, so the harness reports it as a failure rather than dying.

## Frontend Defects Fixed 2026-09-29

- **`LayoutManager.measure()` must skip hidden elements.** A `display:none` element reports a 0×0 rect, and writing that back as inline `width`/`height` pinned it at zero permanently. `#codeViewer` shipped hidden, so the code diff viewer rendered as a 360×**2**px sliver at (0,0) even with `.visible` applied — the CSS `!important` on width won but nothing restored the height. Guard: `if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') continue;` plus a `r.width < 1 && r.height < 1` check. It then lands at 360×77 where the stylesheet puts it.
- **Append to `#intelTerminal`, never rebuild it.** `intelLog()` and `intelTool()` append straight into the node, but `intelMsg()` did `innerHTML = ''` and replayed only `convoMsgs`, so every tool trace and session line was destroyed the instant a run completed. `intelMsg` appends now and trims to 80 lines like its siblings.
- **`esc()` must escape quotes.** It escaped `& < >` only, and it feeds attribute values (`data-path`, `title`) built from filesystem paths, so a directory named `x" onmouseover="…` broke out of the attribute. Session titles in `#sessionSelect` were interpolated **raw** into `<option>` markup from `hermes sessions list`. `esc()` now covers `"` and `'`; the session list escapes `id`, `title` and `last_active`.
- **Untracked `setTimeout` hides the next run's UI.** `progressDone` scheduled a 3.5s hide with no handle, so it fired after the next run had already opened `#progressPanel` and removed `.active`. It has a `progHideTimer` handle now, cleared in both `progressDone` and `progressReset`.
- **Any interval faster than its server-side work will stack requests.** `setInterval(refreshAvd, 7000)` against a poll that runs `adb devices` (5s) + `getprop` (5s) + `emulator -list-avds` (8s) — up to 3 requests in flight, and the oldest response lands last and reverts the panel. `avdPending` single-flight guard. Same shape, lower impact: `refreshKanban` (6s).
- **Core label stuck on RESPONDING.** `speak()` only resets the state to IDLE via `stopVoice()` on the path where audio actually played, and it returns early when muted or the answer is empty. The reset now happens in `transmit()` after `speakDone` resolves, skipping the `ERROR` case.
- **Speech recognition restart loop.** `onerror` only logged and `onend` restarted every 250ms when no final text arrived, so a device that cannot do speech recognition produced 13 identical log lines per click. Fatal errors (`not-allowed`, `service-not-allowed`, `audio-capture`, `network`, `language-not-supported`) now call `stopConvo()`; `no-speech`/`aborted` stay on the retry path.
- **`+ NEW` cleared one session readout, not two.** It reset `#sessionId` in the Intelligence Surface but not `els.stSess` in AGENT STATUS, so the two panels disagreed until the next real run.
- **A locally answered command leaves the session blank, and that is correct.** `/commands` and friends answer in-process and never start a Hermes session, so `stSess` staying at `—` is right. A real prompt populates it from the `session` event.

## Vendored Assets

`ui/vendor/` holds xterm.js, xterm.css and xterm-addon-fit.js (~296K). They were loaded from `cdn.jsdelivr.net`, which meant the whole HUD — including the terminal — failed with no network. The only remaining external request is Google Fonts, and every `font-family` in `tokens.css` has a monospace/system fallback, so offline costs typography only. `smoke.py` checks the three vendor files resolve.

## Restart & Debug

- Dashboard restart is not `pkill` + single `fuser -k` — stale `python3 server.py` (e.g. PID 194638) can hold `127.0.0.1:8730` in TIME_WAIT for several seconds. **`pkill -f "ana-hermes-dashboard.*server"` does NOT match** — the process cmdline is bare `python3 server.py` (cwd is set, not argv), so the path pattern never appears. Kill by PID from `ss -tlnp | grep 8730` instead. Loop `pkill -9 -f "ana-hermes-dashboard.*server"` + `fuser -k 8730/tcp` + `sleep 1` until `ss -tlnp | grep 8730` is empty, then `python3 -m py_compile server.py runtime.py commands.py voice.py terminal.py` and `node --check` every file under `ui/src/` (`ui/app.js` no longer exists — it was removed in the Fase B refactor), then relaunch with `terminal(background=true)` as `python3 server.py` in `~/ana-hermes-dashboard` (Hermes tracks it via `process_manage`). Foreground `nohup`/`setsid` wrappers are rejected by the terminal tool.
- After restart, verify with fresh token: `TOKEN=$(curl -s http://127.0.0.1:8730/ | grep -oP 'ana-token" content="\K[^"]+')` then `curl -H "X-Ana-Token: $TOKEN" -H "Origin: http://127.0.0.1:8730" http://127.0.0.1:8730/api/voices | python3 -m json.tool` and `curl ... /api/run -d '{"message":"/commands"}'` — expect `t:note`+`t:delta`+`t:complete` NDJSON lines.
