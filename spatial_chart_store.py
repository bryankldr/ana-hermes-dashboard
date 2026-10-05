"""
Spatial chart bridge — session state untuk dashboard BI di dalam SPATIAL MAP.

Pola sama seperti map_store.py: Python holder → HTTP → frontend poll → render.
ANA yang control 100% via API.

Dua mode (lihat docs/refaktor/anna_chart.md):
  single — satu chart, back-compat spec lama {visible, chart, meta}
  grid   — banyak chart + KPI dalam SATU panel (charts[], kpis[], narration, evidence)

State shape:
  {
    "visible": bool,
    "layout":  "single" | "grid",
    "title":   str,               # judul box (mode grid)
    "kpis":    [{label,value,unit,sub,tone}],
    "charts":  [chart_spec, ...],  # >1 = multi-chart dalam satu box
    "chart":   chart_spec | None,  # alias charts[0] — Poll frontend lama tetap jalan
    "narration": str,              # kalimat yang dibacakan ANNA
    "evidence":  [{statement,source,scope,value,unit}],
    "meta":    { "source": str, "periode": str, "updated_by": "ana"|"user" },
    "updated": float (epoch)
  }

Thread-safe via Lock. Tidak persist ke disk — session memory.
"""
import threading, time

_LOCK = threading.Lock()
_STATE = {
    "visible": False, "layout": "single", "title": "", "kpis": [], "charts": [],
    "chart": None, "narration": "", "evidence": [], "meta": {}, "updated": 0.0,
}

# type Chart.js native + mapping intent (docs/refaktor/anna_chart.md §12)
_ALIAS = {
    "horizontalbar": "h_bar", "hbar": "h_bar", "barhorizontal": "h_bar",
    "stacked": "stacked_bar", "stackedbar": "stacked_bar", "composition": "stacked_bar",
    "bullet": "bullet", "waterfall": "waterfall", "scatter": "scatter",
    "pareto": "pareto", "line": "line", "doughnut": "doughnut", "pie": "pie",
    "bar": "bar", "heatmap": "bar", "kpi": "bar",
}
ALLOWED_TYPES = frozenset({"bar", "h_bar", "line", "doughnut", "pie", "stacked_bar",
                           "bullet", "waterfall", "scatter", "pareto"})
MAX_CHARTS = 6
MAX_KPIS = 8
_TONES = frozenset({"good", "warn", "bad", "neutral"})


def _norm_type(t):
    s = (t or "").strip().lower()
    if s in _ALIAS:
        return _ALIAS[s]
    if s in ALLOWED_TYPES:          # biarkan nama kanonik apa adanya (stacked_bar, ...)
        return s
    return "bar"


def _nums(seq, n=48):
    out = []
    for v in list(seq)[:n]:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def _norm_chart(chart):
    """Chart spec → bentuk kanonik. Satu chart = satu box."""
    if not isinstance(chart, dict):
        return None
    labels = chart.get("labels") or []
    if not isinstance(labels, list):
        labels = [labels]
    labels = [str(x)[:40] for x in labels][:48]
    raw = chart.get("datasets") or []
    if not isinstance(raw, list):
        raw = [raw]
    norm_ds = []
    for ds in raw[:6]:
        if not isinstance(ds, dict):
            continue
        data = ds.get("data")
        # waterfall & scatter butuh titik (x,y) — jangan dipaksa jadi skalar
        if isinstance(data, dict):
            data = data.get("points") or []
        if not isinstance(data, list):
            data = [data]
        if data and any(isinstance(x, (list, tuple)) and len(x) >= 2 for x in data):
            norm_ds.append({
                "label": str(ds.get("label") or "")[:40],
                "points": [[float(x[0]), float(x[1])] for x in data][:64],
            })
            continue
        cols = ds.get("colors") or ds.get("backgroundColors")
        norm_ds.append({
            "label": str(ds.get("label") or "")[:40],
            "data": _nums(data),
            "color": (str(ds.get("color") or ds.get("backgroundColor") or "").strip()[:20] or None),
            "colors": [str(c)[:20] for c in cols][:48] if isinstance(cols, list) else None,
        })
    if not norm_ds:
        return None
    options = chart.get("options")
    options = options if isinstance(options, dict) else {}
    clean_opt = {}
    for k in ("showLegend", "stacked"):
        if k in options:
            clean_opt[k] = bool(options[k])
    if isinstance(options.get("target"), (int, float)):
        clean_opt["target"] = float(options["target"])
    if isinstance(options.get("yLabel"), str):
        clean_opt["yLabel"] = options["yLabel"][:32]
    out = {
        "type": _norm_type(chart.get("type")),
        "title": str(chart.get("title") or chart.get("label") or "")[:120],
        "labels": labels,
        "datasets": norm_ds,
        "options": clean_opt,
    }
    # poin bubble (scatter: size = luas petak)
    pts = chart.get("points")
    if isinstance(pts, list) and out["type"] == "scatter":
        out["points"] = [[_nums([p[0]], 1)[0], _nums([p[1]], 1)[0],
                          _nums([p[2] if len(p) > 2 else 1], 1)[0]]
                         for p in pts if isinstance(p, (list, tuple)) and len(p) >= 2][:64]
    return out


