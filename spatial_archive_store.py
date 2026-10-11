"""
Spatial archive store — ARSIP chart/laporan per-user, persist server-side.

Pola sama seperti spatial_chart_store.py / spatial_report_store.py:
owner_key (= user_id login) -> daftar entry tersimpan. User simpan snapshot
state live (chart/report yang sedang tampil), tampilkan kembali kapan pun,
atau hapus. Isolasi penuh: user hanya lihat/hapus miliknya sendiri.

Persist ke disk (satu file JSON, atomic write) agar survive restart server —
tanpanya arsip hilang tiap ./start.sh dan fitur "simpan" jadi bohong.

Entry shape:
  { "id": str (unik per owner), "kind": "chart"|"report",
    "title": str, "saved_at": float (epoch),
    "scope": {kode_divre, kode_kph, ...} (stamp penulis, info saja),
    "state": dict (snapshot state live apa adanya) }

Batas: MAX_PER_USER (20) — simpan ke-21 tolak dengan pesan eksplisit
(jangan silent-drop: user harus tahu arsipnya tidak tersimpan).
"""
import json
import os
import threading
import time
import uuid

_LOCK = threading.Lock()
_ARCH = {}          # owner_key -> {entry_id: entry}
_LOADED = False
MAX_PER_USER = 20


def _path():
    try:
        base = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base = os.getcwd()
    return os.path.join(base, ".ana_archive.json")


def _load():
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    try:
        p = _path()
        if not os.path.exists(p):
            return
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return
        for owner, entries in d.items():
            if not isinstance(entries, dict):
                continue
            ok = str(owner or "")
            if not ok:
                continue
            bucket = _ARCH.setdefault(ok, {})
            for eid, e in entries.items():
                if isinstance(e, dict) and isinstance(e.get("state"), dict):
                    bucket[str(eid)[:64]] = e
    except Exception:
        pass


def _save():
    try:
        p = _path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_ARCH, f, ensure_ascii=False)
        os.replace(tmp, p)
    except OSError:
        pass


def _brief(e):
    st = e.get("state") or {}
    n = 0
    try:
        if e.get("kind") == "report":
            n = len(st.get("pages") or [])
        else:
            n = len(st.get("charts") or []) or (1 if st.get("chart") else 0)
    except Exception:
        n = 0
    return {"id": e.get("id"), "kind": e.get("kind"),
            "title": e.get("title") or "(tanpa judul)",
            "saved_at": float(e.get("saved_at") or 0.0),
            "ord": int(e.get("ord") or 0),
            "n_items": n}


def _renumber(bucket):
    """Samakan ord 0..n searah urutan dict (sumber kebenaran tampilan)."""
    for i, e in enumerate(bucket.values()):
        try:
            e["ord"] = i
        except Exception:
            pass


def _ensure_ord(bucket):
    """Migrasi entri lama tanpa ord: pertahankan urutan tampil kini
    (saved_at desc) lalu beri ord 0..n."""
    try:
        if bucket and all(isinstance(e, dict) and "ord" in e for e in bucket.values()):
            return
        ordered = sorted(bucket.values(),
                         key=lambda e: float((e or {}).get("saved_at") or 0.0),
                         reverse=True)
        bucket.clear()
        for e in ordered:
            bucket[e.get("id")] = e
        _renumber(bucket)
    except Exception:
        pass


def list_archive(owner=""):
    """Daftar ringkas milik owner (tanpa state penuh — ringan untuk drawer)."""
    _load()
    key = str(owner or "")
    if not key:
        return []
    with _LOCK:
        bucket = _ARCH.get(key) or {}
        _ensure_ord(bucket)
        items = [_brief(e) for e in bucket.values()]
    items.sort(key=lambda x: (x["ord"], -x["saved_at"]))
    return items


def save_archive(owner="", kind="", title="", state=None, scope=None):
    """Snapshot state live ke arsip. Return (True, entry_brief) / (False, err)."""
    _load()
    key = str(owner or "")
    if not key:
        return False, "arsip wajib lewat sesi user login"
    k = str(kind or "").strip().lower()
    if k not in ("chart", "report"):
        return False, "kind harus chart|report"
    if not isinstance(state, dict) or not state.get("visible"):
        return False, "tak ada chart/laporan yang tampil untuk disimpan"
    with _LOCK:
        bucket = _ARCH.setdefault(key, {})
        if len(bucket) >= MAX_PER_USER:
            return False, f"arsip penuh ({MAX_PER_USER}); hapus salah satu dulu"
        eid = uuid.uuid4().hex[:12]
        entry = {"id": eid, "kind": k,
                 "title": str(title or state.get("title") or "")[:120],
                 "saved_at": time.time(),
                 "ord": len(bucket),
                 "scope": dict(scope or {}),
                 "state": json.loads(json.dumps(state))}
        bucket[eid] = entry
        _save()
        return True, _brief(entry)


def get_archive(owner="", entry_id=""):
    """State penuh satu entry milik owner (untuk tampilkan kembali)."""
    _load()
    key = str(owner or "")
    eid = str(entry_id or "")
    if not key or not eid:
        return None
    with _LOCK:
        e = (_ARCH.get(key) or {}).get(eid)
        if not isinstance(e, dict):
            return None
        try:
            return json.loads(json.dumps(e.get("state")))
        except Exception:
            return None


def move_archive(owner="", entry_id="", to=0):
    """Pindah entry ke posisi `to` (0-based). Return (True, items)/(False, err)."""
    _load()
    key = str(owner or "")
    eid = str(entry_id or "")
    if not key or not eid:
        return False, "entry_id required"
    with _LOCK:
        bucket = _ARCH.get(key) or {}
        if eid not in bucket:
            return False, "arsip tidak ditemukan"
        _ensure_ord(bucket)
        order = list(bucket.keys())
        order.remove(eid)
        try:
            pos = int(to)
        except Exception:
            pos = len(order)
        pos = max(0, min(pos, len(order)))
        order.insert(pos, eid)
        # susun ulang dict searah order (dict menjaga urutan sisip py3.7+)
        tmp = {k: bucket[k] for k in order}
        bucket.clear()
        bucket.update(tmp)
        _renumber(bucket)
        _save()
        items = [_brief(e) for e in bucket.values()]
    items.sort(key=lambda x: (x["ord"], -x["saved_at"]))
    return True, items


def delete_archive(owner="", entry_id=""):
    _load()
    key = str(owner or "")
    eid = str(entry_id or "")
    if not key or not eid:
        return False
    with _LOCK:
        bucket = _ARCH.get(key) or {}
        if eid not in bucket:
            return False
        del bucket[eid]
        _save()
        return True
