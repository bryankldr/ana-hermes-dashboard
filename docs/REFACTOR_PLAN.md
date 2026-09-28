# Rencana Refaktor HUD ANA — Professional Structure

> Status: DRAFT — menunggu konfirmasi screenshot target
> Current: `ana.png` (HUD sekarang) → Target: `Screenshot 2026-09-28 00-45-17`

---

## 1. Audit HUD Sekarang

| File | Lines | Masalah |
|------|-------|---------|
| `ui/index.html` | 165 | Semua section inline, no component, no template |
| `ui/app.js` | 757 | 30+ fungsi campur: API, voice, reactor, chat, projects, briefing — 1 file |
| `ui/styles.css` | 49 lines / 15K chars | Semua style 1 file, no modular, no variables reuse |
| `server.py` | 446 | HTTP handler + business logic + project scan + briefing — monolith |
| `runtime.py` | 301 | Hermes subprocess + session — OK, tapi tightly coupled |
| `commands.py` | 280 | State + jobs + command matrix — 3 concerns 1 file |
| `voice.py` | 175 | OK — paling clean |

**Masalah utama:**
- Ganti 1 fitur = sentuh file 700+ baris, risk regression
- Tidak ada komponen reuse — copy-paste style/logic
- CSS tidak ada design token — warna/spacing hardcode
- JS tidak ada module — semua global scope
- Sulit test — tidak ada unit test, tidak ada mock boundary

---

## 2. Struktur Target (Professional)

```
ana-hermes-dashboard/
├── server.py                 # entry point only (~30 lines)
├── app/
│   ├── __init__.py
│   ├── config.py             # env, constants, PORT, WORKDIR, PERMISSION
│   ├── routes/
│   │   ├── __init__.py       # route registry
│   │   ├── status.py         # GET /api/status
│   │   ├── projects.py       # GET /api/projects
│   │   ├── briefing.py       # GET /api/briefing
│   │   ├── voice.py          # /api/voices, /api/voice, /api/speak, /api/listen
│   │   ├── mode.py           # GET/POST /api/mode
│   │   └── run.py            # POST /api/run (NDJSON stream)
│   ├── services/
│   │   ├── hermes.py         # runtime.py → service (subprocess, session)
│   │   ├── voice.py          # voice.py → service
│   │   ├── commands.py       # commands.py → service
│   │   ├── projects.py       # project scanner (git scan)
│   │   └── briefing.py       # vault briefing loader
│   └── models/
│       └── __init__.py       # dataclass: ProjectCard, Briefing, Session
├── ui/
│   ├── index.html            # shell only — load modules
│   ├── css/
│   │   ├── tokens.css        # --cyan, --bg, --edge, spacing, radius
│   │   ├── base.css          # reset, body, grid-bg, scan
│   │   ├── layout.css        # .hud grid, .col, .topbar
│   │   ├── components.css    # .card, .chip, .ctl, .pill
│   │   ├── reactor.css       # .reactor, rings, arcs, animations
│   │   └── panels.css        # .response, .missionbar, .voicePanel
│   └── js/
│       ├── app.js            # boot only — import & init modules
│       ├── api.js            # fetch wrappers: getStatus, getProjects, run(), etc
│       ├── store.js          # shared state (mode, session, projects)
│       ├── components/
│       │   ├── reactor.js    # reactor SVG + ticks + animations
│       │   ├── projectCard.js # ProjectCard component
│       │   ├── briefingCard.js# BriefingCard component
│       │   ├── chatBar.js    # Chat input + send logic
│       │   ├── voicePicker.js# Voice dropdown + preview/apply
│       │   ├── actionLog.js  # Event stream renderer
│       │   └── systemPanel.js# Gateway/brain/voice pills
│       ├── services/
│       │   ├── voice.js      # TTS/STT, micToggle, speak()
│       │   └── transmit.js   # transmit(), handle(), renderAnswer()
│       └── utils.js          # esc, now, rid, cleanForSpeech
└── tests/
    ├── test_routes.py
    ├── test_services.py
    └── test_components.py
```

---

## 3. Komponen Reuseable

### 3.1 Design Tokens (`tokens.css`)
```css
:root {
  --cyan: #40f3ff; --cyan2: #16b8d4;
  --bg: #02070c; --panel: rgba(5,18,28,.64);
  --edge: rgba(57,232,255,.24);
  --radius-card: 18px; --radius-pill: 999px;
  --space-xs: 4px; --space-sm: 8px; --space-md: 16px;
  --font-mono: "JetBrains Mono", monospace;
  --font-disp: "Chakra Petch", sans-serif;
}
```

### 3.2 Komponen UI

