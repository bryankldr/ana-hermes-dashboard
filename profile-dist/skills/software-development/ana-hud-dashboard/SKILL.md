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
**Portable root** — gunakan `$ANA_WORKDIR` (set via `.env` di tiap mesin) atau fallback `$HOME/PROYEK_2026/ana-hermes-dashboard`.

> ⚠️ **CRITICAL**: Jangan hardcode `/home/bryankldr/...` di skill/config/script. Resolve via `ANA_WORKDIR` env atau `Path(__file__).resolve().parents`.

## Quick Commands
```bash
cd "$ANA_WORKDIR"
./start.sh                 # Start server on 0.0.0.0:8730 (picks interpreter with websockets/edge_tts + guarantees hermes serve WS; aborts loudly instead of silent MOCK unless ANA_NO_SERVE_AUTOSTART=1)
python3 smoke.py           # Run 121 E2E checks
python3 test_services.py   # Run 24 service assertions
node --check ui/src/main.js # Validate JS syntax
```

## Key Files
- `server.py` — stdlib `http.server` dashboard (port 8730), NDJSON `POST /api/run` stream, serves `ui/` static, `api/` endpoints
- `start.sh` — bootstrap: venv, deps, python `server.py`
- `ui/` — hand-written vanilla HTML/JS/CSS (`index.html`, `src/main.js`, `styles/hud.css`); validate with `node --check`, no build step
- `profile-dist/` — **distributable skill package** untuk deploy ke mesin lain (copy ke `~/.hermes/profiles/anna/skills/`). Holds skills/memories/plugins/SOUL.md ONLY — there is no `profile-dist/ui/`; `ui/` + `server.py` ship via git clone, never via profile-dist copy. Verify layout with `ls profile-dist/` before any sync; a `cp ... profile-dist/ui/...` that fails with 'No such file or directory' means the target is wrong, not missing.
- `.env` — `ANA_PORT=8730`, `ANA_TOKEN=...`, `ANA_WORKDIR=/abs/path/ana-hermes-dashboard`
- `smoke.py` / `test_services.py` — E2E regression

## Environment (`.env`)
```
ANA_PORT=8730
ANA_TOKEN=<generate via: openssl rand -hex 32>
ANA_WORKDIR=/abs/path/to/ana-hermes-dashboard  # override bila bukan $HOME/PROYEK_2026/
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
vanilla JS (ui/)  <--fetch NDJSON-->  stdlib http.server:8730  <--skills/tools-->  ANNA profile
    ^                                                              |
    |-- static files (index.html, src/main.js, styles/)            |-- simoge-business (SIMOGE BI)
                                                                   |-- maplibre-* (spatial eval)
                                                                   |-- ana-hud (this skill)
```

## Chat Panel UI Conventions (TPL = reference)
New list panels docked to `#chatBar` must clone the TPL template-question pattern, not invent new structure:
- HTML: `<div id="<x>Panel" class="tpl-panel" hidden></div>` as sibling of `#tplPanel` inside `#chatBar`.
- CSS: extend existing selectors (`#tplPanel, #<x>Panel`, `[hidden]`, phone/tablet media queries) — never new panel CSS.
- JS render: `tpl-bar` header with a `mkBtn(label, title, fn)` helper; rows as `tpl-row` > `button.tpl-item` + per-row `button.tpl-bar-btn.mini.tpl-del` (delete keeps the `tpl-bar-btn` base class; add/refresh buttons live INSIDE the list).
- Behavior: toggle `hidden` on button click; panels mutually exclusive; close on send + Escape; no outside-click close unless TPL gains one.
- Session list payload already carries `created`/`message_count`/`active` — render those instead of inventing a title API (server titles may be `--`). Format epoch with `toLocaleString('id-ID', {day, month, hour, minute})`, same as the INTELLIGENCE SURFACE selector.
- `.tpl-item` ships `width:100%` for full-width view mode — inside a flex `.tpl-row` it eats the whole row and pushes the per-row button out of the panel (horizontal scroll to find delete). Scope an override to the new panel: `#<x>Panel .tpl-row .tpl-item { flex:1 1 auto; min-width:0; width:auto; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }` plus `#<x>Panel .tpl-row .tpl-del { flex-shrink:0; }`. Mirror `.tpl-input`, which already carries `flex:1; min-width:0`.
- After edit: `node --check ui/src/main.js` (ui files ship via git, never via profile-dist).

