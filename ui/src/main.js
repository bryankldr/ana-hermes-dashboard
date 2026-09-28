import { state } from './core/bus.js';
import { api } from './core/api.js';
import { LayoutManager } from './core/layout.js';
import { now, rid, esc, cleanForSpeech } from './utils/helpers.js';
import { ensurePanel } from './utils/dom.js';
import { createTerminal } from './terminal.js';

// ═══ DOM refs ═══
const $ = id => document.getElementById(id);
const els = {
  hud: $('hud'), particles: $('particles'), topDials: $('topDials'),
  octFrame: $('octFrame'), radialTicks: $('radialTicks'), orbitalParticles: $('orbitalParticles'),
  coreLabel: $('coreLabel'), matrixGrid: $('matrixGrid'), workspaceSvg: $('workspaceSvg'),
  pipeline: $('pipeline'), teleCpu: $('teleCpu'), teleRam: $('teleRam'),
  equalizer: $('equalizer'), equalizerWrap: $('equalizerWrap'), chatInput: $('chatInput'), sendBtn: $('sendBtn'),
  micBtn: $('micBtn'), modeBtn: $('modeBtn'), responseText: $('responseText'),
  eventLog: $('eventLog'), eventEntries: $('eventEntries'), codeViewer: $('codeViewer'), cvBody: $('cvBody'),
  stModel: $('stModel'), stMode: $('stMode'), stCtx: $('stCtx'), stMem: $('stMem'),
  stSess: $('stSess'),
};

// Token for layout API (avoids relying on __ANA_TOKEN__ injected into JS)
const ANA_TOKEN = document.querySelector('meta[name="ana-token"]')?.content || '';

// ═══ STATE ═══
let running = false, answer = '', firstDelta = false, speakThisRun = true;
let speakDone = Promise.resolve(), activeController = null;
let muted = false, player = null;
let convo = false, suppress = false;
let recognition = null;
let micStream = null, recorder = null, chunks = [], actx = null, analyser = null, vdata = null;
let vad = null, spoke = false, loudAt = 0, turnStart = 0;
let floorSum = 0, floorN = 0, threshold = 0.02, peak = 0, calibrating = true;
const SILENCE = 900, MIN_TURN_MS = 350, MAX_TURN_MS = 18000, NO_SPEECH_MS = 10000;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const speechSynth = window.speechSynthesis;
// ANA live progress state
let progSteps = [], progStart = 0, progTimer = null;
let codeDiffBuf = '';

// ═══ HELPERS ═══
// now/rid/esc/cleanForSpeech live in utils/helpers.js (imported above).

function setAgentState(agentState) {
  state.agentStatus = agentState;
  els.coreLabel.textContent = agentState;
  const stages = ['intent', 'context', 'memory', 'reasoning', 'tools', 'result'];
  const stageMap = { 'UNDERSTANDING': 1, 'PLANNING': 2, 'EXECUTING': 4, 'ANALYZING': 3, 'RESPONDING': 5, 'WAITING_TOOL': 4, 'ERROR': -1 };
  const si = stageMap[agentState] ?? 0;
  document.querySelectorAll('.pipe-node').forEach((n, i) => n.classList.toggle('active', i <= si && si > 0));
  if (agentState === 'EXECUTING') setMatrixActive('TOOL');
  else if (agentState === 'ANALYZING') setMatrixActive('SRCH');
  else if (agentState === 'RESPONDING') setMatrixActive('CODE');
  else setMatrixActive(null);
}

// ═══ LIVE PROGRESS — Fase A (ANA) ═══
function ensureProgressPanel(){
  let p = document.getElementById('progressPanel');
  if(p) return p;
  p = document.createElement('div');
  p.id='progressPanel'; p.className='panel';
  p.innerHTML='<div class=\"panel-title\" style=\"display:flex;justify-content:space-between;align-items:center\"><span>LIVE PROGRESS</span><span id=\"progressEta\" class=\"progress-eta\"></span></div><div class=\"progress-bar-wrap\"><div id=\"progressBar\" class=\"progress-bar\"></div></div><div id=\"progressSteps\" class=\"progress-steps\"></div><button id=\"progressCancel\" class=\"progress-cancel\">✕ Cancel (Esc)</button>';
  els.hud?.appendChild(p);
  p.querySelector('#progressCancel').addEventListener('click', ()=>{ if(activeController) activeController.abort(); fetch('/api/cancel',{method:'POST',headers:api.headers({'content-type':'application/json'}),body:'{}'}).catch(()=>{}); });
  return p;
}
function progressReset(msg){
  progSteps=[]; progStart=Date.now(); codeDiffBuf='';
  const panel=ensureProgressPanel();
  panel.classList.add('active');
  document.getElementById('progressBar').style.width='6%';
  document.getElementById('progressSteps').innerHTML='<div class=\"progress-step active\">▸ '+esc(msg||'starting')+'<span class=\"step-time\">0.0s</span></div>';
  setAgentState('PLANNING');
  if(progTimer) clearInterval(progTimer);
  progTimer=setInterval(()=>{
    const el=document.getElementById('progressEta');
    if(el && progStart) el.textContent=((Date.now()-progStart)/1000).toFixed(1)+'s';
  },400);
}
function progressStep(label, state='active'){
  const wrap=document.getElementById('progressSteps');
  if(!wrap) return;
  const t=((Date.now()-progStart)/1000).toFixed(1)+'s';
  // mark previous active as done
  wrap.querySelectorAll('.progress-step.active').forEach(e=>{e.classList.remove('active');e.classList.add('done');e.innerHTML=e.innerHTML.replace('▸','✓');});
  const d=document.createElement('div');
  d.className='progress-step '+state;
  const icon=state==='done'?'✓':state==='error'?'✗':'▸';
  d.innerHTML=icon+' '+esc(label)+' <span class=\"step-time\">'+t+'</span>';
  wrap.appendChild(d); wrap.scrollTop=wrap.scrollHeight;
  const pct=Math.min(92, 10+progSteps.length*12);
  const bar=document.getElementById('progressBar');
  if(bar) bar.style.width=pct+'%';
  progSteps.push(label);
}
function progressDone(ok=true){
  if(progTimer){clearInterval(progTimer); progTimer=null;}
  const bar=document.getElementById('progressBar');
  if(bar) bar.style.width=ok?'100%':'100%';
  if(bar) bar.style.background=ok?'linear-gradient(90deg, #4ade80, #86efac)':'linear-gradient(90deg, #f87171, #fca5a5)';
  // finalize last active
  const wrap=document.getElementById('progressSteps');
  if(wrap) wrap.querySelectorAll('.progress-step.active').forEach(e=>{e.classList.remove('active');e.classList.add(ok?'done':'error');});
  setTimeout(()=>{ const p=document.getElementById('progressPanel'); if(p) p.classList.remove('active'); if(bar){bar.style.width='0%'; bar.style.background='';}}, 3500);
}

