"""
bit_case_store.py — Investigation Case Store (anna_spesialis_bisnis.md §G).
Deterministik file JSON, 0 LLM, thread-safe.
Gejala → pertanyaan → metrik+periode → hipotesis → query id → bukti pro/kontra → kesimpulan+kepastian → keputusan → hasil verifikasi.
False conclusion rate = closed cases where kepastian Terkonfirmasi/Didukung tapi hasil=gagal.
"""
import json, pathlib, threading, time, uuid, os
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data" / "bit_cases.json"
_LOCK = threading.Lock()
_ALLOWED_KEPASTIAN = ("Terkonfirmasi","Didukung","Belum teruji","Tidak didukung")
_ALLOWED_STATUS = ("open","closed","verified")

def _now_iso():
    try:
        return datetime.now(timezone.utc).astimezone().isoformat()
    except Exception:
        return time.strftime("%Y-%m-%dT%H:%M:%S+07:00")

def _load():
    if not DATA.exists():
        return []
    try:
        txt = DATA.read_text(encoding="utf-8").strip()
        if not txt:
            return []
        j = json.loads(txt)
        return j if isinstance(j, list) else []
    except Exception:
        return []

def _clean(v):
    import decimal
    if isinstance(v, decimal.Decimal):
        return float(v) if v % 1 else int(v)
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    return v

def _save(rows):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA.with_suffix(".tmp")
    clean = _clean(rows)
    txt = json.dumps(clean, ensure_ascii=False, indent=2)
    tmp.write_text(txt, encoding="utf-8")
    tmp.replace(DATA)

def _user_info_from_scope(scope, email=""):
    return {"email": email or "", "scope": dict(scope or {})}

def _snapshot_for(periode, scope):
    """Ambil snapshot BIT untuk reproducibility; toleran gagal (jangan block create)."""
    try:
        import bit_engine
        p = dict(periode or {})
        tahun = int(p.get("tahun", 2026)); bulan = int(p.get("bulan", 2)); periode_v = int(p.get("periode", 0))
        sd = str(p.get("sampai_dengan", "ya"))
        hypo = bit_engine.get_hypothesis(tahun, bulan, periode_v, scope=scope, sampai_dengan=sd)
        seb = None
        try:
            seb = bit_engine.get_sebaran(tahun, bulan, periode_v, scope=scope, sampai_dengan=sd)
        except Exception:
            seb = None
        return {
            "kpi": hypo.get("kpi"),
            "aktivitas": hypo.get("aktivitas"),
            "hypotheses": hypo.get("hypotheses"),
            "sebaran_level": (seb.get("level") if seb else None),
            "sebaran_top2": (seb.get("rows")[:2] if seb and seb.get("rows") else None),
            "query_ids": [
                {"template":"target_gap","params":{"tahun":tahun,"bulan":bulan,"periode":periode_v,"sampai_dengan":sd, **(scope or {})}},
                {"template":"diagnostic","params":{"tahun":tahun,"bulan":bulan,"periode":periode_v,"sampai_dengan":sd, **(scope or {})}},
                {"template":"hypothesis","params":{"tahun":tahun,"bulan":bulan,"periode":periode_v,"sampai_dengan":sd, **(scope or {})}},
                {"template":"sebaran","params":{"tahun":tahun,"bulan":bulan,"periode":periode_v,"sampai_dengan":sd, **(scope or {})}},
            ]
        }
    except Exception as e:
        return {"error": str(e)[:200], "query_ids": []}

