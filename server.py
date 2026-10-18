"""
ANA Live -- a HUD that drives Hermes Agent.

    python3 server.py

The brain is your own Hermes Agent CLI/profile. Hermes keeps access to the same
configured tools, browser/Chrome automation, MCP servers, skills, memory, and
third-party integrations that your normal Hermes sessions have. Voice can use the
browser Web Speech API, plus server-side Edge TTS (id-ID) for voice output.
"""
import datetime
import json
import gzip
import hashlib
import mimetypes
import os
import pathlib
import queue
import re
import secrets
import socket
import sys
import threading
import time
import traceback
import webbrowser
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("application/manifest+json", ".json")
# .js must be application/javascript, not text/javascript quirk
try:
    mimetypes.add_type("application/javascript", ".js")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parent
UI = ROOT / "ui"

# PMTiles reader for single tile extraction
try:
    import pmtiles.reader as pmtiles_reader
    PMTILES_AVAILABLE = True
except Exception:
    PMTILES_AVAILABLE = False

# load .env before importing anything that reads os.environ
# Robust: inline " # comment" after unquoted values, quoted values keep # inside.
def _parse_env_value(raw: str) -> str:
    s = raw.strip()
    if not s:
        return ""
    if s[0] in ('"', "'"):
        q = s[0]
        end = s.find(q, 1)
        if end != -1:
            return s[1:end]
        return s.strip('"').strip("'")
    # unquoted: strip inline comment starting with # preceded by space or at col 0
    # keep # inside password only when quoted (handled above)
    if " #" in s:
        s = s.split(" #", 1)[0].strip()
    elif s.startswith("#"):
        return ""
    # also handle trailing # without space as comment (conservative: only if no = left)
    if "#" in s:
        # don't chop hashes that are part of password chars when unquoted but no space
        # — only chop if "# " or " #" pattern, otherwise keep (e.g. a#b)
        pass
    return s.strip().strip('"').strip("'")

_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            k = k.strip()
            v = _parse_env_value(v)
            # ponytail: WIKI_PATH/ANA_JOURNAL_PATH must follow .env (hermes snap exports stale ana_journal path)
            if k in ("WIKI_PATH", "ANA_JOURNAL_PATH", "OBSIDIAN_VAULT_PATH", "HERMES_PROFILE", "ANA_PROFILE", "ANA_SIMOGE_SCRIPTS", "HERMES_HOME"):
                os.environ[k] = v
            else:
                os.environ.setdefault(k, v)

import commands
import map_store
import runtime_gateway as runtime
import services
import spatial_chart_store
import spatial_archive_store
import tpl_store
import spatial_intel
import spatial_report_store
import sysmetrics
import terminal as ana_terminal
import voice
import auth_local
import db_source
import landing_insight
import insight_build
try:
    import metabase
except ImportError:
    # WIP paralel (modul belum di-commit): endpoint /api/metabase/* jawab 503
    # sampai file mendarat — server tetap boot, fitur lain utuh.
    metabase = None
try:
    import bit_case_store
    _BIT_CASES_AVAILABLE = True
except ImportError:
    bit_case_store = None
    _BIT_CASES_AVAILABLE = False
try:
    import bit_engine
except ImportError:
    bit_engine = None


def _metabase_503():
    return {"ok": False, "error": "modul metabase belum tersedia di deploy ini"}

# argon2 top-level — jangan import di dalam try yang sama dengan except(VerifyMismatchError)
# itu bikin UnboundLocalError: nama belum ter-bind saat except tuple dievaluasi (bug 17:41).
try:
    from argon2 import PasswordHasher as _ArgonPH
    from argon2.exceptions import VerifyMismatchError as _ArgonVME, InvalidHashError as _ArgonIHE
    try:
        from argon2.exceptions import InvalidHash as _ArgonIH
    except ImportError:
        _ArgonIH = _ArgonIHE
    _ARGON2_AVAILABLE = True
except Exception:
    _ArgonPH = None
    _ArgonVME = _ArgonIH = _ArgonIHE = Exception
    _ARGON2_AVAILABLE = False

# SIMOGE business API -- the `simoge-business` skill in Hermes owns all SQL.
# The server resolves its scripts dir lazily and calls the skill's own entry
# points; it holds no queries of its own. No sys.path mutation at import time.
# Portable: HERMES_HOME/HERMES_PROFILE win, ANA_SIMOGE_SCRIPTS overrides all.
_HERMES_HOME_DIR = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
_SIMOGE_PROFILE = (
    os.environ.get("HERMES_PROFILE", os.environ.get("ANA_PROFILE", "anna")).strip()
    or "anna"
)
_SIMOGE_SCRIPTS = os.environ.get(
    "ANA_SIMOGE_SCRIPTS",
    os.path.join(
        _HERMES_HOME_DIR,
        "profiles",
        _SIMOGE_PROFILE,
        "skills/software-development/simoge-business/scripts",
    ),
)


# ── debug log ────────────────────────────────────────────────────
# Mode dari .env:  ANA_MODE=develop  → log nyala (default kalau tak di-set)
#                  ANA_MODE=production → log mati
# Override sekali jalan: ANA_DEBUG_MAP=1 python3 server.py
# Log satu baris per request: waktu, method, path, status, ms. Tanpa token,
# tanpa SQL, tanpa body — aman dibaca di terminal.
def _debug_on():
    def _norm_flag(raw):
        if raw is None:
            return ""
        # defensive: env var may still contain inline "# comment" if loaded before patch
        s = raw.strip()
        if " #" in s:
            s = s.split(" #", 1)[0].strip()
        return s.lower()
    mode = _norm_flag(os.environ.get("ANA_MODE") or "develop")
    flag = _norm_flag(os.environ.get("ANA_DEBUG_MAP", os.environ.get("ANA_DEBUG", "")))
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


def _alog(msg, level="info"):
    """Auth/startup log — error selalu tampil walau _DEBUG_MAP off, info hanya saat debug on."""
    is_err = level in ("warn", "error")
    if not is_err and not _DEBUG_MAP:
        return
    tag = "auth" if level in ("info", "warn", "error") else "map"
    line = f"  [{tag} {time.strftime('%H:%M:%S')}] {msg}"
    if is_err:
        _log_to_file(line.strip())
    else:
        # info juga ke file bila debug on
        _log_to_file(line.strip())
    try:
        sys.stderr.write(line + "\n")
    except Exception:
        pass


def _blog(msg, level="info"):
    """BIT debug: info hanya saat _DEBUG_MAP, warn/error selalu. Prefix BIT."""
    is_err = level in ("warn", "error")
    if not is_err and not _DEBUG_MAP:
        return
    line = f"  [BIT {time.strftime('%H:%M:%S')}] {msg}"
    _log_to_file(line.strip())
    try:
        sys.stderr.write(line + "\n")
    except Exception:
        pass


def _dlog_req(method, path, code, ms):
    """Log HANYA yang berarti: error/lama/tak-bising. Tak ada filter = bising.
    Auth selalu logged (401/429 dll butuh diagnosa login/refresh/logout).
    """
    if path.startswith("/api/auth/"):
        if code >= 400:
            _alog(f"{method} {path} -> {code} ({ms:.0f}ms)", "warn" if code >= 400 else "info")
        elif _DEBUG_MAP:
            _alog(f"{method} {path} -> {code} ({ms:.0f}ms)", "info")
        return
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
    import datetime
    import decimal
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


def _scope_code(val, key):
    """Ambil satu kode wilayah dari sesi — bentuk dict/int/str semua bisa.
    Session menyimpan hasil expand (dict {'kode_kph':31211,...}) atau mentah."""
    try:
        if val is None:
            return ""
        if isinstance(val, dict):
            v = val.get(key)
            return "" if v is None else str(v).strip()
        if isinstance(val, (list, tuple)):
            return ""
        s = str(val).strip()
        return "" if s.lower() in ("none", "null") else s
    except Exception:
        return ""


_TFA_OFF_WARNED = {"done": False}


def _tfa_enforced():
    """Apakah OTP 2FA diwajibkan saat login. Default YA (perilaku lama).

    Dibaca dari file .env TIAP request (tanpa restart — pola ANA_DB_SOURCE):
    ANA_2FA_ENABLED=0/false/no/off = mati (password saja lolos, UI lewati enroll).
    Legacy ANA_TFA_BYPASS=1 = sama (kompat). JANGAN mati di produksi."""
    try:
        try:
            env = db_source._read_env()
        except Exception:
            env = {}
        v = str(env.get("ANA_2FA_ENABLED", os.environ.get("ANA_2FA_ENABLED", "1")) or "1").strip().lower()
        if v in ("0", "false", "no", "off", "disable", "disabled"):
            off, why = True, "ANA_2FA_ENABLED=0"
        elif str(env.get("ANA_TFA_BYPASS", os.environ.get("ANA_TFA_BYPASS", "")) or "").strip().lower() in ("1", "true", "yes", "on"):
            off, why = True, "ANA_TFA_BYPASS=1 (legacy)"
        else:
            return True
        if not _TFA_OFF_WARNED["done"]:
            _TFA_OFF_WARNED["done"] = True
            try:
                _alog(f"auth 2FA NONAKTIF via {why} — login password saja! JANGAN di produksi.", "warn")
            except Exception:
                pass
        return False
    except Exception:
        return True


_KPH_DIVRE_CACHE = {"at": 0.0, "map": {}}


def _kph_divre_map():
    """Peta kode_kph -> kode_divre (cache proses 10 mnt; tabel kecil)."""
    import time as _t
    now = _t.time()
    if now - _KPH_DIVRE_CACHE.get("at", 0) < 600 and _KPH_DIVRE_CACHE.get("map"):
        return _KPH_DIVRE_CACHE["map"]
    m = {}
    try:
        import db_source
        import pymysql
        kw = db_source.kwargs()
        conn = pymysql.connect(host=kw["host"], port=kw["port"], user=kw["user"],
                               password=kw["password"], database=kw["database"],
                               connect_timeout=5)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT kode_kph, kode_divre FROM kph")
                for r in cur.fetchall():
                    m[str(r[0]).strip()] = str(r[1]).strip()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        _KPH_DIVRE_CACHE["at"] = now
        _KPH_DIVRE_CACHE["map"] = m
    except Exception:
        pass
    return m or _KPH_DIVRE_CACHE.get("map", {})


def _scope_kph_code(scope):
    """Kode KPH efektif user: langsung, atau resolve dari bkph/rph/tpg."""
    try:
        if scope.get("kode_kph"):
            return str(scope["kode_kph"]).strip()
        import db_source
        import pymysql
        kw = db_source.kwargs()
        conn = pymysql.connect(host=kw["host"], port=kw["port"], user=kw["user"],
                               password=kw["password"], database=kw["database"],
                               connect_timeout=5)
        try:
            with conn.cursor() as cur:
                if scope.get("kode_bkph"):
                    cur.execute("SELECT kode_kph FROM bkph WHERE kode_bkph=%s LIMIT 1",
                                (str(scope["kode_bkph"]).strip(),))
                    r = cur.fetchone()
                    if r:
                        return str(r[0]).strip()
                if scope.get("kode_rph"):
                    cur.execute("SELECT kode_kph FROM rph WHERE kode_rph=%s LIMIT 1",
                                (str(scope["kode_rph"]).strip(),))
                    r = cur.fetchone()
                    if r:
                        return str(r[0]).strip()
                for t in (scope.get("kode_tpg_list") or []):
                    cur.execute("SELECT kode_kph FROM getah_daftar_tpg WHERE kode_tpg=%s LIMIT 1",
                                (str(t).strip(),))
                    r = cur.fetchone()
                    if r:
                        return str(r[0]).strip()
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception:
        pass
    return ""


def _tiles_scope_ok(handler, kind, kode):
    """Bolehkah sesi unduh file tile scope (kind=kph/divre, kode=angkanya).
    Fail-closed: tanpa sesi = tolak (sistem/token-only lewat jalur legacy).
    DIREKSI/ADMINISTRATOR = semua. DIVRE = dalam divrenya. ADM = KPH-nya
    (+ bounds se-divre sebagai konteks). Lebih dalam = KPH efektifnya."""
    try:
        sess = _session_from_cookie(handler)
        if not sess:
            return False, "tanpa sesi"
        jab = ""
        try:
            _j = sess.get("jabatan")
            if isinstance(_j, dict):
                jab = str(_j.get("kode_jabatan") or "").strip().upper()
            elif _j is not None:
                jab = str(_j).strip().upper()
        except Exception:
            jab = ""
        if jab in ("DIREKSI", "ADMINISTRATOR"):
            return True, ""
        scope = _wilayah_scope_from_session(handler)
        kode = str(kode or "").strip()
        if not kode:
            return False, "kode kosong"
        if kind == "kph":
            uk = _scope_kph_code(scope)
            if uk and kode == uk:
                return True, ""
            dv = str(scope.get("kode_divre") or "").strip()
            if dv and _kph_divre_map().get(kode) == dv:
                return True, ""
            return False, "di luar scope tile"
        if kind == "divre":
            if scope.get("kode_divre") and kode == str(scope.get("kode_divre")).strip():
                return True, ""
            uk = _scope_kph_code(scope)
            if uk and _kph_divre_map().get(uk) == kode:
                return True, ""
            return False, "di luar scope tile"
        if kind == "overview":
            # Tile overview berwarna = DIVRE ke atas saja. ADM (walau punya
            # divre di scope) DITOLAK tegas — ia hanya dapat bounds netral.
            if jab in ("DIREKSI", "ADMINISTRATOR"):
                return True, ""
            if jab in ("DIVRE",):
                if scope.get("kode_divre") and kode == str(scope.get("kode_divre")).strip():
                    return True, ""
                return False, "di luar scope tile"
            return False, "overview khusus DIVRE ke atas"
        return False, "jenis scope tak dikenal"
    except Exception:
        return False, "gagal cek scope"


def _wilayah_scope_from_session(handler):
    """Scope wilayah user login dari cookie sesi. {} = tak ada sesi
    (pemanggil token-only seperti ANA system — sengaja tanpa scope).

    Jabatan-aware (single source of truth, cerminkan di map.js _userScope):
    - DIREKSI/ADMINISTRATOR → {} (semua, tanpa clamp/filter)
    - DIVRE  → {kode_divre} (semua di bawah divrenya)
    - ADM    → {kode_divre, kode_kph} (admin KPH: hanya wilayah KPH-nya)
    - ASPER/KSSPROD/MANTRI → turun s/d kode_bkph bila ada
    - lain (M1-M5/K1-K5/tanpa jabatan) → apa adanya (terdalam menang)."""
    try:
        sess = _session_from_cookie(handler)
    except Exception:
        return {}
    if not sess:
        return {}
    try:
        # kode jabatan: sesi simpan dict expand {'kode_jabatan':...} atau mentah
        jab = ""
        try:
            _j = sess.get("jabatan")
            if isinstance(_j, dict):
                jab = str(_j.get("kode_jabatan") or _j.get("nama_jabatan") or "").strip().upper()
            elif _j is not None:
                jab = str(_j).strip().upper()
        except Exception:
            jab = ""
        if jab in ("DIREKSI", "ADMINISTRATOR"):
            return {}
        scope = {}
        dv = _scope_code(sess.get("kode_divre"), "kode_divre")
        kp = _scope_code(sess.get("kode_kph"), "kode_kph")
        bk = _scope_code(sess.get("kode_bkph"), "kode_bkph")
        rp = _scope_code(sess.get("kode_rph"), "kode_rph")
        if jab == "DIVRE":
            if dv:
                scope["kode_divre"] = dv
        elif jab == "ADM":
            if dv:
                scope["kode_divre"] = dv
            if kp:
                scope["kode_kph"] = kp
        elif jab in ("ASPER", "KSSPROD", "MANTRI"):
            if dv:
                scope["kode_divre"] = dv
            if kp:
                scope["kode_kph"] = kp
            if bk:
                scope["kode_bkph"] = bk
        else:
            if dv:
                scope["kode_divre"] = dv
            if kp:
                scope["kode_kph"] = kp
            if bk:
                scope["kode_bkph"] = bk
            if rp:
                scope["kode_rph"] = rp
        # user TPG-level: kode_tpg = list M2M [{kode_tpg,...},...] atau mentah
        try:
            tp = sess.get("kode_tpg")
            tpg_list = []
            if isinstance(tp, list):
                for e in tp:
                    c = e.get("kode_tpg") if isinstance(e, dict) else e
                    if c is not None and str(c).strip() != "":
                        tpg_list.append(str(c).strip())
            if tpg_list:
                scope["kode_tpg_list"] = tpg_list
        except Exception:
            pass
        return scope
    except Exception:
        return {}


def _enforce_wilayah_scope(handler, params, template=""):
    """Paksa params query ke dalam wilayah user login (robust: anti tamper
    filter via curl/devtools selama sesi login ada). Tanpa sesi = utuh.
    Return (params_baru, kunci_dipaksa, ditolak, pesan_tolak).
    User TPG-level (kode_tpg_list): query data WAJIB sebut satu kode_tpg miliknya,
    selain itu 403 — kalau tidak, query tanpa filter bocorkan semua TPG."""
    try:
        scope = _wilayah_scope_from_session(handler)
    except Exception:
        return params, [], False, ""
    if not scope:
        return params, [], False, ""
    try:
        p = dict(params or {})
    except Exception:
        return params, [], False, ""
    tpl = str(template or "").strip()
    overridden = []
    for key in ("kode_divre", "kode_kph", "kode_bkph", "kode_rph"):
        if key in scope and scope[key]:
            cur = "" if p.get(key) is None else str(p.get(key)).strip()
            if cur != str(scope[key]).strip():
                if cur != "":
                    overridden.append(key)
                p[key] = scope[key]
    tpg_list = scope.get("kode_tpg_list") or []
    if tpg_list and tpl != "wilayah_labels":
        cur = "" if p.get("kode_tpg") is None else str(p.get("kode_tpg")).strip()
        if cur not in tpg_list:
            try:
                _alog(f"wilayah scope DENY tpg di luar login ({cur[:24] or 'kosong'})", "warn")
            except Exception:
                pass
            return p, overridden, True, "di luar wilayah TPG login"
    if overridden:
        try:
            _alog(f"wilayah scope clamp {','.join(overridden)} ke wilayah login", "warn")
        except Exception:
            pass
    return p, overridden, False, ""


def _wilayah_chain_check(scope, params):
    """Validasi silang rantai: kode_bkph/kode_rph/kode_tpg yang disebut di
    params harus berada di dalam scope login (divre/kph/bkph/rph user).
    Resolve parent via tabel bkph/rph/getah_daftar_tpg. Fail-closed: kode
    tak dikenal saat scope aktif = tolak. Return (deny, pesan)."""
    try:
        p = params or {}
        bk = "" if p.get("kode_bkph") is None else str(p.get("kode_bkph")).strip()
        rp = "" if p.get("kode_rph") is None else str(p.get("kode_rph")).strip()
        tg = "" if p.get("kode_tpg") is None else str(p.get("kode_tpg")).strip()
        if not (bk or rp or tg):
            return False, ""
        if not any(scope.get(k) for k in ("kode_divre", "kode_kph", "kode_bkph", "kode_rph")):
            return False, ""
        import db_source
        import pymysql
        kw = db_source.kwargs()
        conn = pymysql.connect(**kw)
        try:
            with conn.cursor() as cur:
                if bk:
                    cur.execute("SELECT kode_divre, kode_kph, kode_bkph FROM bkph WHERE kode_bkph=%s LIMIT 1", (bk,))
                    r = cur.fetchone()
                    if r is None:
                        return True, f"kode_bkph {bk[:16]} tak dikenal"
                    got = {"kode_divre": r[0], "kode_kph": r[1], "kode_bkph": r[2]}
                    for k in ("kode_divre", "kode_kph", "kode_bkph"):
                        if scope.get(k) and got[k] is not None and str(got[k]).strip() != str(scope[k]).strip():
                            return True, f"bkph {bk[:16]} di luar wilayah login"
                if rp:
                    cur.execute("SELECT kode_divre, kode_kph, kode_bkph, kode_rph FROM rph WHERE kode_rph=%s LIMIT 1", (rp,))
                    r = cur.fetchone()
                    if r is None:
                        return True, f"kode_rph {rp[:16]} tak dikenal"
                    got = {"kode_divre": r[0], "kode_kph": r[1], "kode_bkph": r[2], "kode_rph": r[3]}
                    for k in ("kode_divre", "kode_kph", "kode_bkph", "kode_rph"):
                        if scope.get(k) and got[k] is not None and str(got[k]).strip() != str(scope[k]).strip():
                            return True, f"rph {rp[:16]} di luar wilayah login"
                if tg:
                    cur.execute("SELECT kode_divre, kode_kph, kode_bkph, kode_rph FROM getah_daftar_tpg WHERE kode_tpg=%s LIMIT 1", (tg,))
                    r = cur.fetchone()
                    if r is None:
                        return True, f"kode_tpg {tg[:16]} tak dikenal"
                    got = {"kode_divre": r[0], "kode_kph": r[1], "kode_bkph": r[2], "kode_rph": r[3]}
                    for k in ("kode_divre", "kode_kph", "kode_bkph", "kode_rph"):
                        if scope.get(k) and got[k] is not None and str(got[k]).strip() != str(scope[k]).strip():
                            return True, f"tpg {tg[:16]} di luar wilayah login"
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return False, ""
    except Exception as e:
        # DB check gagal = clamp params sudah jalan; tolak hanya bila yakin.
        try:
            _alog(f"wilayah chain-check gagal {type(e).__name__} (clamp tetap jalan)", "warn")
        except Exception:
            pass
        return False, ""


def _scope_wilayah_labels(data, scope):
    """Saring daftar wilayah_labels ke wilayah login. Tanpa scope = utuh."""
    try:
        if not scope or not isinstance(data, dict):
            return data
        rows = data.get("rows")
        if not rows or not isinstance(rows[0], dict):
            return data
        r0 = dict(rows[0])
        dv = str(scope.get("kode_divre") or "").strip()
        kp = str(scope.get("kode_kph") or "").strip()
        bk = str(scope.get("kode_bkph") or "").strip()
        rp = str(scope.get("kode_rph") or "").strip()
        if dv:
            r0["divre"] = [o for o in (r0.get("divre") or []) if str(o.get("kode_divre")) == dv]
        if kp:
            r0["kph"] = [o for o in (r0.get("kph") or []) if str(o.get("kode_kph")) == kp]
        if dv:
            r0["kph"] = [o for o in (r0.get("kph") or []) if str(o.get("kode_divre") or "") in ("", dv)]
        if kp:
            r0["bkph"] = [o for o in (r0.get("bkph") or []) if str(o.get("kode_kph") or "") in ("", kp)]
        if dv:
            r0["bkph"] = [o for o in (r0.get("bkph") or []) if str(o.get("kode_divre") or "") in ("", dv)]
        if bk:
            r0["bkph"] = [o for o in (r0.get("bkph") or []) if str(o.get("kode_bkph")) == bk]
        if dv or kp or bk:
            def _rph_ok(o):
                for k, v in (("kode_divre", dv), ("kode_kph", kp), ("kode_bkph", bk)):
                    if not v:
                        continue
                    ov = o.get(k)
                    if ov is None or str(ov).strip() == "":
                        continue
                    if str(ov).strip() != v:
                        return False
                return True
            r0["rph"] = [o for o in (r0.get("rph") or []) if _rph_ok(o)]
        if rp:
            r0["rph"] = [o for o in (r0.get("rph") or []) if str(o.get("kode_rph")) == rp]
        tpg = r0.get("tpg") or []
        def _tpg_ok(o):
            for k, v in (("kode_divre", dv), ("kode_kph", kp), ("kode_bkph", bk), ("kode_rph", rp)):
                if not v:
                    continue
                ov = o.get(k)
                if ov is None or str(ov).strip() == "":
                    continue
                if str(ov).strip() != v:
                    return False
            return True
        if dv or kp or bk or rp:
            r0["tpg"] = [o for o in tpg if _tpg_ok(o)]
        data["rows"] = [r0]
        return data
    except Exception:
        return data


def _anna_scope_write(hermes_sid, scope, user_id=""):
    """Tulis scope wilayah untuk satu sesi Hermes: .ana_scope_<sid>.json.

    Tool ANNA (ana_simoge_tool._anna_scope) membaca HERMES_SESSION_ID-nya
    sendiri (dipublish resmi via agent_init._publish_session_id) lalu baca
    file ini — tiap sesi Hermes dapat scope user dashboard yang benar,
    tak peduli berapa user login bersamaan. Idempotent: tulis tiap run.
    Sekaligus tulis .ana_current_sid (sid sesi aktif run ini) — tool
    chart/simoge baca file itu sebagai fallback karena env dashboard
    TIDAK ikut ke proses `terminal` agen Hermes. Tanpa file ini push
    chart/report 401 (server tak bisa resolve owner) walau scope ada.
    Tak pernah raise."""
    try:
        sid = str(hermes_sid or "").strip()
        if not sid or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sid):
            return
        try:
            tmp_cur = ROOT / ".ana_current_sid.tmp"
            tmp_cur.write_text(sid, encoding="utf-8")
            os.replace(tmp_cur, ROOT / ".ana_current_sid")
        except OSError:
            pass
        data = {}
        try:
            uid = str(user_id or "").strip()
            if uid:
                data["user_id"] = uid
            for k in ("kode_divre", "kode_kph", "kode_bkph", "kode_rph"):
                v = (scope or {}).get(k)
                if v:
                    data[k] = str(v).strip()
            tl = (scope or {}).get("kode_tpg_list") or []
            if tl:
                data["kode_tpg_list"] = [str(x) for x in tl]
        except Exception:
            pass
        tmp = ROOT / f".ana_scope_{sid}.json.tmp"
        try:
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, ROOT / f".ana_scope_{sid}.json")
        except OSError:
            pass
    except Exception:
        pass