// ═══ CODE DIFF VIEWER — Fase B ═══
function showCodeDiff(title, diff){
  const v=document.getElementById('codeViewer');
  if(!v) return;
  v.classList.add('visible','live');
  const h=v.querySelector('.cv-header');
  if(h) h.textContent=title||'CODE DIFF';
  const body=document.getElementById('cvBody');
  if(body){
    // simple diff highlight: lines starting + / -
    body.innerHTML=esc(diff).split('\n').map(l=>{
      if(l.startsWith('+')&&!l.startsWith('+++')) return '<span class=\"cv-diff-add\">'+esc(l)+'</span>';
      if(l.startsWith('-')&&!l.startsWith('---')) return '<span class=\"cv-diff-del\">'+esc(l)+'</span>';
      return esc(l);
    }).join('\n');
  }
  // ensure actions
  let acts=v.querySelector('.cv-actions');
  if(!acts){
    acts=document.createElement('div'); acts.className='cv-actions';
    acts.innerHTML='<button class=\"cv-btn-apply\">Apply</button><button class=\"cv-btn-undo\">Dismiss</button>';
    v.appendChild(acts);
    acts.querySelector('.cv-btn-undo').addEventListener('click', ()=>v.classList.remove('visible','live'));
    acts.querySelector('.cv-btn-apply').addEventListener('click', ()=>{ log('code','CODE','diff acknowledged'); v.classList.remove('visible','live'); });
  }
}

// ═══ MISSION KANBAN — Fase C ═══
async function refreshKanban(){
  try{
    const data=await api.getMissions();
    const el=ensurePanel({id:'missionKanban',title:'MISSION KANBAN',body:'<div id="kanbanGrid" style="display:flex;gap:6px"></div>',rail:'left'});
    const grid=el.querySelector('#kanbanGrid');
    const tasks=(data.tasks||[]).slice(-8);
    const missions=(data.missions||[]).slice(-8);
    const open=tasks.filter(t=>!t.done);
    const done=tasks.filter(t=>t.done).concat(missions.filter(m=>m.status==='done'));
    const col=(title, items, emptyMsg)=>'<div class="kanban-col"><div class="kanban-head">'+title+' ('+items.length+')</div>'+(items.length?items.map(it=>'<div class="kanban-card '+(it.done||it.status==='done'?'done':'')+'" title="'+esc(it.text||it.mission||'')+'">'+esc((it.text||it.mission||'').slice(0,48))+'<div style="font-size:10px;color:var(--text-dim)">'+esc(it.at?new Date(it.at*1000).toLocaleTimeString(): '')+'</div></div>').join(''):'<div class="kanban-empty">'+emptyMsg+'</div>')+'</div>';
    grid.innerHTML=col('OPEN',open,'Kosong — /mission &lt;task&gt;')+col('DONE',done.slice(-6),'—');
    grid.querySelectorAll('.kanban-card:not(.done)').forEach(c=>{
      c.addEventListener('click', ()=>{
        const txt=c.getAttribute('title')||c.textContent;
        log('kanban','KANBAN','→ '+txt.slice(0,60));
        transmit(txt);
      });
    });
  }catch(e){}
}

// ═══ VAULT + AVD — Fase D ═══
async function refreshVault(){
  try{
    const data=await api.getVault();
    const el=ensurePanel({id:'vaultPanel',title:'VAULT STATUS',body:'<div id="vaultBody"></div>',rail:'left'});
    const body=el.querySelector('#vaultBody');
    const exists=data.skill_note_exists;
    body.innerHTML='<div class="vault-stat"><span>Vault</span><b>'+esc((data.vault||'').split('/').slice(-2).join('/')||'—')+'</b></div>'
      +'<div class="vault-stat"><span>Daily notes</span><b>'+(data.daily_count??'—')+'</b></div>'
      +'<div class="vault-stat"><span>SKILL/skill_note.md</span><b style="color:'+(exists?'#4ade80':'#f87171')+'">'+(exists?'✓ ada':'✗ belum')+'</b></div>'
      +(exists?'<div style="font-size:10px;color:var(--text-dim);margin-top:4px;max-height:60px;overflow:auto;white-space:pre-wrap">'+esc((data.skill_preview||'').slice(0,400))+'</div>':'');
  }catch(e){}
}
async function refreshAvd(){
  try{
    const data=await api.getAvd();
    const el=ensurePanel({id:'avdPanel',title:'ANDROID AVD',body:'<div id="avdBody"></div>',rail:'left'});
    const body=el.querySelector('#avdBody');
    const running=data.device==='device' && data.boot_completed==='1';
    const offline=!data.device || data.device==='offline';
    const statusCls=running?'running':'offline';
    const statusTxt=running?'● RUNNING (boot 1)': offline?'○ OFFLINE': '◐ '+esc(data.device||'?');
    body.innerHTML='<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
      +'<span class="avd-status '+statusCls+'">'+statusTxt+'</span>'
      +'<span style="font-size:10px;color:var(--text-dim)">'+esc((data.avds||'').split('\n')[0]||'Pixel_9')+'</span></div>'
      +'<div style="display:flex;gap:4px;margin-top:6px"><button id="avdStart" class="avd-btn avd-start">▶ Start</button><button id="avdStop" class="avd-btn avd-stop">■ Stop</button><button id="avdRefresh" class="avd-btn" style="background:rgba(0,220,255,0.06);border:1px solid rgba(0,220,255,0.15);color:var(--text-dim)">↻</button></div>'
      +'<div style="font-size:10px;color:var(--text-dim);margin-top:4px;white-space:pre-wrap">'+esc((data.adb||'').slice(0,160))+'</div>';
    body.querySelector('#avdStart')?.addEventListener('click', async()=>{
      log('avd','AVD','starting Pixel_9...'); const r=await api.avdAction('start'); log('avd','AVD', r.msg||r.error||JSON.stringify(r).slice(0,120)); setTimeout(refreshAvd, 5000);
    });
    body.querySelector('#avdStop')?.addEventListener('click', async()=>{
      log('avd','AVD','stopping...'); const r=await api.avdAction('stop'); log('avd','AVD', r.msg||r.error||JSON.stringify(r).slice(0,120)); setTimeout(refreshAvd, 2000);
    });
    body.querySelector('#avdRefresh')?.addEventListener('click', refreshAvd);
  }catch(e){}
}

// ═══ EVENT LOG ═══
function log(kind, label, msg, jsonHtml) {
  if (!els.eventEntries) return;
  const e = document.createElement('div');
  e.className = 'event-entry';
  e.innerHTML = `<span class="event-time">${now()}</span><span class="event-msg">[${esc(label)}] ${esc(msg)}</span>`;
  els.eventEntries.appendChild(e);
  els.eventEntries.scrollTop = els.eventEntries.scrollHeight;
  const entries = els.eventEntries.querySelectorAll('.event-entry');
  if (entries.length > 50) entries[0].remove();
}
function usageBlock(u) {
  const row = (k, v) => `  <span class="k">"${k}"</span>: <span class="v">${v}</span>`;
  return `{\n  <span class="k">"usage"</span>: {\n` + [row('input_tokens', u.input_tokens), row('output_tokens', u.output_tokens), row('total_tokens', u.total_tokens)].join(',\n') + `\n  }\n}`;
}

