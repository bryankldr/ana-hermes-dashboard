#!/usr/bin/env python3
"""
SIMOGE read-only MariaDB executor + verified business query templates.

ponytail: single shared connection, not a pool — pymysql connections are cheap
to recreate and the dashboard issues a handful of queries per turn. Add a real
pool only if concurrent load shows reconnect latency.
"""
import datetime
import json
import os
import pathlib
import re
import time

import pymysql

# Load .env from dashboard if env vars missing (ANA runs in Hermes venv
# without the dashboard's .env sourced). Safe to call repeatedly.
if not os.getenv("SIMOGE_DB_PASSWORD") and not os.getenv("DB_PASSWORD"):
    for p in pathlib.Path(__file__).resolve().parents:
        cand = p / "ana-hermes-dashboard" / ".env"
        if cand.exists():
            for line in cand.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k, v.strip().strip('"').strip("'"))
            break

CURRENT_YEAR = datetime.date.today().year

# DB source switch: ANA_DB_SOURCE=local|remote via dashboard db_source.py.
# Lokal: DB_* · Remote: REMOTE_DB_* via kphbwb-tunnel 127.0.0.1:13307.
def _db_dict():
    try:
        import sys as _sys
        _root = None
        for p in pathlib.Path(__file__).resolve().parents:
            if (p / "ana-hermes-dashboard" / "db_source.py").exists():
                _root = p / "ana-hermes-dashboard"
                break
        if _root and str(_root) not in _sys.path:
            _sys.path.insert(0, str(_root))
        import db_source
        kw = db_source.kwargs()
        return dict(host=kw["host"], port=kw["port"], user=kw["user"],
                    password=kw["password"], database=kw["database"])
    except Exception:
        pass
    return dict(
        host=os.getenv("SIMOGE_DB_HOST", os.getenv("DB_HOST", "127.0.0.1")),
        port=int(os.getenv("SIMOGE_DB_PORT", os.getenv("DB_PORT", "3306"))),
        user=os.getenv("SIMOGE_DB_USER", os.getenv("DB_USER", "root")),
        password=os.getenv("SIMOGE_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
        database=os.getenv("SIMOGE_DB_NAME", os.getenv("DB_NAME", "kph_bwb_sandbox2")),
    )

DB = dict(
    **_db_dict(),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=True,
    connect_timeout=10,
    read_timeout=60,
)

_conn = None


def conn():
    global _conn
    if _conn is None or not _conn.open:
        _conn = pymysql.connect(**DB)
    return _conn


def reset_conn():
    """Tutup koneksi shared agar query berikut baca DB terbaru (switch source)."""
    global _conn, DB
    try:
        if _conn is not None and _conn.open:
            _conn.close()
    except Exception:
        pass
    _conn = None
    try:
        DB.update(_db_dict())
    except Exception:
        pass


_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|REPLACE|DROP|CREATE|ALTER|TRUNCATE|GRANT|REVOKE|"
    r"COMMIT|ROLLBACK|LOAD|CALL|EXECUTE|SET|LOCK|UNLOCK|OUTFILE|DUMPFILE)\b",
    re.IGNORECASE,
)


def q(sql, params=None):
    """Run one read-only statement. Returns {columns, rows, row_count, elapsed_ms}."""
    if _FORBIDDEN.search(sql):
        raise ValueError("read-only: statement blocked")
    if not re.match(r"^\s*(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN)\b", sql, re.IGNORECASE):
        raise ValueError("read-only: must start with SELECT/WITH/SHOW/DESCRIBE/EXPLAIN")
    t0 = time.perf_counter()
    with conn().cursor() as cur:
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
    return {
        "columns": cols,
        "rows": [dict(zip(cols, r.values())) for r in rows] if rows else [],
        "row_count": len(rows),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
        "sql": " ".join(sql.split()),
    }


# ── period helper ───────────────────────────────────────────────
# Periode 1 = tanggal 1-15, Periode 2 = tanggal 16-akhir bulan.
# Periode 0 (atau "full") = satu bulan penuh (P1+P2 sekaligus).
_FULL_P = (0, "0", "full", "FULL")


def period_bounds(year, month, periode):
    """Return (start_date, end_date) for a periode. end is inclusive.
    periode 0 = bulan penuh (P1+P2)."""
    import calendar
    last = calendar.monthrange(year, month)[1]
    if periode in _FULL_P:
        return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}"
    if periode == 1:
        return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-15"
    return f"{year:04d}-{month:02d}-16", f"{year:04d}-{month:02d}-{last:02d}"


def _prev_month(year, month):
    return (year, month - 1) if month > 1 else (year - 1, 12)


def _prev_period_bounds(year, month, periode):
    """Periode sebelumnya untuk logika idle/bongkor.
    P2→P1 bulan sama · P1→P2 bulan lalu · 0(bulan penuh)→0 bulan lalu."""
    if periode in _FULL_P:
        return period_bounds(*_prev_month(year, month), 0)
    if periode == 2:
        return period_bounds(year, month, 1)
    return period_bounds(*_prev_month(year, month), 2)


# Nilai pembaharuan_ke yang sah di getah_aktivitas_sadap. Live DB (2026-10)
# hanya punya 1/2/3 — 4 dijaga supaya filter tak crash, hasilnya 0 baris.
PEMBARUAN_KE = ("1", "2", "3", "4")


def _pembaharuan_where(kw, alias="s"):
    """Filter pembaharuan_ke opsional untuk getah_aktivitas_sadap.
    Return (sql_frag, vals). 'semua'/''/None = tanpa filter."""
    v = kw.get("pembaharuan_ke")
    s = str(v).strip() if v is not None else ""
    if s == "" or s.lower() in ("semua", "all", "0"):
        return "", []
    if s not in PEMBARUAN_KE:
        raise ValueError(
            f"pembaharuan_ke harus salah satu {PEMBARUAN_KE} atau 'semua', bukan {v!r}")
    return f" AND {alias}.pembaharuan_ke = %s", [s]


# ── templates ──────────────────────────────────────────────────
T = {}


def template(name):
    def deco(fn):
        T[name] = fn
        return fn
    return deco


def describe(template: str) -> dict:
    """P1.1 retrieval: info satu template tanpa kirim 38 template ke model."""
    fn = T.get(template)
    if fn is None:
        return {"ok": False, "error": f"unknown template: {template}", "available": sorted(T.keys())}
    import inspect
    return {"ok": True, "template": template, "doc": (inspect.getdoc(fn) or "").strip(), "params": list(inspect.signature(fn).parameters.keys()), "tool": "call_simoge_packet"}

# helper wilayah — *_map di-where di DB, bukan client post-filter (SPATIAL MAP scoped)
_WILAYAH_COLS = ("kode_divre", "kode_kph", "kode_bkph", "kode_rph", "kode_tpg")
_WILAYAH_NAMES = {"kode_divre": "divre", "kode_kph": "kph", "kode_bkph": "bkph",
                  "kode_rph": "rph", "kode_tpg": "nama_tpg"}


# -- gradasi warna polygon (bisnis kontinu): kunci `warna` (diskrit) tetap
# untuk KPI/hitungan; `warna_hex` memberi warna render kontinu per fitur.
# Klien pakai warna_hex bila ada, else WARNA_STYLE (tanpa regresi).
_GRAD_PRODUKSI = ((0, "EF4444"), (25, "F97316"), (50, "EAB308"),
                  (75, "22C55E"), (100, "22C55E"), (120, "3B82F6"))
_GRAD_COVERAGE = ((0, "EAB308"), (1, "22C55E"))          # rasio andil/baku
_GRAD_AKTIF = ((1, "22C55E"), (15, "3B82F6"))            # intensitas 1..15+


