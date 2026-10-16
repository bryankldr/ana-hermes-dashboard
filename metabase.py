"""metabase.py — proxy server-side ke Metabase MAXBI (deterministik, tanpa LLM).

- Kredensial HANYA dari .env (MB_API_KEY / MB_BASE_URL), dibaca per panggilan
  agar rotasi key tak perlu restart — ikut pola db_source.py.
- Key tak pernah keluar lewat API/log (log hanya key_len, ikut pola db_source).
- stdlib saja (urllib), tanpa dependency baru.
- User-Agent browser-like: Cloudflare di depan bi.kphbwb.web.id menolak
  UA default python (error 1010).
- Semua fungsi mengembalikan dict {ok: ...}, tak pernah raise — ramah server.
"""
import json
import pathlib
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"

UA = "Mozilla/5.0 (X11; Linux x86_64) ANA-Dashboard"
TIMEOUT = 25
CACHE_TTL = 300.0
MAX_ROWS = 50

_LOCK = threading.Lock()
_CACHE = {}


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
    if " #" in s:
        s = s.split(" #", 1)[0].strip()
    return s.strip().strip('"').strip("'")


def _read_env() -> dict:
    env = {}
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = _parse_env_value(v)
    except OSError:
        pass
    return env


def base_url() -> str:
    return (_read_env().get("MB_BASE_URL", "") or "").strip().rstrip("/")


def configured() -> bool:
    env = _read_env()
    return bool((env.get("MB_BASE_URL") or "").strip() and (env.get("MB_API_KEY") or "").strip())


def _req(method: str, path: str, body=None):
    """(status, payload). payload dict/list/str; error -> (code, {"message": ...})."""
    env = _read_env()
    base = (env.get("MB_BASE_URL") or "").strip().rstrip("/")
    key = (env.get("MB_API_KEY") or "").strip()
    if not base or not key:
        return 0, {"message": "metabase belum dikonfigurasi (MB_BASE_URL/MB_API_KEY kosong)"}
    headers = {"User-Agent": UA, "x-api-key": key}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, raw[:500]
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            detail = ""
        try:
            detail = json.loads(detail)
            if isinstance(detail, dict):
                detail = detail.get("message") or detail.get("errors") or detail
        except Exception:
            pass
        return e.code, {"message": f"metabase {e.code}: {str(detail)[:200]}"}
    except Exception as e:  # noqa: BLE001 — timeout/DNS/Cloudflare
        return 0, {"message": f"metabase tak terjangkau: {e}"[:200]}


def _cache_get(key: str):
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and (time.time() - hit[0]) < CACHE_TTL:
            return hit[1]
    return None


def _cache_put(key: str, value):
    with _LOCK:
        _CACHE[key] = (time.time(), value)


def status() -> dict:
    """Ringkasan aman untuk API (tanpa key, tanpa user detail sensitif)."""
    env = _read_env()
    base = (env.get("MB_BASE_URL") or "").strip().rstrip("/")
    if not base or not (env.get("MB_API_KEY") or "").strip():
        return dict(ok=False, configured=False, error="MB_BASE_URL/MB_API_KEY belum di-set")
    host = urllib.parse.urlparse(base).netloc or base
    st, me = _req("GET", "/api/user/current")
    if st != 200 or not isinstance(me, dict):
        err = me.get("message") if isinstance(me, dict) else me
        return dict(ok=False, configured=True, base=host, error=str(err)[:200])
    return dict(ok=True, configured=True, base=host,
                account=str(me.get("first_name") or "metabase")[:40],
                admin=bool(me.get("is_superuser")))


def list_dashboards(refresh: bool = False) -> dict:
    hit = None if refresh else _cache_get("dashboards")
    if hit is not None:
        return dict(ok=True, dashboards=hit, cached=True)
    st, data = _req("GET", "/api/dashboard")
    items = []
    if st == 200:
        coll = data if isinstance(data, list) else data.get("data", [])
        for d in coll if isinstance(coll, list) else []:
            items.append({"id": d.get("id"), "name": d.get("name"),
                          "collection": d.get("collection_name") or d.get("collection_id")})
        _cache_put("dashboards", items)
        return dict(ok=True, dashboards=items, cached=False)
    err = data.get("message") if isinstance(data, dict) else data
    return dict(ok=False, error=str(err)[:200])