// ═══ PARTICLES ═══
function initParticles() {
  const canvas = els.particles, ctx = canvas.getContext('2d');
  let w, h, dots;
  function resize() {
    w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight;
    dots = Array.from({length: 60}, () => ({ x: Math.random()*w, y: Math.random()*h, r: Math.random()*1.5+0.5, o: Math.random()*0.5+0.2, vx: (Math.random()-0.5)*0.2, vy: (Math.random()-0.5)*0.2 }));
  }
  function draw() {
    ctx.clearRect(0, 0, w, h);
    for (const d of dots) {
      ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, Math.PI*2);
      ctx.fillStyle = `rgba(0, 232, 255, ${d.o})`; ctx.fill();
      d.x += d.vx; d.y += d.vy;
      if (d.x < 0 || d.x > w) d.vx *= -1;
      if (d.y < 0 || d.y > h) d.vy *= -1;
    }
    requestAnimationFrame(draw);
  }
  resize(); window.addEventListener('resize', resize); draw();
}

// ═══ TOP DIALS ═══
const DIAL_LABELS = ['CPU', 'RAM', 'GPU', 'AI', 'TOOLS', 'FILES', 'CODE', 'SYS'];
function initDials() {
  els.topDials.innerHTML = DIAL_LABELS.map((label, i) => `
    <div class="dial"><svg viewBox="0 0 40 40">
      <circle cx="20" cy="20" r="18" fill="none" stroke="rgba(0,232,255,0.2)" stroke-width="1"/>
      <circle cx="20" cy="20" r="14" fill="none" stroke="rgba(0,232,255,0.3)" stroke-width="0.5"/>
      <path d="M20 20 L20 4" stroke="rgba(0,232,255,0.6)" stroke-width="0.5" transform="rotate(${i*45} 20 20)"/>
      <circle cx="20" cy="20" r="2" fill="rgba(0,232,255,0.8)"/>
    </svg><span class="dial-label">${label}</span></div>`).join('');
}

// ═══ OCTAGONAL FRAME ═══
function initOctFrame() {
  const cx = 235, cy = 185, r = 160, n = 8, pts = [];
  for (let i = 0; i < n; i++) { const a = (i/n)*Math.PI*2 - Math.PI/2; pts.push(`${cx+r*Math.cos(a)},${cy+r*Math.sin(a)}`); }
  els.octFrame.setAttribute('points', pts.join(' '));
}

// ═══ RADIAL TICKS ═══
function initRadialTicks() {
  const cx = 235, cy = 185; let html = '';
  for (let i = 0; i < 36; i++) {
    const a = (i/36)*Math.PI*2, r1 = 125, r2 = i%9===0 ? 115 : 120;
    html += `<line x1="${cx+r1*Math.cos(a)}" y1="${cy+r1*Math.sin(a)}" x2="${cx+r2*Math.cos(a)}" y2="${cy+r2*Math.sin(a)}"/>`;
  }
  els.radialTicks.innerHTML = html;
}

// ═══ ORBITAL PARTICLES ═══
function initOrbitalParticles() {
  const cx = 235, cy = 185; let html = '';
  for (let i = 0; i < 12; i++) {
    const a = (i/12)*Math.PI*2, r = 70+(i%3)*20;
    html += `<circle cx="${cx+r*Math.cos(a)}" cy="${cy+r*Math.sin(a)}" r="${1+(i%2)}"><animateTransform attributeName="transform" type="rotate" from="0 ${cx} ${cy}" to="360 ${cx} ${cy}" dur="${15+i*2}s" repeatCount="indefinite"/></circle>`;
  }
  els.orbitalParticles.innerHTML = html;
}

// ═══ MATRIX GRID ═══
const MATRIX_ITEMS = ['CODE','GIT','TERM','FILE','SRCH','MEM','TOOL','BUILD','TEST','ERR','DEP','SVC'];
function initMatrix() {
  els.matrixGrid.innerHTML = MATRIX_ITEMS.map(item => `<div class="matrix-cell" data-item="${item}">${item}</div>`).join('');
}
function setMatrixActive(item) {
  document.querySelectorAll('.matrix-cell').forEach(c => c.classList.toggle('active', c.dataset.item === item));
}

// ═══ WORKSPACE WIREFRAME — Interactive ═══
function initWorkspace() {
  const panel = document.getElementById('workspacePanel');
  if (panel) {
    panel.innerHTML = `<div class="panel-title">WORKSPACE</div><div class="panel-body">
      <div class="workspace-grid">
        <div class="ws-item" data-path="src"><span class="ws-icon">📁</span><span class="ws-label">src</span></div>
        <div class="ws-item" data-path="lib"><span class="ws-icon">📁</span><span class="ws-label">lib</span></div>
        <div class="ws-item" data-path="api"><span class="ws-icon">📁</span><span class="ws-label">api</span></div>
        <div class="ws-item" data-path="test"><span class="ws-icon">📁</span><span class="ws-label">test</span></div>
        <div class="ws-item" data-path="docs"><span class="ws-icon">📁</span><span class="ws-label">docs</span></div>
        <div class="ws-item" data-path="config"><span class="ws-icon">📁</span><span class="ws-label">config</span></div>
      </div></div>`;
    panel.querySelectorAll('.ws-item').forEach(item => {
      item.addEventListener('click', () => {
        const path = item.dataset.path;
        intelLog(`📂 ${path}/`, 'info');
        log('workspace', 'WORKSPACE', `exploring ${path}/`);
      });
    });
  }
}

