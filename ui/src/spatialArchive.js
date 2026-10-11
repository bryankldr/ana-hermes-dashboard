// ui/src/spatialArchive.js — ARSIP chart/laporan per-user di DALAM #mapPanel.
// Server-side persist (.ana_archive.json), isolasi per user_id login.
// Drawer 🗂 di toolbar: daftar milik user, klik = tampilkan kembali,
// 🗑 = hapus milik sendiri. Panel chart/laporan bisa digeser (drag via
// header [data-drag]) tapi DIKEPUNG dalam .map-wrap (clamp posisi).
// Frontend hanya render + panggil API; state kebenaran di server.

let _token = "";
let _log = () => {};
let _drawer = null;
let _items = [];
let _open = false;
let _busy = false;

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmtTime(ts) {
  try {
    const d = new Date(Number(ts) * 1000);
    if (isNaN(d)) return "";
    const p = n => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes());
  } catch (_) { return ""; }
}

async function apiList() {
  const r = await fetch("/api/spatial/archive", { headers: { "X-Ana-Token": _token }, cache: "no-store", credentials: "same-origin" });
  if (!r.ok) throw new Error("HTTP " + r.status);
  const j = await r.json();
  if (!j || j.ok === false) throw new Error(j?.error || "gagal");
  return j.items || [];
}

