import { bus, state } from './core/bus.js';
import { api } from './core/api.js';
import { LayoutManager } from './core/layout.js';
import { now, rid, esc, cleanForSpeech } from './utils/helpers.js';
import { ensurePanel } from './utils/dom.js';
import { createTerminal } from './terminal.js';
import { startBootGuard } from './core/bootGuard.js';
import { requireAuth, formatWilayah } from './core/authGuard.js';
import { initMapPanel, startMapBridge } from './map.js';

// ═══ DOM refs ═══
const $ = id => document.getElementById(id);
const els = {
 hud: $('hud'), particles: $('particles'), topDials: $('topDials'),
 core: $('core'), coreLabel: $('coreLabel'), matrixGrid: $('matrixGrid'), workspaceSvg: $('workspaceSvg'),
 pipeline: $('pipeline'), teleCpu: $('teleCpu'), teleRam: $('teleRam'),
 equalizer: $('equalizer'), equalizerWrap: $('equalizerWrap'), chatInput: $('chatInput'), sendBtn: $('sendBtn'),
 micBtn: $('micBtn'), modeBtn: $('modeBtn'), responseText: $('responseText'),
 eventLog: $('eventLog'), eventEntries: $('eventEntries'), codeViewer: $('codeViewer'), cvBody: $('cvBody'),
 stModel: $('stModel'), stMode: $('stMode'), stCtx: $('stCtx'), stMem: $('stMem'),
 stSess: $('stSess'),
 sessionBtn: $('sessionBtn'), sessionIdEl: $('sessionId'),
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
let progSteps = [], progStart = 0, progTimer = null, progHideTimer = null;
let codeDiffBuf = '';
// In-flight guard for the 7s AVD poll; one server-side poll can take 18s.
let avdPending = false;

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

  // Update avatar state classes
  const core = els.core;
  if (!core) return;
  core.classList.remove('idle', 'speaking', 'listening', 'thinking', 'happy', 'concerned', 'error');
  const stateClassMap = {
    'IDLE': 'idle',
    'UNDERSTANDING': 'listening',
    'PLANNING': 'thinking',
    'EXECUTING': 'thinking',
    'ANALYZING': 'thinking',
    'WAITING_TOOL': 'thinking',
    'RESPONDING': 'speaking',
    'LISTENING': 'listening',
    'ERROR': 'error'
  };
  const cls = stateClassMap[agentState] || 'idle';
  core.classList.add(cls);
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
  if(progHideTimer){ clearTimeout(progHideTimer); progHideTimer=null; }
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
  // Keep the handle: an untracked 3.5s timer from the previous run fired after
  // the next one had already opened the panel and removed .active, so LIVE
  // PROGRESS vanished mid-run. Clearing it here keeps the panel visible for
  // the run that is actually in flight.
  if (progHideTimer) { clearTimeout(progHideTimer); progHideTimer = null; }
  progHideTimer = setTimeout(() => {
    progHideTimer = null;
    const p = document.getElementById('progressPanel');
    if (p) p.classList.remove('active');
    if (bar) { bar.style.width = '0%'; bar.style.background = ''; }
  }, 3500);
}