// ═══ INTELLIGENCE SURFACE — Live Chat + Tool Trace ═══
let convoMsgs = [];
let currentSessionId = null;
function initIntel() {
  const panel = document.getElementById('intelPanel');
  if (panel) {
    panel.innerHTML = `<div class="panel-title">INTELLIGENCE SURFACE</div>
      <div class="session-bar">SESSION: <span id="sessionId">—</span></div>
      <div class="session-selector">
        <select id="sessionSelect" class="session-select"><option value="">Loading sessions...</option></select>
        <button id="sessionNew" class="session-btn">+ NEW</button>
        <button id="sessionRefresh" class="session-btn">↻</button>
      </div>
      <div class="panel-body"><div id="intelTerminal" class="intel-terminal"><div class="intel-line dim">Waiting for agent activity...</div></div></div>`;
    document.getElementById('sessionNew').addEventListener('click', () => {
      api.setSession(null).then(() => {
        currentSessionId = null;
        document.getElementById('sessionId').textContent = '—';
        intelLog('🆕 New session started', 'session');
        log('session', 'SESSION', 'new session');
        refreshSessionSelector();
      });
    });
    document.getElementById('sessionRefresh').addEventListener('click', refreshSessionSelector);
    document.getElementById('sessionSelect').addEventListener('change', (e) => {
      const sid = e.target.value;
      if (!sid) return;
      api.setSession(sid).then((r) => {
        if (r.ok) {
          currentSessionId = sid;
          document.getElementById('sessionId').textContent = sid;
          intelLog(`🔗 Switched to session: ${sid}`, 'session');
          log('session', 'SESSION', `switched to ${sid}`);
        }
      });
    });
    refreshSessionSelector();
  }
}
async function refreshSessionSelector() {
  try {
    const data = await api.getSessions();
    const sel = document.getElementById('sessionSelect');
    if (!sel) return;
    const groups = data.groups || {};
    const current = data.current || currentSessionId;
    let html = '<option value="">— New Session —</option>';
    const groupLabels = { today: '📅 HARI INI', yesterday: '📅 KEMARIN', last_week: '📅 MINGGU LALU', older: '📅 LAMA' };
    for (const [key, label] of Object.entries(groupLabels)) {
      const sessions = groups[key] || [];
      if (sessions.length === 0) continue;
      html += `<optgroup label="${label}">`;
      for (const s of sessions) {
        html += `<option value="${s.id}" ${s.id === current ? 'selected' : ''}>${s.title} · ${s.last_active}</option>`;
      }
      html += '</optgroup>';
    }
    sel.innerHTML = html;
  } catch (e) {}
}
function intelLog(text, type = 'info') {
  const term = document.getElementById('intelTerminal');
  if (!term) return;
  const line = document.createElement('div');
  line.className = 'intel-line ' + type;
  line.textContent = text;
  term.appendChild(line);
  term.scrollTop = term.scrollHeight;
  while (term.children.length > 80) term.removeChild(term.firstChild);
}
function intelMsg(role, text) {
  // Prevent duplicate consecutive messages
  if (convoMsgs.length > 0 && convoMsgs[convoMsgs.length - 1].role === role && convoMsgs[convoMsgs.length - 1].text === text) return;
  convoMsgs.push({ role, text });
  if (convoMsgs.length > 40) convoMsgs.shift();
  const term = document.getElementById('intelTerminal');
  if (!term) return;
  term.innerHTML = '';
  for (const m of convoMsgs) {
    const line = document.createElement('div');
    line.className = 'intel-line ' + (m.role === 'user' ? 'user' : 'assistant');
    line.textContent = (m.role === 'user' ? '▸ YOU: ' : '▸ ANA: ') + m.text;
    term.appendChild(line);
  }
  term.scrollTop = term.scrollHeight;
}
function intelTool(name, input, ok, output) {
  const term = document.getElementById('intelTerminal');
  if (!term) return;
  const line = document.createElement('div');
  line.className = 'intel-line ' + (ok ? 'ok' : 'error');
  line.textContent = `⚡ ${name}(${input || ''}) → ${ok ? 'ok' : 'error'}${output ? ' · ' + output.slice(0, 120) : ''}`;
  term.appendChild(line);
  term.scrollTop = term.scrollHeight;
  while (term.children.length > 80) term.removeChild(term.firstChild);
}

// ═══ EQUALIZER ═══
function initEqualizer() {
  const canvas = els.equalizer, ctx = canvas.getContext('2d');
  canvas.width = 80; canvas.height = 24;
  const bars = 12, barW = canvas.width / bars; let phase = 0;
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < bars; i++) {
      const h = 4 + Math.sin(phase + i*0.35)*8 + Math.random()*4;
      ctx.fillStyle = `rgba(0, 232, 255, ${0.3 + h/32})`;
      ctx.fillRect(i*barW+1, canvas.height-h, barW-2, h);
    }
    phase += 0.12; requestAnimationFrame(draw);
  }
  draw();
}

// ═══ TELEMETRY SIMULATION ═══
function initTelemetry() {
  setInterval(() => {
    els.teleCpu.style.width = (20 + Math.random()*40) + '%';
    els.teleRam.style.width = (40 + Math.random()*30) + '%';
  }, 2000);
}

// ═══ SPEAK ═══
// cleanForSpeech is imported from utils/helpers.js.
function playMp3(url) {
  return new Promise(resolve => {
    const a = new Audio(url);
    a.onended = () => { URL.revokeObjectURL(url); resolve(true); };
    a.onerror = () => { URL.revokeObjectURL(url); log('error', 'VOICE', 'audio playback failed'); resolve(false); };
    a.play().catch(() => { URL.revokeObjectURL(url); resolve(false); });
  });
}

function speak(text) {
  return new Promise(async resolve => {
    text = cleanForSpeech(text);
    if (muted || !text) return resolve();
    const spoken = text.length > 700 ? text.slice(0, 680).replace(/\s+\S*$/, '') + '…' : text;
    suppress = true;
    els.hud.classList.add('speaking');

    // prefer server TTS (edge-tts mp3) — same path as voice preview
    try {
      const r = await fetch('/api/speak', {
        method: 'POST',
        headers: api.headers({ 'content-type': 'application/json' }),
        body: JSON.stringify({ text: spoken })
      });
      if (r.ok) {
        const ct = r.headers.get('content-type') || '';
        if (ct.includes('audio')) {
          const blob = await r.blob();
          const url = URL.createObjectURL(blob);
          const okPlay = await playMp3(url);
          els.hud.classList.remove('speaking');
          log('voice', 'VOICE', 'TTS played (server)');
          return resolve();
        }
      }
      let msg = ''; try { const j = await r.clone().json(); msg = j.error || ''; } catch (_) { msg = 'status ' + r.status; }
      if (msg) log('note', 'VOICE', 'server TTS: ' + msg.slice(0, 120) + ' — fallback browser');
    } catch (e) {
      log('note', 'VOICE', 'server TTS error: ' + String(e).slice(0, 120) + ' — fallback browser');
    }

    // fallback browser speechSynthesis
    if (speechSynth) {
      try {
        speechSynth.cancel();
        const u = new SpeechSynthesisUtterance(spoken);
        u.lang = 'id-ID';
        try { const vs = speechSynth.getVoices(); const idv = vs.find(v => /id[-_]ID/i.test(v.lang)) || vs.find(v => /Indones/i.test(v.name)); if (idv) u.voice = idv; } catch (_) {}
        u.rate = 1.0; u.pitch = 1.0; u.volume = 1;
        u.onend = u.onerror = () => { els.hud.classList.remove('speaking'); log('voice', 'VOICE', 'TTS played (browser)'); resolve(); };
        speechSynth.speak(u);
        return;
      } catch (e) {
        els.hud.classList.remove('speaking');
        log('error', 'VOICE', 'browser TTS error: ' + String(e).slice(0, 120));
      }
    }
    els.hud.classList.remove('speaking');
    resolve();
  });
}