## Gateway Event-Loop Rules (`runtime_gateway.py`)
- `run_forever()` / `run_until_complete()` must never be called on a shared global loop from more than one thread — a second connection attempt spawning a second thread on the same loop object raises `RuntimeError: This event loop is already running`. Each background thread owns a LOCAL loop; the global only publishes the live one.
- Retry path needs single-flight: if the gateway thread is still alive and the previous attempt hasn't settled, join/wait on it instead of spawning a second thread+loop.
- A fresh attempt must stop the orphan first (cancel tasks, `shutdown_asyncgens`, `loop.stop`, join thread) and reset the connect/session events before reconnecting — otherwise the old thread races the new one and startup coroutines are left never-awaited.
- `Gateway connection closed` triage (log noise, not always a bug): the line is `gateway_client.py` `_recv_loop` catching `websockets.ConnectionClosed`, followed by `_handle_disconnect` → `_schedule_reconnect` with 1s→30s backoff. Occasional closes with a successful reconnect = normal, ignore. Closes every second + `Failed to connect ... Errno 111` + brain `MOCK` = stale URL — re-run `./start.sh` to rediscover `hermes serve` port/token. Health check is `GET /api/status` reporting `runtime:hermes`; SLOW status timings during a flap are retry effects, not a separate bug.
- Port split: dashboard `ANA_PORT` is static (`.env`, default 8730); serve port is ephemeral (`--port 0` = new port + rotated token every restart, except pinned production units). `start.sh` guarantees serve — reuse the live healthy instance, else autostart `hermes serve --port 0` and rediscover, else abort loudly. Debug probes must resolve port/token the same way (live dashboard process env → `ss` + `/api/health` + root-page token), never a hardcoded port.
- `_map_gateway_event` must read `session_id` from BOTH top level and `payload` (`session.info`, `message.complete`) — the gateway nests it in `payload`, and reading only top level means the session is never persisted and restore drifts to the wrong session.
- Chart/response push auth triage (`POST /api/spatial/chart` 401/403, no chart changes needed): 403 = host/origin gate (`_host_ok`/`_origin_ok` in `do_POST`) — the request never reached auth; 401 with body `chart berisi data wajib push lewat sesi user login` = owner unresolvable — check `.ana_current_sid` freshness against the active session and the matching `.ana_scope_<sid>.json` file (tools resolve owner via `X-Hermes-Session` header → scope file, cookie-less `terminal` processes via the sid file). A stale sid file after session switch/archive looks exactly like broken chart push.

## Session Management Rules (`server.py` + `ui/src/main.js`)
- One painter for session display: a single `paintSessionId()` writes chat span + intel span + status label + localStorage. Duplicate element ids across panels make `getElementById` hit the wrong node — keep ids unique (`sessionId` vs `sessionIdIntel`) and never write session display inline elsewhere.
- New session = `POST /api/session/archive` (archives active to history, keeps Hermes store; next run creates fresh). Never `POST /api/session {action:"new"}` without `session_id` — it falls into the clear+None path and the session is lost, not archived.
- Selecting a session must call `_session_set(sid, None)` so title/created/count history survives; passing fresh meta resets title to `--`.
- Delete is tiered: dashboard history always dropped; Hermes store deleted only when origin is `run` AND orphaned (no user holds it); adopted CLI sessions (`claim`) are never touched in the store.
- Every session mutation from EITHER surface (chat panel or INTELLIGENCE SURFACE) must re-render BOTH: `refreshSessionSelector()` + `loadSessions()`/`sessionPanelRender()` in both directions when the panel is open.
- Boot restore: server `_session_restore()` loads `.ana_session` including history-only entries (id=None); frontend `localStorage` paint is instant-only, the server list via `loadSessions()` is the source of truth.
- Key the frontend sid cache per login user (`ana_session:<id-or-email>` via `anaSessionOwner()`/`anaSessionRead()`), never a single global key — one browser serving two accounts otherwise leaks account A's sid into account B's display, and a stale sid overwrites the correct one. The `storage` event listener must ignore keys that are not the current user's (fall back to the legacy global key only when no per-user key exists). Every successful `loadSessions()` repaints through `paintSessionId()` so a stale cached sid is overwritten by server truth on the next boot.
- TTL: `ANA_SESSION_TTL` default 1h; each completed run refreshes it (`_session_bump_count`) so live chats survive while idle sessions expire.
- History cap is FIFO, never a block: `_session_hist_push()` returns the evicted sid (None when nothing evicted, including re-select which only reorders); `/api/session/archive` replies `{evicted, max}` and `GET /api/session` includes `max`, so both new-session buttons can log which oldest session was dropped instead of silently losing it.