// ═══ CODE DIFF VIEWER — Fase B ═══
function showCodeDiff(title, diff){
  const v=document.getElementById('codeViewer');
  if(!v) return;
  v.classList.add('visible','live');
  // Lapisan atas map via LayoutManager.bringToFront (counter freeZ, bukan
  // z baru) — measure() lewati panel hidden jadi tanpa ini viewer tetap 6.
  if (window._layoutManager?.bringToFront) window._layoutManager.bringToFront('codeViewer');
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
  // The server shells out to adb (5s), getprop (5s) and emulator -list-avds (8s),
  // so one poll can take 18s against a 7s tick. Without a guard three requests
  // overlap and the oldest response lands last, silently reverting the panel to
  // a state that was already false.
  if(avdPending) return; avdPending=true;
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
  finally{ avdPending=false; }
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
// Jarum digerakkan nilai nyata dari /api/sysmetrics, bukan dekorasi. SVG pakai
// viewBox tetap + width/height 100% supaya ikut mewarisi ukuran panel: dial lama
// memakai .dial{width:36px;height:36px} jadi tidak ikut resize sama sekali.
const DIALS = [
  { key: 'cpu',  label: 'CPU',  unit: '%' },
  { key: 'ram',  label: 'RAM',  unit: '%' },
  { key: 'gpu',  label: 'GPU',  unit: '%' },
  { key: 'ai',   label: 'AI',   unit: '%' },
  { key: 'net',  label: 'NET',  unit: '%' },
  { key: 'disk', label: 'DISK', unit: '%' },
];
const DIAL_ARC = 260;              // derajat arc, sisa 100deg jadi celah bawah
const DIAL_R = 17, DIAL_CX = 20, DIAL_CY = 20;

function _polar(deg, r) {
  const rad = (deg - 90) * Math.PI / 180;
  return [DIAL_CX + r * Math.cos(rad), DIAL_CY + r * Math.sin(rad)];
}
function _arcPath(frac) {
  const sweep = DIAL_ARC * Math.max(0, Math.min(1, frac));
  if (sweep <= 0.01) return '';
  const [x0, y0] = _polar(0, DIAL_R);
  const [x1, y1] = _polar(sweep, DIAL_R);
  const large = sweep > 180 ? 1 : 0;
  return `M${x0.toFixed(2)} ${y0.toFixed(2)} A${DIAL_R} ${DIAL_R} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

function initDials() {
  els.topDials.innerHTML = DIALS.map(d => `
    <div class="dial" data-key="${d.key}" title="${d.label}">
      <svg viewBox="0 0 40 40" preserveAspectRatio="xMidYMid meet">
        <circle cx="${DIAL_CX}" cy="${DIAL_CY}" r="${DIAL_R}" fill="none"
          stroke="rgba(0,232,255,0.18)" stroke-width="2.5"
          stroke-dasharray="${DIAL_ARC} ${400 - DIAL_ARC}" transform="rotate(130 ${DIAL_CX} ${DIAL_CY})"/>
        <path class="dial-arc" d="" fill="none" stroke="#00e8ff" stroke-width="2.5"
          stroke-linecap="round" transform="rotate(130 ${DIAL_CX} ${DIAL_CY})"/>
        <line class="dial-needle" x1="${DIAL_CX}" y1="${DIAL_CY}" x2="${DIAL_CX}" y2="${DIAL_CY - 13}"
          stroke="rgba(255,255,255,0.85)" stroke-width="1" stroke-linecap="round"/>
        <circle cx="${DIAL_CX}" cy="${DIAL_CY}" r="2" fill="#00e8ff"/>
      </svg>
      <span class="dial-label">${d.label}</span>
      <b class="dial-val">—</b>
    </div>`).join('');
  setDial('cpu', 0); // jarum ada dari frame pertama, jangan null
}

// Nilai terakhir per key, buat animasi transisi + flip 0->100 tanpa lompat.
const _dialState = {};
function setDial(key, frac) {
  const host = els.topDials.querySelector(`.dial[data-key="${key}"]`);
  if (!host) return;
  const meta = DIALS.find(d => d.key === key);
  const prev = _dialState[key];
  _dialState[key] = frac;
  const known = typeof frac === 'number' && isFinite(frac);
  const shown = known ? Math.max(0, Math.min(100, frac)) : 0;
  const arc = host.querySelector('.dial-arc');
  const needle = host.querySelector('.dial-needle');
  if (arc) arc.setAttribute('d', _arcPath(shown / 100));
  if (needle) {
    const ang = 130 + DIAL_ARC * (shown / 100);
    const [x, y] = _polar(ang, 13);
    needle.setAttribute('x2', x.toFixed(2));
    needle.setAttribute('y2', y.toFixed(2));
  }
  const val = host.querySelector('.dial-val');
  if (val) val.textContent = known ? `${shown.toFixed(0)}${meta.unit}` : '—';
  // indeterminate tak boleh tampil sebagai 0%: hilang total lebih jujur
  host.classList.toggle('dial-na', !known);
  // tooltip native per dial, gaya sama topControls: "CPU 42%" per tombol
  host.title = known ? `${meta.label} ${shown.toFixed(0)}${meta.unit}` : `${meta.label} —`;
  if (known && prev === undefined) host.dataset.prev = String(shown);
}

// Poll 2 detik. Berhenti saat dokumen hidden supaya tab background tak menendang
// server tiap 2 detik tanpa perlu; catch-up terjadi di visibilitychange.
let _dialTimer = null;
let lastSysMetrics = {};   // dipakai initTelemetry() juga: satu fetch, dua widget
async function refreshDials() {
  try {
    const t = document.querySelector('meta[name=ana-token]')?.content;
    const r = await fetch('/api/sysmetrics', { headers: { 'X-Ana-Token': t || '' } });
    if (!r.ok) return;
    const m = await r.json();
    lastSysMetrics = m;
    for (const d of DIALS) setDial(d.key, m[d.key]);
    if (typeof applyTemps === 'function') applyTemps(m);
  } catch (_) { /* offline: dial tetap displaying nilai terakhir, bukan reset 0 */ }
}
function startDialPoll() {
  if (_dialTimer) return;
  refreshDials();
  _dialTimer = setInterval(() => { if (!document.hidden) refreshDials(); }, 2000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshDials(); });
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
      <div class="session-bar">SESI: <span id="sessionId">—</span></div>
      <div class="session-selector">
        <select id="sessionSelect" class="session-select"><option value="">Memuat sesi...</option></select>
        <button id="sessionNew" class="session-btn">+ BARU</button>
        <button id="sessionDel" class="session-btn" title="Hapus sesi terpilih">🗑</button>
        <button id="sessionRefresh" class="session-btn">↻</button>
      </div>
      <div class="panel-body"><div id="intelTerminal" class="intel-terminal"><div class="intel-line dim">Menunggu aktivitas agen...</div></div></div>`;
    document.getElementById('sessionNew').addEventListener('click', () => {
      // Arsip sesi aktif ke histori (maks 3) TANPA hapus store — sesi lama
      // tetap bisa dibuka lagi dari picker; run berikut buat sesi baru.
      api.post('/api/session/archive', {}).then(() => {
        currentSessionId = null;
        document.getElementById('sessionId').textContent = '—';
        els.stSess.textContent = '—';
        intelLog('🆕 Sesi baru dimulai', 'session');
        log('session', 'SESI', 'sesi baru');
        try { _threadLoadHistory(null); } catch (_) {}
        refreshSessionSelector();
      });
    });
    document.getElementById('sessionRefresh').addEventListener('click', refreshSessionSelector);
    document.getElementById('sessionDel')?.addEventListener('click', async () => {
      const sel = document.getElementById('sessionSelect');
      const sid = sel ? sel.value : '';
      if (!sid) return;
      if (!confirm('Hapus sesi ANNA ini? Riwayat chat di dalamnya ikut hilang.')) return;
      try {
        const r = await api.post('/api/session', { action: 'delete', session_id: sid });
        if (r && r.ok) {
          if (currentSessionId === sid) {
            currentSessionId = (r.sessions && r.sessions[0] && r.sessions[0].id) || null;
            document.getElementById('sessionId').textContent = currentSessionId || '—';
            try { localStorage.removeItem('ana_session'); } catch (_) {}
          }
          intelLog('🗑 Sesi dihapus', 'session');
          log('session', 'SESI', 'hapus sesi');
          refreshSessionSelector();
        }
      } catch (_) {}
    });
    document.getElementById('sessionSelect').addEventListener('change', (e) => {
      const sid = e.target.value;
      if (!sid) return;
      api.setSession(sid).then((r) => {
        if (r.ok) {
          currentSessionId = sid;
          document.getElementById('sessionId').textContent = sid;
          intelLog(`🔗 Pindah ke sesi: ${sid}`, 'session');
          log('session', 'SESI', `pindah ke ${sid}`);
          try { _threadLoadHistory(sid); } catch (_) {}
        }
      });
    });
    refreshSessionSelector();
  }
}
async function refreshSessionSelector() {
  try {
    // Sumber utama: sesi ANNA milik user login (maks 3, persisten).
    // GET /api/session = {sessions:[{id,title,created,message_count,active}]}.
    let mine = [];
    try {
      const r = await api.get('/api/session');
      if (r && r.ok && Array.isArray(r.sessions)) mine = r.sessions;
    } catch (_) {}
    const sel = document.getElementById('sessionSelect');
    if (!sel) return;
    if (mine.length) {
      // Tampilkan sesi milik user saja (maks 3) + opsi sesi baru.
      let html = '<option value=\"\">— Sesi Baru —</option>';
      for (const s of mine) {
        const t = s.created ? new Date(s.created * 1000).toLocaleString('id-ID', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
        html += `<option value=\"${esc(s.id)}\" ${s.active ? 'selected' : ''}>${esc(s.title || s.id)} · ${esc(t)}${s.active ? ' ●' : ''}</option>`;
      }
      sel.innerHTML = html;
      const act = mine.find(s => s.active);
      if (act) {
        currentSessionId = act.id;
        const sidEl = document.getElementById('sessionId');
        if (sidEl) sidEl.textContent = act.id;
      }
      return;
    }
    const data = await api.getSessions();
    const sel2 = document.getElementById('sessionSelect');
    if (!sel2) return;
    const groups = data.groups || {};
    const current = data.current || currentSessionId;
    let html = '<option value="">— Sesi Baru —</option>';
    const groupLabels = { today: '📅 HARI INI', yesterday: '📅 KEMARIN', last_week: '📅 MINGGU LALU', older: '📅 LAMA' };
    for (const [key, label] of Object.entries(groupLabels)) {
      const sessions = groups[key] || [];
      if (sessions.length === 0) continue;
      html += `<optgroup label="${label}">`;
      for (const s of sessions) {
        // Waktu relatif Hermes ("13m ago", "just now") → Indonesia untuk tampilan saja.
        // Grouping di backend tak tersentuh.
        const idTime = (la) => {
          const t = String(la || '').toLowerCase().trim();
          if (t === 'just now') return 'baru saja';
          let m = t.match(/^(\d+)\s*m/); if (m) return `${m[1]} mnt lalu`;
          m = t.match(/^(\d+)\s*h/); if (m) return `${m[1]} jam lalu`;
          m = t.match(/^(\d+)\s*d/); if (m) return `${m[1]} h lalu`;
          return t.replace('ago', 'lalu').trim() || '—';
        };
        // Session titles come from `hermes sessions list` and were interpolated
        // raw, so a title containing a tag rendered as markup inside the select.
        html += `<option value="${esc(s.id)}" ${s.id === current ? 'selected' : ''}>${esc(s.title)} · ${esc(idTime(s.last_active))}</option>`;
      }
      html += '</optgroup>';
    }
    sel2.innerHTML = html;
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
  // Append, do not rebuild. intelLog() and intelTool() write straight into this
  // same node, so the old innerHTML='' replay deleted every tool trace and
  // session line the moment a run finished — the trace existed only while the
  // run was in flight, which is the one moment you do not need to read it.
  const line = document.createElement('div');
  line.className = 'intel-line ' + (role === 'user' ? 'user' : 'assistant');
  line.textContent = (role === 'user' ? '▸ YOU: ' : '▸ ANA: ') + text;
  term.appendChild(line);
  term.scrollTop = term.scrollHeight;
  while (term.children.length > 80) term.removeChild(term.firstChild);
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
let eqAnim = null;
function startEqualizer() {
  if (eqAnim) return;
  const canvas = els.equalizer, ctx = canvas.getContext('2d');
  canvas.width = 80; canvas.height = 24;
  const bars = 16, barW = canvas.width / bars; let phase = 0;
  function draw() {
    if (!document.body.classList.contains('speaking') && !els.hud.classList.contains('speaking')) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      eqAnim = null; return;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < bars; i++) {
      // Smooth sine wave with slight randomness for organic feel
      const baseH = 3 + Math.sin(phase + i * 0.4) * 6;
      const noise = (Math.random() - 0.5) * 2;
      const h = Math.max(2, Math.min(20, baseH + noise));
      const alpha = 0.4 + (h / 24) * 0.6;
      const hue = 180 + (h / 20) * 30; // cyan to blue-green
      ctx.fillStyle = `hsla(${hue}, 90%, 60%, ${alpha})`;
      ctx.fillRect(i * barW + 1, canvas.height - h, barW - 2, h);
      // Subtle glow on taller bars
      if (h > 12) {
        ctx.shadowColor = `hsla(${hue}, 90%, 60%, 0.6)`;
        ctx.shadowBlur = 4;
        ctx.fillRect(i * barW + 1, canvas.height - h, barW - 2, h);
        ctx.shadowBlur = 0;
      }
    }
    phase += 0.15;
    eqAnim = requestAnimationFrame(draw);
  }
  draw();
}
window.startEqualizer = startEqualizer;

function stopEqualizer() {
  if (eqAnim) { cancelAnimationFrame(eqAnim); eqAnim = null; }
  const canvas = els.equalizer;
  if (canvas) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
}
window.stopEqualizer = stopEqualizer;

// ═══ TEMPERATURE TELEMETRY ═══
// Skala termometer, bukan persentase: 20C..100C dipetakan ke lebar bar. Angka
// acak lama (Math.random) diganti sensor asli; kalau
// sensor tidak ada, kolomnya diredupkan dan angka disembunyikan — bukan
// menampilkan angka palsu.
const TEMP_MIN = 20, TEMP_MAX = 100;
const TEMP_WARM = 70, TEMP_HOT = 85;

function setTemp(barId, valId, celsius) {
  const bar = document.getElementById(barId);
  const val = document.getElementById(valId);
  if (!bar || !val) return;
  const known = typeof celsius === 'number' && isFinite(celsius);
  if (!known) {
    bar.style.width = '0%';
    bar.parentElement.classList.add('na');
    val.textContent = '--';
    bar.removeAttribute('data-band');
    return;
  }
  bar.parentElement.classList.remove('na');
  const clamped = Math.max(TEMP_MIN, Math.min(TEMP_MAX, celsius));
  bar.style.width = (100 * (clamped - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)) + '%';
  val.textContent = Math.round(celsius);
  bar.setAttribute('data-band', celsius >= TEMP_HOT ? 'hot'
    : celsius >= TEMP_WARM ? 'warm' : 'cool');
}

function applyTemps(m) {
  setTemp('teleCpuTemp', 'teleCpuTempVal', m.cpu_temp);
  setTemp('teleGpuTemp', 'teleGpuTempVal', m.gpu_temp);
}

// Poll-nya piggyback pada dial poll: satu fetch /api/sysmetrics untuk semua
// metrik, bukan satu request per widget.
function initTelemetry() {
  applyTemps(lastSysMetrics);
}

// ═══ SPEAK ═══
// cleanForSpeech is imported from utils/helpers.js.
// Handle for the currently-playing utterance/clip, so a new prompt can cut the
// old one off instead of letting it talk over the new answer. `speakAudio` is the
// server-MP3 <audio>; `speakUtterance` is the browser speechSynthesis fallback.
let speakAudio = null, speakUtterance = null, speakSeq = 0;

// Stop whatever ANA is saying right now. Called on every new transmit() so a new
// question silences the previous answer — otherwise a long answer keeps reading
// while the user already moved on.
function stopSpeaking() {
  speakSeq++;                                  // invalidate in-flight speak() promises
  if (speakAudio) { try { speakAudio.pause(); speakAudio.currentTime = 0; } catch (_) {} speakAudio = null; }
  if (speakUtterance && speechSynth) { try { speechSynth.cancel(); } catch (_) {} }
  speakUtterance = null;
  stopEqualizer();
  els.hud.classList.remove('speaking');
  if (els.core) els.core.classList.remove('speaking');
}

function playMp3(url) {
  return new Promise(resolve => {
    const a = new Audio(url);
    speakAudio = a;
    const done = ok => { if (speakAudio === a) speakAudio = null; URL.revokeObjectURL(url); resolve(ok); };
    a.onended = () => done(true);
    a.onerror = () => { log('error', 'VOICE', 'audio playback failed'); done(false); };
    a.play().catch(() => done(false));
  });
}

function speak(text) {
  return new Promise(async resolve => {
    text = cleanForSpeech(text);
    if (muted || !text) return resolve();
    // Read the answer to the end — no length cap. The old 700-char cap meant a
    // report answer stopped mid-sentence with "…". Guard against runaway instead:
    // split at sentence boundaries and synthesize one clause at a time, so an
    // endless stream never builds a single unbounded request.
    const mySeq = ++speakSeq;
    const finish = () => { if (mySeq === speakSeq) { stopEqualizer(); els.hud.classList.remove('speaking'); if (els.core) els.core.classList.remove('speaking'); } resolve(); };
    const alive = () => mySeq === speakSeq;
    suppress = true;
    els.hud.classList.add('speaking');
    if (els.core) els.core.classList.add('speaking');
    startEqualizer();

    // prefer server TTS (edge-tts mp3) — same path as voice preview
    try {
      const r = await fetch('/api/speak', {
        method: 'POST',
        headers: api.headers({ 'content-type': 'application/json' }),
        body: JSON.stringify({ text })
      });
      if (!alive()) return resolve();                 // superseded while synthesizing
      if (r.ok) {
        const ct = r.headers.get('content-type') || '';
        if (ct.includes('audio')) {
          const blob = await r.blob();
          if (!alive()) return resolve();
          const url = URL.createObjectURL(blob);
          await playMp3(url);
          finish();
          if (alive()) log('voice', 'VOICE', 'TTS played (server)');
          return;
        }
      }
      let msg = ''; try { const j = await r.clone().json(); msg = j.error || ''; } catch (_) { msg = 'status ' + r.status; }
      if (msg) log('note', 'VOICE', 'server TTS: ' + msg.slice(0, 120) + ' — fallback browser');
    } catch (e) {
      log('note', 'VOICE', 'server TTS error: ' + String(e).slice(0, 120) + ' — fallback browser');
    }
    if (!alive()) return resolve();

    // fallback browser speechSynthesis
    if (speechSynth) {
      try {
        speechSynth.cancel();
        const u = new SpeechSynthesisUtterance(text);
        speakUtterance = u;
        u.lang = 'id-ID';
        try {
          const vs = speechSynth.getVoices();
          const id = vs.filter(v => /id[-_]ID/i.test(v.lang) || /Indones/i.test(v.name));
          // Prioritas gender yang sama dengan voice aktif, baru fallback netral.
          // Tanpa ini browser selalu ambil suara perempuan apa pun pilihannya.
          const want = activeVoice.gender;
          const byGender = want ? id.find(v => new RegExp(want === 'male' ? 'male|pria|laki' : 'female|wanita|perempuan', 'i').test(v.name)) : null;
          const idv = byGender || id[0];
          if (idv) u.voice = idv;
        } catch (_) {}
        u.rate = 1.0; u.pitch = 1.0; u.volume = 1;
        u.onend = u.onerror = () => {
          if (speakUtterance === u) speakUtterance = null;
          finish();
          if (alive()) log('voice', 'VOICE', 'TTS played (browser)');
        };
        speechSynth.speak(u);
        return;
      } catch (e) {
        stopEqualizer();
        els.hud.classList.remove('speaking');
        if (els.core) els.core.classList.remove('speaking');
        log('error', 'VOICE', 'browser TTS error: ' + String(e).slice(0, 120));
      }
    }
    finish();
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
  // Fatal errors mean this device/browser will never work; retrying just spams
  // the event log. no-speech and aborted are normal, so they fall through to
  // the onend restart.
  const FATAL = new Set(['not-allowed', 'service-not-allowed', 'audio-capture', 'network', 'language-not-supported']);
  recognition.onerror = e => {
    log('error', 'VOICE', `browser speech: ${e.error || 'error'}`);
    if (FATAL.has(e.error)) stopConvo();
  };
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
  bar.innerHTML = quicks.map(q => `<button class="quick-btn" data-quick="${q}" title="${q}">${{ '/status': '◈', '/tools': '🛠', '/toolsets': '🧰', '/connectors': '🔌' }[q]}</button>`).join('');
  document.getElementById('topControls').appendChild(bar);
  bar.addEventListener('click', e => {
    const b = e.target.closest('.quick-btn'); if (!b) return;
    transmit(b.dataset.quick, { speak: false });
  });
}

// ═══ CHAT INPUT (auto-grow 1 baris → maks 5, kembali 1 saat kirim) ═══
function autosizeChat() {
  const el = els.chatInput;
  if (!el) return;
  el.style.height = 'auto';
  const max = parseFloat(getComputedStyle(el).lineHeight) * 5 + 14;
  el.style.height = Math.min(el.scrollHeight, max) + 'px';
  el.style.overflowY = el.scrollHeight > max ? 'auto' : 'hidden';
}

function sendFromChat() {
  const raw = els.chatInput.value.trim();
  const armed = els.chatInput.dataset.cmd || '';
  if (!raw && !armed) return;
  const full = (armed && !raw.startsWith('/')) ? `${armed} ${raw}` : (raw || armed);
  els.chatInput.value = '';
  autosizeChat();
  disarm();
  log('send', 'SEND', `transmit (chat): ${full}`);
  transmit(full);
}
els.sendBtn.addEventListener('click', sendFromChat);
els.chatInput.addEventListener('input', autosizeChat);
els.chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendFromChat(); }
});
autosizeChat();

// ═══ SESSION MANAGEMENT (chat panel) — konsisten dengan TPL ═══
function sessionIdDisplay(sid) {
  if (!sid) { els.sessionIdEl.textContent = '—'; return; }
  els.sessionIdEl.textContent = String(sid).slice(0, 20);
}

async function loadSessions() {
  try {
    const j = await api.get('/api/session');
    if (j.ok) {
      currentSessionId = j.session || null;
      sessionIdDisplay(j.session);
      return j.sessions || [];
    }
  } catch (_) {}
  currentSessionId = null;
  sessionIdDisplay(null);
  return [];
}

function sessionPanelRender(sessions) {
  const panel = document.getElementById('sessionPanel');
  if (!panel) return;
  panel.innerHTML = '';

  // Bar — sama seperti tpl-bar (tombol + di dalam daftar)
  const bar = document.createElement('div');
  bar.className = 'tpl-bar';
  const mkBtn = (label, title, fn) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'tpl-bar-btn';
    b.textContent = label;
    b.title = title;
    b.addEventListener('click', ev => { ev.stopPropagation(); fn(); });
    return b;
  };

  const addBtn = mkBtn('+', 'Sesi baru', async () => {
    await createNewSession();
  });
  addBtn.classList.add('mini');
  bar.appendChild(addBtn);
  panel.appendChild(bar);

  // Header label (mirror TPL group header style)
  const label = document.createElement('div');
  label.style.cssText = 'padding:4px 6px;border-bottom:1px solid var(--neon-dim);color:var(--neon-dim);font-size:10px;margin-bottom:4px;font-family:var(--font-mono);';
  label.textContent = 'SESI';
  panel.appendChild(label);

  for (const s of sessions) {
    const isActive = s.id === currentSessionId;
    const row = document.createElement('div');
    row.className = 'tpl-row';
    if (isActive) row.style.cssText = 'background:rgba(0,220,255,0.08);';

    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'tpl-item';
    item.textContent = (s.title || '--') + '  ·  ' + String(s.id).slice(0, 12) + (isActive ? '  ✓' : '');
    item.title = 'Pilih sesi: ' + s.id;
    item.addEventListener('click', async () => {
      await api.setSession(s.id);
      const list = await loadSessions();
      sessionPanelRender(list);
      try { _threadLoadHistory(s.id); } catch (_) {}
      try { document.getElementById('sessionPanel').hidden = true; } catch(_) {}
    });
    row.appendChild(item);

    // Delete button INSIDE each row — sama seperti tpl-del di TPL
    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.className = 'tpl-del mini';
    delBtn.textContent = '🗑';
    delBtn.title = 'Hapus sesi ' + s.id;
    delBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm('Hapus sesi ' + s.id + '?')) return;
      try {
        const j = await api.post('/api/session', { action: 'delete', session_id: s.id });
        if (j.ok) {
          const list = await loadSessions();
          sessionPanelRender(list);
        } else {
          alert('Gagal hapus sesi: ' + (j.error || 'tidak diketahui'));
        }
      } catch (ee) {
        alert('Gagal hapus sesi: ' + ee.message);
      }
    });
    row.appendChild(delBtn);
    panel.appendChild(row);
  }
}

