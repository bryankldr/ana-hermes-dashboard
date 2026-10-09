# FUI HUD Layout & Component Reference

Depth for the cinematic command-center layout at 1128×622. Always-on rules live in
`SKILL.md`; this file holds the zone map, per-component mount table, design tokens, and
the user-flagged layout regressions that must not come back.

## Zone map

```
┌────────────────────────────────────────────────────────────┐
│                    TOP DIALS (8 instruments)               │
├──────────────┬────────────────────────────┬────────────────┤
│ LEFT RAIL    │       CENTRAL CORE         │  RIGHT RAIL    │
│  220px       │   470×370px octagonal      │  240px         │
│  scrollable  │   + orbital particles      │  scrollable    │
├──────────────┴────────────────────────────┴────────────────┤
│              BOTTOM TELEMETRY (CPU/RAM/equalizer)           │
└────────────────────────────────────────────────────────────┘
```

## Component mount table (all wired in `main.js`)

| Component | Mount Point | Source |
|-----------|-------------|--------|
| Top Dials | `#topDials` (8 SVG dials) | `initDials()` — CPU/RAM/GPU/AI/TOOLS/FILES/CODE/SYS |
| Agent Status | `#agentPanel` `.stat-row` | `loadStatus()` — MODEL/MODE/CONTEXT/MEMORY/SESSION (no TOOLS row) |
| System Matrix | `#matrixGrid` (12 cells) | `initMatrix()` + `setMatrixActive()` — CODE/GIT/TERM/FILE/SRCH/MEM/TOOL/BUILD/TEST/ERR/DEP/SVC |
| Workspace | `#workspacePanel` `.workspace-grid` | `initWorkspace()` — 6 clickable items (src/lib/api/test/docs/config) → `intelLog()` |
| Central Core | `#coreSvg` octagonal + orbital | `initOctFrame()` + `initRadialTicks()` + `initOrbitalParticles()` |
| Intelligence Surface | `#intelPanel` `.intel-terminal` | `intelLog()` — live tool calls + stream from `handle()` |
| Agent Pipeline | `#pipeline` `.pipe-node` | `setAgentState()` — INTENT→CONTEXT→MEMORY→REASONING→TOOLS→RESULT |
| Bottom Telemetry | `#teleCpu`/`#teleRam`/`#equalizer` | `initTelemetry()` + `initEqualizer()` |
| Command Matrix | `#cmdPanel` `.cmd-grid` (8 buttons) | `initCommandMatrix()` — `/new` `/goal` `/tools` `/browser` `/background` `/mission` `/personality` `/commands` |
| Quick Buttons | `.quick-bar` (4 buttons) | `initQuickButtons()` — STATUS/TOOLS/TOOLSETS/CONNECTORS |
| Voice Picker | `#voicePicker` `.voice-select` | `loadVoices()` → `fetch('/api/voices')` |
| System Telemetry | `#sysTelemetry` `.tele-grid` | `initSystemTelemetry()` — Brain/Runtime/Profile/Uplink/Clock |
| Connected Tools | `#toolsPanel` `.tools-chips` | `initToolsChips()` + `loadStatus()` |
| Event Log | `#eventLog` `.event-entry` | `log()` + `initEventLog()` |
| Code Viewer | `#code-viewer` `.cv-body` | `showCode()` — agent execution runtime |
| Projects | `#projectList` `.proj-card` | `refreshProjects()` — click → `transmit()` |
| Briefing | `#briefingContent` | `refreshBriefing()` → `fetch('/api/briefing')` |
| Live Progress | `#progressPanel` | `progressReset/progressStep/progressDone` (Fase A) |
| Code Diff | `#codeViewer.live` | `showCodeDiff(title,diff)` (Fase B) |
| Mission Kanban | `#missionKanban #kanbanGrid` | `refreshKanban()` (Fase C) |
| Vault / AVD | `#vaultPanel` / `#avdPanel` | `refreshVault()` / `refreshAvd()` (Fase D) |
| Background Jobs | — | polling 4s → `fetch('/api/jobs')` → `log()` |
| Voice STT / TTS | `#micBtn` / — | `micToggle()`, `speak()` |
| Mode Toggle | `#modeBtn` | `setMode()` → `POST /api/mode` |
| Chat / Response | `#chatInput` `#chatSend` / `#responseText` | `sendFromChat()` → `transmit()`, `renderAnswer()` |
| Equalizer | `#equalizer` canvas in `#equalizerWrap` | `startEqualizer()` / `stopEqualizer()` — only during voice |

`ensurePanel()` (in `utils/dom.js`) registers each panel with `LayoutManager` the moment it is
created, so there is no per-panel `register()` call to remember. Panels built by hand in
`index.html` are registered by the `LayoutManager` constructor's id list in `init()`. A panel that
is neither is not draggable.

## Equalizer behavior

Canvas `#equalizer` (80×24) sits in `#equalizerWrap` (`tele-center`). It must be **idle until voice plays**.

- `startEqualizer()` / `stopEqualizer()` on `window` — call from `speak()` (server TTS + browser fallback) and `previewVoice()` (ElevenLabs + browser fallback).
- Animation loop: `requestAnimationFrame` with `.hud.speaking` guard on every frame — auto-stops + clears canvas when class removed.
- Visual: 16 bars, smooth sine wave + organic noise, cyan→blue-green hue shift, subtle glow on bars >12px.
- `initEqualizer()` NOT called at boot — equalizer stays empty until first voice event.

## Design tokens

