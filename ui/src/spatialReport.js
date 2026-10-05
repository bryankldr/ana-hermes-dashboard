// ui/src/spatialReport.js — LAPORAN BISNIS multi halaman di DALAM #mapPanel.
// Full control ANA via session state /api/spatial/report. Frontend hanya render + poll.
// Chart.js (<canvas>) TIDAK dipakai — canvas tak tercetak rapi di PDF.
// Angka masuk lewat KPI + tabel + paragraf, satu elemen pages[] = satu halaman.
// @media print menyembunyikan semua panel lain lalu cetak .rpt-page saja.

let _token = "";
let _log = () => {};
let _timer = null;
let _lastUpdated = 0;
let _renderedOnce = false;
let _wrap = null;

function esc(s) {
  const C = String.fromCharCode;
  const t = String(s ?? C());
  return t.split(C(38)).join(C(38,97,109,112,59)).split(C(60)).join(C(38,108,116,59)).split(C(62)).join(C(38,103,116,59)).split(C(34)).join(C(38,113,117,111,116,59)).split(C(39)).join(C(38,35,51,57,59));
}
// Chart: inline SVG, bukan Chart.js.
// Palet & geometri MENGIKUTI proposal/stitch_image_to_html_converter/code.html
// (hasil konversi template ke HTML): urutan warna bar/pie, legend di atas bar,
// legend bawah pie "LABEL (n%)", area fill 2 seri untuk tren, tick x putar 40.
// Skala: px HTML x 0.8741 = pt A4. viewBox disesuaikan proporsi HTML (canvas).

const RPT_SVG = {
  bar:  ["#d6eef2", "#95d7df", "#8fa9b6", "#526f7a", "#9b51e0"],
  line: "#9edbe3", lineFill: "#e2f5f7",
  proj: "#526f7a",  projFill: "#8ba0ab",
  pie:  ["#9ddae3", "#546e7a", "#9bb3bf"],
  grid: "#e2e8f0", gridT: "#cbd5e1", axis: "#64748b",
  legendDot: ["#dcf3f5", "#526f7a"],
};

function svgOpen(w, h) {
  return '<svg class="rpt-svg" viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMidYMid meet" role="img">';
}

function fmtTick(v) {
  const a = Math.abs(v);
  if (a >= 1e6) return (v/1e6).toFixed(a % 1e6 === 0 ? 0 : 1) + "M";
  if (a >= 1e3) return (v/1e3).toFixed(a % 1e3 === 0 ? 0 : 1) + "k";
  return String(Math.round(v * 100) / 100);
}

function renderBarChart(b) {
  const W = 440, H = 220, PL = 48, PR = 16, PB = 52;
  const labels = b.labels, data = b.series[0].data;
  // Legend wrap greedy ala HTML flex-wrap: baris di-center, PT ikut jumlah baris.
  const _iw = W - PL - PR;
  const _br = [[]]; let _bw = 0;
  labels.forEach((lab, i) => {
    const wpx = 25 + String(lab).length * 7.2;
    if (_bw + wpx > _iw && _br[_br.length - 1].length) { _br.push([]); _bw = 0; }
    _br[_br.length - 1].push(i); _bw += wpx;
  });
  const PT = 2 + _br.length * 12;
  const max = Math.max(0, ...data);
  const top = max > 0 ? max : 1;
  const iw = W - PL - PR, ih = H - PT - PB;
  const bw = iw / labels.length;
  let s = svgOpen(W, H);

  for (let i = 0; i <= 4; i++) {
    const y = PT + ih - (ih * i / 4);
    s += '<line class="rpt-grid" x1="' + PL + '" y1="' + y.toFixed(1) + '" x2="' + (W - PR) + '" y2="' + y.toFixed(1) + '"/>';
    s += '<text class="rpt-axis" x="' + (PL - 6) + '" y="' + (y + 3).toFixed(1) + '" text-anchor="end">' + esc(fmtTick(top * i / 4)) + '</text>';
  }

  labels.forEach((lab, i) => {
    const v = data[i] || 0;
    const h = Math.max(0, (v / top) * ih);
    const x = PL + i * bw + bw * 0.24, w = bw * 0.52;
    const fill = RPT_SVG.bar[i % RPT_SVG.bar.length];
    s += '<rect class="rpt-bar" x="' + x.toFixed(1) + '" y="' + (PT + ih - h).toFixed(1) + '" width="' + w.toFixed(1) + '" height="' + h.toFixed(1) + '" rx="3" fill="' + fill + '"/>';
    const tx = (x + w/2).toFixed(1), ty = PT + ih + 14;
    s += '<text class="rpt-axis rpt-axis-x" x="' + tx + '" y="' + ty + '" text-anchor="end" transform="rotate(40 ' + tx + ' ' + ty + ')">' + esc(lab) + '</text>';
  });
  s += '<line class="rpt-axis-line" x1="' + PL + '" y1="' + (PT + ih) + '" x2="' + (W - PR) + '" y2="' + (PT + ih) + '"/>';

  _br.forEach((row, ri) => {
    const ly = 6 + ri * 12;
    const _rw = row.reduce((a, i) => a + 20 + esc(labels[i].toUpperCase()).length * 6.5 + 12, -12);
    let lx = PL + Math.max(0, (_iw - _rw) / 2);
    row.forEach(i => {
      const lab = labels[i];
      const fill = RPT_SVG.bar[i % RPT_SVG.bar.length];
      const t = esc(lab.toUpperCase()), wpx = 20 + t.length * 6.5;
      s += '<circle cx="' + (lx + 5) + '" cy="' + ly + '" r="5" fill="' + fill + '"/>';
      s += '<text class="rpt-legend" x="' + (lx + 13) + '" y="' + (ly + 4) + '">' + t + '</text>';
      lx += wpx + 12;
    });
  });
  return s + '</svg>';
}

