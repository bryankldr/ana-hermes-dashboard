// ui/src/spatialChart.js — panel chart di DALAM #mapPanel (SPATIAL MAP).
// Full control ANA via session state /api/spatial/chart. Frontend hanya render + poll.
// Vendor: Chart.js 4 UMD (window.Chart). Tanpa npm.
//
// Mendukung >1 chart dalam 1 box (layout "grid"), KPI row, dan narasi.
// Lihat docs/refaktor/anna_chart.md untuk mapping intent → visualisasi.
let _charts = [];                 // instance Chart.js, paralel dgn spec
let _token = "";
let _log = () => {};
let _timer = null;
let _lastUpdated = 0;
let _renderedOnce = false;   // true setelah render pertama (beda dari updated=0)
let _wrap = null, _canvas = null, _titleEl = null, _metaEl = null;

const PALETTE = ["#EF4444","#FACC15","#22C55E","#3B82F6","#A78BFA","#F97316","#38BDF8","#F472B6","#22D3EE","#E879F9","#34D399","#FDE047"];
const STATUS_TONE = { Aktif:"#22C55E", AKTIF:"#22C55E", "Aktif":"#22C55E", Idle:"#FACC15", IDLE:"#FACC15",
  Idle:"#FACC15", Bongkor:"#EF4444", BONGKOR:"#EF4444", "Tanpa penyadap":"#F97316",
  "Multi penyadap":"#3B82F6", Terpenuhi:"#22C55E", Kurang:"#FACC15" };
const GOOD = "#22C55E", WARN = "#FACC15", BAD = "#EF4444", INFO = "#3B82F6";
function palette(i){ return PALETTE[i % PALETTE.length]; }
function hexOk(s){ return typeof s==="string" && /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(s.trim()); }

function ensureDom(){
  if (_wrap) return _wrap;
  const host = document.querySelector("#mapPanel .map-wrap") || document.getElementById("mapPanel") || document.getElementById("mapBox")?.parentElement;
  if (!host) return null;
  let wrap = document.getElementById("spatialChartWrap");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.id = "spatialChartWrap";
    wrap.className = "spatial-chart flying hidden";
    wrap.innerHTML = ''
      + '<div class="spatial-chart-head">'
      + '  <span class="spatial-chart-title" id="spatialChartTitle">Chart</span>'
      + '  <span class="spatial-chart-meta" id="spatialChartMeta"></span>'
      + '  <button class="spatial-chart-close" id="spatialChartClose" title="Tutup (ANA bisa tampilkan lagi)">✕</button>'
      + '</div>'
      + '<div class="spatial-chart-kpis" id="spatialChartKpis"></div>'
      + '<div class="spatial-chart-grid" id="spatialChartGrid"></div>'
      + '<div class="spatial-chart-narration" id="spatialChartNarration"></div>';
    host.appendChild(wrap);
  }
  _wrap = wrap;
  _canvas = wrap.querySelector("#spatialChartCanvas");  // mode single lama, opsional
  _titleEl = wrap.querySelector("#spatialChartTitle");
  _metaEl = wrap.querySelector("#spatialChartMeta");
  wrap.querySelector("#spatialChartClose")?.addEventListener("click", () => {
    hideLocal();
    try { fetch("/api/spatial/chart", { method:"POST", headers:{ "X-Ana-Token": _token, "Content-Type":"application/json" }, body: JSON.stringify({visible:false, chart:null}) }); } catch(_){}
  });
  return wrap;
}

function hideLocal(){
  if (_wrap) { _wrap.classList.add("hidden"); _wrap.classList.remove("visible"); }
  destroyCharts();
}

// ── status petak: warna semantik, bukan acak ──────────────────────────────────
function colorFor(label, i){
  const k = String(label||"").trim();
  if (STATUS_TONE[k]) return STATUS_TONE[k];
  return palette(i);
}

