"""Business spatial intelligence layer — implementasi directive #1-20.

Sumber kebenaran: ui/data/petak_simple.json — wrapper {meta, features} harian
dari kph_bwb_sandbox2 (cadangan evaluasi hari ini) + backward compat array lama [{n,p}].
Business Map polygon bisnis tetap dari DB 100% via simoge-business (7 _map);
file ini hanya cadangan geometri + identitas untuk YOY / fallback ANNA.

Lapisan (directive #13):
  Business/Data (petak_simple.json {meta,features} ← generator harian DB)
    -> Spatial Intelligence (file ini, toleran wrapper)
      -> Map Control (map_store.py antrean + ui/src/mapControl.js adapter)
        -> render (Leaflet + Esri)

Prinsip (#CORE): tak pernah tebak koordinat. Semua geometri dari data.
ID = kode_evapot (join kunci getah_petak/petak_polygon). Jangan karang YOY — sebut meta.generated_at.
"""
import json
import math
import pathlib
import time
from collections import OrderedDict

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "ui" / "data" / "petak_simple.json"

_EARTH_M = 6371000.0

_cache = {"features": None, "by_id": None, "loaded_at": 0.0, "meta": None, "mtime": 0.0}
_recent = OrderedDict()  # directive #15: cache metadata ringan, max 50
RECENT_MAX = 50