def search(q: str, limit: int = 10) -> dict:
    q = (q or "").strip()[:100]
    if not q:
        return dict(ok=False, error="q kosong")
    st, data = _req("GET", "/api/search?" + urllib.parse.urlencode({"q": q}))
    if st != 200 or not isinstance(data, dict):
        err = data.get("message") if isinstance(data, dict) else data
        return dict(ok=False, error=str(err)[:200])
    items = [{"model": i.get("model"), "id": i.get("id"), "name": i.get("name")}
             for i in (data.get("data") or [])[:max(1, min(limit, 25))]
             if i.get("model") in ("card", "dashboard")]
    return dict(ok=True, items=items)


def get_card(card_id: int) -> dict:
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return dict(ok=False, error="card_id harus angka")
    st, data = _req("GET", f"/api/card/{cid}")
    if st != 200 or not isinstance(data, dict):
        err = data.get("message") if isinstance(data, dict) else data
        return dict(ok=False, error=str(err)[:200])
    dq = data.get("dataset_query") or {}
    return dict(ok=True, card={"id": data.get("id"), "name": data.get("name"),
                               "display": data.get("display"),
                               "description": (data.get("description") or "")[:300],
                               "database": dq.get("database")})


def run_card(card_id: int, params=None) -> dict:
    try:
        cid = int(card_id)
    except (TypeError, ValueError):
        return dict(ok=False, error="card_id harus angka")
    st, data = _req("POST", f"/api/card/{cid}/query", params or {})
    if st not in (200, 202) or not isinstance(data, dict):
        err = data.get("message") if isinstance(data, dict) else data
        return dict(ok=False, error=str(err)[:200])
    d = data.get("data") or {}
    if d.get("status") == "failed":
        return dict(ok=False, error=str(d.get("error") or data.get("error"))[:200])
    cols = [c.get("name", "") for c in (d.get("cols") or [])]
    rows = d.get("rows") or []
    return dict(ok=True, card_id=cid, columns=cols, rows=rows[:MAX_ROWS],
                row_count=len(rows), truncated=len(rows) > MAX_ROWS)


def run_sql(database_id: int, sql: str) -> dict:
    try:
        dbid = int(database_id)
    except (TypeError, ValueError):
        return dict(ok=False, error="database_id harus angka")
    sql = (sql or "").strip()
    if not sql or len(sql) > 8000:
        return dict(ok=False, error="sql kosong / terlalu panjang")
    lowered = sql.lower()
    if not lowered.startswith("select") and not lowered.startswith("with"):
        return dict(ok=False, error="hanya SELECT/WITH yang diizinkan")
    st, data = _req("POST", "/api/dataset", {"database": dbid, "type": "native",
                                             "native": {"query": sql}})
    if st not in (200, 202) or not isinstance(data, dict):
        err = data.get("message") if isinstance(data, dict) else data
        return dict(ok=False, error=str(err)[:200])
    d = data.get("data") or {}
    if d.get("status") == "failed":
        return dict(ok=False, error=str(d.get("error") or data.get("error"))[:200])
    cols = [c.get("name", "") for c in (d.get("cols") or [])]
    rows = d.get("rows") or []
    return dict(ok=True, columns=cols, rows=rows[:MAX_ROWS],
                row_count=len(rows), truncated=len(rows) > MAX_ROWS)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def to_chart(result: dict, title: str = "") -> dict:
    """Hasil run_* -> chart_spec + kpi untuk tile existing. Skalar (1x1) jadi KPI."""
    cols = result.get("columns") or []
    rows = result.get("rows") or []
    title = (title or "MAXBI")[:80]
    if len(cols) >= 1 and len(rows) == 1 and len(rows[0]) == 1:
        val = rows[0][0]
        return dict(kpis=[{"label": cols[0] or title, "value": val,
                           "unit": "", "tone": "neutral"}],
                    charts=[], title=title)
    labels = [str(r[0])[:40] for r in rows] if rows and len(cols) >= 1 else []
    datasets = []
    for j in range(1, min(len(cols), 4)):
        datasets.append({"label": cols[j][:40],
                         "data": [_num(r[j]) if j < len(r) else 0.0 for r in rows]})
    if not datasets and rows:
        datasets = [{"label": (cols[0] if cols else "nilai")[:40],
                     "data": [_num(r[0]) for r in rows]}]
    return dict(kpis=[], title=title,
                charts=[{"type": "bar", "title": title, "labels": labels,
                         "datasets": datasets}])