| Komponen | File | Props | Reuse |
|----------|------|-------|-------|
| `Card` | `components.css` | `title, variant, padding` | Project, Briefing, Voice, Log |
| `Chip` | `components.css` | `label, color, ghost` | Tools, status, branch |
| `Button` | `components.css` | `variant (ctl/mic/run), icon, onClick` | Semua tombol |
| `Panel` | `components.css` | `header, body, glass` | Left/Right/Center panels |
| `ProjectCard` | `projectCard.js` | `name, branch, commit, dirty` | List projects |
| `BriefingCard` | `briefingCard.js` | `date, text` | Daily briefing |
| `ActionLog` | `actionLog.js` | `events[]` | Event stream |
| `Reactor` | `reactor.js` | `state (idle/running/listening)` | Center visualizer |

### 3.3 API Layer (`api.js`)
```js
// Semua fetch terpusat — ganti endpoint 1 tempat
export const api = {
  status: () => get('/api/status'),
  projects: () => get('/api/projects'),
  briefing: () => get('/api/briefing'),
  voices: () => get('/api/voices'),
  run: (msg, opts) => postStream('/api/run', {message: msg, ...opts}),
  speak: (text) => postBlob('/api/speak', {text}),
  setVoice: (id) => post('/api/voice', {voice_id: id}),
  setMode: (mode) => post('/api/mode', {mode}),
};
```

### 3.4 Store (`store.js`)
```js
// Shared state — tidak ada global variable berceceran
export const store = {
  mode: 'coding',
  session: null,
  projects: [],
  briefing: null,
  voice: null,
  running: false,
  subscribe(fn) { /* observer */ }
};
```

---

## 4. Fungsi Baru (Banyak Fungsi)

| Fitur | Deskripsi | File |
|-------|-----------|------|
| **Project quick actions** | Klik card → review, git pull, open in editor | `projectCard.js` |
| **Briefing editor** | Edit briefing inline, save ke vault | `briefingCard.js` |
| **Command palette** | `Cmd+K` → search commands | `components/commandPalette.js` |
| **Theme switch** | Cyan/Amber/Green reactor themes | `tokens.css` + `store.js` |
| **Layout presets** | Compact / Full / Focus mode | `layout.css` |
| **Keyboard shortcuts** | `Enter` send, `Esc` cancel, `Cmd+K` palette | `app.js` |
| **Auto-refresh** | Projects poll tiap 30s, briefing tiap 5m | `api.js` |
| **Error boundary** | Toast notification, tidak silent fail | `components/toast.js` |

---

## 5. Migrasi — Langkah Aman (Tidak Break Existing)

### Fase A: CSS Split (1-2 jam, zero risk)
1. `tokens.css` — extract `:root` variables
2. `base.css` — body, grid-bg, scan, ambient
3. `layout.css` — .hud, .col, .topbar
4. `components.css` — .card, .chip, .ctl
5. `reactor.css` — reactor + animations
6. `panels.css` — response, missionbar
7. `index.html` → 6x `<link>` — verify visual identik

### Fase B: JS Modular (2-3 jam, medium risk)
1. `utils.js` — esc, now, rid, cleanForSpeech
2. `api.js` — semua fetch wrappers
3. `store.js` — shared state
4. `components/*` — 1 per 1, test tiap extract
5. `app.js` — boot only, import modules
6. Verify: `node --check` + manual click semua tombol

### Fase C: Server Split (2-3 jam, medium risk)
1. `app/config.py` — env loading
2. `app/services/*` — hermes, voice, projects, briefing
3. `app/routes/*` — 1 file per endpoint group
4. `server.py` — registry + serve_forever only
5. Verify: `py_compile` + `curl /api/*` semua endpoint

### Fase D: Polish (1-2 jam)
1. Add `tests/` — minimal smoke test per route
2. Screenshot diff — before/after pixel compare
3. Update `README.md` + `docs/`

**Total: ~6-10 jam, incremental, tiap fase verifiable, rollback 1 file jika fail.**

---

## 6. Screenshot Target — Butuh Info

Vision tool tidak bisa baca `ana.png` / `Screenshot 00-45-17` (model tanpa vision).
Untuk desain akurat, butuh deskripsi:

1. **Layout** — masih 3 kolom? Atau berubah? (misal: top bar beda, grid beda)
2. **Warna** — masih cyan? Atau ada warna baru?
3. **Komponen baru** — ada panel/card yang belum ada sekarang?
4. **Typography** — font sama atau ganti?
5. **Reactor** — masih ada atau diganti visual lain?

**Opsi:**
- Deskripsikan 3-5 perbedaan utama target vs sekarang (paling cepat)
- Atau: saya inspect `ana.png` via browser manual dan buat HTML preview untuk compare

---

## 7. Keputusan — Tunggu Approval

- [ ] Setuju struktur di atas? Atau ada preferensi lain (misal: tetap 1 file tapi rapikan saja)?
- [ ] Deskripsikan target screenshot (3-5 poin)?
- [ ] Prioritas fase? (A → B → C → D, atau langsung B?)

Setelah approval → eksekusi Fase A dulu (CSS split, zero risk, 1 jam).
