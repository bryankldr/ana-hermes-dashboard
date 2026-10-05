"""
ANA Live -- a HUD that drives Hermes Agent.

    python3 server.py

The brain is your own Hermes Agent CLI/profile. Hermes keeps access to the same
configured tools, browser/Chrome automation, MCP servers, skills, memory, and
third-party integrations that your normal Hermes sessions have. Voice can use the
browser Web Speech API, plus server-side Edge TTS (id-ID) for voice output.
"""
import json
import mimetypes
import os
import pathlib
import secrets
import sys
import threading
import queue
import re
import time
import traceback
import webbrowser
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent
UI = ROOT / "ui"

# PMTiles reader for single tile extraction
try:
    import pmtiles.reader as pmtiles_reader
    PMTILES_AVAILABLE = True
except Exception:
    PMTILES_AVAILABLE = False

# load .env before importing anything that reads os.environ
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import commands         # noqa: E402
import runtime_gateway as runtime         # noqa: E402
import services         # noqa: E402
import map_store        # noqa: E402
import spatial_intel    # noqa: E402
import spatial_chart_store  # noqa: E402
import spatial_report_store  # noqa: E402
import terminal as ana_terminal  # noqa: E402
import voice            # noqa: E402
import sysmetrics       # noqa: E402

# SIMOGE business API -- the `simoge-business` skill in Hermes owns all SQL.
# The server resolves its scripts dir lazily and calls the skill's own entry
# points; it holds no queries of its own. No sys.path mutation at import time.
_SIMOGE_SCRIPTS = os.path.join(
    os.path.expanduser("~/.hermes/profiles/anna/skills/software-development/simoge-business/scripts")
)


# ── debug log ────────────────────────────────────────────────────
# Mode dari .env:  ANA_MODE=develop  → log nyala (default kalau tak di-set)
#                  ANA_MODE=production → log mati
# Override sekali jalan: ANA_DEBUG_MAP=1 python3 server.py
# Log satu baris per request: waktu, method, path, status, ms. Tanpa token,
# tanpa SQL, tanpa body — aman dibaca di terminal.
def _debug_on():
    mode = (os.environ.get("ANA_MODE") or "develop").strip().lower()
    flag = os.environ.get("ANA_DEBUG_MAP", os.environ.get("ANA_DEBUG", "")).strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    if flag in {"0", "false", "no", "off"}:
        return False
    return mode in {"develop", "dev", "debug", "test"}


_DEBUG_MAP = _debug_on()

# Path yang dipoll tiap-detik oleh dashboard. 200-nya tidak pernah menarik.
# (bridge 400ms, chart 2s, jobs 4s, avd 7s) tapi menutupi baris yang penting.
# Skip hanya kalau SUKSES; 401/4xx/5xx tetap logged. Request lambat (>_SLOW_MS)
# juga selalu logged apa pun path-nya — di situ masalah sebenarnya muncul.
_NOISY_OK = {
    "/api/map/queue", "/api/spatial/chart", "/api/spatial/report", "/api/jobs", "/api/missions",
    "/api/avd", "/api/token-status", "/api/sessions", "/api/voices",
    "/api/vault", "/api/projects", "/api/kanban", "/api/briefing",
    "/api/terminals", "/api/status", "/api/sysmetrics",
}
_SLOW_MS = 400.0
_LOG_FILE = ROOT / "logs" / "server.log"
_LOG_LOCK = threading.Lock()


def _log_to_file(line):
    """Salin baris penting ke logs/server.log (rotasi 2MB x3) untuk grep/tail."""
    try:
        with _LOG_LOCK:
            _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            if _LOG_FILE.exists() and _LOG_FILE.stat().st_size > 2_000_000:
                _LOG_FILE.replace(_LOG_FILE.with_suffix(".log.1"))
            with _LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


def _dlog(msg):
    """Satu baris log debug ke stderr (terminal). Tak pernah lempar."""
    if not _DEBUG_MAP:
        return
    line = f"  [map {time.strftime('%H:%M:%S')}] {msg}"
    _log_to_file(line.strip())
    try:
        sys.stderr.write(line + "\n")
    except Exception:  # noqa: BLE001
        pass


def _dlog_req(method, path, code, ms):
    """Log HANYA yang berarti: error/lama/tak-bising. Tak ada filter = bising."""
    if not _DEBUG_MAP:
        return
    if code >= 400:
        _dlog(f"{method} {path} -> {code} ({ms:.0f}ms)")
    elif ms >= _SLOW_MS:
        _dlog(f"SLOW {method} {path} -> {code} ({ms:.0f}ms)")
    elif path not in _NOISY_OK:
        _dlog(f"{method} {path} -> {code} ({ms:.0f}ms)")


def _simoge_mod(name):
    """Import a module from the simoge-business skill (Hermes owns it)."""
    import importlib
    if _SIMOGE_SCRIPTS not in sys.path:
        sys.path.insert(0, _SIMOGE_SCRIPTS)
    return importlib.import_module(name)


def _simoge_templates():
    try:
        T = _simoge_mod("simoge_db").T
        return {"templates": sorted(T.keys())}
    except Exception as e:
        return {"error": str(e)}