// -- dataset per tipe -- ─────────────────────────────────────────────────────
function buildDatasets(spec){
  const t = spec.type || "bar";
  const labels = spec.labels || [];
  const sets = spec.datasets || [];
  if (t === "scatter") {
    // bubble: {points:[[x,y,size]]} → Chart.js bubble
    const pts = spec.points || sets.flatMap(ds => (ds.points||[]).map(p => [p[0], p[1], p.length>2 ? p[2] : 1]));
    return {
      type: "bubble",
      datasets: [{ label: sets[0]?.label || "petak", data: pts,
        backgroundColor: sets[0]?.color || "#3B82F699", borderColor: sets[0]?.color || "#3B82F6", borderWidth: 1 }]
    };
  }
  return {
    type: null, // Chart.js ikut type utama
    datasets: sets.map((ds, i) => {
      const base = hexOk(ds.color) ? ds.color : palette(i);
      if (t === "line") {
        return { label: ds.label||"", data: ds.data||[], borderColor: base,
          backgroundColor: base+"33", tension: 0.35, fill: false, pointRadius: 3, borderWidth: 2 };
      }
      return { label: ds.label||"", data: ds.data||[], backgroundColor: base,
        borderColor: base, borderWidth: 1, borderRadius: 4 };
    })
  };
}

// ── bullet: bar horizontal + marker target + label angka ──────────────────────
function buildBullet(spec){
  const ds = spec.datasets?.[0] || {};
  const vals = ds.data || [];
  const target = Number(spec.options?.target || 0);
  const max = Math.max(target, ...vals.map(Number)) * 1.15 || 1;
  const actual = Number(vals[0] || 0);
  const ds2 = [{
    label: ds.label || "aktual",
    data: [actual],
    backgroundColor: actual >= target ? GOOD : WARN,
    borderRadius: 4, borderWidth: 0,
    // marker target digambar sebagai overflow bar transparan — teknik Chart.js baku
  }];
  return {
    type: "bar",
    indexAxis: "x",
    data: { labels: [spec.options?.yLabel || ds.label || "Aktual"], datasets: ds2 },
    extra: { target, max, actual, labels: spec.labels }
  };
}

// ── waterfall: target → aktual → gap, semua dari angka nyata ───────────────────
function buildWaterfall(spec){
  const ds = spec.datasets?.[0] || {};
  const v = (ds.data||[]).map(Number);
  const target = Number(spec.options?.target || v[0] || 0);
  const actual = Number(v[1] || v[0] || 0);
  const gap = actual - target;
  return { target, actual, gap, labels: ["Target", "Aktual", "Gap"],
    colors: ["#38BDF8", actual >= target ? GOOD : BAD, gap >= 0 ? GOOD : BAD] };
}