## System Prompt Rules (`server.py` `_stream_run` + `runtime_gateway.py`)
Full prompt (persona + identity + wiki + scope + mode) goes out ONLY on a new session — `fresh=true` (`/new`), first message ever, or no active session. Continuations send `system=None` and let Hermes resume; re-injecting every turn wastes tokens and makes every user message carry the full instruction block.
- `fresh` must ALSO force `session_id="default"` and pop the user's `_GW_LIVE` slot — the frontend always sends the old `session_id` in the payload, so without this the run resumes the old session while carrying a brand-new full prompt. Clear + sid None → gateway creates truly fresh.
- Background-mission runner passes `system=None` (`runtime.run(m, None, None)`), never `persona()` — the mission runs in its own fresh session and a full prompt there is pure waste.
- Identity rides with scope: `_anna_identity_block(handler)` builds `## IDENTITAS USER` from the login cookie (name + email + jabatan + wilayah as NAMES, never codes alone) at the same assembly points as the scope block, so the model greets by name/jabatan instead of generic `Boss`/`Bapak-Ibu`. Token-only or minimal sessions yield empty string — never invent an identity. Privacy: name/jabatan/work-area only, never password/token/hash; the function must never raise.
- Verify with a stubbed simulation (`FakeRT` recording `(session_id, FULL|None)` per case: continue-old / fresh / first-ever) run against a freshly `importlib.reload`ed server module with live `time.time()` stamps — the execute_code kernel reuses imports (stale code silently passes) and epoch-1970 fixtures look TTL-expired and skew every branch.

## Premium Conversation Polish (`ui/src/main.js` + `server.py` persona overlay)
The user only ever sees: smooth status → one clean answer → one follow-up offer. Chart/map visuals are out of scope — never touch what already renders well. Internal machinery (spinner prose, tool JSON, reasoning narration) must never reach the user surface.
- Thinking events: map kawaii spinner prose (`mulling...`, `reflecting...`) and model self-narration (`Composing...`, `Summarizing...`) through a `cleanThinking()` normalizer — strip leading `(face)` emoticon prefix, map `*ing...` verbs to Indonesian status (`Memikirkan…`, `Menghitung…`, `Menyusun jawaban…`), pass through genuine wait/provider notices, dedupe consecutive repeats via `_lastThinking` (reset it every `transmit()`). Other raw statuses get the same treatment: `Menghubungkan…`, `Respons pertama…`, `Mengambil data…`, `Data diterima` — never `core online · N tools` / `first token Nms` / `TOOL → name(args)`.
- Tool trace lines show the tool name only (`⚡ name → ok`); raw args/output move to the line's `title` tooltip — untruncated JSON dumps in the terminal read as debug output, not product.
- Anti-stutter at finalize time via `finalizeAnswer()` on `complete`: dedupe GLOBALLY (a `seen` set over the whole answer — consecutive-only misses repeats separated by other sentences) and strip process-narration sentences ANYWHERE, not just leading (`siapkan…`, `tarik/menarik/tarikan angka|data|produksi`, `menjawab…tarik`, `belum masuk, cek…`, `kosong, telusur…`, `render chart…`, `perbaiki autentikasi…`, `cek sesi…`, `saya cek…`, `menyusun…`). Panel, intel log, and TTS must all consume the finalized text, never the raw stream. Keep a fallback: if every sentence matches narration, return the deduped original so the answer is never empty. Split sentences decimal-safe (mask `\d.\d` before splitting or `1.200,5` breaks into fragments). Anchor narration patterns to sentence start — a bare `siap[,.]` eats real greetings (`Halo Boss, ANNA siap.`). Verify ALL string surgery with a runnable `node` unit check before shipping, including the exact user-reported text, a no-op case proving normal answers are untouched, and a pure-duplicate case.
- Asisten overlay structure (replaces the old `1-2 kalimat` cap, which starved analytical answers into bare numbers): opening sentence MAX 1x, then content (numbers + insight), then 1 relevant follow-up offer (e.g. breakdown by month/petak). Never open with content-free filler. Explicitly forbid process narration in the answer (`DILARANG menarasikan proses — langsung isi`) — model self-narration can arrive inside `delta` (not the thinking channel), where no frontend filter can catch it without risking real content; the overlay stops it at the source and `finalizeAnswer()` is the second line of defence. The budget-path overlay copy must stay identical to the real one (measure = send).