def _lerp_hex(stops, x):
    """Interpolasi linear heksa antar stop ((nilai, 'RRGGBB'), ...). Clamp tepi."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    if not stops:
        return None
    if x <= stops[0][0]:
        return "#" + stops[0][1]
    for (x0, c0), (x1, c1) in zip(stops, stops[1:]):
        if x <= x1:
            t = (x - x0) / (x1 - x0) if x1 != x0 else 1.0
            r0, g0, b0 = int(c0[0:2], 16), int(c0[2:4], 16), int(c0[4:6], 16)
            r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
            return "#%02X%02X%02X" % (round(r0 + (r1 - r0) * t),
                                      round(g0 + (g1 - g0) * t),
                                      round(b0 + (b1 - b0) * t))
    return "#" + stops[-1][1]


def _paint_produksi(row):
    """Gradasi capaian; target-nol (warna NULL) = tanpa hex (fallback klien)."""
    if row.get("warna") is None:
        return None
    try:
        return _lerp_hex(_GRAD_PRODUKSI, float(row.get("pencapaian_pct") or 0))
    except (TypeError, ValueError):
        return None


def _paint_coverage(row):
    """Bongkor = merah solid; berpenyadap = kuning-hijau by andil/baku."""
    try:
        if (row.get("kategori") or row.get("warna")) in ("bongkor", "merah"):
            return "#EF4444"
        baku = float(row.get("luas_baku") or 0)
        if baku <= 0:
            return None
        return _lerp_hex(_GRAD_COVERAGE, float(row.get("luas_andil") or 0) / baku)
    except (TypeError, ValueError):
        return None


def _paint_aktivitas(row):
    """Bongkor merah solid, idle kuning solid, aktif hijau-biru by intensitas."""
    try:
        kat = str(row.get("kategori") or row.get("warna") or "").lower()
        if kat in ("bongkor", "merah"):
            return "#EF4444"
        if kat in ("idle", "kuning"):
            return "#EAB308"
        return _lerp_hex(_GRAD_AKTIF, float(row.get("jumlah_aktivitas") or 0))
    except (TypeError, ValueError):
        return None


def _paint_rows(rows, painter):
    for _r in (rows or []):
        try:
            _h = painter(_r)
        except Exception:
            _h = None
        if _h:
            _r["warna_hex"] = _h
    return rows

def _require_level(level):
    """GROUP BY dinamis hanya dari allowlist — cegah injeksi via param `level`."""
    if level not in _WILAYAH_COLS:
        raise ValueError(f"bad level: {level}. ada: {list(_WILAYAH_COLS)}")
    return level

def _wilayah_where(kw, alias="p"):
    """Return (sql_frag, params) untuk {alias}.kode_* yang ada di kw. Allowlist, paramised."""
    parts, vals = [], []
    for col in _WILAYAH_COLS:
        v = kw.get(col)
        if v is None or str(v).strip() == "":
            continue
        s = str(v).strip()
        if not s.isdigit():
            continue
        parts.append(f"{alias}.{col} = %s")
        vals.append(int(s))
    if not parts:
        return "", []
    return " AND " + " AND ".join(parts), vals


def _bbox_sql(bounds):
    """Filter spatial viewport. bounds=[west,south,east,north]
    atau string "[w,s,e,n]" (via spatial_set str()).
    petak_polygon.polygon = GeoJSON longtext (TANPA kolom geom spasial) —
    filter via ST_GeomFromGeoJSON(pp.polygon), bukan pp.geom yang tak ada
    (Unknown column 1054 → panel blank tiap kirim bounds).
    MBRContains dulu, ST_Intersects exact sesudahnya.
    Return (sql_frag, vals). bounds kosong/invalid = tanpa filter."""
    if isinstance(bounds, str):
        s = bounds.strip()
        if not s:
            return "", []
        try:
            import json as _js
            bounds = _js.loads(s) if s.startswith("[") else [x.strip() for x in s.split(",")]
        except Exception:
            return "", []
    if not bounds or len(bounds) != 4:
        return "", []
    try:
        west, south, east, north = (float(bounds[0]), float(bounds[1]),
                                    float(bounds[2]), float(bounds[3]))
    except (TypeError, ValueError):
        return "", []
    if not (-180 <= west <= 180 and -180 <= east <= 180
            and -90 <= south <= 90 and -90 <= north <= 90):
        return "", []
    if west >= east or south >= north:
        return "", []
    poly = ("POLYGON((%s %s, %s %s, %s %s, %s %s, %s %s))")
    vals = [west, south, east, south, east, north, west, north, west, south]
    frag = (f" AND MBRContains(ST_GeomFromText('{poly}'), ST_GeomFromGeoJSON(pp.polygon))"
            f" AND ST_Intersects(ST_GeomFromText('{poly}'), ST_GeomFromGeoJSON(pp.polygon))")
    return frag, vals + vals


def _page_size(kw, default=500):
    """LIMIT efektif viewport: page_size clamp 50-2000, fallback limit/default."""
    try:
        v = int(kw.get("page_size", kw.get("limit", default)))
    except (TypeError, ValueError):
        v = default
    return max(50, min(2000, v))


def _target_pct(tahun, bulan, periode):
    """Persen RO kumulatif s/d (bulan, periode) sebagai skalar float.
    P2 = Σ(p1+p2) Jan..bulan; P1 = bulan penuh sebelum + p1 berjalan.
    Skalar via Python — JOIN getah_target_ro_nps per-baris ikut perkalian
    (polygon-dup × 12 baris persen) sehingga target_periode ganda di
    petak ber-polygon ganda. Seluruh pemakai target_expr wajib lewat sini."""

    if periode == 2:
        rows = q(
            "SELECT COALESCE(SUM(ro_periode_1 + ro_periode_2), 0) AS p "
            "FROM getah_target_ro_nps WHERE tahun = %s AND bulan BETWEEN 1 AND %s",
            (tahun, bulan))["rows"]
    else:
        rows = q(
            "SELECT COALESCE((SELECT SUM(ro_periode_1 + ro_periode_2) "
            "FROM getah_target_ro_nps WHERE tahun = %s AND bulan < %s), 0) "
            "+ COALESCE((SELECT ro_periode_1 FROM getah_target_ro_nps "
            "WHERE tahun = %s AND bulan = %s), 0) AS p",
            (tahun, bulan, tahun, bulan))["rows"]
    return float(rows[0]["p"] or 0)


@template("petak_count")
def petak_count(tahun, **kw):
    """Jumlah petak RTT per tahun."""
    return q("""
        SELECT tahun_rtt AS tahun, COUNT(*) AS jumlah_petak,
               ROUND(SUM(luas_baku), 2) AS total_luas_baku
        FROM getah_petak
        WHERE tahun_rtt = %s
        GROUP BY tahun_rtt
    """, (tahun,))


@template("petak_area")
def petak_area(tahun, **kw):
    """Luas baku RTT per tahun, plus luas andil terpakai. Scoped bila wilayah filter diberi."""
    w, wv = _wilayah_where(kw)
    return q(f"""
        SELECT p.tahun_rtt AS tahun,
               COUNT(*) AS jumlah_petak,
               ROUND(SUM(p.luas_baku), 2) AS luas_baku_total,
               ROUND(SUM(COALESCE(a.luas_andil, 0)), 2) AS luas_andil_total,
               ROUND(100 * SUM(COALESCE(a.luas_andil, 0)) / NULLIF(SUM(p.luas_baku), 0), 2)
                 AS rasio_andil_pct
        FROM getah_petak p
        LEFT JOIN (
            SELECT kode_evapot, SUM(luas_andil) AS luas_andil
            FROM getah_andil GROUP BY kode_evapot
        ) a ON a.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s{w}
        GROUP BY p.tahun_rtt
    """, (tahun, *wv))


@template("petak_by_kph")
def petak_by_kph(tahun, level="kode_kph", **kw):
    """Distribusi petak per wilayah (allowlist level + nama manusia)."""
    _require_level(level)
    ncol = _WILAYAH_NAMES[level]
    return q(f"""
        SELECT {level} AS kode, MAX({ncol}) AS nama_wilayah, COUNT(*) AS jumlah_petak,
               ROUND(SUM(luas_baku), 2) AS luas_baku
        FROM getah_petak
        WHERE tahun_rtt = %s
        GROUP BY {level} ORDER BY jumlah_petak DESC
    """, (tahun,))


@template("petak_with_geometry")
def petak_with_geometry(tahun, limit=1000, **kw):
    """Petak RTT + geometry. Join via kode_evapot (kode_petak is NULL in this DB)."""
    return q("""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.tahun_rtt,
               p.target_rkap, p.kode_divre, p.kode_kph, p.kode_bkph, p.kode_rph, p.kode_tpg,
               pp.polygon
        FROM getah_petak p
        JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL
        LIMIT %s
    """, (tahun, limit))


@template("petak_effectiveness")
def petak_effectiveness(tahun, **kw):
    """Efektivitas petak: tidak ada penyadap / luas_andil < luas_baku / >= luas_baku."""
    return q("""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.target_rkap,
               COALESCE(a.penyadap, 0) AS jumlah_penyadap,
               COALESCE(a.luas_andil, 0) AS luas_andil,
               CASE
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'bongkor'
                   WHEN COALESCE(a.luas_andil, 0) < p.luas_baku THEN 'kurang'
                   ELSE 'terpenuhi'
               END AS kategori,
               CASE
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'merah'
                   WHEN COALESCE(a.luas_andil, 0) < p.luas_baku THEN 'kuning'
                   ELSE 'hijau'
               END AS warna
        FROM getah_petak p
        LEFT JOIN (
            SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap, GROUP_CONCAT(DISTINCT nama_penyadap SEPARATOR ', ') AS nama_penyadap,
                   SUM(luas_andil) AS luas_andil
            FROM getah_andil GROUP BY kode_evapot
        ) a ON a.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s
        ORDER BY luas_andil / NULLIF(p.luas_baku, 0)
    """, (tahun,))


@template("petak_bongkor")
def petak_bongkor(tahun, **kw):
    """Petak bongkor: tidak ada penyadap sama sekali."""
    return q("""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.kode_kph, p.kode_bkph
        FROM getah_petak p
        WHERE p.tahun_rtt = %s
          AND NOT EXISTS (SELECT 1 FROM getah_andil a WHERE a.kode_evapot = p.kode_evapot)
        ORDER BY p.luas_baku DESC
    """, (tahun,))

@template("petak_bongkor_map")
def petak_bongkor_map(tahun, limit=1000, bounds=None, **kw):
    """Petak bongkor + polygon + warna merah (untuk map bongkor)."""
    w, wv = _wilayah_where(kw)
    b, bv = _bbox_sql(bounds if bounds is not None else kw.get("bounds"))
    lim = _page_size(kw, default=limit)
    return q(f"""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.tahun_rtt,
               p.target_rkap, p.kode_divre, p.kode_kph, p.kode_bkph, p.kode_rph, p.kode_tpg,
               p.divre AS divre_nama, p.kph AS kph_nama, p.bkph AS bkph_nama, p.rph AS rph_nama, p.nama_tpg AS tpg_nama,
               'bongkor' AS kategori, 'merah' AS warna,
               pp.polygon
        FROM getah_petak p
        JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL{w}{b}
          AND NOT EXISTS (SELECT 1 FROM getah_andil a WHERE a.kode_evapot = p.kode_evapot)
        ORDER BY p.luas_baku DESC
        LIMIT %s
    """, tuple([tahun] + wv + bv + [lim]))


@template("kph_summary_map")
def kph_summary_map(tahun, limit=1000, aggregated_level="kode_kph", bounds=None, zoom=None, **kw):
    """Ringkasan KPI per KPH/BKPH — centroid + metrik untuk zoom out / seluruh DIVRE.
    
    aggregated_level: 'kode_divre' | 'kode_kph' | 'kode_bkph' (default 'kode_kph')
    bounds: [west, south, east, north] — filter spatial viewport via geom index
    zoom: level zoom map — server bisa otomatis naikkan aggregated_level kalau zoom rendah
    
    Return: centroid (ST_Centroid of first polygon), count, sum_luas, bongkor/kurang/terpenuhi, achievement avg.
    """
    from simoge_db import _require_level, _wilayah_where
    
    level = _require_level(aggregated_level)
    ncol = _WILAYAH_NAMES[level]
    w, wv = _wilayah_where(kw)

    # Spatial bounds filter (lihat _bbox_sql: via ST_GeomFromGeoJSON)
    b, bv = _bbox_sql(bounds if bounds is not None else kw.get("bounds"))
    lim = _page_size(kw, default=limit)
    
    # Auto-escalate aggregation level if zoom low (less detail needed)
    effective_level = level
    if zoom is not None and zoom < 11:
        if level == "kode_bkph":
            effective_level = "kode_kph"
            ncol = _WILAYAH_NAMES[effective_level]
        elif level == "kode_kph":
            effective_level = "kode_divre"
            ncol = _WILAYAH_NAMES[effective_level]
    
    # Join table for names
    name_join = ""
    name_col = "p.{} AS nama_wilayah".format(_WILAYAH_NAMES[effective_level])
    if effective_level == "kode_divre":
        name_join = "LEFT JOIN divre d ON d.kode_divre = p.kode_divre"
        name_col = "d.divre AS nama_wilayah"
    elif effective_level == "kode_kph":
        name_join = "LEFT JOIN kph k ON k.kode_kph = p.kode_kph"
        name_col = "k.kph AS nama_wilayah"
    elif effective_level == "kode_bkph":
        name_join = "LEFT JOIN bkph b ON b.kode_bkph = p.kode_bkph"
        name_col = "b.bkph AS nama_wilayah"
    
    # Use MIN(ST_AsGeoJSON(ST_Centroid(...))) as representative centroid.
    # pp.polygon = GeoJSON longtext (tanpa kolom geom) — parse dulu.
    return q(f"""
        SELECT p.{effective_level} AS kode_wilayah, {name_col},
               COUNT(*) AS total_petak,
               ROUND(SUM(p.luas_baku), 2) AS total_luas_ha,
               MIN(ST_AsGeoJSON(ST_Centroid(ST_GeomFromGeoJSON(pp.polygon)))) AS centroid,
               SUM(CASE WHEN COALESCE(a.penyadap, 0) = 0 THEN 1 ELSE 0 END) AS bongkor,
               SUM(CASE WHEN COALESCE(a.penyadap, 0) > 0 AND COALESCE(a.luas_andil, 0) < p.luas_baku THEN 1 ELSE 0 END) AS kurang,
               SUM(CASE WHEN COALESCE(a.luas_andil, 0) >= p.luas_baku THEN 1 ELSE 0 END) AS terpenuhi,
               ROUND(AVG(COALESCE(a.luas_andil, 0) / NULLIF(p.luas_baku, 0) * 100), 2) AS avg_efektivitas_pct
        FROM getah_petak p
        JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap,
                   SUM(luas_andil) AS luas_andil
            FROM getah_andil GROUP BY kode_evapot
        ) a ON a.kode_evapot = p.kode_evapot
        {name_join}
        WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL{w}{b}
        GROUP BY p.{effective_level}
        ORDER BY bongkor DESC, total_petak DESC
        LIMIT %s
    """, tuple([tahun] + wv + bv + [lim]))


@template("petak_efektivitas_map")
def petak_efektivitas_map(tahun, limit=1000, bounds=None, **kw):
    """Efektivitas petak + polygon + warna bisnis (merah/kuning/hijau) untuk map."""
    w, wv = _wilayah_where(kw)
    b, bv = _bbox_sql(bounds if bounds is not None else kw.get("bounds"))
    lim = _page_size(kw, default=limit)
    _paint_out = q(f"""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.tahun_rtt,
               p.target_rkap, p.kode_divre, p.kode_kph, p.kode_bkph, p.kode_rph, p.kode_tpg,
               p.divre AS divre_nama, p.kph AS kph_nama, p.bkph AS bkph_nama, p.rph AS rph_nama, p.nama_tpg AS tpg_nama,
               a.nama_penyadap AS penyadap_nama,
               COALESCE(a.penyadap, 0) AS jumlah_penyadap,
               COALESCE(a.luas_andil, 0) AS luas_andil,
               CASE
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'bongkor'
                   WHEN COALESCE(a.luas_andil, 0) < p.luas_baku THEN 'kurang'
                   ELSE 'terpenuhi'
               END AS kategori,
               CASE
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'merah'
                   WHEN COALESCE(a.luas_andil, 0) < p.luas_baku THEN 'kuning'
                   ELSE 'hijau'
               END AS warna,
               pp.polygon
        FROM getah_petak p
        JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap,
                   SUM(luas_andil) AS luas_andil,
                   GROUP_CONCAT(DISTINCT nama_penyadap SEPARATOR ', ') AS nama_penyadap
            FROM getah_andil GROUP BY kode_evapot
        ) a ON a.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL{w}{b}
        ORDER BY a.luas_andil / NULLIF(p.luas_baku, 0)
        LIMIT %s
    """, tuple([tahun] + wv + bv + [lim]))
    _paint_rows(_paint_out.get("rows"), _paint_coverage)
    return _paint_out


@template("petak_multi_penyadap_map")
def petak_multi_penyadap_map(tahun, limit=1000, bounds=None, **kw):
    """Petak multi-penyadap (>1 penyadap) + polygon. Warna kuning (2 penyadap) / oranye (3) / hijau (>3)."""
    w, wv = _wilayah_where(kw)
    b, bv = _bbox_sql(bounds if bounds is not None else kw.get("bounds"))
    lim = _page_size(kw, default=limit)
    return q(f"""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.tahun_rtt,
               p.target_rkap, p.kode_divre, p.kode_kph, p.kode_bkph, p.kode_rph, p.kode_tpg,
               p.divre AS divre_nama, p.kph AS kph_nama, p.bkph AS bkph_nama, p.rph AS rph_nama, p.nama_tpg AS tpg_nama,
               a.nama_penyadap AS penyadap_nama,
               COALESCE(a.penyadap, 0) AS jumlah_penyadap,
               COALESCE(a.luas_andil, 0) AS luas_andil,
               CASE
                   WHEN COALESCE(a.penyadap, 0) = 2 THEN 'kuning'
                   WHEN COALESCE(a.penyadap, 0) = 3 THEN 'oranye'
                   ELSE 'hijau'
               END AS warna,
               'multi' AS kategori,
               pp.polygon
        FROM getah_petak p
        JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
        JOIN (
            SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap, SUM(luas_andil) AS luas_andil, GROUP_CONCAT(DISTINCT nama_penyadap SEPARATOR ', ') AS nama_penyadap
            FROM getah_andil GROUP BY kode_evapot HAVING COUNT(DISTINCT id_penyadap) > 1
        ) a ON a.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL{w}{b}
        ORDER BY a.penyadap DESC, a.luas_andil DESC
        LIMIT %s
    """, tuple([tahun] + wv + bv + [lim]))


@template("rkap_map")
def rkap_map(tahun, bulan, periode, limit=1000, bounds=None, **kw):
    """RKAP achievement + polygon + warna (merah/oranye/kuning/hijau/emas) untuk map.
    target_periode = target_rkap × persen skalar _target_pct (kumulatif s/d periode).
    Skalar — bukan JOIN target (12 baris persen × polygon ganda = target ganda)."""
    pct = _target_pct(tahun, bulan, periode)
    d0, _e1 = period_bounds(tahun, 1, 1)
    _, dlast = period_bounds(tahun, bulan, periode)
    w, wv = _wilayah_where(kw)
    b, bv = _bbox_sql(bounds if bounds is not None else kw.get("bounds"))
    lim = _page_size(kw, default=limit)
    _paint_out = q(f"""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.target_rkap,
               p.kode_divre, p.kode_kph, p.kode_bkph, p.kode_rph, p.kode_tpg,
               p.divre AS divre_nama, p.kph AS kph_nama, p.bkph AS bkph_nama, p.rph AS rph_nama, p.nama_tpg AS tpg_nama,
               COALESCE(r.realisasi, 0) AS realisasi,
               ROUND(p.target_rkap * %s / 100, 2) AS target_periode,
               ROUND(100 * COALESCE(r.realisasi, 0) /
                     NULLIF(p.target_rkap * %s / 100, 0), 2) AS pencapaian_pct,
               CASE
                   WHEN p.target_rkap * %s / 100 = 0 THEN NULL
                   WHEN 100 * COALESCE(r.realisasi, 0) /
                        (p.target_rkap * %s / 100) <= 25 THEN 'merah'
                   WHEN 100 * COALESCE(r.realisasi, 0) /
                        (p.target_rkap * %s / 100) <= 50 THEN 'oranye'
                   WHEN 100 * COALESCE(r.realisasi, 0) /
                        (p.target_rkap * %s / 100) <= 75 THEN 'kuning'
                   WHEN 100 * COALESCE(r.realisasi, 0) /
                        (p.target_rkap * %s / 100) <= 100 THEN 'hijau'
                   ELSE 'emas'
               END AS warna,
               pp.polygon
        FROM getah_petak p
        JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT pen.kode_evapot, SUM(COALESCE(pen.berat_penerimaan, 0)) AS realisasi
            FROM getah_aktivitas_penerimaan pen
            WHERE pen.tanggal BETWEEN %s AND %s AND pen.kode_evapot IS NOT NULL
            GROUP BY pen.kode_evapot
        ) r ON r.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL{w}{b}
        GROUP BY p.kode_evapot
        LIMIT %s
    """, tuple([pct] * 7 + [d0, dlast, tahun] + wv + bv + [lim]))
    _paint_rows(_paint_out.get("rows"), _paint_produksi)
    return _paint_out


@template("idle_petak")
def idle_petak(tahun, bulan, periode, **kw):
    """Status aktif/idle/bongkor per petak — agregat = status_petak_per_wilayah global.
    Loose GROUP BY kode_evapot (selaras polygon idle_petak_map, bukan strict
    join andil yg hilangkan aktivitas petak bongkor). prev = prev-periode
    (P2→P1 bulan sama; P1→P2 bulan lalu). Prioritas CASE ikut diperjelas:
    cur>0 aktif → tanpa penyadap/>2bln sepi bongkor → selain itu idle.
    Scoped wilayah via _wilayah_where + nama manusia."""
    d0, e1 = period_bounds(tahun, bulan, periode)
    if periode == 2:
        dprev, eprev = period_bounds(tahun, bulan, 1)
    else:
        pb = bulan - 1 if bulan > 1 else 12
        py = tahun if bulan > 1 else tahun - 1
        dprev, eprev = period_bounds(py, pb, 2)
    import datetime as _dt
    _d0 = _dt.date.fromisoformat(d0)
    _d2 = _d0 - _dt.timedelta(days=61)
    d2s, d2e = _d2.isoformat(), (_d0 - _dt.timedelta(days=1)).isoformat()
    w, wv = _wilayah_where(kw)
    return q(f"""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku,
               p.kode_divre, p.kode_kph, p.kode_bkph, p.kode_rph, p.kode_tpg,
               p.divre AS divre_nama, p.kph AS kph_nama, p.bkph AS bkph_nama,
               p.rph AS rph_nama, p.nama_tpg AS tpg_nama,
               COALESCE(cur.cnt, 0) AS aktivitas_periode_ini,
               COALESCE(prev.cnt, 0) AS aktivitas_periode_lalu,
               CASE
                   WHEN COALESCE(cur.cnt, 0) > 0 THEN 'aktif'
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'bongkor'
                   WHEN COALESCE(two.cnt, 0) = 0 THEN 'bongkor'
                   ELSE 'idle'
               END AS status
        FROM getah_petak p
        LEFT JOIN (
            SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap, COUNT(*) AS jumlah_andil
            FROM getah_andil GROUP BY kode_evapot
        ) a ON a.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(*) AS cnt FROM getah_aktivitas_sadap
            WHERE tgl_pembaharuan BETWEEN %s AND %s GROUP BY kode_evapot
        ) cur ON cur.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(*) AS cnt FROM getah_aktivitas_sadap
            WHERE tgl_pembaharuan BETWEEN %s AND %s GROUP BY kode_evapot
        ) prev ON prev.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(*) AS cnt FROM getah_aktivitas_sadap
            WHERE tgl_pembaharuan BETWEEN %s AND %s GROUP BY kode_evapot
        ) two ON two.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s{w}
    """, (d0, e1, dprev, eprev, d2s, d2e, tahun, *wv))


@template("idle_petak_map")
def idle_petak_map(tahun, bulan, periode, limit=1000, bounds=None, **kw):
    """Idle/bongkor/aktif + polygon — Evaluasi Aktivitas IDLE (sesuai diperjelas.md)
    AKTIF hijau: cur > 0
    IDLE kuning: punya penyadap + aktivitas dalam 2 bulan terakhir, tapi 0 di
                 periode ini (termasuk prev=0 — prev cuma 1 periode, jadi terlalu
                 sempit: 114 petak aktif jadi salah merah sebelum fix ini)
    BONGKOR merah: tanpa penyadap, atau punya penyadap tapi 0 aktivitas >2 bulan
    """
    d0, e1 = period_bounds(tahun, bulan, periode)
    if periode == 2:
        dprev, eprev = period_bounds(tahun, bulan, 1)
    else:
        pb = bulan - 1 if bulan > 1 else 12
        py = tahun if bulan > 1 else tahun - 1
        dprev, eprev = period_bounds(py, pb, 2)
    import datetime as _dt
    _d0 = _dt.date.fromisoformat(d0)
    _d2 = _d0 - _dt.timedelta(days=61)
    d2s, d2e = _d2.isoformat(), (_d0 - _dt.timedelta(days=1)).isoformat()
    w, wv = _wilayah_where(kw)
    b, bv = _bbox_sql(bounds if bounds is not None else kw.get("bounds"))
    lim = _page_size(kw, default=limit)
    return q(f"""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.target_rkap,
               p.kode_divre, p.kode_kph, p.kode_bkph, p.kode_rph, p.kode_tpg, p.tahun_rtt,
               p.divre AS divre_nama, p.kph AS kph_nama, p.bkph AS bkph_nama, p.rph AS rph_nama, p.nama_tpg AS tpg_nama,
               COALESCE(a.penyadap,0) AS jumlah_penyadap,
               COALESCE(a.jumlah_andil,0) AS jumlah_andil,
               COALESCE(cur.cnt, 0) AS aktivitas_periode_ini,
               COALESCE(prev.cnt, 0) AS aktivitas_periode_lalu,
               COALESCE(two.cnt, 0) AS aktivitas_2bulan,
               -- tiga status, urutan sesuai 2nd_kontek_bisnis_diperjelas.md:
               --   AKTIF  : aktivitas pada periode berjalan
               --   IDLE   : ada penyadap + ada aktivitas 2 bulan, tapi TIDAK di
               --            periode ini (termasuk yang Prev=0 — prev cuma satu
               --            periode, 2 bulan lebih representatif untuk "masih hidup")
               --   BONGKOR: tanpa penyadap, atau penyadap tapi >2 bulan tanpa
               --            aktivitas sama sekali
               -- ELSE lama='bongkor' membuat 114 petak aktif jadi merah.
               CASE
                   WHEN COALESCE(cur.cnt, 0) > 0 THEN 'aktif'
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'bongkor'
                   WHEN COALESCE(two.cnt, 0) = 0 THEN 'bongkor'
                   ELSE 'idle'
               END AS status,
               CASE
                   WHEN COALESCE(cur.cnt, 0) > 0 THEN 'hijau'
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'merah'
                   WHEN COALESCE(two.cnt, 0) = 0 THEN 'merah'
                   ELSE 'kuning'
               END AS warna,
               CASE
                   WHEN COALESCE(cur.cnt, 0) > 0 THEN 'aktif'
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'bongkor'
                   WHEN COALESCE(two.cnt, 0) = 0 THEN 'bongkor'
                   ELSE 'idle'
               END AS kategori,
               pp.polygon
        FROM getah_petak p
        JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap, COUNT(*) AS jumlah_andil
            FROM getah_andil GROUP BY kode_evapot
        ) a ON a.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(*) AS cnt FROM getah_aktivitas_sadap
            WHERE tgl_pembaharuan BETWEEN %s AND %s GROUP BY kode_evapot
        ) cur ON cur.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(*) cnt FROM getah_aktivitas_sadap
            WHERE tgl_pembaharuan BETWEEN %s AND %s GROUP BY kode_evapot
        ) prev ON prev.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(*) cnt FROM getah_aktivitas_sadap
            WHERE tgl_pembaharuan BETWEEN %s AND %s GROUP BY kode_evapot
        ) two ON two.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL{w}{b}
        ORDER BY
            CASE WHEN COALESCE(cur.cnt,0)>0 THEN 2
                 WHEN COALESCE(a.penyadap,0)=0 THEN 0
                 WHEN COALESCE(two.cnt,0)=0 THEN 0 ELSE 1 END,
            p.luas_baku DESC
        LIMIT %s
    """, tuple([d0, e1, dprev, eprev, d2s, d2e, tahun] + wv + bv + [lim]))


# ── agregasi aktivitas multi-dimensi ────────────────────────────
# Satu template untuk 3 sudut pandang: per Penyadap, perJenis Aktivitas,
# per Pembaharuan. Chunking 40 baris per stmt (MariaDB max_prepared_stmt_count=16382).
# gp='penyadap' → id_penyadap · 'aktivitas' → kolom flag · 'pembaharuan' → pembaharuan_ke
AKTIVITAS_FLAGS = ("quare", "semprot_cas", "kerok", "budaya_bersih",
                   "naik_batok")
AKTIVITAS_LABEL = {"quare": "Quare", "semprot_cas": "Semprot CAS",
                   "kerok": "Kerok", "budaya_bersih": "Budaya Bersih",
                   "naik_batok": "Naik Batok"}


@template("aktivitas_agregat")
def aktivitas_agregat(tahun, bulan, periode, grup_by="penyadap",
                      limit=100, **kw):
    """Agregat aktivitas 3 dimensi dari getah_aktivitas_sadap.
    grup_by: 'penyadap' (id_penyadap, nama) · 'aktivitas' (jenis flag kolom) ·
             'pembaharuan' (pembaharuan_ke + label).
    periode=0 → bulan penuh. kw.pembaharuan_ke menyaring sumber.
    Kembalikan {dim, label, count, photo_count, ...} terurut count desc.
    """
    d0, e1 = period_bounds(tahun, bulan, periode)
    w, wv = _wilayah_where(kw)
    pw, pv = _pembaharuan_where(kw, "s")
    base = f"""FROM getah_aktivitas_sadap s
        LEFT JOIN getah_penyadap py ON py.id = s.id_penyadap
        JOIN getah_petak p ON p.kode_evapot = s.kode_evapot AND p.tahun_rtt = %s
        WHERE s.tgl_pembaharuan BETWEEN %s AND %s{pw}{w}"""
    bv = [tahun, d0, e1] + pv + wv

    if grup_by == "penyadap":
        r = q(f"""SELECT s.id_penyadap AS dim, py.nama_penyadap AS label,
                COUNT(*) AS count,
                SUM(s.aktivitas_photo IS NOT NULL AND s.aktivitas_photo<>'') AS photo_count,
                COUNT(DISTINCT s.kode_evapot) AS petak_count,
                MAX(s.tgl_pembaharuan) AS tgl_terakhir
            {base}
            GROUP BY s.id_penyadap, py.nama_penyadap
            ORDER BY count DESC LIMIT %s""", tuple(bv + [limit]))
    elif grup_by == "pembaharuan":
        r = q(f"""SELECT s.pembaharuan_ke AS dim,
                CONCAT('Pembaharuan ', s.pembaharuan_ke) AS label,
                COUNT(*) AS count,
                SUM(s.aktivitas_photo IS NOT NULL AND s.aktivitas_photo<>'') AS photo_count,
                COUNT(DISTINCT s.kode_evapot) AS petak_count,
                MAX(s.tgl_pembaharuan) AS tgl_terakhir
            {base}
            GROUP BY s.pembaharuan_ke ORDER BY s.pembaharuan_ke LIMIT %s""",
              tuple(bv + [limit]))
    elif grup_by == "aktivitas":
        # 1 stmt per kolom flag, digabung di Python. MariaDB tidak punya
        # unpivot; 5 stmt kecil lebih murah daripada GROUPING SETS.
        rows = []
        for c in AKTIVITAS_FLAGS:
            r = q(f"""SELECT %s AS dim, %s AS label, COUNT(*) AS count,
                    SUM(s.aktivitas_photo IS NOT NULL AND s.aktivitas_photo<>'') AS photo_count,
                    COUNT(DISTINCT s.kode_evapot) AS petak_count,
                    MAX(s.tgl_pembaharuan) AS tgl_terakhir
                {base} AND s.{c} = 1
                GROUP BY s.{c} LIMIT %s""",
                  tuple([c, AKTIVITAS_LABEL[c]] + bv + [limit]))
            rows.extend(r["rows"])
        r = {"rows": rows, "row_count": len(rows)}
    else:
        raise ValueError(
            f"grup_by harus 'penyadap'|'aktivitas'|'pembaharuan', bukan {grup_by!r}")

    for x in r["rows"]:
        x["count"] = int(x.get("count") or 0)
        x["photo_count"] = int(x.get("photo_count") or 0)
        x["petak_count"] = int(x.get("petak_count") or 0)
    r["rows"].sort(key=lambda z: -z["count"])
    return r


@template("aktivitas_top_petak")
def aktivitas_top_petak(tahun, bulan, periode, limit=10, **kw):
    """Petak dengan aktivitas terbanyak pada periode (bisa periode=0 = bulan penuh).
   _one row per petak_, lengkap dengan nomor_petak, komposisi Pem1/2/3/4,
    jumlah penyadap, dan polygon (bisa langsung di-push ke map).
    """
    d0, e1 = period_bounds(tahun, bulan, periode)
    w, wv = _wilayah_where(kw)
    pw, pv = _pembaharuan_where(kw, "s")
    r = q(f"""
        SELECT p.nomor_petak, s.kode_evapot, COUNT(*) AS jumlah_aktivitas,
               SUM(s.pembaharuan_ke='1') AS pem1, SUM(s.pembaharuan_ke='2') AS pem2,
               SUM(s.pembaharuan_ke='3') AS pem3, SUM(s.pembaharuan_ke='4') AS pem4,
               COUNT(DISTINCT s.id_penyadap) AS jumlah_penyadap,
               COUNT(DISTINCT p.nama_tpg) AS jumlah_tpg,
               SUM(s.aktivitas_photo IS NOT NULL AND s.aktivitas_photo<>'') AS jumlah_foto,
               MAX(s.tgl_pembaharuan) AS tgl_terakhir,
               pp.polygon
        FROM getah_aktivitas_sadap s
        JOIN getah_petak p ON p.kode_evapot = s.kode_evapot AND p.tahun_rtt = %s
        JOIN petak_polygon pp ON pp.kode_evapot = s.kode_evapot
        WHERE s.tgl_pembaharuan BETWEEN %s AND %s{pw}{w}
        GROUP BY s.kode_evapot, p.nomor_petak, pp.polygon
        ORDER BY jumlah_aktivitas DESC, jumlah_penyadap DESC
        LIMIT %s
    """, tuple([tahun, d0, e1] + pv + wv + [limit]))
    return r


@template("aktivitas_per_penyadap_petak")
def aktivitas_per_penyadap_petak(tahun, bulan, periode, id_penyadap=None,
                                 limit=200, **kw):
    """Semua aktivitas 1 penyadap pada 1 periode — untuk drill-down
    'penyadap XONU nth di petak mana bulan ini'. Menyertakan polygon petak."""
    d0, e1 = period_bounds(tahun, bulan, periode)
    w, wv = _wilayah_where(kw)
    pw, pv = _pembaharuan_where(kw, "s")
    r = q(f"""
        SELECT py.nama_penyadap, py.nomor_penyadap AS nik, s.id_penyadap,
               p.nomor_petak, s.kode_evapot, s.pembaharuan_ke, s.tgl_pembaharuan,
               s.latitude, s.longitude, s.quare, s.semprot_cas, s.kerok,
               s.budaya_bersih, s.naik_batok,
               s.aktivitas_photo, f.filename_disk AS foto_file,
               pp.polygon
        FROM getah_aktivitas_sadap s
        JOIN getah_petak p ON p.kode_evapot = s.kode_evapot AND p.tahun_rtt = %s
        JOIN petak_polygon pp ON pp.kode_evapot = s.kode_evapot
        LEFT JOIN getah_penyadap py ON py.id = s.id_penyadap
        LEFT JOIN directus_files f ON f.id = s.aktivitas_photo
        WHERE s.tgl_pembaharuan BETWEEN %s AND %s{pw}{w}
          {" AND s.id_penyadap = %s" if id_penyadap is not None else ""}
        ORDER BY s.tgl_pembaharuan DESC, s.id DESC
        LIMIT %s
    """, tuple([tahun, d0, e1] + pv + wv
               + ([int(id_penyadap)] if id_penyadap is not None else []) + [limit]))
    return r


@template("aktivitas_petak_map")
def aktivitas_petak_map(tahun, bulan, periode, limit=1000, bounds=None, **kw):
    """Evaluasi Aktivitas per petak — sesuai 2nd_kontek_bisnis_diperjelas.md
    AKTIV: ada aktivitas periode berjalan → hijau
    IDLE: sebelumnya ada, berjalan tidak ada → kuning
    BONGKOR: petak tanpa penyadap ATAU andil >2 bulan tanpa aktivitas → merah
    Petak BONGKOR ≠ Andil BONGKOR — dibedakan via jumlah_penyadap & aktivitas_2bulan.
    Warna polygon: merah bongkor / kuning idle / hijau aktif.
    Kolom tambahan: jumlah_penyadap, jumlah_andil, andil_aktif/idle/bongkor, aktivitas_prev, aktivitas_2bulan.

    periode=0 → satu bulan penuh (P1+P2). kw.pembaharuan_ke='1'..'4'|'semua'
    memfilter SEMUA hitungan aktivitas (cur/prev/two) supaya polygon, KPI, dan
    pin aktivitas_recent melihat himpunan baris yang sama.
    """
    d0, e1 = period_bounds(tahun, bulan, periode)
    dprev, eprev = _prev_period_bounds(tahun, bulan, periode)
    # 2 bulan window sebelum periode berjalan (andil bongkor)
    import datetime as _dt
    _d0 = _dt.date.fromisoformat(d0)
    # approx 61 days back
    _d2 = _d0 - _dt.timedelta(days=61)
    d2s, d2e = _d2.isoformat(), (_d0 - _dt.timedelta(days=1)).isoformat()
    w, wv = _wilayah_where(kw)
    pw, pv = _pembaharuan_where(kw, "s")
    b, bv = _bbox_sql(bounds if bounds is not None else kw.get("bounds"))
    lim = _page_size(kw, default=limit)
    _paint_out = q(f"""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.target_rkap,
               p.kode_divre, p.kode_kph, p.kode_bkph, p.kode_rph, p.kode_tpg, p.tahun_rtt,
               p.divre AS divre_nama, p.kph AS kph_nama, p.bkph AS bkph_nama, p.rph AS rph_nama, p.nama_tpg AS tpg_nama,
               COALESCE(a.penyadap, 0) AS jumlah_penyadap,
               COALESCE(a.jumlah_andil, 0) AS jumlah_andil,
               COALESCE(act.cnt, 0) AS jumlah_aktivitas,
               COALESCE(prev.cnt, 0) AS aktivitas_prev,
               COALESCE(two.cnt, 0) AS aktivitas_2bulan,
               -- andil breakdown: andil_aktif = andil yg punya aktivitas di periode berjalan
               COALESCE(aa.cnt, 0) AS andil_aktif,
               GREATEST(COALESCE(a.jumlah_andil,0) - COALESCE(aa.cnt,0) - COALESCE(ab.cnt,0), 0) AS andil_idle,
               COALESCE(ab.cnt, 0) AS andil_bongkor,
               CASE
                   WHEN COALESCE(act.cnt, 0) > 0 THEN 'aktif'
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'bongkor'
                   WHEN COALESCE(two.cnt, 0) = 0 THEN 'bongkor'
                   ELSE 'idle'
               END AS kategori,
               CASE
                   WHEN COALESCE(act.cnt, 0) > 0 THEN 'hijau'
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'merah'
                   WHEN COALESCE(two.cnt, 0) = 0 THEN 'merah'
                   ELSE 'kuning'
               END AS warna,
               pp.polygon
        FROM getah_petak p
        JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap, COUNT(*) AS jumlah_andil
            FROM getah_andil GROUP BY kode_evapot
        ) a ON a.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(*) AS cnt FROM getah_aktivitas_sadap s
            WHERE s.tgl_pembaharuan BETWEEN %s AND %s{pw} GROUP BY kode_evapot
        ) act ON act.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(*) AS cnt FROM getah_aktivitas_sadap s
            WHERE s.tgl_pembaharuan BETWEEN %s AND %s{pw} GROUP BY kode_evapot
        ) prev ON prev.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(*) AS cnt FROM getah_aktivitas_sadap s
            WHERE s.tgl_pembaharuan BETWEEN %s AND %s{pw} GROUP BY kode_evapot
        ) two ON two.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT a.kode_evapot, COUNT(*) AS cnt FROM getah_andil a
            WHERE EXISTS (SELECT 1 FROM getah_aktivitas_sadap s WHERE s.kode_evapot=a.kode_evapot AND s.id_penyadap=a.id_penyadap AND s.tgl_pembaharuan BETWEEN %s AND %s{pw})
            GROUP BY a.kode_evapot
        ) aa ON aa.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT a.kode_evapot, COUNT(*) AS cnt FROM getah_andil a
            WHERE NOT EXISTS (SELECT 1 FROM getah_aktivitas_sadap s WHERE s.kode_evapot=a.kode_evapot AND s.id_penyadap=a.id_penyadap AND s.tgl_pembaharuan BETWEEN %s AND %s{pw})
            GROUP BY a.kode_evapot
        ) ab ON ab.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL{w}{b}
        ORDER BY
            CASE WHEN COALESCE(a.penyadap,0)=0 THEN 0 WHEN COALESCE(act.cnt,0)=0 AND COALESCE(prev.cnt,0)>0 THEN 1 WHEN COALESCE(act.cnt,0)=0 THEN 0 ELSE 2 END,
            act.cnt DESC
        LIMIT %s
    """, tuple([d0, e1] + pv + [dprev, eprev] + pv + [d2s, d2e] + pv
               + [d0, e1] + pv + [d2s, d2e] + pv
               + [tahun] + wv + bv + [lim]))
    _paint_rows(_paint_out.get("rows"), _paint_aktivitas)
    return _paint_out


@template("matriks_map")
def matriks_map(tahun, bulan, periode, limit=1000, bounds=None, **kw):
    """Matriks: hubungan luas_andil vs pencapaian RKAP per petak + polygon.
    Warna: merah=bongkor, oranye=kurang & cap<50, kuning=kurang, hijau=terpenuhi 0-100, emas=terpenuhi >100.
    Kolom: kategori_efektivitas, pencapaian_pct, luas_andil, realisasi, warna.
    target_periode skalar via _target_pct (alasan sama seperti rkap_map).
    """
    pct = _target_pct(tahun, bulan, periode)
    d0, _e1 = period_bounds(tahun, 1, 1)
    _, dlast = period_bounds(tahun, bulan, periode)
    w, wv = _wilayah_where(kw)
    b, bv = _bbox_sql(bounds if bounds is not None else kw.get("bounds"))
    lim = _page_size(kw, default=limit)
    return q(f"""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.target_rkap,
               p.kode_divre, p.kode_kph, p.kode_bkph, p.kode_rph, p.kode_tpg, p.tahun_rtt,
               p.divre AS divre_nama, p.kph AS kph_nama, p.bkph AS bkph_nama, p.rph AS rph_nama, p.nama_tpg AS tpg_nama,
               COALESCE(a.nama_penyadap, '') AS penyadap_nama,
               COALESCE(a.luas_andil, 0) AS luas_andil,
               COALESCE(a.jml_pohon, 0) AS jml_pohon_andil,
               p.jumlah_pohon AS jumlah_pohon_petak,
               ROUND(COALESCE(a.jml_pohon,0)/NULLIF(p.jumlah_pohon,0)*100,1) AS pohon_pct,
               COALESCE(a.penyadap, 0) AS jumlah_penyadap,
               COALESCE(r.realisasi, 0) AS realisasi,
               ROUND(p.target_rkap * %s / 100, 2) AS target_periode,
               ROUND(100 * COALESCE(r.realisasi, 0) /
                     NULLIF(p.target_rkap * %s / 100, 0), 2) AS pencapaian_pct,
               CASE
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'bongkor'
                   WHEN COALESCE(a.luas_andil, 0) < p.luas_baku THEN 'kurang'
                   ELSE 'terpenuhi'
               END AS kategori_efektivitas,
               CASE
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'merah'
                   WHEN COALESCE(a.luas_andil, 0) < p.luas_baku AND 100 * COALESCE(r.realisasi, 0) / NULLIF(p.target_rkap * %s / 100, 0) < 50 THEN 'oranye'
                   WHEN COALESCE(a.luas_andil, 0) < p.luas_baku THEN 'kuning'
                   WHEN 100 * COALESCE(r.realisasi, 0) / NULLIF(p.target_rkap * %s / 100, 0) > 100 THEN 'emas'
                   WHEN 100 * COALESCE(r.realisasi, 0) / NULLIF(p.target_rkap * %s / 100, 0) >= 0 THEN 'hijau'
                   ELSE 'kuning'
               END AS warna,
               CASE
                   WHEN COALESCE(a.penyadap, 0) = 0 THEN 'bongkor'
                   WHEN COALESCE(a.luas_andil, 0) < p.luas_baku AND 100 * COALESCE(r.realisasi, 0) / NULLIF(p.target_rkap * %s / 100, 0) < 50 THEN 'oranye'
                   WHEN COALESCE(a.luas_andil, 0) < p.luas_baku THEN 'kurang'
                   ELSE 'terpenuhi'
               END AS kategori,
               pp.polygon
        FROM getah_petak p
        JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap, SUM(luas_andil) AS luas_andil, SUM(jml_pohon) AS jml_pohon, GROUP_CONCAT(DISTINCT nama_penyadap SEPARATOR ', ') AS nama_penyadap
            FROM getah_andil GROUP BY kode_evapot
        ) a ON a.kode_evapot = p.kode_evapot
        LEFT JOIN (
            SELECT pen.kode_evapot, SUM(COALESCE(pen.berat_penerimaan, 0)) AS realisasi
            FROM getah_aktivitas_penerimaan pen
            WHERE pen.tanggal BETWEEN %s AND %s AND pen.kode_evapot IS NOT NULL
            GROUP BY pen.kode_evapot
        ) r ON r.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL{w}{b}
        GROUP BY p.kode_evapot
        ORDER BY COALESCE(a.luas_andil, 0) / NULLIF(p.luas_baku, 0)
        LIMIT %s
    """, tuple([pct] * 6 + [d0, dlast, tahun] + wv + bv + [lim]))


@template("rkap_achievement")
def rkap_achievement(tahun, bulan, periode, upto_bulan=None, upto_periode=None, **kw):
    """
    Pencapaian target RKAP per petak.
    Realisasi = SUM(berat_penerimaan) pada periode.
    Target    = target_rkap * persen(ro_periode / nps_periode) per bulan s/d upto.
    upto_*    default = (bulan, periode) → akumulasi 1 s/d periode yang diminta.
    """
    upto_bulan = upto_bulan or bulan
    upto_periode = upto_periode or periode
    cols = []
    for m in range(1, upto_bulan + 1):
        p1 = f"COALESCE(SUM(CASE WHEN t.bulan = {m} THEN t.ro_periode_1 ELSE 0 END), 0)"
        p2 = f"COALESCE(SUM(CASE WHEN t.bulan = {m} THEN t.ro_periode_2 ELSE 0 END), 0)"
        cols.append(f"{p1} + {p2}")
    target_expr = " + ".join(cols) if cols else "0"
    d0, _e1 = period_bounds(tahun, 1, 1)
    _, dlast = period_bounds(tahun, upto_bulan, upto_periode)
    return q(f"""
        SELECT p.nomor_petak, p.kode_evapot, p.luas_baku, p.target_rkap,
               COALESCE(r.realisasi, 0) AS realisasi,
               ROUND(p.target_rkap * ({target_expr}) / 100, 2) AS target_periode,
               ROUND(100 * COALESCE(r.realisasi, 0) /
                     NULLIF(p.target_rkap * ({target_expr}) / 100, 0), 2) AS pencapaian_pct,
               CASE
                   WHEN p.target_rkap * ({target_expr}) = 0 THEN NULL
                   WHEN 100 * COALESCE(r.realisasi, 0) /
                        (p.target_rkap * ({target_expr}) / 100) <= 25 THEN 'merah'
                   WHEN 100 * COALESCE(r.realisasi, 0) /
                        (p.target_rkap * ({target_expr}) / 100) <= 50 THEN 'oranye'
                   WHEN 100 * COALESCE(r.realisasi, 0) /
                        (p.target_rkap * ({target_expr}) / 100) <= 75 THEN 'kuning'
                   WHEN 100 * COALESCE(r.realisasi, 0) /
                        (p.target_rkap * ({target_expr}) / 100) <= 100 THEN 'hijau'
                   ELSE 'emas'
               END AS warna
        FROM getah_petak p
        LEFT JOIN (
            SELECT a.kode_evapot, SUM(COALESCE(pen.berat_penerimaan, 0)) AS realisasi
            FROM getah_andil a
            JOIN getah_aktivitas_penerimaan pen ON pen.id_penyadap = a.id_penyadap
            WHERE pen.tanggal BETWEEN %s AND %s
            GROUP BY a.kode_evapot
        ) r ON r.kode_evapot = p.kode_evapot
        JOIN getah_target_ro_nps t ON t.tahun = p.tahun_rtt
        WHERE p.tahun_rtt = %s
    """, (d0, dlast, tahun))


@template("penyadap_productivity")
def penyadap_productivity(tahun, bulan, periode, **kw):
    """Penyadap aktif per periode — scoped wilayah bila filter diberi (via pen.kode_*)."""
    d0, e1 = period_bounds(tahun, bulan, periode)
    w, wv = _wilayah_where(kw, alias="pen")
    return q(f"""
        SELECT pen.id_penyadap, tpg.nama_tpg, tpg.alias,
               COUNT(DISTINCT a.kode_evapot) AS jumlah_petak,
               COUNT(pen.nomor_drum) AS jumlah_drum,
               ROUND(SUM(COALESCE(pen.berat_penerimaan, 0)), 2) AS total_penerimaan,
               MAX(pen.tanggal) AS aktivitas_terakhir
        FROM getah_aktivitas_penerimaan pen
        JOIN getah_daftar_tpg tpg ON tpg.kode_tpg = pen.kode_tpg
        LEFT JOIN getah_andil a ON a.id_penyadap = pen.id_penyadap
        WHERE pen.tanggal BETWEEN %s AND %s{w}
        GROUP BY pen.id_penyadap, tpg.nama_tpg, tpg.alias
        ORDER BY total_penerimaan
    """, (d0, e1, *wv))


@template("drum_flow")
def drum_flow(tahun, bulan, **kw):
    """Status drum: sah / dalam pengangkutan / sudah perni."""
    d0 = f"{tahun:04d}-{bulan:02d}-01"
    d1 = f"{tahun:04d}-{bulan:02d}-31"
    return q("""
        SELECT d.status_drum, COUNT(*) AS jumlah_drum,
               COUNT(DISTINCT d.nomor_pengangkutan) AS jumlah_pengangkutan,
               COUNT(DISTINCT d.nomor_perni) AS jumlah_perni
        FROM getah_drum d
        WHERE d.tanggal BETWEEN %s AND %s
        GROUP BY d.status_drum
    """, (d0, d1))


@template("petak_detail")
def petak_detail(kode_evapot: str, **kw):
    """Full detail of a single petak (clicked in map)."""
    return q("""
        SELECT
            p.nomor_petak, p.kode_evapot, p.luas_baku, p.rencana_luas,
            p.target_rkap, p.jenis_sadap,
            p.kode_kph, p.kode_bkph, p.kode_rph, p.kode_tpg, p.tahun_rtt,
            p.kph AS kph_nama, p.bkph AS bkph_nama, p.rph AS rph_nama,
            p.nama_tpg AS tpg_nama,
            p.jumlah_pohon, p.tahun_tanam
        FROM getah_petak p
        WHERE p.kode_evapot = %s
    """, (kode_evapot,))


@template("petak_mandor_kts")
def petak_mandor_kts(kode_tpg: int, **kw):
    """Mandor + KTS pengampu satu TPG (pemimpin para penyadap).

    Rantai: getah_daftar_tpg.kode_tpg -> t.id -> junction ->
    directus_users -> jabatan (M1-M5 = Mandor, K1-K5 = KTS).
    Return {nama, kode_jabatan, nama_jabatan, peran} order Mandor dulu.
    """
    return q("""
        SELECT
            CASE WHEN u.last_name IS NULL OR TRIM(u.last_name) = ''
                      OR LOCATE(TRIM(u.last_name), TRIM(u.first_name)) > 0
                 THEN TRIM(u.first_name)
                 ELSE TRIM(CONCAT(COALESCE(u.first_name,''), ' ', COALESCE(u.last_name,''))) END AS nama,
            jb.kode_jabatan, jb.nama_jabatan,
            CASE WHEN jb.kode_jabatan LIKE 'M%%' THEN 'Mandor'
                 WHEN jb.kode_jabatan LIKE 'K%%' THEN 'KTS'
                 ELSE COALESCE(jb.nama_jabatan, '-') END AS peran
        FROM getah_daftar_tpg t
        JOIN junction_directus_users_getah_daftar_tpg j ON j.getah_daftar_tpg_id = t.id
        JOIN directus_users u ON u.id = j.directus_users_id
        LEFT JOIN jabatan jb ON jb.id = u.jabatan
        WHERE t.kode_tpg = %s
        ORDER BY CASE WHEN jb.kode_jabatan LIKE 'M%%' THEN 0
                      WHEN jb.kode_jabatan LIKE 'K%%' THEN 1 ELSE 2 END, nama
    """, (kode_tpg,))


@template("petak_penyadap")
def petak_penyadap(kode_evapot: str, **kw):
    """All penyadap (andil) for a specific petak."""
    return q("""
        SELECT
            a.id_penyadap, a.nama_penyadap, a.luas_andil,
            p.nomor_penyadap, a.jml_pohon, p.telpon, p.alamat
        FROM getah_andil a
        JOIN getah_penyadap p ON p.id = a.id_penyadap
        WHERE a.kode_evapot = %s
        ORDER BY a.luas_andil DESC
    """, (kode_evapot,))


@template("aktivitas_penyadap_petak")
def aktivitas_penyadap_petak(kode_evapot: str, tahun: int, bulan: int, periode: int, **kw):
    """Siapa mengerjakan apa di satu petak pada satu periode (modal aktivitas).

    Per penyadap: hitungan aktivitas berjalan + jenis (quare/semprot/kerok/
    budaya/naik_batok) + tahap pembaharuan dominan + tgl terakhir.
    Petak tanpa andil (contoh 11B-1: aktivitas ada, andil nol) tetap tampil —
    pelaku dibaca dari baris aktivitas, bukan dari getah_andil.
    """
    d0, e1 = period_bounds(tahun, bulan, periode)
    return q("""
        SELECT
            s.id_penyadap, COALESCE(py.nama_penyadap, '-') AS nama_penyadap,
            COUNT(*) AS n_aktivitas,
            SUM(COALESCE(s.quare,0)) AS quare,
            SUM(COALESCE(s.semprot_cas,0)) AS semprot_cas,
            SUM(COALESCE(s.kerok,0)) AS kerok,
            SUM(COALESCE(s.budaya_bersih,0)) AS budaya_bersih,
            SUM(COALESCE(s.naik_batok,0)) AS naik_batok,
            (SELECT s2.pembaharuan_ke FROM getah_aktivitas_sadap s2
              WHERE s2.kode_evapot = s.kode_evapot AND s2.id_penyadap = s.id_penyadap
                AND s2.tgl_pembaharuan BETWEEN %s AND %s
              GROUP BY s2.pembaharuan_ke ORDER BY COUNT(*) DESC LIMIT 1) AS pembaharuan_dominan,
            MAX(s.tgl_pembaharuan) AS tgl_terakhir
        FROM getah_aktivitas_sadap s
        LEFT JOIN getah_penyadap py ON py.id = s.id_penyadap
        WHERE s.kode_evapot = %s AND s.tgl_pembaharuan BETWEEN %s AND %s
        GROUP BY s.id_penyadap, py.nama_penyadap
        ORDER BY n_aktivitas DESC
    """, (d0, e1, kode_evapot, d0, e1))


@template("produksi_penyadap_petak")
def produksi_penyadap_petak(kode_evapot: str, tahun: int, bulan: int, periode: int, **kw):
    """Setoran per penyadap di satu petak pada satu periode (modal produksi).

    Dari getah_aktivitas_penerimaan (berat_penerimaan), bukan dari andil —
    penyadap tanpa setoran pada periode ini tak muncul (wajar: 0 kg).
    """
    d0, e1 = period_bounds(tahun, bulan, periode)
    return q("""
        SELECT
            p.id_penyadap, COALESCE(py.nama_penyadap, '-') AS nama_penyadap,
            COUNT(*) AS n_terima,
            ROUND(SUM(COALESCE(p.berat_penerimaan, 0)), 2) AS kg,
            MAX(p.tanggal) AS tgl_terakhir
        FROM getah_aktivitas_penerimaan p
        LEFT JOIN getah_penyadap py ON py.id = p.id_penyadap
        WHERE p.kode_evapot = %s AND p.tanggal BETWEEN %s AND %s
        GROUP BY p.id_penyadap, py.nama_penyadap
        ORDER BY kg DESC
    """, (kode_evapot, d0, e1))


@template("penyadap_aktivitas")
def penyadap_aktivitas(kode_evapot: str, **kw):
    """Aktivitas penyadapan for a specific petak — lengkap lat/lng/alt/pembaharuan_ke/foto."""
    return q("""
        SELECT
            s.id, s.tgl_pembaharuan, s.pembaharuan_ke, s.quare,
            s.latitude, s.longitude, s.altitude,
            s.aktivitas_photo, f.filename_disk AS foto_file, f.storage AS foto_storage,
            s.cuaca, s.akses_lokasi,
            p.nama_penyadap, a.luas_andil
        FROM getah_aktivitas_sadap s
        LEFT JOIN getah_penyadap p ON p.id = s.id_penyadap
        LEFT JOIN directus_files f ON f.id = s.aktivitas_photo
        JOIN getah_andil a ON a.id_penyadap = s.id_penyadap
            AND a.kode_evapot = s.kode_evapot
        WHERE s.kode_evapot = %s
        ORDER BY s.tgl_pembaharuan DESC
        LIMIT 20
    """, (kode_evapot,))


@template("data_freshness")
def data_freshness(**kw):
    """Kapan data terakhir masuk? 1 query, tanpa agregasi berat.

    PENTING untuk presentasi: data SIMOGE bukan realtime. Input operator paling
    banyak 12.00-15.00 dan sore-malam; pagi biasanya minim. Jadi laporan pagi
    tidak boleh dibaca sebagai "kondisi hari ini sudah final".

    => 1 row: {tgl_terakhir, jam, zona, fase_hari, status, sisa_jam_ke_spoil}
    """
    r = q("""SELECT MAX(s.tgl_pembaharuan) AS tgl_terakhir,
                   COUNT(*) AS total_baris,
                   SUM(s.tgl_pembaharuan >= CURDATE()) AS hari_ini,
                   SUM(s.tgl_pembaharuan >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)) AS tujuh_hari
            FROM getah_aktivitas_sadap s""")
    # WAJIB return {rows, row_count, columns} — call_simoge_tool/ana_chart_tool
    # hanya baca "rows". Template yang return dict telanjang akan hilang.
    return r


@template("data_identity")
def data_identity(**kw):
    """Siapa yang mengisi data, kapan, dan dari mana? 1 query, ringan.

    answer untuk "ini data siapa?" - yang mengisi, kapan record terakhir,
    dan sebaran per penyadap. ANNA wajib menyebut ini saat jawab "kondisi
    sekarang" supaya operator tahu ini bukan angka final.
    """
    r = q("""SELECT
              (SELECT COUNT(DISTINCT id_penyadap) FROM getah_aktivitas_sadap) AS n_penyadap,
              (SELECT COUNT(DISTINCT kode_evapot) FROM getah_aktivitas_sadap) AS n_petak,
              (SELECT MAX(tgl_pembaharuan) FROM getah_aktivitas_sadap) AS tgl_terakhir,
              (SELECT MIN(tgl_pembaharuan) FROM getah_aktivitas_sadap) AS tgl_awal,
              (SELECT COUNT(*) FROM getah_aktivitas_sadap
                 WHERE tgl_pembaharuan >= CURDATE()) AS hari_ini,
              (SELECT COUNT(DISTINCT id_penyadap) FROM getah_aktivitas_sadap
                 WHERE tgl_pembaharuan >= CURDATE()) AS penyadap_hari_ini""")
    return r


@template("aktivitas_recent")
def aktivitas_recent(limit=20, **kw):
    """Aktivitas sadap terbaru — tiap record bawa lat/lng/alt/pembaharuan_ke/foto.

    Popup pin butuh konteks lengkap, jadi satu query ini sudah bawa:
      - 5 kolom cekbox jenis aktivitas: quare, semprot_cas, kerok, budaya_bersih,
        naik_batok (tinyint 0/1, semua baris punya >=1 — dicek 0 kosong)
      - nomor_petak (getah_petak), nama_penyadap (getah_penyadap)
      - user_created → directus_users.first_name/last_name
      - nama jabatan: directus_users.jabatan → jabatan.nama_jabatan

    Bila tahun/bulan/periode diberi via kw (dipakai pin-point SPATIAL MAP), filter
    tgl_pembaharuan BETWEEN period_bounds. Tanpa itu → recent global tanpa filter
    tanggal. Wilayah (kode_bkph/rph/tpg) tetap via _wilayah_where → JOIN getah_petak.
    kw.pembaharuan_ke='1'..'4'|'semua' menyaring pin ke satu tahap pembaharuan.
    ponytail: run() pakai signature, bukan co_varnames — locals _tahun/_bulan/_periode
    tidak picu auto-inject.
    """
    _tahun = kw.pop("tahun", None)
    _bulan = kw.pop("bulan", None)
    _periode = kw.pop("periode", None)
    # Filter kategori petak (selaras definisi idle_petak_map: aktif cur>0;
    # idle cur=0+ada penyadap+ada aktivitas 61 hari; bongkor sisanya).
    # - aktif  : baris periode berjalan (≡ semua baris, tanpa predikat).
    # - idle   : baris PERIODE LALU pada petak yang kini idle (bukti + label).
    # - bongkor: SELALU KOSONG secara definisi — petak bongkor (cur=0) tak
    #   punya baris periode berjalan; baris apa pun di periode ini membuat
    #   petaknya aktif menurut prioritas CASE (cur>0 menang). AND 1=0 di
    #   bawah menjaga bentuk respons (total 0, jujur) tanpa query mahal.
    # Selain itu = tanpa filter (perilaku lama).
    kat = str(kw.pop("kategori", "") or "").strip().lower()
    if kat not in ("aktif", "idle", "bongkor"):
        kat = ""
    w, wv = _wilayah_where(kw)
    has_w = bool(w)
    pw, pv = _pembaharuan_where(kw, "s")
    date_where = ""
    date_vals = []
    d0 = d1 = None
    try:
        y = int(_tahun) if _tahun is not None and str(_tahun).strip() != "" else None
        m = int(_bulan) if _bulan is not None and str(_bulan).strip() != "" else None
        pr = int(_periode) if _periode is not None and str(_periode).strip() != "" else None
        if y and m and (pr in (1, 2) or pr in _FULL_P):
            d0, d1 = period_bounds(y, m, pr)
            date_where = " AND s.tgl_pembaharuan BETWEEN %s AND %s"
            date_vals = [d0, d1]
    except Exception:
        pass
    # Predikat kategori (butuh rentang tanggal valid; tanpa itu diabaikan).
    kat_where = ""
    kat_vals = []
    if kat and date_where:
        import datetime as _dt
        _d0 = _dt.date.fromisoformat(d0)
        _d2 = _d0 - _dt.timedelta(days=61)
        d2s, d2e = _d2.isoformat(), (_d0 - _dt.timedelta(days=1)).isoformat()
        _andil = ("EXISTS (SELECT 1 FROM getah_andil a WHERE a.kode_evapot = s.kode_evapot"
                  " AND a.id_penyadap IS NOT NULL)")
        _two = ("EXISTS (SELECT 1 FROM getah_aktivitas_sadap t WHERE t.kode_evapot = s.kode_evapot"
                " AND t.tgl_pembaharuan BETWEEN %s AND %s)")
        if kat == "idle":
            # Baris periode LALU; petak harus idle SEKARANG (cur=0 implisit karena
            # ... di bawah dibuktikan via NOT EXISTS; penyadap ada; ramai 61 hari).
            rd0, rd1 = _prev_period_bounds(y, m, pr)
            date_where = " AND s.tgl_pembaharuan BETWEEN %s AND %s"
            date_vals = [rd0, rd1]
            kat_where = (f" AND NOT EXISTS (SELECT 1 FROM getah_aktivitas_sadap c"
                         f" WHERE c.kode_evapot = s.kode_evapot AND c.tgl_pembaharuan BETWEEN %s AND %s)"
                         f" AND {_andil} AND {_two}")
            kat_vals = [d0, d1, d2s, d2e]
        elif kat == "bongkor":
            kat_where = " AND 1 = 0"
            kat_vals = []

    # Kolom popup + join sama untuk 3 cabang. Cuma JOIN getah_petak (untuk
    # nomor_petak) yang bergantung pada filter wilayah — Left Join supaya petak
    # tanpa RTT tidak killing baris aktivitas.
    cols = """s.id, s.kode_evapot, s.pembaharuan_ke, s.tgl_pembaharuan,
            DATE_FORMAT(s.date_created, '%%H:%%i') AS jam_input,
            s.latitude, s.longitude, s.altitude,
            s.quare, s.semprot_cas, s.kerok, s.budaya_bersih, s.naik_batok,
            s.aktivitas_photo, f.filename_disk AS foto_file, f.storage AS foto_storage,
            s.cuaca, s.akses_lokasi,
            py.nama_penyadap,
            u.first_name AS user_first, u.last_name AS user_last,
            jb.nama_jabatan,
            COUNT(*) OVER () AS _total,
            SUM(s.latitude IS NULL OR s.latitude = 0 OR s.longitude IS NULL OR s.longitude = 0) OVER () AS _no_coord"""
    joins = """FROM getah_aktivitas_sadap s
            LEFT JOIN directus_files f ON f.id = s.aktivitas_photo
            LEFT JOIN getah_penyadap py ON py.id = s.id_penyadap
            LEFT JOIN directus_users u ON u.id = s.user_created
            LEFT JOIN jabatan jb ON jb.id = u.jabatan"""
    if has_w:
        tahun_rtt = int(_tahun) if _tahun else 2026
        return q(f"""
            SELECT {cols}, p.nomor_petak
            {joins}
            JOIN getah_petak p ON p.kode_evapot = s.kode_evapot AND p.tahun_rtt = %s
            WHERE 1=1{w}{date_where}{kat_where}{pw}
            ORDER BY s.tgl_pembaharuan DESC, s.id DESC
            LIMIT %s
        """, tuple([tahun_rtt] + wv + date_vals + kat_vals + pv + [limit]))
    # Fallback tanpa filter wilayah: petak tetap di-join supaya nomor_petak muncul.
    # tahun_rtt diambil dari tgl_pembaharuan (perpetuum RTT), bukan default keras.
    if not date_where:
        return q(f"""
            SELECT {cols}, p.nomor_petak
            {joins}
            LEFT JOIN getah_petak p ON p.kode_evapot = s.kode_evapot
                 AND p.tahun_rtt = YEAR(s.tgl_pembaharuan)
            WHERE 1=1{pw}
            ORDER BY s.tgl_pembaharuan DESC, s.id DESC
            LIMIT %s
        """, tuple(pv + [limit]))
    return q(f"""
        SELECT {cols}, p.nomor_petak
        {joins}
        LEFT JOIN getah_petak p ON p.kode_evapot = s.kode_evapot
             AND p.tahun_rtt = YEAR(s.tgl_pembaharuan)
        WHERE 1=1{date_where}{kat_where}{pw}
        ORDER BY s.tgl_pembaharuan DESC, s.id DESC
        LIMIT %s
    """, tuple(date_vals + kat_vals + pv + [limit]))


@template("petak_adjacent")
def petak_adjacent(kode_tpg: int, kode_evapot: str, **kw):
    """Petak sebelah (same TPG, different evapot)."""
    return q("""
        SELECT kode_evapot, nomor_petak, tahun_rtt, luas_baku
        FROM getah_petak
        WHERE kode_tpg = %s AND kode_evapot <> %s AND tahun_rtt = 2026
        LIMIT 5
    """, (kode_tpg, kode_evapot))


@template("petak_multi_penyadap")
def petak_multi_penyadap(tahun: int = 2026, **kw):
    """Petak with more than 1 penyadap."""
    return q("""
        SELECT
            p.kode_evapot, p.nomor_petak,
            COUNT(DISTINCT a.id_penyadap) AS n_penyadap,
            ROUND(SUM(a.luas_andil), 2) AS total_andil,
            p.luas_baku
        FROM getah_petak p
        JOIN getah_andil a ON a.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s
        GROUP BY p.id
        HAVING n_penyadap > 1
        ORDER BY n_penyadap DESC
    """, (tahun,))


@template("produksi_aktiv")
def produksi_aktiv(tahun: int, bulan: int, periode: int, **kw):
    """Produksi getah per periode (P1=1-15, P2=16-end). Scoped wilayah bila filter diberi."""
    d0, d1 = period_bounds(tahun, bulan, periode)
    w, wv = _wilayah_where(kw, alias="p")
    return q(f"""
        SELECT
            ROUND(SUM(p.berat_penerimaan), 2) AS total_kg,
            COUNT(*) AS n_terima,
            COUNT(DISTINCT p.kode_evapot) AS n_petak
        FROM getah_aktivitas_penerimaan p
        WHERE p.tanggal BETWEEN %s AND %s{w}
    """, (d0, d1, *wv))


@template("produksi_year_to_date")
def produksi_year_to_date(tahun: int, bulan: int, day: int = 15, **kw):
    """Produksi getah YTD (Jan sampai tgl tertentu). Scoped wilayah bila filter diberi."""
    w, wv = _wilayah_where(kw, alias="p")
    return q(f"""
        SELECT
            ROUND(SUM(p.berat_penerimaan), 2) AS total_kg,
            COUNT(*) AS n_terima,
            COUNT(DISTINCT p.kode_evapot) AS n_petak
        FROM getah_aktivitas_penerimaan p
        WHERE YEAR(p.tanggal) = %s
          AND p.tanggal <= %s{w}
    """, (tahun, f"{tahun:04d}-{bulan:02d}-{day:02d}", *wv))


@template("petak_tidak_efisien")
def petak_tidak_efisien(tahun: int, **kw):
    """Petak tidak efisien (luas_andil < luas_baku)."""
    return q("""
        SELECT
            p.kode_evapot, p.nomor_petak,
            p.luas_baku,
            ROUND(SUM(a.luas_andil), 2) AS total_andil,
            ROUND(p.luas_baku - SUM(a.luas_andil), 2) AS selisih
        FROM getah_petak p
        JOIN getah_andil a ON a.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s
        GROUP BY p.id
        HAVING SUM(a.luas_andil) < p.luas_baku
        ORDER BY selisih DESC
    """, (tahun,))


@template("bongkor_per_wilayah")
def bongkor_per_wilayah(tahun: int, level: str = "kode_bkph", **kw):
    """Petak bongkor per wilayah (allowlist level + nama manusia dari getah_petak)."""
    _require_level(level)
    ncol = _WILAYAH_NAMES[level]
    return q(f"""
        SELECT
            p.{level} AS kode_wilayah,
            MAX(p.{ncol}) AS nama_wilayah,
            COUNT(*) AS jumlah_petak,
            ROUND(SUM(p.luas_baku), 2) AS total_luas
        FROM getah_petak p
        WHERE p.tahun_rtt = %s
          AND NOT EXISTS (
            SELECT 1 FROM getah_andil a WHERE a.kode_evapot = p.kode_evapot
          )
        GROUP BY p.{level}
        ORDER BY jumlah_petak DESC
    """, (tahun,))


@template("status_petak_per_wilayah")
def status_petak_per_wilayah(tahun, bulan, periode, level="kode_bkph", **kw):
    """Status bongkor/idle/aktif per wilayah. CASE persis selaras polygon
    idle_petak_map: cur>0 aktif → cur=0+prev>0 idle → tanpa penyadap/>2bln
    sepi bongkor → ELSE bongkor. Tiga kolom partisi penuh total_petak
    (aktif+idle+bongkor = total, residu 0) sehingga agregat = jumlah polygon.
    Nama manusia langsung dari getah_petak (810/810 terisi, tanpa join)."""
    _require_level(level)
    ncol = _WILAYAH_NAMES[level]
    d0, e1 = period_bounds(tahun, bulan, periode)
    if periode == 2:
        dprev, eprev = period_bounds(tahun, bulan, 1)
    else:
        pb = bulan - 1 if bulan > 1 else 12
        py = tahun if bulan > 1 else tahun - 1
        dprev, eprev = period_bounds(py, pb, 2)
    import datetime as _dt
    _d0 = _dt.date.fromisoformat(d0)
    _d2 = _d0 - _dt.timedelta(days=61)
    d2s, d2e = _d2.isoformat(), (_d0 - _dt.timedelta(days=1)).isoformat()
    w, wv = _wilayah_where(kw)
    return q(f"""
        SELECT p.{level} AS kode_wilayah, MAX(p.{ncol}) AS nama_wilayah,
               COUNT(*) AS total_petak,
               ROUND(SUM(p.luas_baku), 2) AS total_luas,
               SUM(CASE WHEN COALESCE(cur.cnt,0) > 0 THEN 1 ELSE 0 END) AS aktif,
               SUM(CASE WHEN COALESCE(cur.cnt,0) = 0 AND COALESCE(prev.cnt,0) > 0 THEN 1 ELSE 0 END) AS idle,
               -- = ELSE bongkor polygon (penyadap=0 / two-sepi / sisa) → partisi penuh
               SUM(CASE WHEN COALESCE(cur.cnt,0) = 0 AND COALESCE(prev.cnt,0) = 0
                        THEN 1 ELSE 0 END) AS bongkor,
               ROUND(SUM(CASE WHEN COALESCE(a.penyadap,0) = 0 THEN p.luas_baku ELSE 0 END), 2) AS luas_bongkor
        FROM getah_petak p
        LEFT JOIN (SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap,
                          COUNT(*) AS jumlah_andil
                   FROM getah_andil GROUP BY kode_evapot) a ON a.kode_evapot = p.kode_evapot
        LEFT JOIN (SELECT kode_evapot, COUNT(*) AS cnt FROM getah_aktivitas_sadap
                   WHERE tgl_pembaharuan BETWEEN %s AND %s GROUP BY kode_evapot
                  ) cur ON cur.kode_evapot = p.kode_evapot
        LEFT JOIN (SELECT kode_evapot, COUNT(*) AS cnt FROM getah_aktivitas_sadap
                   WHERE tgl_pembaharuan BETWEEN %s AND %s GROUP BY kode_evapot
                  ) prev ON prev.kode_evapot = p.kode_evapot
        LEFT JOIN (SELECT kode_evapot, COUNT(*) AS cnt FROM getah_aktivitas_sadap
                   WHERE tgl_pembaharuan BETWEEN %s AND %s GROUP BY kode_evapot
                  ) two ON two.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s{w}
        GROUP BY p.{level}
        ORDER BY bongkor DESC
    """, (d0, e1, dprev, eprev, d2s, d2e, tahun, *wv))


@template("produksi_per_wilayah")
def produksi_per_wilayah(tahun, bulan, periode, level="kode_bkph", **kw):
    """Produksi + achievement per wilayah. actual = SUM langsung penerimaan per grup;
    target/achievement = agregat rkap_map logic (SUM realisasi / SUM target) per grup —
    bukan rata-rata persen per petak. Nama manusia dari getah_petak."""
    _require_level(level)
    ncol = _WILAYAH_NAMES[level]
    # Kumulatif Jan s/d (bulan, periode) — selaras rkap_map: actual kumulatif
    # vs target kumulatif. Periode-saja vs kumulatif = achievement bias.
    d0y, _e1 = period_bounds(tahun, 1, 1)
    _, dlast = period_bounds(tahun, bulan, periode)
    # persen kumulatif skalar via helper — bukan SUM-dalam-SUM (err 1111).
    total_pct = _target_pct(tahun, bulan, periode)
    return q(f"""
        SELECT p.{level} AS kode_wilayah, MAX(p.{ncol}) AS nama_wilayah,
               COUNT(*) AS n_petak,
               ROUND(COALESCE(SUM(prod.actual), 0), 1) AS actual_kg,
               ROUND(COALESCE(SUM(p.target_rkap), 0) * %s / 100, 1) AS target_kg,
               ROUND(100 * COALESCE(SUM(prod.actual), 0)
                     / NULLIF(SUM(p.target_rkap) * %s / 100, 0), 2) AS achievement_pct
        FROM getah_petak p
        LEFT JOIN (
            SELECT kode_evapot, SUM(COALESCE(berat_penerimaan, 0)) AS actual
            FROM getah_aktivitas_penerimaan
            WHERE tanggal BETWEEN %s AND %s
            GROUP BY kode_evapot
        ) prod ON prod.kode_evapot = p.kode_evapot
        WHERE p.tahun_rtt = %s
        GROUP BY p.{level}
        ORDER BY actual_kg DESC
    """, (total_pct, total_pct, d0y, dlast, tahun))


@template("produksi_trend")
def produksi_trend(tahun: int, **kw):
    """Produksi per periode P1/P2 Jan-Des 1 tahun — 1 query hemat 18 call. Untuk chart trend & hitung growth."""
    w, wv = _wilayah_where(kw, alias="p")
    # periode P1=1-15, P2=16-end — group langsung di DB, bukan loop Python
    return q(f"""
        SELECT MONTH(p.tanggal) AS bulan,
               CASE WHEN DAY(p.tanggal) <= 15 THEN 1 ELSE 2 END AS periode,
               ROUND(SUM(p.berat_penerimaan), 2) AS total_kg,
               COUNT(*) AS n_terima,
               COUNT(DISTINCT p.kode_evapot) AS n_petak
        FROM getah_aktivitas_penerimaan p
        WHERE YEAR(p.tanggal) = %s{w}
        GROUP BY bulan, periode
        ORDER BY bulan, periode
    """, (tahun, *wv))


@template("aktivitas_trend")
def aktivitas_trend(tahun: int, **kw):
    """Aktivitas sadap per periode P1/P2 — 1 query. aktif = distinct petak dengan cur>0."""
    w, wv = _wilayah_where(kw, alias="p")
    # _wilayah_where untuk aktivitas perlu join petak — filter via petak.kode_*
    # bila tanpa wilayah, w kosong; bila ada, join getah_petak p
    if w:
        return q(f"""
            SELECT MONTH(s.tgl_pembaharuan) AS bulan,
                   CASE WHEN DAY(s.tgl_pembaharuan) <= 15 THEN 1 ELSE 2 END AS periode,
                   COUNT(*) AS n_aktivitas,
                   COUNT(DISTINCT s.kode_evapot) AS n_petak_aktif,
                   COUNT(DISTINCT s.id_penyadap) AS n_penyadap
            FROM getah_aktivitas_sadap s
            JOIN getah_petak p ON p.kode_evapot = s.kode_evapot AND p.tahun_rtt = %s{w}
            WHERE YEAR(s.tgl_pembaharuan) = %s
            GROUP BY bulan, periode ORDER BY bulan, periode
        """, (tahun, tahun, *wv))
    return q("""
        SELECT MONTH(s.tgl_pembaharuan) AS bulan,
               CASE WHEN DAY(s.tgl_pembaharuan) <= 15 THEN 1 ELSE 2 END AS periode,
               COUNT(*) AS n_aktivitas,
               COUNT(DISTINCT s.kode_evapot) AS n_petak_aktif,
               COUNT(DISTINCT s.id_penyadap) AS n_penyadap
        FROM getah_aktivitas_sadap s
        WHERE YEAR(s.tgl_pembaharuan) = %s
        GROUP BY bulan, periode ORDER BY bulan, periode
    """, (tahun,))


@template("target_pct")
def target_pct(tahun, bulan, periode, **kw):
    """Persen RO kumulatif s/d (bulan, periode) — skalar untuk guard KPI.
    Satu pintu dengan _target_pct agar narasi tak hitung persen sendiri."""
    return {"columns": ["pct"], "rows": [{"pct": _target_pct(tahun, bulan, periode)}],
            "row_count": 1, "elapsed_ms": 0, "sql": "target_pct"}


@template("petak_non_rtt")
def petak_non_rtt(tahun: int, **kw):
    """Petak yang tidak termasuk RTT (bukan petak tahun ini)."""
    return q("""
        SELECT
            kode_evapot, nomor_petak, luas_baku, tahun_rtt
        FROM getah_petak
        WHERE tahun_rtt <> %s
        LIMIT 20
    """, (tahun,))



@template("laporan_perencanaan_target_setor_vs_ro_nps")
def laporan_perencanaan_target_setor_vs_ro_nps(tahun, bulan, periode, **kw):
    """LAPORAN PERENCANAAN TARGET SETOR VS TARGET RO/NPS per Mandor/KTS x TPG.
    Kolom (urut MERENCANAKAN terbesar): BKPH, TPG (alias), NAMA (TRIM first_name+last_name), KODE JAB (jabatan.kode_jabatan), TARGET RO/NPS (Kg) = SUM DISTINCT petak.target_rkap * _target_pct /100, MERENCANAKAN (Kg) = SUM rencana_berat periode, GAP % = 100*MERENCANAKAN/TARGET.
    Periode: P1=1-15, P2=16-akhir bulan. TARGET kumulatif s/d (bulan,periode) via _target_pct. Dedup petak per mandor x TPG."""
    d0, e1 = period_bounds(tahun, bulan, periode)
    total_pct = _target_pct(tahun, bulan, periode)
    w, wv = _wilayah_where(kw, alias="pt")
    return q(f"""
        SELECT t.BKPH AS bkph, t.alias AS tpg, TRIM(CONCAT(COALESCE(u.first_name,''), ' ', COALESCE(u.last_name,''))) AS nama, COALESCE(jb.kode_jabatan, '-') AS kode_jab, ROUND(SUM(d.target_rkap) * %s / 100, 1) AS target_ro_nps_kg, ROUND(SUM(d.merencanakan_kg), 1) AS merencanakan_kg, ROUND(100 * SUM(d.merencanakan_kg) / NULLIF(SUM(d.target_rkap) * %s / 100, 0), 1) AS gap_pct
        FROM ( SELECT r.user_created, pt.kode_tpg, pt.kode_evapot, MAX(pt.target_rkap) AS target_rkap, SUM(r.rencana_berat) AS merencanakan_kg FROM getah_rencana_aktivitas r JOIN getah_petak pt ON pt.kode_evapot = r.kode_evapot AND pt.tahun_rtt = %s WHERE r.tanggal_rencana BETWEEN %s AND %s{w} GROUP BY r.user_created, pt.kode_tpg, pt.kode_evapot ) d
        LEFT JOIN getah_daftar_tpg t ON t.kode_tpg = d.kode_tpg LEFT JOIN directus_users u ON u.id = d.user_created LEFT JOIN jabatan jb ON jb.id = u.jabatan
        GROUP BY t.BKPH, t.alias, u.first_name, u.last_name, jb.kode_jabatan, d.kode_tpg, d.user_created ORDER BY merencanakan_kg DESC
    """, (total_pct, total_pct, tahun, d0, e1, *wv))

@template("rencana_aktivitas")
def rencana_aktivitas(tahun, bulan, periode, **kw):
    """Rencana berat getah per periode (getah_rencana_aktivitas.rencana_berat). Scoped wilayah bila filter diberi."""
    d0, e1 = period_bounds(tahun, bulan, periode)
    w, wv = _wilayah_where(kw, alias="r")
    return q(f"""
        SELECT COUNT(*) AS n_rencana,
               ROUND(COALESCE(SUM(r.rencana_berat),0),1) AS rencana_kg
        FROM getah_rencana_aktivitas r
        WHERE r.tanggal_rencana BETWEEN %s AND %s{w}
    """, (d0, e1, *wv))

@template("wilayah_lookup")
def wilayah_lookup(nama, **kw):
    """Fuzzy lookup wilayah by name/alias (case-insensitive LIKE). Returns level+kode+nama+alias for disambiguasi."""
    qstr = f"%{nama.strip().lower()}%"
    return q("""
        SELECT * FROM (
            SELECT 'bkph' AS level, CAST(kode_bkph AS CHAR) AS kode, bkph AS nama, '' AS alias, CAST(kode_kph AS CHAR) AS kode_kph, CAST(kode_divre AS CHAR) AS kode_divre FROM bkph WHERE LOWER(bkph) LIKE %s
            UNION ALL SELECT 'rph', kode_rph, rph, '', CAST(kode_kph AS CHAR), CAST(kode_divre AS CHAR) FROM rph WHERE LOWER(rph) LIKE %s
            UNION ALL SELECT 'tpg', CAST(kode_tpg AS CHAR), nama_tpg, alias, CAST(kode_kph AS CHAR), CAST(kode_divre AS CHAR) FROM getah_daftar_tpg WHERE LOWER(nama_tpg) LIKE %s OR LOWER(alias) LIKE %s
            UNION ALL SELECT 'kph', CAST(kode_kph AS CHAR), kph, '', CAST(kode_kph AS CHAR), CAST(kode_divre AS CHAR) FROM kph WHERE LOWER(kph) LIKE %s
            UNION ALL SELECT 'divre', CAST(kode_divre AS CHAR), divre, '', NULL, CAST(kode_divre AS CHAR) FROM divre WHERE LOWER(divre) LIKE %s
        ) u LIMIT 10
    """, (qstr, qstr, qstr, qstr, qstr, qstr))

@template("wilayah_labels")
def wilayah_labels(**kw):
    """Distinct wilayah codes + human names (for filter labels). Include parent codes for hierarchical filtering.

    Setiap level membawa rantai KODE parent numerik (bukan nama) agar cascade
    frontend + scope server tak perlu menebak via pencocokan nama/slice:
    kph{divre,kode_divre}, bkph{kph,kode_kph,kode_divre}, rph{bkph,kode_bkph,
    kode_kph,kode_divre}, tpg{kode_rph,kode_bkph,kode_kph,kode_divre}.
    Kolom nama (divre/kph/bkph/RPH/BKPH) ikut disertakan untuk kompat mundur.
    Junk TPG (kode kecil tes, mis. 45/992/993/999) dibuang via panjang 11 digit."""
    divre = q("SELECT kode_divre, divre FROM divre WHERE kode_divre IS NOT NULL ORDER BY kode_divre")
    kph = q("SELECT kode_kph, kph, kode_divre, divre FROM kph ORDER BY kode_kph")
    bkph = q("SELECT kode_bkph, bkph, kode_kph, kph, kode_divre, divre FROM bkph ORDER BY kode_bkph")
    rph = q("SELECT kode_rph, rph, kode_bkph, bkph, kode_kph, kph, kode_divre, divre FROM rph ORDER BY kode_rph")
    tpg = q("SELECT kode_tpg, nama_tpg, alias, RPH, BKPH, kph, divre, kode_rph, kode_bkph, kode_kph, kode_divre FROM getah_daftar_tpg WHERE kode_tpg IS NOT NULL AND CHAR_LENGTH(CAST(kode_tpg AS CHAR)) = 11 ORDER BY kode_tpg LIMIT 500")
    return {"columns": [], "rows": [{"divre": divre["rows"], "kph": kph["rows"], "bkph": bkph["rows"], "rph": rph["rows"], "tpg": tpg["rows"]}], "row_count": 1, "elapsed_ms": 0, "sql": "wilayah_labels"}

def run(name, **params):
    if name not in T:
        raise KeyError(f"unknown template: {name}. ada: {sorted(T)}")
    # Default tahun/bulan/periode so ANA never has to guess — hanya bila benar-benar param formal, bukan local.
    import inspect as _insp
    sig = _insp.signature(T[name])
    _has = sig.parameters
    if "tahun" not in params and "tahun" in _has:
        params["tahun"] = CURRENT_YEAR
    if "bulan" not in params and "bulan" in _has:
        params["bulan"] = datetime.date.today().month
    if "periode" not in params and "periode" in _has:
        params["periode"] = 1
    return T[name](**params)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        def parse_val(v):
            # bare except dipersempit ke ValueError: parse_val hanya gagal saat
            # parsing angka, error lain harus tetap naik ke caller.
            try:
                return int(v)
            except ValueError:
                try:
                    return float(v)
                except ValueError:
                    return v
        r = run(sys.argv[1], **{k: parse_val(v) for k, v in (a.split("=") for a in sys.argv[2:])})
        print(json.dumps(r, default=str, indent=1, ensure_ascii=False))
    else:
        print(json.dumps(sorted(T), indent=1))