def _anna_scope_prune(max_age_sec=86400):
    """Hapus file .ana_scope_<sid>.json yatim (tak dirujuk sesi ANNA mana pun
    atau lebih tua dari max_age_sec). Dipanggil saat /api/new, logout, dan
    switch DB (semua sesi ANNA dibuang di titik itu). Tak pernah raise."""
    try:
        with _SESSION_LOCK:
            live = {str((v or {}).get("id") or "") for v in SESSION.values()}
        live.discard("")
        now = time.time()
        for f in ROOT.glob(".ana_scope_*.json"):
            try:
                m = re.fullmatch(r"\.ana_scope_(.+)\.json", f.name)
                if not m:
                    continue
                sid = m.group(1)
                if sid in live:
                    continue
                try:
                    age = now - f.stat().st_mtime
                except OSError:
                    age = max_age_sec + 1
                if age >= max_age_sec:
                    try:
                        f.unlink(missing_ok=True)
                    except OSError:
                        pass
            except Exception:
                continue
    except Exception:
        pass


def _anna_identity_block(handler):
    """Blok identitas user login untuk system prompt ANNA (/api/run).
    Tanpa sesi = string kosong (token-only tetap netral).
    Isi: nama + email + jabatan + wilayah kerja (nama, bukan kode saja).
    Privasi: hanya nama/jabatan/wilayah kerja — tanpa password/token/hash.
    Tak pernah raise."""
    try:
        sess = _session_from_cookie(handler)
    except Exception:
        return ""
    if not sess:
        return ""
    try:
        fn = str(sess.get("first_name") or "").strip()
        ln = str(sess.get("last_name") or "").strip()
        nama = (fn + " " + ln).strip()
        email = str(sess.get("email") or "").strip()
        _j = sess.get("jabatan")
        jab_nama = jab_kode = ""
        try:
            if isinstance(_j, dict):
                jab_nama = str(_j.get("nama_jabatan") or "").strip()
                jab_kode = str(_j.get("kode_jabatan") or "").strip().upper()
            elif _j is not None:
                jab_kode = str(_j).strip().upper()
        except Exception:
            pass
        def _nm(v, *keys):
            try:
                if isinstance(v, dict):
                    for k in keys:
                        s = str(v.get(k) or "").strip()
                        if s:
                            return s
                elif v is not None:
                    s = str(v).strip()
                    if s:
                        return s
            except Exception:
                pass
            return ""
        wil = []
        dv = _nm(sess.get("kode_divre"), "divre", "kode_divre")
        kp = _nm(sess.get("kode_kph"), "kph", "kode_kph")
        bk = _nm(sess.get("kode_bkph"), "bkph", "kode_bkph")
        rp = _nm(sess.get("kode_rph"), "rph", "kode_rph")
        if dv:
            wil.append("DIVRE " + dv)
        if kp:
            wil.append("KPH " + kp)
        if bk:
            wil.append("BKPH " + bk)
        if rp:
            wil.append("RPH " + rp)
        who = nama or email
        jab_txt = jab_nama or jab_kode
        if not who and not jab_txt and not wil:
            return ""
        lines = ["## IDENTITAS USER (lawan bicara)"]
        id_line = ""
        if who:
            id_line += who
        if jab_txt:
            id_line += (", " if id_line else "") + jab_txt
        if id_line:
            lines.append("- " + id_line)
        if email and nama:
            lines.append("- Email: " + email)
        if wil:
            lines.append("- Wilayah kerja: " + ", ".join(wil))
        lines.append("Sapa dengan nama/jabatan secara wajar (mis. 'Pak/Bu <nama>' bila tahu); jangan sebut email kecuali perlu. Jangan pernah sebut password/token/sesi.")
        return "\n".join(lines)
    except Exception:
        return ""


def _anna_scope_block(scope):
    """Blok instruksi scope wilayah untuk system prompt ANNA (/api/run).
    Tanpa scope (DIREKSI / tanpa kode / token-only) = string kosong."""
    try:
        if not scope:
            return ""
        parts = []
        dv = str(scope.get("kode_divre") or "").strip()
        kp = str(scope.get("kode_kph") or "").strip()
        bk = str(scope.get("kode_bkph") or "").strip()
        rp = str(scope.get("kode_rph") or "").strip()
        tg = list(scope.get("kode_tpg_list") or [])
        if dv:
            parts.append(f"DIVRE {dv}")
        if kp:
            parts.append(f"KPH {kp}")
        if bk:
            parts.append(f"BKPH {bk}")
        if rp:
            parts.append(f"RPH {rp}")
        if tg:
            _tg_txt = ", ".join(tg[:10]) + (f" (+{len(tg)-10} lain)" if len(tg) > 10 else "")
            parts.append(f"TPG {_tg_txt}")
        if not parts:
            return ""
        wil = ", ".join(parts)
        luar = []
        if dv:
            luar.append("divre lain")
        if kp:
            luar.append("KPH lain")
        if bk:
            luar.append("BKPH lain")
        if rp:
            luar.append("RPH lain")
        if tg:
            luar.append("TPG lain")
        _luar_txt = ", ".join(luar) if luar else "wilayah lain"
        return (
            "## BATAS WILAYAH USER (wajib ditaati)\n"
            f"User login hanya berhak atas wilayah: {wil}. "
            "Semua angka/chart/peta/laporan HANYA dari wilayah itu — selalu sertakan "
            "filter kode_* yang sesuai di setiap pemanggilan tool bisnis "
            "(call_simoge_tool/call_simoge_packet/show_on_map/answer_production). "
            f"Jika user meminta data di luar itu ({_luar_txt}), "
            "TOLAK dengan sopan ('di luar wilayah Bapak/Ibu') dan tawarkan data wilayahnya. "
            "Jangan mengakali dengan query tanpa filter — tool menolaknya."
        )
    except Exception:
        return ""


# == P1 Business Context Packet ==============================================
# Transform DB rows -> {intent, period, scope, kpi, evidence} for Anna.
# Model receives packet; raw rows only included when explicitly requested.

def _get_wilayah_consts():
    """Get wilayah constants from simoge_db module."""
    try:
        mod = _simoge_mod("simoge_db")
        return mod._WILAYAH_COLS, mod._WILAYAH_NAMES
    except Exception:
        # Fallback constants
        cols = ("kode_divre", "kode_kph", "kode_bkph", "kode_rph", "kode_tpg")
        names = {"kode_divre": "divre", "kode_kph": "kph", "kode_bkph": "bkph",
                 "kode_rph": "rph", "kode_tpg": "nama_tpg"}
        return cols, names


_WILAYAH_COLS, _WILAYAH_NAMES = _get_wilayah_consts()


def _build_packet(template, params, result):
    """Build Business Context Packet from template result."""
    rows = result.get("rows") or []
    row_count = result.get("row_count", len(rows))
    explanation = result.get("explanation") or ""
    
    # Extract period/scope from params
    tahun = params.get("tahun", datetime.date.today().year)
    bulan = params.get("bulan", datetime.date.today().month)
    periode = params.get("periode", 0)
    level = params.get("level", "kode_bkph")
    
    # Scope label
    scope_label = _WILAYAH_NAMES.get(level, level)
    kode_wilayah = params.get(level) if level in _WILAYAH_COLS else None
    
    # Period text
    per_txt = "bulan penuh" if int(periode) == 0 else f"P{int(periode)}"
    bln_nama = ["Januari","Februari","Maret","April","Mei","Juni",
                "Juli","Agustus","September","Oktober","November","Desember"]
    scope_str = f"{scope_label} {bln_nama[bulan-1]} {tahun} - {per_txt}"
    if kode_wilayah:
        scope_str = f"{kode_wilayah} {scope_str}"
    
    # Map template -> intent + kpi extractor
    packet = {
        "intent": template,
        "period": {"tahun": int(tahun), "bulan": int(bulan), "periode": int(periode)},
        "scope": {"level": level, "label": scope_label, "kode": kode_wilayah, "text": scope_str},
        "kpi": {},
        "evidence": [],
        "row_count": row_count,
    }
    
    if not rows:
        packet["evidence"] = [{"statement": f"Tidak ada data untuk {scope_str}",
                               "source": template, "value": None}]
        return packet
    
    # Template-specific KPI aggregation (no raw rows to model)
    try:
        if template == "petak_count":
            r = rows[0]
            packet["kpi"] = {
                "total_petak": int(r.get("jumlah_petak", 0)),
                "total_luas_baku_ha": float(r.get("total_luas_baku", 0) or 0),
            }
            packet["evidence"] = [{
                "statement": f"{packet['kpi']['total_petak']} petak, luas {packet['kpi']['total_luas_baku_ha']:.2f} ha",
                "source": template, "value": scope_str
            }]
        
        elif template == "petak_area":
            r = rows[0]
            packet["kpi"] = {
                "luas_baku_total_ha": float(r.get("luas_baku_total", 0) or 0),
                "luas_andil_total_ha": float(r.get("luas_andil_total", 0) or 0),
                "rasio_andil_pct": float(r.get("rasio_andil_pct", 0) or 0),
            }
            packet["evidence"] = [{
                "statement": f"Luas baku {packet['kpi']['luas_baku_total_ha']:.2f} ha, andil {packet['kpi']['luas_andil_total_ha']:.2f} ha ({packet['kpi']['rasio_andil_pct']:.1f}%)",
                "source": template, "value": scope_str
            }]
        
        elif template == "status_petak_per_wilayah":
            tot = {k: sum(float(r.get(k) or 0) for r in rows) for k in ("total_petak","aktif","idle","bongkor","luas_bongkor")}
            packet["kpi"] = {k: int(v) if k != "luas_bongkor" else float(v) for k,v in tot.items()}
            packet["evidence"] = [{
                "statement": f"PETAK {tot['total_petak']} · AKTIF {tot['aktif']} · IDLE {tot['idle']} · BONGKOR {tot['bongkor']} ({tot['luas_bongkor']:.1f} ha)",
                "source": template, "value": scope_str
            }]
        
        elif template == "produksi_per_wilayah":
            act_kg = sum(float(r.get("actual_kg") or 0) for r in rows)
            tgt_kg = sum(float(r.get("target_kg") or 0) for r in rows)
            ach = (act_kg / tgt_kg * 100) if tgt_kg else 0
            # ponytail: breakdown per wilayah (<=10 rows) untuk chart langsung tanpa rows penuh
            breakdown = [{"kode": r.get("kode_wilayah"), "nama": r.get("nama_wilayah"), "n_petak": int(r.get("n_petak") or 0), "actual_ton": round(float(r.get("actual_kg") or 0)/1000,2), "target_ton": round(float(r.get("target_kg") or 0)/1000,2), "achievement_pct": round(float(r.get("achievement_pct") or 0),2)} for r in rows[:10]]
            packet["kpi"] = {
                "actual_ton": round(act_kg / 1000, 2),
                "target_ton": round(tgt_kg / 1000, 2),
                "achievement_pct": round(ach, 2),
                "breakdown": breakdown,
            }
            packet["evidence"] = [{
                "statement": f"Produksi {packet['kpi']['actual_ton']:.2f} ton dari target {packet['kpi']['target_ton']:.2f} ton ({packet['kpi']['achievement_pct']:.2f}%)",
                "source": template, "value": scope_str
            }]
        
        elif template == "bongkor_per_wilayah":
            tot_b = sum(int(r.get("jumlah_petak") or 0) for r in rows)
            tot_ha = sum(float(r.get("total_luas") or 0) for r in rows)
            top_wil = max(rows, key=lambda r: int(r.get("jumlah_petak") or 0)) if rows else {}
            breakdown = [{"kode": r.get("kode_wilayah"), "nama": r.get("nama_wilayah"), "jumlah_petak": int(r.get("jumlah_petak") or 0), "total_luas": round(float(r.get("total_luas") or 0),2)} for r in rows[:10]]
            packet["kpi"] = {
                "total_bongkor_petak": tot_b,
                "total_bongkor_ha": round(tot_ha, 1),
                "top_wilayah": str(top_wil.get("nama_wilayah") or top_wil.get("kode_bkph") or "-"),
                "top_petak": int(top_wil.get("jumlah_petak") or 0),
                "breakdown": breakdown,
            }
            packet["evidence"] = [{
                "statement": f"{tot_b} petak bongkor, {tot_ha:.1f} ha, tersebar. Terbanyak: {packet['kpi']['top_wilayah']} ({packet['kpi']['top_petak']} petak)",
                "source": template, "value": scope_str
            }]
        
        elif template == "aktivitas_agregat":
            gb = params.get("grup_by", "penyadap")
            total = sum(int(r.get("count") or 0) for r in rows)
            top = rows[0] if rows else {}
            breakdown = [{"label": r.get("label"), "count": int(r.get("count") or 0)} for r in rows[:10]]
            packet["kpi"] = {
                "total_aktivitas": total,
                "grup_by": gb,
                "top_label": str(top.get("label") or "-"),
                "top_count": int(top.get("count") or 0),
                "breakdown": breakdown,
            }
            packet["evidence"] = [{
                "statement": f"Total {total} aktivitas per {gb}. Teratas: {packet['kpi']['top_label']} ({packet['kpi']['top_count']})",
                "source": template, "value": scope_str
            }]
        
        elif template == "produksi_trend":
            # 1 query -> 20 baris P1/P2 Jan-Des — hitung growth di packet, bukan di LLM
            # rows: bulan, periode, total_kg, n_terima, n_petak
            pts=[{"bulan":int(r["bulan"]),"periode":int(r["periode"]),"total_kg":float(r["total_kg"] or 0),"n_petak":int(r["n_petak"] or 0),"label":f"P{int(r['periode'])} {bln_nama[int(r['bulan'])-1][:3]}"} for r in rows]
            # growth periode-ke-periode
            for i in range(1,len(pts)):
                prev=pts[i-1]["total_kg"]; cur=pts[i]["total_kg"]
                pts[i]["growth_pct"]=round(100*(cur-prev)/prev,2) if prev else None
            if pts: pts[0]["growth_pct"]=None
            drops=[x for x in pts if x.get("growth_pct") is not None and x["growth_pct"] < -30]
            packet["kpi"]={"total_kg":round(sum(x["total_kg"] for x in pts),1),"n_periode":len(pts),"drops":drops[:5],"breakdown":pts}
            packet["evidence"]=[{"statement":f"Produksi {tahun}: {len(pts)} periode, total {packet['kpi']['total_kg']/1000:.1f} ton. Drop <-30%: "+( ", ".join(f"{d['label']} {d['growth_pct']}%" for d in drops[:3]) if drops else "tidak ada"),"source":template,"value":scope_str}]

        elif template == "aktivitas_trend":
            pts=[{"bulan":int(r["bulan"]),"periode":int(r["periode"]),"n_aktivitas":int(r["n_aktivitas"] or 0),"n_petak_aktif":int(r["n_petak_aktif"] or 0),"n_penyadap":int(r["n_penyadap"] or 0),"label":f"P{int(r['periode'])} {bln_nama[int(r['bulan'])-1][:3]}"} for r in rows]
            packet["kpi"]={"total_aktivitas":sum(x["n_aktivitas"] for x in pts),"n_periode":len(pts),"breakdown":pts}
            packet["evidence"]=[{"statement":f"Aktivitas {tahun}: {len(pts)} periode, total {packet['kpi']['total_aktivitas']} aktivitas, petak aktif max {max((x['n_petak_aktif'] for x in pts), default=0)}","source":template,"value":scope_str}]

        elif template == "aktivitas_top_petak":
            top = rows[0] if rows else {}
            packet["kpi"] = {
                "n_petak": len(rows),
                "total_aktivitas": sum(int(r.get("jumlah_aktivitas") or 0) for r in rows),
                "top_nomor_petak": str(top.get("nomor_petak") or "-"),
                "top_aktivitas": int(top.get("jumlah_aktivitas") or 0),
            }
            packet["evidence"] = [{
                "statement": f"Paling aktif: petak {packet['kpi']['top_nomor_petak']} ({packet['kpi']['top_aktivitas']} aktivitas)",
                "source": template, "value": scope_str
            }]
        
        elif template == "petak_effectiveness":
            cats = {}
            for r in rows:
                k = r.get("kategori", "unknown")
                cats[k] = cats.get(k, 0) + 1
            packet["kpi"] = {"kategori": cats, "total": row_count}
            packet["evidence"] = [{
                "statement": f"Efektivitas {row_count} petak: " + ", ".join(f"{k}={v}" for k,v in sorted(cats.items())),
                "source": template, "value": scope_str
            }]
        
        elif template == "petak_bongkor":
            luas = sum(float(r.get("luas_baku") or 0) for r in rows)
            packet["kpi"] = {"total_bongkor_petak": row_count, "total_luas_ha": round(luas, 1)}
            packet["evidence"] = [{
                "statement": f"{row_count} petak bongkor, luas total {luas:.1f} ha",
                "source": template, "value": scope_str
            }]
        
        elif template == "idle_petak":
            stats = {}
            for r in rows:
                s = r.get("status", "unknown")
                stats[s] = stats.get(s, 0) + 1
            packet["kpi"] = {"status": stats, "total": row_count}
            packet["evidence"] = [{
                "statement": f"{row_count} petak idle: " + ", ".join(f"{k}={v}" for k,v in sorted(stats.items())),
                "source": template, "value": scope_str
            }]
        
        elif template == "petak_by_kph":
            packet["kpi"] = {"wilayah": [{"kode": r.get("kode"), "nama": r.get("nama_wilayah"), "petak": int(r.get("jumlah_petak") or 0), "luas": float(r.get("luas_baku") or 0)} for r in rows[:10]]}
            packet["evidence"] = [{
                "statement": "Top 10 wilayah: " + "; ".join(f"{w['nama'] or w['kode']}: {w['petak']} petak" for w in packet["kpi"]["wilayah"]),
                "source": template, "value": scope_str
            }]
        
        elif template == "rkap_achievement":
            cats = {}
            for r in rows:
                w = r.get("warna", "unknown")
                cats[w] = cats.get(w, 0) + 1
            packet["kpi"] = {"warna": cats, "total": row_count}
            packet["evidence"] = [{
                "statement": f"RKAP achievement {row_count} petak: " + ", ".join(f"{k}={v}" for k,v in sorted(cats.items())),
                "source": template, "value": scope_str
            }]
        
        elif template == "penyadap_productivity":
            packet["kpi"] = {"n_penyadap": row_count}
            packet["evidence"] = [{
                "statement": f"{row_count} penyadap tercatat",
                "source": template, "value": scope_str
            }]
        
        elif template == "drum_flow":
            stats = {}
            for r in rows:
                stats[r.get("status_drum", "?")] = int(r.get("jumlah_drum") or 0)
            packet["kpi"] = {"status_drum": stats}
            packet["evidence"] = [{
                "statement": "Drum flow: " + ", ".join(f"{k}={v}" for k,v in stats.items()),
                "source": template, "value": scope_str
            }]
        
        else:
            # Generic fallback
            packet["kpi"] = {"rows": row_count}
            packet["evidence"] = [{"statement": explanation or f"Query {template} returned {row_count} rows",
                                   "source": template, "value": scope_str}]
    
    except Exception as e:
        packet["kpi"] = {"error": str(e)[:100], "rows": row_count}
        packet["evidence"] = [{"statement": f"Packet build error: {e}", "source": template}]
    
    return packet


def _simoge_query_packet(template, params):
    """Wrapper: query + build packet (no raw rows to model unless requested)."""
    result = _simoge_query(template, params)
    packet = _build_packet(template, params, result)
    # Optionally include rows for debug: params.get("include_rows") == True
    if params.get("include_rows"):
        packet["rows"] = result.get("rows") or []
    packet["explanation"] = result.get("explanation") or ""
    packet["elapsed_ms"] = result.get("elapsed_ms")
    return packet