- Colors: `--bg-deep: #001A38`, `--neon: #00E8FF`, `--core-bright: #BFFFFF`, `--text-dim: #5A7A8A`, `--text-body: #B0D8E8`, `--text-header: #7AF8FF`
- Fonts: `Orbitron` (display), `Share Tech Mono` (data)
- Background: `radial-gradient` deep navy + 40px grid + particle canvas
- Frame: corner brackets (L-shape 24px/2px) + top/bottom bars
- Panels: `.panel` — `rgba(0,26,56,0.7)` bg, 1px cyan border, `::before` top glow line
- Core: SVG octagon + concentric circles + 36 radial ticks + 12 orbital particles + center glow
- Responsive: `≤1200px` shrink rails, `≤900px` hide left rail, `≤600px` hide right rail + top dials

## Agent state machine

`setAgentState(state)` drives core label + pipeline + matrix:

| State | Pipeline Active | Matrix Highlight |
|-------|-----------------|------------------|
| IDLE | none | none |
| LISTENING | intent | none |
| UNDERSTANDING | intent→context | none |
| PLANNING | intent→context→memory | none |
| EXECUTING | intent→context→memory→reasoning→tools | TOOL |
| WAITING_TOOL | intent→context→memory→reasoning→tools | TOOL |
| ANALYZING | intent→context→memory | SRCH |
| RESPONDING | all | CODE |
| ERROR | none | none |

## Overflow measurement recipe

`scrollWidth > clientWidth` is useless here — `html,body{overflow:hidden}` pins both to the
viewport. Probe per element instead, and confirm the page context first because an evaluation
against a lost context reports a clean zero for a page that is actually full of overflow.

```js
// browser_console, after browser_navigate (never trust about:blank)
if (location.href.includes('about:blank')) throw new Error('wrong context');
const de = document.documentElement, vw = de.clientWidth, vh = de.clientHeight, bad = [];
document.querySelectorAll('body *').forEach(el => {
  const r = el.getBoundingClientRect();
  if (!r.width && !r.height) return;
  if (r.right - vw > 1 || r.bottom - vh > 1)
    bad.push({ sel: el.id ? '#' + el.id : '.' + el.classList[0],
               ovR: Math.round(r.right - vw), ovB: Math.round(r.bottom - vh) });
});
// group by sel and take the max — content inflation shows up as many children overflowing
```

Healthy result at 1280×577: `bad.length === 0`. Because `LayoutManager` re-parents every panel
out of its rail, **vertical overflow is expected** — 10 left-rail panels stack to ~1277px inside a
457px rail. Horizontal overflow is the real regression signal; vertical means content density.

### When a rail's content exceeds the viewport — options, in order of cost

| Option | Cost | When it is right |
|---|---|---|
| Leave it, panels stay draggable below the fold | free | default; the layout was designed at 1128×622 and behaves the same way on a taller window |
| `@media (max-height: 700px)` collapse low-priority panels to header-only | small | user wants everything on one screen without new structure |
| `overflow-y: auto` on `.hud` | **do not** | scrolls `topControls` and the core dial too, and `position: fixed` cannot rescue `.core` because it already carries `transform: translate(-50%,-50%)` — that pins the transform origin and breaks the centering |
| Stop `LayoutManager` re-parenting panels out of the rail | large | only if scrollable rails are actually required; it is a structural change, not a CSS one |

## User-flagged layout regressions — do not reintroduce

- **Rails need scroll.** Left/right rails must be `overflow-y: auto` with `min-width` ≥ 220px; without it bottom panels get clipped ("CONNECTED TOOLS terpotong di bagian bawah halaman").
- **Panels need breathing room and legible type.** padding ≥4px, font-size ≥8px ("Agent Status terlalu kecil", "System Matrix juga terlalu kecil", "command matrix terlalu kecil"). Microtext below 7px is unreadable at 1080p.
- **Font scaling final ratio: 1.5× font-size, 0.75× dimensions.** User asked 2×, then "terlalu besar, kurangi 1/4". Apply with a regex pass over `font-size: <n>px` then scale padding/margin/gap/width/height by 0.75. Verify via `curl -s http://127.0.0.1:8730/styles/hud.css | grep font-size`.
- **Interactive, not decorative.** A static SVG wireframe is invisible to the user — Workspace items need click handlers and hover states ("Workspace tidak jelas fungsinya, saat ini tidak dapat diakses / diklik"). The Intelligence Surface must show real live agent activity, not a static chart ("seharusnya menunjukkan animasi code terminal proses background agent yang sesungguhnya"): feed it from `handle()` tool/delta events, height ≥280px, line classes `.intel-line.tool` (cyan) / `.ok` (green) / `.error` (red) / `.stream` (dim).
- **Event Log needs a header and size.** ≥300px wide, ≥340px tall, background panel, `.event-log-header` prepended and `position: sticky; top: 0`. Entry format is inline `[LABEL] msg` with a timestamp, not block display. Max 50 entries.
- **Cache beats correctness when CSS "didn't change."** Check what the server actually serves (`curl -s http://127.0.0.1:8730/styles/hud.css | grep -A5 '.class {'`) before re-editing. If the server is right, it is the browser: add `!important` to key dimensional properties and hard-refresh `Ctrl+Shift+R`.
- **Feature ports must be exhaustive.** When moving to a new layout, audit every old feature and confirm each has a new home before reporting done ("semua fiturnya di HUD LAMA belum muncul di HUD baru, pastikan 100% kamu porting").