async function createNewSession() {
  try {
    const j = await api.post('/api/session', { action: 'new' });
    if (j.ok) {
      const list = await loadSessions();
      sessionPanelRender(list);
      try { _threadLoadHistory(null); } catch (_) {}
      try { document.getElementById('sessionPanel').hidden = true; } catch(_) {}
    } else {
      alert('Gagal buat sesi baru: ' + (j.error || 'tidak diketahui'));
    }
  } catch (e) {
    alert('Gagal buat sesi baru: ' + e.message);
  }
}

els.sessionBtn.addEventListener('click', async (e) => {
  e.stopPropagation();
  const panel = document.getElementById('sessionPanel');
  if (!panel) return;
  panel.hidden = !panel.hidden;
  if (!panel.hidden) {
    const sessions = await loadSessions();
    sessionPanelRender(sessions);
  }
});

// Tutup panel saat klik di luar
document.addEventListener('click', (e) => {
  const panel = document.getElementById('sessionPanel');
  const btn = els.sessionBtn;
  if (!panel || panel.hidden) return;
  if (!panel.contains(e.target) && e.target !== btn) {
    panel.hidden = true;
  }
});

// ═══ TEMPLATE PERTANYAAN per-user (hanya mode asisten via .only-asisten) ═══
// Sumber kebenaran: GET /api/tpl (default bawaan = TPL_GROUPS di bawah,
// user baru otomatis dapat salinan; edit milik sendiri via panel Kelola).
// Klik item = isi chatInput (user tekan Enter untuk kirim).
async function tplFetch(path, opts = {}) {
  const r = await fetch(path, { credentials: 'same-origin', headers: api.headers({ 'content-type': 'application/json' }), ...(opts || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.ok === false) throw new Error(j?.error || ('HTTP ' + r.status));
  return j;
}
let _tplGroups = null;   // null = belum dimuat (pakai TPL_GROUPS fallback)
let _tplEdit = false;    // mode kelola tampil
let _tplAddG = false;    // form grup baru tampil
let _tplAddQ = -1;       // index grup yang form tambah-pertanyaan tampil
function tplGroups() {
  return Array.isArray(_tplGroups) && _tplGroups.length ? _tplGroups : TPL_GROUPS;
}
function tplRender() {
  const panel = document.getElementById('tplPanel');
  if (!panel) return;
  panel.innerHTML = '';
  const groups = tplGroups();
  // Bar mode: Lihat vs Kelola + Reset default
  const bar = document.createElement('div');
  bar.className = 'tpl-bar';
  const mkBtn = (label, title, fn) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'tpl-bar-btn'; b.textContent = label; b.title = title;
    b.addEventListener('click', ev => { ev.stopPropagation(); fn(); });
    return b;
  };
  bar.appendChild(mkBtn(_tplEdit ? '✓' : '✎', _tplEdit ? 'Selesai kelola' : 'Kelola template', () => { _tplEdit = !_tplEdit; _tplAddG = false; _tplAddQ = -1; tplRender(); }));
  if (_tplEdit) {
    bar.appendChild(mkBtn('+', 'Grup baru', () => { _tplAddG = !_tplAddG; tplRender(); }));
    bar.appendChild(mkBtn('↺', 'Kembalikan ke bawaan', async () => {
      if (!confirm('Kembalikan template ke bawaan? Edit Anda hilang.')) return;
      try {
        const j = await tplFetch('/api/tpl', { method: 'POST', body: JSON.stringify({ op: 'reset' }) });
        _tplGroups = j.groups; _tplEdit = false; _tplAddG = false; _tplAddQ = -1; tplRender();
      } catch (e) { alert('Reset gagal: ' + String(e?.message || e).slice(0, 120)); }
    }));
  }
  panel.appendChild(bar);
  // Form grup baru inline (tanpa dialog): nama + pertanyaan pertama wajib
  // (aturan server buang grup kosong).
  if (_tplEdit && _tplAddG) {
    const f = document.createElement('div');
    f.className = 'tpl-form';
    const nt = document.createElement('input');
    nt.className = 'tpl-input'; nt.placeholder = 'Nama grup…'; nt.maxLength = 60;
    const nq = document.createElement('input');
    nq.className = 'tpl-input'; nq.placeholder = 'Pertanyaan pertama…'; nq.maxLength = 300;
    const ok = mkBtn('+', 'Simpan grup', async () => {
      const t = nt.value.trim().slice(0, 60);
      const first = nq.value.trim().slice(0, 300) || 'Pertanyaan baru — ubah saya';
      if (!t) { nt.focus(); return; }
      _tplGroups = [...tplGroups(), { t, q: [first] }];
      _tplAddG = false;
      tplRender();
      await tplSave();
    });
    ok.classList.add('mini');
    f.appendChild(nt); f.appendChild(nq); f.appendChild(ok);
    panel.appendChild(f);
    setTimeout(() => nt.focus(), 0);
  }
  groups.forEach((g, gi) => {
    const wrap = document.createElement('div');
    wrap.className = 'tpl-gwrap';
    const h = document.createElement('div');
    h.className = 'tpl-group';
    if (!_tplEdit) {
      const ht = document.createElement('span');
      ht.textContent = g.t;
      h.appendChild(ht);
    } else {
      // Rename grup = input inline, pola sama seperti edit pertanyaan
      // (change = simpan). Tanpa dialog prompt.
      const gi2 = document.createElement('input');
      gi2.className = 'tpl-ginput'; gi2.value = g.t; gi2.maxLength = 60;
      gi2.title = 'Ubah nama grup — Enter untuk simpan';
      gi2.setAttribute('aria-label', 'Nama grup');
      gi2.addEventListener('change', async () => {
        const t = gi2.value.trim().slice(0, 60);
        if (!t) { gi2.value = g.t; return; }
        if (t === g.t) return;
        _tplGroups = tplGroups().map((x, i) => i === gi ? { ...x, t } : x);
        tplRender();
        await tplSave();
      });
      h.appendChild(gi2);
      // Hapus grup KUNCI bila masih ada isi: kosongkan dulu pertanyaannya
      // satu per satu, baru tombol hapus aktif. Cegah hapus massal tak sengaja.
      const locked = (g.q || []).length > 0;
      const del = mkBtn('🗑', locked ? 'Kosongkan dulu pertanyaannya untuk hapus grup' : 'Hapus grup kosong ini', async () => {
        if (locked) return;
        if (!confirm('Hapus grup "' + g.t + '"?')) return;
        _tplGroups = tplGroups().filter((_, i) => i !== gi);
        if (!_tplGroups.length) { alert('Minimal 1 grup berisi 1 pertanyaan.'); _tplGroups = tplGroups(); return; }
        tplRender();
        await tplSave();
      });
      del.classList.add('mini');
      del.classList.add('tpl-del');
      if (locked) del.disabled = true;
      h.appendChild(del);
    }
    wrap.appendChild(h);
    (g.q || []).forEach((q, qi) => {
      if (!_tplEdit) {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'tpl-item'; b.textContent = q; b.title = q;
        b.addEventListener('click', () => { els.chatInput.value = q; autosizeChat(); els.chatInput.focus(); try { document.getElementById('tplPanel').hidden = true; } catch(_) {} });
        wrap.appendChild(b);
      } else {
        const row = document.createElement('div');
        row.className = 'tpl-row';
        const inp = document.createElement('input');
        inp.className = 'tpl-input'; inp.value = q; inp.title = q;
        inp.addEventListener('change', async () => {
          const v = inp.value.trim().slice(0, 300);
          if (!v) { alert('Pertanyaan kosong — hapus saja bila tak perlu.'); inp.value = q; return; }
          _tplGroups = tplGroups().map((x, i) => i === gi ? { ...x, q: x.q.map((y, j) => j === qi ? v : y) } : x);
          tplRender();
          await tplSave();
        });
        const del = document.createElement('button');
        del.type = 'button'; del.className = 'tpl-bar-btn mini tpl-del'; del.textContent = '🗑'; del.title = 'Hapus pertanyaan';
        del.addEventListener('click', async () => {
          _tplGroups = tplGroups().map((x, i) => i === gi ? { ...x, q: x.q.filter((_, j) => j !== qi) } : x);
          if (!_tplGroups.every(x => x.q.length)) { alert('Tiap grup wajib berisi minimal 1 pertanyaan.'); _tplGroups = tplGroups(); return; }
          tplRender();
          await tplSave();
        });
        row.appendChild(inp); row.appendChild(del);
        wrap.appendChild(row);
      }
    });
    if (_tplEdit) {
      // Tambah pertanyaan = form inline (tanpa dialog), pola sama grup baru.
      if (_tplAddQ === gi) {
        const f = document.createElement('div');
        f.className = 'tpl-form';
        const nq = document.createElement('input');
        nq.className = 'tpl-input'; nq.placeholder = 'Pertanyaan baru…'; nq.maxLength = 300;
        const ok = mkBtn('+', 'Simpan', async () => {
          const v = nq.value.trim().slice(0, 300);
          if (!v) { nq.focus(); return; }
          _tplGroups = tplGroups().map((x, i) => i === gi ? { ...x, q: [...x.q, v] } : x);
          _tplAddQ = -1;
          tplRender();
          await tplSave();
        });
        ok.classList.add('mini');
        const cancel = mkBtn('✕', 'Batal', () => { _tplAddQ = -1; tplRender(); });
        cancel.classList.add('mini');
        f.appendChild(nq); f.appendChild(ok); f.appendChild(cancel);
        wrap.appendChild(f);
        setTimeout(() => nq.focus(), 0);
      } else {
        const add = mkBtn('+', 'Tambah pertanyaan ke ' + g.t, () => { _tplAddQ = gi; tplRender(); });
        add.classList.add('wide');
        wrap.appendChild(add);
      }
    }
    panel.appendChild(wrap);
  });
}
async function tplSave() {
  try {
    const j = await tplFetch('/api/tpl', { method: 'POST', body: JSON.stringify({ groups: _tplGroups }) });
    _tplGroups = j.groups;
    tplRender();
  } catch (e) { alert('Simpan gagal: ' + String(e?.message || e).slice(0, 120)); }
}
async function tplLoad() {
  try {
    const j = await tplFetch('/api/tpl');
    if (Array.isArray(j.groups) && j.groups.length) _tplGroups = j.groups;
  } catch (_) { /* offline/anonim: pakai TPL_GROUPS bawaan */ }
  tplRender();
}
const TPL_GROUPS = [
  { t: 'RINGKASAN & LAPORAN', q: [
    'Ringkasan sekarang KPH Banyuwangi Barat bulan ini',
    'Ringkasan sekarang BKPH KPH Banyuwangi Barat tahun ini',
    'Perbandingan bulan ini vs bulan lalu produksi KPH Banyuwangi Barat',
    'Tren produksi KPH Banyuwangi Barat selama tahun ini per bulan',
  ]},
  { t: 'PRODUKSI & TARGET', q: [
    'Berapa produksi KPH Banyuwangi Barat bulan ini?',
    'Produksi Rogojampi bulan ini',
    'Berapa pencapaian target KPH Banyuwangi Barat bulan ini?',
    'Petak produksi tidak mencapai target bulan ini',
  ]},
  { t: 'PETAK', q: [
    'Berapa jumlah petak KPH Banyuwangi Barat?',
    'Berapa luas baku KPH Banyuwangi Barat?',
    'Petak bongkor di Rogojampi tahun ini',
    'Petak idle di Glenmore tahun ini',
    'Petak tidak efektif di Licin tahun ini',
    'Daftar petak di KPH Banyuwangi Barat',
    'Detail petak 31211020110201_11B-1 (ganti kode petak)',
    'Petak tetangga di sekitar petak 31211020110201_11B-1 (ganti kode)',
  ]},
  { t: 'AKTIVITAS & PENYADAP', q: [
    'Bagaimana aktivitas Glenmore bulan ini?',
    'Top petak aktivitas Rogojampi bulan ini',
    'Siapa penyadap di petak 31211020110201_11B-1? (ganti kode)',
    'Berapa produktivitas penyadap per TPG tahun ini?',
    'Matriks aktivitas vs petak Licin tahun ini',
    'Tampilkan bukti foto aktivitas Glenmore bulan ini',
  ]},
  { t: 'PETA', q: [
    'Tampilkan polygon petak Licin di peta tahun ini',
    'Tampilkan polygon petak Rogojampi di peta tahun ini',
    'Tampilkan petak KPH Banyuwangi Barat di peta tahun ini',
    'Tampilkan petak DIVRE Jawa Timur di peta tahun ini',
    'Tampilkan aktivitas Glenmore bulan ini di peta',
    'Tampilkan pencapaian RKAP bulan ini di peta',
    'Ringkasan KPH seluruh DIVRE tahun ini tampilkan di peta',
  ]},
  { t: 'DATA', q: [
    'Apakah data hari ini sudah masuk?',
    'Kapan terakhir update data?',
  ]},
];
(function initTpl(){
  const btn = document.getElementById('tplBtn'), panel = document.getElementById('tplPanel');
  if (!btn || !panel) return;
  btn.addEventListener('click', () => { panel.hidden = !panel.hidden; });
  els.sendBtn.addEventListener('click', () => { panel.hidden = true; });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !panel.hidden) panel.hidden = true; });
  tplLoad();
})();