function renderLineChart(b) {
  const W = 844, H = 220, PL = 56, PR = 24, PT = 16, PB = 40;
  const labels = b.labels;
  const flat = b.series.flatMap(s => s.data);
  const max = Math.max(0, ...flat), min = Math.min(0, ...flat);
  const span = (max - min) || 1;
  const top = max + span * 0.08, bot = min - span * 0.08;
  const iw = W - PL - PR, ih = H - PT - PB;
  const n = Math.max(1, labels.length - 1);
  const X = i => PL + (iw * i / n);
  const Y = v => PT + ih - ((v - bot) / (top - bot)) * ih;
  let s = svgOpen(W, H);

  for (let i = 0; i <= 4; i++) {
    const val = bot + (top - bot) * i / 4;
    const y = Y(val);
    s += '<line class="rpt-grid-t" x1="' + PL + '" y1="' + y.toFixed(1) + '" x2="' + (W - PR) + '" y2="' + y.toFixed(1) + '"/>';
    s += '<text class="rpt-axis-y" x="' + (PL - 6) + '" y="' + (y + 3).toFixed(1) + '" text-anchor="end">' + esc(fmtTick(val)) + '</text>';
  }

  b.series.forEach((ser, si) => {
    const proj = si > 0;
    const color = proj ? RPT_SVG.proj : RPT_SVG.line;
    const fill = proj ? RPT_SVG.projFill : RPT_SVG.lineFill;
    const base = (PT + ih).toFixed(1);
    const pts = ser.data.map((v, i) => X(i).toFixed(1) + ',' + Y(v).toFixed(1));
    s += '<polygon class="rpt-line-fill" fill="' + fill + '" fill-opacity="0.85" points="' + X(0).toFixed(1) + ',' + base + ' ' + pts.join(" ") + ' ' + X(ser.data.length-1).toFixed(1) + ',' + base + '"/>';
    s += '<polyline class="rpt-line" points="' + pts.join(" ") + '" stroke="' + color + '" stroke-width="' + (proj ? '1.5' : '2.5') + '" stroke-linejoin="round" fill="none"/>';
    ser.data.forEach((v, i) => {
      s += '<circle cx="' + X(i).toFixed(1) + '" cy="' + Y(v).toFixed(1) + '" r="2" fill="' + color + '"/>';
    });
  });

  labels.forEach((lab, i) => {
    s += '<text class="rpt-axis-tx" x="' + X(i).toFixed(1) + '" y="' + (H - 10) + '" text-anchor="middle">' + esc(lab) + '</text>';
  });
  s += '<line class="rpt-axis-line" x1="' + PL + '" y1="' + (PT + ih) + '" x2="' + (W - PR) + '" y2="' + (PT + ih) + '"/>';

  const unit = b.series[0].unit;
  const items = b.series.map((ser, si) => ({name: esc(ser.name), color: si > 0 ? RPT_SVG.proj : RPT_SVG.line}));
  let lx = W / 2 - items.reduce((a, it) => a + 18 + it.name.length * 5.5, 0) / 2;
  items.forEach((it, si) => {
    s += '<circle cx="' + (lx + 6) + '" cy="10" r="6" fill="' + RPT_SVG.legendDot[si % RPT_SVG.legendDot.length] + '"/>';
    s += '<text class="rpt-legend-t" x="' + (lx + 16) + '" y="14">' + it.name + (unit ? ' (' + esc(unit) + ')' : '') + '</text>';
    lx += 22 + it.name.length * 5.5 + 24;
  });
  return s + '</svg>';
}