// ═══ VOICE CONVERSATION ═══
function micToggle() {
  if (convo) { stopConvo(); return; }
  if (SpeechRecognition) {
    convo = true; suppress = false;
    els.micBtn.classList.add('on'); els.micBtn.textContent = '● Live';
    log('voice', 'VOICE', 'browser speech recognition open · listening');
    setAgentState('LISTENING');
    startBrowserRecognition(); return;
  }
  log('error', 'VOICE', 'no speech recognition available');
}
function stopConvo() {
  convo = false; suppress = false;
  if (recognition) { try { recognition.onend = null; recognition.stop(); } catch (_) {} recognition = null; }
  if (vad) { clearInterval(vad); vad = null; }
  if (recorder && recorder.state === 'recording') { recorder._cancel = true; try { recorder.stop(); } catch (_) {} }
  recorder = null;
  if (player) { try { player.pause(); } catch (_) {} }
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  if (actx) { actx.close().catch(() => {}); actx = null; analyser = null; }
  els.hud.classList.remove('speaking');
  els.micBtn.classList.remove('on'); els.micBtn.textContent = '🎤';
  log('voice', 'VOICE', 'conversation closed');
  setAgentState('IDLE');
}
function startBrowserRecognition() {
  if (!convo || suppress || !SpeechRecognition) return;
  recognition = new SpeechRecognition();
  recognition.lang = 'id-ID'; recognition.interimResults = true; recognition.continuous = false;
  let finalText = '';
  recognition.onresult = e => {
    let interim = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const txt = e.results[i][0].transcript;
      if (e.results[i].isFinal) finalText += txt; else interim += txt;
    }
    const shown = (finalText || interim || '').trim();
    if (shown) els.coreLabel.textContent = 'HEARD: ' + shown.slice(0, 30);
  };
  recognition.onerror = e => log('error', 'VOICE', `browser speech: ${e.error || 'error'}`);
  recognition.onend = async () => {
    const text = finalText.trim();
    if (!convo) return;
    if (!text) { if (!suppress) setTimeout(startBrowserRecognition, 250); return; }
    log('voice', 'VOICE', `browser transcribed: "${text}"`);
    els.chatInput.value = '';
    log('send', 'SEND', `auto-sent voice: ${text}`);
    await transmit(text);
    suppress = false;
    if (convo) setTimeout(startBrowserRecognition, 350);
  };
  setAgentState('LISTENING');
  try { recognition.start(); } catch (e) { log('error', 'VOICE', 'speech recognition failed to start'); }
}

// ═══ COMMAND MATRIX ═══
const PAYLOAD_COMMANDS = new Set(['/goal', '/browser', '/background', '/mission', '/personality']);
const TIPS = {
  '/new': 'Fresh thread — clears the Hermes conversation and starts clean.',
  '/goal': 'Say your standing objective, e.g. "ship the dashboard and verify tool access".',
  '/tools': 'Shows Hermes tool status from the active profile.',
  '/toolsets': 'Asks Hermes to list enabled toolsets and connected tools.',
  '/browser': 'Say a Chrome/browser mission, e.g. "inspect the current tab".',
  '/background': 'Say a mission, e.g. "research competitors and save a report".',
  '/mission': 'Add or read mission queue items.',
  '/personality': 'Set the persona, e.g. "calm, laconic, Stark tower operator".',
  '/kanban': 'Ask about the work queue, e.g. "what\'s on my board today?".',
  '/commands': 'Show all dashboard slash commands.'
};
let defaultTip = '';
function initCommandMatrix() {
  const cmds = ['/new','/goal','/tools','/browser','/background','/mission','/personality','/commands'];
  const matrix = document.createElement('div');
  matrix.className = 'panel'; matrix.id = 'cmdPanel';
  matrix.innerHTML = `<div class="panel-title">COMMAND MATRIX</div><div class="panel-body"><div class="cmd-grid">${cmds.map(c => `<button class="cmd-btn" data-cmd="${c}">${c}</button>`).join('')}</div></div>`;
  document.querySelector('.left-rail').appendChild(matrix);
  matrix.addEventListener('click', e => {
    const b = e.target.closest('.cmd-btn'); if (!b) return;
    const cmd = b.dataset.cmd;
    if (running) { log('note', 'BUSY', `${cmd} not sent — ANA is still working.`); return; }
    if (PAYLOAD_COMMANDS.has(cmd)) {
      b.classList.add('armed');
      els.chatInput.dataset.cmd = cmd; els.chatInput.focus();
      log('command', 'COMMAND', `${cmd} armed — type payload next`);
    } else {
      log('command', 'COMMAND', `executing ${cmd} on Hermes backend`);
      transmit(cmd, { speak: !['/tools', '/commands'].includes(cmd) });
    }
  });
}
function disarm() {
  document.querySelectorAll('.cmd-btn').forEach(c => c.classList.remove('armed'));
  els.chatInput.dataset.cmd = '';
}

// ═══ QUICK MISSION BUTTONS ═══
function initQuickButtons() {
  const quicks = ['/status', '/tools', '/toolsets', '/connectors'];
  const bar = document.createElement('div');
  bar.className = 'quick-bar';
  bar.innerHTML = quicks.map(q => `<button class="quick-btn" data-quick="${q}">${q.slice(1).toUpperCase()}</button>`).join('');
  document.getElementById('topControls').appendChild(bar);
  bar.addEventListener('click', e => {
    const b = e.target.closest('.quick-btn'); if (!b) return;
    transmit(b.dataset.quick, { speak: false });
  });
}

// ═══ CHAT INPUT ═══
function sendFromChat() {
  const raw = els.chatInput.value.trim();
  const armed = els.chatInput.dataset.cmd || '';
  if (!raw && !armed) return;
  const full = (armed && !raw.startsWith('/')) ? `${armed} ${raw}` : (raw || armed);
  els.chatInput.value = '';
  disarm();
  log('send', 'SEND', `transmit (chat): ${full}`);
  transmit(full);
}
els.sendBtn.addEventListener('click', sendFromChat);
els.chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendFromChat(); }
});