// ═══ CHAT THREAD PREMIUM ═══
// RESPONSE = thread percakapan (bubble user/ANA + kutip + timestamp + aksi),
// bukan satu teks jawaban terakhir + kursor. Tanpa ini user tak bisa scroll
// riwayat sesi aktif, tak bisa kutip pertanyaan, tak ada aksi per pesan.
const _thread = { sid: null, items: [], streaming: null };

function _threadTime(ts) {
  try {
    return new Date(ts || Date.now()).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
  } catch (_) { return ''; }
}

function _threadScroll() {
  try { els.responseText.scrollTop = els.responseText.scrollHeight; } catch (_) {}
}

function _threadBubble(role, text, opts = {}) {
  const isUser = role === 'user';
  const wrap = document.createElement('div');
  wrap.className = 'th-' + (isUser ? 'user' : 'ana') + (opts.streaming ? ' th-stream' : '');
  const content = document.createElement('div');
  content.className = 'th-content';
  const bub = document.createElement('div');
  bub.className = 'th-bubble';
  const head = document.createElement('div');
  head.className = 'th-head';
  const who = document.createElement('span');
  who.className = 'th-who';
  who.textContent = isUser ? 'Anda' : 'Anna';
  const time = document.createElement('span');
  time.className = 'th-time';
  time.textContent = _threadTime(opts.ts);
  head.appendChild(who); head.appendChild(time);
  bub.appendChild(head);
  if (role === 'user' || opts.quote) {
    const q = document.createElement('div');
    q.className = 'th-quote';
    q.textContent = role === 'user' ? text : opts.quote;
    if (role === 'user') q.title = 'Klik untuk pakai lagi';
    if (role === 'user') q.addEventListener('click', () => {
      try { els.chatInput.value = text; autosizeChat(); els.chatInput.focus(); } catch (_) {}
    });
    bub.appendChild(q);
  }
  if (role !== 'user' || !opts.quoteOnly) {
    const body = document.createElement('div');
    body.className = 'th-body';
    body.textContent = role === 'user' ? '' : text;
    if (role === 'user') body.style.display = 'none';
    else bub.appendChild(body);
  }
  content.appendChild(bub);
  if (role !== 'user') {
    const acts = document.createElement('div');
    acts.className = 'th-acts';
    const copy = document.createElement('button');
    copy.type = 'button'; copy.className = 'th-act'; copy.textContent = 'Salin';
    copy.title = 'Salin jawaban';
    copy.addEventListener('click', async (e) => {
      e.stopPropagation();
      try { els.chatInput.value = text; autosizeChat(); els.chatInput.focus(); } catch (_) {}
      try { await navigator.clipboard.writeText(text); copy.textContent = 'Tersalin ✓'; }
      catch (_) { copy.textContent = 'Tersalin'; }
      setTimeout(() => { copy.textContent = 'Salin'; }, 1500);
    });
    const again = document.createElement('button');
    again.type = 'button'; again.className = 'th-act'; again.textContent = 'Tanya lagi';
    again.title = 'Isi pertanyaan ini ke chat';
    again.addEventListener('click', (e) => {
      e.stopPropagation();
      try { els.chatInput.value = opts.quote || ''; autosizeChat(); els.chatInput.focus(); } catch (_) {}
    });
    acts.appendChild(copy); acts.appendChild(again);
    content.appendChild(acts);
  }
  wrap.appendChild(content);
  return wrap;
}

function _threadRender() {
  const box = els.responseText;
  if (!box) return;
  box.innerHTML = '';
  if (!_thread.items.length && !_thread.streaming) {
    box.innerHTML = '<span class="rplaceholder">Siap menerima perintah.</span>';
    return;
  }
  for (let i = 0; i < _thread.items.length; i++) {
    const it = _thread.items[i];
    // Quote hanya bila BUKAN pengulangan bubble user tepat di atasnya —
    // tanpa ini tiap jawaban ANNA mengulang pertanyaan di bawahnya (kembar).
    let q = it.quote;
    if (it.role !== 'user' && q && i > 0) {
      const prev = _thread.items[i - 1];
      if (prev.role === 'user' && prev.text.trim() === q.trim()) q = '';
    }
    box.appendChild(_threadBubble(it.role, it.text, { quote: q, ts: it.ts }));
  }
  if (_thread.streaming) {
    const s = _thread.streaming;
    let sq = s.quote;
    try {
      const lastU = [..._thread.items].reverse().find(x => x.role === 'user');
      if (lastU && sq && lastU.text.trim() === String(sq).trim()) sq = '';
    } catch (_) {}
    const node = _threadBubble('ana', s.text || '', { quote: sq, ts: s.ts, streaming: true });
    if (!s.text) {
      const cur = document.createElement('span');
      cur.className = 'cur';
      node.querySelector('.th-body')?.appendChild(cur);
    }
    box.appendChild(node);
  }
  _threadScroll();
}

function _threadPush(role, text, opts = {}) {
  const it = { role, text, quote: opts.quote || '', ts: opts.ts || Date.now() };
  _thread.items.push(it);
  if (_thread.items.length > 40) _thread.items.splice(0, _thread.items.length - 40);
  _threadRender();
  return it;
}

function _threadStreamStart(quote) {
  _thread.streaming = { text: '', quote: quote || '', ts: Date.now() };
  _threadRender();
}

function _threadStreamAppend(t) {
  if (!_thread.streaming) _threadStreamStart('');
  _thread.streaming.text += t;
  _threadRender();
}

function _threadStreamDone(finalText) {
  const s = _thread.streaming;
  _thread.streaming = null;
  if (s) _threadPush('ana', finalText || s.text, { quote: s.quote, ts: s.ts });
  else _threadRender();
}

async function _threadLoadHistory(sid) {
  _thread.sid = sid || null;
  _thread.items = [];
  _thread.streaming = null;
  if (!sid) { _threadRender(); return; }
  try {
    // credentials WAJIB: tanpa cookie, server baca user_key="" dan tolak
    // transcript 401 (login dulu) — tanpa ini riwayat selalu kosong diam-diam.
    const r = await fetch('/api/session/transcript?session_id=' + encodeURIComponent(sid), { headers: api.headers(), credentials: 'same-origin' });
    const j = await r.json().catch(() => ({}));
    if (j.error) { try { intelLog(`⚠ Riwayat tak termuat: ${j.error}`, 'error'); } catch (_) {} }
    const msgs = Array.isArray(j.messages) ? j.messages : [];
    let pendingQ = '';
    for (const m of msgs.slice(-20)) {
      if (m.role === 'user') { pendingQ = m.text; }
      else if (m.role === 'assistant') { _thread.items.push({ role: 'ana', text: m.text, quote: pendingQ, ts: Date.now() }); pendingQ = ''; }
    }
    if (pendingQ) _thread.items.push({ role: 'user', text: pendingQ, ts: Date.now() });
  } catch (_) {}
  _threadRender();
}