## Chat Thread Premium (`ui/src/main.js` + `ui/styles/hud.css`)
RESPONSE is a conversation thread (user/ANA bubbles + question quotes + timestamps + per-message actions), never a single last-answer text. State: `_thread = { sid, items, streaming }` (cap 40 items); render via `_threadBubble` / `_threadRender` using `textContent` (XSS-safe, no `esc` needed).
- `transmit()` pushes the user bubble then starts the ANA stream bubble; `delta` appends to the stream; `complete` runs `finalizeAnswer()` then `_threadStreamDone()` — panel, intel log, and TTS must all consume the finalized text, never the raw stream. `error` also lands in the thread (`⚠ ...`) so failures stay visible.
- Branding is ANNA everywhere user-facing: thread bubble `who` is `Anda`/`ANNA`, intel terminal prefix is `▸ ANNA:`, panel header is `ANNA` — never bare `ANA`. A `\bANA\b` grep over `ui/` before shipping catches regressions (excluding `ANA_TOKEN`, `ANA_PORT`, code identifiers).
- Quote pairing: every ANA bubble carries the originating question as `quote` (rendered as a quote block above the answer); suppress the quote when it exactly repeats the user bubble directly above it (history render + streaming render) — otherwise every answer visually repeats the question and reads as stutter. Residual quotes render as dim context (small, max 2 lines + ellipsis), never full-size body text. User bubbles are clickable (refill input) and each ANA bubble has Salin (clipboard + `Tersalin ✓` feedback) and Tanya lagi (resend). Timestamps via `toLocaleString('id-ID', {hour, minute})`; streaming bubble gets a dashed border + cursor.
- Session binding: switching sessions loads history from `GET /api/session/transcript?session_id=` (pair consecutive user→assistant, last 20); transcript resolves CLI export first, then gateway `session.history` — runs use gateway 8-hex sids the CLI store never sees, so CLI-only lookup returns empty history for the active session. The fetch must send `credentials: 'same-origin'` — without the login cookie the server reads user_key="" and rejects 401, which looks like empty history. New session clears the thread; deleting the active session loads the replacement; boot loads history for the restored session; clear button empties the thread. CSS: `.th-user` right / `.th-ana` left bubbles with entry animation, quote/action sub-styles — extend, never restyle chart/map panels.

