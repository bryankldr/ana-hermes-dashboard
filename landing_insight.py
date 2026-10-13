"""Insight publik landing — agregat NYATA dari kph_bwb_sandbox2, bukan karangan.

Aturan keras #2: tiap angka = hasil COUNT langsung + label periode/sumber/waktu.
Gagal DB = raise (endpoint ubah jadi 503 + kartu disembunyikan frontend),
BUKAN angka 0 bohong. Tanpa data per-user/wilayah sensitif (pra-login tak ada
scope) — hanya agregat total + tren + cakupan.
"""
import time

try:
    import pymysql
except Exception:
    pymysql = None


def _conn():
    import auth_local
    if pymysql is None:
        raise RuntimeError("pymysql tak tersedia")
    return pymysql.connect(**auth_local._db_kwargs())


def _one(cur, sql, args=()):
    cur.execute(sql, args)
    r = cur.fetchone()
    return r[0] if r else 0


def snapshot():
    """Kembalikan dict 3 indeks + tren 6 periode. Raise bila DB mati."""
    t0 = time.time()
    conn = _conn()
    try:
        cur = conn.cursor()
        # 1. Petak aktif tahun berjalan (distinct kode_evapot, bukan baris mentah).
        cur.execute("SELECT YEAR(CURDATE())")
        year = cur.fetchone()[0]
        petak = _one(cur, "SELECT COUNT(DISTINCT kode_evapot) FROM getah_petak WHERE tahun_rtt=%s", (year,))
        # 2. Aktivitas P1/P2 berjalan vs periode lalu (dua query, tren dihitung).
        cur.execute("SELECT YEAR(CURDATE()), MONTH(CURDATE()), DAY(CURDATE())")
        y, m, d = cur.fetchone()
        if d <= 15:
            cur_lo, cur_hi = f"{y}-{m:02d}-01", f"{y}-{m:02d}-15"
            if m == 1:
                prev_lo, prev_hi = f"{y-1}-12-16", f"{y-1}-12-31"
            else:
                import calendar
                last = calendar.monthrange(y, m - 1)[1]
                prev_lo, prev_hi = f"{y}-{m-1:02d}-16", f"{y}-{m-1:02d}-{last:02d}"
            periode = f"{y}-{m:02d}-P1"
        else:
            import calendar
            last = calendar.monthrange(y, m)[1]
            cur_lo, cur_hi = f"{y}-{m:02d}-16", f"{y}-{m:02d}-{last:02d}"
            prev_lo, prev_hi = f"{y}-{m:02d}-01", f"{y}-{m:02d}-15"
            periode = f"{y}-{m:02d}-P2"
        akt = _one(cur, "SELECT COUNT(*) FROM getah_aktivitas_sadap WHERE tgl_pembaharuan BETWEEN %s AND %s", (cur_lo, cur_hi))
        prev = _one(cur, "SELECT COUNT(*) FROM getah_aktivitas_sadap WHERE tgl_pembaharuan BETWEEN %s AND %s", (prev_lo, prev_hi))
        tren = None
        if prev:
            tren = round((akt - prev) * 100.0 / prev, 1)
        # Deret 6 periode terakhir untuk mini chart (nyata, 6x COUNT).
        series = []
        yy, mm, half = y, m, (1 if d <= 15 else 2)
        for _ in range(6):
            import calendar
            if half == 1:
                lo, hi = f"{yy}-{mm:02d}-01", f"{yy}-{mm:02d}-15"
                label = f"{mm:02d}-P1"
            else:
                last = calendar.monthrange(yy, mm)[1]
                lo, hi = f"{yy}-{mm:02d}-16", f"{yy}-{mm:02d}-{last:02d}"
                label = f"{mm:02d}-P2"
            series.insert(0, {"label": label,
                              "value": _one(cur, "SELECT COUNT(*) FROM getah_aktivitas_sadap WHERE tgl_pembaharuan BETWEEN %s AND %s", (lo, hi))})
            if half == 1:
                half = 2
                mm -= 1
                if mm < 1:
                    mm, yy = 12, yy - 1
            else:
                half = 1
        # 3. Cakupan wilayah (COUNT tabel nyata).
        bkph = _one(cur, "SELECT COUNT(*) FROM bkph")
        rph = _one(cur, "SELECT COUNT(*) FROM rph")
        tpg = _one(cur, "SELECT COUNT(*) FROM getah_daftar_tpg")
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {
        "ok": True,
        "periode": periode,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "petak": {"value": petak, "tahun": year, "sumber": "getah_petak"},
        "aktivitas": {"value": akt, "prev": prev, "tren_pct": tren, "sumber": "getah_aktivitas_sadap"},
        "series": series,
        "wilayah": {"bkph": bkph, "rph": rph, "tpg": tpg, "sumber": "bkph/rph/getah_daftar_tpg"},
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


# Self-check: python3 landing_insight.py (butuh DB hidup)
if __name__ == "__main__":
    import json
    print(json.dumps(snapshot(), indent=1, default=str)[:1500])
