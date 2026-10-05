"""
Spatial report bridge — LAPORAN BISNIS multi halaman di dalam SPATIAL MAP.

Pola sama seperti spatial_chart_store.py: Python holder → HTTP → frontend poll → render.
ANA yang control 100% via API (buka/tutup/ganti isi). Session memory, tidak persist.

Perbedaan dari chart: laporan = dokumen siap cetak. Isinya `pages[]`,
satu elemen pages[] = satu halaman A4. Chart TIDAK jadi blok di sini
(Chart.js = <canvas>, tak terbaca di PDF); angka masuk lewat tabel + KPI.

State shape:
  {
    "visible": bool,
    "title":   str,               # judul dokumen
    "subtitle": str,              # mis. scope + periode
    "pages":   [{title, subtitle, blocks:[...]}],
    "evidence": [{statement, source, value}],
    "meta":    {"source": str, "periode": str},
    "updated": float (epoch)
  }

Block types (hanya ini — cukup untuk dokumen):
  {"type":"para",  "text": str}
  {"type":"kpi",   "items": [{label,value,unit,tone}]}
  {"type":"table", "title": str, "columns": [str], "rows": [[..]]}
  {"type":"list",  "items": [str]}
  {"type":"note",  "text": str}   # catatan keterbatasan / evidence
  {"type":"chart", "chart": "bar|pie|line", "title": str, "labels": [str],
                  "series": [{name, data:[num], unit}]}
  {"type":"row",   "cols": [block, ...]}          # grid 2 kolom (blok di dalam)
  {"type":"cover", "title": str, "subtitle": str, "period": str, "org": str}

Chart TIDAK pakai Chart.js/<canvas> — canvas tak tercetak rapi di PDF. Chart
dirender sebagai SVG inline: vektor, tajam di layar maupun di kertas, nol dependency.
"""
import threading, time

_LOCK = threading.Lock()
_STATE = {
    "visible": False, "title": "", "subtitle": "", "pages": [],
    "evidence": [], "meta": {}, "updated": 0.0,
}

MAX_PAGES = 30
MAX_BLOCKS = 20
MAX_ROWS = 60
MAX_COLS = 10
MAX_KPIS = 8
MAX_TEXT = 4000
MAX_LABELS = 24
MAX_SERIES = 6
MAX_ROW_COLS = 2
MAX_NEST = 2            # {type:"row"} boleh satu tingkat di dalam {type:"row"}
MAX_DEPTH = 3
_TONES = frozenset({"good", "warn", "bad", "neutral"})
_CHARTS = frozenset({"bar", "pie", "line"})
_BLOCKS = frozenset({"para", "kpi", "table", "list", "note", "chart", "row", "cover"})


def _s(v, n=MAX_TEXT):
    return str(v if v is not None else "")[:n]


def _num(v):
    """Coerce chart datum to a finite float. Non-numeric → None (slot becomes a gap).

    Report pages are rendered as inline SVG, so every number MUST be a real
    number before it reaches the coordinate maths — NaN/''/None would produce
    `NaN` attributes that silently drop the whole path.
    """
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _norm_series(series, n_labels):
    out = []
    for s in (series or [])[:MAX_SERIES]:
        if not isinstance(s, dict):
            continue
        data = []
        for v in (s.get("data") or [])[:n_labels]:
            f = _num(v)
            data.append(f if f is not None else 0.0)
        out.append({"name": _s(s.get("name"), 40), "data": data,
                    "unit": _s(s.get("unit"), 16)})
    return [s for s in out if s["data"]]


def _norm_chart(b):
    kind = _s(b.get("chart"), 12).strip().lower()
    if kind not in _CHARTS:
        return None
    labels = [_s(x, 40) for x in (b.get("labels") or [])[:MAX_LABELS]]
    if not labels:
        return None
    series = _norm_series(b.get("series"), len(labels))
    if not series:
        return None
    return {"type": "chart", "chart": kind, "title": _s(b.get("title"), 120),
            "labels": labels, "series": series}


def _norm_kpi(k):
    if not isinstance(k, dict):
        return None
    tone = _s(k.get("tone"), 16).strip().lower()
    return {"label": _s(k.get("label"), 40), "value": _s(k.get("value"), 24),
            "unit": _s(k.get("unit"), 16), "sub": _s(k.get("sub"), 64),
            "tone": tone if tone in _TONES else "neutral"}