// ── render 1 chart ke canvas + container ─────────────────────────────────────
function renderOne(spec, canvas, meta){
  const t = spec.type || "bar";
  const labels = spec.labels || [];
  const opts = spec.options || {};
  const title = spec.title || "Chart";
  const showLegend = opts.showLegend !== false && (spec.datasets||[]).length > 1;

  if (t === "bullet") {
    const b = buildBullet(spec);
    const pct = b.target > 0 ? (b.actual / b.target * 100) : 0;
    // Anotasi achievement disimpan di inst (untuk tooltip/narasi ANNA) (achievement % + gap), lalu bar
    const cfg = {
      type: "bar",
      data: { labels: [b.target > 0 ? `${opts.yLabel || "Aktual"} (${b.actual}) / target ${b.target}` : (opts.yLabel || "Aktual")],
              datasets: [{ label: b.labels?.[0] || "", data: [b.actual],
                backgroundColor: b.actual >= b.target ? GOOD : WARN, borderRadius: 4 }] },
      options: { responsive:true, maintainAspectRatio:false, indexAxis:"x",
        animation:{duration:420}, plugins:{ legend:{display:false},
          tooltip:{enabled:true} },
        scales: { x:{ grid:{display:false}, ticks:{color:"#7DD3E8", font:{size:10}} },
          y:{ beginAtZero:true, suggestedMax: b.max,
              grid:{color:"rgba(45,242,255,0.08)"}, ticks:{color:"#7DD3E8", font:{size:10}} } }
      }
    };
    const inst = new window.Chart(canvas.getContext("2d"), cfg);
    inst.$anaAch = pct; inst.$anaGap = b.actual - b.target;
    return inst;
  }

  if (t === "waterfall") {
    const w = buildWaterfall(spec);
    // 3 batang: target, aktual, gap (dari 0)
    const cfg = {
      type: "bar",
      data: { labels: w.labels, datasets: [{ label: spec.datasets?.[0]?.label || "ton",
        data: [w.target, w.actual, Math.abs(w.gap)],
        backgroundColor: w.colors, borderRadius: 4, borderWidth: 0 }] },
      options: { responsive:true, maintainAspectRatio:false,
        animation:{duration:420}, plugins:{ legend:{display:false}, tooltip:{enabled:true} },
        scales: { x:{ stacked:false, grid:{display:false}, ticks:{color:"#7DD3E8", font:{size:10}} },
          y:{ beginAtZero:true, grid:{color:"rgba(45,242,255,0.08)"}, ticks:{color:"#7DD3E8", font:{size:10}} } }
      }
    };
    const inst = new window.Chart(canvas.getContext("2d"), cfg);
    inst.$anaWaterfall = w;
    return inst;
  }

  const { datasets } = buildDatasets(spec);
  const isPie = t === "doughnut" || t === "pie";
  let type = "bar", indexAxis = "x";
  if (t === "h_bar" || t === "stacked_bar") { type = "bar"; indexAxis = t === "h_bar" ? "y" : "x"; }
  else if (t === "pareto") { type = "bar"; }
  else if (t === "scatter") { type = "bubble"; }
  else if (t === "line") type = "line";
  else if (t === "doughnut") type = "doughnut";
  else if (t === "pie") type = "pie";

  // stacked: warna per kategori status, segment per dataset
  let cs = datasets;
  if (t === "stacked_bar") {
    // satu bar per kategori, warna = status; atau dataset per status?
    // Spec: labels=status, datasets=1 → horizontal stacked composer.
    // Kalau labels Multi-P1/P2, dataset = status → stacked vertikal.
    cs = (spec.datasets||[]).map((ds, i) => ({
      label: ds.label||"", data: ds.data||[],
      backgroundColor: colorFor(ds.label, i),
      borderColor: colorFor(ds.label, i), borderWidth: 0, borderRadius: 3
    }));
  }
  if (isPie) {
    cs = [(spec.datasets?.[0])].filter(Boolean).map((ds, i) => ({
      label: ds.label||"", data: ds.data||[],
      backgroundColor: (Array.isArray(ds.colors) && ds.colors.length)
        ? ds.colors.filter(hexOk) : labels.map((_, j) => colorFor(labels[j], j)),
      borderColor: "rgba(0,0,0,0.25)", borderWidth: 1
    }));
  }
  const stacked = opts.stacked || t === "stacked_bar";

  const cfg = {
    type,
    data: { labels, datasets: cs },
    options: {
      responsive: true, maintainAspectRatio: false, indexAxis,
      animation: { duration: 420 },
      plugins: {
        legend: { display: showLegend && !isPie, labels:{ color:"#CFFAFE", boxWidth:12, font:{ family:"Share Tech Mono", size:10 } } },
        title: { display: false }, tooltip: { enabled: true }
      },
      scales: isPie ? {} : {
        x: { stacked, ticks:{ color:"#7DD3E8", font:{size:10} }, grid:{ color:"rgba(45,242,255,0.08)" } },
        y: { stacked, beginAtZero:true, ticks:{ color:"#7DD3E8", font:{size:10} }, grid:{ color:"rgba(45,242,255,0.08)" } }
      }
    }
  };
  if (t === "scatter") { cfg.options.plugins.legend.display = false; cfg.options.scales.x.title = { display:true, text: opts.xLabel || "Aktivitas" }; cfg.options.scales.y.title = { display:true, text: opts.yLabel || "Produksi" }; }
  const inst = new window.Chart(canvas.getContext("2d"), cfg);
  return inst;
}