function renderPieChart(b) {
  const W = 280, H = 220, LG = 56;
  const cx = W / 2, cy = (H - LG) / 2, R = Math.min(cx, cy) - 10;
  const vals = b.series[0].data.slice(0, b.labels.length);
  const total = vals.reduce((a, v) => a + Math.abs(v), 0);
  let s = svgOpen(W, H);
  if (total <= 0) return s + '<text class="rpt-axis" x="' + W/2 + '" y="' + H/2 + '" text-anchor="middle">Data kosong</text></svg>';
  let ang = -Math.PI / 2;
  vals.forEach((v, i) => {
    const frac = Math.abs(v) / total;
    const sweep = frac * Math.PI * 2;
    const x2 = cx + R * Math.cos(ang + sweep), y2 = cy + R * Math.sin(ang + sweep);
    const large = sweep > Math.PI ? 1 : 0;
    const fill = RPT_SVG.pie[i % RPT_SVG.pie.length];
    if (frac >= 0.9999) {
      s += '<circle cx="' + cx + '" cy="' + cy + '" r="' + R + '" fill="' + fill + '"/>';
    } else {
      s += '<path d="M' + cx + ',' + cy + ' L' + cx + ',' + (cy - R) + ' A' + R + ',' + R + ' 0 ' + large + ' 1 ' + x2.toFixed(2) + ',' + y2.toFixed(2) + ' Z" fill="' + fill + '" stroke="#ffffff" stroke-width="1.5"/>';
    }
    ang += sweep;
  });
  const lines = b.labels.map((lab, i) => esc(lab) + ' (' + (Math.abs(vals[i]) / total * 100).toFixed(1) + '%)');
  lines.slice(0, 3).forEach((t, i) => {
    const y = H - LG + 14 + i * 13;
    const tw = t.trim().length * 5.8;
    s += '<rect x="' + (W / 2 - tw / 2 - 18).toFixed(1) + '" y="' + (y - 9) + '" width="12" height="8" fill="' + RPT_SVG.pie[i % RPT_SVG.pie.length] + '"/>';
    s += '<text class="rpt-legend-p" x="' + (W / 2 + 4) + '" y="' + y + '" text-anchor="middle">' + t.trim() + '</text>';
  });
  return s + '</svg>';
}

function renderChart(b, wide) {
  const body = b.chart === "pie" ? renderPieChart(b) : b.chart === "line" ? renderLineChart(b) : renderBarChart(b);
  return '<figure class="rpt-chart' + (wide ? ' rpt-chart--wide' : '') + '">' + (b.title ? '<figcaption class="rpt-chart-t">' + esc(b.title) + '</figcaption>' : '') + body + '</figure>';
}

function ensureDom() {
  if (_wrap && _wrap.isConnected) return _wrap;
  const host = document.querySelector("#mapPanel .map-wrap") || document.getElementById("mapPanel") || document.getElementById("mapBox")?.parentElement;
  if (!host) return null;
  let wrap = document.getElementById("spatialReportWrap");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.id = "spatialReportWrap";
    wrap.className = "spatial-report flying hidden";
    wrap.innerHTML = '<div class="rpt-head"><span class="rpt-head-title" id="rptTitle">LAPORAN</span><span class="rpt-head-meta" id="rptMeta"></span><button class="rpt-btn" id="rptPrint" title="Unduh / cetak (PDF)">Unduh</button><button class="rpt-btn ghost" id="rptClose" title="Tutup (ANA bisa tampilkan lagi)">Tutup</button></div><div class="rpt-body" id="rptBody"></div>';
    host.appendChild(wrap);
  }
  _wrap = wrap;
  wrap.querySelector("#rptPrint")?.addEventListener("click", () => {
    document.body.classList.add("rpt-printing");
    const done = () => document.body.classList.remove("rpt-printing");
    window.addEventListener("afterprint", done, { once: true });
    window.print();
    setTimeout(done, 1200);
  });
  wrap.querySelector("#rptClose")?.addEventListener("click", () => {
    hideLocal();
    fetch("/api/spatial/report", { method: "POST", headers: { "X-Ana-Token": _token, "Content-Type": "application/json" }, body: JSON.stringify({ visible: false, pages: [] }) }).catch(() => {});
  });
  return wrap;
}

function hideLocal() {
  if (_wrap) { _wrap.classList.add("hidden"); _wrap.classList.remove("visible"); }
}