// ═══ TRANSMIT ═══
async function transmit(message, options = {}) {
  if (!message.trim()) return;
  if (running) { log('note', 'BUSY', `still working — "${message.slice(0, 40)}" not sent. Wait, or press Esc to cancel.`); return; }
  running = true; answer = ''; firstDelta = false; speakThisRun = options.speak !== false;
  convoMsgs = [];
  const fresh = /^\/new\b/.test(message.trim());
  const id = rid();
  setAgentState('UNDERSTANDING');
  progressReset(message.slice(0, 48));
  els.responseText.innerHTML = '<span class="cur"></span>';
  intelMsg('user', message);
  log('run', 'RUN', `started ${id}; uplink cleared`);
  const t0 = performance.now();
  const tick = setInterval(() => {
    if (!running) return;
    const s = ((performance.now() - t0) / 1000).toFixed(1);
    if (!answer) els.coreLabel.textContent = `thinking… ${s}s`;
  }, 200);
  try {
    activeController = new AbortController();
    const res = await fetch('/api/run', {
      method: 'POST', headers: api.headers({ 'content-type': 'application/json' }),
      body: JSON.stringify({ message, fresh }), signal: activeController.signal
    });
    if (!res.ok) throw new Error(`backend returned HTTP ${res.status}`);
    const reader = res.body.getReader(); const dec = new TextDecoder(); let buf = '';
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n')) >= 0) { const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (line) handle(JSON.parse(line)); }
    }
  } catch (e) {
    if (e?.name === 'AbortError') { log('note', 'CANCEL', 'run cancelled'); setAgentState('IDLE'); progressDone(false); }
    else { log('error', 'ERROR', String(e).slice(0, 200)); setAgentState('ERROR'); progressDone(false); }
  }
  activeController = null; running = false; clearInterval(tick);
  // progressDone handled in complete/error; fallback if no complete
  if (running === false && progTimer) {
    // if handle didn't already close, keep bar a bit then close via timeout inside progressDone
  }
  await speakDone;
}

function handle(ev) {
  switch (ev.t) {
    case 'session':
      if (ev.session_id) {
        els.stSess.textContent = ev.session_id.slice(0, 8);
        currentSessionId = ev.session_id;
        const sid = document.getElementById('sessionId');
        if (sid) sid.textContent = ev.session_id;
      }
      break;
    case 'status':
      if (ev.session_id) { els.stSess.textContent = ev.session_id.slice(0, 8); const sid = document.getElementById('sessionId'); if (sid) sid.textContent = ev.session_id; }
      log('status', 'STATUS', `core online · Hermes tools=${ev.tools ?? 0} profile=${ev.profile || 'default'} permission=${ev.permission || 'normal'}`);
      progressStep(`core online · ${ev.tools ?? 0} tools`);
      setAgentState('UNDERSTANDING');
      break;
    case 'latency': log('latency', 'LATENCY', `first token after ${ev.ms}ms`); progressStep(`first token ${ev.ms}ms`); setAgentState('ANALYZING'); break;
    case 'tool':
      if (ev.phase === 'use') { log('tool', 'TOOL', `→ ${ev.name}(${ev.input || ''})`); intelTool(ev.name, ev.input || '', true, ''); progressStep(`TOOL → ${ev.name}`); setAgentState('ANALYZING'); }
      else {
        log('tool', 'TOOL', `✓ ${ev.ok === false ? 'error' : 'ok'}`); intelTool(ev.name, '', ev.ok !== false, ev.output || '');
        if (ev.ok === false) progressStep(`TOOL ✗ ${ev.name}`, 'error');
        else progressStep(`TOOL ✓ ${ev.name}`, 'done');
        // Fase B: auto diff viewer for file edits
        const out = ev.output || '';
        if (out && (out.includes('diff --git') || out.includes('+++ ') || (ev.name && /write_file|patch|edit/i.test(ev.name)))) {
          const title = `CODE · ${ev.name}`;
          if (out.length < 8000) showCodeDiff(title, out.slice(0, 6000));
          else showCodeDiff(title, out.slice(0, 6000) + '\n…truncated');
        }
      }
      break;
    case 'delta':
      answer += ev.text; renderAnswer();
      if (!firstDelta) { firstDelta = true; log('reason', 'REASONING', answer.slice(0, 220)); progressStep('streaming response'); setAgentState('RESPONDING'); }
      break;
    case 'usage': log('status', 'COMPLETE', 'run completed', usageBlock(ev)); break;
    case 'complete':
      setAgentState('RESPONDING');
      log('complete', 'COMPLETE', ev.ms != null ? `run completed in ${ev.ms}ms` : 'run completed');
      renderAnswer(true);
      intelMsg('assistant', answer);
      progressDone(true);
      speakDone = speakThisRun ? speak(answer) : Promise.resolve();
      // refresh kanban/vault after complete
      refreshKanban().catch(()=>{}); refreshVault().catch(()=>{});
      break;
    case 'error':
      setAgentState('ERROR');
      log('error', 'ERROR', ev.message || 'unknown');
      if (!answer) els.responseText.innerHTML = `<span style="color:var(--red)">⚠ ${esc(ev.message || 'Run failed.')}</span>`;
      else renderAnswer(true);
      progressDone(false);
      break;
    case 'note': log('note', 'NOTE', ev.message || ''); break;
  }
}
function renderAnswer(finaldone) {
  els.responseText.innerHTML = esc(answer) + (finaldone ? '' : '<span class="cur"></span>');
  els.responseText.scrollTop = els.responseText.scrollHeight;
}

function applyMode(m) {
  state.mode = (m === 'asisten' ? 'asisten' : 'coding');
  els.modeBtn.textContent = state.mode.toUpperCase();
  log('note', 'MODE', state.mode === 'asisten' ? 'Mode asisten — jawaban ringkas tanpa markdown/code' : 'Mode coding — jawaban lengkap dengan markdown/code');
}
async function setMode(m) {
  try {
    const r = await fetch('/api/mode', { method: 'POST', headers: api.headers({ 'content-type': 'application/json' }), body: JSON.stringify({ mode: m }) });
    const j = await r.json(); if (j.mode) applyMode(j.mode);
  } catch (e) { log('error', 'MODE', String(e).slice(0, 120)); }
}
els.modeBtn.addEventListener('click', () => setMode(state.mode === 'coding' ? 'asisten' : 'coding'));