## Scoped Tile Chain (PMTiles builder → server → map.js)
Builder writes year-suffixed files (`kph_<kode>_<thn>`, `bounds_<divre>_<thn>`, `overview_<divre>_<thn>`) and deletes legacy unsuffixed variants — treat the suffixed name as the canonical contract, never the bare name.
- Server allowlist (`_serve_pmtiles_file`) must accept an optional year: `(kph_\d+(?:_\d{4})?|bounds_\d+(?:_\d{4})?|overview_\d+(?:_\d{4})?|petak)\.pmtiles` — a bare-name allowlist 404s every real file on disk.
- Scope route (`/api/tiles/scope/`) regexes must accept an optional year group and resolve `_fname` to what exists: explicit suffix in path wins, else `?tahun=`, else newest suffixed glob on disk, else legacy bare name. Same fallback for `bounds_geo` ndjson (`bounds_<dv>.ndjson` → `bounds_<dv>_*.ndjson`).
- Client manifest lookup must match by basename (strip the year) and prefer the highest year, then build the URL with the real suffix — never `have.has('kph_'+k+'.pmtiles')` exact-match, which is always false once the builder suffixes.
- Overview gate: `multi = kphList.length !== 1` breaks single-KPH databases for top jabatan. DIREKSI/ADMINISTRATOR/DIVRE must get the colored overview even when scope holds 1 KPH (`wantOv = ... && (multi || isTop)`); mirror on server by allowing DIREKSI/ADMINISTRATOR in `_tiles_scope_ok` for `kind == "overview"` (previously DIVRE-only, so DIREKSI got 403 on its own overview).
- Multi-business overview (petak/aktivitas/produksi/matriks): the overview must NOT hardcode `biz === 'petak'` in the gate or the aggregate template — other businesses silently fall through to neutral bounds. Per business needs its own KPH aggregate template with ALIGNED output columns (`kode_kph, kph, kode_divre, total_petak, bongkor, kurang, terpenuhi`) so the client reuses one `_ovColor` classifier: aktivitas maps idle→kurang/active→terpenuhi (definitions mirror `aktivitas_petak_map`: active = activity in running period, bongkor = no penyadap OR 0 activity in 61 days). PRODUCTION IS THE EXCEPTION — never reuse `_ovColor` porsi-petaka thresholds for produksi: a healthy KPH whose petak mostly sit in the 50–75 cap band still paints yellow at KPH level. Production KPH color must come from WEIGHTED achievement (`produksi_per_wilayah(level='kode_kph')`: `100*SUM(actual)/SUM(target*pct/100)`, cumulative Jan→period): red <50, yellow 50–85, green >85 — aligned with `rkap_map` bands. That template needs `_wilayah_where(kw)` scoping plus overview-compatible aliases (`kode_kph, kph, kode_divre, total_petak`) before the client can use it; tooltip/insight show `actual/target kg (pct%)` with the number colored by the same band. Client picks template + period params (bulan/periode/pembaharuan_ke) per business, recolors the SAME geometry file via per-`kode_kph` filter rules (`_ovTileRules(colors)`; petak keeps the baked `warna` prop), and labels insight/tooltip per business (B/I/A for aktivitas, actual/target+pct for produksi). The overview cache key must be period-aware (`biz|z|tahun|bulan|periode|pemke|kph|divre`) or switching periods serves the stale color. Live-DB test each new `*_per_kph` template before shipping (single-KPH DB returns exactly 1 row). For flag-type filters, verify green-polygon count per flag value EQUALS raw `COUNT(DISTINCT kode_evapot)` with that flag=1 in the same period — a 1-2 row gap is polygon-less petak (expected), but identical counts across flag values on an empty period means the test period has no data; check `MAX(tgl_pembaharuan)` first and re-test on a period with data. New DB columns may not exist on live yet — guard with an `information_schema` check returning `AND 1 = 0` instead of erroring, so the filter degrades to zero rows and auto-activates when the column lands.
- Verify with a regex simulation over all six route shapes + five allowlist names, then `py_compile server.py` + `node --check ui/src/map.js`, then sync `simoge_db.py` into `profile-dist/skills/...` and `diff -q` to confirm IN-SYNC (ui files stay in git, never in profile-dist).
- `reloadBusiness()` must call `_scheduleOverview()` at its top — it is debounced (500ms, key-checked) so a same-key call is cheap, but WITHOUT it the Apply button and month/period changes only reload polygons while the tile keeps the stale key's color. Any new filter-triggered reload path needs the same call; overview refresh that only fires on tier/zoom change leaves the choropleth frozen on old filters.
- Overview responsiveness (ganti bisnis/filter must repaint without hard refresh): debounce 500ms→200ms so the repaint starts promptly; a monotonic `_ovSeq` guard discards stale async responses (slow business-A query finishing after fast business-B must not repaint the wrong color); a per-key color cache (`_ovColorCache`, key = the period-aware overview key) serves repeat biz/filter switches instantly without re-query. Declare sequence/cache vars ONCE at module scope — re-declaring in a later patch is a `let` redeclaration syntax error.
- New time filter (e.g. Sampai dengan Ya/Tidak) must be wired END-TO-END in one edit or the dropdown silently does nothing: HTML `<select id="f<x>">` in the Waktu fgroup + `const f<x> = $sel('#f<x>')` + `collectState()` spread + `spatialMapState.js` allowlist + clamp + `businessAdapter.js` wilayah pass-through + overview key segment + `_ovParams` + `renderChips()` item + reset/clear/chip-remove handlers + `spatial_set` `_map` objects. Miss any one link and the value never reaches the template — verify with grep for the new key across `map.js`, `spatialMapState.js`, `businessAdapter.js` before shipping.
- Stale-JS triage when the tile misbehaves after a `map.js` patch: `sw.js` is network-first for `/src`, so a hard-refresh (Ctrl+Shift+R) picks up the new file — but a dashboard process started BEFORE the edit still serves the old bytes. Check server start time (`ps -o lstart=`) against the file mtime; restart `./start.sh` when the process predates the patch before blaming logic.
- Tier guard must be business-aware: a blanket `want = z <= 11 ? 'pmtiles' : 'geojson'` hides the colored GeoJSON polygons for non-petak businesses (their `set_petak_polygons_visibility(false)` kills the very layer carrying their analysis) while petak looks fine because its color comes from the tile itself — a silent per-business break that reads as 'tile/KPI/legend stuck'. Non-petak businesses stay `geojson` at every zoom; only petak uses PMTiles at z≤11.
- Effectiveness coloring (tree-ratio per petak, e.g. Aktivitas): per-type ratio = `MAX(jml_phn_<type>) / jumlah_pohon` (coverage — one tree reworked across 1-4 pembaharuan still counts once; use `MAX(NULLIF(col,0))` so absent rows don't join the MAX), all-types = average of per-type ratios over types WITH data only (denominator = count of non-null ratios) — never a raw SUM, or one tree worked 3 ways scores 300% and a 4x-reworked petak always beats a 1x petak with identical coverage. Keep `SUM` as a separate `intensitas` (effort) column, never folded into the score. Bands: red = no work, orange ≤50, yellow 51-79, green 80-99, blue (emas) =100, gray (abu, new `WARNA_STYLE` entry) = no data — without gray, empty data paints red and reads as failure. Mirror all six in legend + KPI + insight + overview tooltip + `_ovColorCache` classifier + KPH aggregate buckets. Overview aggregate = AVG score + bucket counts per KPH, same band thresholds.

## Spatial Business Split Pattern (map.js + businessAdapter.js + server.py + simoge_db.py)
When one business mixes two semantics (e.g. structural status vs per-type work spread sharing one template + filter), SPLIT into two businesses rather than overloading one filter — an overloaded filter produces ambiguous categories users cannot interpret.
- New business entry in `BUSINESS_OPTIONS` at the requested position + `KATEGORI_OPTIONS` clone; adapter gets its own branch with its own template; `server.py` `_TEMPLATE_SPATIAL` gains the new template→(business, kategori) mapping or panel sync breaks silently.
- Backend: prefer thin WRAPPER templates delegating to the shared implementation (`T["base"](...)`, pop the inapplicable kwarg defensively) over duplicating SQL — a regex-duplicated 90-line template corrupts the file (one bad splice breaks every template below it) while a 10-line wrapper cannot.
- Scope new filters per business in the adapter (pass `jenis_aktivitas` only for the work-spread business, never the structural one); the structural template pops the kwarg defensively so a leaked value cannot change its meaning.
- Pin layer follows ONLY the work-spread business (Aktivitas shows pins; structural Keaktifan shows none) — never both. `fetchAktivitasPoints` passes the same type/time filters so pins match polygons.
- Pin stability under `preferCanvas`: the map renders all vectors on ONE canvas, so `pane`/`zIndex` on circleMarkers are IGNORED — pins sink under GeoJSON polygons (vanish at high zoom, clicks land on the petak modal). Fix: dedicated Leaflet panes (`aktivitasPane` zIndex 650 for pins, `aktivitasLinePane` 640 for connector lines, below popup 700) PLUS a dedicated `L.svg({pane})` renderer passed per-marker/per-polyline (`renderer:` option) — only the SVG renderer honors panes. Set `bubblingMouseEvents: false` on pins and connector lines so clicks stop at the pin and never bubble to the polygon beneath.
- Split businesses get DISTINCT polygon colors so users can tell them apart at a glance: structural status keeps merah/kuning/hijau (bongkor/idle/aktif); work-spread uses hijau (selected type) / biru-emas (other work only) / merah (sepi). Mirror the distinction in legend + KPI labels + overview tooltip tags (H/L/S vs B/I/A).
- Overview: the structural business reuses the existing `*_per_kph` aggregate via its own thin wrapper (same aligned columns); the work-spread business reuses the same aggregate with its type filter.

## Spatial Filter Panel Conventions (`ui/src/map.js` + `ui/styles/map.css`)
Filter drawer groups: Waktu (Tahun, Bulan, Sampai Dengan, Periode) then AKTIVITAS (Pembaharuan + Aktivitas side-by-side in one row — flag filter `jenis_aktivitas`: quare/semprot_cas/kerok/naik_batok/budaya_bersih/pulung, backend helper mirrors `_pembaharuan_where` but applies to `cur`/andil-breakdown only, never prev/two windows) then WILAYAH (DIVRE/KPH/BKPH row, RPH/TPG + Terapkan/Reset row). Time row uses a 4-column grid (`.spatial-row.cols4`: fixed narrow Tahun/Bulan, flexible remainder) — never let a year dropdown stretch full width. Destructive Reset is `.spatial-btn.danger` (red), never `ghost`.

## Map Legend Rules (`ui/src/map.js` + `ui/styles/map.css`)
- Legend is always visible — never a hide/collapse toggle. The user treats the legend as essential, so remove the toggle button, the `legend-collapsed` class, its listener, and all related CSS dead rules in the same edit; leaving any one of them re-hides the legend or leaves a dead button.
- Verify with a zero-match grep over `ui/` for `legendToggle|legend-collapsed|legend-toggle` before shipping, then `node --check ui/src/map.js`.

## Dev Loop
1. Edit `server.py` / `ui/` → `node --check ui/src/main.js` + `python3 -m py_compile server.py runtime_gateway.py`
2. `./start.sh` restarts server
3. `python3 smoke.py` verifies 121 checks (< 30s)

## Dual Theme (dark/light) — color only, never layout/business
- Dark is default and untouched: `:root, html[data-theme="dark"]` in `tokens.css` holds identical dark values. Light is an override block `html[data-theme="light"]` (token values only) + `styles/theme-light.css` (scoped `html[data-theme="light"]` color-property overrides for hex hardcoded outside tokens). File holds ZERO layout properties (no position/display/width/height/margin/padding/flex/grid) — verify with grep before shipping.
- State = `data-theme` on `<html>`, persisted `localStorage.ana_theme` (default dark), set by an inline pre-paint script in `<head>` (anti-flash). Toggle `btnTheme` (☀/🌙) lives in `topControls` next to terminal/options buttons; also updates `meta theme-color` and calls `window.__spatialChartRepaint()`.
- Map stays dark (satellite, per Stitch mockup: bright cards over dark map) — never recolor tiles/canvas. Chart DATA series colors stay (semantic status); only tick/grid/legend adapt via `tickColor()/gridColor()/legendColor()` in `spatialChart.js` reading `data-theme`. `render()` saves `_lastState` so the toggle repaints without new data.
- `sw.js` CACHE bump + precache `theme-light.css` on every theme change. After edit: `node --check` all touched JS, run `smoke.py`.

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