def _norm_kpi(k):
    if not isinstance(k, dict):
        return None
    tone = str(k.get("tone") or "neutral").strip().lower()
    return {
        "label": str(k.get("label") or "")[:40],
        "value": str(k.get("value") if k.get("value") is not None else "")[:24],
        "unit": str(k.get("unit") or "")[:16],
        "sub": str(k.get("sub") or "")[:64],
        "tone": tone if tone in _TONES else "neutral",
    }


def _hide(meta=None):
    with _LOCK:
        _STATE.update(visible=False, layout="single", title="", kpis=[], charts=[],
                      chart=None, narration="", evidence=[],
                      meta=dict(meta or {}), updated=time.time())
    return True, None


def set_chart(payload: dict):
    """payload = {visible, layout, title, kpis, charts|chart, narration, evidence, meta}."""
    if not isinstance(payload, dict):
        return False, "payload harus object"
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    charts_in = payload.get("charts")
    if charts_in is None:
        charts_in = payload.get("chart")
    vis = payload.get("visible")

    # ── hide HANYA kalau operator benar-benar minta sembunyi ──
    # charts_in=None (key tak ada) = "tak ada opinion" -> abaikan, jangan hide.
    # charts_in=None tapi key 'chart'/'charts' HADIR = eksplisit kosong = hide.
    if vis is False:
        return _hide(meta)
    explicit = ("charts" in payload) or ("chart" in payload)
    if charts_in is None:
        if explicit:
            return _hide(meta)
        return True, None                      # tak ada opinion sama sekali
    if isinstance(charts_in, dict):
        charts_in = [charts_in]
    if charts_in == []:
        return True, None          # daftar kosong = "tak ada chart baru", bukan hide
    if not isinstance(charts_in, list):
        return False, "charts harus list"

    norm = [c for c in (_norm_chart(c) for c in charts_in[:MAX_CHARTS]) if c]
    if not norm:
        return False, "datasets kosong"

    kpis = [k for k in (_norm_kpi(x) for x in (payload.get("kpis") or [])[:MAX_KPIS]) if k]
    evidence = []
    for e in (payload.get("evidence") or [])[:MAX_CHARTS * 2]:
        if isinstance(e, dict):
            evidence.append({
                "statement": str(e.get("statement") or "")[:200],
                "source": str(e.get("source") or "")[:120],
                "value": str(e.get("value") if e.get("value") is not None else "")[:32],
                "unit": str(e.get("unit") or "")[:16],
            })

    layout = "grid" if (len(norm) > 1 or kpis) else "single"
    with _LOCK:
        _STATE.update(
            visible=True if vis is None else bool(vis),
            layout=layout,
            title=str(payload.get("title") or "")[:120],
            kpis=kpis,
            charts=norm,
            chart=norm[0],                      # alias: frontend/poll lama tak pecah
            narration=str(payload.get("narration") or "")[:1200],
            evidence=evidence,
            meta=dict(meta or {}),
            updated=time.time(),
        )
    return True, None


def get_state():
    with _LOCK:
        return {
            "visible": bool(_STATE["visible"]), "layout": _STATE["layout"],
            "title": _STATE["title"], "kpis": list(_STATE["kpis"]),
            "charts": list(_STATE["charts"]), "chart": _STATE["chart"],
            "narration": _STATE["narration"], "evidence": list(_STATE["evidence"]),
            "meta": dict(_STATE["meta"]), "updated": float(_STATE["updated"]),
        }


def clear():
    return set_chart({"visible": False, "chart": None})