// ═══ VOICE PICKER ═══
let voicesCache = [];
async function loadVoices() {
  try {
    const r = await fetch('/api/voices', { headers: api.headers() });
    const d = await r.json(); voicesCache = d.voices || [];
    const cur = d.current || '';
    const all = d.has_eleven ? [{ id: '21m00Tcm4TlvDq8ikWAM', name: 'Rachel (EN, multilingual)', gender: 'female', desc: 'Calm British' }, ...voicesCache] : [...voicesCache];
    const vp = ensurePanel({
      id: 'voicePicker', title: 'VOICE CONFIG', rail: 'right',
      body: `<select id="voiceSelect" class="voice-select"></select>
        <div class="voice-btns"><button id="voicePreview" class="voice-btn">Preview</button><button id="voiceApply" class="voice-btn primary">Pakai</button></div>
        <div id="voiceDesc" class="voice-desc"></div>`,
    });
    // Wire the buttons once; the option list is refreshed on every call,
    // because applyVoice() re-invokes loadVoices() to show the new selection.
    if (!vp.dataset.wired) {
      vp.dataset.wired = '1';
      vp.querySelector('#voicePreview').addEventListener('click', previewVoice);
      vp.querySelector('#voiceApply').addEventListener('click', applyVoice);
    }
    const sel = vp.querySelector('#voiceSelect');
    if (sel) {
      sel.innerHTML = all.map(v => `<option value="${v.id}" ${v.id === cur ? 'selected' : ''}>${v.name} - ${v.desc.slice(0, 40)}</option>`).join('');
      const curObj = all.find(v => v.id === cur) || all[0];
      const desc = vp.querySelector('#voiceDesc');
      if (desc && curObj) desc.textContent = curObj.desc + ' | ' + (curObj.gender || '') + ' | ' + curObj.id.slice(0, 8) + '..';
    }
  } catch (e) { const d = document.getElementById('voiceDesc'); if (d) d.textContent = 'Gagal memuat daftar suara'; }
}
async function previewVoice() {
  const sel = document.getElementById('voiceSelect'); if (!sel) return;
  const name = sel.options[sel.selectedIndex]?.textContent?.split(' - ')[0] || sel.value.slice(0, 8);
  const text = 'Halo Pak, saya ' + name + '. Ini preview suara Indonesia ANA.';
  try {
    const r = await fetch('/api/voice-preview', { method: 'POST', headers: api.headers({ 'content-type': 'application/json' }), body: JSON.stringify({ voice_id: sel.value, text }) });
    if (r.ok) {
      const ct = r.headers.get('content-type') || '';
      if (ct.includes('audio')) {
        const blob = await r.blob(); const url = URL.createObjectURL(blob);
        const a = new Audio(url); a.onended = () => URL.revokeObjectURL(url); await a.play();
        log('voice', 'VOICE', 'preview ' + name); return;
      }
    }
    let msg = ''; try { const j = await r.clone().json(); msg = j.error || ''; } catch (_) { msg = 'status ' + r.status; }
    if (msg) log('note', 'VOICE', 'ElevenLabs: ' + msg.slice(0, 120) + ' — fallback browser');
    if (!speechSynth) { log('error', 'VOICE', 'browser TTS tidak tersedia'); return; }
    speechSynth.cancel();
    const u = new SpeechSynthesisUtterance(text); u.lang = 'id-ID';
    try { const vs = speechSynth.getVoices(); const idv = vs.find(v => /id[-_]ID/i.test(v.lang)) || vs.find(v => /Indones/i.test(v.name)); if (idv) u.voice = idv; } catch (_) {}
    u.rate = 1.0; u.pitch = 1.0;
    u.onend = () => log('voice', 'VOICE', 'preview browser ' + name);
    u.onerror = e => log('error', 'VOICE', 'browser TTS error ' + (e.error || ''));
    speechSynth.speak(u);
  } catch (e) { log('error', 'VOICE', String(e).slice(0, 150)); }
}
async function applyVoice() {
  const sel = document.getElementById('voiceSelect'); if (!sel) return;
  try {
    const r = await fetch('/api/voice', { method: 'POST', headers: api.headers({ 'content-type': 'application/json' }), body: JSON.stringify({ voice_id: sel.value }) });
    const d = await r.json(); if (!r.ok) throw new Error(d.error || 'gagal');
    log('voice', 'VOICE', 'suara diganti ke ' + (sel.options[sel.selectedIndex]?.textContent || sel.value.slice(0, 8)));
    loadVoices();
  } catch (e) { log('error', 'VOICE', String(e).slice(0, 150)); }
}

// ═══ TOOLS CHIPS ═══
function initToolsChips() {
  ensurePanel({ id: 'toolsPanel', title: 'CONNECTED TOOLS', rail: 'left',
    body: '<div id="toolsList" class="tools-chips"><span class="chip ghost">loading...</span></div>' });
}
function renderTools(tools) {
  const list = document.getElementById('toolsList');
  if (list) list.innerHTML = (tools || []).length
    ? tools.map(t => `<span class="chip">${esc(t)}</span>`).join('')
    : '<span class="chip ghost">Hermes tool list unavailable</span>';
}
// ═══ SYSTEM TELEMETRY ═══
function initSystemTelemetry() {
  ensurePanel({ id: 'sysTelemetry', title: 'SYSTEM TELEMETRY', rail: 'left',
    body: `<div class="tele-grid">
      <div class="tele-item"><span class="tele-label">Brain</span><b id="sy-brain" class="tele-val">—</b></div>
      <div class="tele-item"><span class="tele-label">Runtime</span><b id="sy-runtime" class="tele-val">—</b></div>
      <div class="tele-item"><span class="tele-label">Profile</span><b id="sy-profile" class="tele-val">—</b></div>
      <div class="tele-item"><span class="tele-label">Uplink</span><b id="sy-uplink" class="tele-val">—</b></div>
      <div class="tele-item"><span class="tele-label">Clock</span><b id="sy-clock" class="tele-val">—</b></div>
    </div>` });
  setInterval(() => { const c = document.getElementById('sy-clock'); if (c) c.textContent = now(); }, 1000);
}
function renderSystemTelemetry(s) {
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set('sy-brain', s.runtime === 'hermes' ? 'Hermes Agent' : 'Hermes offline');
  set('sy-runtime', s.runtime || '—');
  set('sy-profile', s.profile || 'default');
  set('sy-uplink', 'online');
}
// ═══ STATUS ═══
async function loadStatus() {
  try {
    const s = await api.getStatus();
    els.stModel.textContent = s.model || '—';
    els.stMode.textContent = s.mode || '—';
    els.stCtx.textContent = s.context || '—';
    els.stMem.textContent = s.memory || '—';

    els.stSess.textContent = s.session || '—';
    // Same payload feeds the tools chips and system telemetry, so one fetch
    // renders all three panels instead of three separate calls.
    renderTools(s.tools?.slice(0, 12));
    renderSystemTelemetry(s);
  } catch (e) { console.error('Status error:', e); }
}

// ═══ PROJECTS ═══
async function refreshProjects() {
  try {
    const data = await api.getProjects();
    const projects = data.projects || [];
    const pl = ensurePanel({ id: 'projectList', title: 'ACTIVE REPOSITORIES', rail: 'left',
      body: '<div class="proj-grid" id="projGrid"></div>' });
    const grid = pl.querySelector('#projGrid');
    if (!projects.length) { grid.innerHTML = '<span class="chip ghost">No active git repositories</span>'; return; }
    grid.innerHTML = projects.map(p => {
      const dirtyCls = p.dirty > 0 ? 'dirty' : 'clean';
      const dirtyTxt = p.dirty > 0 ? `${p.dirty} changed` : 'clean';
      return `<div class="proj-card" data-path="${esc(p.path)}" title="${esc(p.path)}">
        <div class="pname">${esc(p.name)}</div><div class="pbranch">${esc(p.branch)}</div>
        <div class="pcommit">${esc(p.last_commit)}</div><div class="pdirty ${dirtyCls}">${dirtyTxt}</div></div>`;
    }).join('');
    grid.querySelectorAll('.proj-card').forEach(c => {
      c.onclick = () => {
        const name = c.querySelector('.pname')?.textContent || c.dataset.path;
        const commit = c.querySelector('.pcommit')?.textContent || '';
        const msg = `Review project ${name}: branch ${c.querySelector('.pbranch')?.textContent}, last commit: ${commit}. Any issues or next steps?`;
        log('send', 'SEND', `transmit (project): ${msg.slice(0, 60)}`);
        transmit(msg);
      };
    });
  } catch (e) { log('error', 'ERROR', 'Gagal memuat repositori: ' + e.message); }
}