function renderBlock(b, depth) {
  depth = depth || 0;
  switch (b.type) {
    case "para": return '<p class="rpt-para">' + esc(b.text) + '</p>';
    case "note": return '<div class="rpt-note">' + esc(b.text) + '</div>';
    case "cover": return '<div class="rpt-cover"><div class="rpt-cover-main">' + esc(b.title || "") + '</div>' + (b.subtitle ? '<div class="rpt-cover-sub">' + esc(b.subtitle) + '</div>' : '') + '<div class="rpt-cover-meta">' + (b.period ? '<span>' + esc(b.period) + '</span>' : '') + (b.org ? '<span> · </span><span>' + esc(b.org) + '</span>' : '') + '</div></div>';
    case "row": return '<div class="rpt-row" data-cols="' + b.cols.length + '">' + b.cols.map(c => '<div class="rpt-row-c">' + renderBlock(c, depth + 1) + '</div>').join("") + '</div>';
    case "list": { if (!b.items.length) return ""; const lis = b.items.map(i => '<li>' + esc(i) + '</li>').join(""); return b.title ? '<div class="rpt-panel"><div class="rpt-panel-t">' + esc(b.title) + '</div><ul class="rpt-list">' + lis + '</ul></div>' : '<ul class="rpt-list">' + lis + '</ul>'; }
    case "kpi": { if (!b.items.length) return ""; return '<div class="rpt-kpis">' + b.items.map(k => '<div class="rpt-kpi" data-tone="' + esc(k.tone || "neutral") + '"><span class="rpt-kpi-label">' + esc(k.label) + '</span><span class="rpt-kpi-value">' + esc(k.value) + (k.unit ? ' <i>' + esc(k.unit) + '</i>' : '') + '</span>' + (k.sub ? '<span class="rpt-kpi-sub">' + esc(k.sub) + '</span>' : '') + '</div>').join("") + '</div>'; }
    case "table": { if (!b.columns.length) return ""; const head = '<tr>' + b.columns.map(c => '<th>' + esc(c) + '</th>').join("") + '</tr>'; const body = b.rows.map(r => '<tr>' + r.map(c => '<td>' + esc(c) + '</td>').join("") + '</tr>').join(""); return '<div class="rpt-tablewrap"><table class="rpt-table">' + (b.title ? '<caption>' + esc(b.title) + '</caption>' : '') + '<thead>' + head + '</thead><tbody>' + body + '</tbody></table></div>'; }
    case "chart": return renderChart(b, depth === 0);
    default: return "";
  }
}

function render(state) {
  const wrap = ensureDom();
  if (!wrap) return;
  const body = document.getElementById("rptBody");
  const titleEl = document.getElementById("rptTitle");
  const metaEl = document.getElementById("rptMeta");
  if (!state || !state.visible || !state.pages?.length) { hideLocal(); return; }
  titleEl.textContent = state.title || "LAPORAN BISNIS";
  const m = state.meta || {};
  metaEl.textContent = [m.periode, m.source].filter(Boolean).join(" · ");
  body.innerHTML = state.pages.map((p, i) => '<article class="rpt-page">' + (p.title ? '<h3 class="rpt-h">' + esc(p.title) + '</h3>' : '') + (p.subtitle ? '<p class="rpt-sub">' + esc(p.subtitle) + '</p>' : '') + p.blocks.map(b => renderBlock(b, 0)).join("") + '<footer class="rpt-foot">Halaman ' + (i + 1) + ' dari ' + state.pages.length + (state.evidence?.length ? ' · ' + state.evidence.length + ' jejak evidence' : '') + '</footer></article>').join("");
  wrap.classList.remove("hidden");
  wrap.classList.add("visible");
}

let _busy = false;
async function tick() {
  if (_busy) return;
  _busy = true;
  try {
    const r = await fetch("/api/spatial/report", { headers: { "X-Ana-Token": _token }, cache: "no-store" });
    if (!r.ok) return;
    const j = await r.json();
    if (!j || j.ok === false) return;
    const upd = Number(j.updated || 0);
    if (upd === _lastUpdated && _renderedOnce) return;
    _lastUpdated = upd; _renderedOnce = true;
    ensureDom();
    if (!j.visible) { hideLocal(); return; }
    render(j);
  } catch (_) {}
  finally { _busy = false; }
}

export function initSpatialReport({ token = "", log = () => {} } = {}) {
  _token = token || "";
  _log = log;
  ensureDom();
  if (_timer) return;
  tick();
  _timer = setInterval(tick, 2000);
  try { window.__spatialReport = { tick, hide: hideLocal, get lastUpdated() { return _lastUpdated; } }; } catch (_) {}
}

export function stopSpatialReport() {
  if (_timer) clearInterval(_timer);
  _timer = null;
}