def create_case(payload: dict, user_email="", scope=None):
    payload = dict(payload or {})
    gejala = str(payload.get("gejala") or payload.get("symptom") or "").strip()
    if len(gejala) < 5:
        raise ValueError("gejala minimal 5 karakter")
    if len(gejala) > 2000:
        raise ValueError("gejala maksimal 2000 karakter")
    pertanyaan = str(payload.get("pertanyaan") or payload.get("question") or "").strip()[:2000]
    kesimpulan = str(payload.get("kesimpulan") or payload.get("conclusion") or "").strip()[:3000]
    kepastian = str(payload.get("kepastian") or payload.get("certainty") or "Belum teruji").strip()
    if kepastian not in _ALLOWED_KEPASTIAN:
        kepastian = "Belum teruji"
    keputusan = str(payload.get("keputusan") or payload.get("decision") or "").strip()[:3000]
    periode = payload.get("periode") or {}
    # normalize periode
    if isinstance(periode, dict):
        try:
            periode = {
                "tahun": int(periode.get("tahun", 2026)),
                "bulan": int(periode.get("bulan", 2)),
                "periode": int(periode.get("periode", 0)),
                "sampai_dengan": str(periode.get("sampai_dengan", "ya")).lower()[:5],
                "scope": dict(periode.get("scope") or scope or {}),
            }
            if periode["sampai_dengan"] not in ("ya","tidak","y","t"): periode["sampai_dengan"]="ya"
            if periode["sampai_dengan"] in ("y","t"): periode["sampai_dengan"]="ya"
        except Exception:
            periode = {"tahun":2026,"bulan":2,"periode":0,"sampai_dengan":"ya","scope": dict(scope or {})}
    else:
        periode = {"tahun":2026,"bulan":2,"periode":0,"sampai_dengan":"ya","scope": dict(scope or {})}

    # snapshot auto if not provided
    snapshot = payload.get("snapshot")
    if not snapshot:
        snapshot = _clean(_snapshot_for(periode, scope))
    else:
        snapshot = _clean(snapshot)

    hip = payload.get("hipotesis") or payload.get("hypotheses") or snapshot.get("hypotheses") or []
    # ensure hipotesis is list of dict with id/label/status
    if isinstance(hip, list):
        hip = [dict(h) for h in hip[:8]]
    else:
        hip = []

    now = _now_iso()
    cid = "c_" + uuid.uuid4().hex[:8]
    case = {
        "id": cid,
        "created_at": now,
        "updated_at": now,
        "created_by": _user_info_from_scope(scope, user_email),
        "status": "open",
        "gejala": gejala,
        "pertanyaan": pertanyaan,
        "periode": periode,
        "snapshot": snapshot,
        "hipotesis": hip,
        "kesimpulan": kesimpulan,
        "kepastian": kepastian,
        "keputusan": keputusan,
        "hasil": payload.get("hasil") or {"catatan":"", "outcome":"belum", "verified_at": None},
        "tags": list(payload.get("tags") or [])[:10],
    }
    with _LOCK:
        rows = _load()
        rows.insert(0, case)
        # cap 500 cases (ponytail: file JSON cukup untuk <10k case)
        if len(rows) > 500:
            rows = rows[:500]
        _save(rows)
    return case

def _visible(case_scope, viewer):
    """Case boleh dilihat bila berada di dalam scope wilayah viewer.

    viewer {} = DIREKSI/ADMINISTRATOR (tanpa clamp) → semua case.
    viewer ber-scope = hanya case yang scope-nya memuat seluruh kode viewer.
    Case tanpa scope (global) hanya untuk viewer tanpa clamp."""
    view = {k: str(x).strip() for k, x in (viewer or {}).items()
            if k in ("kode_divre", "kode_kph", "kode_bkph", "kode_rph") and str(x or "").strip()}
    if not view:
        return True
    cs = dict(case_scope or {}) if isinstance(case_scope, dict) else {}
    if not cs:
        return False
    return all(str(cs.get(k) or "").strip() == val for k, val in view.items())


