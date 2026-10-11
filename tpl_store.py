"""Template pertanyaan per-user — default bawaan, bisa tambah/ubah/hapus.

Pola sama seperti spatial_archive_store.py: owner_key (= user_id login)
-> daftar grup pertanyaan. User baru otomatis dapat salinan DEFAULT
(dari TPL_DEFAULT di bawah — cerminan TPL_GROUPS di ui/src/main.js).
Edit milik sendiri tak pengaruhi user lain.

Persist ke disk (.ana_tpl.json, atomic write) agar survive restart.
Tanpa sesi login (owner kosong) semua op DITOLAK 401 di endpoint.
"""
import copy
import json
import os
import threading

_LOCK = threading.Lock()
_TPL = {}          # owner_key -> {"groups": [{"t": str, "q": [str]}]}
_LOADED = False

# Default = cerminan TPL_GROUPS di main.js. Ubah keduanya bersamaan bila
# menambah template bawaan (fallback frontend pakai copy-nya sendiri).
TPL_DEFAULT = [
    {"t": "RINGKASAN & LAPORAN", "q": [
        "Ringkasan sekarang KPH Banyuwangi Barat bulan ini",
        "Ringkasan sekarang BKPH KPH Banyuwangi Barat tahun ini",
        "Perbandingan bulan ini vs bulan lalu produksi KPH Banyuwangi Barat",
        "Tren produksi KPH Banyuwangi Barat selama tahun ini per bulan",
    ]},
    {"t": "PRODUKSI & TARGET", "q": [
        "Berapa produksi KPH Banyuwangi Barat bulan ini?",
        "Produksi Rogojampi bulan ini",
        "Berapa pencapaian target KPH Banyuwangi Barat bulan ini?",
        "Petak produksi tidak mencapai target bulan ini",
    ]},
    {"t": "PETAK", "q": [
        "Berapa jumlah petak KPH Banyuwangi Barat?",
        "Berapa luas baku KPH Banyuwangi Barat?",
        "Petak bongkor di Rogojampi tahun ini",
        "Petak idle di Glenmore tahun ini",
        "Petak tidak efektif di Licin tahun ini",
        "Daftar petak di KPH Banyuwangi Barat",
        "Detail petak 31211020110201_11B-1 (ganti kode petak)",
        "Petak tetangga di sekitar petak 31211020110201_11B-1 (ganti kode)",
    ]},
    {"t": "AKTIVITAS & PENYADAP", "q": [
        "Bagaimana aktivitas Glenmore bulan ini?",
        "Top petak aktivitas Rogojampi bulan ini",
        "Siapa penyadap di petak 31211020110201_11B-1? (ganti kode)",
        "Berapa produktivitas penyadap per TPG tahun ini?",
        "Matriks aktivitas vs petak Licin tahun ini",
        "Tampilkan bukti foto aktivitas Glenmore bulan ini",
    ]},
    {"t": "PETA", "q": [
        "Tampilkan polygon petak Licin di peta tahun ini",
        "Tampilkan polygon petak Rogojampi di peta tahun ini",
        "Tampilkan petak KPH Banyuwangi Barat di peta tahun ini",
        "Tampilkan petak DIVRE Jawa Timur di peta tahun ini",
        "Tampilkan aktivitas Glenmore bulan ini di peta",
        "Tampilkan pencapaian RKAP bulan ini di peta",
        "Ringkasan KPH seluruh DIVRE tahun ini tampilkan di peta",
    ]},
    {"t": "DATA", "q": [
        "Apakah data hari ini sudah masuk?",
        "Kapan terakhir update data?",
    ]},
]

MAX_GROUPS = 20
MAX_Q_PER_GROUP = 50


def _path():
    try:
        base = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        base = os.getcwd()
    return os.path.join(base, ".ana_tpl.json")


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
        for owner, payload in d.items():
            ok = str(owner or "")
            if not ok or not isinstance(payload, dict):
                continue
            groups = payload.get("groups")
            if isinstance(groups, list):
                clean = _clean_groups(groups)
                if clean:
                    _TPL[ok] = {"groups": clean}
    except Exception:
        pass


def _save():
    try:
        p = _path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_TPL, f, ensure_ascii=False)
        os.replace(tmp, p)
    except OSError:
        pass


def _clean_groups(groups):
    """Normalisasi list grup mentah -> list valid (buang yang rusak)."""
    out = []
    for g in groups:
        if not isinstance(g, dict):
            continue
        t = str(g.get("t") or "").strip()[:60]
        q = g.get("q")
        if not t or not isinstance(q, list):
            continue
        qs = [str(x).strip()[:300] for x in q
              if isinstance(x, str) and str(x).strip()][:MAX_Q_PER_GROUP]
        if not qs:
            continue
        out.append({"t": t, "q": qs})
    return out[:MAX_GROUPS]


def list_tpl(owner=""):
    """Daftar grup milik owner; user baru dapat salinan default."""
    _load()
    key = str(owner or "")
    if not key:
        return []
    with _LOCK:
        if key not in _TPL:
            _TPL[key] = {"groups": copy.deepcopy(TPL_DEFAULT)}
            _save()
        return copy.deepcopy(_TPL[key]["groups"])


def set_tpl(owner="", groups=None):
    """Timpa seluruh daftar milik owner. Return (True, groups)/(False, err)."""
    _load()
    key = str(owner or "")
    if not key:
        return False, "template wajib lewat sesi user login"
    if not isinstance(groups, list):
        return False, "groups harus list"
    clean = _clean_groups(groups)
    if not clean:
        return False, "minimal 1 grup berisi 1 pertanyaan"
    with _LOCK:
        _TPL[key] = {"groups": clean}
        _save()
        return True, copy.deepcopy(clean)


def reset_tpl(owner=""):
    """Kembalikan milik owner ke default bawaan."""
    _load()
    key = str(owner or "")
    if not key:
        return False, "template wajib lewat sesi user login"
    with _LOCK:
        _TPL[key] = {"groups": copy.deepcopy(TPL_DEFAULT)}
        _save()
        return True, copy.deepcopy(_TPL[key]["groups"])


# Self-check runnable: python3 tpl_store.py
if __name__ == "__main__":
    _ARCH_BAK = dict(_TPL)
    _TPL.clear()
    _LOADED = True
    g = list_tpl("u1")
    assert len(g) == 6 and g[0]["t"] == "RINGKASAN & LAPORAN", g
    g[0]["q"].append("baru?")
    ok, res = set_tpl("u1", g)
    assert ok and isinstance(res, list) and res[0]["q"][-1] == "baru?", res
    g2 = list_tpl("u2")
    assert all("baru?" not in x["q"] for x in g2), "isolasi bocor"
    ok, res = set_tpl("u1", [])
    assert not ok, "grup kosong harus ditolak"
    ok, res = reset_tpl("u1")
    assert ok and isinstance(res, list) and all("baru?" not in x["q"] for x in res), res
    _TPL.clear()
    _TPL.update(_ARCH_BAK)
    print("tpl_store self-check OK")