def _hav(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_M * math.asin(math.sqrt(a))


MANIFEST = ROOT / "ui" / "data" / "snapshots" / "manifest.json"
PERIODE_DIR = ROOT / "ui" / "data" / "snapshots" / "periode"
DAILY_DIR = ROOT / "ui" / "data" / "snapshots" / "daily"

def _latest_snapshot():
    """Snapshot terbaru sebagai fallback bila live corrupt/hilang. Scan periode+daily+legacy flat."""
    candidates = []
    for d in [PERIODE_DIR, DAILY_DIR, ROOT / "ui" / "data" / "snapshots"]:
        try:
            candidates.extend(list(d.glob("petak_*.json")))
        except Exception:
            pass
    if not candidates:
        return None
    try:
        candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        return candidates[0]
    except Exception:
        return candidates[0] if candidates else None

def _raw_list_and_meta(src=None):
    """Toleran wrapper {meta,features} maupun array lama [{n,p}]. Robust: corrupt -> fallback snapshot."""
    path = src or DATA
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        # fallback ke snapshot terbaru
        snap = _latest_snapshot()
        if snap and snap != path:
            try:
                raw = json.loads(snap.read_text(encoding="utf-8"))
            except Exception:
                raise e
        else:
            raise
    if isinstance(raw, dict) and "features" in raw:
        return raw.get("features") or [], raw.get("meta") or {}
    if isinstance(raw, dict) and "data" in raw:  # varian lama bila ada
        return raw.get("data") or [], raw.get("meta") or {}
    if isinstance(raw, list):
        return raw, {}
    return [], {}

def _load():
    try:
        mt = DATA.stat().st_mtime
    except FileNotFoundError:
        mt = 0.0
    if _cache["features"] is not None and _cache.get("mtime") == mt:
        return _cache["features"], _cache["by_id"]
    try:
        feats_raw, meta = _raw_list_and_meta()
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        if _cache["features"] is not None:
            return _cache["features"], _cache["by_id"]
        snap = _latest_snapshot()
        if snap:
            try:
                feats_raw, meta = _raw_list_and_meta(snap)
                mt = snap.stat().st_mtime
            except Exception:
                raise e
        else:
            raise
    feats = []
    by_id = {}
    for f in feats_raw:
        pid = str(f.get("n", ""))
        rings = f.get("p") or []
        if not pid or not rings or not isinstance(rings, list):
            continue
        try:
            if rings and isinstance(rings[0], list) and rings[0] and isinstance(rings[0][0], list) and isinstance(rings[0][0][0], list):
                rings = [ring for poly in rings for ring in poly]
                f["p"] = rings
        except Exception:
            continue
        # validasi ring: skip rusak (non-numeric / <3 point)
        valid_rings = []
        for ring in rings:
            if not isinstance(ring, list) or len(ring) < 3:
                continue
            ok = True
            for c in ring:
                if not isinstance(c, (list, tuple)) or len(c) < 2:
                    ok = False; break
                try:
                    float(c[0]); float(c[1])
                except Exception:
                    ok = False; break
            if ok:
                valid_rings.append(ring)
        if not valid_rings:
            continue
        rings = valid_rings
        try:
            lons = [float(c[0]) for ring in rings for c in ring]
            lats = [float(c[1]) for ring in rings for c in ring]
            south, north = min(lats), max(lats)
            west, east = min(lons), max(lons)
        except Exception:
            continue
        n_pts = sum(len(r) for r in rings)
        outer = rings[0]
        try:
            cx = sum(float(c[0]) for c in outer) / len(outer)
            cy = sum(float(c[1]) for c in outer) / len(outer)
        except Exception:
            continue
        my = math.radians((south + north) / 2)
        area = 0.0
        for ring in rings:
            s = 0.0
            valid = True
            for i in range(len(ring)):
                try:
                    x1 = math.radians(float(ring[i][0])) * math.cos(my) * _EARTH_M
                    y1 = math.radians(float(ring[i][1])) * _EARTH_M
                    x2 = math.radians(float(ring[(i + 1) % len(ring)][0])) * math.cos(my) * _EARTH_M
                    y2 = math.radians(float(ring[(i + 1) % len(ring)][1])) * _EARTH_M
                except Exception:
                    valid = False; break
                s += (x1 * y2 - x2 * y1)
            if valid:
                area += abs(s) / 2
        rec = {"id": pid, "rings": len(rings), "points": n_pts,
               "bounds": {"south": south, "west": west, "north": north, "east": east},
               "centroid": {"lat": cy, "lng": cx}, "area_m2": round(area, 1),
               "nomor_petak": str(f.get("nomor_petak") or ""), "tahun_rtt": f.get("tahun_rtt")}
        feats.append(rec)
        by_id[pid] = rec
    if not feats and _cache["features"] is not None:
        return _cache["features"], _cache["by_id"]
    _cache.update(features=feats, by_id=by_id, loaded_at=time.time(), meta=meta, mtime=mt)
    return feats, by_id


def _touch(pid, meta):
    _recent[pid] = {"at": time.time(), **meta}
    while len(_recent) > RECENT_MAX:
        _recent.popitem(last=False)


# ── #6 semantic ops ──────────────────────────────────────────────
def resolve_entity(ref, selected=None, highlighted=None):
    """Resolve ref business -> id exact. Prioritas (#9): selected >
    highlighted > ref langsung > prefix search. Tak pernah tebak."""
    ref = (ref or "").strip()
    lower = ref.lower()
    if lower in ("petak ini", "yang ini", "polygon yang dipilih", "yang tadi",
                 "area tersebut", "di sebelahnya") or not ref:
        if selected and find_petak(selected):
            return {"id": selected, "via": "selected"}
        if highlighted:
            hl = highlighted if isinstance(highlighted, list) else [highlighted]
            for h in hl:
                if find_petak(str(h)):
                    return {"id": str(h), "via": "highlighted"}
        return {"id": None, "via": "ambiguous",
                "hint": "tidak ada petak terpilih — sebut nomor petak 14 digit"}
    if find_petak(ref):
        return {"id": ref, "via": "exact"}
    # substring search (kode_evapot atau nomor_petak, mis. "2111" atau "20B") -> kandidat
    feats, _ = _load()
    hits = [f["id"] for f in feats if ref in f["id"] or ref in (f.get("nomor_petak") or "")][:20]
    if len(hits) == 1:
        return {"id": hits[0], "via": "unique-substring"}
    return {"id": None, "via": "candidates", "candidates": hits,
            "count": sum(1 for f in feats if ref in f["id"])}


def find_petak(pid):
    _, by_id = _load()
    return by_id.get(str(pid))


def find_rph(prefix8):
    """Grup 8 digit pertama (mis. 21111030). Inferred dari pola ID, bukan SK resmi."""
    feats, _ = _load()
    p = str(prefix8)
    return [f["id"] for f in feats if f["id"].startswith(p)]


def find_by_prefix(prefix, limit=200):
    feats, _ = _load()
    p = str(prefix)
    # cocok kode_evapot prefix ATAU nomor_petak prefix (mis. 20B, 21A) untuk YOY cari
    hits = [f["id"] for f in feats if f["id"].startswith(p) or (f.get("nomor_petak") or "").startswith(p)]
    return {"prefix": p, "count": len(hits), "ids": hits[:limit],
            "truncated": len(hits) > limit}


def get_polygon(pid):
    """Geometri exact dari data (lon/lat apa adanya). Ringan: tanpa ini
    jangan kirim polygon ke LLM (#14)."""
    try:
        feats_raw, _ = _raw_list_and_meta()
    except Exception:
        if _cache["features"] is not None:
            # fallback via cache bounds? tetap coba raw snapshot
            try:
                snap = _latest_snapshot()
                if snap:
                    feats_raw, _ = _raw_list_and_meta(snap)
                else:
                    return None
            except Exception:
                return None
        else:
            return None
    for f in feats_raw:
        if str(f.get("n")) == str(pid):
            pp = f["p"] or []
            try:
                if pp and isinstance(pp[0], list) and pp[0] and isinstance(pp[0][0], list) and isinstance(pp[0][0][0], list):
                    pp = [ring for poly in pp for ring in poly]
            except Exception:
                pass
            return {"id": str(pid), "polygons": pp}
    return None


def get_feature_context(pid):
    """Metadata + bounds + centroid + area + tetangga untuk reasoning (#5)."""
    rec = find_petak(pid)
    if not rec:
        return None
    out = {"id": rec["id"], "bounds": rec["bounds"], "centroid": rec["centroid"],
           "area_m2": rec["area_m2"], "rings": rec["rings"], "points": rec["points"],
           "neighbors": [n["id"] for n in find_neighboring_polygons(pid, limit=8)],
           "map_op": {"op": "select_feature", "args": {"id": rec["id"]}},
           "fit": {"op": "fit_bounds", "args": {"bounds": rec["bounds"]}}}
    _touch(rec["id"], {"bounds": rec["bounds"]})
    return out


# ── #7 spatial ops (stdlib, di data — bukan di LLM) ──────────────
def _point_in_ring(lng, lat, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > lat) != (y2 > lat):
            xi = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lng < xi:
                inside = not inside
    return inside


def point_in_petak(lng, lat):
    feats, _ = _load()
    for f in feats:
        b = f["bounds"]
        if not (b["west"] <= lng <= b["east"] and b["south"] <= lat <= b["north"]):
            continue
        poly = get_polygon(f["id"])
        if poly and any(_point_in_ring(lng, lat, ring) for ring in poly["polygons"]):
            return f["id"]
    return None


def _bounds_overlap(a, b):
    return not (a["east"] < b["west"] or a["west"] > b["east"]
                or a["north"] < b["south"] or a["south"] > b["north"])


def find_neighboring_polygons(pid, limit=20):
    me = find_petak(pid)
    if not me:
        return []
    feats, _ = _load()
    scored = []
    for f in feats:
        if f["id"] == me["id"]:
            continue
        if _bounds_overlap(me["bounds"], f["bounds"]):
            d = _hav(me["centroid"]["lng"], me["centroid"]["lat"],
                     f["centroid"]["lng"], f["centroid"]["lat"])
            scored.append((d, f))
    scored.sort(key=lambda t: t[0])
    return [{"id": f["id"], "dist_m": round(d, 1), "bounds": f["bounds"]}
            for d, f in scored[:limit]]


def find_within_radius(lat, lng, radius_m=1000.0, limit=50):
    feats, _ = _load()
    out = []
    for f in feats:
        d = _hav(lng, lat, f["centroid"]["lng"], f["centroid"]["lat"])
        if d <= radius_m:
            out.append((d, f))
    out.sort(key=lambda t: t[0])
    return [{"id": f["id"], "dist_m": round(d, 1), "centroid": f["centroid"]}
            for d, f in out[:limit]]


def find_in_bounds(bounds, limit=200):
    feats, _ = _load()
    hits = [f["id"] for f in feats if _bounds_overlap(f["bounds"], bounds)]
    return {"count": len(hits), "ids": hits[:limit], "truncated": len(hits) > limit}


def collection_bounds(ids):
    _, by_id = _load()
    bs = [by_id[i]["bounds"] for i in ids if i in by_id]
    if not bs:
        return None
    return {"south": min(b["south"] for b in bs), "west": min(b["west"] for b in bs),
            "north": max(b["north"] for b in bs), "east": max(b["east"] for b in bs)}


def _load_manifest():
    try:
        if MANIFEST.exists():
            return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"periods": {}, "_meta": {}}