async function apiShow(entry) {
  const r = await fetch("/api/spatial/archive", { method: "POST", headers: { "X-Ana-Token": _token, "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify({ entry_id: entry.id, kind: entry.kind }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.ok === false) throw new Error(j?.error || ("HTTP " + r.status));
  // paksa poll chart/report render ulang: bump via tick langsung
  try { window.__spatialChart?.tick(); } catch (_) {}
  try { window.__spatialReport?.tick?.(); } catch (_) {}
  return j;
}

async function apiSave(kind) {
  const r = await fetch("/api/spatial/archive", { method: "POST", headers: { "X-Ana-Token": _token, "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify({ kind }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.ok === false) throw new Error(j?.error || ("HTTP " + r.status));
  return j;
}

async function apiMove(id, to) {
  const r = await fetch("/api/spatial/archive", { method: "POST", headers: { "X-Ana-Token": _token, "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify({ op: "move", entry_id: id, to }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.ok === false) throw new Error(j?.error || ("HTTP " + r.status));
  return j;
}

async function apiDel(id) {
  // Hapus via POST {"op":"delete"} — server tak punya do_DELETE (501).
  const r = await fetch("/api/spatial/archive", { method: "POST", headers: { "X-Ana-Token": _token, "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify({ op: "delete", entry_id: id }) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.ok === false) throw new Error(j?.error || ("HTTP " + r.status));
  return j;
}

function renderList() {
  const host = document.getElementById("spatialArchiveList");
  if (!host) return;
  if (!_items.length) {
    host.innerHTML = '<div class="arch-empty">Belum ada arsip.<br>Tampilkan chart/laporan lalu tekan 💾 untuk menyimpan.</div>';
    return;
  }
  host.innerHTML = _items.map((e, i) => {
    const badge = e.kind === "report" ? "LAPORAN" : "CHART";
    const sub = (e.n_items ? e.n_items + (e.kind === "report" ? " hlm" : " chart") + " · " : "") + fmtTime(e.saved_at);
    return '<div class="arch-item" data-id="' + esc(e.id) + '">'
      + '<span class="arch-num">' + (i + 1) + '</span>'
      + '<span class="arch-grip" data-act="grip" title="Seret untuk pindah urutan">⋮⋮</span>'
      + '<button class="arch-open" data-act="open" title="' + esc(e.title) + ' — klik untuk tampilkan kembali">'
      + '<span class="arch-badge" data-kind="' + esc(e.kind) + '">' + badge + '</span>'
      + '<span class="arch-title" title="' + esc(e.title) + '">' + esc(e.title) + '</span>'
      + '<span class="arch-sub">' + esc(sub) + '</span></button>'
      + '<button class="arch-del" data-act="del" title="Hapus arsip ini"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button></div>';
  }).join("");
}

async function refresh() {
  const host = document.getElementById("spatialArchiveList");
  try {
    _items = await apiList();
    renderList();
  } catch (e) {
    if (host) host.innerHTML = '<div class="arch-empty">Gagal memuat arsip: ' + esc(String(e?.message || e).slice(0, 80)) + '</div>';
  }
  try {
    const c = document.getElementById("spatialArchiveCount");
    if (c) { c.textContent = String(_items.length); c.style.display = _items.length ? "flex" : "none"; }
  } catch (_) {}
}

function setOpen(v) {
  _open = !!v;
  if (!_drawer) return;
  _drawer.classList.toggle("open", _open);
  const btn = document.getElementById("spatialArchiveBtn");
  if (btn) btn.classList.toggle("active", _open);
  if (_open) refresh();
}

// ── drag dalam panel: header [data-drag] jadi handle, posisi DIKEPUNG ──
// Panel .flying absolute left/top 50% + translate(-50%,-50%). Saat drag
// pertama: bekukan posisi piksel saat itu (dari getBoundingClientRect relatif
// host), lepas translate, lalu gerak via left/top — selalu clamp agar
// seluruh header tetap dalam .map-wrap (tak bisa kabur keluar panel).
function clampWrap(wrap, x, y) {
  const host = wrap.parentElement;
  if (!host) return [x, y];
  const hr = host.getBoundingClientRect();
  const r = wrap.getBoundingClientRect();
  const w = r.width, h = r.height;
  const m = 8; // margin dalam
  // header (48px pertama) wajib terlihat: batas atas longgar, bawah ketat
  const minX = m - (w - 60), maxX = hr.width - 60 - m;
  const minY = m, maxY = hr.height - 48 - m;
  return [Math.min(Math.max(x, minX), Math.max(maxX, minX)), Math.min(Math.max(y, minY), Math.max(maxY, minY))];
}

function makeDraggable(wrap) {
  if (!wrap || wrap._anaDrag) return;
  wrap._anaDrag = true;
  const handle = wrap.querySelector("[data-drag]");
  if (!handle) return;
  handle.style.cursor = "grab";
  handle.addEventListener("pointerdown", ev => {
    if (ev.target.closest("button")) return; // tombol tetap klik
    const host = wrap.parentElement;
    if (!host) return;
    ev.preventDefault();
    const hr = host.getBoundingClientRect();
    const r = wrap.getBoundingClientRect();
    // bekukan ke piksel (lepas centering translate)
    wrap.style.transform = "none";
    let x = r.left - hr.left, y = r.top - hr.top;
    wrap.style.left = x + "px"; wrap.style.top = y + "px";
    wrap.style.right = "auto"; wrap.style.bottom = "auto";
    const sx = ev.clientX, sy = ev.clientY;
    handle.style.cursor = "grabbing";
    handle.setPointerCapture?.(ev.pointerId);
    const move = e2 => {
      const nx = x + (e2.clientX - sx), ny = y + (e2.clientY - sy);
      const [cx, cy] = clampWrap(wrap, nx, ny);
      wrap.style.left = cx + "px"; wrap.style.top = cy + "px";
    };
    const up = () => {
      handle.style.cursor = "grab";
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", up);
      handle.removeEventListener("pointercancel", up);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
    handle.addEventListener("pointercancel", up);
  });
}

// ── FAB arsip geser vertikal + jepit kiri/kanan ──
// Seret vertikal (>6px) = pindah posisi Y. Seret horizontal jauh (>60px)
// = jepit ke sisi kiri/kanan terdekat. Klik (tanpa seret) = buka/tutup.
// Sisi + posisi Y disimpan di localStorage agar tetap pasca refresh.
let _fabDragged = false;
function _fabApplySide(b, side) {
  b.dataset.side = side;
  if (side === "right") {
    b.style.left = "auto";
    b.style.right = "10px";
  } else {
    b.style.right = "auto";
    b.style.left = "10px";
  }
  try { localStorage.setItem("ana_arch_fab_side", side); } catch (_) {}
}
function makeFabDraggable(b, host) {
  if (!b || b._anaFabDrag) return;
  b._anaFabDrag = true;
  // pulihkan sisi + posisi simpanan
  try {
    const side = localStorage.getItem("ana_arch_fab_side") || "left";
    _fabApplySide(b, side === "right" ? "right" : "left");
    const sv = parseFloat(localStorage.getItem("ana_arch_fab_top") || "");
    if (isFinite(sv)) {
      b.style.transform = "none";
      b.style.top = Math.max(8, sv) + "px";
    }
  } catch (_) {}
  // dblclick = pindah sisi cepat (tanpa seret jauh)
  b.addEventListener("dblclick", ev => {
    ev.preventDefault(); ev.stopPropagation();
    _fabApplySide(b, (b.dataset.side === "right") ? "left" : "right");
  });
  b.addEventListener("pointerdown", ev => {
    ev.preventDefault();
    const hr = host.getBoundingClientRect();
    const r = b.getBoundingClientRect();
    // bekukan ke piksel (lepas centering translateY)
    b.style.transform = "none";
    let y = r.top - hr.top;
    b.style.top = y + "px";
    const sx = ev.clientX, sy = ev.clientY;
    let moved = false;
    _fabDragged = false;
    b.style.cursor = "grabbing";
    try { b.setPointerCapture(ev.pointerId); } catch (_) {}
    const minY = 8;
    const move = e2 => {
      const dx = e2.clientX - sx, dy = e2.clientY - sy;
      if (Math.abs(dy) > 6 || Math.abs(dx) > 6) moved = true;
      if (!moved) return;
      const maxY = Math.max(minY, host.clientHeight - b.offsetHeight - 8);
      const ny = Math.min(Math.max(y + dy, minY), maxY);
      b.style.top = ny + "px";
      // pregeser horizontal: jepit sisi secara live saat seret jauh
      if (dx > 60) _fabApplySide(b, "right");
      else if (dx < -60) _fabApplySide(b, "left");
    };
    const up = () => {
      b.style.cursor = "";
      if (moved) { _fabDragged = true; } // tekan click berikutnya
      try {
        const v = parseFloat(b.style.top) || 0;
        localStorage.setItem("ana_arch_fab_top", String(Math.round(v)));
      } catch (_) {}
      b.removeEventListener("pointermove", move);
      b.removeEventListener("pointerup", up);
      b.removeEventListener("pointercancel", up);
    };
    b.addEventListener("pointermove", move);
    b.addEventListener("pointerup", up);
    b.addEventListener("pointercancel", up);
  });
}

function ensureDom() {
  const host = document.querySelector("#mapPanel .map-wrap");
  if (!host) return null;
  // tombol 🗂 FLYING kecil di sisi map (kiri/kanan, di atas peta)
  if (!document.getElementById("spatialArchiveBtn")) {
    const b = document.createElement("button");
    b.id = "spatialArchiveBtn";
    b.className = "spatial-archive-fab";
    b.title = "Arsip saya — klik buka, seret geser, dobel-klik pindah sisi";
    b.setAttribute("aria-label", "Arsip chart dan laporan");
    b.innerHTML = '<span class="arch-fab-ico">🗂</span>'
      + '<span class="arch-fab-label">ARSIP</span>'
      + '<span class="arch-fab-count" id="spatialArchiveCount">0</span>';
    b.addEventListener("click", ev => {
      if (_fabDragged) { _fabDragged = false; ev.preventDefault(); ev.stopPropagation(); return; }
      setOpen(!_open);
    });
    host.appendChild(b);
    makeFabDraggable(b, host);
  }
  // drawer dalam map-wrap (kanan, di atas peta, di bawah panel konten)
  let dw = document.getElementById("spatialArchiveDrawer");
  if (!dw) {
    dw = document.createElement("div");
    dw.id = "spatialArchiveDrawer";
    dw.className = "spatial-archive";
    dw.innerHTML = '<div class="arch-head" data-drag="1"><span class="arch-title-h">🗂 ARSIP SAYA</span>'
      + '<button class="arch-close" id="spatialArchiveClose" title="Tutup">✕</button></div>'
      + '<div class="arch-list" id="spatialArchiveList"></div>'
      + '<div class="arch-foot" id="spatialArchiveFoot">maks 20 per user · tersimpan di server</div>';
    host.appendChild(dw);
    dw.querySelector("#spatialArchiveClose")?.addEventListener("click", () => setOpen(false));
    dw.querySelector("#spatialArchiveList")?.addEventListener("pointerdown", ev => {
      // Seret via gagang ⋮⋮: geser item, lepas = simpan urutan ke server.
      const grip = ev.target.closest('[data-act="grip"]');
      if (!grip || _busy) return;
      ev.preventDefault();
      const host = document.getElementById("spatialArchiveList");
      const item = grip.closest(".arch-item");
      if (!host || !item) return;
      const from = _items.findIndex(x => x.id === item.dataset?.id);
      if (from < 0) return;
      const h = item.offsetHeight + 6;
      item.classList.add("dragging");
      let cur = from;
      const move = e2 => {
        const dy = e2.clientY - ev.clientY;
        let to = from + Math.round(dy / h);
        to = Math.max(0, Math.min(_items.length - 1, to));
        if (to !== cur) {
          cur = to;
          const rows = [...host.querySelectorAll(".arch-item")];
          rows.forEach(r => r.classList.remove("drop-before", "drop-after"));
          const target = rows[to];
          if (target && target !== item) {
            target.classList.add(to < from ? "drop-before" : "drop-after");
          }
        }
        item.style.transform = "translateY(" + Math.max(-from * h, Math.min((_items.length - 1 - from) * h, dy)) + "px)";
      };
      const up = async () => {
        grip.removeEventListener("pointermove", move);
        grip.removeEventListener("pointerup", up);
        grip.removeEventListener("pointercancel", up);
        item.classList.remove("dragging");
        item.style.transform = "";
        host.querySelectorAll(".drop-before,.drop-after").forEach(r => r.classList.remove("drop-before", "drop-after"));
        if (cur === from) return;
        _busy = true;
        try {
          const e0 = _items[from];
          const j = await apiMove(e0.id, cur);
          _items = j.items || [];
          renderList();
          _log("arch", "ARSIP", "geser #" + (from + 1) + " -> #" + (cur + 1) + ": " + (e0.title || e0.id).slice(0, 60));
        } catch (err) {
          _log("arch", "ARSIP", "gagal: " + String(err?.message || err).slice(0, 100));
          alert("Arsip gagal: " + String(err?.message || err).slice(0, 120));
        } finally { _busy = false; }
      };
      grip.addEventListener("pointermove", move);
      grip.addEventListener("pointerup", up);
      grip.addEventListener("pointercancel", up);
      try { grip.setPointerCapture?.(ev.pointerId); } catch (_) {}
    });
    dw.querySelector("#spatialArchiveList")?.addEventListener("click", async ev => {
      const btn = ev.target.closest("[data-act]");
      if (!btn || _busy) return;
      if (btn.dataset.act === "grip") return; // gagang = seret, bukan klik
      const item = ev.target.closest(".arch-item");
      const id = item?.dataset?.id;
      const e = _items.find(x => x.id === id);
      if (!e) return;
      _busy = true;
      btn.classList.add("busy");
      try {
        const act = btn.dataset.act;
        const idx = _items.findIndex(x => x.id === id);
        if (act === "open") {
          await apiShow(e);
          _log("arch", "ARSIP", "tampilkan: " + (e.title || e.id).slice(0, 60));
          // drawer SENGAJA tetap terbuka — user bandingkan banyak arsip
          // tanpa buka-tutup berulang. Tutup manual via ✕.
        } else if (act === "del") {
          if (!confirm("Hapus arsip \"" + (e.title || e.id).slice(0, 60) + "\"?")) return;
          const j = await apiDel(e.id);
          _items = j.items || _items.filter(x => x.id !== e.id);
          renderList();
          _log("arch", "ARSIP", "hapus: " + (e.title || e.id).slice(0, 60));
        }
      } catch (err) {
        _log("arch", "ARSIP", "gagal: " + String(err?.message || err).slice(0, 100));
        alert("Arsip gagal: " + String(err?.message || err).slice(0, 120));
      } finally {
        _busy = false;
        btn.classList.remove("busy");
      }
    });
  }
  _drawer = dw;
  // drawer arsip ikut bisa digeser via header [data-drag], sama seperti
  // panel chart/laporan — tetap dikepung dalam .map-wrap (clamp di JS).
  makeDraggable(dw);
  // tombol 💾 di panel chart + laporan
  const cs = document.getElementById("spatialChartSave");
  if (cs && !cs._anaBind) {
    cs._anaBind = true;
    cs.addEventListener("click", async () => {
      if (_busy) return; _busy = true;
      try {
        const j = await apiSave("chart");
        _items = j.items || [];
        _log("arch", "ARSIP", "chart tersimpan: " + String(j.saved?.title || "").slice(0, 60));
        alert("Chart tersimpan di arsip.");
        if (_open) renderList();
      } catch (e) { alert("Simpan gagal: " + String(e?.message || e).slice(0, 120)); }
      finally { _busy = false; }
    });
  }
  const rs = document.getElementById("rptSave");
  if (rs && !rs._anaBind) {
    rs._anaBind = true;
    rs.addEventListener("click", async () => {
      if (_busy) return; _busy = true;
      try {
        const j = await apiSave("report");
        _items = j.items || [];
        _log("arch", "ARSIP", "laporan tersimpan: " + String(j.saved?.title || "").slice(0, 60));
        alert("Laporan tersimpan di arsip.");
        if (_open) renderList();
      } catch (e) { alert("Simpan gagal: " + String(e?.message || e).slice(0, 120)); }
      finally { _busy = false; }
    });
  }
  // panel bisa digeser tapi tetap dalam panel map
  makeDraggable(document.getElementById("spatialChartWrap"));
  makeDraggable(document.getElementById("spatialReportWrap"));
  return dw;
}

export function initSpatialArchive({ token = "", log = () => {} } = {}) {
  _token = token || "";
  _log = log;
  ensureDom();
  // panel chart/report dibuat on-demand oleh pollernya — pasang ulang tiap 3 dtk
  // sampai dua-duanya draggable (guard _anaDrag bikin ini murah).
  let n = 0;
  const t = setInterval(() => {
    try {
      ensureDom();
      const c = document.getElementById("spatialChartWrap");
      const r = document.getElementById("spatialReportWrap");
      if (c?._anaDrag && r?._anaDrag && document.getElementById("spatialArchiveBtn")) { clearInterval(t); }
    } catch (_) {}
    if (++n > 40) clearInterval(t);
  }, 3000);
  try { window.__spatialArchive = { refresh, open: () => setOpen(true), close: () => setOpen(false) }; } catch (_) {}
}