def list_cases(limit=50, offset=0, status=None, q=None, scope=None):
    with _LOCK:
        rows = _load()
    if scope is not None:
        rows = [r for r in rows if _visible((r.get("periode") or {}).get("scope") or r.get("scope"), scope)]
    # filter
    if status and status in _ALLOWED_STATUS:
        rows = [r for r in rows if r.get("status")==status]
    if q:
        qq = q.lower()
        rows = [r for r in rows if qq in json.dumps(r, ensure_ascii=False).lower()]
    total = len(rows)
    lim = max(1, min(200, int(limit or 50)))
    off = max(0, int(offset or 0))
    page = rows[off:off+lim]
    # stats for false conclusion
    # Terkonfirmasi/Didukung tapi hasil outcome=gagal
    false_n = sum(1 for r in rows if r.get("kepastian") in ("Terkonfirmasi","Didukung") and isinstance(r.get("hasil"),dict) and r["hasil"].get("outcome")=="gagal")
    closed_n = sum(1 for r in rows if r.get("status") in ("closed","verified"))
    false_rate = round(100*false_n/closed_n,1) if closed_n else None
    return {"rows": page, "total": total, "limit": lim, "offset": off, "false_n": false_n, "closed_n": closed_n, "false_rate_pct": false_rate}

def _case_scope_of(row):
    return (row.get("periode") or {}).get("scope") or row.get("scope")


def get_case(cid: str, scope=None):
    cid = str(cid or "").strip()
    if not cid:
        raise ValueError("id diperlukan")
    with _LOCK:
        rows = _load()
    for r in rows:
        if r.get("id")==cid:
            if scope is not None and not _visible(_case_scope_of(r), scope):
                raise PermissionError("case di luar wilayah login")
            return r
    raise KeyError(f"case {cid} tidak ditemukan")

def update_case(cid: str, patch: dict, user_email="", scope=None):
    cid = str(cid or "").strip()
    patch = dict(patch or {})
    with _LOCK:
        rows = _load()
        idx = next((i for i,r in enumerate(rows) if r.get("id")==cid), None)
        if idx is None:
            raise KeyError(f"case {cid} tidak ditemukan")
        if scope is not None and not _visible(_case_scope_of(rows[idx]), scope):
            raise PermissionError("case di luar wilayah login")
        cur = rows[idx]
        # allow fields: status, kesimpulan, kepastian, keputusan, hasil, tags, hipotesis
        if "status" in patch:
            s = str(patch["status"]).strip().lower()
            if s in _ALLOWED_STATUS:
                cur["status"]=s
        if "kesimpulan" in patch:
            cur["kesimpulan"]=str(patch["kesimpulan"])[:3000]
        if "kepastian" in patch:
            k = str(patch["kepastian"]).strip()
            if k in _ALLOWED_KEPASTIAN:
                cur["kepastian"]=k
        if "keputusan" in patch:
            cur["keputusan"]=str(patch["keputusan"])[:3000]
        if "hasil" in patch and isinstance(patch["hasil"], dict):
            h = cur.get("hasil") or {}
            for kk in ("catatan","outcome","verified_at"):
                if kk in patch["hasil"]:
                    h[kk]=patch["hasil"][kk]
            if not h.get("verified_at") and h.get("outcome") in ("sukses","gagal"):
                h["verified_at"]=_now_iso()
            cur["hasil"]=h
        if "tags" in patch and isinstance(patch["tags"], list):
            cur["tags"]=list(patch["tags"])[:10]
        if "hipotesis" in patch and isinstance(patch["hipotesis"], list):
            cur["hipotesis"]= [dict(x) for x in patch["hipotesis"][:8]]
        cur["updated_at"]=_now_iso()
        if user_email:
            cur.setdefault("updated_by", {})["email"]=user_email
        rows[idx]=cur
        _save(rows)
        return cur

def delete_case(cid: str, scope=None):
    cid = str(cid or "").strip()
    with _LOCK:
        rows = _load()
        if scope is not None:
            hit = next((r for r in rows if r.get("id")==cid), None)
            if hit is not None and not _visible(_case_scope_of(hit), scope):
                raise PermissionError("case di luar wilayah login")
        n0=len(rows)
        rows=[r for r in rows if r.get("id")!=cid]
        if len(rows)==n0:
            raise KeyError(f"case {cid} tidak ditemukan")
        _save(rows)
    return {"deleted": cid}