// Narasi internal model (kawaii spinner + self-narration) → satu status
// Indonesia yang rapi. Tanpa ini dapur bocor ke ruang tamu.
let _lastThinking = '';
function cleanThinking(raw) {
  let t = String(raw || '').replace(/^\s*\([^)\n]{0,40}\)\s*/u, '').trim();
  if (!t) return '';
  const g = t.match(/^([A-Za-z]+?)(ing)?\.{2,}\s*$/);
  if (g) {
    const map = { reason: 'Menalar', deliberat: 'Menimbang', mull: 'Memikirkan', reflect: 'Merefleksi', comput: 'Menghitung', think: 'Berpikir', summariz: 'Meringkas', compos: 'Menyusun', analyz: 'Menganalisis', check: 'Memeriksa', fetch: 'Mengambil data', search: 'Mencari' };
    const k = Object.keys(map).find(k => g[1].toLowerCase().startsWith(k));
    return (k ? map[k] : 'Memproses') + '…';
  }
  if (/wait|tunggu|provider|antre|queue|retry|menghubungi/i.test(t)) return t.slice(0, 90);
  return 'Menyusun jawaban…';
}


// ═══ TRANSMIT ═══
async function transmit(message, options = {}) {
  if (!message.trim()) return;
  if (running) { log('note', 'BUSY', `still working — "${message.slice(0, 40)}" not sent. Wait, or press Esc to cancel.`); return; }
  // A new question silences the previous answer. ANA now reads every answer to
  // the end, so without this a long report keeps talking over the new question.
  stopSpeaking();
  running = true; answer = ''; firstDelta = false; speakThisRun = options.speak !== false;
  convoMsgs = [];
  const fresh = /^\/new\b/.test(message.trim());
  const id = rid();
  setAgentState('UNDERSTANDING');
  progressReset(message.slice(0, 48));
  _threadPush('user', message);
  _threadStreamStart(message);
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
      body: JSON.stringify({ message, fresh, session_id: currentSessionId || '' }), signal: activeController.signal
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
  // Nothing else resets the state to IDLE: speak() only does so via stopVoice()
  // on the path where audio actually played, and it returns early when muted or
  // the answer is empty. Without this the core label stays stuck on RESPONDING
  // forever after the first silent run.
  await speakDone;
  if (state.agentStatus !== 'IDLE' && state.agentStatus !== 'ERROR') setAgentState('IDLE');
}

