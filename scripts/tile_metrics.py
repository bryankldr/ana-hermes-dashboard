#!/usr/bin/env python3
"""Metrik bisnis per petak per periode untuk atribut tile (single source).

Dipakai export_petak.py (atribut per petak) dan export_kph_overview.py
(agregat per KPH): realisasi + hitungan aktivitas per setengah-bulan,
pencapaian vs target periode (skalar RO/NPS kumulatif, pola _target_pct).

Kunci properti tile (skalar numerik — MVT tak dukung array):
  tg = target_rkap, lb = luas_baku, la = luas_andil, py = jml penyadap,
  c01..c24 = pencapaian % per P1/P2 Jan..Des (-1 = tanpa target/data),
  m01..m12 = pencapaian % bulan penuh, a01..a24 = hitungan aktivitas P1/P2,
  am01..am12 = hitungan aktivitas bulan penuh.
Indeks: (bulan-1)*2 + (0 untuk P1, 1 untuk P2); panel periode 0 = bulanan.
"""
import calendar


def period_bounds(year, month, periode):
    last = calendar.monthrange(year, month)[1]
    if periode == 0:
        return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last:02d}"
    if periode == 1:
        return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-15"
    return f"{year:04d}-{month:02d}-16", f"{year:04d}-{month:02d}-{last:02d}"


def target_pct_map(cur, tahun):
    """{bulan: {1: pct_p1, 2: pct_p2, 0: pct_full}} dari getah_target_ro_nps."""
    cur.execute(
        """SELECT bulan, COALESCE(SUM(ro_periode_1),0), COALESCE(SUM(ro_periode_2),0)
           FROM getah_target_ro_nps WHERE tahun=%s GROUP BY bulan""", (tahun,))
    per = {}
    for r in cur.fetchall():
        vals = list(r.values())
        m, a, b = vals[0], vals[1], vals[2]
        per[int(m)] = {"p1": float(a or 0), "p2": float(b or 0)}
    out = {}
    for m in range(1, 13):
        p1 = per.get(m, {"p1": 0.0})["p1"]
        p2 = per.get(m, {"p2": 0.0})["p2"]
        cum = sum(per.get(k, {"p1": 0.0})["p1"] + per.get(k, {"p2": 0.0})["p2"] for k in range(1, m))
        out[m] = {1: cum + p1, 2: cum + p1 + p2, 0: cum + p1 + p2}
    return out


def petak_metrics(cur, tahun, kode_kph=None):
    """Return {kode_evapot: {tgt, lb, la, py, nomor, real:[24], act:[24]}} + target pct map.

    DUA query terpisah (realisasi | aktivitas): join ganda dalam satu query
    meledakkan baris (fan-out) dan menggandakan SUM. Tiap query agregasi
    kondisional per setengah-bulan dalam sekali jalan."""
    tpct = target_pct_map(cur, tahun)
    scope = " AND p.kode_kph = %s" if kode_kph else ""
    scopev = [int(kode_kph)] if kode_kph else []
    rcols, rvals = [], []
    for m in range(1, 13):
        for pr in (1, 2):
            d0, d1 = period_bounds(tahun, m, pr)
            rcols.append(
                "SUM(CASE WHEN pen.tanggal BETWEEN %s AND %s "
                "THEN COALESCE(pen.berat_penerimaan,0) ELSE 0 END) AS r" + "%02d" % (m * 2 - (2 - pr)))
            rvals += [d0, d1]
    cur.execute(
        "SELECT p.kode_evapot, MAX(p.target_rkap) AS tgt, MAX(p.luas_baku) AS lb,"
        " MAX(COALESCE(a.luas_andil,0)) AS la, MAX(COALESCE(a.penyadap,0)) AS py,"
        " MAX(p.nomor_petak) AS nomor, MAX(p.kode_kph) AS kph, " + ", ".join(rcols) +
        " FROM getah_petak p"
        " LEFT JOIN (SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap,"
        " SUM(luas_andil) AS luas_andil FROM getah_andil GROUP BY kode_evapot) a"
        " ON a.kode_evapot = p.kode_evapot"
        " LEFT JOIN getah_aktivitas_penerimaan pen ON pen.kode_evapot = p.kode_evapot"
        " WHERE p.tahun_rtt = %s" + scope +
        " GROUP BY p.kode_evapot", rvals + [tahun] + scopev)
    out = {}
    for r in cur.fetchall():
        ev = str(r["kode_evapot"])
        out[ev] = {"tgt": float(r.get("tgt") or 0), "lb": float(r.get("lb") or 0),
                   "la": float(r.get("la") or 0), "py": int(r.get("py") or 0),
                   "nomor": r.get("nomor"), "kph": str(r.get("kph") or ""),
                   "real": [float(r.get("r%02d" % i) or 0) for i in range(1, 25)],
                   "act": [0] * 24}
    acols, avals = [], []
    for m in range(1, 13):
        for pr in (1, 2):
            d0, d1 = period_bounds(tahun, m, pr)
            acols.append(
                "SUM(CASE WHEN s2.tgl_pembaharuan BETWEEN %s AND %s THEN 1 ELSE 0 END) AS a" + "%02d" % (m * 2 - (2 - pr)))
            avals += [d0, d1]
    cur.execute(
        "SELECT p.kode_evapot, " + ", ".join(acols) +
        " FROM getah_petak p"
        " LEFT JOIN getah_aktivitas_sadap s2 ON s2.kode_evapot = p.kode_evapot"
        " WHERE p.tahun_rtt = %s" + scope +
        " GROUP BY p.kode_evapot", avals + [tahun] + scopev)
    for r in cur.fetchall():
        ev = str(r["kode_evapot"])
        if ev in out:
            out[ev]["act"] = [int(r.get("a%02d" % i) or 0) for i in range(1, 25)]
    return out, tpct


def pencapaian(real, tgt, pct):
    t = tgt * pct / 100.0
    if t <= 0:
        return None
    return round(100.0 * real / t, 2)


def period_props(m, tpct):
    """Semua kunci c/m/a/am untuk satu petak."""
    props = {"tg": round(m["tgt"], 2), "lb": round(m["lb"], 2),
             "la": round(m["la"], 2), "py": m["py"]}
    for mi in range(1, 13):
        for pi, key in ((1, "c%02d" % (mi * 2 - 1)), (2, "c%02d" % (mi * 2))):
            v = pencapaian(m["real"][mi * 2 - (3 - pi)], m["tgt"], tpct[mi][pi])
            props[key] = -1 if v is None else v
        vm = pencapaian(m["real"][mi * 2 - 2] + m["real"][mi * 2 - 1], m["tgt"], tpct[mi][0])
        props["m%02d" % mi] = -1 if vm is None else vm
        props["a%02d" % (mi * 2 - 1)] = m["act"][mi * 2 - 2]
        props["a%02d" % (mi * 2)] = m["act"][mi * 2 - 1]
        props["am%02d" % mi] = m["act"][mi * 2 - 2] + m["act"][mi * 2 - 1]
    return props