def list_periods():
    m = _load_manifest()
    periods = sorted(m.get("periods", {}).keys())
    return {"periods": periods, "manifest": m, "count": len(periods)}

def get_period(periode: str):
    """Load wrapper periode YYYY-MM-P1/P2. Returns {meta,features} or None."""
    periode = (periode or "").strip()
    if not periode:
        return None
    # via manifest
    m = _load_manifest()
    ent = (m.get("periods") or {}).get(periode)
    if ent and ent.get("file"):
        fp = ROOT / "ui" / "data" / "snapshots" / ent["file"]
        if fp.exists():
            try:
                raw = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and "features" in raw:
                    return raw
            except Exception:
                pass
    # direct
    for d in [PERIODE_DIR, DAILY_DIR]:
        fp = d / f"petak_{periode}.json"
        if fp.exists():
            try:
                raw = json.loads(fp.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and "features" in raw:
                    return raw
            except: pass
    # legacy daily YYYY-MM-DD yang periode-nya sama
    return None

def diff_periods(a: str, b: str):
    pa = get_period(a); pb = get_period(b)
    if not pa or not pb:
        return {"ok": False, "error": f"periode tidak ketemu: {a if not pa else b}"}
    ca = (pa.get("meta") or {}).get("counts") or {}
    cb = (pb.get("meta") or {}).get("counts") or {}
    # selisih counts numerik
    keys = sorted(set(list(ca.keys()) + list(cb.keys())))
    diff = {}
    for k in keys:
        try:
            va = int(ca.get(k, 0) or 0); vb = int(cb.get(k, 0) or 0)
            diff[k] = {"from": va, "to": vb, "delta": vb - va}
        except: 
            diff[k] = {"from": ca.get(k), "to": cb.get(k)}
    # geometri diff: tambah/hilang kode_evapot
    sa = {str(f.get("n")) for f in (pa.get("features") or [])}
    sb = {str(f.get("n")) for f in (pb.get("features") or [])}
    return {"ok": True, "from": a, "to": b,
            "meta_from": pa.get("meta"), "meta_to": pb.get("meta"),
            "counts_diff": diff,
            "added": sorted(list(sb - sa))[:50], "removed": sorted(list(sa - sb))[:50],
            "added_count": len(sb - sa), "removed_count": len(sa - sb)}

def get_history():
    m = _load_manifest()
    periods = sorted(m.get("periods", {}).keys())
    # ringkas untuk ANNA YOY
    summary = {k: {"generated_at": v.get("generated_at"), "tahun_rtt": v.get("tahun_rtt"), "counts": v.get("counts"), "finalized": v.get("finalized")} for k,v in (m.get("periods") or {}).items()}
    return {"periods": periods, "manifest": m, "summary": summary, "latest": periods[-1] if periods else None}

def stats():
    try:
        feats, _ = _load()
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        base = {"count": 0, "source": str(DATA), "lon_range": [0,0], "lat_range": [0,0], "recent_cached": len(_recent), "error": str(e)[:200], "stale": bool(_cache.get("features"))}
        if _cache.get("features"):
            base["count"] = len(_cache["features"])
        snap = _latest_snapshot()
        if snap:
            base["fallback_snapshot"] = str(snap)
        return base
    meta = _cache.get("meta") or {}
    if not meta:
        try:
            _, m = _raw_list_and_meta()
            meta = m or {}
        except Exception:
            meta = {}
    # history summary untuk ANNA YOY (tanpa scan berat)
    try:
        hist = get_history()
        hist_summary = {"periods": hist["periods"], "latest": hist["latest"], "count": len(hist["periods"])}
    except Exception:
        hist_summary = {"periods": [], "latest": None, "count": 0}
    base = {"count": len(feats), "source": str(DATA),
            "lon_range": [min(f["bounds"]["west"] for f in feats),
                          max(f["bounds"]["east"] for f in feats)] if feats else [0,0],
            "lat_range": [min(f["bounds"]["south"] for f in feats),
                          max(f["bounds"]["north"] for f in feats)] if feats else [0,0],
            "recent_cached": len(_recent),
            "history": hist_summary}
    if meta:
        base["meta"] = meta
        # expose top-level juga untuk ANNA cepat baca tanpa nested
        for k in ("generated_at","source_db","tahun_rtt","periode","counts","generator","version"):
            if k in meta:
                base[k] = meta[k]
    return base

def get_meta():
    """Meta cadangan harian untuk YOY — jangan karang, sebut generated_at."""
    feats, _ = _load()
    m = _cache.get("meta")
    if m is not None:
        return m
    _, meta = _raw_list_and_meta()
    _cache["meta"] = meta
    return meta