function renderKpis(kpis){
  const host = document.getElementById("spatialChartKpis");
  if (!host) return;
  if (!kpis || !kpis.length) { host.innerHTML = ""; host.style.display = "none"; return; }
  host.style.display = "grid";
  host.innerHTML = kpis.map(k => {
    const tone = k.tone || "neutral";
    return '<div class="spatial-kpi" data-tone="' + tone + '">'
      + '<span class="spatial-kpi-label">' + escapeHtml(k.label) + '</span>'
      + '<span class="spatial-kpi-value">' + escapeHtml(k.value) + (k.unit ? ' <i>' + escapeHtml(k.unit) + '</i>' : '') + '</span>'
      + (k.sub ? '<span class="spatial-kpi-sub">' + escapeHtml(k.sub) + '</span>' : '')
      + '</div>';
  }).join("");
}

function escapeHtml(s){
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}

// ── Teks header jalan kalau kepotong (marquee) ──────────────────────────────
// Hanya tempel .marquee saat teks benar-benar overflow (scrollWidth > clientWidth).
// Jarak geser = kelebihan teks; durasi ~24px/detik + jeda baca di keyframes.
// Teks pendek = statis (class dilepas). Dipanggil tiap judul berubah.
function setTitleMarquee(txt){
  if (!_titleEl) return;
  let track = _titleEl.querySelector(":scope > .mq-track");
  if (!track) { _titleEl.textContent = ""; track = document.createElement("span"); track.className = "mq-track"; _titleEl.appendChild(track); }
  track.textContent = txt || "Chart";
  _titleEl.classList.remove("marquee");
  track.style.transform = "";
  // offsetWidth span (inline-block selalu, ukur kapan saja), bukan scrollWidth
  // yang 0 saat class marquee dilepas.
  const over = track.offsetWidth - _titleEl.clientWidth;
  if (over > 8) {
    _titleEl.style.setProperty("--mq-dist", (-(over + 24)) + "px");
    _titleEl.style.setProperty("--mq-dur", (Math.round(over / 24) + 10) + "s");
    _titleEl.classList.add("marquee");
  }
}

// Ukur ulang saat lebar panel berubah (resize LayoutManager) — teks yang dulu
// muat bisa kepotong, atau sebaliknya. Guard: ResizeObserver mati di tab hidden,
// jadi render() tiap judul berubah tetap jadi titik sinkron utama.
let _mqRO = null;
function watchTitleMarquee(){
  if (_mqRO || !_titleEl || typeof ResizeObserver === "undefined") return;
  let t = 0;
  _mqRO = new ResizeObserver(() => {
    clearTimeout(t);
    t = setTimeout(() => {
      const track = _titleEl.querySelector(":scope > .mq-track");
      if (track) setTitleMarquee(track.textContent);
    }, 150);
  });
  try { _mqRO.observe(_titleEl); } catch(_) { _mqRO = null; }
}

// -- render grid / single ----------------------------------------------------
function destroyCharts(){
  for (const c of _charts) { try { c.destroy(); } catch(_) {} }
  _charts = [];
}

