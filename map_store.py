"""
Map command bridge — Fase 5 SPATIAL_MAP.

Server Python tidak bisa panggil window.__anaMap langsung (peta hidup di
browser). Jadi pola antrean:

  ANA/Hermes --POST /api/map/command--> antrean --GET /api/map/queue--> frontend
  frontend eksekusi via adapter --> POST /api/map/result --> ANA baca hasil
  frontend --POST /api/map/state--> cache --> GET /api/map/state --> ANA baca state

Semua visual-only (zoom/highlight/select). Tidak ada mutasi data persisten,
jadi tanpa konfirmasi operator. Thread-safe via satu Lock.
"""
import threading
import time

_LOCK = threading.Lock()
_STATE = {"state": None, "updated": 0.0}
_SEQ = {"n": 0}
_PENDING = []
_RESULTS = {}

# Whitelist op — harus cocok dengan method LeafletAdapter di mapControl.js,
# kecuali op spatial_* yang di-intercept map.js (bukan method _ctl).
ALLOWED_OPS = frozenset({
    "get_state", "set_view", "fit_bounds", "fit_all", "reset_view",
    "get_layers", "set_layer_visibility", "toggle_layer", "set_basemap",
    "select_feature", "get_selected", "clear_selection",
    "clear_filter", "clear_highlights", "highlight_features",
    "set_filter", "set_features", "clear_features",
    # ANA full control Toolbar atas + Panel Filter + Pencarian petak
    # (di-intercept map.js poll/_drainBusinessQueue → spatial state + reload):
    "spatial_set", "spatial_get", "spatial_search", "spatial_reload",
    # Viewport-based loading for kph_summary_map at zoom out levels:
    "load_viewport",
    # P2-3 hybrid vector tier: geometri via PMTiles, atribut via viewport:
    "set_pmtiles",
})

RESULT_TTL = 300  # detik; hasil basi dibuang


def push_command(op, args=None):
    """Enqueue op. Returns (cmd_id, error). error None bila ok."""
    op = (op or "").strip()
    if op not in ALLOWED_OPS:
        return None, f"op tidak dikenal: {op!r}. allowed: {sorted(ALLOWED_OPS)}"
    if args is not None and not isinstance(args, dict):
        return None, "args harus object"
    with _LOCK:
        _SEQ["n"] += 1
        cmd = {"id": f"m{_SEQ['n']}", "op": op,
               "args": args or {}, "at": time.time()}
        _PENDING.append(cmd)
        _gc_locked()
        return cmd["id"], None


def take_pending():
    """Frontend ambil + kosongkan antrean."""
    with _LOCK:
        out = list(_PENDING)
        _PENDING.clear()
        return out


def put_result(cmd_id, ok, payload):
    with _LOCK:
        _RESULTS[str(cmd_id)] = {"ok": bool(ok), "at": time.time(),
                                 **({"data": payload} if ok else {"error": str(payload)[:300]})}
        _gc_locked()


def get_result(cmd_id):
    with _LOCK:
        return dict(_RESULTS.get(str(cmd_id), {}))


def set_state(state):
    if not isinstance(state, dict):
        return False
    with _LOCK:
        _STATE["state"] = state
        _STATE["updated"] = time.time()
        return True


def get_state():
    with _LOCK:
        return {"state": _STATE["state"], "updated": _STATE["updated"]}


def _gc_locked():
    now = time.time()
    dead = [k for k, v in _RESULTS.items() if now - v.get("at", 0) > RESULT_TTL]
    for k in dead:
        _RESULTS.pop(k, None)