function handle(ev) {
  switch (ev.t) {
    case 'session':
      if (ev.session_id) {
        els.stSess.textContent = ev.session_id.slice(0, 8);
        currentSessionId = ev.session_id;
        const sid = document.getElementById('sessionId');
        if (sid) sid.textContent = ev.session_id;
        // Persist tiap event session (bukan hanya setSession manual) agar
        // complete antar-tab + boot restore selalu baca id terbaru.
        try {
          localStorage.setItem('ana_session', JSON.stringify({ id: ev.session_id, meta: null, ts: Date.now() }));
        } catch (_) {}
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
      answer += ev.text; _threadStreamAppend(ev.text);
      if (!firstDelta) { firstDelta = true; log('reason', 'REASONING', answer.slice(0, 220)); progressStep('Menjawab…'); setAgentState('RESPONDING'); }
      break;
    case 'usage': log('status', 'COMPLETE', 'run completed', usageBlock(ev)); break;
    case 'complete':
      setAgentState('RESPONDING');
      log('complete', 'COMPLETE', ev.ms != null ? `run completed in ${ev.ms}ms` : 'run completed');
      answer = finalizeAnswer(answer);
      _threadStreamDone(answer);
      intelMsg('assistant', answer);
      progressDone(true);
      speakDone = speakThisRun ? speak(answer) : Promise.resolve();
      // refresh kanban/vault after complete
      refreshKanban().catch(()=>{}); refreshVault().catch(()=>{});
      break;
    case 'error':
      setAgentState('ERROR');
      log('error', 'ERROR', ev.message || 'unknown');
      if (!answer) { _threadStreamDone('⚠ ' + (ev.message || 'Run failed.')); }
      else { answer = finalizeAnswer(answer); _threadStreamDone(answer); }
      progressDone(false);
      break;
    case 'note': log('note', 'NOTE', ev.message || ''); break;
    // thinking: kawaii spinner prose and provider wait notices. Never part of
    // `answer` — it goes to the progress trace and the core label only, so
    // speak() never reads ANA's own narration aloud.
    case 'thinking': {
      const clean = (typeof cleanThinking === 'function') ? cleanThinking(ev.text) : '';
      if (!clean || clean === _lastThinking) break;
      _lastThinking = clean;
      progressStep(clean); intelLog(clean, 'thinking'); setAgentState('PLANNING');
      break;
    }
  }
}
function finalizeAnswer(raw) {
  let t = String(raw || '').replace(/(\d)\.(\d)/g, '$1\0$2');
  const parts = t.match(/[^.…!?]+[.…!?]+/g) || [];
  const tail = t.replace(/[^.…!?]+[.…!?]+/g, '').trim();
  if (tail) parts.push(tail);
  const norm = s => s.trim().toLowerCase().replace(/[.…!?]+$/,'').replace(/\s+/g,' ');
  const NARR = /render chart|tarik(an)? (angka|data)|tarik data|menarik (angka|data|produksi)|tarikan (angka|data)|perbaiki autentikasi|sesi (login|push)|cek sesi|telusur|saya cek|mengecek|memeriksa|menunggu|menyusun|menjawab.*tarik|belum masuk,?\s*cek|kosong,?\s*telusur|siapkan|laporan gagal|cek format|format ketemu|render ulang|^(\s*)(siap|tunggu|sebentar)[\s,.]/i;
  const seen = new Set();
  const out = [];
  for (const p of parts) {
    const s = p.replace(/\0/g, '.').trim();
    if (!s) continue;
    const n = norm(s);
    if (!n || seen.has(n)) continue;
    seen.add(n);
    out.push(s);
  }
  const content = out.filter(s => !NARR.test(s));
  return (content.length ? content : out).join(' ');
}

function applyMode(m) {
  state.mode = (m === 'asisten' ? 'asisten' : 'coding');
  els.modeBtn.textContent = state.mode.toUpperCase();
  log('note', 'MODE', state.mode === 'asisten' ? 'Mode asisten — jawaban ringkas tanpa markdown/code' : 'Mode coding — jawaban lengkap dengan markdown/code');
  try { bus.emit('MODE_CHANGED', state.mode); } catch (_) {}
  try { document.documentElement.setAttribute('data-ana-mode', state.mode); } catch (_) {}
  try { window.dispatchEvent(new CustomEvent('ana:mode', { detail: state.mode })); } catch (_) {}
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
// Voice aktif (id + gender). Dipakai fallback browser speechSynthesis supaya
// pilihan di panel VOICE CONFIG dihormati juga di jalur cadangan — dulu fallback
// cuma cari /id[-_]ID/ yang selalu kena suara perempuan, jadi user memilih Ardi
// tetap mendengar Gadis.
let activeVoice = { id: '', gender: '' };
async function loadVoices() {
  try {
    const r = await fetch('/api/voices', { headers: api.headers() });
    const d = await r.json(); voicesCache = d.voices || [];
    const cur = d.current || '';
    const all = [...voicesCache];
    const curObj = all.find(v => v.id === cur);
    activeVoice = { id: cur, name: (curObj && curObj.agent_name) || '', gender: (curObj && curObj.gender) || '' };
    const vp = ensurePanel({
      id: 'voicePicker', title: 'VOICE CONFIG', rail: 'right',
      body: `<select id="voiceSelect" class="voice-select"></select>
        <div class="voice-btns"><button id="voicePreview" class="voice-btn">Preview</button><button id="voiceApply" class="voice-btn primary">Pakai</button></div>
        <div id="voiceDesc" class="voice-desc"></div>`,
    });
    // Wire buttons once (ensurePanel updates body in place, preserving event handlers)
    if (!vp.dataset.wired) {
      vp.dataset.wired = '1';
      vp.querySelector('#voicePreview').addEventListener('click', previewVoice);
      vp.querySelector('#voiceApply').addEventListener('click', applyVoice);
    }
    const sel = vp.querySelector('#voiceSelect');
    if (sel) {
      // Label memakai agent_name (nama yang diucapkan), bukan nama voice, dan
      // data-agent-name disimpan untuk preview. "Gadis" dan "Ardi" itu nama
      // mesin TTS, bukan identitas yang introduce diri — menampilkan keduanya
      // bikin user mengira sedang memilih nama, bukan timbre.
      sel.innerHTML = all.map(v => {
        const agent = v.agent_name || 'ANNA';
        const timbre = v.gender === 'male' ? 'suara laki-laki' : v.gender === 'female' ? 'suara perempuan' : '';
        return `<option value="${v.id}" data-agent-name="${esc(agent)}" ${v.id === cur ? 'selected' : ''}>${esc(agent)} - ${esc(timbre)} ${esc(v.desc.slice(0, 34))}</option>`;
      }).join('');
      const dv = all.find(v => v.id === sel.value) || curObj || all[0];
      const desc = vp.querySelector('#voiceDesc');
      if (desc && dv) desc.textContent = 'Nama: ' + (dv.agent_name || 'ANNA') + ' | ' + dv.desc + ' | ' + dv.id.slice(0, 12) + '..';
    }
  } catch (e) { const d = document.getElementById('voiceDesc'); if (d) d.textContent = 'Gagal memuat daftar suara'; }
}
async function previewVoice() {
  const sel = document.getElementById('voiceSelect'); if (!sel) return;
  const opts = [...sel.options].find(o => o.value === sel.value);
  const name = (opts?.dataset.agentName || opts?.textContent?.split(' - ')[0] || sel.value.slice(0, 8)).trim();
  // Preview memperkenalkan diri dengan nama yang cocok dengan voice aktif
  // (Gadis -> ANNA, Ardi -> MAX), bukan dengan nama voice itu sendiri. Kalau
  // bunyinya "saya Ardi", user mengira nama agen berubah jadi Ardi. Aturan nama
  // yang sama ada di server.persona(), jadi preview dan jawaban konsisten.
  const text = 'Halo Pak, saya ' + name + '. Ini pratinjau suara bahasa Indonesia.';
  try {
    const r = await fetch('/api/voice-preview', { method: 'POST', headers: api.headers({ 'content-type': 'application/json' }), body: JSON.stringify({ voice_id: sel.value, text }) });
    if (r.ok) {
      const ct = r.headers.get('content-type') || '';
      if (ct.includes('audio')) {
        const blob = await r.blob(); const url = URL.createObjectURL(blob);
        startEqualizer();
        els.hud.classList.add('speaking');
        if (els.core) els.core.classList.add('speaking');
        const a = new Audio(url);
        a.onended = () => { URL.revokeObjectURL(url); stopEqualizer(); els.hud.classList.remove('speaking'); if (els.core) els.core.classList.remove('speaking'); };
        await a.play();
        log('voice', 'VOICE', 'preview ' + name); return;
      }
    }
    let msg = ''; try { const j = await r.clone().json(); msg = j.error || ''; } catch (_) { msg = 'status ' + r.status; }
    if (msg) log('note', 'VOICE', 'Edge TTS: ' + msg.slice(0, 120) + ' — fallback browser');
    if (!speechSynth) { log('error', 'VOICE', 'browser TTS tidak tersedia'); return; }
    speechSynth.cancel();
    const u = new SpeechSynthesisUtterance(text); u.lang = 'id-ID';
    try { const vs = speechSynth.getVoices(); const idv = vs.find(v => /id[-_]ID/i.test(v.lang)) || vs.find(v => /Indones/i.test(v.name)); if (idv) u.voice = idv; } catch (_) {}
    u.rate = 1.0; u.pitch = 1.0;
    startEqualizer();
    els.hud.classList.add('speaking');
    if (els.core) els.core.classList.add('speaking');
    u.onend = () => { stopEqualizer(); els.hud.classList.remove('speaking'); if (els.core) els.core.classList.remove('speaking'); log('voice', 'VOICE', 'preview browser ' + name); };
    u.onerror = e => { stopEqualizer(); els.hud.classList.remove('speaking'); if (els.core) els.core.classList.remove('speaking'); log('error', 'VOICE', 'browser TTS error ' + (e.error || '')); };
    speechSynth.speak(u);
  } catch (e) { stopEqualizer(); els.hud.classList.remove('speaking'); log('error', 'VOICE', String(e).slice(0, 150)); }
}
window.previewVoice = previewVoice;
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
    // These five fields all come from /api/status. Do not read keys the server
    // never sends: mode lives behind /api/mode, and there is no context or
    // memory counter anywhere in the API — the labels show what the runtime
    // actually reports instead of sitting at "—" forever.
    els.stMode.textContent = s.profile || '—';
    els.stCtx.textContent = s.permission || '—';
    els.stMem.textContent = s.runtime || '—';
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
async function initMuteClear() {
  const bar = document.createElement('div'); bar.className = 'mute-clear-bar';
  bar.innerHTML = `<button id="muteBtn" class="mute-btn" title="Voice On — klik untuk matikan">🔊</button><button id="dbBtn" class="db-btn" title="DB: lokal — klik untuk ganti sumber">🗄</button><button id="restartBtn" class="restart-btn" title="Restart server (mis. setelah update kode)">↻</button><button id="clearBtn" class="clear-btn" title="Clear — bersihkan panel response">✕</button>`;
  document.getElementById('topControls').appendChild(bar);
  // ── DB source menu (pilih: lokal | remote via kphbwb-tunnel) ──
  // innerHTML di bawah aman: hanya label statis + host/port/db dari API internal.
  const dbBtn = bar.querySelector('#dbBtn');
  const paintDb = (src) => {
    const remote = src === 'remote';
    dbBtn.textContent = remote ? '🗄ᴿ' : '🗄';
    dbBtn.classList.toggle('remote', remote);
    dbBtn.title = `DB: ${remote ? 'remote (server kphbwb via tunnel)' : 'lokal'} — klik untuk pilih`;
  };
  try {
    const ds = await api.getDbSource();
    if (ds && ds.source) paintDb(ds.source);
  } catch (_) {}
  const closeDbMenu = () => { const m = document.querySelector('.db-menu'); if (m) m.remove(); };
  dbBtn.addEventListener('click', async (ev) => {
    ev.stopPropagation();
    if (document.querySelector('.db-menu')) { closeDbMenu(); return; }
    let info = null;
    try { info = await api.getDbSource(); } catch (_) {}
    const cur = (info && info.source) || 'local';
    const L = (info && info.local) || {};
    const R = (info && info.remote) || {};
    const tun = info ? !!info.tunnel : false;
    const row = (key, label, sub, active) => `<button class="db-menu-item${active ? ' active' : ''}" data-src="${key}"><span class="db-dot">${active ? '✓' : '○'}</span><span><b>${label}</b><small>${sub}</small></span></button>`;
    const menu = document.createElement('div');
    menu.className = 'db-menu';
    menu.innerHTML = `<div class="db-menu-head">DATABASE</div>`
      + row('local', 'Lokal', `${L.host || '127.0.0.1'}:${L.port || 3306} / ${L.database || ''}`, cur === 'local')
      + row('remote', 'Remote kphbwb', `${R.host || '127.0.0.1'}:${R.port || 13307} / ${R.database || ''} · tunnel ${tun ? 'OK' : 'mati'}`, cur === 'remote');
    document.body.appendChild(menu);
    const rc = dbBtn.getBoundingClientRect();
    menu.style.top = `${rc.bottom + 6}px`;
    menu.style.left = `${Math.max(8, rc.left - 140)}px`;
    const pick = async (next) => {
      closeDbMenu();
      if (next === cur) return;
      if (next === 'remote' && !confirm('Pindah ke DB REMOTE (server kphbwb via tunnel)? Data yang tampil ikut DB server. Lanjut?')) return;
      dbBtn.disabled = true;
      log('note', 'DB', `switch DB → ${next}…`);
      try {
        const res = await api.setDbSource(next);
        if (res && res.ok) {
          paintDb(next);
          log('complete', 'DB', `sumber DB sekarang: ${next} — sesi lama logout, alihkan ke login…`);
          setTimeout(() => { location.href = `/login.html#db-${next}`; }, 800);
        } else {
          log('error', 'DB', `gagal switch: ${(res && res.error) || 'unknown'}`);
        }
      } catch (e) {
        log('error', 'DB', `gagal switch: ${e.message || e}`);
      }
      dbBtn.disabled = false;
    };
    menu.querySelectorAll('.db-menu-item').forEach((b) => b.addEventListener('click', () => pick(b.dataset.src)));
    setTimeout(() => {
      document.addEventListener('click', closeDbMenu, { once: true });
      document.addEventListener('keydown', function esc(e) { if (e.key === 'Escape') closeDbMenu(); }, { once: true });
    }, 0);
  });
  bar.querySelector('#muteBtn').addEventListener('click', () => {
    muted = !muted;
    const b = bar.querySelector('#muteBtn');
    b.textContent = muted ? '🔇' : '🔊';
    b.title = muted ? 'Voice Off — klik untuk nyalakan' : 'Voice On — klik untuk matikan';
    b.classList.toggle('off', muted); b.classList.toggle('on', !muted);
    if (muted) stopSpeaking();
  });
  bar.querySelector('#restartBtn').addEventListener('click', async () => {
    const b = bar.querySelector('#restartBtn');
    if (!confirm('Restart server ANA? Sesi chat aktif ikut reset. Lanjut?')) return;
    b.disabled = true; b.textContent = '↻'; b.title = 'Restarting…';
    log('note', 'RESTART', 'permintaan restart dikirim, server exec ulang…');
    try {
      const r = await api.restart();
      if (!r || !r.ok) {
        // Server lama (sebelum patch ini) belum punya /api/restart.
        b.disabled = false; b.textContent = '↻'; b.title = 'Restart server (mis. setelah update kode)';
        log('error', 'RESTART', 'server ini terlalu lama untuk restart via tombol — restart manual sekali terakhir dari terminal, setelah itu tombol berfungsi.');
        return;
      }
    } catch (_) {}
    // Poll sampai server baru jawab /api/status (maks ~30 dtk), lalu reload.
    const t0 = Date.now();
    const tick = async () => {
      try {
        const s = await api.getStatus();
        // Respon apa pun (termasuk 401: token baru setelah exec) = server baru sudah online.
        // Reload ambil token segar dari meta tag index.html.
        if (s && (s.model || s.runtime || s.error)) {
          log('complete', 'RESTART', 'server baru online — reload UI…');
          setTimeout(() => location.reload(), 800);
          return;
        }
      } catch (_) {}
      if (Date.now() - t0 > 30000) {
        b.disabled = false; b.textContent = '↻'; b.title = 'Restart server (mis. setelah update kode)';
        log('error', 'RESTART', 'server belum online setelah 30 dtk — cek terminal');
        return;
      }
      setTimeout(tick, 1000);
    };
    setTimeout(tick, 2500);
  });
  bar.querySelector('#clearBtn').addEventListener('click', () => {
    answer = '';
    try { _thread.items = []; _thread.streaming = null; _threadRender(); } catch (_) {}
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

// ═══ PANEL ACCESS — allowlist dari directus_users.panel_access ═══
// value (string di JSON) → id panel DOM. 1=mapPanel dikunci sesuai DB.
// NULL di DB = tanpa batasan (semua enabled, perilaku lama) — cegah lockout.
// Panel tak terdaftar: force-hide + checkbox Options di-disable (tak bisa ON).
// Panel terdaftar: kontrol penuh via Options + layout.json seperti semula.
const PANEL_ACCESS_MAP = {
  '1': 'mapPanel', '2': 'agentPanel', '3': 'statusMatrix',
  '4': 'workspacePanel', '5': 'intelPanel', '6': 'pipelinePanel',
  '7': 'toolsPanel', '8': 'sysTelemetry', '9': 'cmdPanel',
  '10': 'voicePicker', '11': 'briefingPanel', '12': 'projectList',
  '13': 'missionKanban', '14': 'vaultPanel', '15': 'avdPanel',
  '16': 'termPanel', '17': 'eventLog', '18': 'codeViewer',
  '19': 'topDials', '20': 'chatBox',
  '22': 'core', '23': 'bottomTelemetry',
};
function applyPanelAccess(layout) {
  const pa = window._authUser?.panel_access;
  if (pa == null) return; // NULL = tanpa batasan
  const allowed = new Set((Array.isArray(pa) ? pa : []).map(String));
  for (const [val, id] of Object.entries(PANEL_ACCESS_MAP)) {
    if (allowed.has(val)) continue;
    try { layout.setPanelEnabled(id, false); } catch (_) {}
    const cb = document.querySelector(`#panelOptionsList input[data-id="${CSS.escape(id)}"]`);
    if (cb) { cb.checked = false; cb.disabled = true; cb.closest('label')?.classList.add('locked'); }
  }
}

// ═══ PANEL OPTIONS — enable / disable any panel ═══
function initPanelOptions(layout) {
  const btn = document.getElementById('optBtn');
  if (!btn) return;
  if (document.getElementById('panelOptionsMenu')) return;

  const wrap = document.createElement('div');
  wrap.className = 'panel-options-wrap';
  wrap.innerHTML = `
    <div class="panel-options-menu" id="panelOptionsMenu">
      <div class="panel-options-head">PANELS</div>
      <div class="panel-options-list" id="panelOptionsList"></div>
    </div>`;
  // id-resolved, bukan variabel lokal init(): topControls di init()_scope
  // tak terlihat dari sini. getElementById selalu benar.
  document.getElementById('topControls').appendChild(wrap);

  const menu = wrap.querySelector('#panelOptionsMenu');
  const list = wrap.querySelector('#panelOptionsList');

  // Sumber kebenaran = LayoutManager yang sudah menarik semua panel ke .hud.
  // Whitelist manual sebelumnya (contentPanelIds) cepat basi: panel baru yang
  // didaftarkan ensurePanel() tidak pernah muncul di menu. Pengecualian hanya
  // topControls, karena menu ini menempel padanya.
  const NOT_TOGGLABLE = new Set(['topControls']);
  const ids = (layout?.ids || []).filter(id =>
    !NOT_TOGGLABLE.has(id) && document.getElementById(id));
  const titles = {
    agentPanel: 'AGENT STATUS', statusMatrix: 'SYSTEM MATRIX',
    workspacePanel: 'WORKSPACE', intelPanel: 'INTELLIGENCE SURFACE',
    pipelinePanel: 'AGENT PIPELINE', toolsPanel: 'CONNECTED TOOLS',
    sysTelemetry: 'SYSTEM TELEMETRY', cmdPanel: 'COMMAND MATRIX',
    voicePicker: 'VOICE CONFIG', briefingPanel: 'PROACTIVE BRIEFING',
    projectList: 'ACTIVE REPOSITORIES', missionKanban: 'MISSION KANBAN',
    vaultPanel: 'VAULT STATUS', avdPanel: 'ANDROID AVD', termPanel: 'TERMINAL',
    mapPanel: 'SPATIAL MAP',
    eventLog: 'EVENT STREAM', codeViewer: 'CODE VIEWER',
    topDials: 'SYSTEM DIALS',
    chatBox: 'CHAT', core: 'CORE',
    bottomTelemetry: 'BOTTOM TELEMETRY',
  };

  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el) continue;
    const label = document.createElement('label');
    label.className = 'panel-opt';
    label.innerHTML = `<input type="checkbox" data-id="${esc(id)}" checked> ${esc(titles[id] || id)}`;
    list.appendChild(label);
  }

  // Restore saved disabled state
  for (const id of layout.disabled) {
    const cb = list.querySelector(`input[data-id="${CSS.escape(id)}"]`);
    if (cb) cb.checked = false;
  }

  list.addEventListener('change', e => {
    const cb = e.target.closest('input[data-id]');
    if (!cb) return;
    const id = cb.dataset.id;
    layout.setPanelEnabled(id, cb.checked);
    log('status', 'PANEL', `${titles[id] || id} ${cb.checked ? 'shown' : 'hidden'}`);
  });

  btn.addEventListener('click', e => {
    e.stopPropagation();
    menu.classList.toggle('open');
    // fixed ke viewport: tempel di bawah tombol, kanan sejajar tombol.
    // Tanpa ini menu nempel top:auto/left:auto viewport (pojok).
    if (menu.classList.contains('open')) {
      const r = btn.getBoundingClientRect();
      menu.style.top = (r.bottom + 6) + 'px';
      menu.style.left = Math.max(8, r.right - 220) + 'px';
    }
  });
  document.addEventListener('click', e => {
    if (!menu.contains(e.target) && e.target !== btn) menu.classList.remove('open');
  });
}

// ═══ INIT ═══
async function init() {
  initParticles(); initDials();
  initMatrix(); initWorkspace(); initIntel(); initTelemetry(); startDialPoll();
  initCommandMatrix(); initQuickButtons(); initMuteClear();
  initToolsChips(); initSystemTelemetry();
  loadStatus(); setInterval(loadStatus, 30000);

  // Cross-tab session sync: read persisted session on boot
  (() => {
    try {
      const stored = localStorage.getItem('ana_session');
      if (stored) {
        const { id, meta, ts } = JSON.parse(stored);
        if (id && Date.now() - ts < 86400000) { // 24h max age
          currentSessionId = id;
          const sidEl = document.getElementById('sessionId');
          if (sidEl) sidEl.textContent = id;
          els.stSess.textContent = id.slice(0, 8);
          intelLog(`🔗 Sesi dipulihkan: ${id}`, 'session');
        }
      }
    } catch (_) {}
  })();

  // Listen for session changes from other tabs
  window.addEventListener('storage', (e) => {
    if (e.key === 'ana_session') {
      try {
        if (e.newValue) {
          const { id, meta } = JSON.parse(e.newValue);
          if (id && id !== currentSessionId) {
            currentSessionId = id;
            const sidEl = document.getElementById('sessionId');
            if (sidEl) sidEl.textContent = id;
            els.stSess.textContent = id.slice(0, 8);
            intelLog(`🔗 Sesi disinkron dari tab lain: ${id}`, 'session');
            refreshSessionSelector();
          }
        } else {
          // Session cleared in another tab
          if (currentSessionId) {
            currentSessionId = null;
            const sidEl = document.getElementById('sessionId');
            if (sidEl) sidEl.textContent = '—';
            els.stSess.textContent = '—';
            intelLog('🔗 Sesi dihapus dari tab lain', 'session');
            refreshSessionSelector();
          }
        }
      } catch (_) {}
    }
  });

  // Layout: drag / resize / lock toggle
  const layout = new LayoutManager(els.hud, [
    'agentPanel','statusMatrix','workspacePanel',
    'intelPanel','pipelinePanel',
    'eventLog','codeViewer','toolsPanel','sysTelemetry',
    'cmdPanel','chatBox','core','topControls',
    'topDials','bottomTelemetry'
  ].filter(id => document.getElementById(id)),
    // FASE 1 header-lock + map full-body: posisi 4 id ini dari CSS, bukan layout.json
    { static: ['topControls','topDials','bottomTelemetry','mapPanel'],
      dockPair: ['chatBox'] });
  window._layoutManager = layout;
  // FASE 3 drawer (konsep v3 §4): phone (<780px) header 3 strip sembunyi
  // default (peta full-body), floating ☰ buka/tutup. TABLET (781-1180px)
  // header TETAP tampil (layar cukup) — drawer hanya phone. Desktop abaikan.
  // Deteksi via device.js tier + flags data-device/data-touch di <html>;
  // resize/orientation/visualViewport (keyboard tablet) semua sinkron ulang.
  try {
    const { deviceTier, onViewportChange, applyDeviceFlags } = await import('./core/device.js');
    const drawerBtn = document.getElementById('hudDrawerBtn');
    const syncDrawer = () => {
      applyDeviceFlags();
      // Slot layout ikut mode kini: pindah desktop↔mobile = reload agar
      // panel baca slot yang benar (layout.js loadConfig per mode).
      try {
        const m = deviceTier() === 'desktop' ? 'desktop' : 'mobile';
        if (layout && layout._mode && layout._mode !== m) { location.reload(); return; }
      } catch (_) {}
      if (deviceTier() !== 'phone') { document.body.classList.remove('hud-header-open', 'hud-header-hidden'); return; }
      document.body.classList.toggle('hud-header-hidden', !document.body.classList.contains('hud-header-open'));
    };
    drawerBtn?.addEventListener('click', () => {
      document.body.classList.toggle('hud-header-open');
      syncDrawer();
    });
    onViewportChange(syncDrawer);
    // Resize/orientasi dalam mode yang sama (tanpa reload): jaga pair tetap
    // berdampingan di dalam map (kanan/tengah-bawah + tak tindih legend).
    // Mode beda sudah reload di atas, jadi debounce ini tak balap apa pun.
    let _pairRsz = 0;
    onViewportChange(() => {
      try { clearTimeout(_pairRsz); } catch (_) {}
      _pairRsz = setTimeout(() => { try { layout.positionPairInMap(); } catch (_) {} }, 220);
    });
    syncDrawer();
  } catch (_) {}
  // Tunggu GET /api/layout selesai DULU sebelum panel dinamis dibuat:
  // tanpa ini register()/save() panel dinamis (mapPanel, voicePicker, ...)
  // berpacu dengan loadConfig dan menimpa layout.json dengan disabled:[].
  await layout.ready;
  // Map panel harus ada di DOM sebelum initPanelOptions bangun menu —
  // whitelist filter by getElementById, panel belum ada = tidak masuk list.
  try { initMapPanel({ log }); } catch (_) {}
  // Pair response↔chatBar ikut status map kini (dock + z map / home dashboard),
  // lalu susun berdampingan di dalam map + amati geometrinya.
  try { layout.syncPairWithMap(); } catch (_) {}
  try { layout.positionPairInMap(); } catch (_) {}
  try { layout.watchPairGeometry(); } catch (_) {}
  // Bridge ANA ↔ peta: poll /api/map/queue, eksekusi via adapter (Fase 5).
  try { startMapBridge({ token: ANA_TOKEN, log }); } catch (_) {}
  // Token basi (server restart) → auto-reload via BOOT_ID poll, tanpa baca token.
  // Auth gate — redirect to /login.html if no Directus cookie session
  // Handler evict: perangkat ini ditendang login perangkat lain → banner +
  // tombol ambil alih (login ulang), BUKAN redirect buta. Tanpa ini user
  // yang kena tendang bingung kenapa tiba-tiba di login.html.
  try {
    api.evictedHandler = (info) => {
      try {
        let b = document.getElementById('evictBanner');
        if (!b) {
          b = document.createElement('div');
          b.id = 'evictBanner';
          b.style.cssText = 'position:fixed;top:52px;left:50%;transform:translateX(-50%);z-index:9999;max-width:min(480px,calc(100%-24px));background:rgba(2,15,42,.96);border:1px solid #FB7185;border-radius:10px;padding:10px 14px;box-shadow:0 12px 32px rgba(0,0,0,.6);font-size:13px;color:var(--text-main);display:flex;gap:10px;align-items:center;';
          b.innerHTML = '<span style="flex:1">Akun ini login di perangkat lain — sesi perangkat ini dialihkan. Chat & arsip ANNA tetap aman.</span>';
          const btn = document.createElement('button');
          btn.textContent = 'Ambil alih kembali';
          btn.style.cssText = 'flex:0 0 auto;border:1px solid var(--neon);background:rgba(45,242,255,.12);color:var(--text-header);border-radius:6px;padding:6px 12px;cursor:pointer;font-size:12px;';
          btn.addEventListener('click', () => { location.href = '/login.html?next=' + encodeURIComponent(location.pathname + location.search); });
          b.appendChild(btn);
          document.body.appendChild(b);
        }
        b.style.display = 'flex';
        try { log('session', 'SESI', 'ditendang perangkat lain — banner tampil'); } catch {}
      } catch {}
    };
  } catch {}
  // Switch-device bind: pendatang via QR belum punya did — daftarkan sekali
  // ke sesinya SEBELUM cek auth, agar tak terevict sesaat setelah masuk.
  // Browser normal (did sudah ada dari login) = no-op total.
  try {
    let _did0 = null;
    try { _did0 = localStorage.getItem('ana_device_id') || ''; } catch (_) {}
    if (!_did0 || !/^[A-Za-z0-9_=-]{8,64}$/.test(_did0)) {
      _did0 = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + '-' + Math.random().toString(36).slice(2)) + '';
      _did0 = _did0.replace(/[^A-Za-z0-9_=-]/g, '').slice(0, 64);
      if (_did0.length < 8) _did0 = 'dev-' + Math.random().toString(36).slice(2, 14);
      try { localStorage.setItem('ana_device_id', _did0); } catch (_) {}
      try {
        await fetch('/api/auth/bind-device', { method: 'POST', credentials: 'same-origin', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ did: _did0 }) });
      } catch (_) {}
    }
  } catch {}
  try {
    const _auth = await requireAuth();
    if (_auth && _auth.user) {
      // show wilayah in AGENT STATUS panel (SESSION row doubles as user)
      const sessEl = document.getElementById('stSess');
      if (sessEl) sessEl.textContent = [ _auth.user.email, _auth.user.jabatan?.nama_jabatan || _auth.user.jabatan || '', _auth.user.kode_divre?.divre || '', _auth.user.kode_kph?.kph || '' ].filter(Boolean).join(' · ') || _auth.user.email;
      // also expose on state for other panels
      try { state.authUser = _auth.user; window._authUser = _auth.user; } catch {}
      // SPATIAL MAP: terapkan scope wilayah login (DIVRE/KPH user) ke filter —
      // initMapPanel jalan sebelum auth selesai, jadi panel tak tahu user saat boot.
      try { if (typeof window.__spatialApplyUserScope === 'function') window.__spatialApplyUserScope(); } catch {}
      // inject 2FA badge into topControls if not exists (logout button lives
      // next to Reset — see injectLogoutBtn() in the topControls block below)
      const tc = document.getElementById('topControls');
      if (tc) {
        // 2FA badge (sembunyikan bila 2FA dimatikan via env)
        if (!_auth.user.tfa_enabled && _auth.user.tfa_enforced !== false) {
          const t = document.createElement('a');
          t.textContent='🛡'; t.title='Aktifkan 2FA'; t.href='#'; t.style.cssText='font-size:14px;width:38px;height:26px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--amber);border-radius:2px;color:var(--amber);text-decoration:none';
          t.onclick=(e)=>{ e.preventDefault(); location.href='/login.html#tfa'; };
          tc.appendChild(t);
        }
      }
    }
  } catch (_) {}
  try { startBootGuard(); } catch (_) {}
  // Dynamically created panels register themselves inside ensurePanel(), so
  // these only have to fire — no .then(register) bookkeeping to keep in sync.
  // Await them so initPanelOptions sees every panel in the DOM.
  await Promise.allSettled([loadVoices(), refreshProjects(), refreshBriefing(),
    refreshKanban(), refreshVault(), refreshAvd()]);
  // Panel options must run after every ensurePanel() call above, otherwise
  // the dynamic panels (voicePicker, briefingPanel, projectList,
  // missionKanban, vaultPanel, avdPanel) are missing from the menu.
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
    termBtn.innerHTML = '<span class="toggle-icon">⌘</span>';
    termBtn.title = 'Terminal — toggle (Ctrl+`)';
    termBtn.addEventListener('click', terminal.toggle);
    topControls.appendChild(termBtn);

    // Options button — panel enable/disable list
    const optBtn = document.createElement('button');
    optBtn.className = 'layout-toggle';
    optBtn.id = 'optBtn';
    optBtn.innerHTML = '<span class="toggle-icon">⚙</span>';
    optBtn.title = 'Options — show / hide panels';
    topControls.appendChild(optBtn);

    const t = document.createElement('button');
    t.className = 'layout-toggle' + (layout.locked ? '' : ' active');
    t.id = 'layoutLockBtn';
    t.innerHTML = `<span class="toggle-icon">${layout.locked ? '🔒' : '✎'}</span>`;
    t.title = layout.locked ? 'Lock — layout terkunci' : 'Unlock — drag + resize aktif';
    t.onclick = () => {
      const locked = layout.toggleLock();
      t.innerHTML = `<span class="toggle-icon">${locked ? '🔒' : '✎'}</span>`;
      t.title = locked ? 'Lock — layout terkunci' : 'Unlock — drag + resize aktif';
      t.classList.toggle('active', !locked);
      log('status', 'LAYOUT', locked ? 'layout locked' : 'layout unlocked (drag + resize enabled)');
    };
    topControls.appendChild(t);
    const resetBtn = document.createElement('button');
    resetBtn.className = 'layout-toggle';
    resetBtn.textContent = '↺';
    resetBtn.title = 'Reset — kembalikan layout ke default';
    resetBtn.onclick = () => {
      if (!confirm('Reset layout?')) return;
      layout.reset();
    };
    topControls.appendChild(resetBtn);
    // Logout — kanan Reset, merah
    if (!document.getElementById('btnLogout')) {
      const lo = document.createElement('button');
      lo.id = 'btnLogout'; lo.textContent = '⏻'; lo.title = 'Keluar (logout)';
      lo.className = 'layout-toggle logout-btn';
      lo.onclick = async () => { try { await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }); } catch (_) {} location.href = '/login.html'; };
      topControls.appendChild(lo);
    }
    // Switch HP — kanan logout: QR sekali-pakai, scan = sesi pindah ke HP
    // tanpa ketik password/OTP. Perangkat ini terevict (aturan 1-perangkat).
    if (!document.getElementById('btnSwitch')) {
      const sw = document.createElement('button');
      sw.id = 'btnSwitch'; sw.textContent = '📱'; sw.title = 'Pindah ke HP (QR, tanpa login ulang)';
      sw.className = 'layout-toggle';
      sw.onclick = () => { try { openSwitchModal(); } catch (_) {} };
      topControls.appendChild(sw);
    }
  }
  // Modal QR switch: render lokal (vendor qrcode), countdown TTL, refresh.
  // Tanpa innerHTML string server (XSS): semua teks via textContent.
  function closeSwitchModal() {
    try {
      const ov = document.getElementById('switchModal');
      if (ov) { try { clearInterval(ov._t); } catch (_) {} ov.remove(); }
    } catch (_) {}
  }
  function openSwitchModal() {
    closeSwitchModal();
    const ov = document.createElement('div');
    ov.id = 'switchModal';
    ov.style.cssText = 'position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.6)';
    ov.addEventListener('click', (e) => { if (e.target === ov) closeSwitchModal(); });
    const card = document.createElement('div');
    card.style.cssText = 'background:rgba(2,15,42,.97);border:1px solid var(--neon);border-radius:12px;padding:18px;width:min(320px,92vw);text-align:center;color:var(--text-main)';
    const t = document.createElement('div');
    t.textContent = 'Pindah ke HP';
    t.style.cssText = 'font-weight:700;margin-bottom:4px';
    const sub = document.createElement('div');
    sub.textContent = 'Scan dengan kamera HP — sesi pindah, perangkat ini keluar.';
    sub.style.cssText = 'font-size:12px;color:var(--text-body);margin-bottom:10px';
    const img = document.createElement('img');
    img.alt = 'QR pindah perangkat';
    img.style.cssText = 'width:200px;height:200px;background:#fff;padding:8px;border-radius:8px;display:none;margin:0 auto';
    const cd = document.createElement('div');
    cd.style.cssText = 'font-size:12px;margin-top:8px;color:var(--text-body);min-height:16px';
    const row = document.createElement('div');
    row.style.cssText = 'margin-top:10px;display:flex;gap:8px;justify-content:center';
    const mkBtn = (label) => {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = label;
      b.style.cssText = 'border:1px solid var(--neon);background:rgba(45,242,255,.12);color:var(--text-header);border-radius:6px;padding:6px 12px;cursor:pointer;font-size:12px';
      return b;
    };
    const btnRe = mkBtn('QR baru');
    const btnX = mkBtn('Tutup');
    btnX.onclick = () => closeSwitchModal();
    async function load() {
      cd.textContent = 'Membuat QR…';
      img.style.display = 'none';
      try {
        const r = await fetch('/api/auth/switch-mint', { method: 'POST', credentials: 'same-origin', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ origin: location.origin }) });
        const j = await r.json().catch(() => ({}));
        if (!r.ok || !j.url) throw new Error((j && j.error) || ('HTTP ' + r.status));
        if (typeof qrcode === 'function') {
          const qr = qrcode(0, 'M');
          qr.addData(j.url);
          qr.make();
          img.src = qr.createDataURL(6, 4);
          img.style.display = 'block';
        } else {
          cd.textContent = 'Buka di HP: ' + j.url;
        }
        const exp = Date.now() + (j.expires_in || 120) * 1000;
        try { clearInterval(ov._t); } catch (_) {}
        const tick = () => {
          const s = Math.max(0, Math.round((exp - Date.now()) / 1000));
          cd.textContent = s > 0 ? ('Berlaku ' + s + ' dtk — scan sekarang') : 'Kedaluarsa — tekan QR baru';
          if (s <= 0) { try { clearInterval(ov._t); } catch (_) {} }
        };
        tick();
        ov._t = setInterval(tick, 1000);
      } catch (e) { cd.textContent = 'Gagal: ' + String((e && e.message) || e); }
    }
    btnRe.onclick = () => load();
    row.appendChild(btnRe); row.appendChild(btnX);
    card.appendChild(t); card.appendChild(sub); card.appendChild(img); card.appendChild(cd); card.appendChild(row);
    ov.appendChild(card);
    document.body.appendChild(ov);
    load();
  }
  // optBtn dibuat di blok topControls di atas, jadi di frame yang sama sudah ada
  // di DOM — tidak perlu menunggu frame berikutnya. rAF sengaja dihindari: tab
  // yang tidak terlihat (background tab, SESI idle) tidak pernah menjalankan rAF,
  // jadi menu Options tidak akan pernah dibangun sampai tab di-render ulang.
  initPanelOptions(layout);
  // Allowlist panel_access (DB) — setelah menu Options jadi, panel tak
  // terdaftar di-hide + checkbox dikunci. Panel terdaftar tak tersentuh.
  try { applyPanelAccess(layout); } catch (_) {}
  // ChatBox minimize/maximize — 1 tombol ─ di head + FAB 💬 44px.
  // Elegan: fade+scale halus, FAB di kiri/kanan vertikal (mirror tombol arsip).
  // Perilaku: seret vertikal, dobel-klik pindah sisi kiri↔kanan, posisi tersimpan.
  (function(){
    try {
      const box = document.getElementById('chatBox');
      const fab = document.getElementById('chatFab');
      const minBtn = document.getElementById('chatMinBtn');
      if(!box || !fab || !minBtn) return;
      const KEY = 'ana_chat_min';
      const KEY_SIDE = 'ana_chat_fab_side';
      const KEY_TOP = 'ana_chat_fab_top';
      // migrasikan posisi bebas lama (left) → hanya sisi kiri (arsip behaviour)
      try { if (localStorage.getItem('ana_chat_fab_left') != null) { localStorage.removeItem('ana_chat_fab_left'); } } catch(_){}
      const hud = document.getElementById('hud') || fab.parentElement;
      const applySide = (side) => {
        const s = side === 'right' ? 'right' : 'left';
        fab.dataset.side = s;
        if (s === 'right') { fab.style.left = ''; fab.style.right = '10px'; }
        else { fab.style.left = '10px'; fab.style.right = ''; }
        try { localStorage.setItem(KEY_SIDE, s); } catch(_){}
      };
      const applyPos = () => {
        try {
          const side = localStorage.getItem(KEY_SIDE) || '';
          if (side === 'right' || side === 'left') applySide(side);
          else fab.removeAttribute('data-side'); // default tengah-bawah sampai dipindah
          const t = parseFloat(localStorage.getItem(KEY_TOP) || '');
          if (isFinite(t)) {
            // sudah pernah dipindah: bekukan vertikal, kosongkan bottom
            if (!fab.dataset.side) applySide('left');
            fab.style.top = Math.max(8, t) + 'px';
            fab.style.bottom = 'auto';
            fab.style.transform = 'none';
          }
        } catch(_){}
      };
      applyPos();
      const apply = (min) => {
        box.classList.toggle('is-minimized', !!min);
        fab.classList.toggle('is-visible', !!min);
        try { fab.setAttribute('aria-hidden', String(!min)); } catch(_){}
      };
      let min = false;
      try { min = localStorage.getItem(KEY) === '1'; } catch(_){}
      apply(min);
      const setMin = (v) => {
        min = !!v;
        apply(min);
        try { localStorage.setItem(KEY, min ? '1' : '0'); } catch(_){}
        if(!min) { try { document.getElementById('chatInput')?.focus(); } catch(_){} }
      };
      minBtn.addEventListener('click', (e) => { e.stopPropagation(); setMin(true); });
      let fabDragged = false;
      fab.addEventListener('click', (e) => {
        if (fabDragged) { fabDragged = false; e.preventDefault(); e.stopPropagation(); return; }
        setMin(false);
      });
      fab.addEventListener('dblclick', (e) => {
        e.preventDefault(); e.stopPropagation();
        const cur = fab.dataset.side === 'right' ? 'right' : 'left';
        // belum pernah dipindah (tengah): dblclick pertama → kiri (posisi 50% tinggi)
        if (!fab.dataset.side) {
          applySide('left');
          const hr = hud ? hud.getBoundingClientRect() : { top: 0, height: window.innerHeight };
          const y = Math.round(hr.height / 2 - fab.offsetHeight / 2);
          fab.style.top = y + 'px';
          fab.style.bottom = 'auto';
          fab.style.transform = 'none';
          try { localStorage.setItem(KEY_TOP, String(y)); } catch(_){}
        } else {
          applySide(cur === 'right' ? 'left' : 'right');
        }
      });
      // Drag vertikal saja — sisi dijepit saat seret horizontal jauh (mirror arsip dx>60)
      fab.addEventListener('pointerdown', (ev) => {
        if (!fab.classList.contains('is-visible')) return;
        ev.preventDefault();
        const hr = (hud && hud.getBoundingClientRect) ? hud.getBoundingClientRect() : { left: 0, top: 0, height: window.innerHeight };
        const r = fab.getBoundingClientRect();
        // Bekukan dari centering/default ke piksel; pastikan sisi terpasang
        if (!fab.dataset.side) applySide('left');
        // top kini: jika sudah ada top tersimpan pakai itu, kalau tidak dari posisi sekarang
        let curTop = parseFloat(fab.style.top);
        if (!isFinite(curTop)) curTop = r.top - hr.top;
        fab.style.transform = 'none';
        fab.style.bottom = 'auto';
        fab.style.top = curTop + 'px';
        // left/right sudah via data-side — jangan ubah horizontal kecuali jepit sisi
        const sx = ev.clientX, sy = ev.clientY;
        let moved = false;
        fabDragged = false;
        try { fab.setPointerCapture(ev.pointerId); } catch(_){}
        fab.style.cursor = 'grabbing';
        const minY = 8;
        const move = (e2) => {
          const dx = e2.clientX - sx, dy = e2.clientY - sy;
          if (Math.abs(dy) > 6 || Math.abs(dx) > 6) moved = true;
          if (!moved) return;
          const maxY = Math.max(minY, (hud ? hud.clientHeight : window.innerHeight) - fab.offsetHeight - 8);
          const ny = Math.min(Math.max(curTop + dy, minY), maxY);
          fab.style.top = ny + 'px';
          // jepit sisi saat seret horizontal jauh (mirror arsip)
          if (dx > 60) applySide('right');
          else if (dx < -60) applySide('left');
        };
        const up = () => {
          fab.style.cursor = '';
          if (moved) fabDragged = true;
          try {
            const vT = parseFloat(fab.style.top) || 0;
            localStorage.setItem(KEY_TOP, String(Math.round(vT)));
          } catch(_){}
          fab.removeEventListener('pointermove', move);
          fab.removeEventListener('pointerup', up);
          fab.removeEventListener('pointercancel', up);
        };
        fab.addEventListener('pointermove', move);
        fab.addEventListener('pointerup', up);
        fab.addEventListener('pointercancel', up);
      });
    } catch(_){}
  })();
  log('status', 'INIT', 'ANA FUI HUD terintegrasi penuh.');
  setAgentState('IDLE');
  // Boot
  (async () => {
    try {
      const s = await api.getStatus();
      await loadSessions();
      try { _threadLoadHistory(currentSessionId); } catch (_) {}
      loadStatus();
      log('status', 'BOOT', `gateway online · ${s.runtime} core · profile=${s.profile || 'default'} · permission=${s.permission}`);
      try { const mj = await fetch('/api/mode', { headers: api.headers() }).then(r => r.json()); if (mj.mode) applyMode(mj.mode); } catch (_) {}
      log('voice', 'VOICE', `channel ready — ${s.stt || 'browser'} / ${s.tts || 'browser'}`);
    } catch (e) { log('error', 'STATUS', 'server unreachable'); }
  })();
}

init();