// Penting untuk stabilitas: JANGAN rebuild Chart.js kalau state tak berubah.
// Tanpa guard ini, poll 2 detik + destroy/rebuild bikin instance menumpuk
// dan browser "stuck". render() dipanggil hanya saat `updated` benar-benar beda.
function render(state){
  const wrap = ensureDom();
  if (!wrap) return;
  const grid = document.getElementById("spatialChartGrid");
  const narr = document.getElementById("spatialChartNarration");
  if (!state || !state.visible) { destroyCharts(); grid.innerHTML = ""; renderKpis(null); hideLocal(); return; }

  const charts = (state.charts && state.charts.length) ? state.charts
               : (state.chart ? [state.chart] : null);
  if (!charts || !charts.length) { destroyCharts(); grid.innerHTML = ""; renderKpis(null); hideLocal(); return; }

  destroyCharts();
  grid.innerHTML = "";
  setTitleMarquee(state.title || charts[0]?.title || "Chart");
  watchTitleMarquee();
  if (_metaEl) {
    const m = state.meta || {};
    const parts = [m.periode || "", m.source || ""].filter(Boolean);
    // Badge provenance: operator harus selalu lihat kapan data terakhir masuk,
    // karena data SIMOGE bukan realtime (input paling banyak 12.00-15.00 + sore).
    const pv = m.provenance;
    if (pv) {
      const staleTxt = pv.hot ? "hot" : ((pv.stale_hari || 0) + " hari lalu");
      const who = (pv.n_penyadap || 0) + " penyadap";
      parts.push("data " + (pv.tgl || "?") + " · " + staleTxt + " · " + who);
      _metaEl.classList.toggle("stale", !pv.hot);
    }
    _metaEl.textContent = parts.join(" · ");
  }
  renderKpis(state.kpis);

  const multi = charts.length > 1;
  grid.classList.toggle("grid", multi);
  grid.style.display = multi ? "grid" : "block";
  if (multi) grid.style.setProperty("--ana-cols", charts.length > 3 ? 3 : 2);
  wrap.classList.toggle("multi", multi || (state.kpis||[]).length > 0);

  for (const spec of charts) {
    const cell = document.createElement("div");
    cell.className = "spatial-chart-cell";
    const h = document.createElement("div");
    h.className = "spatial-chart-cell-title";
    h.textContent = spec.title || "Chart";
    // wrapper berheight tetap: canvas Chart.js responsive mengisi wrapper,
    // bukan kontrak layout flex yang bisa tumbuh tanpa batas (bug "meninggi").
    const holder = document.createElement("div");
    holder.className = "spatial-chart-canvas";
    const cv = document.createElement("canvas");
    holder.appendChild(cv);
    cell.appendChild(h); cell.appendChild(holder);
    grid.appendChild(cell);
    try {
      const inst = renderOne(spec, cv, state.meta);
      _charts.push(inst);
    } catch(e){
      cell.innerHTML = '<div class="spatial-chart-err">Gagal render: ' + escapeHtml(String(e?.message||e).slice(0,90)) + '</div>';
      _log("chart","CHART","render gagal [" + (spec.type||"?") + "]: " + String(e?.message||e).slice(0,120));
    }
  }
  if (narr) { narr.textContent = state.narration || ""; narr.style.display = state.narration ? "block" : "none"; }

  wrap.classList.remove("hidden");
  wrap.classList.add("visible");
}

// In-flight guard: setInterval(2s) bisa memicu tick lagi sementara fetch
// sebelumnya masih jalan. Dua render paralel = dua instance Chart.js pada
// canvas yang sama = browser "stuck". JANGAN hapus _busy.
let _busy = false;

async function tick(){
  if (_busy) return;
  _busy = true;
  try{
    const r = await fetch("/api/spatial/chart", { headers:{ "X-Ana-Token": _token }, cache:"no-store" });
    if (!r.ok) return;
    const j = await r.json();
    if (!j || j.ok===false) return;
    // guard berlaku juga saat updated=0 (state awal) — sebelumnya 0 lolos
    // sehingga panel di-render ulang tiap 2 detik walau tak ada perubahan.
    const upd = Number(j.updated||0);
    if (upd === _lastUpdated && _renderedOnce) return;
    _lastUpdated = upd; _renderedOnce = true;
    ensureDom();
    if (!j.visible) { hideLocal(); return; }
    render(j);
  }catch(_){}
  finally { _busy = false; }
}

export function initSpatialChart({ token="", log=()=>{} }={}){
  _token = token||"";
  _log = log;
  ensureDom();
  if (_timer) return;
  tick();
  _timer = setInterval(tick, 2000);
  try{ window.__spatialChart = { tick, render, hide: hideLocal, get lastUpdated(){return _lastUpdated;}, get count(){return _charts.length;} }; }catch(_){}
}

export function stopSpatialChart(){
  if (_timer) clearInterval(_timer);
  _timer=null;
  destroyCharts();
}
