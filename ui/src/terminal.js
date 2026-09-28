// Terminal panel — xterm.js over a pty(7) session on the server.
//
// Self-contained: it owns its DOM, its server session, and its stream
// reader. Needs only `api`, `token` and a `log` callback, so main.js does
// not have to hold any of it.

const SESSIONS = new Map();
const PANELS = new Map();
const KEY = 'termPanel';

export function createTerminal({ api, token, log, hud, isOpen }) {
  function close() {
    const panel = PANELS.get(KEY);
    const id = SESSIONS.get(KEY);
    const ctrl = SESSIONS.get(KEY + ':ctrl');
    if (ctrl) try { ctrl.abort(); } catch (_) {}
    const term = id ? SESSIONS.get(KEY + '+' + id) : null;
    if (term) try { term.dispose(); } catch (_) {}
    const ro = id ? SESSIONS.get(KEY + '+' + id + ':resize') : null;
    if (ro) try { ro.disconnect(); } catch (_) {}
    const winResize = SESSIONS.get(KEY + ':win');
    if (winResize) window.removeEventListener('resize', winResize);
    if (id) {
      api.post('/api/terminal', { action: 'close', id }).catch(() => {});
      SESSIONS.delete(KEY + '+' + id);
      SESSIONS.delete(KEY + '+' + id + ':resize');
    }
    SESSIONS.delete(KEY + ':ctrl');
    SESSIONS.delete(KEY + ':win');
    SESSIONS.delete(KEY);
    if (panel) panel.remove();
    PANELS.delete(KEY);
    log('note', 'TERM', 'terminal closed');
  }

  function fail(panel, msg) {
    log('error', 'TERM', msg);
    panel.remove();
    PANELS.delete(KEY);
  }

  async function open() {
    if (!hud) return;
    if (PANELS.get(KEY)?.isConnected) return;

    const panel = document.createElement('div');
    panel.className = 'panel terminal-panel';
    panel.id = KEY;
    panel.innerHTML = `
      <div class="panel-title" style="display:flex;justify-content:space-between;align-items:center">TERMINAL <span class="term-id" style="font-weight:400;opacity:.6"></span><button class="term-close" title="Close" style="background:transparent;border:1px solid var(--neon-dim);color:var(--text-dim);border-radius:2px;padding:0 6px;cursor:pointer;font-size:11px">✕</button></div>
      <div class="panel-body" style="padding:0;overflow:hidden;display:flex;flex-direction:column">
        <div id="termCanvas" style="flex:1;min-height:220px;background:#001126"></div>
      </div>
    `;
    hud.appendChild(panel);
    // Without a rail the layout manager falls back to the rect the panel
    // already has, which is 0,0 full width — it then lands on top of the
    // top controls and covers STATUS/TOOLS/mute/Clear/Terminal. Park it in
    // the right rail and let the manager do the placement.
    panel.dataset.rail = 'right';
    panel.querySelector('.term-close').addEventListener('click', close);
    PANELS.set(KEY, panel);
    if (window._layoutManager) {
      window._layoutManager.register(KEY);
      // Terminal panel created after initPanelOptions ran — add it to the
      // Options menu if the menu already exists.
      if (document.getElementById('panelOptionsMenu')) {
        const list = document.getElementById('panelOptionsList');
        if (list && !list.querySelector('input[data-id="termPanel"]')) {
          const label = document.createElement('label');
          label.className = 'panel-opt';
          label.innerHTML = `<input type="checkbox" data-id="termPanel" checked> TERMINAL`;
          list.appendChild(label);
          label.querySelector('input').addEventListener('change', e => {
            window._layoutManager.setPanelEnabled('termPanel', e.target.checked);
          });
        }
      }
    }

    const termIdEl = panel.querySelector('.term-id');
    const canvas = panel.querySelector('#termCanvas');

    let j;
    try { j = await api.post('/api/terminal', { action: 'create', cols: 90, rows: 28 }); }
    catch { fail(panel, 'Server unreachable'); return; }
    if (!j.ok || !j.id) { fail(panel, 'Gagal create terminal: ' + (j.error || 'unknown')); return; }

    const id = j.id;
    if (termIdEl) termIdEl.textContent = `(${id.slice(0, 8)})`;
    SESSIONS.set(KEY, id);

    const term = new Terminal({
      cursorBlink: true, fontSize: 13,
      fontFamily: 'Share Tech Mono, monospace',
      theme: { background: '#001126', foreground: '#B0D8E8', cursor: '#00E8FF', selectionBackground: 'rgba(0,232,255,0.3)' },
      scrollback: 5000, convertEol: true,
    });
    const fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(canvas);
    try { fitAddon.fit(); } catch (_) {}
    api.post('/api/terminal', { action: 'resize', id, cols: term.cols, rows: term.rows }).catch(() => {});

    const resizeObs = new ResizeObserver(() => {
      try {
        fitAddon.fit();
        api.post('/api/terminal', { action: 'resize', id, cols: term.cols, rows: term.rows }).catch(() => {});
      } catch (_) {}
    });
    resizeObs.observe(canvas);
    const onWinResize = () => { try { fitAddon.fit(); } catch (_) {} };
    window.addEventListener('resize', onWinResize);

    term.onData(data => { api.post('/api/terminal', { action: 'input', id, data }).catch(() => {}); });
    term.focus();

    // Raw PTY stream via fetch — the server sends application/octet-stream,
    // not SSE, so this is a raw reader with no framing.
    const ctrl = new AbortController();
    SESSIONS.set(KEY + ':ctrl', ctrl);
    SESSIONS.set(KEY + '+' + id, term);
    SESSIONS.set(KEY + '+' + id + ':resize', resizeObs);
    SESSIONS.set(KEY + ':win', onWinResize);
    const url = `/api/terminal-stream?id=${encodeURIComponent(id)}&token=${encodeURIComponent(token)}`;
    try {
      const res = await fetch(url, { headers: { 'X-Ana-Token': token }, signal: ctrl.signal });
      if (!res.ok) { log('error', 'TERM', 'stream failed HTTP ' + res.status); return; }
      const reader = res.body.getReader();
      const dec = new TextDecoder('utf-8', { fatal: false });
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        if (value && value.length) term.write(dec.decode(value, { stream: true }));
      }
    } catch (e) {
      if (e?.name !== 'AbortError') log('note', 'TERM', 'stream ended: ' + String(e).slice(0, 120));
    } finally {
      window.removeEventListener('resize', onWinResize);
    }
  }

  function toggle() {
    if (isOpen()) { close(); return; }
    open();
  }

  // Ctrl+` / Cmd+`
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === '`') { e.preventDefault(); toggle(); }
  });

  return { toggle, close, isOpen: () => !!PANELS.get(KEY)?.isConnected };
}