def _simoge_query(template, params):
    import decimal, datetime
    def _coerce(o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        if isinstance(o, bytes):
            return o.decode("utf-8", errors="replace")
        raise TypeError(f"Cannot serialize {type(o)}")
    call_simoge_tool = _simoge_mod("ana_simoge_tool").call_simoge_tool
    result = call_simoge_tool(template, params)
    return json.loads(json.dumps(result, default=_coerce))


def _simoge_features(result):
    """Rows with a polygon or centroid column -> GeoJSON FeatureCollection features.
    
    Supports:
    - 'polygon' (Polygon/MultiPolygon) for full petak templates
    - 'centroid' (Point) for kph_summary_map aggregated templates
    """
    feats = []
    for r in result.get("rows") or []:
        # Try polygon first (full petak templates)
        geom = r.get("polygon")
        geom_type = "polygon"
        if not geom:
            # Fallback to centroid (kph_summary_map)
            geom = r.get("centroid")
            geom_type = "centroid"
        if not geom:
            continue
        try:
            g = json.loads(geom) if isinstance(geom, str) else geom
        except (ValueError, TypeError):
            continue
        # Build properties excluding geometry columns
        props = {}
        for k, v in r.items():
            if k in ("polygon", "centroid"):
                continue
            props[k] = "" if v is None else str(v)
        # Add a hint about geometry type for styling if needed
        props["_geom_type"] = geom_type
        # Stable feature id untuk diff inkremental client (mapControl dedup by id,
        # map.js incremental {full:false}). Polygon: nomor_petak unik per baris.
        # Agregat (kph_summary_map): level+kode wilayah agar centroid stabil.
        _fid = (str(r.get("nomor_petak") or "").strip()
                or "|".join(str(r.get(k) or "") for k in
                            ("aggregated_level", "kode_bkph", "kode_kph", "kode_divre"))
                or str(len(feats)))
        feats.append({
            "type": "Feature",
            "id": _fid,
            "properties": props,
            "geometry": g,
        })
    return feats


# Template → (business, kategori) agar show_on_map konvergen ke panel state.
# Tanpa ini: push mentah set_features ditimpa reloadBusiness() panel (wipe),
# KPI/legend/insight desync. Dengan ini: server dorong spatial_set sesudah
# set_features → panel reload sendiri → hasil akhir = subset sama.
_TEMPLATE_SPATIAL = {
    "petak_bongkor_map": ("petak", "bongkor"),
    "petak_efektivitas_map": ("petak", "semua"),
    "petak_multi_penyadap_map": ("petak", "multi_penyadap"),
    "idle_petak_map": ("petak", "idle"),
    "aktivitas_petak_map": ("aktivitas", "semua"),
    "aktivitas_top_petak": ("aktivitas", "semua"),
    "rkap_map": ("produksi", "semua"),
    "matriks_map": ("matriks", "semua"),
    "kph_summary_map": ("petak", "ringkasan"),
}
# warna subset → kategori (hanya efektivitas; template lain abaikan warna)
_WARNA_KATEGORI = {"kuning": "kurang"}
# Tambah: aggregated_level, bounds, zoom untuk viewport query & auto-aggregation
_SPATIAL_FILTER_KEYS = ("bulan", "tahun", "periode", "divre", "kph",
                        "bkph", "rph", "tpg", "pembaharuan_ke",
                        "aggregated_level", "bounds", "zoom", "page_size")


_SPATIAL_SIG = {}
_SHOW_CACHE = {}
_SPATIAL_TTL = 3.0
# ThreadingHTTPServer = thread per koneksi; _spatial_sync + _remember/_SHOW_CACHE
# baca-tulis dari thread run & panel bersamaan → satu lock untuk ketiganya.
_SPATIAL_LOCK = threading.Lock()


def _remember(key, payload):
    """Simpan respons show_on_map TTL pendek (anti reload-loop dari panel)."""
    if not key:
        return
    now = time.monotonic()
    with _SPATIAL_LOCK:
        _SHOW_CACHE[key] = (now, payload)
        for k in [k for k, v in _SHOW_CACHE.items() if (now - v[0]) > _SPATIAL_TTL]:
            _SHOW_CACHE.pop(k, None)


def _spatial_sync(template, params, warna_only):
    """Dorong spatial_set agar panel reload ke state yang sama.

    Identik dalam _SPATIAL_TTL detik → pakai id yang ada, jangan push lagi.
    Tanpa ini panel reload → show_on_map → spatial_set → reload … tak berhenti:
    tiap putaran query MariaDB lagi (180ms) dan menggambar ulang peta.

    Warna yang tak punya kontrol panel (mis. idle_petak_map kuning) ikut
    dikirim sebagai filters.warna supaya panel query subset yang sama — kalau
    tidak, panel render seluruh petak dan menimpa subset ANA.

    Kontrak state penuh (solusi A): SEMUA kunci _SPATIAL_FILTER_KEYS selalu
    dikirim; yang absen di params dikirim "" agar panel RESET dropdown-nya.
    Tanpa ini handler panel merge di atas DOM usang (map.js _next.filters):
    turn 1 bkph=3121102 menempel di turn 2 yang tanpa filter wilayah → peta
    subset, narasi ANNA populasi penuh (split-brain).
    """
    bizkat = _TEMPLATE_SPATIAL.get(template)
    if not bizkat:
        return None  # mis. petak_with_geometry: legacy, tanpa sync
    biz, kat = bizkat
    if warna_only and template == "petak_efektivitas_map":
        kat = _WARNA_KATEGORI.get(warna_only, kat)
    filters = {}
    for k in _SPATIAL_FILTER_KEYS:
        v = params.get(k, params.get("kode_" + k, ""))
        # Kontrak penuh solusi A: absen = "" (reset eksplisit di panel),
        # bukan di-skip (skip = warisan filter turn lama menempel).
        filters[k] = "" if v is None else str(v).strip()
    if kat:
        filters["kategori"] = kat
    # warna tanpa padanan kontrol → teruskan sebagai filter (adapter baca f.warna)
    if warna_only:
        filters["warna"] = warna_only
    args = {"business": biz, "filters": filters, "template": template}
    sig = json.dumps(args, sort_keys=True, default=str)
    now = time.monotonic()
    with _SPATIAL_LOCK:
        prev = _SPATIAL_SIG.get(sig)
        if prev and (now - prev[0]) < _SPATIAL_TTL:
            return prev[1]
    cmd_id, err = map_store.push_command("spatial_set", args)
    if err:
        return None
    with _SPATIAL_LOCK:
        _SPATIAL_SIG[sig] = (now, cmd_id)
        # buang signature lama supaya dict tak tumbuh tanpa batas
        for k in [k for k, v in _SPATIAL_SIG.items() if (now - v[0]) > _SPATIAL_TTL]:
            _SPATIAL_SIG.pop(k, None)
    return cmd_id


def _simoge_show_on_map(template, params, drive_panel=True):
    """One call: query template -> GeoJSON untuk pemanggil + set state peta.

    The dashboard owns map delivery; Hermes owns SQL. ANA never hand-writes
    GeoJSON or calls urllib from a sandboxed tool.

    Dua pemanggil dengan kebutuhan berbeda:

      - drive_panel=True (ANA via show_on_map): yang penting efeknya di peta.
        Query dulu untuk knows-featured, lalu dorong `spatial_set` supaya PANEL
        yang query + render sendiri. Kalau ANA ikut push features, ada dua
        penulis: push ANA lalu panel reload menimpanya (809 vs 6) → peta
        berkedip dan hasil akhir milik panel. Jadi ANA tak pernah push.

      - drive_panel=False (panel SPATIAL MAP via loadBusinessData): jangan
        sentuh state (memaling), cukup kembalikan GeoJSON supaya panel render
        hasil query-nya sendiri.

    Optional params.warna: filter server-side ke satu warna bisnis (mis.
    'kuning' untuk "kurang efektif saja"). params.warna di-pop sebelum query
    (template fn tak kenal param itu).
    """
    params = dict(params or {})
    warna_only = str(params.pop("warna", "") or "").lower().strip()

    # Cache respons: panel reload memanggil endpoint ini lagi dengan param
    # identik; query MariaDB tak perlu diulang.
    cache_key = None
    if template in _TEMPLATE_SPATIAL:
        # drive WAJIB masuk key: respons ANA (tanpa geojson) tak boleh dilayani
        # ke panel, dan sebaliknya — satu template, dua bentuk jawaban.
        cache_key = json.dumps([template, warna_only, bool(drive_panel), params],
                               sort_keys=True, default=str)
        with _SPATIAL_LOCK:
            hit = _SHOW_CACHE.get(cache_key)
        if hit and (time.monotonic() - hit[0]) < _SPATIAL_TTL:
            return dict(hit[1], cached=True)
    else:
        cache_key = None

    result = _simoge_query(template, params)
    rows_all = result.get("rows") or []
    rows = [r for r in rows_all
            if str(r.get("warna") or "").lower().strip() == warna_only] if warna_only else rows_all
    expl = result.get("explanation") or ""
    if warna_only:
        expl += f" · filter warna={warna_only}: {len(rows)} dari {len(rows_all)}"
    feats = _simoge_features({"rows": rows})
    warna_counts = {}
    try:
        for r in rows:
            w = str(r.get("warna") or r.get("kategori") or "").lower().strip()
            if w:
                warna_counts[w] = warna_counts.get(w, 0) + 1
    except Exception:
        warna_counts = {}
    # Ringkasan ranking untuk template top (tanpa kolom warna → KPI panel
    # tak bisa hitung dari warna_counts). Panel render dari sini, bukan
    # dari kalkulasi ulang — satu sumber angka dengan explanation.
    top_summary = None
    if template == "aktivitas_top_petak":
        try:
            _king = rows[0] if rows else {}
            top_summary = {
                "n_petak": len(rows),
                "total_aktivitas": sum(int(r.get("jumlah_aktivitas") or 0) for r in rows),
                "total_foto": sum(int(r.get("jumlah_foto") or 0) for r in rows),
                "top_nomor": str(_king.get("nomor_petak") or "-"),
                "top_count": int(_king.get("jumlah_aktivitas") or 0),
                "pem": str(params.get("pembaharuan_ke") or ""),
            }
        except Exception:
            top_summary = None
    if not feats:
        return {"ok": False, "error": f"template {template} returned no geometry" + (f" (filter warna={warna_only})" if warna_only else ""),
                "row_count": len(rows_all), "features": 0}

    # ── pemanggil ANA: effects lewat state, tanpa menulis peta langsung ──
    if drive_panel and template in _TEMPLATE_SPATIAL:
        try:
            sp_id = _spatial_sync(template, params, warna_only)
            if sp_id:
                out = {"ok": True, "template": template, "row_count": len(rows),
                       "features": len(rows), "spatial_id": sp_id,
                       "delivery": "state", "explanation": expl, "params": params}
                _remember(cache_key, out)
                return out
        except Exception as e:
            expl += f" · sync gagal ({type(e).__name__}), fallback push"

    # ── pemanggil panel: kembalikan GeoJSON supaya dia render sendiri ──
    # Panel query template ANA langsung bila dikenal (mis. aktivitas_top_petak
    # dari spatial_set): resolveTemplate tak kenal template itu dan fallback
    # ke evaluasi penuh 809 — panel harus render subset yang sama, bukan semua.
    panel_template = template if template in _TEMPLATE_SPATIAL else None
    cmd_id, err = map_store.push_command("set_features", {
        "geojson": {"type": "FeatureCollection", "features": feats},
        # fit:False — panel fit SEKALI per ganti filter (first load /
        # spatial_set) di reloadBusiness. fit:True tiap reload = snapback:
        # fit_all fire moveend → _pushViewport → reload berulang, kamera user
        # dibuang kembali ke extent lama. ANNA tetap bisa fit eksplisit via
        # op fit_all / fit_bounds.
        "fit": False,
    })
    if err:
        return {"ok": False, "error": err, "features": 0, "warna_counts": warna_counts}
    out = {"ok": True, "template": panel_template or template,
           "row_count": len(rows),
           "features": len(feats), "map_id": cmd_id,
           "delivery": "push",
           "explanation": expl,
           "warna_counts": warna_counts, "params": params}
    if top_summary:
        out["top_summary"] = top_summary
    if warna_only:
        out["filter_warna"] = warna_only
        out["row_count_unfiltered"] = len(rows_all)
    return out


PORT = int(os.environ.get("ANA_PORT", "8730"))
# Bind host: "127.0.0.1" (default, localhost-only) atau "0.0.0.0" (semua interface, akses eksternal).
# Gunakan env ANA_HOST=0.0.0.0 agar bisa diakses via IP LAN.
BIND_HOST = os.environ.get("ANA_HOST", "127.0.0.1")
# Boot id — identitas proses server, BARU tiap start. Bukan rahasia: frontend
# pakainya untuk tahu token-nya basi (server restart) vs token ditolak (jahat).
# Dipakai juga `/api/token-status` yang tanpa auth, jadi tak ada cara baca token.
BOOT_ID = secrets.token_hex(4)
# Token: env wins, otherwise reuse existing file so a failed second instance
# that dies on EADDRINUSE doesn't clobber the running server's token.
_TOKEN_FILE = ROOT / ".ana_token"
if os.environ.get("ANA_TOKEN"):
    API_TOKEN = os.environ["ANA_TOKEN"]
else:
    try:
        _reuse = _TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        _reuse = ""
    API_TOKEN = _reuse if _reuse else secrets.token_urlsafe(32)
# File is written inside main() after the port guard, not at import time.
RUN_LOCK = threading.Lock()
MAX_JSON_BODY = 16 * 1024 * 1024

# The Ana persona, appended to every run. Without it, the model answers as a
# coding agent and narrates its own tooling -- which is not what you want spoken
# out loud. Edit persona.md to change how it talks.
_PERSONA_FILE = ROOT / "persona.md"
# Cache isi persona.md (6KB baca disk tiap request: persona() dipanggil tiap
# /api/run + 2x per command-matrix). Key mtime+size; edit persona.md live tetap
# kepick tanpa restart.
_PERSONA_CACHE: dict = {"key": None, "base": ""}

# ANNA Knowledge Wiki (llm-wiki) disuntik ke system prompt tiap run.
# WIKI_PATH dari .env profil anna. Cache by mtime+size; hilang/rusak =
# degradasi ke string kosong (SOUL + persona tetap jalan, wiki pasif).
_WIKI_CACHE: dict = {"key": None, "text": ""}
_WIKI_MAX_INDEX = 6000  # index.md ~7KB: cukup untuk katalog + ringkasan
_WIKI_MAX_ALIAS = 2000  # alias-wilayah.md ~1.6KB: wajib full (licin/glenmore/jatim)


def _wiki_path():
    p = (os.environ.get("WIKI_PATH") or "").strip()
    return pathlib.Path(p) if p else None


def wiki_block():
    base = _wiki_path()
    if base is None:
        return ""
    try:
        idx_f, alias_f = base / "index.md", base / "concepts" / "alias-wilayah.md"
        st = idx_f.stat()
        try:
            ast = alias_f.stat()
            key = (st.st_mtime_ns, st.st_size, ast.st_mtime_ns, ast.st_size)
        except OSError:
            key = (st.st_mtime_ns, st.st_size, None, None)
    except OSError:
        return ""
    if _WIKI_CACHE["key"] == key:
        return _WIKI_CACHE["text"]
    try:
        idx = idx_f.read_text(encoding="utf-8", errors="replace")[:_WIKI_MAX_INDEX]
    except OSError:
        return ""
    try:
        alias = alias_f.read_text(encoding="utf-8", errors="replace")[:_WIKI_MAX_ALIAS]
    except OSError:
        alias = ""
    parts = ["## ANNA Knowledge Wiki (kompas semantik — bukan sumber angka)",
             idx.strip()]
    if alias.strip():
        parts.append("## Alias wilayah (verbatim, filter resmi)\n" + alias.strip())
    parts.append("Aturan pakai wiki: semantik/ontology/alias dari sini; "
                 "angka/fakta selalu dari Business Data Engine. "
                 "Tak ada SQL langsung — larangan tetap.")
    text = "\n\n".join(parts)
    _WIKI_CACHE.update(key=key, text=text)
    return text


MODE_FILE = ROOT / ".ana_mode"
def _load_mode():
    try:
        v = MODE_FILE.read_text().strip().lower()
        # Default assists, not coding: mode asisten is the safe default (jawaban
        # ringkas tanpa markdown/code, cocok untuk TTS), so a corrupt or unknown
        # value must never silently flip the HUD into a markdown-heavy agent.
        return v if v in ("asisten","coding") else "asisten"
    except OSError:
        env = (os.environ.get("ANA_MODE") or "asisten").strip().lower()
        return env if env in ("asisten","coding") else "asisten"
MODE = {"v": _load_mode()}


def _clamp(value, lo, hi, default):
    """Terminal dimensions arrive as JSON, so they can be a string, a list or
    None. int() raises on any of those and would kill the request thread, so
    anything unusable falls back to the caller's default."""
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def get_mode(): return MODE["v"]
def set_mode(v):
    v = (v or "").strip().lower()
    if v not in ("asisten","coding"): raise ValueError("mode must be asisten or coding")
    MODE["v"] = v
    try: MODE_FILE.write_text(v)
    except OSError: pass
    return v

# One continuing Hermes conversation until the user hits /new.
# Extended with metadata for cross-tab sync and TTL.
# Diakses dari banyak thread (ThreadingHTTPServer tanpa batas thread):
# _stream_run tulis, /api/session tulis, /api/status baca — lindungi semua.
SESSION: dict[str, str | None | dict | None] = {
    "id": None,
    "meta": None,  # {"title": str, "created": float, "message_count": int} | None
}
_SESSION_LOCK = threading.Lock()
SESSION_TTL_SEC = int(os.environ.get("ANA_SESSION_TTL", "3600"))  # 1h default

# Persist session id+meta ke disk agar survive restart server.
# Tanpa ini SESSION in-memory hilang tiap restart dan chat mulai fresh
# padahal Hermes masih punya history-nya.
_SESSION_FILE = ROOT / ".ana_session"

def _session_save():
    try:
        sid, meta = SESSION.get("id"), SESSION.get("meta")
        if sid and runtime.valid_session(sid):
            _SESSION_FILE.write_text(
                json.dumps({"id": sid, "meta": meta or {}}), encoding="utf-8")
        else:
            try:
                _SESSION_FILE.unlink(missing_ok=True)
            except OSError:
                pass
    except OSError:
        pass


def _session_restore():
    try:
        d = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(d, dict) and runtime.valid_session(d.get("id")):
        meta = d.get("meta") if isinstance(d.get("meta"), dict) else None
        if isinstance(meta, dict) and not isinstance(meta.get("created"), (int, float)):
            meta["created"] = time.time()  # file lama tanpa stamp: mulai TTL dari restore
        with _SESSION_LOCK:
            SESSION["id"] = str(d["id"])
            SESSION["meta"] = meta

def _session_expired() -> bool:
    with _SESSION_LOCK:
        meta = SESSION.get("meta")
    if not isinstance(meta, dict) or "created" not in meta:
        return False
    created = meta.get("created")
    if not isinstance(created, (int, float)):
        return False
    return (time.time() - created) > SESSION_TTL_SEC


def _clear_session():
    with _SESSION_LOCK:
        SESSION["id"] = None
        SESSION["meta"] = None
    _session_save()


def _session_get():
    with _SESSION_LOCK:
        return SESSION.get("id"), SESSION.get("meta")


def _session_set(sid, meta=None):
    with _SESSION_LOCK:
        SESSION["id"] = sid
        if meta is not None:
            SESSION["meta"] = meta
    _session_save()


def _session_bump_count():
    # Tiap run selesai = aktivitas: refresh TTL agar chat yang hidup tidak
    # diputus tiap 1 jam. Session idle tetap expired via _session_expired.
    with _SESSION_LOCK:
        meta = SESSION.get("meta")
        if isinstance(meta, dict):
            meta["message_count"] = meta.get("message_count", 0) + 1
            meta["created"] = time.time()
    _session_save()

def persona():
    try:
        st = _PERSONA_FILE.stat()
        key = (st.st_mtime_ns, st.st_size)
    except OSError:
        key = None
    if key is not None and _PERSONA_CACHE["key"] == key:
        base = _PERSONA_CACHE["base"]
    else:
        try:
            base = _PERSONA_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            base = ""
        if key is not None:
            _PERSONA_CACHE.update(key=key, base=base)
    extra = commands.context_block()
    wiki = wiki_block()
    mode = get_mode()
    # Nama yang diucapkan mengikuti voice aktif: Gadis -> ANNA, Ardi -> MAX.
    # Identitas sistem tetap ANNA (profil Hermes tidak diubah); yang varies hanya
    # nama yang keluar dari mulut TTS, jadi memilih Ardi tidak mengubah sistem.
    agent = voice.agent_name()
    name_rule = ('- Nama yang boleh diucapkan untuk mode suara ini: ' + agent
                 + '. Pakai nama itu kalau diminta menyebut nama; jangan sebut nama lain.')
    base = base.replace('You are ANNA \u2014', 'You are ' + agent + ' \u2014', 1)
    # Sisipkan sebagai baris baru, bukan replace: persona.md tidak boleh
    # memegang nama agent (nama ikut voice), hanya aturan yang disimpan di server.
    anchor = '### Mode asisten'
    if anchor in base:
        base = base.replace(anchor, anchor + '\n' + name_rule, 1)
    else:
        base = name_rule + '\n' + base
    overlay = "[MODE: asisten] Jawab 1-2 kalimat, no markdown/code/tabel, untuk TTS." if mode=="asisten" else "[MODE: coding] Mode agen koding: boleh markdown, code block, tabel, path exact. Jelaskan lengkap & verifikasi pakai output real."
    return "\n\n".join(x for x in (base, overlay, wiki, extra) if x)



class QuietServer(ThreadingHTTPServer):
    # Bungkam traceback noise dari client yang disconnect tiba-tiba
    # (scanner LAN, browser close tab) — bukan error server.
    def handle_error(self, request, client_address):
        import sys as _sys
        exc = _sys.exc_info()[1]
        if isinstance(exc, (ConnectionResetError, BrokenPipeError, OSError)):
            return  # client disconnect tiba-tiba — bukan error server
        super().handle_error(request, client_address)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # With HTTP/1.1 keep-alive and no socket timeout, a client that opens a
    # connection and then goes quiet pins its thread for the life of the
    # process, and ThreadingHTTPServer spawns one thread per connection without
    # a ceiling. 30s of silence is far longer than any real request here needs
    # and lets the server reap the thread itself.
    timeout = 30

    def log_message(self, fmt, *args):
        if os.environ.get("ANA_VERBOSE"):
            sys.stderr.write("  " + (fmt % args) + "\n")

    # ── helpers ──────────────────────────────────────────────
    def _json(self, body, code=200):
        data = json.dumps(body).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        # debug: satu baris per respons, TAPI hanya yang berarti (error/lama/non-bising)
        try:
            ms = (time.time() - getattr(self, "_t0", time.time())) * 1000
            _dlog_req(self.command, urlparse(self.path).path, code, ms)
        except Exception:  # noqa: BLE001
            pass

    def _bytes(self, data, ctype, code=200):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _serve_pmtiles(self):
        # PMTiles v3 via range request (P2-2). Statis, tanpa Martin/tippecanoe.
        # Client (protomaps-leaflet) kirim Range: bytes=a-b; jawab 206 +
        # Content-Range, atau 200 penuh bila tanpa Range.
        # NEW: Jika query param z,x,y diberikan -> ekstrak single MVT tile (bukan byte range).
        f = ROOT / "tiles" / "petak.pmtiles"
        if not f.is_file():
            return self._json({"error": "petak.pmtiles belum dibangun"}, 404)

        # Check for z/x/y query params (protomaps-leaflet tile request)
        qs = parse_qs(urlparse(self.path).query)
        z_str = qs.get('z', [None])[0]
        x_str = qs.get('x', [None])[0]
        y_str = qs.get('y', [None])[0]

        # If z/x/y provided, extract single MVT tile using pmtiles.reader
        if z_str is not None and x_str is not None and y_str is not None:
            if not PMTILES_AVAILABLE:
                return self._json({"error": "pmtiles.reader tidak tersedia"}, 500)
            try:
                z = int(z_str)
                x = int(x_str)
                y = int(y_str)
                with f.open("rb") as fh:
                    reader = pmtiles_reader.Reader(pmtiles_reader.MmapSource(fh))
                    tile_data = reader.get(z, x, y)
                if tile_data is None:
                    # Tile exists but empty - return 204 No Content (valid per PMTiles spec)
                    self.send_response(204)
                    self.send_header("Content-Type", "application/vnd.mapbox-vector-tile")
                    self.send_header("Content-Encoding", "gzip")
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    return
                # Return single MVT tile (gzipped)
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.mapbox-vector-tile")
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(tile_data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(tile_data)
                return
            except (ValueError, OSError) as e:
                return self._json({"error": f"tile extract: {str(e)[:200]}"}, 400)

        # Otherwise serve full file with Range support (original behavior)
        try:
            size = f.stat().st_size
            rng = (self.headers.get("Range") or "").strip()
            start, end = 0, size - 1
            code = 200
            if rng.startswith("bytes="):
                spec = rng[len("bytes="):].split(",", 1)[0].strip()
                if spec.startswith("-"):
                    start = max(0, size - int(spec[1:] or 0))
                else:
                    a, _, b = spec.partition("-")
                    start = int(a or 0)
                    end = int(b) if b else size - 1
                if start >= size:
                    # RFC 7233: range tak satisfiable -> 416. Melayani byte
                    # terakhir dengan 206 berarti klien baca data salah tanpa error.
                    try:
                        self.send_response(416)
                        self.send_header("Content-Range", f"bytes */{size}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                    return
                start = max(0, min(start, size - 1))
                end = max(start, min(end, size - 1))
                code = 206
            with f.open("rb") as fh:
                fh.seek(start)
                data = fh.read(end - start + 1)
            try:
                self.send_response(code)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                if code == 206:
                    self.send_header("Content-Range",
                                     f"bytes {start}-{end}/{size}")
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
        except (ValueError, OSError) as e:
            return self._json({"error": str(e)[:200]}, 400)

    def _rebuild_pmtiles(self):
        """Rebuild petak.pmtiles full chain: export NDJSON dari DB lalu build.
        Export gagal -> fallback build dari NDJSON lama (PMTiles kemarin tetap
        lebih baik daripada 404)."""
        import subprocess
        import sys
        out = {"export": None, "build": None, "fallback": False}
        try:
            exp = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "export_petak.py"),
                 "--tahun", "2026", "--out", "tiles/petak.ndjson"],
                cwd=str(ROOT), capture_output=True, text=True, timeout=180,
            )
            try:
                out["export"] = json.loads(exp.stdout.strip().splitlines()[-1])
            except Exception:
                out["export"] = {"ok": exp.returncode == 0,
                                 "tail": (exp.stdout + exp.stderr)[-500:]}
            if exp.returncode != 0:
                out["fallback"] = True  # DB down: pakai NDJSON kemarin
        except Exception as e:                        # noqa: BLE001
            out["export"] = {"ok": False, "error": str(e)[:200]}
            out["fallback"] = True
        script = ROOT / "scripts" / "build_pmtiles.py"
        if not script.is_file():
            return self._json({"error": "build_pmtiles.py not found"}, 500)
        try:
            result = subprocess.run(
                [sys.executable, str(script)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                out["build"] = {"ok": False,
                                "stderr": result.stderr[-500:],
                                "stdout": result.stdout[-500:]}
                return self._json({**out, "error": "build failed"}, 500)
            try:
                output = json.loads(result.stdout.strip().splitlines()[-1])
            except Exception:
                output = {"ok": True, "stdout": result.stdout.strip()[-500:]}
            out["build"] = output
            return self._json(out)
        except subprocess.TimeoutExpired:
            return self._json({**out, "error": "build timeout (>120s)"}, 500)
        except Exception as e:                        # noqa: BLE001
            return self._json({**out, "error": f"rebuild: {str(e)[:200]}"}, 500)

    def _tiles_status(self):
        """Status PMTiles/NDJSON/cron untuk modal pengaturan UI (read-only)."""
        import subprocess
        st = {}
        for name in ("tiles/petak.pmtiles", "tiles/petak.ndjson"):
            f = ROOT / name
            try:
                s = f.stat()
                st[name.split("/")[1]] = {"exists": True, "bytes": s.st_size,
                                          "mtime": s.st_mtime}
            except OSError:
                st[name.split("/")[1]] = {"exists": False}
        try:
            nd = ROOT / "tiles" / "petak.ndjson"
            if nd.is_file():
                with nd.open(encoding="utf-8") as fh:
                    st["petak.ndjson"]["lines"] = sum(1 for _ in fh)
        except OSError:
            pass
        try:
            cr = subprocess.run(["crontab", "-l"], capture_output=True,
                                text=True, timeout=10)
            st["cron"] = [ln for ln in (cr.stdout or "").splitlines()
                          if "ana-hermes-dashboard" in ln and ln.strip()
                          and not ln.strip().startswith("#")]
        except Exception as e:                        # noqa: BLE001
            st["cron"] = []
            st["cron_error"] = str(e)[:120]
        try:
            lg = ROOT / "logs" / "refresh_petak.log"
            if lg.is_file():
                with lg.open(encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
                st["log_tail"] = "".join(lines[-8:])[-1200:]
            else:
                st["log_tail"] = "(belum ada log)"
        except OSError as e:
            st["log_tail"] = f"(log tak terbaca: {e})"
        return self._json({"ok": True, **st})

    # ── P2-4 cron rebuild harian (dikelola dari UI) ──
    _CRON_MARKER = "ana-pmtiles-daily"

    def _cron_read(self):
        """Baca crontab user. Return (lines, error). Tak ada crontab -> ([], None)."""
        import subprocess
        try:
            cr = subprocess.run(["crontab", "-l"], capture_output=True,
                                text=True, timeout=10)
            if cr.returncode != 0:
                if "no crontab" in (cr.stderr or "").lower():
                    return [], None
                return [], (cr.stderr or "").strip()[:120]
            return (cr.stdout or "").splitlines(), None
        except Exception as e:                        # noqa: BLE001
            return [], str(e)[:120]

    def _cron_write(self, lines):
        import subprocess
        data = "\n".join(lines).rstrip("\n") + "\n"
        wr = subprocess.run(["crontab", "-"], input=data, capture_output=True,
                            text=True, timeout=10)
        if wr.returncode != 0:
            return (wr.stderr or "").strip()[:200]
        return None

    def _tiles_cron(self, action, schedule=""):
        """status|enable|disable baris cron rebuild harian.

        Hanya baris ber-marker ana-pmtiles-daily yang disentuh; cron lain
        milik user tak diganggu. Default jadwal 10 6 * * * (06:10 WIB).
        """
        import re as _re
        sched = (schedule or "").strip() or "10 6 * * *"
        lines, err = self._cron_read()
        if err:
            return self._json({"ok": False, "error": f"crontab -l: {err}"}, 500)
        mine = [ln for ln in lines if self._CRON_MARKER in ln]
        others = [ln for ln in lines if self._CRON_MARKER not in ln]
        if action == "status":
            return self._json({"ok": True, "enabled": bool(mine),
                               "lines": mine, "cron_error": err})
        if action not in ("enable", "disable"):
            return self._json({"error": "action harus status|enable|disable"}, 400)
        if action == "enable":
            # validasi jadwal minimal: 5 field cron
            parts = sched.split()
            if len(parts) != 5 or not _re.match(
                    r"^[\d\*,/\- ]+$", sched):
                return self._json({"error": f"jadwal tak valid: {sched!r} "
                                            "(butuh 5 field, mis. '10 6 * * *')"}, 400)
            script = ROOT / "scripts" / "rebuild_tiles_daily.sh"
            logf = ROOT / "logs" / "refresh_petak.log"
            entry = (f"{sched} bash {script} >> {logf} 2>&1 "
                     f"# {self._CRON_MARKER}")
            werr = self._cron_write(others + [entry])
            if werr:
                return self._json({"ok": False, "error": f"crontab -: {werr}"}, 500)
            return self._json({"ok": True, "enabled": True, "lines": [entry]})
        # disable: buang hanya baris marker
        werr = self._cron_write(others)
        if werr:
            return self._json({"ok": False, "error": f"crontab -: {werr}"}, 500)
        return self._json({"ok": True, "enabled": False, "lines": []})

    def _read(self, limit):
        n = int(self.headers.get("Content-Length", 0))
        if n < 0 or n > limit:
            raise ValueError(f"request body exceeds {limit} bytes")
        return self.rfile.read(n) if n else b""

    def _host_ok(self):
        host = (self.headers.get("Host", "") or "").strip()
        if not host:
            return False
        # Localhost-only mode: strict allowlist (anti DNS-rebinding).
        if BIND_HOST == "127.0.0.1":
            return host in {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
        # External mode (0.0.0.0 / IP spesifik): Host header berisi IP LAN
        # client (mis. 192.168.1.7:8730), jadi terima host apa pun dengan port benar.
        return host.endswith(f":{PORT}")

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        if not origin:
            return False
        # Localhost-only mode: strict.
        if BIND_HOST == "127.0.0.1":
            return origin in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
        # External mode: terima origin apa pun dengan port benar (http/https).
        # Proteksi utama tetap X-Ana-Token; origin check hanya layer tambahan.
        try:
            o = urlparse(origin)
            return o.port == PORT and o.scheme in {"http", "https"}
        except (ValueError, TypeError):
            return False

    def _token_ok(self):
        supplied = self.headers.get("X-Ana-Token", "")
        if supplied and secrets.compare_digest(supplied, API_TOKEN):
            return True
        # Query token only for GET streaming where headers cannot be set (still localhost-only)
        path_only = urlparse(self.path).path
        if self.command == "GET" and (path_only == "/api/terminal-stream"
                or path_only == "/api/tiles/petak.pmtiles"
                or path_only == "/api/tiles/rebuild"
                or path_only.startswith("/api/aktivitas/photo/")):
            try:
                qs = parse_qs(urlparse(self.path).query)
                qtoken = (qs.get("token", [""])[0] or qs.get("t", [""])[0] or "").strip()
                if qtoken and secrets.compare_digest(qtoken, API_TOKEN):
                    return True
            except Exception:
                pass
        return False

    def _unauth(self):
        # 401 selalu bawa boot id — pembeda "token basi" (server restart, frontend
        # perlu reload) vs "token salah" (tetap tolak diam). Boot id bukan rahasia:
        # hanya 8 hex acak, tidak pernah jadi cara bypass token.
        _dlog(f"401 {self.command} {urlparse(self.path).path} (token salah/basi)")
        return self._json({"error": "unauthorized", "boot": BOOT_ID}, 401)

    # ── GET ──────────────────────────────────────────────────
    def do_GET(self):
        self._t0 = time.time()
        if not self._host_ok():
            return self._json({"error": "invalid host"}, 403)
        p = urlparse(self.path).path
        # Tanpa auth dan TANPA menyentuh token: hanya sinyal "server ini proses
        # yang mana". Frontend poll ini; boot berubah = server restart = token
        # meta di HTML lama sudah basi → reload. Tidak ada cara baca token dari
        # endpoint ini karena respons tak pernah memuat API_TOKEN.
        if p == "/api/token-status":
            return self._json({"boot": BOOT_ID})
        if p in ("/api/status", "/api/voices", "/api/mode"):
            # Bocorkan workdir/profile/model/daftar tools ke LAN tanpa token —
            # kunci ketiganya. Frontend selalu kirim X-Ana-Token (api.headers()),
            # dan flow restart tetap jalan: 401 dari server baru (token baru)
            # memicu reload via `s.error` di main.js. token-status tetap publik
            # (deteksi restart tanpa token).
            if not self._token_ok():
                return self._unauth()
        if p == "/api/status":
            return self._json(dict(
                runtime=runtime.runtime_kind(),
                permission=runtime.PERMISSION,
                profile=runtime.PROFILE,
                source=runtime.SOURCE,
                workdir=runtime.WORKDIR,
                model=runtime.MODEL or "Hermes default",
                tools=runtime.hermes_tools_snapshot(),
                browser_stt=True,
                browser_tts=True,
                voice_mode="edge",
                voice_id=voice.voice_id(),
                stt="browser",
                tts="edge",
                session=_session_get()[0]))
        if p == "/api/voices":
            cur = voice.voice_id()
            return self._json(dict(current=cur, agent_name=voice.agent_name(cur), available=voice.available(), voices=voice.curated_voices()))
        if p == "/api/mode":
            return self._json(dict(mode=get_mode()))
        if p == "/api/sysmetrics":
            if not self._token_ok():
                return self._unauth()
            # AI dial = status agen (busy/idle) plus jumlah job, bukan
            # persentase tebakan: tak ada counter context token di API mana pun,
            # jadi angka 0-100 akan jadi fiksi.
            m = sysmetrics.snapshot()
            running = commands.jobs_snapshot()
            m["ai"] = 100.0 if any(j.get("status") == "running" for j in running) else 0.0
            m["jobs"] = len(running)
            return self._json(m)
        if p == "/api/jobs":
            if not self._token_ok():
                return self._unauth()
            # finished background missions, reported once each
            return self._json(dict(done=commands.take_finished(),
                                   running=[j for j in commands.jobs_snapshot()
                                            if j["status"] == "running"]))
        if p == "/api/terminals":
            if not self._token_ok():
                return self._unauth()
            with ana_terminal._LOCK:
                ana_terminal._cleanup_locked()
                sessions = {
                    sid: {"cols": t.cols, "rows": t.rows, "alive": t.alive,
                          "created_at": getattr(t, "created_at", 0),
                          "ttl": getattr(t, "ttl", 3600)}
                    for sid, t in ana_terminal._SESSIONS.items()
                }
            return self._json({"terminals": sessions, "count": len(sessions)})

        if p == "/api/projects":
            if not self._token_ok():
                return self._unauth()
            return self._json(services.scan_projects(runtime.WORKDIR))
        if p == "/api/briefing":
            if not self._token_ok():
                return self._unauth()
            return self._json(services.load_briefing())
        if p == "/api/session/transcript":
            if not self._token_ok():
                return self._unauth()
            q = parse_qs(urlparse(self.path).query)
            sid = (q.get("session_id") or [""])[0].strip()
            if not runtime.valid_session(sid):
                return self._json({"messages": [], "error": "session_id tidak valid"}, 400)
            return self._json(services.session_transcript(
                runtime._hermes_base(), runtime.WORKDIR, sid))
        if p == "/api/sessions":
            if not self._token_ok():
                return self._unauth()
            return self._json(services.list_sessions(
                runtime._hermes_base(), runtime.WORKDIR, runtime.valid_session, _session_get()[0]))
        if p == "/api/vault":
            if not self._token_ok():
                return self._unauth()
            return self._json(services.vault_status())
        if p == "/api/avd":
            if not self._token_ok():
                return self._unauth()
            return self._json(services.avd_status())
        if p == "/api/missions":
            if not self._token_ok():
                return self._unauth()
            try:
                d = commands.load()
                tasks = d.get("tasks", [])[-20:]
                missions = d.get("missions", [])[-20:]
                return self._json({"tasks": tasks, "missions": missions, "goal": d.get("goal","")})
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 500)
        # ── spatial map bridge (Fase 5) ──────────────────────
        # Browser satu-satunya pemilik peta (window.__anaMap). ANA baca state
        # terakhir yang di-push frontend, dan kirim perintah via antrean.
        # Pola sama seperti /api/layout dan /api/terminals: plain JSON, token-gated.
        if p == "/api/map/state":
            if not self._token_ok():
                return self._unauth()
            return self._json(map_store.get_state())
        if p == "/api/map/queue":
            if not self._token_ok():
                return self._unauth()
            return self._json({"commands": map_store.take_pending()})
        if p == "/api/map/result":
            cmd_id = ""
            try:
                qs = parse_qs(urlparse(self.path).query)
                cmd_id = (qs.get("id", [""])[0] or "").strip()
            except Exception:
                pass
            if not self._token_ok():
                return self._unauth()
            if not cmd_id:
                return self._json({"error": "id required"}, 400)
            return self._json(map_store.get_result(cmd_id))
        if p == "/api/spatial/chart":
            if not self._token_ok():
                return self._unauth()
            return self._json(dict(ok=True, **spatial_chart_store.get_state()))
        if p == "/api/spatial/report":
            if not self._token_ok():
                return self._unauth()
            return self._json(dict(ok=True, **spatial_report_store.get_state()))
        if p.startswith("/api/aktivitas/photo/"):
            # query ?token= allowed so <img> works like terminal-stream
            if not self._token_ok():
                try:
                    _qs = parse_qs(urlparse(self.path).query)
                    _qt = (_qs.get("token",[""])[0] or _qs.get("t",[""])[0] or "").strip()
                    if _qt and secrets.compare_digest(_qt, API_TOKEN):
                        pass
                    else:
                        return self._unauth()
                except Exception:
                    return self._unauth()
            import re as _re
            fid = p.rsplit("/",1)[-1].strip().split("?")[0]
            if not _re.match(r"^[0-9a-fA-F-]{8,36}$", fid):
                return self._json({"error": "bad id"}, 400)
            try:
                mod = _simoge_mod("simoge_db")
                r = mod.q("SELECT id, filename_disk, storage, type, filesize FROM directus_files WHERE id=%s", (fid,))
                rows = r.get("rows") or []
                if not rows:
                    return self._json({"error": "file not found"}, 404)
                row = rows[0]
                import pathlib as _pl
                data = None
                ctype = (row.get("type") or "image/jpeg")
                if ctype == "application/octet-stream":
                    ctype = "image/jpeg"
                for base in [str(ROOT / "uploads"), "/mnt/data/direktus/uploads",
                             "/mnt/data/direktusBWB/uploads",
                             "/var/lib/directus/uploads", "/uploads"]:
                    cand = _pl.Path(base) / (row.get("filename_disk") or "")
                    if cand.is_file():
                        data = cand.read_bytes()
                        break
                if data is None:
                    return self._json({"ok": False, "error": "file bytes not available in sandbox", "meta": {"id": row["id"], "filename_disk": row["filename_disk"], "storage": row["storage"]}}, 404)
                return self._bytes(data, ctype)
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 500)
        if p == "/api/tiles/petak.pmtiles":
            # Range fetch dari protomaps-leaflet tak bisa set header —
            # izinkan ?token= seperti /api/aktivitas/photo.
            if not self._token_ok():
                try:
                    _qs = parse_qs(urlparse(self.path).query)
                    _qt = (_qs.get("token",[""])[0] or _qs.get("t",[""])[0] or "").strip()
                    if _qt and secrets.compare_digest(_qt, API_TOKEN):
                        pass
                    else:
                        return self._unauth()
                except Exception:
                    return self._unauth()
            return self._serve_pmtiles()
        if p == "/api/tiles/rebuild":
            if not self._token_ok():
                return self._unauth()
            return self._rebuild_pmtiles()
        if p == "/api/tiles/status":
            if not self._token_ok():
                return self._unauth()
            return self._tiles_status()
        if p == "/api/layout":
            if not self._token_ok():
                return self._unauth()
            layout_file = ROOT / "layout.json"
            if layout_file.exists():
                try:
                    return self._json(json.loads(layout_file.read_text()))
                except Exception as e:
                    return self._json({"error": str(e)}, 500)
            return self._json({"locked": True, "layouts": {}})
        if p == "/api/terminal-stream":
            if not self._token_ok():
                return self._unauth()
            qs = parse_qs(urlparse(self.path).query)
            tid = (qs.get("id", [""])[0] or "").strip()
            return self._terminal_stream(tid)
        rel = "index.html" if p == "/" else p.lstrip("/")
        # A plain startswith() check passes for "../ui_secret" and
        # "../uix/anything" because there is no separator between the prefix
        # and the attacker-controlled part. relative_to() is exact.
        try:
            f = (UI / rel).resolve()
            f.relative_to(UI.resolve())
        except (ValueError, OSError):
            return self._bytes(b"not found", "text/plain", 404)
        if not f.is_file():
            return self._bytes(b"not found", "text/plain", 404)
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        data = f.read_bytes()
        if rel == "index.html":
            data = data.replace(b"__ANA_TOKEN__", API_TOKEN.encode())
        return self._bytes(data, ctype)

    # ── terminal stream (GET long-poll) ──────────────
    def _terminal_stream(self, tid):
        t = ana_terminal.get(tid)
        if not t:
            return self._json({"error": "terminal not found"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            while t.alive:
                try:
                    data = t.queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if not data:
                    continue
                self.wfile.write(data)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ── POST ─────────────────────────────────────────
    def do_POST(self):
        self._t0 = time.time()
        p = urlparse(self.path).path
        if not self._host_ok() or not self._origin_ok():
            return self._json({"error": "request origin rejected"}, 403)
        if not self._token_ok():
            return self._unauth()
        ctype = self.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if p in {"/api/run", "/api/speak", "/api/new", "/api/cancel"} and ctype != "application/json":
            return self._json({"error": "application/json required"}, 415)
        try:
            raw = self._read(MAX_JSON_BODY)
        except (TypeError, ValueError):
            return self._json({"error": "request body too large"}, 413)
        # Parse once, for every JSON endpoint. Valid JSON that is not an object
        # (a bare string, number or list) used to reach `.get()` outside the
        # try below, so the handler thread died and the client saw a closed
        # socket with no status line at all instead of a 400.
        if ctype == "application/json":
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            if not isinstance(body, dict):
                return self._json({"error": "body must be a JSON object"}, 400)
        else:
            body = {}

        if p == "/api/layout":
            try:
                layout_file = ROOT / "layout.json"
                # validate: layouts must be dict, each entry is dict
                layouts = body.get("layouts", {})
                if not isinstance(layouts, dict):
                    return self._json({"error": "layouts must be dict"}, 400)
                for k, v in layouts.items():
                    if not isinstance(k, str) or not isinstance(v, dict):
                        return self._json({"error": "invalid layout entry"}, 400)
                data = {"locked": bool(body.get("locked", True)), "layouts": layouts, "disabled": body.get("disabled", [])}
                layout_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                return self._json(data)
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 500)

        # ── SIMOGE Business API ──────────────────────────────
        if p == "/api/simoge/templates":
            return self._json(_simoge_templates())
        if p == "/api/simoge/query":
            template = (body.get("template") or "").strip()
            if not template:
                return self._json({"error": "template required"}, 400)
            params = body.get("params", {})
            if not isinstance(params, dict):
                return self._json({"error": "params must be object"}, 400)
            try:
                return self._json(_simoge_query(template, params))
            except Exception as e:
                _dlog(f"simoge/query {template} ERROR {type(e).__name__}: {str(e)[:160]}")
                if _DEBUG_MAP:
                    traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/simoge/show_on_map":
            template = (body.get("template") or "petak_with_geometry").strip()
            params = body.get("params", {})
            if not isinstance(params, dict):
                return self._json({"error": "params must be object"}, 400)
            try:
                # drive=True  → pemanggil ANA: efek lewat `spatial_set`, server
                #   tak push GeoJSON (satu penulis peta = panel).
                # drive=False → pemanggil panel: server tak sentuh state, cuma
                #   kembalikan GeoJSON hasil query-nya.
                # Default True: panel selalu kirim drive:false eksplisit
                #   (businessAdapter.loadBusinessData), jadi aman. Default False
                #   bikin show_on_map ANA (tanpa flag) jatuh ke push mentah.
                data = _simoge_show_on_map(template, params,
                                           drive_panel=bool(body.get("drive", True)))
                if _DEBUG_MAP and data.get("ok"):
                    _dlog(f"show_on_map {template} feats={data.get('features')} "
                          f"drive={bool(body.get('drive', True))} "
                          + (f"warna={data.get('filter_warna')} " if data.get("filter_warna") else "")
                          + f"delivery={data.get('delivery')}")
                return self._json(data, 200 if data.get("ok") else 400)
            except Exception as e:                        # noqa: BLE001
                _dlog(f"show_on_map {template} ERROR {type(e).__name__}: {str(e)[:160]}")
                if _DEBUG_MAP:
                    traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/tiles/cron":
            # Manajemen cron rebuild harian dari UI (P2-4). Body: {action:
            # "status"|"enable"|"disable", schedule: "10 6 * * *" opsional}.
            # Marker: ana-pmtiles-daily. Hanya baris marker yang disentuh —
            # cron lain milik user tak diganggu.
            action = (body.get("action") or "status").strip().lower()
            return self._tiles_cron(action, (body.get("schedule") or "").strip())
        if p == "/api/session":
            sid = body.get("session_id")
            if sid and runtime.valid_session(sid):
                _session_set(str(sid), {"title": body.get("title", "--"), "created": time.time(), "message_count": 0})
                cur_id, cur_meta = _session_get()
                return self._json({"ok": True, "session": cur_id, "meta": cur_meta})
            _clear_session()
            return self._json({"ok": True, "session": None})

        if p == "/api/speak":
            try:
                text = (body.get("text") or "").strip()
                return self._bytes(voice.speak(text), "audio/mpeg")
            except Exception as e:                        # noqa: BLE001
                return self._json({"error": str(e)[:200]}, 503)

        if p == "/api/voice-preview":
            try:
                vid = (body.get("voice_id") or "").strip()
                txt = (body.get("text") or "Halo Pak, ini preview suara ANA.").strip()[:400]
            # hanya id Edge yang valid
                if not __import__("re").match(r"^[A-Za-z0-9_\-]{8,60}$", vid):
                    raise ValueError("voice_id tidak valid")
                try:
                    data = voice.speak_with_voice(txt, vid)
                except Exception as he:
                    return self._json({"error": str(he)[:400]}, 502)
                return self._bytes(data, "audio/mpeg")
            except Exception as e:
                return self._json({"error": str(e)[:300]}, 500)
        if p == "/api/voice":
            try:
                vid = voice.set_voice((body.get("voice_id") or "").strip())
                return self._json(dict(ok=True, current=vid, agent_name=voice.agent_name(vid)))
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 400)
        if p == "/api/mode":
            try:
                v = (body.get("mode") or "").strip().lower()
                set_mode(v)
                return self._json(dict(ok=True, mode=get_mode()))
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 400)
        if p == "/api/new":
            runtime.cancel_active()
            _clear_session()
            return self._json({"ok": True})

        if p == "/api/cancel":
            # Cancel hanya kill proses aktif — session tetap agar chat berikutnya
            # resume konteks Hermes, bukan mulai fresh diam-diam.
            stopped = runtime.cancel_active()
            return self._json({"ok": True, "stopped": stopped})
        if p == "/api/restart":
            # Restart proses sendiri: respon ok dulu, lalu exec ulang
            # server.py di thread daemon. Token+origin+host check sudah
            # lolos di atas (localhost only). Layout aman (layout.json di
            # disk); sesi chat in-memory hilang -- bisa /new lagi.
            def _restart_later():
                time.sleep(0.8)
                try:
                    sys.stdout.flush()
                    sys.stderr.flush()
                except Exception:  # noqa: BLE001
                    pass
                os.execv(sys.executable, [sys.executable, str(ROOT / "server.py")])
            threading.Thread(target=_restart_later, daemon=True).start()
            return self._json({"ok": True, "restarting": True})
        if p == "/api/avd":
            try:
                ok, info = services.avd_action(body.get("action"))
            except Exception as e:                        # noqa: BLE001
                return self._json({"error": str(e)[:200]}, 500)
            if ok is None:
                return self._json(info, 400)
            return self._json({"ok": ok, **info}, 200 if ok else 500)

        # ── terminal endpoints ──────────────────────────────
        if p == "/api/terminal":
            # A bad action, id or dimension is a client mistake, so nothing in
            # here may raise past this handler: the thread would die and the
            # client would see a closed socket rather than a status code.
            try:
                action = (body.get("action") or "").strip()
                if action == "create":
                    cols = _clamp(body.get("cols"), 20, 200, 80)
                    rows = _clamp(body.get("rows"), 5, 60, 24)
                    t = ana_terminal.create(cols, rows)
                    return self._json({"ok": True, "id": t.id, "cols": t.cols, "rows": t.rows})
                if action == "close":
                    tid = (body.get("id") or "").strip()
                    if not tid:
                        return self._json({"error": "id required"}, 400)
                    ok = ana_terminal.close(tid)
                    return self._json({"ok": ok})
                if action == "resize":
                    tid = (body.get("id") or "").strip()
                    t = ana_terminal.get(tid)
                    if not t:
                        return self._json({"error": "terminal not found"}, 404)
                    cols = _clamp(body.get("cols"), 20, 200, t.cols)
                    rows = _clamp(body.get("rows"), 5, 60, t.rows)
                    t.resize(cols, rows)
                    return self._json({"ok": True, "cols": t.cols, "rows": t.rows})
                if action == "input":
                    tid = (body.get("id") or "").strip()
                    t = ana_terminal.get(tid)
                    if not t:
                        return self._json({"error": "terminal not found"}, 404)
                    data = body.get("data", "")
                    if isinstance(data, str):
                        data = data.encode("utf-8", "surrogateescape")
                    if not isinstance(data, (bytes, bytearray)):
                        return self._json({"error": "data must be string"}, 400)
                    t.write(bytes(data))
                    return self._json({"ok": True})
                return self._json({"error": "unknown action"}, 400)
            except ValueError as e:
                return self._json({"error": str(e)[:200]}, 400)
            except OSError as e:
                # PTY creation can fail outright (no shell, fd exhaustion). The
                # terminal code closes its own fds, so this is a clean 503 and
                # not a dropped connection.
                return self._json({"error": str(e)[:200]}, 503)

        # ── map command bridge (Fase 5, POST) ────────────────
        if p == "/api/map/command":
            try:
                op = (body.get("op") or "").strip()
                args = body.get("args", {})
                cmd_id, err = map_store.push_command(op, args)
            except Exception as e:                        # noqa: BLE001
                return self._json({"error": str(e)[:200]}, 500)
            if err:
                return self._json({"error": err}, 400)
            _dlog(f"map/command {op} -> {cmd_id}")
            return self._json({"ok": True, "id": cmd_id, "op": op})
        if p == "/api/map/state":
            # Frontend push state terbaru dari adapter (canonical, satu sumber).
            if not isinstance(body.get("state"), dict):
                return self._json({"error": "state must be object"}, 400)
            map_store.set_state(body["state"])
            return self._json({"ok": True})
        if p == "/api/map/result":
            # Frontend lapor hasil eksekusi perintah antrean.
            cmd_id = str(body.get("id") or "").strip()
            if not cmd_id:
                return self._json({"error": "id required"}, 400)
            map_store.put_result(cmd_id, body.get("ok", True), body.get("data", body.get("error", "")))
            return self._json({"ok": True})
        # ── spatial intel (directive #1-20): DB=data file, bukan SQL mentah ──
        if p == "/api/spatial/resolve":
            ref = str(body.get("ref") or body.get("id") or "").strip()
            try:
                cur = (map_store.get_state().get("state") or {})
                r = spatial_intel.resolve_entity(
                    ref, selected=cur.get("selected"),
                    highlighted=cur.get("highlighted"))
            except Exception as e:                        # noqa: BLE001
                return self._json({"error": str(e)[:200], "stale": True}, 503)
            return self._json(r)
        if p == "/api/spatial/context":
            pid = str(body.get("id") or body.get("ref") or "").strip()
            if not pid:
                return self._json({"error": "id required"}, 400)
            try:
                ctx = spatial_intel.get_feature_context(pid)
            except Exception as e:
                return self._json({"error": str(e)[:200], "stale": True}, 503)
            if not ctx:
                return self._json({"error": f"petak {pid} tidak ketemu"}, 404)
            return self._json(ctx)
        if p == "/api/spatial/query":
            try:
                q = str(body.get("q") or body.get("query") or "nearby").strip().lower()
                if q in ("neighbors", "tetangga"):
                    pid = str(body.get("id") or "").strip()
                    try:
                        hit = spatial_intel.find_petak(pid)
                    except Exception as ex:
                        return self._json({"error": f"spatial tidak siap: {ex}"[:200], "stale": True}, 503)
                    if not hit:
                        return self._json({"error": f"petak {pid} tidak ketemu"}, 404)
                    return self._json({"items": spatial_intel.find_neighboring_polygons(
                        pid, limit=int(body.get("limit", 20) or 20))})
                if q in ("nearby", "radius"):
                    lat = float(body.get("lat")); lng = float(body.get("lng"))
                    rad = float(body.get("radius_m", body.get("radius", 1000)))
                    lim = int(body.get("limit", 50) or 50)
                    return self._json({"items": spatial_intel.find_within_radius(lat, lng, rad, lim)})
                if q in ("in_bounds", "bounds", "didalam", "area"):
                    b = body.get("bounds", {})
                    lim = int(body.get("limit", 200) or 200)
                    return self._json(spatial_intel.find_in_bounds(
                        {"south": float(b["south"]), "west": float(b["west"]),
                         "north": float(b["north"]), "east": float(b["east"])}, lim))
                if q in ("prefix", "grup"):
                    return self._json(spatial_intel.find_by_prefix(
                        str(body.get("prefix", "")), int(body.get("limit", 200) or 200)))
                if q in ("point", "lokasi"):
                    hit = spatial_intel.point_in_petak(float(body.get("lng")), float(body.get("lat")))
                    return self._json({"id": hit})
                if q in ("stats",):
                    try:
                        return self._json(spatial_intel.stats())
                    except Exception as ex:
                        return self._json({"count": 0, "error": str(ex)[:200], "stale": True}, 503)
                if q in ("history", "periods", "riwayat"):
                    try:
                        return self._json(spatial_intel.get_history())
                    except Exception as ex:
                        return self._json({"periods": [], "error": str(ex)[:200], "stale": True}, 503)
                if q in ("period", "periode"):
                    per = str(body.get("periode") or body.get("period") or body.get("prefix") or "").strip()
                    if not per:
                        return self._json({"error": "periode required, format YYYY-MM-P1/P2"}, 400)
                    try:
                        data = spatial_intel.get_period(per)
                    except Exception as ex:
                        return self._json({"error": str(ex)[:200], "stale": True}, 503)
                    if not data:
                        return self._json({"error": f"periode {per} tidak ketemu"}, 404)
                    # ringkas bila ?full!=true (hemat bandwidth; polygon 999)
                    if str(body.get("full", "")).lower() not in ("1","true","ya"):
                        meta = data.get("meta") or {}
                        return self._json({"ok": True, "periode": per, "meta": meta, "counts": meta.get("counts"), "features": len(data.get("features") or [])})
                    return self._json({"ok": True, "periode": per, **data})
                if q in ("diff", "selisih"):
                    a = str(body.get("from") or body.get("a") or "").strip()
                    b = str(body.get("to") or body.get("b") or "").strip()
                    if not a or not b:
                        return self._json({"error": "from & to periode required (YYYY-MM-P1/P2)"}, 400)
                    try:
                        return self._json(spatial_intel.diff_periods(a, b))
                    except Exception as ex:
                        return self._json({"error": str(ex)[:200]}, 500)
                return self._json({"error": "q harus neighbors|nearby|in_bounds|prefix|point|stats|history|period|diff"}, 400)
            except (KeyError, TypeError, ValueError) as e:
                return self._json({"error": f"args tidak valid: {e}"[:200]}, 400)
            except Exception as e:                        # noqa: BLE001
                return self._json({"error": str(e)[:200]}, 500)
        if p == "/api/spatial/history":
            try:
                return self._json(spatial_intel.get_history())
            except Exception as ex:
                return self._json({"periods": [], "error": str(ex)[:200], "stale": True}, 503)
        # ── spatial chart (panel di dalam SPATIAL MAP — full control ANA, session state) ──
        if p == "/api/spatial/chart":
            if not self._token_ok():
                return self._unauth()
            # GET already handled; POST = set chart state (visible+chart+meta)
            if not isinstance(body, dict):
                return self._json({"error": "body must be object"}, 400)
            # allow bare {chart:{}} as shorthand hide/show
            ok, err = spatial_chart_store.set_chart(body)
            if not ok:
                return self._json({"ok": False, "error": err}, 400)
            return self._json(dict(ok=True, **spatial_chart_store.get_state()))
        # ── spatial report (LAPORAN BISNIS multi halaman — full control ANA, session state) ──
        if p == "/api/spatial/report":
            if not self._token_ok():
                return self._unauth()
            if not isinstance(body, dict):
                return self._json({"error": "body must be object"}, 400)
            ok, err = spatial_report_store.set_report(body)
            if not ok:
                return self._json({"ok": False, "error": err}, 400)
            return self._json(dict(ok=True, **spatial_report_store.get_state()))
        if p == "/api/run":
            if not RUN_LOCK.acquire(blocking=False):
                return self._json({"error": "ANA is already processing a request"}, 409)
            try:
                return self._stream_run(body)
            finally:
                RUN_LOCK.release()

        return self._json({"error": "no such endpoint"}, 404)

    # ── the run: NDJSON stream of events ─────────────────────
    def _stream_run(self, payload):
        # The body was parsed and type-checked in do_POST; re-reading the raw
        # bytes here meant a bare string or number crashed this thread after the
        # response headers were gone, so the client only saw a dropped socket.
        message = (payload.get("message") or "").strip()
        extra = (payload.get("system") or "").strip()
        system = "\n\n".join(x for x in (persona(), extra) if x) or None
        fresh = bool(payload.get("fresh"))
        if not message:
            return self._json({"error": "empty message"}, 400)
        if fresh:
            _clear_session()

        # -- natural language mode switch ("ganti ke mode asisten/coding", "ubah mode", etc.)
        _low = message.strip().lower()
        _m = None
        if any(k in _low for k in ("mode asisten", "mode coding")) or re.search(r"ganti.*mode|ubah.*mode|switch.*mode", _low):
            if "asisten" in _low: _m = "asisten"
            elif "coding" in _low: _m = "coding"
        if _m is not None:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            def _emit(ev):
                self.wfile.write((json.dumps(ev) + "\n").encode())
                self.wfile.flush()
            try:
                set_mode(_m)
                _emit(dict(t="delta", text=f"Mode ANA diganti ke {_m}."))
            except Exception as e:
                _emit(dict(t="error", message=str(e)[:200]))
            _emit(dict(t="complete", ms=0))
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        # Check session TTL before running
        if _session_expired():
            _clear_session()

        def emit(ev):
            self.wfile.write((json.dumps(ev) + "\n").encode())
            self.wfile.flush()
        # -- the command matrix: /new /profile /goal /personality /kanban /mission /background /tools /status /browser
        cmd = commands.handle(
            message,
            runner=lambda m: runtime.run(m, None, persona()))
        if cmd:
            if cmd.get("note"):
                emit(dict(t="note", message=cmd["note"]))
            if cmd.get("fresh"):
                _clear_session()
            if cmd.get("message") is None:
                # answered locally -- no model call needed
                emit(dict(t="delta", text=cmd.get("reply", "Done.")))
                emit(dict(t="complete", ms=0))
                return
            message = cmd["message"]
            system = "\n\n".join(x for x in (persona(), extra) if x) or None

        try:
            sid0, _ = _session_get()
            for ev in runtime.run(message, sid0, system):
                # Only remember a real Hermes session, never demo/mock identifiers.
                sid = ev.get("session_id")
                # Save session when Hermes emits it (from session_id: marker)
                if ev.get("t") == "session" and runtime.valid_session(sid):
                    cur_id, cur_meta = _session_get()
                    if cur_id != str(sid):
                        _session_set(str(sid))
                    if cur_meta is None:
                        _session_set(str(sid), {"title": "--", "created": time.time(), "message_count": 0})
                # Only remember a session that actually COMPLETED. Storing it from
                # `status` (which fires at init) means one broken run poisons every
                # run after it with --resume <half-born session>.
                if ev.get("t") == "complete" and runtime.valid_session(sid):
                    _session_set(sid)
                    _session_bump_count()
                if ev.get("t") == "error":
                    _clear_session()       # drop a bad/stale session so the next run is fresh
                emit(ev)
        except (BrokenPipeError, ConnectionResetError):
            pass                                          # client navigated away
        except Exception as e:                            # noqa: BLE001
            try:
                emit(dict(t="error", message=str(e)[:300]))
            except OSError:
                pass


def _port_free(port, host="127.0.0.1"):
    """True if we can bind the port. Used to fail fast with a clear message
    instead of an OSError traceback when an old server still holds it."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


def main():
    kind = runtime.runtime_kind()
    brain = ("Hermes Agent (profile tools, skills, memory, MCP, browser integrations live)"
             if kind == "hermes" else "MOCK -- Hermes CLI not reachable")
    vo = f"edge · {voice.agent_name()} · {voice.voice_id()}"
    perm = runtime.PERMISSION
    perm_note = ("  can run tools without asking -- set ANA_PERMISSION=default to require approval"
                 if perm == "bypass" else "")

    # ── port guard ────────────────────────────────────────────
    if not _port_free(PORT, BIND_HOST):
        print(f"  PORT {PORT} in use -- waiting 2s for release...")
        time.sleep(2)
        if not _port_free(PORT, BIND_HOST):
            print(f"  PORT {PORT} still busy. Kill existing process first:\n    lsof -ti:{PORT} | xargs kill")
            sys.exit(1)

    # Persist token only after the port is confirmed free.
    # Never clobber the running server's token from a failed second instance.
    try:
        _TOKEN_FILE.write_text(API_TOKEN + "\n", encoding="utf-8")
    except OSError:
        pass

    print(f"""
  ANA · Hermes Live HUD
  ──────────────────────────────────────────────
  brain        {brain}
  profile      {runtime.PROFILE}
  workdir      {runtime.WORKDIR}
  permission   {perm}{perm_note}
  voice        {vo} + browser Web Speech fallback
  open         http://localhost:{PORT}
  bind         {BIND_HOST}:{PORT}
  debug        {"ON  (mode=" + (os.environ.get("ANA_MODE") or "develop") + ") — log map/token per baris di terminal ini" if _DEBUG_MAP else "off (mode=" + (os.environ.get("ANA_MODE") or "develop") + ") — set ANA_MODE=develop di .env atau ANA_DEBUG_MAP=1"}
""", flush=True)

    srv = QuietServer((BIND_HOST, PORT), Handler)
    _session_restore()  # session terakhir survive restart; TTL tetap berlaku
    if os.environ.get("ANA_OPEN", "1") != "0":
        webbrowser.open(f"http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  down.")
        srv.shutdown()


if __name__ == "__main__":
    main()