def _simoge_analyze(template, params, operations, max_result_rows=20):
    """Pandas analytical — 1 call batch SQL->pandas->small result (hemat dynamic tokens)."""
    mod = _simoge_mod("ana_pandas_tool")
    return mod.call_pandas_tool(template=template, params=params, operations=operations, max_result_rows=max_result_rows)


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
        # Agregat (kph_summary_map): kode_wilayah (dulu join key yang tak ada di
        # rows sehingga id jatuh ke "|||" -> tooltip "Petak |||").
        _fid = (str(r.get("nomor_petak") or "").strip()
                or str(r.get("kode_wilayah") or "").strip()
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
    "aktivitas_kerja_map": ("aktivitas", "semua"),
    "keaktifan_petak_map": ("keaktifan", "semua"),
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


def _spatial_sync(template, params, warna_only, scope=None, owner=""):
    _mowner = str(owner or "")
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

    scope (opsional): wilayah login — filter wilayah ANA di luar scope
    DIABAIKAN (panel tak boleh disuruh keluar wilayah user). Tanpa scope
    (token-only) = utuh seperti dulu.
    """
    bizkat = _TEMPLATE_SPATIAL.get(template)
    if not bizkat:
        return None  # mis. petak_with_geometry: legacy, tanpa sync
    biz, kat = bizkat
    if warna_only and template == "petak_efektivitas_map":
        kat = _WARNA_KATEGORI.get(warna_only, kat)
    filters = {}
    _scope = dict(scope or {})
    _tpg_list = _scope.get("kode_tpg_list") or []
    for k in _SPATIAL_FILTER_KEYS:
        v = params.get(k, params.get("kode_" + k, ""))
        # Kontrak penuh solusi A: absen = "" (reset eksplisit di panel),
        # bukan di-skip (skip = warisan filter turn lama menempel).
        s = "" if v is None else str(v).strip()
        # Scope login: filter wilayah ANA di luar scope dibuang (jangan suruh
        # panel keluar wilayah user). Berlaku untuk divre/kph/bkph/rph/tpg.
        if k in ("divre", "kph", "bkph", "rph"):
            sk = _scope.get("kode_" + k, "")
            if sk and s and s != str(sk).strip():
                try:
                    _alog(f"spatial_set abaikan {k}={s[:16]} di luar scope login", "warn")
                except Exception:
                    pass
                s = ""
        elif k == "tpg" and _tpg_list and s and s not in _tpg_list:
            try:
                _alog(f"spatial_set abaikan tpg={s[:16]} di luar scope login", "warn")
            except Exception:
                pass
            s = ""
        filters[k] = s
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
    cmd_id, err = map_store.push_command("spatial_set", args, owner=_mowner)
    if err:
        return None
    with _SPATIAL_LOCK:
        _SPATIAL_SIG[sig] = (now, cmd_id)
        # buang signature lama supaya dict tak tumbuh tanpa batas
        for k in [k for k, v in _SPATIAL_SIG.items() if (now - v[0]) > _SPATIAL_TTL]:
            _SPATIAL_SIG.pop(k, None)
    return cmd_id


def _simoge_show_on_map(template, params, drive_panel=True, scope=None, owner=""):
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
            sp_id = _spatial_sync(template, params, warna_only, scope=scope, owner=owner)
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
    }, owner=str(owner or ""))
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
# ── Insight publik landing (aturan keras #2) ──
# Rate-limit sendiri 30/menit/IP (jangan pakai limiter auth 5/menit —
# login page yang dibuka 6x langsung 429 = bug). Cache 60 dtk di handler.
_LANDING_RL = {}
_LANDING_RL_LOCK = threading.Lock()
_LANDING_CACHE = {}
# ── Switch perangkat via QR: token satu-pakai + cooldown per user ──
# In-memory + lock (restart = hangus = aman; TTL pendek). Asumsi satu proses
# (sama seperti _LOCK sesi). JANGAN pindah ke file tanpa TTL+lock setara.
_SWITCH_TOKENS = {}
_SWITCH_LOCK = threading.Lock()
_SWITCH_TTL = 120
_SWITCH_COOLDOWN = {}
_SWITCH_COOLDOWN_SEC = 10
# ── Insight Engine v1 (Tahap C): snapshot file + scheduler thread ──
# API baca snapshot (tanpa query per request). Scheduler hitung berkala.
# Gagal total (file tak ada + DB mati) = 503, bukan angka bohong.
_INSIGHT_LOCK = threading.Lock()
_INSIGHT_MIN = 360
try:
    _INSIGHT_MIN = int((os.environ.get("ANA_INSIGHT_MIN") or "360").strip() or "360")
except Exception:
    _INSIGHT_MIN = 360


def _insight_loop():
    import insight_build as _ib
    # Fallback bila cron 06:00 tak ada: hitung bila snapshot basi/tak ada.
    # Cron aktif = thread ini hampir tak pernah hitung (hemat DB).
    # Interval fallback: ANA_INSIGHT_MIN (default 360 mnt = 6 jam).
    try:
        snap = _ib.load_snapshot()
        gen = (snap or {}).get("generated_at", "")
        stale = True
        try:
            dt = datetime.datetime.fromisoformat(gen)
            stale = (datetime.datetime.now() - dt).total_seconds() > 6 * 3600
        except Exception:
            stale = True
        if not snap or stale:
            _ib.refresh()
    except Exception as e:
        _alog(f"insight boot refresh gagal {type(e).__name__}: {str(e)[:120]}", "warn")
    while True:
        try:
            time.sleep(max(_INSIGHT_MIN, 5) * 60)
        except Exception:
            return
        if _INSIGHT_LOCK.acquire(blocking=False):
            try:
                _ib.refresh()
            except Exception as e:
                _alog(f"insight refresh gagal {type(e).__name__}: {str(e)[:120]}", "warn")
            finally:
                try:
                    _INSIGHT_LOCK.release()
                except Exception:
                    pass


def _landing_rl_ok(ip):
    now = time.time()
    with _LANDING_RL_LOCK:
        arr = [t for t in _LANDING_RL.get(ip, []) if now - t < 60]
        if len(arr) >= 30:
            _LANDING_RL[ip] = arr
            return False
        arr.append(now)
        _LANDING_RL[ip] = arr
        return True
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
# ── Local session cookie helpers (HttpOnly, 1 akun 1 perangkat) ──
ANA_AUTH_REQUIRED = os.environ.get("ANA_AUTH_REQUIRED", "0").strip() not in ("0","", "false", "False")
AUTH_MODE = "local"

def _parse_cookies(header_val: str) -> dict:
    out={}
    for part in (header_val or "").split(";"):
        if "=" in part:
            k,v = part.strip().split("=",1)
            out[k.strip()] = v.strip()
    return out

def _ana_device_id(handler) -> str:
    """Device UUID persisten per browser dari header X-Ana-Device.

    Generate sekali di localStorage (login.js), kirim tiap request.
    Validasi ringan: alnum + '-'/'_'/'='/_' maks 64 char — tanpa ini header
    sampah masuk ke hash dan evict jadi tak deterministik."""
    try:
        if handler is None:
            return ""
        d = str(handler.headers.get("X-Ana-Device", "") or "").strip()[:64]
        if d and re.fullmatch(r"[A-Za-z0-9_=\-]{8,64}", d):
            return d
        # Navigasi browser (GET / usai login) tak bisa kirim custom header —
        # baca cermin ana_device (cookie HttpOnly, ditulis saat login, ikut
        # terkirim otomatis). Tanpa fallback ini tiap navigasi = did kosong =
        # hash mismatch = 302 login.html = loop login↔dashboard selamanya.
        try:
            c = _parse_cookies(handler.headers.get("Cookie", "") or "").get("ana_device", "").strip()[:64]
            if c and re.fullmatch(r"[A-Za-z0-9_=\-]{8,64}", c):
                return c
        except Exception:
            pass
    except Exception:
        pass
    return ""


def _get_client_ip(handler) -> str:
    """Get client IP, respect X-Forwarded-For from Apache proxy."""
    forwarded = handler.headers.get("X-Forwarded-For", "").strip()
    if forwarded:
        # Take first IP in X-Forwarded-For chain
        return forwarded.split(",")[0].strip()
    return handler.client_address[0] if handler.client_address else "unknown"

def _session_from_cookie(handler) -> dict | None:
    raw = handler.headers.get("Cookie","")
    sid = _parse_cookies(raw).get("ana_session","").strip()
    if not sid: return None
    sess = auth_local.get_session(sid)
    if not sess:
        handler._ana_auth_reason = "expired"
        return None
    # Soft-revoked (ditendang login perangkat lain) = reason eksplisit agar
    # frontend tampilkan banner + tombol ambil alih, bukan redirect buta.
    if sess.get("revoked_by"):
        handler._ana_auth_reason = "evicted_by_new_device"
        try:
            handler._ana_auth_evict = {"device_label": str(sess.get("revoked_label") or "?"),
                                       "at": float(sess.get("revoked_at") or 0)}
        except Exception:
            handler._ana_auth_evict = {}
        return None
    if time.time() > float(sess.get("expires_at", 0)):
        refreshed,_ = auth_local.refresh_session(sid)
        if not refreshed:
            handler._ana_auth_reason = "expired"
            return None
        sess = refreshed
    ua = handler.headers.get("User-Agent","") or ""
    if sess.get("device_hash") and sess.get("device_hash") != auth_local.device_hash(ua, "", _ana_device_id(handler)):
        handler._ana_auth_reason = "evicted_by_new_device"
        try:
            handler._ana_auth_evict = {"device_label": str(sess.get("device_label") or "?"),
                                       "at": float(sess.get("last_seen") or 0)}
        except Exception:
            handler._ana_auth_evict = {}
        return None
    auth_local.touch_session(sid)
    return sess


def _ana_auth_error(handler) -> tuple:
    """(status, body) 401 dengan reason eksplisit — frontend bedakan aksi:
    expired → refresh/coba login; evicted_by_new_device → banner + ambil alih;
    bad_device → login ulang. Tanpa reason semua 401 = redirect buta (frustrasi)."""
    try:
        reason = getattr(handler, "_ana_auth_reason", "") or "expired"
    except Exception:
        reason = "expired"
    try:
        info = getattr(handler, "_ana_auth_evict", {}) or {}
    except Exception:
        info = {}
    if reason == "evicted_by_new_device":
        return 401, {"error": "evicted_by_new_device",
                     "message": "Akun ini login di perangkat lain — sesi perangkat ini dialihkan.",
                     "evict": info}
    return 401, {"error": "tidak ada sesi", "authenticated": False, "reason": reason}

def _set_session_cookie(handler, sid: str, did: str = ""):
    # Auto-detect HTTPS from environment or Apache proxy headers
    secure = os.environ.get("ANA_COOKIE_SECURE","0").strip() == "1"
    if not secure:
        # Check Apache proxy headers for HTTPS
        secure = (
            handler.headers.get("X-Forwarded-Proto", "").lower() == "https" or
            handler.headers.get("X-Forwarded-SSL", "").lower() == "on" or
            handler.headers.get("HTTPS", "").lower() == "on"
        )
    parts = [f"ana_session={sid}", "Path=/", "HttpOnly", "SameSite=Lax"]
    if secure: parts.append("Secure")
    try: ttl = int(os.environ.get("ANA_SESSION_TTL","28800"))
    except: ttl = 28800
    parts.append(f"Max-Age={ttl}")
    handler.send_header("Set-Cookie", "; ".join(parts))
    # Cermin device_id ke cookie HttpOnly agar NAVIGASI lolos cek device_hash
    # (dibaca _ana_device_id). HttpOnly juga — JS tak perlu baca, hanya server.
    try:
        d = (did or "").strip()[:64]
        if d and re.fullmatch(r"[A-Za-z0-9_=\-]{8,64}", d):
            dp = [f"ana_device={d}", "Path=/", "HttpOnly", "SameSite=Lax"]
            if secure: dp.append("Secure")
            dp.append(f"Max-Age={ttl}")
            handler.send_header("Set-Cookie", "; ".join(dp))
    except Exception:
        pass

def _clear_session_cookie(handler):
    # Auto-detect HTTPS for secure cookie deletion
    secure = (
        handler.headers.get("X-Forwarded-Proto", "").lower() == "https" or
        handler.headers.get("X-Forwarded-SSL", "").lower() == "on" or
        handler.headers.get("HTTPS", "").lower() == "on"
    )
    secure_flag = "; Secure" if secure else ""
    handler.send_header("Set-Cookie", f"ana_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax{secure_flag}")
    try:
        handler.send_header("Set-Cookie", f"ana_device=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax{secure_flag}")
    except Exception:
        pass

# ── FASE 2: layout store per-user (konsep v3 §3/§5) ──
# layout_<uid>.json {v:3,locked,disabled,desktop:{layouts},mobile:{layouts}}.
# uid HANYA dari cookie sesi, bukan body/query. Tulis atomic tmp+rename.
def _layout_uid_file(uid: str) -> pathlib.Path | None:
    uid = (uid or "").strip()
    if not uid or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", uid):
        return None
    return ROOT / f"layout_{uid}.json"

def _layout_validate_layouts(layouts):
    if not isinstance(layouts, dict):
        return "layouts must be dict"
    for k, v in layouts.items():
        if not isinstance(k, str) or not isinstance(v, dict):
            return "invalid layout entry"
    return None

def _layout_load_for_uid(uid: str) -> dict:
    f = _layout_uid_file(uid)
    if f is not None and f.exists():
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("desktop"), dict):
                return data
        except Exception:
            pass
    # seed: desktop = layout.json lama, mobile = {} (clamp di frontend)
    seed_layouts, locked, disabled = {}, True, []
    try:
        old = json.loads((ROOT / "layout.json").read_text(encoding="utf-8"))
        if isinstance(old, dict):
            seed_layouts = old.get("layouts", {}) if isinstance(old.get("layouts"), dict) else {}
            locked = bool(old.get("locked", True))
            disabled = old.get("disabled", []) if isinstance(old.get("disabled"), list) else []
    except Exception:
        pass
    return {"v": 3, "locked": locked, "disabled": disabled,
            "desktop": {"layouts": seed_layouts}, "mobile": {"layouts": {}}}

def _layout_atomic_write(path: pathlib.Path, data: dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)

RUN_STATE = {"active": False, "since": 0.0, "message": ""}
RUN_STATE_GUARD = threading.Lock()
# Run paralel per-user: satu user nyangkut TIDAK boleh 409-kan user lain.
# RUN_STATE global di atas dipertahankan untuk kanal netral/token-only;
# user login punya slot sendiri di _RUN_BY_USER {user_key: {active,since,message}}.
# Tanpa ini: user A stall 120s = user B 409 walau sesinya sehat.
_RUN_BY_USER: dict = {}
try:
    RUN_TIMEOUT_SEC = float(os.environ.get("ANA_RUN_TIMEOUT", "300"))
except ValueError:
    RUN_TIMEOUT_SEC = 300.0
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
_WIKI_MAX_INDEX = 1700  # ponytail: 6000→1700 tiered T1 header+18 entities clean-cut, full 104 via describe() on-demand; add when query butuh concept detail
_WIKI_MAX_ALIAS = 2000  # alias-wilayah.md ~1.6KB: wajib full (licin/glenmore/jatim)


def _wiki_path():
    p = (os.environ.get("WIKI_PATH") or "").strip()
    return pathlib.Path(p) if p else None


def _journal_path():
    p = (os.environ.get("ANA_JOURNAL_PATH") or "").strip()
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
    # journal daily mtime into cache key so 10 Daily edits invalidate
    _j_daily_key = None
    try:
        _jb = _journal_path()
        if _jb is not None:
            import datetime as _dt
            _jf = _jb / "10 Daily" / f"{_dt.date.today().isoformat()}.md"
            _stj = _jf.stat()
            _j_daily_key = (_stj.st_mtime_ns, _stj.st_size)
    except OSError:
        _j_daily_key = None
    _full_key = (key, _j_daily_key)
    if _WIKI_CACHE["key"] == _full_key:
        return _WIKI_CACHE["text"]
    try:
        raw = idx_f.read_text(encoding="utf-8", errors="replace")
        if len(raw) > _WIKI_MAX_INDEX:
            cut = raw[:_WIKI_MAX_INDEX]
            nl = cut.rfind("\n")
            idx = cut[:nl] if nl > 800 else cut  # ponytail: clean line-cut, need header intact
        else:
            idx = raw
    except OSError:
        return ""
    try:
        alias = alias_f.read_text(encoding="utf-8", errors="replace")[:_WIKI_MAX_ALIAS]
    except OSError:
        alias = ""
    # Second brain: ana_journal daily context — OSError on index.md must still try daily
    journal_extra = ""
    jbase = _journal_path()
    j_daily_key = None
    if jbase is not None:
        jidx = ""
        jidx_ok = False
        # try jbase/index.md then jbase/ANNA-KNOWLEDGE/index.md (vault root varies)
        for cand in [jbase / "index.md", jbase / "ANNA-KNOWLEDGE" / "index.md"]:
            try:
                jidx = cand.read_text(encoding="utf-8", errors="replace")[:2000]
                jidx_ok = True
                break
            except OSError:
                continue
        if jidx_ok and jidx.strip() and "Total pages: 0" not in jidx:
            journal_extra = jidx.strip()
        else:
            # fallback: today's daily note (also used when index.md missing)
            import datetime
            today = datetime.date.today().isoformat()
            jf = jbase / "10 Daily" / f"{today}.md"
            try:
                journal_extra = jf.read_text(encoding="utf-8", errors="replace")[:2000].strip()
                try:
                    _ = jf.stat()
                except OSError:
                    pass
            except OSError:
                journal_extra = ""
    # T1 hemat: journal 2000c -> 400c Fokus+MIT, skip index kosong
    if journal_extra:
        _lines = []
        for _l in journal_extra.splitlines():
            _s = _l.strip()
            if "Fokus Hari Ini" in _l or _s.startswith("- [ ]") or _s.startswith("- [x]") or _s.startswith(">") or _l.startswith("# ") and "\u2014" in _l:
                _lines.append(_l)
        _c = "\n".join(_lines).strip()[:400]
        journal_extra = _c if _c else journal_extra[:400].strip()
    _idx_text = idx.strip()
    if "Total pages: 0" in _idx_text:
        _idx_text = ""
    parts = ["## ANNA Knowledge Wiki (kompas semantik — bukan sumber angka)"]
    if _idx_text:
        parts.append(_idx_text)
    if alias.strip():
        parts.append("## Alias wilayah (verbatim, filter resmi)\n" + alias.strip())
    if journal_extra:
        parts.append("## Journal (second brain — daily context)\n" + journal_extra)
    parts.append("Aturan pakai wiki: semantik/ontology/alias dari sini; "
                 "angka/fakta selalu dari Business Data Engine. "
                 "Tak ada SQL langsung — larangan tetap.")
    text = "\n\n".join(parts)
    _WIKI_CACHE.update(key=_full_key, text=text)
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

# One continuing Hermes conversation per LOGIN USER until /new.
# Pola resmi Hermes (docs/user-guide/sessions): sesi gateway di-key per-user
# (agent:main:<platform>:<chat>:<user_id>, group_sessions_per_user=true) —
# Alice dan Bob tak berbagi transcript. Dashboard ikut pola itu: SESSION
# adalah dict user_id -> {id, meta}, bukan satu sesi global.
# Key = user_id sesi cookie login (fallback "" = token-only tanpa cookie).
# Diakses dari banyak thread (ThreadingHTTPServer tanpa batas thread):
# _stream_run tulis, /api/session tulis, /api/status baca — lindungi semua.
SESSION: dict = {}
_SESSION_LOCK = threading.Lock()

# Cache transcript sisi server (stabil pasca-restart/gateway-putus).
# Kunci: sid Hermes. Nilai: list [{role, text}] maks 20. Ditulis saat
# complete (user msg + jawaban final), dibaca pertama oleh transcript
# sebelum fallback gateway. Tak pernah raise.
_TRANS = {}
_TRANS_LOCK = threading.Lock()
_TRANS_FILE = ROOT / ".ana_transcript"

def _trans_push(sid, role, text):
    try:
        s = str(sid or "").strip()
        t = str(text or "").strip()
        if not s or not t or role not in ("user", "assistant"):
            return
        with _TRANS_LOCK:
            lst = _TRANS.get(s) or []
            lst.append({"role": role, "text": t[:2000]})
            _TRANS[s] = lst[-20:]
        try:
            with _TRANS_LOCK:
                _TRANS_FILE.write_text(json.dumps({k: v for k, v in _TRANS.items()}), encoding="utf-8")
        except OSError:
            pass
    except Exception:
        pass

def _trans_get(sid):
    try:
        with _TRANS_LOCK:
            lst = list(_TRANS.get(str(sid or "").strip()) or [])
        if lst:
            return {"messages": lst}
    except Exception:
        pass
    return None

def _trans_restore():
    try:
        d = json.loads(_TRANS_FILE.read_text(encoding="utf-8"))
        if isinstance(d, dict):
            with _TRANS_LOCK:
                for k, v in d.items():
                    if isinstance(v, list):
                        _TRANS[str(k)] = [m for m in v if isinstance(m, dict)][:20]
    except (OSError, ValueError):
        pass

_trans_restore()
SESSION_TTL_SEC = int(os.environ.get("ANA_SESSION_TTL", "3600"))  # 1h default
# Sesi ANNA per user: maks 3 sesi Hermes aktif (histori). Login kembali =
# lanjutkan sesi terakhir; /new atau pilih sesi = ganti aktif. Logout TIDAK
# menghapus sesi ANNA (hanya cookie auth) — user hapus manual per sesi.
_ANNA_MAX_SESSIONS = 3

# Live session gateway per user: {user_key: live_sid}.
# Tanpa ini _CURRENT_SESSION_ID global di runtime_gateway dipakai ulang
# lintas user — run user B tanpa sesi aktif masuk ke live session user A
# (transcript campur + rename judul menimpa milik A). Dengan peta ini tiap
# user selalu kirim sid live MILIKNYA eksplisit; run fresh reset global
# dulu agar gateway create baru, bukan resume sesi orang.
_GW_LIVE: dict = {}

# Persist session id+meta per user ke disk agar survive restart server.
# Tanpa ini SESSION in-memory hilang tiap restart dan chat mulai fresh
# padahal Hermes masih punya history-nya.
_SESSION_FILE = ROOT / ".ana_session"


def _anna_user_key(handler=None) -> str:
    """Kunci sesi ANNA = user_id cookie login. "" = token-only tanpa cookie
    (ANNA system/dev — tetap satu sesi netral seperti dulu)."""
    try:
        if handler is not None:
            sess = _session_from_cookie(handler)
            if sess:
                uid = str(sess.get("user_id") or "").strip()
                if uid:
                    return uid
    except Exception:
        pass
    return ""


def _anna_owner_from_request(handler):
    """(owner_key, scope) untuk state chart/report.

    Cookie diprioritaskan (browser user). Fallback: header X-Hermes-Session
    dari tool ANNA — resolve HERMES_SESSION_ID -> user_id via file
    .ana_scope_<sid>.json (ditulis per run, berisi user_id penulis).
    Tanpa keduanya = ("", {}) kanal netral — push berdata DITOLAK 401,
    hanya hide/clear yang boleh.
    Tak pernah raise."""
    try:
        uid = _anna_user_key(handler)
        if uid:
            return uid, _wilayah_scope_from_session(handler)
        if handler is not None:
            try:
                hdrs = getattr(handler, "headers", {}) or {}
                sid = ""
                try:
                    sid = str(hdrs.get("X-Hermes-Session") or "").strip()
                except Exception:
                    sid = ""
                if sid and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sid):
                    p = ROOT / f".ana_scope_{sid}.json"
                    try:
                        d = json.loads(p.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        d = None
                    if isinstance(d, dict) and str(d.get("user_id") or "").strip():
                        scope = {}
                        for k in ("kode_divre", "kode_kph", "kode_bkph", "kode_rph"):
                            v = d.get(k)
                            if v is not None and str(v).strip() != "":
                                scope[k] = str(v).strip()
                        tl = d.get("kode_tpg_list") or []
                        if tl:
                            scope["kode_tpg_list"] = [str(x) for x in tl]
                        return str(d["user_id"]).strip(), scope
            except Exception:
                pass
    except Exception:
        pass
    return "", {}


def _session_save():
    """Persist SESSION per user ke disk agar survive restart server.

    Simpan entri yang punya sesi AKTIF valid ATAU histori non-kosong —
    tanpa ini arsip pasca-+BARU (id=None, histori ada) dibuang dari file
    dan user kehilangan sesi lamanya tiap restart. Tak pernah raise."""
    try:
        with _SESSION_LOCK:
            items = {k: {"id": v.get("id"), "meta": v.get("meta")} for k, v in SESSION.items()}
        valid = {}
        for k, e in items.items():
            try:
                m = e.get("meta") if isinstance(e.get("meta"), dict) else {}
                hist = m.get("sessions") or []
                has_hist = any(isinstance(s, dict) and s.get("id") for s in hist)
                if (e.get("id") and runtime.valid_session(e["id"])) or has_hist:
                    valid[k] = e
            except Exception:
                continue
        if valid:
            _SESSION_FILE.write_text(json.dumps(valid), encoding="utf-8")
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
    if not isinstance(d, dict):
        return
    # Format baru: {user_key: {id, meta}}. Format lama: {id, meta} langsung.
    items = d if all(isinstance(v, dict) and ("id" in v or "meta" in v) for v in d.values()) and "id" not in d else {"": d}
    for key, ent in items.items():
        if not isinstance(ent, dict):
            continue
        # Muat entri ber-aktif-valid ATAU ber-histori (arsip pasca-+BARU:
        # id=None tapi histori ada — tanpa ini arsip hilang tiap restart).
        meta = ent.get("meta") if isinstance(ent.get("meta"), dict) else None
        hist = (meta.get("sessions") or []) if isinstance(meta, dict) else []
        has_hist = any(isinstance(s, dict) and s.get("id") for s in hist)
        if not runtime.valid_session(ent.get("id")) and not has_hist:
            continue
        if isinstance(meta, dict) and not isinstance(meta.get("created"), (int, float)):
            meta["created"] = time.time()  # file lama tanpa stamp: mulai TTL dari restore
        with _SESSION_LOCK:
            SESSION[str(key)] = {"id": (str(ent["id"]) if runtime.valid_session(ent.get("id")) else None), "meta": meta}

def _session_expired(key="") -> bool:
    with _SESSION_LOCK:
        ent = SESSION.get(key) or {}
        meta = ent.get("meta")
    if not isinstance(meta, dict) or "created" not in meta:
        return False
    created = meta.get("created")
    if not isinstance(created, (int, float)):
        return False
    return (time.time() - created) > SESSION_TTL_SEC


def _clear_session(key=None):
    """Kosongkan sesi AKTIF milik key, histori tetap (arsip).

    Dipakai /api/session/archive (+BARU) dan /api/new: sesi lama tetap
    bisa dibuka lagi dari picker; run berikut buat sesi baru. Tanpa
    semantik arsip ini +BARU = dead-end (sesi lama hilang).
    key=None (switch DB) = hanguskan SEMUA (satu-satunya kasus global).
    Tak pernah raise."""
    try:
        with _SESSION_LOCK:
            if key is None:
                SESSION.clear()
            else:
                ent = SESSION.get(key)
                if isinstance(ent, dict):
                    ent["id"] = None
                    SESSION[key] = ent
                else:
                    SESSION.pop(key, None)
        _session_save()
    except Exception:  # noqa: BLE001
        try:
            _session_save()
        except Exception:
            pass
    # P0-A: SESSION id/meta cleared but gateway cached _CURRENT_SESSION_ID
    # persisted -> fresh:true reuse old session. Reset both layers here so
    # every caller (fresh, /api/new, /new, TTL, error) gets true isolation.
    # Per-user: reset gateway hanya bila tak ada sesi user lain yang hidup.
    try:
        with _SESSION_LOCK:
            _still = bool(SESSION)
        if not _still:
            runtime.reset_session()
    except Exception:  # noqa: BLE001
        pass


def _session_get(key=""):
    """Return (sid_aktif, meta_aktif). meta = {title, created, message_count,
    sessions: [{id, title, created, message_count}]} — histori maks 3."""
    with _SESSION_LOCK:
        ent = SESSION.get(key) or {}
        return ent.get("id"), ent.get("meta")


def _session_list(key=""):
    """Histori sesi ANNA milik user (maks 3, terbaru dulu). Tiap item:
    {id, title, created, message_count, active}."""
    with _SESSION_LOCK:
        ent = SESSION.get(key) or {}
        active = ent.get("id")
        meta = ent.get("meta") if isinstance(ent.get("meta"), dict) else {}
        out = []
        for s in (meta.get("sessions") or []):
            if not isinstance(s, dict) or not s.get("id"):
                continue
            out.append({
                "id": str(s["id"]),
                "title": str(s.get("title") or "--"),
                "created": s.get("created") or 0,
                "message_count": int(s.get("message_count") or 0),
                "active": str(s["id"]) == str(active),
            })
        if active and not any(s["id"] == str(active) for s in out):
            out.insert(0, {
                "id": str(active),
                "title": str(meta.get("title") or "--"),
                "created": meta.get("created") or 0,
                "message_count": int(meta.get("message_count") or 0),
                "active": True,
            })
        return out[:_ANNA_MAX_SESSIONS]


def _session_hist_push(key, sid, title=None, origin="run"):
    """Catat sesi ke histori user (maks 3, sid unik, terbaru dulu).

    origin: "run" (sesi lahir dari chat /api/run milik key ini — pemilik
    penuh) atau "claim" (adopsi ID dari store, mis. sesi CLI). Klaim
    silang DITOLAK di endpoint (403), jadi claim di sini hanya untuk
    ID yatim. Origin lama dipertahankan: push ulang entri yang sudah ada
    (mis. re-select) tak mengubah run jadi claim atau sebaliknya.
    Tak pernah raise. Return sid yang tergusur kapasitas (None bila tak ada)."""
    try:
        with _SESSION_LOCK:
            ent = SESSION.get(key) or {}
            meta = ent.get("meta") if isinstance(ent.get("meta"), dict) else {}
            old_origin = ""
            try:
                for _s in (meta.get("sessions") or []):
                    if isinstance(_s, dict) and str(_s.get("id") or "") == str(sid):
                        old_origin = str(_s.get("origin") or "")
                        break
            except Exception:
                pass
            before_ids = [str(_s.get("id")) for _s in (meta.get("sessions") or [])
                          if isinstance(_s, dict) and _s.get("id")]
            hist = [s for s in (meta.get("sessions") or [])
                    if isinstance(s, dict) and s.get("id") and str(s["id"]) != str(sid)]
            now = time.time()
            hist.insert(0, {"id": str(sid), "title": str(title or "--"),
                            "created": now, "message_count": 0,
                            "origin": old_origin or str(origin or "run")})
            meta["sessions"] = hist[:_ANNA_MAX_SESSIONS]
            after_ids = {str(_s.get("id")) for _s in (meta["sessions"] or [])
                         if isinstance(_s, dict) and _s.get("id")}
            evicted = next((i for i in before_ids if i != str(sid) and i not in after_ids), None)
            ent["meta"] = meta
            SESSION[key] = ent
        _session_save()
        return evicted
    except Exception:
        return None


def _session_owners_snapshot():
    """{sid: user_key} untuk semua sesi yang dipegang user mana pun.

    Dipakai gerbang klaim: sid yang sudah dipegang user lain DITOLAK
    untuk diklaim (403), kecuali pemiliknya. Tak pernah raise."""
    try:
        with _SESSION_LOCK:
            out = {}
            for k, ent in SESSION.items():
                try:
                    kk = str(k)
                    e = ent or {}
                    if e.get("id"):
                        out.setdefault(str(e["id"]), kk)
                    m = e.get("meta") if isinstance(e.get("meta"), dict) else {}
                    for s in (m.get("sessions") or []):
                        if isinstance(s, dict) and s.get("id"):
                            out.setdefault(str(s["id"]), kk)
                except Exception:
                    continue
            return out
    except Exception:
        return {}


def _session_hist_drop(key, sid):
    """Hapus satu sesi dari histori user. Return True bila ada yang dibuang."""
    try:
        sid = str(sid or "").strip()
        if not sid:
            return False
        with _SESSION_LOCK:
            ent = SESSION.get(key) or {}
            meta = ent.get("meta") if isinstance(ent.get("meta"), dict) else {}
            hist = [s for s in (meta.get("sessions") or [])
                    if isinstance(s, dict) and str(s.get("id") or "") != sid]
            dropped = len(hist) != len(meta.get("sessions") or [])
            meta["sessions"] = hist[:_ANNA_MAX_SESSIONS]
            if str(ent.get("id") or "") == sid:
                ent["id"] = hist[0]["id"] if hist else None
                if not hist:
                    meta.pop("title", None)
            ent["meta"] = meta
            SESSION[key] = ent
        _session_save()
        return dropped
    except Exception:
        return False


def _session_set(sid, meta=None, key=""):
    with _SESSION_LOCK:
        ent = SESSION.get(key) or {}
        old_meta = ent.get("meta") if isinstance(ent.get("meta"), dict) else {}
        ent["id"] = sid
        if meta is not None:
            new_meta = dict(meta) if isinstance(meta, dict) else {}
            # Pertahankan histori sesi (maks 3) + sinkronkan entri aktif.
            # Origin entri lama dipertahankan (klaim tetap klaim); entri baru
            # dari run = pemilik penuh.
            _old_origin = {}
            try:
                for _s in (old_meta.get("sessions") or []):
                    if isinstance(_s, dict) and _s.get("id"):
                        _old_origin[str(_s["id"])] = str(_s.get("origin") or "run")
            except Exception:
                pass
            hist = [s for s in (old_meta.get("sessions") or [])
                    if isinstance(s, dict) and s.get("id") and str(s["id"]) != str(sid)]
            hist.insert(0, {"id": str(sid),
                            "title": str(new_meta.get("title") or "--"),
                            "created": new_meta.get("created") or time.time(),
                            "message_count": int(new_meta.get("message_count") or 0),
                            "origin": _old_origin.get(str(sid), "run")})
            new_meta["sessions"] = hist[:_ANNA_MAX_SESSIONS]
            ent["meta"] = new_meta
        SESSION[key] = ent
    _session_save()


def _session_bump_count(key=""):
    # Tiap run selesai = aktivitas: refresh TTL agar chat yang hidup tidak
    # diputus tiap 1 jam. Session idle tetap expired via _session_expired.
    with _SESSION_LOCK:
        ent = SESSION.get(key) or {}
        meta = ent.get("meta")
        if isinstance(meta, dict):
            meta["message_count"] = meta.get("message_count", 0) + 1
            meta["created"] = time.time()
            try:
                sid = str(ent.get("id") or "")
                hist = list(meta.get("sessions") or [])
                for s in hist:
                    if isinstance(s, dict) and str(s.get("id") or "") == sid:
                        s["message_count"] = meta["message_count"]
                        s["created"] = meta["created"]
                        break
                meta["sessions"] = hist[:_ANNA_MAX_SESSIONS]
            except Exception:
                pass
            ent["meta"] = meta
            SESSION[key] = ent
    _session_save()

def _session_owned_ids(key=""):
    """Semua ID sesi Hermes milik user: aktif + histori (maks 3).

    Dipakai menutup 3 celah: (1) transcript hanya untuk miliknya, (2)
    /api/sessions difilter miliknya, (3) pilih sesi ditolak bila ID tak ada
    di store Hermes (session_ids) DAN bukan miliknya. Key "" (token-only)
    = pemilik tunggal kanal netral.
    Tak pernah raise."""
    try:
        with _SESSION_LOCK:
            ent = SESSION.get(key) or {}
            active = ent.get("id")
            meta = ent.get("meta") if isinstance(ent.get("meta"), dict) else {}
            hist = meta.get("sessions") or []
        out = set()
        if active:
            out.add(str(active))
        for s in hist:
            if isinstance(s, dict) and s.get("id"):
                out.add(str(s["id"]))
        return out
    except Exception:
        return set()

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
    overlay = "[MODE: asisten] Untuk TTS: ringkas, no markdown/code/tabel. Struktur jawaban: kalimat pembuka MAKSIMAL 1x (jangan diulang), lalu isi (angka + insight), lalu 1 kalimat tawaran lanjut yang relevan (mis. bedah per bulan/petak). Jangan buka dengan filler tanpa isi. DILARANG menarasikan proses di jawaban (jangan tulis 'Siap render.../Menarik data.../Perbaiki autentikasi...') — langsung isi. Semua tool bisnis (call_simoge_packet/call_pandas_tool/show_dashboard/show_on_map/chart/peta/tabel KPI) adalah TOOL BIASA — langsung execute_code TETAP di asisten, tanpa set_mode(coding). Chart/peta/pandas TIDAK butuh coding. TTS-only tanpa visual saat diminta = GAGAL." if mode=="asisten" else "[MODE: coding] Mode agen koding: hanya untuk artifact kode/file. Pertanyaan bisnis tetap di asisten."
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
    def _set_security_headers(self):
        """Set security headers untuk enterprise requirements."""
        # HSTS - Enforce HTTPS (opsional, hanya jika HTTPS enabled)
        if os.environ.get("ANA_HTTPS", "").lower() in ("1", "true", "yes"):
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        # Frame protection - clickjacking
        self.send_header("X-Frame-Options", "DENY")
        # MIME sniffing protection
        self.send_header("X-Content-Type-Options", "nosniff")
        # XSS protection
        self.send_header("X-XSS-Protection", "1; mode=block")
        # Referrer policy
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        # Content-Security-Policy - Permissive untuk awal, bisa diperketat nanti
        # Allow inline scripts/styles untuk legacy compatibility
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://static.cloudflareinsights.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https://server.arcgisonline.com; "
            "font-src 'self' data:; "
            "connect-src 'self' https://server.arcgisonline.com https://static.cloudflareinsights.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        self.send_header("Content-Security-Policy", csp)

    def _json(self, body, code=200):
        import decimal
        def _dec(o):
            if isinstance(o, decimal.Decimal): return float(o)
            raise TypeError
        data = json.dumps(body, default=_dec).encode()
        try:
            self.send_response(code)
            self._set_security_headers()
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

    def _bytes(self, data, ctype, code=200, cache_control="no-store", extra_headers=None):
        # gzip for text assets when client supports it (cuts 772K vendor -> ~210K)
        ctype_low = (ctype or "").split(";")[0].strip().lower()
        compressible = ctype_low in ("text/html","text/css","application/javascript","text/javascript","application/json","application/manifest+json","image/svg+xml","text/plain")
        if compressible and len(data) > 512:
            try:
                ae = (self.headers.get("Accept-Encoding") or "").lower()
                if "gzip" in ae:
                    gz = gzip.compress(data, compresslevel=6)
                    # only use if actually smaller (tiny files may grow)
                    if len(gz) < len(data):
                        data = gz
                        # mark for header below
                        if extra_headers is None:
                            extra_headers = {}
                        extra_headers["Content-Encoding"] = "gzip"
                        extra_headers["Vary"] = "Accept-Encoding"
            except Exception:
                pass
        # ETag for cacheable assets (so 304 works even without explicit If-None-Match handling)
        etag = None
        if cache_control != "no-store" and code == 200 and len(data) > 0:
            try:
                etag = '"' + hashlib.md5(data).hexdigest()[:16] + '"'
                inm = (self.headers.get("If-None-Match") or "").strip()
                if inm and inm == etag:
                    try:
                        self.send_response(304)
                        self.send_header("ETag", etag)
                        self.send_header("Cache-Control", cache_control)
                        self.end_headers()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                    return
            except Exception:
                pass
        try:
            self.send_response(code)
            self._set_security_headers()
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", cache_control)
            if etag:
                self.send_header("ETag", etag)
            if extra_headers:
                for k, v in extra_headers.items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    # Basemap Esri via server (same-origin) — lihat route /api/tiles/esri/.
    _ESRI_TILES = {
        "sat": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "street": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "topo": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        "pencil": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        "ref": "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
    }

    def _serve_esri_tile(self, svc, z, x, y):
        try:
            z, x, y = int(z), int(x), int(y)
        except (TypeError, ValueError):
            return self._bytes(b"koordinat salah", "text/plain", 400)
        if svc not in self._ESRI_TILES or not (0 <= z <= 19) or x < 0 or y < 0 or x >= 2 ** z or y >= 2 ** z:
            return self._bytes(b"not found", "text/plain", 404)
        try:
            import urllib.request
            req = urllib.request.Request(
                self._ESRI_TILES[svc].format(z=z, y=y, x=x),
                headers={"User-Agent": "SIMOGE-HUD/1.0"},
            )
            with urllib.request.urlopen(req, timeout=12) as r:
                data = r.read(2 * 1024 * 1024 + 1)
                if len(data) > 2 * 1024 * 1024:
                    return self._bytes(b"terlalu besar", "text/plain", 502)
                ctype = (r.headers.get("Content-Type") or "image/jpeg").split(";")[0].strip() or "image/jpeg"
                if not ctype.startswith("image/"):
                    return self._bytes(b"bukan gambar", "text/plain", 502)
                return self._bytes(data, ctype, 200, cache_control="public, max-age=86400, immutable")
        except Exception:
            return self._bytes(b"esri tak terjangkau", "text/plain", 502)

    def _serve_pmtiles_file(self, fname):
        # PMTiles v3 via range request (P2-2). Statis, tanpa Martin/tippecanoe.
        # Client (protomaps-leaflet) kirim Range: bytes=a-b; jawab 206 +
        # Content-Range, atau 200 penuh bila tanpa Range.
        # NEW: Jika query param z,x,y diberikan -> ekstrak single MVT tile (bukan byte range).
        # fname allowlist ketat (anti traversal): kph_<kode>/bounds_<divre>/petak.
        if not re.fullmatch(r"(kph_\d+(?:_\d{4})?|bounds_\d+(?:_\d{4})?|overview_\d+(?:_\d{4})?|petak)\.pmtiles", fname or ""):
            return self._json({"error": "nama file tile tidak dikenal"}, 404)
        f = ROOT / "tiles" / fname
        if not f.is_file():
            return self._json({"error": f"{fname} belum dibangun"}, 404)

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

    def _serve_pmtiles(self):
        return self._serve_pmtiles_file("petak.pmtiles")

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
            # Lanjutan ter-scope (best-effort, tak menggugurkan legacy): per-KPH
            # petak + per-DIVRE bounds + manifest. Gagal di sini = legacy tetap ok.
            try:
                scoped = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "build_scoped_tiles.py")],
                    cwd=str(ROOT), capture_output=True, text=True, timeout=600)
                try:
                    out["scoped"] = json.loads(scoped.stdout.strip().splitlines()[-1])
                except Exception:
                    out["scoped"] = {"ok": scoped.returncode == 0,
                                     "tail": (scoped.stdout + scoped.stderr)[-500:]}
            except subprocess.TimeoutExpired:
                out["scoped"] = {"ok": False, "error": "scoped build timeout (>600s)"}
            except Exception as e:  # noqa: BLE001
                out["scoped"] = {"ok": False, "error": str(e)[:200]}
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
        # File ter-scope (kph_*/bounds_*) + manifest — ringkas per pola.
        try:
            _scoped = {}
            for f in sorted((ROOT / "tiles").glob("kph_*.pmtiles")):
                _scoped[f.name] = {"bytes": f.stat().st_size, "mtime": f.stat().st_mtime}
            for f in sorted((ROOT / "tiles").glob("bounds_*.pmtiles")):
                _scoped[f.name] = {"bytes": f.stat().st_size, "mtime": f.stat().st_mtime}
            for f in sorted((ROOT / "tiles").glob("overview_*.pmtiles")):
                _scoped[f.name] = {"bytes": f.stat().st_size, "mtime": f.stat().st_mtime}
            if _scoped:
                st["scoped"] = _scoped
            _mf = ROOT / "tiles" / "manifest.json"
            if _mf.is_file():
                st["manifest"] = {"exists": True, "bytes": _mf.stat().st_size,
                                  "mtime": _mf.stat().st_mtime}
        except OSError:
            pass
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
            raw_cron = [ln for ln in (cr.stdout or "").splitlines()
                        if "ana-hermes-dashboard" in ln and ln.strip()
                        and not ln.strip().startswith("#")]
            # Sederhanakan: hanya jadwal + status, tanpa path demi keamanan
            cron_simple = []
            for ln in raw_cron:
                parts = ln.split()
                sched = " ".join(parts[:5]) if len(parts) >= 5 else ln[:32]
                cron_simple.append(sched)
            st["cron"] = raw_cron
            st["cron_simple"] = cron_simple
            st["cron_status"] = "aktif" if raw_cron else "mati"
        except Exception as e:                        # noqa: BLE001
            st["cron"] = []
            st["cron_simple"] = []
            st["cron_status"] = "mati"
            st["cron_error"] = str(e)[:120]
        try:
            lg = ROOT / "logs" / "refresh_petak.log"
            if lg.is_file():
                with lg.open(encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()
                # Sederhanakan log: buang path absolut, ambil ringkasan saja
                tail = "".join(lines[-8:])[-1200:]
                # Sanitasi path demi keamanan
                import re as _re
                tail = _re.sub(r"/[^\s]*ana-hermes-dashboard[^\s]*", "[app]", tail)
                tail = _re.sub(r"/home/[^\s]+", "[home]", tail)
                # Ringkas: ambil baris berisi kata kunci status saja
                keep_kw = ("OK", "sukses", "berhasil", "gagal", "error", "rebuild", "cron")
                short = [ln for ln in tail.splitlines() if any(k in ln.lower() for k in keep_kw)]
                st["log_tail"] = "\n".join(short[-4:]) if short else tail.strip().splitlines()[-1] if tail.strip() else "(log kosong)"
                st["log_tail"] = st["log_tail"][-600:]
            else:
                st["log_tail"] = "(belum ada log)"
        except OSError as e:
            st["log_tail"] = "(log tak terbaca)"
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

    _CRON_JOBS = {
        # marker: (script, log, jadwal default)
        "ana-pmtiles-daily": ("rebuild_tiles_daily.sh", "refresh_petak.log", "10 6 * * *"),
        "ana-insight-daily": ("rebuild_insight_daily.sh", "insight.log", "0 6 * * *"),
    }

    def _tiles_cron(self, action, schedule="", marker="ana-pmtiles-daily"):
        """status|enable|disable baris cron rebuild harian (generik dua marker).

        Hanya baris ber-marker yang disentuh; cron lain milik user tak diganggu.
        """
        import re as _re
        if marker not in self._CRON_JOBS:
            return self._json({"error": f"marker tak dikenal: {marker!r}"}, 400)
        _script, _logf, _def_sched = self._CRON_JOBS[marker]
        sched = (schedule or "").strip() or _def_sched
        lines, err = self._cron_read()
        if err:
            return self._json({"ok": False, "error": f"crontab -l: {err}"}, 500)
        mine = [ln for ln in lines if marker in ln]
        others = [ln for ln in lines if marker not in ln]
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
            script = ROOT / "scripts" / _script
            logf = ROOT / "logs" / _logf
            entry = (f"{sched} bash {script} >> {logf} 2>&1 "
                     f"# {marker}")
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
        # Reverse-proxy/tunnel domain allowlist (mis. Cloudflare -> localhost:8730).
        extra = {h.strip().lower() for h in os.environ.get("ANA_ALLOWED_HOSTS", "").split(",") if h.strip()}
        bare = host.rsplit(":", 1)[0] if ":" in host else host
        if extra and (host.lower() in extra or bare.lower() in extra):
            return True
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
        # Domain tunnel/proxy resmi (Cloudflare -> localhost) selalu diterima
        # terlepas dari BIND_HOST — request memang tiba via listener lokal.
        # Proteksi utama tetap X-Ana-Token; origin check hanya layer tambahan.
        try:
            o = urlparse(origin)
            if o.scheme == "https" and not o.port:
                extra = {h.strip().lower() for h in os.environ.get("ANA_ALLOWED_HOSTS", "").split(",") if h.strip()}
                host = (o.hostname or "").lower()
                if host and host in extra:
                    return True
        except (ValueError, TypeError):
            pass
        # Localhost-only mode: strict.
        if BIND_HOST == "127.0.0.1":
            return origin in {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}
        # External mode: terima origin apa pun dengan port benar (http/https),
        # atau origin domain tanpa port eksplisit (https baku :443) bila host
        # domainnya ada di ANA_ALLOWED_HOSTS (tunnel/proxy resmi).
        # Proteksi utama tetap X-Ana-Token; origin check hanya layer tambahan.
        try:
            o = urlparse(origin)
            if o.port == PORT and o.scheme in {"http", "https"}:
                return True
            if not o.port and o.scheme == "https":
                extra = {h.strip().lower() for h in os.environ.get("ANA_ALLOWED_HOSTS", "").split(",") if h.strip()}
                host = (o.hostname or "").lower()
                return bool(host and host in extra)
            return False
        except (ValueError, TypeError):
            return False

    def _token_ok(self):
        supplied = self.headers.get("X-Ana-Token", "")
        if supplied and secrets.compare_digest(supplied, API_TOKEN):
            return True
        try:
            if _session_from_cookie(self) is not None:
                return True
        except Exception:
            pass
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
        
        # Anti-scraping: Check suspicious User-Agent (DISABLED for Apache proxy)
        # ua = self.headers.get("User-Agent", "") or ""
        # if auth_local.is_suspicious_user_agent(ua):
        #     ip = _get_client_ip(self)
        #     _alog(f"suspicious ua blocked ip={ip} ua={(ua[:50] if ua else 'empty')}", "warn")
        #     return self._json({"error": "suspicious request"}, 403)
        
        # Anti-scraping: Global rate limit per IP
        ip = _get_client_ip(self)
        allowed, remaining = auth_local.check_global_rate_limit(ip)
        if not allowed:
            _alog(f"global rate limit blocked ip={ip}", "warn")
            self.send_response(429)
            self._set_security_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("X-RateLimit-Remaining", "0")
            self.send_header("Retry-After", str(auth_local._RL_GLOBAL_WINDOW_SECONDS))
            self.end_headers()
            return
        
        p = urlparse(self.path).path
        # Tanpa auth dan TANPA menyentuh token: hanya sinyal "server ini proses
        # yang mana". Frontend poll ini; boot berubah = server restart = token
        # meta di HTML lama sudah basi → reload. Tidak ada cara baca token dari
        # endpoint ini karena respons tak pernah memuat API_TOKEN.
        if p in ("/api/auth/login", "/api/auth/tfa/generate", "/api/auth/refresh") or p.startswith("/api/auth/"):
            pass
        if p == "/api/auth/me":
            sess = _session_from_cookie(self)
            if not sess:
                _st, _bd = _ana_auth_error(self)
                return self._json(_bd, _st)
            try:
                prof = auth_local.fetch_user_profile_by_id(sess.get("user_id"))
            except Exception as e:
                _alog(f"auth me 503 db unreachable {type(e).__name__}", "error")
                return self._json({"error": "database tidak terjangkau (tunnel DB mati?)", "authenticated": False}, 503)
            if not prof:
                return self._json({"error": "profil tidak tersedia"}, 500)
            _me_safe = auth_local.sanitize_profile_for_client(prof)
            try:
                _me_safe["tfa_enforced"] = bool(_tfa_enforced())
            except Exception:
                pass
            # Generate CSRF token for this session
            session_id = sess.get("id") or ""
            csrf_token = auth_local.generate_csrf_token(session_id)
            return self._json({"ok": True, "authenticated": True, "user": _me_safe, "session": {"created": sess.get("created"), "last_seen": sess.get("last_seen")}, "csrf_token": csrf_token})
        if p == "/api/token-status":
            return self._json({"boot": BOOT_ID})
        if p == "/api/landing/insight":
            # Publik pra-login (tanpa token, tanpa sesi): agregat NYATA saja.
            # Rate-limit 30/menit/IP; cache 60 dtk agar DB tak dihantam tiap
            # buka login. Gagal DB = 503 (frontend sembunyikan kartu, bukan
            # angka bohong). Aturan keras #2.
            try:
                ip = (self.client_address[0] if self.client_address else "?")
            except Exception:
                ip = "?"
            if not _landing_rl_ok(ip):
                return self._json({"ok": False, "error": "terlalu banyak permintaan"}, 429)
            now = time.time()
            try:
                if now - _LANDING_CACHE.get("at", 0) < 60 and _LANDING_CACHE.get("data"):
                    return self._json(_LANDING_CACHE["data"])
            except Exception:
                pass
            try:
                data = landing_insight.snapshot()
            except Exception as e:
                return self._json({"ok": False, "error": "data insight belum tersedia"}, 503)
            try:
                _LANDING_CACHE["at"] = now
                _LANDING_CACHE["data"] = data
            except Exception:
                pass
            return self._json(data)
        if p == "/api/public/landing-insights":
            # Engine v1 (Q2: endpoint baru). Baca snapshot file — TANPA query
            # per request. Publik tanpa token. Rate-limit ikut landing.
            try:
                ip = (self.client_address[0] if self.client_address else "?")
            except Exception:
                ip = "?"
            if not _landing_rl_ok(ip):
                return self._json({"ok": False, "status": "error",
                                   "error": "terlalu banyak permintaan"}, 429)
            try:
                snap = insight_build.load_snapshot()
            except Exception:
                snap = None
            if not snap or not snap.get("cards"):
                return self._json({"ok": False, "status": "unavailable",
                                   "error": "data insight belum tersedia"}, 503)
            return self._json({"generated_at": snap.get("generated_at"),
                               "status": "ok",
                               "metric_version": snap.get("metric_version"),
                               "data_terbaru": snap.get("data_terbaru", {}),
                               "scoreboard": snap.get("scoreboard"),
                               "cards": snap.get("cards")})
        if ANA_AUTH_REQUIRED and p in ("/api/status", "/api/voices", "/api/mode"):
            # Bocorkan workdir/profile/model/daftar tools ke LAN tanpa token —
            # kunci ketiganya. Frontend selalu kirim X-Ana-Token (api.headers()),
            # dan flow restart tetap jalan: 401 dari server baru (token baru)
            # memicu reload via `s.error` di main.js. token-status tetap publik
            # (deteksi restart tanpa token). Dev (ANA_AUTH_REQUIRED=0): terbuka.
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
                tools=[],  # kode asli : tools=runtime.hermes_tools_snapshot(), Disable tools snapshot for now (Hermes gateway not configured)
                browser_stt=True,
                browser_tts=True,
                voice_mode="edge",
                voice_id=voice.voice_id(),
                stt="browser",
                tts="edge",
                session=_session_get(_anna_user_key(self))[0]))
        if p == "/api/voices":
            cur = voice.voice_id()
            return self._json(dict(current=cur, agent_name=voice.agent_name(cur), available=voice.available(), voices=voice.curated_voices()))
        if p == "/api/mode":
            return self._json(dict(mode=get_mode()))
        if p == "/api/db-source":
            # Gated: bocorkan has_password saja, bukan password.
            if not self._token_ok():
                return self._unauth()
            try:
                info = db_source.public_info()
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 500)
            return self._json(info)
        # voice metrics endpoint removed (rollback TTS/STT)
        # (GET /api/voice/metrics removed)
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
        if p == "/api/session":
            # GET = daftar sesi ANNA milik user login (maks 3).
            if not self._token_ok():
                return self._unauth()
            _uk = _anna_user_key(self)
            cur_id, cur_meta = _session_get(_uk)
            return self._json({"ok": True, "session": cur_id, "meta": cur_meta,
                               "sessions": _session_list(_uk)})
        if p == "/api/session/transcript":
            if not self._token_ok():
                return self._unauth()
            q = parse_qs(urlparse(self.path).query)
            sid = (q.get("session_id") or [""])[0].strip()
            if not runtime.valid_session(sid):
                return self._json({"messages": [], "error": "session_id tidak valid"}, 400)
            # Celah 1: transcript hanya untuk sesi milik user peminta.
            # Tanpa ini siapa pun bertoken yang menebak ID bisa baca chat orang.
            # Tanpa cookie login = 401 eksplisit (bukan 403 yang menyesatkan).
            _uk = _anna_user_key(self)
            if _uk == "":
                return self._json({"messages": [], "error": "login dulu untuk baca transcript"}, 401)
            if sid not in _session_owned_ids(_uk):
                return self._json({"messages": [], "error": "bukan sesi milik Anda"}, 403)
            # Cache server dulu (stabil pasca-restart/gateway-putus) —
            # baru CLI lalu gateway. Tanpa ini riwayat hilang tiap restart.
            _hit = _trans_get(sid)
            if _hit:
                return self._json(_hit)
            # Dunia ganda: run via gateway (sid 8-hex), transcript CLI hanya
            # kenal sid store format timestamp. Resolve live->stored dulu,
            # CLI kosong/basi -> fallback gateway session.history.
            try:
                sid = runtime.resolve_stored(sid)
            except Exception:
                pass
            _cli = services.session_transcript(
                runtime._hermes_base(), runtime.WORKDIR, sid)
            try:
                _cli_msgs = _cli.get("messages") if isinstance(_cli, dict) else None
            except Exception:
                _cli_msgs = None
            if _cli_msgs:
                return self._json(_cli)
            try:
                _gw = runtime.session_history(sid, limit=20)
            except Exception as e:
                _gw = {"messages": [], "error": str(e)[:200]}
            try:
                _gw_msgs = _gw.get("messages") if isinstance(_gw, dict) else None
            except Exception:
                _gw_msgs = None
            if _gw_msgs:
                return self._json(_gw)
            _err = ""
            try:
                _err = str((_cli or {}).get("error") or (_gw or {}).get("error") or "")[:200]
            except Exception:
                _err = ""
            return self._json({"messages": [], "error": _err or "riwayat kosong"})
        if p == "/api/sessions":
            if not self._token_ok():
                return self._unauth()
            # Celah 2: daftar global difilter ke milik user (judul tak bocor).
            # Token-only tanpa cookie (ANNA system) = kanal netral, tetap utuh.
            _uk = _anna_user_key(self)
            _own = _session_owned_ids(_uk)
            _allow = None if (_uk == "" and not _own) else _own
            _lst = services.list_sessions(
                runtime._hermes_base(), runtime.WORKDIR, runtime.valid_session, _session_get(_uk)[0],
                allowed=_allow)
            # Sinkron penuh: live gateway session (8-hex) menumpang di daftar
            # bila stored-nya belum ada — tanpa ini sesi aktif tak terlihat.
            try:
                _cur = str(_session_get(_uk)[0] or "")
                if _cur and isinstance(_lst, dict):
                    _seen = set()
                    for _g in ((_lst.get("groups") or {}).values()):
                        for _it in (_g or []):
                            if isinstance(_it, dict) and _it.get("id"):
                                _seen.add(str(_it["id"]))
                    if _cur not in _seen:
                        _st = None
                        try:
                            _st = runtime.resolve_stored(_cur)
                        except Exception:
                            _st = None
                        if not _st or _st == _cur or _st not in _seen:
                            _grps = _lst.get("groups") or {}
                            _today = _grps.get("today") or []
                            _today.insert(0, {"id": _cur, "title": "Sesi aktif", "last_active": "now"})
                            _grps["today"] = _today
                            _lst["groups"] = _grps
            except Exception:
                pass
            return self._json(_lst)
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
            _ow, _ = _anna_owner_from_request(self)
            return self._json(map_store.get_state(owner=_ow))
        if p == "/api/map/queue":
            if not self._token_ok():
                return self._unauth()
            _ow, _ = _anna_owner_from_request(self)
            return self._json({"commands": map_store.take_pending(owner=_ow)})
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
            _ow, _ = _anna_owner_from_request(self)
            return self._json(map_store.get_result(cmd_id, owner=_ow))
        if p == "/api/spatial/chart":
            if not self._token_ok():
                return self._unauth()
            _ow, _ = _anna_owner_from_request(self)
            return self._json(dict(ok=True, **spatial_chart_store.get_state(owner=_ow)))
        if p == "/api/metabase/status":
            if not self._token_ok():
                return self._unauth()
            if metabase is None:
                return self._json(_metabase_503(), 503)
            return self._json(metabase.status())
        if p == "/api/metabase/dashboards":
            if not self._token_ok():
                return self._unauth()
            if metabase is None:
                return self._json(_metabase_503(), 503)
            return self._json(metabase.list_dashboards())
        if p.startswith("/api/metabase/card/"):
            if not self._token_ok():
                return self._unauth()
            try:
                cid = int(p.rsplit("/", 1)[-1].split("?")[0])
            except ValueError:
                return self._json({"ok": False, "error": "card id harus angka"}, 400)
            if metabase is None:
                return self._json(_metabase_503(), 503)
            return self._json(metabase.get_card(cid))
        if p == "/api/spatial/report":
            if not self._token_ok():
                return self._unauth()
            _ow, _ = _anna_owner_from_request(self)
            return self._json(dict(ok=True, **spatial_report_store.get_state(owner=_ow)))
        if p == "/api/spatial/archive":
            if not self._token_ok():
                return self._unauth()
            _ow, _ = _anna_owner_from_request(self)
            if not _ow:
                return self._json({"ok": False, "error": "arsip wajib lewat sesi user login"}, 401)
            return self._json({"ok": True,
                               "items": spatial_archive_store.list_archive(owner=_ow)})
        if p == "/api/tpl":
            # Template pertanyaan per-user: default bawaan, bisa edit penuh.
            if not self._token_ok():
                return self._unauth()
            _ow, _ = _anna_owner_from_request(self)
            if not _ow:
                return self._json({"ok": False, "error": "template wajib lewat sesi user login"}, 401)
            return self._json({"ok": True,
                               "groups": tpl_store.list_tpl(owner=_ow)})
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
            # Kunci scope: sesi user ber-scope sempit dilarang ambil file
            # global (pakai /api/tiles/scope/). Tanpa sesi (sistem/token-only,
            # mis. ANNA) = lolos seperti dulu. Klien dashboard sudah migrasi.
            try:
                _sess = _session_from_cookie(self)
            except Exception:
                _sess = None
            if _sess:
                try:
                    _jj = _sess.get("jabatan")
                    _jab = (str(_jj.get("kode_jabatan") or "").strip().upper()
                            if isinstance(_jj, dict) else str(_jj or "").strip().upper())
                except Exception:
                    _jab = ""
                if _jab not in ("DIREKSI", "ADMINISTRATOR"):
                    try:
                        _sc = _wilayah_scope_from_session(self)
                    except Exception:
                        _sc = {}
                    if any(_sc.get(k) for k in ("kode_divre", "kode_kph", "kode_bkph", "kode_rph")) or _sc.get("kode_tpg_list"):
                        return self._json({"error": "di luar scope tile — pakai file scope (/api/tiles/scope/)"}, 403)
            return self._serve_pmtiles()
        if p.startswith("/api/tiles/scope/"):
            # File tile ter-scope jabatan: kph/<kode>.pmtiles | bounds_<divre>.pmtiles
            # | overview_<divre>.pmtiles (berwarna, DIVRE ke atas saja).
            # Auth ganda: token (atau ?token=, tile fetch tak bisa header) DAN
            # sesi login dalam scope (fail-closed untuk user ber-scope).
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
            _rest = (p or "")[len("/api/tiles/scope/"):]
            _m1 = re.fullmatch(r"kph/(\d+)(?:_(\d{4}))?\.pmtiles", _rest or "")
            _m2 = re.fullmatch(r"bounds_(\d+)(?:_(\d{4}))?\.pmtiles", _rest or "")
            _m3 = re.fullmatch(r"overview_(\d+)(?:_(\d{4}))?\.pmtiles", _rest or "")
            if _m3:
                _kind, _kode, _yr = "overview", _m3.group(1), _m3.group(2)
                _fname = "overview_%s%s.pmtiles" % (_kode, ("_" + _yr) if _yr else "")
                if not _yr:
                    for _cand in sorted((ROOT / "tiles").glob("overview_%s_*.pmtiles" % _kode)):
                        _fname = _cand.name
                        break
                    else:
                        _fname = "overview_%s.pmtiles" % _kode
            elif _m1:
                _kind, _kode = "kph", _m1.group(1)
                _yr = _m1.group(2)
                _qyr = ""
                try:
                    _qyr = (parse_qs(urlparse(self.path).query).get("tahun", [""])[0] or "").strip()
                except Exception:
                    _qyr = ""
                if not _yr:
                    _yr = _qyr if re.fullmatch(r"\d{4}", _qyr or "") else ""
                _fname = "kph_%s%s.pmtiles" % (_kode, ("_" + _yr) if _yr else "")
                if not (ROOT / "tiles" / _fname).is_file():
                    for _cand in sorted((ROOT / "tiles").glob("kph_%s_*.pmtiles" % _kode)):
                        _fname = _cand.name
                        break
                    else:
                        _fname = "kph_%s.pmtiles" % _kode
            elif _m2:
                _kind, _kode = "divre", _m2.group(1)
                _yr = _m2.group(2)
                _fname = "bounds_%s%s.pmtiles" % (_kode, ("_" + _yr) if _yr else "")
                if not _yr:
                    for _cand in sorted((ROOT / "tiles").glob("bounds_%s_*.pmtiles" % _kode)):
                        _fname = _cand.name
                        break
                    else:
                        _fname = "bounds_%s.pmtiles" % _kode
            else:
                return self._json({"error": "jalur tile scope tidak dikenal"}, 404)
            _ok, _msg = _tiles_scope_ok(self, _kind, _kode)
            if not _ok:
                try:
                    _alog(f"tiles scope DENY {_kind}={_kode[:16]} ({_msg})", "warn")
                except Exception:
                    pass
                return self._json({"error": _msg or "di luar scope tile"}, 403)
            return self._serve_pmtiles_file(_fname)
        if p == "/api/tiles/bounds_geo":
            # Geometri outline KPH (dissolve, BUKAN batas resmi) sebagai GeoJSON
            # ringan untuk choropleth overview — transport terverifikasi ganti
            # tile bila paint vector bermasalah. Sumber: tiles/bounds_*.ndjson.
            # Auth ganda: token + sesi dalam scope (fail-closed).
            if not self._token_ok():
                return self._unauth()
            try:
                _qs = parse_qs(urlparse(self.path).query)
                _dv = (_qs.get("divre", [""])[0] or "").strip()
            except Exception:
                _dv = ""
            if not re.fullmatch(r"\d+", _dv or ""):
                return self._json({"error": "param divre wajib (angka)"}, 400)
            _ok, _msg = _tiles_scope_ok(self, "divre", _dv)
            if not _ok:
                return self._json({"error": _msg or "di luar scope tile"}, 403)
            try:
                _bf = ROOT / "tiles" / ("bounds_%s.ndjson" % _dv)
                if not _bf.is_file():
                    for _cand in sorted((ROOT / "tiles").glob("bounds_%s_*.ndjson" % _dv)):
                        _bf = _cand
                        break
                if not _bf.is_file():
                    return self._json({"ok": True, "features": [], "note": "bounds belum dibangun"})
                feats = []
                for _ln in _bf.read_text(encoding="utf-8").splitlines():
                    _ln = _ln.strip()
                    if not _ln:
                        continue
                    try:
                        _d = json.loads(_ln)
                        _g, _pr = _d.get("geometry"), _d.get("properties") or {}
                        if isinstance(_g, dict) and _g.get("type") in ("Polygon", "MultiPolygon"):
                            feats.append({"type": "Feature", "geometry": _g,
                                          "properties": {"kode_kph": str(_pr.get("kode_kph") or ""),
                                                         "kph": str(_pr.get("kph") or ""),
                                                         "kode_divre": str(_pr.get("kode_divre") or _dv)}})
                    except Exception:
                        continue
                return self._json({"ok": True, "features": feats})
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 500)
        if p == "/api/tiles/manifest":
            # Inventory file tile, disaring ke scope sesi (tanpa sesi = utuh).
            if not self._token_ok():
                return self._unauth()
            try:
                _mf = ROOT / "tiles" / "manifest.json"
                _data = json.loads(_mf.read_text(encoding="utf-8")) if _mf.is_file() else {"files": []}
            except Exception:
                _data = {"files": []}
            try:
                _sess = _session_from_cookie(self)
            except Exception:
                _sess = None
            if _sess and isinstance(_data.get("files"), list):
                _kept = []
                for _e in _data["files"]:
                    _scp = (_e or {}).get("scope") or {}
                    _lv = str(_scp.get("level") or "")
                    # File overview berwarna = DIVRE ke atas saja (ADM ditolak
                    # tegas walau se-divre) — aturan sama seperti endpoint.
                    if str(_scp.get("kind") or "") == "overview":
                        _ok, _ = _tiles_scope_ok(self, "overview", str(_scp.get("kode") or ""))
                        if not _ok:
                            continue
                    elif _lv in ("kph", "divre"):
                        _ok, _ = _tiles_scope_ok(self, _lv, str(_scp.get("kode") or ""))
                        if not _ok:
                            continue
                    _kept.append(_e)
                _data = dict(_data)
                _data["files"] = _kept
            return self._json(_data)
        if p == "/api/tiles/rebuild":
            if not self._token_ok():
                return self._unauth()
            return self._rebuild_pmtiles()
        if p == "/api/tiles/status":
            if not self._token_ok():
                return self._unauth()
            return self._tiles_status()
        if p.startswith("/api/tiles/esri/"):
            # Basemap Esri via server (same-origin): klien yang diblokir
            # adblock/DNS tetap dapat ubin tanpa error console. BUKAN proxy
            # terbuka: 3 service whitelist + koordinat int tervalidasi,
            # tanpa query diteruskan. Publik (citra basemap memang publik).
            parts = p[len("/api/tiles/esri/"):].split("/")
            if len(parts) == 4:
                return self._serve_esri_tile(parts[0], parts[1], parts[2], parts[3])
            return self._bytes(b"not found", "text/plain", 404)
        if p == "/api/layout":
            if not self._token_ok():
                return self._unauth()
            # FASE 2 per-user slot: sesi login -> layout_<uid>.json (v3
            # {v,locked,disabled,desktop:{layouts},mobile:{layouts}}). Tanpa
            # sesi (token global) -> layout.json lama read-only.
            sess = _session_from_cookie(self)
            if sess and sess.get("user_id"):
                return self._json(_layout_load_for_uid(str(sess["user_id"])))
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
        if ANA_AUTH_REQUIRED and p in ("/", "/index.html"):
            if _session_from_cookie(self) is None and not self._token_ok():
                self.send_response(302)
                self.send_header("Location", "/login.html")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
        if p in ("/login.html", "/login.js", "/login.css") or p.startswith("/src/login"):
            pass
        elif p == "/switch":
            # Consume tautan QR pindah perangkat: token dibakar DULU (di bawah
            # lock) baru sesi dibuat — dua scan bersamaan = satu menang, satu
            # ke login + pesan. Sesi baru pending_bind (diikat device mobile
            # saat kontak pertama). create_session otomatis evict perangkat
            # lama (aturan 1-perangkat utuh = ini PINDAH, bukan ganda).
            try:
                qs = parse_qs(urlparse(self.path).query)
                tok = (qs.get("t", [""])[0] or "").strip()
            except Exception:
                tok = ""
            rec = None
            if tok and len(tok) <= 128:
                with _SWITCH_LOCK:
                    rec = _SWITCH_TOKENS.pop(tok, None)
                    if rec is not None:
                        try:
                            if time.time() - float(rec.get("created", 0)) > _SWITCH_TTL:
                                rec = None
                        except Exception:
                            rec = None
            if not rec or not rec.get("uid"):
                self.send_response(302)
                self.send_header("Location", "/login.html?err=switch")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            ua = self.headers.get("User-Agent", "") or ""
            ip = self.client_address[0] if self.client_address else "unknown"
            try:
                sid, _, evicted, _ = auth_local.create_session(
                    rec.get("profile") or {}, ua, ip, "", pending_bind=True)
            except Exception:
                self.send_response(302)
                self.send_header("Location", "/login.html?err=switch")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            _alog(f"auth switch-consume ok user={str(rec.get('uid') or '')[:8]} evicted_lama={bool(evicted)}", "info")
            self.send_response(302)
            _set_session_cookie(self, sid, "")
            self.send_header("Location", "/")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        elif ANA_AUTH_REQUIRED and p.startswith("/api/") and not p.startswith("/api/auth/") and p not in ("/api/token-status",):
            if not self._token_ok():
                return self._unauth()
            # API rate limiting for authenticated requests
            sess = _session_from_cookie(self)
            if sess:
                session_id = sess.get("id") or ""
                allowed, remaining = auth_local.check_api_rate_limit(session_id)
                if not allowed:
                    _alog(f"api 429 rate-limit session={session_id[:8]} path={p}", "warn")
                    self.send_response(429)
                    self._set_security_headers()
                    self.send_header("Content-Type", "application/json")
                    self.send_header("X-RateLimit-Remaining", "0")
                    self.send_header("Retry-After", str(auth_local._RL_API_WINDOW_SECONDS))
                    self.end_headers()
                    return
        # Default: resolve file path
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
        # smart mime: .webmanifest must be manifest+json, .js -> javascript
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        if f.suffix == ".webmanifest":
            ctype = "application/manifest+json"
        elif f.suffix == ".js":
            ctype = "application/javascript"
        data = f.read_bytes()
        if rel == "index.html":
            data = data.replace(b"__ANA_TOKEN__", API_TOKEN.encode())
            # Base URL foto Directus server (popup pin aktivitas, opsi langsung).
            # Publik tanpa kredensial — hanya host, bukan secret.
            try:
                _durl = (os.environ.get("DIRECTUS_URL") or "https://sandbox2.kphbwb.web.id").strip().rstrip("/")
            except Exception:
                _durl = "https://sandbox2.kphbwb.web.id"
            data = data.replace(b"__ANA_DIRECTUS_URL__", _durl.encode())
        # ── cache policy ──
        # HTML navigations: no-store (must revalidate token), SW: no-cache (update fast)
        # versioned/hashed vendor & styles: immutable 1y, icons/assets: 1y, else 1h
        extra = None
        if rel in ("index.html", "login.html") or rel == "":
            cc = "no-store, no-cache, must-revalidate"
        elif rel == "sw.js":
            cc = "no-cache"
            extra = {"Service-Worker-Allowed": "/"}
        elif rel.startswith("vendor/") or rel.startswith("styles/") or rel.startswith("icons/") or rel.startswith("assets/"):
            cc = "public, max-age=31536000, immutable"
        elif f.suffix in (".js", ".css", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff", ".woff2", ".svg"):
            cc = "public, max-age=3600"
        else:
            cc = "public, max-age=3600"
        # manifest must be cacheable but not immutable (Chrome checks every install)
        if rel in ("manifest.webmanifest", "manifest.json"):
            cc = "public, max-age=3600"
            if ctype == "application/octet-stream":
                ctype = "application/manifest+json"
        return self._bytes(data, ctype, cache_control=cc, extra_headers=extra)

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
        if not self._host_ok():
            return self._json({"error": "request origin rejected"}, 403)
        
        # Anti-scraping: Check suspicious User-Agent (DISABLED for Apache proxy)
        # ua = self.headers.get("User-Agent", "") or ""
        # if auth_local.is_suspicious_user_agent(ua):
        #     ip = _get_client_ip(self)
        #     _alog(f"suspicious ua blocked POST ip={ip} ua={(ua[:50] if ua else 'empty')}", "warn")
        #     return self._json({"error": "suspicious request"}, 403)
        
        # Anti-scraping: Global rate limit per IP
        ip = _get_client_ip(self)
        allowed, remaining = auth_local.check_global_rate_limit(ip)
        if not allowed:
            _alog(f"global rate limit blocked POST ip={ip}", "warn")
            self.send_response(429)
            self._set_security_headers()
            self.send_header("Content-Type", "application/json")
            self.send_header("X-RateLimit-Remaining", "0")
            self.send_header("Retry-After", str(auth_local._RL_GLOBAL_WINDOW_SECONDS))
            self.end_headers()
            return
        # /api/auth/* adalah entry-point login: browser fetch selalu kirim Origin,
        # tapi curl/ health-check tanpa Origin tetap harus lulus host-check saja.
        if not p.startswith("/api/auth/") and not self._origin_ok():
            return self._json({"error": "request origin rejected"}, 403)
        # Auth endpoints are public (login) or cookie-authenticated (logout/refresh/tfa/me)
        # — they must not require X-Ana-Token
        if p.startswith("/api/auth/"):
            # handled below after body is read (no X-Ana-Token needed)
            pass
        elif not self._token_ok():
            return self._unauth()
        # CSRF validation for state-changing POST requests (non-auth) - DISABLED for now
        # elif p not in ("/api/auth/login", "/api/auth/tfa/generate", "/api/auth/refresh"):
        #     sess = _session_from_cookie(self)
        #     if sess:
        #         session_id = sess.get("id") or ""
        #         csrf_token = self.headers.get("X-CSRF-Token", "")
        #         if not auth_local.validate_csrf_token(session_id, csrf_token):
        #             _alog(f"csrf validation failed session={session_id[:8]} path={p}", "warn")
        #             return self._json({"error": "invalid csrf token"}, 403)
        ctype = self.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if p in {"/api/run", "/api/speak", "/api/new", "/api/cancel"} and ctype != "application/json":
            return self._json({"error": "application/json required"}, 415)
        # /api/stt removed (server-side STT rollback)
        try:
            raw = self._read(MAX_JSON_BODY)
        except (TypeError, ValueError):
            return self._json({"error": "request body too large"}, 413)
        if ctype == "application/json":
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            if not isinstance(body, dict):
                return self._json({"error": "body must be a JSON object"}, 400)
        else:
            body = {}
        # ── Local Auth (internal DB, public + cookie) ─────────────
        if p == "/api/auth/login":
            ip = self.client_address[0] if self.client_address else "unknown"
            email = (body.get("email") or "").strip() if isinstance(body, dict) else ""
            if not auth_local.check_rate_limit(ip):
                _alog(f"auth login 429 rate-limit ip={ip} email={(email or '')[:32]}", "warn")
                return self._json({"error": "terlalu banyak percobaan, tunggu 1 menit"}, 429)
            password = body.get("password") or ""
            otp = (body.get("otp") or "").strip() or None
            if not email or not password:
                _alog(f"auth login 400 missing field ip={ip} email={(email or '')[:32]}", "warn")
                return self._json({"error": "email dan password wajib"}, 400)
            # Watchdog dulu: source remote tapi tunnel mati = fallback lokal
            # darurat agar dashboard tetap bisa login (tanpa hapus sesi).
            try:
                wd = db_source.watchdog_tick()
                if wd.get("source") == "remote" and not wd.get("tunnel"):
                    db_source.set_source("local")
                    _alog("db watchdog: tunnel remote mati -> fallback lokal (darurat)", "error")
            except Exception:
                pass
            try:
                row = auth_local.get_user_by_email(email)
            except Exception as e:
                _alog(f"auth login 503 db unreachable {type(e).__name__} email={(email or '')[:32]}", "error")
                return self._json({"error": "database tidak terjangkau — cek DB lokal (port 3306) lalu coba lagi"}, 503)
            try:
                _h = (row.get("password","") or "") if row else ""
                _pw_len = len(password)
                _h_len = len(_h)
                _h_pre = _h[:18] if _h else "-"
                _pw_pre = password[:2] + "*"*(max(0,_pw_len-2)) if _pw_len else "-"
                _ver = False
                _ver_err = ""
                if row and _h and _ARGON2_AVAILABLE and _h.startswith("$argon2"):
                    try:
                        _ph=_ArgonPH()
                        _ph.verify(_h, password)
                        _ver=True
                    except (_ArgonVME, _ArgonIH, _ArgonIHE) as e:
                        _ver_err=type(e).__name__
                    except Exception as e:
                        _ver_err=type(e).__name__+":"+str(e)[:60]
                elif row and _h:
                    try:
                        _ver = bool(auth_local.verify_password(_h, password))
                        if not _ver:
                            _ver_err = "VerifyMismatch"
                    except Exception as e:
                        _ver_err=type(e).__name__+":"+str(e)[:60]
                _alog(f"auth login DBG email={email[:32]} ip={ip} found={bool(row)} h_len={_h_len} h_pre={_h_pre} pw_len={_pw_len} pw_pre={_pw_pre} ver={_ver} err={_ver_err}", "warn")
            except Exception as _e:
                _alog(f"auth login DBG err {type(_e).__name__}:{str(_e)[:80]}", "warn")
            if not row or not auth_local.verify_password(row.get("password","") or "", password):
                _alog(f"auth login 401 bad credentials email={email[:32]} ip={ip} found={bool(row)}", "warn")
                return self._json({"error": "email atau password salah"}, 401)
            prof = auth_local.fetch_user_profile_by_id(row["id"])
            if not prof:
                _alog(f"auth login 500 profil gagal email={email[:32]} ip={ip}", "error")
                return self._json({"error": "gagal ambil profil user"}, 500)
            if prof.get("status") and prof.get("status") != "active":
                _alog(f"auth login 403 status={prof.get('status')} email={email[:32]} ip={ip}", "warn")
                return self._json({"error": "akun tidak aktif"}, 403)
            hud = prof.get("hud_access")
            hud_ok = bool(int(hud) if isinstance(hud, (int, float)) or (isinstance(hud, str) and hud.isdigit()) else hud) if hud is not None else False
            has_hud_field = "hud_access" in prof
            if has_hud_field and not hud_ok:
                _alog(f"auth login 403 hud_access=0 email={email[:32]} ip={ip}", "warn")
                return self._json({"error": "akun tidak punya akses HUD (hud_access=0) \u2014 hubungi admin"}, 403)
            is_2fa = False
            if "2fa" in prof:
                try: is_2fa = bool(int(prof.get("2fa") or 0))
                except: is_2fa = bool(prof.get("2fa"))
            else:
                is_2fa = bool(prof.get("tfa_secret"))
            secret = (prof.get("2fa_secret") or "").strip() if isinstance(prof.get("2fa_secret"), str) else ""
            # Saklar 2FA via env (ANA_2FA_ENABLED): 0 = OTP tak pernah diminta,
            # password saja lolos + UI lewati enroll. Default 1 = perilaku lama.
            _tfa_on = _tfa_enforced()
            if is_2fa and _tfa_on:
                if not otp:
                    _alog(f"auth login 401 otp_required email={email[:32]} ip={ip}", "warn")
                    return self._json({"error": "otp_required", "message": "kode 2FA diperlukan"}, 401)
                if not secret:
                    _alog(f"auth login 500 2fa secret kosong email={email[:32]} ip={ip}", "error")
                    return self._json({"error": "2FA aktif tapi secret kosong \u2014 hubungi admin untuk reset 2fa_secret"}, 500)
                if not auth_local.totp_verify(secret, otp):
                    _alog(f"auth login 401 otp salah/kadaluarsa email={email[:32]} ip={ip}", "warn")
                    return self._json({"error": "kode 2FA salah atau kadaluarsa"}, 401)
            ua = self.headers.get("User-Agent","") or ""
            did = _ana_device_id(self)
            sid, sess, evicted, evict_info = auth_local.create_session(prof, ua, ip, did)
            if evicted:
                # Switch perangkat: batalkan run aktif user ini agar slot
                # _RUN_BY_USER[user] bebas detik itu juga (tanpa nunggu 300s).
                # Hanya milik user ini — user lain tak tersentuh.
                try:
                    _uk_ev = str(sess.get("user_id") or "").strip()
                    if _uk_ev:
                        _sid_ev, _ = _session_get(_uk_ev)
                        runtime.cancel_active(_sid_ev)
                        with RUN_STATE_GUARD:
                            _RUN_BY_USER.pop(_uk_ev, None)
                        _log_to_file(f"[auth] switch device: user={_uk_ev[:8]} evicted={len(evicted)} run dibatalkan")
                except Exception:
                    pass
            _alog(f"auth login 200 ok email={email[:32]} ip={ip} evicted={bool(evicted)}", "info")
            safe = auth_local.sanitize_profile_for_client(prof)
            try:
                safe["tfa_enforced"] = bool(_tfa_on)
            except Exception:
                pass
            body_out = json.dumps({"ok": True, "user": safe, "evicted": bool(evicted),
                                   "tfa_enforced": bool(_tfa_on),
                                   "evict": evict_info or {}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_out)))
            self.send_header("Cache-Control", "no-store")
            _set_session_cookie(self, sid, did)
            self.end_headers()
            self.wfile.write(body_out)
            return
        if p == "/api/auth/refresh":
            raw_ck = self.headers.get("Cookie","")
            sid = _parse_cookies(raw_ck).get("ana_session","").strip()
            if not sid:
                return self._json({"error": "tidak ada sesi"}, 401)
            refreshed, err = auth_local.refresh_session(sid)
            if not refreshed:
                body_out = json.dumps({"error": err or "sesi habis"}).encode()
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body_out)))
                _clear_session_cookie(self)
                self.end_headers()
                self.wfile.write(body_out)
                return
            body_out = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_out)))
            try:
                _did_keep = _parse_cookies(raw_ck).get("ana_device", "").strip()[:64]
            except Exception:
                _did_keep = ""
            _set_session_cookie(self, sid, _did_keep)
            self.end_headers()
            self.wfile.write(body_out)
            return
        if p == "/api/auth/logout":
            raw_ck = self.headers.get("Cookie","")
            sid = _parse_cookies(raw_ck).get("ana_session","").strip()
            if sid:
                auth_local.destroy_session(sid)
            # Logout TIDAK menghapus sesi ANNA: login kembali lanjutkan sesi
            # terakhir sampai user /new atau pilih sesi lain. Hanya cookie auth
            # yang dibuang; histori ANNA (maks 3/user) tetap persisten.
            try:
                _anna_scope_prune()
            except Exception:
                pass
            body_out = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_out)))
            _clear_session_cookie(self)
            self.end_headers()
            self.wfile.write(body_out)
            return
        # ── Switch perangkat via QR (tanpa login ulang) ──
        # Token satu-pakai, TTL 120 dtk, burn-di-bawah-lock SEBELUM buat sesi.
        # Mint wajib sesi valid (delegasi auth, bukan bypass). Consume memakai
        # create_session sehingga aturan 1-perangkat (evict) tetap berlaku.
        if p == "/api/auth/switch-mint":
            sess = _session_from_cookie(self)
            if not sess:
                return self._json({"error": "login dulu"}, 401)
            uid = str(sess.get("user_id") or "")
            if not uid:
                return self._json({"error": "sesi tak valid"}, 401)
            try:
                origin = (body.get("origin") or "") if isinstance(body, dict) else ""
                ou = urlparse(str(origin or "").strip())
                if ou.scheme not in ("http", "https") or not ou.hostname:
                    raise ValueError("origin")
                host_hdr = (self.headers.get("Host", "") or "").split(":")[0].strip().lower()
                if (ou.hostname or "").lower() != host_hdr or "@" in (ou.netloc or ""):
                    raise ValueError("origin")
                base = ou.scheme + "://" + ou.hostname + ((":" + str(ou.port)) if ou.port else "")
            except Exception:
                return self._json({"error": "origin tak valid"}, 400)
            now_sw = time.time()
            with _SWITCH_LOCK:
                try:
                    for tk, rec in list(_SWITCH_TOKENS.items()):
                        if now_sw - float(rec.get("created", 0)) > _SWITCH_TTL:
                            _SWITCH_TOKENS.pop(tk, None)
                except Exception:
                    pass
                try:
                    if now_sw - float(_SWITCH_COOLDOWN.get(uid, 0)) < _SWITCH_COOLDOWN_SEC:
                        return self._json({"error": "tunggu sebentar sebelum QR baru"}, 429)
                except Exception:
                    pass
                _SWITCH_COOLDOWN[uid] = now_sw
                tok = secrets.token_urlsafe(32)
                prof = {k: sess.get(k) for k in (
                    "id", "email", "first_name", "last_name", "role", "jabatan",
                    "kode_divre", "kode_kph", "kode_bkph", "kode_rph", "kode_tpg",
                    "hud_access", "panel_access", "tfa_enabled", "2fa")}
                prof["id"] = uid
                _SWITCH_TOKENS[tok] = {"uid": uid, "profile": prof, "created": now_sw}
            _alog(f"auth switch-mint ok user={uid[:8]}", "info")
            return self._json({"ok": True, "token": tok,
                               "url": base + "/switch?t=" + tok,
                               "expires_in": _SWITCH_TTL})
        if p == "/api/auth/bind-device":
            sess = _session_from_cookie(self)
            if not sess:
                return self._json({"error": "login dulu"}, 401)
            try:
                did = (body.get("did") or "") if isinstance(body, dict) else ""
            except Exception:
                did = ""
            ua = self.headers.get("User-Agent", "") or ""
            if not auth_local.bind_session_device(sess.get("id"), did, ua):
                return self._json({"error": "sesi sudah terikat / did tak valid"}, 403)
            _alog(f"auth bind-device ok user={str(sess.get('user_id') or '')[:8]}", "info")
            # Cookie mirror DITULIS manual (send_header langsung) karena
            # _set_session_cookie mendahului baris status bila dipanggil
            # sebelum _json — urutan header HTTP wajib: status dulu.
            body_out = json.dumps({"ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body_out)))
            _set_session_cookie(self, sess.get("id"), did)
            self.end_headers()
            try:
                self.wfile.write(body_out)
            except Exception:
                pass
            return
        if p == "/api/auth/tfa/generate":
            sess = _session_from_cookie(self)
            if not sess:
                return self._json({"error": "login dulu"}, 401)
            password = body.get("password") or ""
            if not password:
                return self._json({"error": "password wajib"}, 400)
            # verifikasi password lokal
            prof_check = auth_local.fetch_user_profile_by_id(sess.get("user_id"))
            email_check = (prof_check or {}).get("email") or sess.get("email")
            row_check = auth_local.get_user_by_email(email_check) if email_check else None
            if not row_check or not auth_local.verify_password(row_check.get("password","") or "", password):
                return self._json({"error": "password salah"}, 401)
            # generate secret custom
            secret = auth_local._b32_secret(20)
            otpauth = auth_local.totp_otpauth_url(secret, email_check, issuer="ANA HUD")
            # simpan pending di sesi server (tidak tulis DB sampai verify)
            try:
                import json as _js
                db = auth_local._load_sessions()
                cur = db.get(sess.get("id"))
                if cur is not None:
                    cur["_pending_2fa_secret"] = secret
                    db[sess.get("id")] = cur
                    auth_local._save_sessions(db)
            except: pass
            return self._json({"data": {"secret": secret, "otpauth_url": otpauth}})
        if p == "/api/auth/tfa/enable":
            sess = _session_from_cookie(self)
            if not sess:
                return self._json({"error": "login dulu"}, 401)
            secret = (body.get("secret") or "").strip()
            otp = (body.get("otp") or "").strip()
            if not secret or not otp:
                return self._json({"error": "secret dan otp wajib"}, 400)
            # validasi TOTP terhadap secret yang dikirim (atau pending di sesi)
            if not auth_local.totp_verify(secret, otp):
                # coba pending secret jika client kirim secret berbeda
                try:
                    db = auth_local._load_sessions()
                    pending = (db.get(sess.get("id")) or {}).get("_pending_2fa_secret")
                    if pending and pending != secret and auth_local.totp_verify(pending, otp):
                        secret = pending
                    else:
                        return self._json({"error": "kode 2FA salah atau kadaluarsa — pastikan jam HP sinkron"}, 400)
                except:
                    return self._json({"error": "kode 2FA salah atau kadaluarsa"}, 400)
            ok, err = auth_local.update_user_2fa(sess.get("user_id"), True, secret)
            if not ok:
                return self._json({"error": f"gagal aktifkan 2FA: {err}", "detail": err}, 500)
            # bersihkan pending dan refresh sesi flag
            try:
                db = auth_local._load_sessions()
                cur = db.get(sess.get("id"))
                if cur is not None:
                    cur.pop("_pending_2fa_secret", None)
                    cur["tfa_enabled"] = True
                    cur["2fa"] = True
                    db[sess.get("id")] = cur
                    auth_local._save_sessions(db)
            except: pass
            prof = auth_local.fetch_user_profile_by_id(sess.get("user_id"))
            return self._json({"ok": True, "user": auth_local.sanitize_profile_for_client(prof) if prof else None})
        if p == "/api/auth/tfa/disable":
            sess = _session_from_cookie(self)
            if not sess:
                return self._json({"error": "login dulu"}, 401)
            otp = (body.get("otp") or "").strip()
            if not otp:
                return self._json({"error": "otp wajib"}, 400)
            prof = auth_local.fetch_user_profile_by_id(sess.get("user_id"))
            if not prof:
                return self._json({"error": "gagal baca profil"}, 500)
            secret = (prof.get("2fa_secret") or "").strip() if isinstance(prof.get("2fa_secret"), str) else ""
            if not secret:
                # fallback: coba baca dari DB langsung (ikut ANA_DB_SOURCE)
                try:
                    import pymysql
                    import db_source as _dbsrc
                    conn=pymysql.connect(**_dbsrc.kwargs())
                    with conn.cursor() as cur:
                        cur.execute("SELECT `2fa_secret` FROM directus_users WHERE id=%s", (sess.get("user_id"),))
                        row=cur.fetchone()
                        if row: secret=(row[0] or "").strip()
                    conn.close()
                except: pass
            if not secret or not auth_local.totp_verify(secret, otp):
                return self._json({"error": "kode 2FA salah atau kadaluarsa"}, 400)
            ok, err = auth_local.update_user_2fa(sess.get("user_id"), False, None)
            if not ok:
                return self._json({"error": f"gagal matikan 2FA: {err}"}, 500)
            try:
                db = auth_local._load_sessions()
                cur = db.get(sess.get("id"))
                if cur is not None:
                    cur["tfa_enabled"]=False; cur["2fa"]=False
                    db[sess.get("id")]=cur
                    auth_local._save_sessions(db)
            except: pass
            return self._json({"ok": True})
        if p == "/api/layout":
            try:
                # FASE 2: sesi login -> slot desktop|mobile di layout_<uid>.json
                # (atomic tmp+rename). Token global tanpa sesi -> 401, tanpa tulis.
                sess = _session_from_cookie(self)
                uid = str(sess.get("user_id", "") or "") if sess else ""
                ufile = _layout_uid_file(uid) if uid else None
                if ufile is None:
                    return self._json({"error": "login diperlukan untuk menyimpan layout"}, 401)
                mode = str(body.get("mode", "desktop") or "desktop").strip()
                if mode not in ("desktop", "mobile"):
                    return self._json({"error": "mode harus desktop|mobile"}, 400)
                layouts = body.get("layouts", {})
                err = _layout_validate_layouts(layouts)
                if err:
                    return self._json({"error": err}, 400)
                cur = _layout_load_for_uid(uid)
                cur["v"] = 3
                cur["locked"] = bool(body.get("locked", cur.get("locked", True)))
                if isinstance(body.get("disabled"), list):
                    cur["disabled"] = body["disabled"]
                cur[mode] = {"layouts": layouts}
                _layout_atomic_write(ufile, cur)
                return self._json(cur)
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
            params, _clamped, _deny, _deny_msg = _enforce_wilayah_scope(self, params, template)
            if _deny:
                return self._json({"error": _deny_msg}, 403)
            try:
                _scope_now = _wilayah_scope_from_session(self)
            except Exception:
                _scope_now = {}
            try:
                _deny2, _deny2_msg = _wilayah_chain_check(_scope_now, params)
            except Exception:
                _deny2, _deny2_msg = False, ""
            if _deny2:
                return self._json({"error": _deny2_msg}, 403)
            try:
                data = _simoge_query(template, params)
                if _clamped:
                    data["scope_clamped"] = _clamped
                if template == "wilayah_labels":
                    data = _scope_wilayah_labels(data, _scope_now)
                return self._json(data)
            except Exception as e:
                _dlog(f"simoge/query {template} ERROR {type(e).__name__}: {str(e)[:160]}")
                if _DEBUG_MAP:
                    traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/simoge/packet":
            template = (body.get("template") or "").strip()
            if not template:
                return self._json({"error": "template required"}, 400)
            params = body.get("params", {})
            if not isinstance(params, dict):
                return self._json({"error": "params must be object"}, 400)
            params, _clamped, _deny, _deny_msg = _enforce_wilayah_scope(self, params, template)
            if _deny:
                return self._json({"error": _deny_msg}, 403)
            try:
                _deny2, _deny2_msg = _wilayah_chain_check(_wilayah_scope_from_session(self), params)
            except Exception:
                _deny2, _deny2_msg = False, ""
            if _deny2:
                return self._json({"error": _deny2_msg}, 403)
            try:
                data = _simoge_query_packet(template, params)
                if _clamped:
                    data["scope_clamped"] = _clamped
                return self._json(data)
            except Exception as e:
                _dlog(f"simoge/packet {template} ERROR {type(e).__name__}: {str(e)[:160]}")
                if _DEBUG_MAP:
                    traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/simoge/analyze":
            template = (body.get("template") or "").strip()
            if not template:
                return self._json({"error": "template required"}, 400)
            params = body.get("params", {})
            if not isinstance(params, dict):
                return self._json({"error": "params must be object"}, 400)
            operations = body.get("operations") or body.get("ops") or []
            if not isinstance(operations, list):
                return self._json({"error": "operations must be list"}, 400)
            try:
                mrr = int(body.get("max_result_rows", 20))
            except Exception:
                mrr = 20
            params, _clamped, _deny, _deny_msg = _enforce_wilayah_scope(self, params, template)
            if _deny:
                return self._json({"error": _deny_msg}, 403)
            try:
                _deny2, _deny2_msg = _wilayah_chain_check(_wilayah_scope_from_session(self), params)
            except Exception:
                _deny2, _deny2_msg = False, ""
            if _deny2:
                return self._json({"error": _deny2_msg}, 403)
            try:
                return self._json(_simoge_analyze(template, params, operations, max_result_rows=mrr))
            except Exception as e:
                _dlog(f"simoge/analyze {template} ERROR {type(e).__name__}: {str(e)[:160]}")
                if _DEBUG_MAP:
                    traceback.print_exc()
                return self._json({"error": str(e)[:400]}, 500)

        if p == "/api/simoge/show_on_map":
            template = (body.get("template") or "petak_with_geometry").strip()
            params = body.get("params", {})
            if not isinstance(params, dict):
                return self._json({"error": "params must be object"}, 400)
            params, _clamped, _deny, _deny_msg = _enforce_wilayah_scope(self, params, template)
            if _deny:
                return self._json({"error": _deny_msg}, 403)
            try:
                _deny2, _deny2_msg = _wilayah_chain_check(_wilayah_scope_from_session(self), params)
            except Exception:
                _deny2, _deny2_msg = False, ""
            if _deny2:
                return self._json({"error": _deny2_msg}, 403)
            try:
                # drive=True  → pemanggil ANA: efek lewat `spatial_set`, server
                #   tak push GeoJSON (satu penulis peta = panel).
                # drive=False → pemanggil panel: server tak sentuh state, cuma
                #   kembalikan GeoJSON hasil query-nya.
                # Default True: panel selalu kirim drive:false eksplisit
                #   (businessAdapter.loadBusinessData), jadi aman. Default False
                #   bikin show_on_map ANA (tanpa flag) jatuh ke push mentah.
                # scope = wilayah login: filter wilayah ANA di luar scope tak
                # diteruskan ke panel via spatial_set (lihat _spatial_sync).
                try:
                    _sync_scope = _wilayah_scope_from_session(self)
                except Exception:
                    _sync_scope = {}
                _ow_show, _ = _anna_owner_from_request(self)
                data = _simoge_show_on_map(template, params,
                                           drive_panel=bool(body.get("drive", True)),
                                           scope=_sync_scope, owner=_ow_show)
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

        if p == "/api/bit/target_gap":
            # BIT v0.1 — deterministic Target vs Rencana vs Actual
            # Body: {tahun, bulan, periode, include_breakdown?, kode_* scope optional (ditimpa scope login)}
            try:
                tahun = int(body.get("tahun", 2026))
                bulan = int(body.get("bulan", 4))
                periode = int(body.get("periode", 2))
            except Exception:
                return self._json({"error": "tahun/bulan/periode harus angka"}, 400)
            if not (1 <= bulan <= 12) or periode not in (0,1,2):
                return self._json({"error": "bulan 1-12, periode 0/1/2"}, 400)
            sampai_dengan = str(body.get("sampai_dengan", body.get("sampaiDengan", "ya")) or "ya").strip().lower()
            if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
            elif sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
            else: sampai_dengan="ya"
            include_breakdown = bool(body.get("include_breakdown", body.get("breakdown", False)))
            # scope from login (enforced) + optional body scope (clamped)
            try:
                _scope = _wilayah_scope_from_session(self)
            except Exception:
                _scope = {}
            # allow body to hint deeper scope but clamp to login scope
            for k in ("kode_divre","kode_kph","kode_bkph","kode_rph","kode_tpg"):
                if body.get(k):
                    body.setdefault(k, body.get(k))
            # merge body scope into _scope (body = params, _enforce does it)
            _params_scope = {k: body.get(k) for k in ("kode_divre","kode_kph","kode_bkph","kode_rph","kode_tpg") if body.get(k) is not None}
            if _params_scope:
                # reuse enforce logic
                _merged, _clamped2, _deny2, _deny2_msg = _enforce_wilayah_scope(self, _params_scope, "bit_target_gap")
                if _deny2:
                    return self._json({"error": _deny2_msg}, 403)
                _scope = {**_scope, **{k: v for k, v in _merged.items() if v}}
            if bit_engine is None:
                return self._json({"error": "bit_engine belum tersedia"}, 503)
            try:
                out = bit_engine.get_target_gap(tahun, bulan, periode, scope=_scope, sampai_dengan=sampai_dengan, include_breakdown=include_breakdown)
                try:
                    _k = (out.get("kpi") or {}) if isinstance(out, dict) else {}
                    _blog(f"target_gap {tahun}-{bulan:02d} P{periode} s/d={sampai_dengan} scope={_scope or '{}'} -> target={_k.get('target_expected_kg')} rencana={_k.get('rencana_main_kg')} actual={_k.get('actual_main_kg')} ach={_k.get('achievement_pct')} gap={_k.get('current_gap_kg')} cached={out.get('cached', False)}")
                    if out.get("limitations"):
                        _blog(f"  limitations: {'; '.join(map(str, out.get('limitations',[])[:2]))[:200]}")
                except Exception:
                    pass
                # chain check already via _scope handling above; keep consistent
                return self._json(out)
            except Exception as e:
                _blog(f"target_gap ERROR scope={_scope}  {type(e).__name__}: {str(e)[:160]}", "error")
                if _DEBUG_MAP:
                    import traceback; traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/bit/diagnostic":
            try:
                tahun = int(body.get("tahun", 2026))
                bulan = int(body.get("bulan", 4))
                periode = int(body.get("periode", 2))
            except Exception:
                return self._json({"error": "tahun/bulan/periode harus angka"}, 400)
            if not (1 <= bulan <= 12) or periode not in (0,1,2):
                return self._json({"error": "bulan 1-12, periode 0/1/2"}, 400)
            sampai_dengan = str(body.get("sampai_dengan", body.get("sampaiDengan", "ya")) or "ya").strip().lower()
            if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
            elif sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
            else: sampai_dengan="ya"
            try:
                _scope = _wilayah_scope_from_session(self)
            except Exception:
                _scope = {}
            _params_scope = {k: body.get(k) for k in ("kode_divre","kode_kph","kode_bkph","kode_rph","kode_tpg") if body.get(k) is not None}
            if _params_scope:
                _merged, _clamped2, _deny2, _deny2_msg = _enforce_wilayah_scope(self, _params_scope, "bit_diagnostic")
                if _deny2:
                    return self._json({"error": _deny2_msg}, 403)
                _scope = {**_scope, **{k: v for k, v in _merged.items() if v}}
            if bit_engine is None:
                return self._json({"error": "bit_engine belum tersedia"}, 503)
            try:
                out = bit_engine.get_diagnostic(tahun, bulan, periode, scope=_scope, sampai_dengan=sampai_dengan)
                try:
                    _k = (out.get("kpi") or {}); _a = (out.get("aktivitas") or {})
                    _blog(f"diagnostic {tahun}-{bulan:02d} P{periode} s/d={sampai_dengan} scope={_scope or '{}'} -> aktivitas={_a.get('n_aktivitas')} penyadap={_a.get('n_penyadap_aktiv')} petak={_a.get('n_petak_aktiv')} pohon_tersentuh={_a.get('pohon_tersentuh_total')} target={_k.get('target_expected_kg')}")
                except Exception:
                    pass
                return self._json(out)
            except Exception as e:
                _blog(f"diagnostic ERROR scope={_scope}  {type(e).__name__}: {str(e)[:160]}", "error")
                if _DEBUG_MAP:
                    import traceback; traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/bit/hypothesis":
            try:
                tahun = int(body.get("tahun", 2026))
                bulan = int(body.get("bulan", 4))
                periode = int(body.get("periode", 2))
            except Exception:
                return self._json({"error": "tahun/bulan/periode harus angka"}, 400)
            if not (1 <= bulan <= 12) or periode not in (0,1,2):
                return self._json({"error": "bulan 1-12, periode 0/1/2"}, 400)
            sampai_dengan = str(body.get("sampai_dengan", body.get("sampaiDengan", "ya")) or "ya").strip().lower()
            if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
            elif sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
            else: sampai_dengan="ya"
            try:
                _scope = _wilayah_scope_from_session(self)
            except Exception:
                _scope = {}
            _params_scope = {k: body.get(k) for k in ("kode_divre","kode_kph","kode_bkph","kode_rph","kode_tpg") if body.get(k) is not None}
            if _params_scope:
                _merged, _c2, _d2, _m2 = _enforce_wilayah_scope(self, _params_scope, "bit_hypothesis")
                if _d2:
                    return self._json({"error": _m2}, 403)
                _scope = {**_scope, **{k: v for k, v in _merged.items() if v}}
            if bit_engine is None:
                return self._json({"error": "bit_engine belum tersedia"}, 503)
            try:
                out = bit_engine.get_hypothesis(tahun, bulan, periode, scope=_scope, sampai_dengan=sampai_dengan)
                try:
                    _hy = out.get("hypotheses") or []; _s = ", ".join([f"{h.get('id')}:{h.get('status')}" for h in _hy])
                    _blog(f"hypothesis {tahun}-{bulan:02d} P{periode} s/d={sampai_dengan} scope={_scope or '{}'} -> {_s} cmp={out.get('meta',{}).get('comparison','')}")
                except Exception:
                    pass
                return self._json(out)
            except Exception as e:
                _blog(f"hypothesis ERROR scope={_scope}  {type(e).__name__}: {str(e)[:160]}", "error")
                if _DEBUG_MAP:
                    import traceback; traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/bit/sebaran":
            try:
                tahun = int(body.get("tahun", 2026))
                bulan = int(body.get("bulan", 4))
                periode = int(body.get("periode", 2))
            except Exception:
                return self._json({"error": "tahun/bulan/periode harus angka"}, 400)
            if not (1 <= bulan <= 12) or periode not in (0,1,2):
                return self._json({"error": "bulan 1-12, periode 0/1/2"}, 400)
            sampai_dengan = str(body.get("sampai_dengan", body.get("sampaiDengan", "ya")) or "ya").strip().lower()
            if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
            elif sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
            else: sampai_dengan="ya"
            try:
                _scope = _wilayah_scope_from_session(self)
            except Exception:
                _scope = {}
            _params_scope = {k: body.get(k) for k in ("kode_divre","kode_kph","kode_bkph","kode_rph","kode_tpg") if body.get(k) is not None}
            if _params_scope:
                _merged, _c2, _d2, _m2 = _enforce_wilayah_scope(self, _params_scope, "bit_sebaran")
                if _d2:
                    return self._json({"error": _m2}, 403)
                _scope = {**_scope, **{k: v for k, v in _merged.items() if v}}
            if bit_engine is None:
                return self._json({"error": "bit_engine belum tersedia"}, 503)
            try:
                out = bit_engine.get_sebaran(tahun, bulan, periode, scope=_scope, sampai_dengan=sampai_dengan)
                try:
                    _rows = out.get("rows") or []; _lvl = out.get("level","")
                    _top = ( _rows[0].get("nama","")[:18] + f" gap { _rows[0].get('gap_kg')}" ) if _rows else "no rows"
                    _blog(f"sebaran {tahun}-{bulan:02d} P{periode} s/d={sampai_dengan} scope={_scope or '{}'} lvl={_lvl} rows={len(_rows)} top={_top}")
                except Exception:
                    pass
                return self._json(out)
            except Exception as e:
                _blog(f"sebaran ERROR scope={_scope}  {type(e).__name__}: {str(e)[:160]}", "error")
                if _DEBUG_MAP:
                    import traceback; traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/bit/analisis":
            try:
                tahun = int(body.get("tahun", 2026)); bulan = int(body.get("bulan", 4)); periode = int(body.get("periode", 2))
            except Exception:
                return self._json({"error": "tahun/bulan/periode harus angka"}, 400)
            if not (1 <= bulan <= 12) or periode not in (0,1,2):
                return self._json({"error": "bulan 1-12, periode 0/1/2"}, 400)
            sampai_dengan = str(body.get("sampai_dengan", body.get("sampaiDengan", "ya")) or "ya").strip().lower()
            if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
            elif sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
            else: sampai_dengan="ya"
            try: _scope = _wilayah_scope_from_session(self)
            except Exception: _scope={}
            _ps = {k: body.get(k) for k in ("kode_divre","kode_kph","kode_bkph","kode_rph","kode_tpg") if body.get(k) is not None}
            if _ps:
                _m,_c,_d,_msg = _enforce_wilayah_scope(self, _ps, "bit_analisis")
                if _d: return self._json({"error": _msg}, 403)
                _scope = {**_scope, **{k: v for k, v in _m.items() if v}}
            if bit_engine is None: return self._json({"error": "bit_engine belum tersedia"}, 503)
            try:
                import time as _tt; _t0=_tt.perf_counter()
                out = bit_engine.get_analisis(tahun, bulan, periode, scope=_scope, sampai_dengan=sampai_dengan)
                _ms=(_tt.perf_counter()-_t0)*1000
                _blog(f"analisis {tahun}-{bulan:02d} P{periode} s/d={sampai_dengan} scope={_scope or '{}'} tren={len(out.get('tren',[]))} anomali={len(out.get('anomali',[]))} ({_ms:.0f}ms)")
                return self._json(out)
            except Exception as e:
                _blog(f"analisis ERROR scope={_scope}  {type(e).__name__}: {str(e)[:160]}", "error")
                if _DEBUG_MAP:
                    import traceback; traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/bit/rekomendasi":
            try:
                tahun = int(body.get("tahun", 2026))
                bulan = int(body.get("bulan", 4))
                periode = int(body.get("periode", 2))
            except Exception:
                return self._json({"error": "tahun/bulan/periode harus angka"}, 400)
            if not (1 <= bulan <= 12) or periode not in (0,1,2):
                return self._json({"error": "bulan 1-12, periode 0/1/2"}, 400)
            sampai_dengan = str(body.get("sampai_dengan", body.get("sampaiDengan", "ya")) or "ya").strip().lower()
            if sampai_dengan in ("y","yes","t","1","true"): sampai_dangan="ya"
            else: sampai_dengan = "ya" if sampai_dengan in ("ya","y") else ("tidak" if sampai_dengan in ("tidak","n","no","0","false") else "ya")
            # fix typo
            sampai_dengan = str(body.get("sampai_dengan", body.get("sampaiDengan", "ya")) or "ya").strip().lower()
            if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
            elif sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
            else: sampai_dengan="ya"
            try:
                _scope = _wilayah_scope_from_session(self)
            except Exception:
                _scope = {}
            _params_scope = {k: body.get(k) for k in ("kode_divre","kode_kph","kode_bkph","kode_rph","kode_tpg") if body.get(k) is not None}
            if _params_scope:
                _merged, _c2, _d2, _m2 = _enforce_wilayah_scope(self, _params_scope, "bit_rekomendasi")
                if _d2:
                    return self._json({"error": _m2}, 403)
                _scope = {**_scope, **{k: v for k, v in _merged.items() if v}}
            if bit_engine is None:
                return self._json({"error": "bit_engine belum tersedia"}, 503)
            _t0 = 0
            try:
                import time as _tt
                _t0 = _tt.perf_counter()
                out = bit_engine.get_rekomendasi(tahun, bulan, periode, scope=_scope, sampai_dengan=sampai_dengan)
                _ms = (_tt.perf_counter() - _t0) * 1000
                _blog(f"rekomendasi {tahun}-{bulan:02d} P{periode} s/d={sampai_dengan} scope={_scope or '{}'} -> {len(out.get('rekomendasi',[]))} opsi prio1={[r.get('id') for r in (out.get('rekomendasi_sorted') or [])[:2]]} ({_ms:.0f}ms)")
                return self._json(out)
            except Exception as e:
                _blog(f"rekomendasi ERROR scope={_scope}  {type(e).__name__}: {str(e)[:160]}", "error")
                if _DEBUG_MAP:
                    import traceback; traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p in ("/api/bit/cases", "/api/bit/case"):
            if bit_case_store is None:
                return self._json({"error": "bit_case_store belum tersedia"}, 503)
            body = body or {}
            method = self.command
            # derive user
            try:
                sess = _session_from_cookie(self)
                email = str((sess or {}).get("email") or (sess or {}).get("user_email") or "")
                scope = _wilayah_scope_from_session(self) or {}
            except Exception:
                email=""; scope={}
            try:
                if p == "/api/bit/cases":
                    if method == "GET" or body.get("action") in (None, "", "list"):
                        q = str(body.get("q") or body.get("search") or "").strip()[:200]
                        status = str(body.get("status") or "").strip().lower() or None
                        lim = int(body.get("limit", 20) or 20)
                        off = int(body.get("offset", 0) or 0)
                        out = bit_case_store.list_cases(limit=lim, offset=off, status=status, q=q or None)
                        return self._json({"ok": True, **out})
                    if body.get("action") in ("create", "add"):
                        payload = body.get("payload") or body.get("case") or {k: body[k] for k in ("gejala","pertanyaan","periode","snapshot","hipotesis","kesimpulan","kepastian","keputusan","hasil","tags") if k in body}
                        # periode now: if missing use current BIT params
                        if not payload.get("periode"):
                            payload["periode"] = {"tahun": int(body.get("tahun", 2026)), "bulan": int(body.get("bulan", 2)), "periode": int(body.get("periode", 0)), "sampai_dengan": str(body.get("sampai_dengan","ya")), "scope": scope}
                        out = bit_case_store.create_case(payload, user_email=email, scope=scope)
                        _blog(f"cases create {out.get('id')} gejala={out.get('gejala','')[:60]} by {email or 'anon'}", "info")
                        return self._json({"ok": True, "case": out})
                    return self._json({"error": "action list|create"}, 400)
                else:  # /api/bit/case single
                    cid = str(body.get("id") or body.get("case_id") or "").strip()
                    act = str(body.get("action") or "").strip().lower()
                    if not cid and act not in ("list",):
                        return self._json({"error": "id case diperlukan"}, 400)
                    if act in ("", "get"):
                        out = bit_case_store.get_case(cid)
                        return self._json({"ok": True, "case": out})
                    if act in ("update","patch"):
                        patch = body.get("patch") or {k: body[k] for k in ("status","kesimpulan","kepastian","keputusan","hasil","tags","hipotesis") if k in body}
                        out = bit_case_store.update_case(cid, patch, user_email=email)
                        _blog(f"cases update {cid} -> {patch} by {email}", "info")
                        return self._json({"ok": True, "case": out})
                    if act in ("delete","remove"):
                        out = bit_case_store.delete_case(cid)
                        _blog(f"cases delete {cid} by {email}", "info")
                        return self._json({"ok": True, **out})
                    if act in ("verify",):
                        # shortcut: status verified + hasil
                        patch = {"status": "verified", "hasil": body.get("hasil") or {"outcome": str(body.get("outcome","sukses")), "catatan": str(body.get("catatan",""))}}
                        out = bit_case_store.update_case(cid, patch, user_email=email)
                        return self._json({"ok": True, "case": out})
                    return self._json({"error": "action get|update|delete|verify"}, 400)
            except ValueError as ve:
                return self._json({"error": str(ve)[:300]}, 400)
            except KeyError as ke:
                return self._json({"error": str(ke)[:300]}, 404)
            except Exception as e:
                _blog(f"cases ERROR {type(e).__name__}: {str(e)[:160]}", "error")
                if _DEBUG_MAP:
                    import traceback; traceback.print_exc()
                return self._json({"error": str(e)[:300]}, 500)

        if p == "/api/tiles/cron":
            # Manajemen cron rebuild harian dari UI (P2-4). Body: {action:
            # "status"|"enable"|"disable", schedule: "10 6 * * *" opsional}.
            # Marker: ana-pmtiles-daily. Hanya baris marker yang disentuh —
            # cron lain milik user tak diganggu.
            action = (body.get("action") or "status").strip().lower()
            return self._tiles_cron(action, (body.get("schedule") or "").strip())
        if p == "/api/insight/cron":
            # Manajemen cron insight harian 06:00 dari UI. Body sama.
            # Marker: ana-insight-daily. Thread scheduler = fallback bila off.
            action = (body.get("action") or "status").strip().lower()
            return self._tiles_cron(action, (body.get("schedule") or "").strip(),
                                    marker="ana-insight-daily")
        if p == "/api/session":
            # CRUD sesi ANNA milik user login (maks 3, histori persisten).
            # GET/POST-tanpa-action = daftar; {session_id} = pilih aktif;
            # {action:"new"} = sesi baru (terbaru digeser, maks 3);
            # {action:"delete", session_id} = hapus satu miliknya.
            _uk = _anna_user_key(self)
            action = (body.get("action") or "").strip().lower()
            if action == "delete":
                # Baca origin SEBELUM drop (sesudah drop entrinya hilang).
                _origin = ""
                try:
                    _dsid0 = str(body.get("session_id") or "").strip()
                    if _dsid0:
                        with _SESSION_LOCK:
                            _ent0 = SESSION.get(_uk) or {}
                            _m0 = _ent0.get("meta") if isinstance(_ent0.get("meta"), dict) else {}
                            for _s0 in (_m0.get("sessions") or []):
                                if isinstance(_s0, dict) and str(_s0.get("id") or "") == _dsid0:
                                    _origin = str(_s0.get("origin") or "run")
                                    break
                            if not _origin and str(_ent0.get("id") or "") == _dsid0:
                                _origin = "run"
                except Exception:
                    _origin = ""
                ok = _session_hist_drop(_uk, body.get("session_id"))
                try:
                    _anna_scope_prune()
                except Exception:
                    pass
                # Hapus bertingkat: histori dashboard selalu dibuang; store
                # Hermes ikut dihapus HANYA bila sesi lahir dari dashboard
                # (origin "run" via chat /api/run) dan sudah yatim (tak ada
                # user memegangnya) — honori janji UI "riwayat ikut hilang" +
                # cegah klaim-ulang pasca-hapus. Sesi adopsi CLI ("claim")
                # TAK PERNAH disentuh store-nya: itu riwayat CLI user,
                # dashboard hanya melepas pegangannya.
                _store_deleted = False
                try:
                    _dsid = str(body.get("session_id") or "").strip()
                    if ok and _dsid and (_origin or "run") == "run":
                        _mine_now = _session_owned_ids(_uk)
                        if _dsid not in _mine_now:
                            _owners = _session_owners_snapshot()
                            if _dsid not in _owners:
                                try:
                                    _store_deleted = bool(services.delete_session(
                                        runtime._hermes_base(), runtime.WORKDIR, _dsid))
                                except Exception:
                                    _store_deleted = False
                except Exception:
                    pass
                return self._json({"ok": True, "deleted": bool(ok),
                                   "store_deleted": bool(_store_deleted),
                                   "sessions": _session_list(_uk)})
            sid = body.get("session_id")
            if sid and runtime.valid_session(sid):
                # Klaim sesi baru wajib cookie login VALID. Tanpa ini klaim
                # dengan cookie mati/asing jatuh ke kunci netral "" dan
                # mengotori kanal ANNA system (kasus: cookie pra-login).
                if _uk == "":
                    raw_ck = ""
                    try:
                        raw_ck = self.headers.get("Cookie", "") or ""
                    except Exception:
                        raw_ck = ""
                    if not _parse_cookies(raw_ck).get("ana_session", "").strip():
                        return self._json({"ok": False, "error": "login dulu sebelum pilih sesi"}, 401)
                # Wire session_ids(): regex valid != sesi ada di store.
                # Pilih ID basi/asing: 404 eksplisit, bukan diam-diam jadi
                # sesi aktif lalu run gagal saat --resume. Store tak bisa
                # dibaca (None) = fallback accept seperti dulu (fail-open).
                try:
                    _known = services.session_ids(runtime._hermes_base(), runtime.WORKDIR)
                except Exception:
                    _known = None
                if _known is not None and str(sid) not in _known and str(sid) not in _session_owned_ids(_uk):
                    return self._json({"ok": False, "error": "sesi tidak dikenal di store Hermes"}, 404)
                # Gerbang kepemilikan global: sid yang sudah dipegang user
                # LAIN tidak boleh diklaim — user hanya boleh pilih miliknya
                # (atau ID yatim yang belum dipegang siapa pun). Tanpa ini
                # user B yang tahu ID sesi A bisa klaim + resume + baca
                # transcript A. Pemilik mengklaim ulang miliknya = boleh.
                try:
                    _owners = _session_owners_snapshot()
                    _holder = _owners.get(str(sid))
                    if _holder is not None and str(_holder) != str(_uk):
                        return self._json({"ok": False, "error": "sesi milik user lain"}, 403)
                except Exception:
                    pass
                if action == "new":
                    _session_hist_push(_uk, str(sid), body.get("title"), origin="claim")
                else:
                    # Pilih langsung (tanpa new): pastikan entri histori ada
                    # dengan origin claim — tanpa ini origin default "run"
                    # dan hapus nanti keliru menyentuh store CLI user.
                    try:
                        _have = str(sid) in _session_owned_ids(_uk)
                    except Exception:
                        _have = True
                    if not _have:
                        _session_hist_push(_uk, str(sid), body.get("title"), origin="claim")
                _session_set(str(sid), None, key=_uk)
                cur_id, cur_meta = _session_get(_uk)
                return self._json({"ok": True, "session": cur_id, "meta": cur_meta,
                                   "sessions": _session_list(_uk)})
            if action in ("", "list"):
                cur_id, cur_meta = _session_get(_uk)
                return self._json({"ok": True, "session": cur_id, "meta": cur_meta,
                                   "sessions": _session_list(_uk), "max": _ANNA_MAX_SESSIONS})
            _clear_session(_uk)
            return self._json({"ok": True, "session": None, "sessions": []})

        if p == "/api/session/archive":
            # Arsip sesi aktif ke histori (maks 3) TANPA menghapus sesi di
            # store Hermes. Dipakai tombol +BARU: sesi lama tetap utuh dan
            # bisa dibuka lagi dari picker; run berikut buat sesi baru.
            # Tanpa endpoint ini +BARU = setSession(null) yang arsipnya
            # hilang (dead-end): user tak bisa kembali ke sesi lama.
            if not self._token_ok():
                return self._unauth()
            _uk = _anna_user_key(self)
            if _uk == "":
                return self._json({"ok": False, "error": "login dulu"}, 401)
            try:
                _aid, _ameta = _session_get(_uk)
            except Exception:
                _aid, _ameta = None, None
            _evicted = None
            try:
                if _aid and runtime.valid_session(_aid):
                    _evicted = _session_hist_push(_uk, str(_aid),
                                       (dict(_ameta or {}).get("title") if isinstance(_ameta, dict) else None))
            except Exception:
                pass
            _clear_session(_uk)
            return self._json({"ok": True, "session": None, "sessions": _session_list(_uk),
                               "evicted": _evicted, "max": _ANNA_MAX_SESSIONS})

        if p == "/api/speak":
            text = (body.get("text") or "").strip()
            # TTS chunk per kalimat: metrics sesi ditulis sekali — start di
            # chunk 0 (total_chars penuh), end+complete di chunk final.
            try:
                ci = int(body.get("chunk_index") or 0)
            except (TypeError, ValueError):
                ci = 0
            cf = bool(body.get("chunk_final", True))
            if ci == 0:
                try:
                    total = int(body.get("total_chars") or len(text))
                except (TypeError, ValueError):
                    total = len(text)
                # voice_metrics removed (rollback)
            try:
                audio = voice.speak(text)
                if cf:
                    pass  # voice_metrics removed (rollback)
                return self._bytes(audio, "audio/mpeg")
            except Exception as e:
                # voice_metrics removed (rollback)
                # voice_metrics removed (rollback)
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
        if p == "/api/db-source":
            # POST {source:"local"|"remote"} atau {action:"test"}.
            # Switch tanpa restart: auth baca .env tiap query,
            # koneksi shared simoge di-reset agar ikut sumber baru.
            try:
                src = (body.get("source") or "").strip().lower()
                action = (body.get("action") or "").strip().lower()
                if action == "test":
                    try:
                        kw = db_source.kwargs(src or None)
                        if db_source.source() == "remote" or src == "remote":
                            db_source.ensure_tunnel(kw.get("port", 13307))
                        r = db_source.test(kw)
                        return self._json(dict(ok=r.get("ok"), source=src or db_source.source(),
                                               users=r.get("users"), error=""))
                    except Exception as e:
                        return self._json(dict(ok=False, source=src or db_source.source(),
                                               error=f"{type(e).__name__}: {str(e)[:160]}"))
                if not src:
                    return self._json({"error": "source wajib: local|remote"}, 400)
                if src == "remote":
                    kw = db_source.kwargs("remote")
                    if not db_source.tunnel_ok(kw.get("port", 13307)):
                        if not db_source.ensure_tunnel(kw.get("port", 13307)):
                            return self._json({"error": "tunnel kphbwb-tunnel gagal dibuka (cek ssh key)"}, 502)
                    try:
                        r = db_source.test(kw)
                    except Exception as e:
                        return self._json({"error": f"remote DB tak terjangkau: {type(e).__name__}: {str(e)[:160]}"}, 502)
                    if not r.get("ok"):
                        return self._json({"error": "remote DB test gagal"}, 502)
                db_source.set_source(src)
                # Switch DB = sesi lama hangus (user wajib login ulang ke DB baru).
                try:
                    auth_local.destroy_all_sessions()
                except Exception:
                    pass
                # Sesi ANNA per-user ikut hangus semua (data beda DB) + prune scope.
                try:
                    _clear_session(None)
                except Exception:
                    pass
                try:
                    _anna_scope_prune(0)
                except Exception:
                    pass
                try:
                    for _m in ("simoge_db",):
                        if _m in sys.modules:
                            _rc = getattr(sys.modules[_m], "reset_conn", None)
                            if callable(_rc):
                                _rc()
                except Exception:
                    pass
                _alog(f"db-source switch -> {src} (semua sesi logout)", "warn")
                try:
                    body_out = json.dumps(dict(ok=True, source=src, logout=True)).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body_out)))
                    _clear_session_cookie(self)
                    self.end_headers()
                    self.wfile.write(body_out)
                    return
                except (BrokenPipeError, ConnectionResetError):
                    return
                return
            except ValueError as e:
                return self._json({"error": str(e)[:200]}, 400)
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 500)
        if p == "/api/new":
            # Sesi baru: arsipkan sesi aktif ke histori (maks 3), kosongkan
            # aktif — run berikut buat sesi Hermes baru. Histori lama tetap
            # bisa dipilih lagi via /api/session {session_id}.
            _uk = _anna_user_key(self)
            try:
                _sid0, _meta0 = _session_get(_uk)
            except Exception:
                _sid0, _meta0 = None, None
            runtime.cancel_active(_sid0)
            try:
                if _sid0 and runtime.valid_session(_sid0):
                    _session_hist_push(_uk, str(_sid0),
                                       (dict(_meta0 or {}).get("title") if isinstance(_meta0, dict) else None))
            except Exception:
                pass
            with _SESSION_LOCK:
                ent = SESSION.get(_uk) or {}
                ent["id"] = None
                SESSION[_uk] = ent
            _session_save()
            try:
                _anna_scope_prune()
            except Exception:
                pass
            return self._json({"ok": True, "sessions": _session_list(_uk)})

        if p == "/api/cancel":
            # Cancel hanya kill proses aktif — session tetap agar chat berikutnya
            # resume konteks Hermes, bukan mulai fresh diam-diam.
            # Target = sesi Hermes user peminta (bukan sesi global) supaya
            # cancel user A tak memutus turn user B yang sedang jalan.
            try:
                _sid0, _ = _session_get(_anna_user_key(self))
            except Exception:
                _sid0 = None
            stopped = runtime.cancel_active(_sid0)
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

        # voice metrics endpoint removed (rollback TTS/STT)

        # voice metrics sub-endpoint removed

        # voice metrics sub-endpoint removed

        # /api/stt removed (server-side STT rollback)
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
                _ow, _ = _anna_owner_from_request(self)
                cmd_id, err = map_store.push_command(op, args, owner=_ow)
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
            _ow, _ = _anna_owner_from_request(self)
            map_store.set_state(body["state"], owner=_ow)
            return self._json({"ok": True})
        if p == "/api/map/result":
            # Frontend lapor hasil eksekusi perintah antrean.
            cmd_id = str(body.get("id") or "").strip()
            if not cmd_id:
                return self._json({"error": "id required"}, 400)
            _ow, _ = _anna_owner_from_request(self)
            map_store.put_result(cmd_id, body.get("ok", True), body.get("data", body.get("error", "")), owner=_ow)
            return self._json({"ok": True})
        # ── spatial intel (directive #1-20): DB=data file, bukan SQL mentah ──
        if p == "/api/spatial/resolve":
            ref = str(body.get("ref") or body.get("id") or "").strip()
            try:
                _ow, _ = _anna_owner_from_request(self)
                cur = (map_store.get_state(owner=_ow).get("state") or {})
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
        if p == "/api/metabase/query":
            # Query deterministik ke MAXBI (tanpa LLM): {card_id} | {database_id, sql}.
            # {"push": true} = tampilkan hasilnya di tile chart existing (meta.source MAXBI).
            if not self._token_ok():
                return self._unauth()
            if metabase is None:
                return self._json(_metabase_503(), 503)
            if not isinstance(body, dict):
                return self._json({"error": "body must be object"}, 400)
            try:
                if "card_id" in body:
                    res = metabase.run_card(body.get("card_id"), body.get("params") or {})
                    title = str(body.get("title") or "") or \
                        (metabase.get_card(body.get("card_id")).get("card") or {}).get("name", "")
                elif "sql" in body:
                    res = metabase.run_sql(body.get("database_id", 9), body.get("sql"))
                    title = str(body.get("title") or "MAXBI")
                else:
                    return self._json({"ok": False, "error": "perlu card_id atau sql"}, 400)
                if not res.get("ok"):
                    return self._json(res)
                out = dict(res)
                out["chart"] = metabase.to_chart(res, title)
                if body.get("push"):
                    _ow, _osc = _anna_owner_from_request(self)
                    if not _ow:
                        return self._json({"ok": False, "error": "push berisi data wajib lewat sesi user login"}, 401)
                    spec = dict(out["chart"], visible=True,
                                meta={"source": "MAXBI", "title": title})
                    okp, errp = spatial_chart_store.set_chart(spec, owner=_ow, scope=_osc)
                    if not okp:
                        return self._json({"ok": False, "error": errp}, 400)
                    out["pushed"] = True
                return self._json(out)
            except Exception as e:                        # noqa: BLE001
                return self._json({"ok": False, "error": str(e)[:200]}, 500)
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
            # Robust: push BERDATA wajib lewat sesi user login (cookie) atau
            # sesi Hermes milik user (header X-Hermes-Session dari tool ANNA).
            # Tanpa itu DITOLAK 401 — tak ada kanal netral berisi data.
            # Hide (visible False) tetap boleh netral (clear umum, tak ada data).
            _ow, _osc = _anna_owner_from_request(self)
            if not _ow and body.get("visible") is not False and any(
                    body.get(k) for k in ("charts", "chart", "kpis", "title", "narration", "evidence")):
                return self._json({"ok": False, "error": "chart berisi data wajib push lewat sesi user login"}, 401)
            ok, err = spatial_chart_store.set_chart(body, owner=_ow, scope=_osc)
            if not ok:
                return self._json({"ok": False, "error": err}, 400)
            return self._json(dict(ok=True, **spatial_chart_store.get_state(owner=_ow)))
        # ── spatial report (LAPORAN BISNIS multi halaman — full control ANA, session state) ──
        if p == "/api/spatial/report":
            if not self._token_ok():
                return self._unauth()
            if not isinstance(body, dict):
                return self._json({"error": "body must be object"}, 400)
            _ow, _osc = _anna_owner_from_request(self)
            if not _ow and body.get("visible") is not False and any(
                    body.get(k) for k in ("pages", "title", "subtitle", "evidence")):
                return self._json({"ok": False, "error": "report berisi data wajib push lewat sesi user login"}, 401)
            ok, err = spatial_report_store.set_report(body, owner=_ow, scope=_osc)
            if not ok:
                return self._json({"ok": False, "error": err}, 400)
            return self._json(dict(ok=True, **spatial_report_store.get_state(owner=_ow)))
        # ── arsip chart/laporan per-user (server-side, survive restart) ──
        # GET daftar → {"items":[{id,kind,title,saved_at,n_items}]} milik peminta.
        # POST {"kind","entry_id"?} → simpan snapshot live (tanpa entry_id)
        #   atau tampilkan kembali (dengan entry_id → timpa state live).
        # POST {"op":"delete","entry_id"} → hapus milik sendiri (server tak
        #   punya do_DELETE — hapus mentah 501 — jadi lewat POST).
        # Isolasi penuh: owner dari sesi login/header sesi; netral DITOLAK
        # 401 untuk semua op (daftar pun tak ada gunanya tanpa owner).
        if p == "/api/spatial/archive":
            if not self._token_ok():
                return self._unauth()
            _ow, _osc = _anna_owner_from_request(self)
            if not _ow:
                return self._json({"ok": False, "error": "arsip wajib lewat sesi user login"}, 401)
            if self.command == "GET" or not isinstance(body, dict) or not body:
                return self._json({"ok": True,
                                   "items": spatial_archive_store.list_archive(owner=_ow)})
            if body.get("op") == "move":
                eid = str(body.get("entry_id") or body.get("id") or "")
                if not eid:
                    return self._json({"ok": False, "error": "entry_id required"}, 400)
                try:
                    pos = int(body.get("to", 0))
                except Exception:
                    pos = 0
                ok, res = spatial_archive_store.move_archive(
                    owner=_ow, entry_id=eid, to=pos)
                if not ok:
                    return self._json({"ok": False, "error": res}, 404)
                return self._json({"ok": True, "moved": eid, "items": res})
            if body.get("op") == "delete":
                eid = str(body.get("entry_id") or body.get("id") or "")
                if not eid:
                    return self._json({"ok": False, "error": "entry_id required"}, 400)
                if not spatial_archive_store.delete_archive(owner=_ow, entry_id=eid):
                    return self._json({"ok": False, "error": "arsip tidak ditemukan"}, 404)
                return self._json({"ok": True, "deleted": eid,
                                   "items": spatial_archive_store.list_archive(owner=_ow)})
            if body.get("entry_id") or body.get("id"):
                st = spatial_archive_store.get_archive(
                    owner=_ow, entry_id=str(body.get("entry_id") or body.get("id")))
                if st is None:
                    return self._json({"ok": False, "error": "arsip tidak ditemukan"}, 404)
                kind = str(body.get("kind") or "").strip().lower()
                if not kind:
                    kind = "report" if st.get("pages") else "chart"
                if kind == "report":
                    ok, err = spatial_report_store.set_report(st, owner=_ow, scope=_osc)
                    if not ok:
                        return self._json({"ok": False, "error": err}, 400)
                    return self._json(dict(ok=True, restored="report",
                                           **spatial_report_store.get_state(owner=_ow)))
                ok, err = spatial_chart_store.set_chart(st, owner=_ow, scope=_osc)
                if not ok:
                    return self._json({"ok": False, "error": err}, 400)
                return self._json(dict(ok=True, restored="chart",
                                       **spatial_chart_store.get_state(owner=_ow)))
            kind = str(body.get("kind") or "").strip().lower()
            if kind == "report":
                live = spatial_report_store.get_state(owner=_ow)
            elif kind == "chart":
                live = spatial_chart_store.get_state(owner=_ow)
            else:
                return self._json({"ok": False, "error": "kind harus chart|report"}, 400)
            ok, res = spatial_archive_store.save_archive(
                owner=_ow, kind=kind, title=str(body.get("title") or ""),
                state=live, scope=_osc)
            if not ok:
                return self._json({"ok": False, "error": res}, 400)
            return self._json({"ok": True, "saved": res,
                               "items": spatial_archive_store.list_archive(owner=_ow)})
        if p == "/api/tpl":
            # Simpan penuh / reset default milik sendiri.
            if not self._token_ok():
                return self._unauth()
            _ow, _ = _anna_owner_from_request(self)
            if not _ow:
                return self._json({"ok": False, "error": "template wajib lewat sesi user login"}, 401)
            if not isinstance(body, dict) or not body:
                return self._json({"ok": True,
                                   "groups": tpl_store.list_tpl(owner=_ow)})
            if str(body.get("op") or "").strip().lower() == "reset":
                ok, res = tpl_store.reset_tpl(owner=_ow)
                if not ok:
                    return self._json({"ok": False, "error": res}, 400)
                return self._json({"ok": True, "groups": res})
            ok, res = tpl_store.set_tpl(owner=_ow, groups=body.get("groups"))
            if not ok:
                return self._json({"ok": False, "error": res}, 400)
            return self._json({"ok": True, "groups": res})
        if p == "/api/run":
            # Browser WAJIB cookie login valid: perangkat yang ditendang
            # (revoked) DITOLAK 401 dengan reason, walau token-nya benar.
            # Token-only tanpa cookie = jalur tool internal (ANNA system),
            # tetap boleh (kanal netral). Tanpa gate ini evict tak ada
            # gunanya: tablet yang ditendang tetap chat penuh via token.
            _run_has_cookie = False
            try:
                _raw_ck = self.headers.get("Cookie", "") or ""
                _run_has_cookie = bool(_parse_cookies(_raw_ck).get("ana_session", "").strip())
            except Exception:
                _run_has_cookie = False
            if _run_has_cookie and _session_from_cookie(self) is None:
                _st, _bd = _ana_auth_error(self)
                return self._json(_bd, _st)
            # Watchdog anti-409-nyangkut PER-USER: ijin run baru bila user ini
            # tak ada run aktif ATAU run-nya lewat RUN_TIMEOUT_SEC (300s).
            # Slot = _RUN_BY_USER[user_key]; kanal netral (""/token-only)
            # pakai RUN_STATE global seperti dulu. Tanpa slot per-user: satu
            # run A yang stall menahan SEMUA user lain dengan 409.
            _run_uk = ""
            try:
                _run_uk = _anna_user_key(self)
            except Exception:
                _run_uk = ""
            _run_slot = _RUN_BY_USER.setdefault(str(_run_uk or ""), {"active": False, "since": 0.0, "message": ""}) if _run_uk else RUN_STATE
            _allow_run = False
            _stale_msg = ""
            try:
                with RUN_STATE_GUARD:
                    # Flag boolean, BUKAN thread.is_alive(): thread koneksi
                    # keep-alive server hidup terus walau run sudah selesai —
                    # cek is_alive selalu True dan semua run 409 selamanya.
                    _busy = bool(_run_slot.get("active"))
                    _age = time.time() - float(_run_slot.get("since") or 0.0)
                    if not _busy:
                        _allow_run = True
                    elif _age > RUN_TIMEOUT_SEC:
                        _stale_msg = str(_run_slot.get("message") or "")[:60]
                        _allow_run = True
            except Exception:
                _allow_run = True
            if not _allow_run:
                try:
                    _log_to_file(f"[run] 409 ditolak: user={str(_run_uk)[:8] or '-'} holder_age={_age:.0f}s msg={str(_run_slot.get('message') or '')[:60]}")
                except Exception:
                    pass
                return self._json({"error": "ANA is already processing a request"}, 409)
            if _stale_msg:
                try:
                    _log_to_file(f"[run] stale run diambil alih (> {RUN_TIMEOUT_SEC:.0f}s): {str(_stale_msg)[:60]}")
                except Exception:
                    pass
            try:
                with RUN_STATE_GUARD:
                    _run_slot["active"] = True
                    _run_slot["since"] = time.time()
                    _run_slot["message"] = str((body.get("message") or "")[:60]) if isinstance(body, dict) else ""
                return self._stream_run(body)
            finally:
                try:
                    with RUN_STATE_GUARD:
                        _run_slot["active"] = False
                except Exception:
                    pass

        return self._json({"error": "no such endpoint"}, 404)

    # ── the run: NDJSON stream of events ─────────────────────
    def _stream_run(self, payload):
        # The body was parsed and type-checked in do_POST; re-reading the raw
        # bytes here meant a bare string or number crashed this thread after the
        # response headers were gone, so the client only saw a dropped socket.
        message = (payload.get("message") or "").strip()
        extra = (payload.get("system") or "").strip()
        fresh = bool(payload.get("fresh"))
        # Scope wilayah login → blok instruksi untuk ANNA (per-request, ikut
        # sesi saat itu). Tanpa sesi = tanpa blok (ANNA system bebas).
        # ANNA yang taat menolak permintaan di luar wilayah user; yang nakal
        # tetap dijegal tool-guard (ana_simoge_tool) + enforcement server.
        try:
            _run_scope = _wilayah_scope_from_session(self)
        except Exception:
            _run_scope = {}
        _scope_block = ""
        try:
            _scope_block = _anna_scope_block(_run_scope)
        except Exception:
            _scope_block = ""
        _ident_block = ""
        try:
            _ident_block = _anna_identity_block(self)
        except Exception:
            _ident_block = ""
        # System prompt (persona + wiki + scope + mode) hanya dikirim sekali
        # pada fresh=true (session baru). Turn berikutnya biarkan Hermes resume
        # session dengan konteks yang sudah ada — jangan inject ulang wiki/
        # persona setiap kali, boros token dan membuat setiap pesan user sertai
        # blok instruksi penuh.
        if fresh:
            system = "\n\n".join(x for x in (persona(), _ident_block, _scope_block, extra) if x) or None
        else:
            system = None
        # P0-B: ukur budget konteks per /api/run (static vs dynamic, chars).
        # ponytail: history/schema gateway-side belum terukur di sini; upgrade
        # lanjut = gateway usage + retriever counts saat P1.
        try:
            _b_base = _PERSONA_CACHE.get("base") or ""
            _b_wiki = wiki_block()
            _b_ctx = commands.context_block()
            _b_mode = get_mode()
            _b_overlay = ("[MODE: asisten] Untuk TTS: ringkas, no markdown/code/tabel. Struktur jawaban: kalimat pembuka MAKSIMAL 1x (jangan diulang), lalu isi (angka + insight), lalu 1 kalimat tawaran lanjut yang relevan (mis. bedah per bulan/petak). Jangan buka dengan filler tanpa isi. DILARANG menarasikan proses di jawaban (jangan tulis 'Siap render.../Menarik data.../Perbaiki autentikasi...') — langsung isi. Semua tool bisnis (packet/pandas/chart/peta) adalah TOOL BIASA — langsung execute_code TETAP di asisten, tanpa set_mode(coding). Chart/peta TIDAK butuh coding. TTS-only tanpa visual = GAGAL."
                          if _b_mode == "asisten" else
                          "[MODE: coding] Mode agen koding: boleh markdown, code block, tabel, path exact. Jelaskan lengkap & verifikasi pakai output real.")
            _budget_init = dict(t="budget", persona=len(_b_base), overlay=len(_b_overlay),
                                wiki=len(_b_wiki), context=len(_b_ctx), extra=len(extra),
                                message=len(message), system=len(system or ""))
        except Exception:  # noqa: BLE001
            _budget_init = None
        if not message:
            return self._json({"error": "empty message"}, 400)
        # Sesi ANNA per-user (pola resmi Hermes: key per user_id).
        _uk = _anna_user_key(self)
        # fresh = sesi baru: sid payload (sesi lama) JANGAN dipakai — kalau
        # tidak, run jatuh ke resume sesi lama padahal prompt lengkap baru
        # sudah dikirim. Isolasi penuh: clear + sid None → gateway create baru.
        if fresh:
            _clear_session(_uk)
            try:
                _GW_LIVE.pop(str(_uk), None)
            except Exception:
                pass
        _run_initial_mode = get_mode()  # snapshot for auto-restore: asisten→coding→asisten

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
        if _session_expired(_uk):
            _clear_session(_uk)

        # System prompt: kirim hanya saat fresh=true atau belum ada session aktif
        # (first message ever / setelah clear). Turn berikutnya biarkan Hermes
        # resume session — jangan inject ulang persona/wiki setiap kali.
        if system is None:
            _sid_chk, _ = _session_get(_uk)
            if _sid_chk is None:
                system = "\n\n".join(x for x in (persona(), _ident_block, _scope_block, extra) if x) or None

        def emit(ev):
            self.wfile.write((json.dumps(ev) + "\n").encode())
            self.wfile.flush()
        if _budget_init is not None:
            emit(_budget_init)
            try:
                _log_to_file(
                    f"[budget] persona={_budget_init['persona']} overlay={_budget_init['overlay']} "
                    f"wiki={_budget_init['wiki']} context={_budget_init['context']} "
                    f"extra={_budget_init['extra']} message={_budget_init['message']} "
                    f"system={_budget_init['system']}")
            except Exception:  # noqa: BLE001
                pass
        # -- the command matrix: /new /profile /goal /personality /kanban /mission /background /tools /status /browser
        cmd = commands.handle(
            message,
            # runner = misi background: JANGAN kirim persona lengkap — misi
            # jalan di sesi barunya sendiri, prompt lengkap boros dan bikin
            # pesan user tersertai blok instruksi penuh.
            runner=lambda m: runtime.run(m, None, None),
            owner=_uk)
        if cmd:
            if cmd.get("note"):
                emit(dict(t="note", message=cmd["note"]))
            if cmd.get("fresh"):
                _clear_session(_uk)
            if cmd.get("message") is None:
                # answered locally -- no model call needed
                emit(dict(t="delta", text=cmd.get("reply", "Done.")))
                emit(dict(t="complete", ms=0))
                return
            message = cmd["message"]
            # System prompt hanya saat fresh=true atau belum ada session aktif.
            # Turn berikutnya biarkan Hermes resume — jangan inject ulang.
            if cmd.get("fresh"):
                system = "\n\n".join(x for x in (persona(), _ident_block, _scope_block, extra) if x) or None
            else:
                _sid_cmd, _ = _session_get(_uk)
                if _sid_cmd is None:
                    system = "\n\n".join(x for x in (persona(), _ident_block, _scope_block, extra) if x) or None
                else:
                    system = None

        try:
            sid0, _ = _session_get(_uk)
            # fresh = sesi baru: sid payload/sid0 (sesi lama) JANGAN dipakai —
            # kalau tidak run jatuh ke resume sesi lama padahal prompt lengkap
            # baru sudah dikirim (lawan dari _clear_session di atas).
            if fresh:
                session_id = "default"
            else:
                session_id_raw = payload.get("session_id")
                session_id = (session_id_raw or sid0 or "default")
            if isinstance(session_id, str):
                session_id = session_id.strip()
            else:
                session_id = "default"
            # Isolasi live session per user: gateway punya _CURRENT_SESSION_ID
            # global yang dipakai ulang bila sid None/tak-valid. Tanpa peta
            # ini user B tanpa sesi aktif masuk ke live session user A.
            # Selalu teruskan sid live MILIK user ini eksplisit; bila tak ada
            # (fresh/arsip) reset global dulu agar gateway create baru.
            try:
                if session_id and runtime.valid_session(session_id):
                    try:
                        _GW_LIVE[str(_uk)] = str(session_id)
                    except Exception:
                        pass
                else:
                    try:
                        _GW_LIVE.pop(str(_uk), None)
                    except Exception:
                        pass
                    # Reset global HANYA bila tak ada user lain pegang live
                    # session — tanpa syarat ini reset memutus turn user lain
                    # yang sedang jalan (pola sama seperti _clear_session).
                    try:
                        _other_live = False
                        try:
                            with _SESSION_LOCK:
                                for _k, _e in SESSION.items():
                                    try:
                                        if str(_k) != str(_uk) and (_e or {}).get("id"):
                                            _other_live = True
                                            break
                                    except Exception:
                                        continue
                        except Exception:
                            _other_live = True
                        if not _other_live and not _GW_LIVE:
                            runtime.reset_session()
                    except Exception:
                        pass
                    session_id = "default"
            except Exception:
                pass
            # voice_metrics removed (rollback)
            _llm_first = False
            _run_deltas = []
            _run_user_pushed = []
            def _push_user(_sid):
                try:
                    if _run_user_pushed or not _sid or not runtime.valid_session(_sid):
                        return
                    _trans_push(_sid, "user", message)
                    _run_user_pushed.append(True)
                except Exception:
                    pass
            # sid awal (resume) langsung dapat pesan user — stream putus pun tersimpan.
            try:
                _push_user(session_id)
            except Exception:
                pass
            # Penanda sid yang sudah ditulis scope-nya run ini. Scope+current_sid
            # ditulis SECEPATNYA (event valid pertama, biasanya `status`), BUKAN
            # menunggu event `session` — tool ANNA jalan di tengah stream dan
            # butuh .ana_current_sid SUDAH ada saat push chart/report.
            _scope_sid_written = None
            # Scope wilayah user ini ditulis ke file per-sesi-Hermes saat sid
            # emisi tiba (di bawah) — tool ANNA baca HERMES_SESSION_ID-nya
            # sendiri. Bila run me-reuse sid0 yang sudah ada, tulis sekarang.
            try:
                if sid0 and runtime.valid_session(sid0):
                    _anna_scope_write(sid0, _run_scope, _uk)
                    _scope_sid_written = str(sid0)
            except Exception:
                pass
            # Callback sesi per-user: sid baru/resume/emitted dari turn ini
            # disimpan ke slot _GW_LIVE[user] — BUKAN global runtime.
            # Tanpa ini dua user paralel saling timpa _CURRENT_SESSION_ID.
            def _on_sid(_sid, _k=str(_uk)):
                try:
                    if _sid and runtime.valid_session(_sid):
                        _GW_LIVE[str(_k)] = str(_sid)
                except Exception:
                    pass
            for ev in runtime.run(message, session_id, system, on_session=_on_sid):
                # Only remember a real Hermes session, never demo/mock identifiers.
                sid = ev.get("session_id")
                # Tulis scope+current_sid pada event valid PERTAMA (status).
                # Tanpa ini tool yang jalan sebelum event `session` push tanpa
                # header sesi -> 401 walau scope file sesi itu sendiri ada.
                try:
                    if sid and sid != _scope_sid_written and runtime.valid_session(sid):
                        _anna_scope_write(sid, _run_scope, _uk)
                        _scope_sid_written = str(sid)
                except Exception:
                    pass
                # Save session when Hermes emits it (from session_id: marker)
                if ev.get("t") == "session" and runtime.valid_session(sid):
                    cur_id, cur_meta = _session_get(_uk)
                    _is_new = (cur_id != str(sid))
                    if _is_new:
                        _session_set(str(sid), key=_uk)
                    if cur_meta is None:
                        _session_set(str(sid), {"title": "--", "created": time.time(), "message_count": 0}, key=_uk)
                    try:
                        _session_hist_push(_uk, str(sid), None)
                    except Exception:
                        pass
                    _push_user(sid)
                    try:
                        _anna_scope_write(sid, _run_scope, _uk)
                    except Exception:
                        pass
                # Only remember a session that actually COMPLETED. Storing it from
                # `status` (which fires at init) means one broken run poisons every
                # run after it with --resume <half-born session>.
                if ev.get("t") == "usage":
                    tok = ev.get("total_tokens") or ev.get("output_tokens") or 0
                    try:
                        tok = int(tok)
                    except (TypeError, ValueError):
                        tok = 0
                    if tok:
                        pass  # voice_metrics removed (rollback)
                if ev.get("t") == "complete" and runtime.valid_session(sid):
                    _session_set(sid, key=_uk)
                    _session_bump_count(_uk)
                    try:
                        _push_user(sid)
                        txt = "".join(_run_deltas)
                        _trans_push(sid, "assistant", txt)
                    except Exception:
                        pass
                    try:
                        _anna_scope_write(sid, _run_scope, _uk)
                    except Exception:
                        pass
                    # voice_metrics removed (rollback) — token metrics stripped
                if ev.get("t") == "error":
                    _push_user(sid)
                    _clear_session(_uk)       # drop a bad/stale session so the next run is fresh
                if ev.get("t") == "delta" and isinstance(ev.get("text"), str):
                    try:
                        _run_deltas.append(ev.get("text") or "")
                    except Exception:
                        pass
                if ev.get("t") == "delta" and not _llm_first:
                    _llm_first = True
                    # voice_metrics removed (rollback)
                emit(ev)
        except (BrokenPipeError, ConnectionResetError):
            pass                                          # client navigated away
        except Exception as e:                            # noqa: BLE001
            try:
                emit(dict(t="error", message=str(e)[:300]))
            except OSError:
                pass
        finally:
            # Auto-restore: jika run diawali asisten lalu ANNA eskalasi ke coding,
            # balikin ke asisten agar run berikutnya tidak bocor markdown ke TTS.
            # Catatan: SEMUA tool bisnis (packet/pandas/chart/peta) adalah TOOL BIASA
            # di asisten — TIDAK butuh coding. Coding HANYA untuk artifact kode/file
            # (bukan bisnis); auto-restore hanya safety net bila lupa balik.
            try:
                cur = get_mode()
                ini = locals().get('_run_initial_mode', 'asisten')
                if ini == 'asisten' and cur == 'coding':
                    set_mode('asisten')
                    try: emit(dict(t='mode', mode='asisten', auto=True, reason='auto-restore after coding run'))
                    except Exception: pass
                    try: _log_to_file('[mode] auto-restore coding→asisten after run')
                    except Exception: pass
            except Exception:
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
    # Insight Engine scheduler (daemon; file-lock anti-bersamaan di dalam loop).
    try:
        threading.Thread(target=_insight_loop, daemon=True).start()
    except Exception as e:
        _alog(f"insight scheduler gagal start {type(e).__name__}", "warn")
    if os.environ.get("ANA_OPEN", "1") != "0":
        webbrowser.open(f"http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  down.")
        srv.shutdown()


if __name__ == "__main__":
    main()