def _norm_block(b, depth=0):
    if not isinstance(b, dict):
        return None
    if depth > MAX_DEPTH:
        return None
    t = _s(b.get("type"), 20).strip().lower()
    if t not in _BLOCKS:
        return None
    if t == "para" or t == "note":
        return {"type": t, "text": _s(b.get("text"))}
    if t == "cover":
        return {"type": t, "title": _s(b.get("title"), 160),
                "subtitle": _s(b.get("subtitle"), 200),
                "period": _s(b.get("period"), 80), "org": _s(b.get("org"), 160)}
    if t == "list":
        items = [_s(x) for x in (b.get("items") or [])[:20] if _s(x)]
        # title opsional → judul panel (template: INSIGHT / STRATEGI)
        return {"type": t, "title": _s(b.get("title"), 120), "items": items}
    if t == "kpi":
        items = [x for x in (_norm_kpi(k) for k in (b.get("items") or [])[:MAX_KPIS]) if x]
        return {"type": t, "items": items}
    if t == "chart":
        return _norm_chart(b)
    if t == "row":
        cols = [x for x in (_norm_block(c, depth + 1) for c in (b.get("cols") or [])[:MAX_ROW_COLS]) if x]
        if not cols:
            return None
        return {"type": t, "cols": cols}
    # table
    cols = [_s(c, 40) for c in (b.get("columns") or [])[:MAX_COLS]]
    if not cols:
        return None
    rows = []
    for r in (b.get("rows") or [])[:MAX_ROWS]:
        if not isinstance(r, (list, tuple)):
            continue
        cells = [_s(v, 60) for v in list(r)[:MAX_COLS]]
        cells += [""] * (len(cols) - len(cells))
        rows.append(cells[:MAX_COLS])
    return {"type": "table", "title": _s(b.get("title"), 120),
            "columns": cols, "rows": rows}


def _norm_page(p):
    if not isinstance(p, dict):
        return None
    blocks = [x for x in (_norm_block(b) for b in (p.get("blocks") or [])[:MAX_BLOCKS]) if x]
    if not blocks:
        return None
    return {"title": _s(p.get("title"), 160), "subtitle": _s(p.get("subtitle"), 160),
            "blocks": blocks}


def _hide(meta=None):
    with _LOCK:
        _STATE.update(visible=False, title="", subtitle="", pages=[],
                      evidence=[], meta=dict(meta or {}), updated=time.time())
    return True, None


def set_report(payload: dict):
    """payload = {visible, title, subtitle, pages, evidence, meta}."""
    if not isinstance(payload, dict):
        return False, "payload harus object"
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    if payload.get("visible") is False:
        return _hide(meta)
    pages_in = payload.get("pages")
    if pages_in is None:
        if "pages" in payload:          # eksplisit kosong = hide
            return _hide(meta)
        return True, None                # tak ada opinion = biarkan
    if isinstance(pages_in, dict):
        pages_in = [pages_in]
    if pages_in == []:
        return True, None
    if not isinstance(pages_in, list):
        return False, "pages harus list"
    pages = [p for p in (_norm_page(x) for x in pages_in[:MAX_PAGES]) if p]
    if not pages:
        return False, "pages kosong setelah normalisasi"
    evidence = []
    for e in (payload.get("evidence") or [])[:40]:
        if isinstance(e, dict):
            evidence.append({"statement": _s(e.get("statement"), 240),
                             "source": _s(e.get("source"), 120),
                             "value": _s(e.get("value"), 40)})
    with _LOCK:
        _STATE.update(visible=True if payload.get("visible") is None else bool(payload["visible"]),
                      title=_s(payload.get("title"), 160),
                      subtitle=_s(payload.get("subtitle"), 200),
                      pages=pages, evidence=evidence,
                      meta=dict(meta or {}), updated=time.time())
    return True, None


def get_state():
    with _LOCK:
        return {"visible": bool(_STATE["visible"]), "title": _STATE["title"],
                "subtitle": _STATE["subtitle"], "pages": [dict(p, blocks=list(p["blocks"]))
                                                         for p in _STATE["pages"]],
                "evidence": list(_STATE["evidence"]), "meta": dict(_STATE["meta"]),
                "updated": float(_STATE["updated"])}


def clear():
    return set_report({"visible": False, "pages": []})