// ═══ BRIEFING ═══
async function refreshBriefing() {
  try {
    const data = await api.getBriefing();
    const bp = ensurePanel({ id: 'briefingPanel', title: 'PROACTIVE BRIEFING', rail: 'left',
      body: '<div id="briefingContent" class="briefing-body">Memuat briefing...</div>' });
    bp.querySelector('#briefingContent').textContent = data.briefing || 'Belum ada briefing hari ini. Dijadwalkan otomatis pukul 08:00 WIB.';
  } catch (e) {}
}

// ═══ MIC / MUTE / CLEAR ═══
els.micBtn.addEventListener('click', micToggle);
function initMuteClear() {
  const bar = document.createElement('div'); bar.className = 'mute-clear-bar';
  bar.innerHTML = `<button id="muteBtn" class="mute-btn">🔊 Voice On</button><button id="clearBtn" class="clear-btn">Clear</button>`;
  document.getElementById('topControls').appendChild(bar);
  bar.querySelector('#muteBtn').addEventListener('click', () => {
    muted = !muted;
    const b = bar.querySelector('#muteBtn');
    b.textContent = muted ? '🔇 Voice Off' : '🔊 Voice On';
    b.classList.toggle('off', muted); b.classList.toggle('on', !muted);
    if (muted && player) player.pause();
  });
  bar.querySelector('#clearBtn').addEventListener('click', () => {
    answer = '';
    els.responseText.innerHTML = '<span class="rplaceholder">Display cleared. Standing by.</span>';
    log('note', 'CLEAR', 'response panel cleared');
  });
}

// ═══ KEYBOARD ═══
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (running && activeController) {
    fetch('/api/cancel', { method: 'POST', headers: api.headers({ 'content-type': 'application/json' }), body: '{}' }).catch(() => {});
    activeController.abort(); return;
  }
  if (convo) stopConvo();
});

// ═══ BACKGROUND JOBS POLLING ═══
setInterval(async () => {
  try {
    const j = await api.getJobs();
    for (const d of (j.done || [])) {
      log('complete', 'MISSION', `${d.mission} → ${(d.result || '').slice(0, 200)}`);
      if (!running) speak(`Mission complete. ${(d.result || '').slice(0, 300)}`);
    }
  } catch (_) {}
}, 4000);

// ═══ INIT ═══
function init() {
  initParticles(); initDials(); initOctFrame(); initRadialTicks(); initOrbitalParticles();
  initMatrix(); initWorkspace(); initIntel(); initEqualizer(); initTelemetry();
  initCommandMatrix(); initQuickButtons(); initMuteClear();
  initToolsChips(); initSystemTelemetry();
  loadStatus(); setInterval(loadStatus, 30000);
  // Layout: drag / resize / lock toggle
  const layout = new LayoutManager(els.hud, [
    'agentPanel','statusMatrix','workspacePanel',
    'intelPanel','pipelinePanel',
    'eventLog','codeViewer','toolsPanel','sysTelemetry',
    'cmdPanel','response','chatBar','core','topControls',
    'bottomTelemetry'
  ].filter(id => document.getElementById(id)));
  window._layoutManager = layout;
  // Dynamically created panels register themselves inside ensurePanel(), so
  // these only have to fire — no .then(register) bookkeeping to keep in sync.
  loadVoices(); refreshProjects(); refreshBriefing();
  refreshKanban(); refreshVault(); refreshAvd();
  setInterval(() => { refreshKanban().catch(()=>{}); }, 6000);
  setInterval(() => { refreshAvd().catch(()=>{}); }, 7000);
  // Terminal is its own module (ui/src/terminal.js); it owns its DOM,
  // pty session and stream reader, and binds Ctrl+` itself.
  const terminal = createTerminal({
    api, token: ANA_TOKEN, log, hud: els.hud, isOpen: () => !!document.getElementById('termPanel'),
  });
  const topControls = document.getElementById('topControls');
  if (topControls) {
    // Terminal button — inserted left of Lock per spec
    const termBtn = document.createElement('button');
    termBtn.className = 'layout-toggle';
    termBtn.id = 'termBtn';
    termBtn.innerHTML = '<span class="toggle-icon">⌘</span> Terminal';
    termBtn.title = 'Toggle terminal (Ctrl+`)';
    termBtn.addEventListener('click', terminal.toggle);
    topControls.appendChild(termBtn);

    const t = document.createElement('button');
    t.className = 'layout-toggle' + (layout.locked ? '' : ' active');
    t.id = 'layoutLockBtn';
    t.innerHTML = `<span class="toggle-icon">${layout.locked ? '🔒' : '✎'}</span> ${layout.locked ? 'Lock' : 'Unlock'}`;
    t.title = 'Lock / unlock panel layout (drag + resize)';
    t.onclick = () => {
      const locked = layout.toggleLock();
      t.innerHTML = `<span class="toggle-icon">${locked ? '🔒' : '✎'}</span> ${locked ? 'Lock' : 'Unlock'}`;
      t.classList.toggle('active', !locked);
      log('status', 'LAYOUT', locked ? 'layout locked' : 'layout unlocked (drag + resize enabled)');
    };
    topControls.appendChild(t);
    const resetBtn = document.createElement('button');
    resetBtn.className = 'layout-toggle';
    resetBtn.textContent = 'Reset';
    resetBtn.title = 'Reset layout to defaults';
    resetBtn.onclick = () => {
      if (!confirm('Reset layout?')) return;
      layout.reset();
    };
    topControls.appendChild(resetBtn);
  }
  log('status', 'INIT', 'ANA FUI HUD terintegrasi penuh.');
  setAgentState('IDLE');
  // Boot
  (async () => {
    try {
      const s = await api.getStatus();
      loadStatus();
      log('status', 'BOOT', `gateway online · ${s.runtime} core · profile=${s.profile || 'default'} · permission=${s.permission}`);
      try { const mj = await fetch('/api/mode', { headers: api.headers() }).then(r => r.json()); if (mj.mode) applyMode(mj.mode); } catch (_) {}
      log('voice', 'VOICE', `channel ready — ${s.stt || 'browser'} / ${s.tts || 'browser'}`);
    } catch (e) { log('error', 'STATUS', 'server unreachable'); }
  })();
}

init();
