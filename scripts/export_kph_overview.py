#!/usr/bin/env python3
"""Export overview KPH berwarna bisnis -> ndjson per DIVRE (query khusus
DIVRE/DIREKSI): dissolve bentuk + klasifikasi warna per KPH.

Warna (disepakati): merah bila porsi bongkor >= 25%; kuning bila porsi
kurang >= 30% atau terpenuhi < 60%; hijau sisanya. Definisi kategori persis
petak_efektivitas_map. Fill SOLID di tile (bukan transparan/gradasi).

Jalankan: python3 scripts/export_kph_overview.py [--tahun 2026]
Hasil: tiles/overview_{kode_divre}.ndjson per divre + ringkasan JSON.
Build: build_pmtiles.py --layer petak (reuse rules warna statis klien).
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from refresh_petak_simple import load_env, db_conn  # noqa: E402
from export_kph_bounds import dissolve_per_kph  # noqa: E402
import tile_metrics as _tm  # noqa: E402


def classify(b, k, t):
    tot = (b or 0) + (k or 0) + (t or 0)
    if tot <= 0:
        return "kuning", 0, 0, 0, 0
    if b / tot >= 0.25:
        warna = "merah"
    elif k / tot >= 0.30 or t / tot < 0.60:
        warna = "kuning"
    else:
        warna = "hijau"
    return warna, tot, b, k, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tahun", type=int, default=2026)
    ap.add_argument("--out-dir", default="tiles")
    ap.add_argument("--simplify", type=float, default=0.0005)
    args = ap.parse_args()

    env = load_env()
    conn = db_conn(env)
    try:
        per_kph, kph_meta, bad, degenerat = dissolve_per_kph(conn, args.tahun, args.simplify)
        # Metrik per periode untuk pewarnaan dinamis klien (produksi/matriks/
        # aktivitas + bulan/periode): agregat per KPH dari data per petak.
        _cur = conn.cursor()
        try:
            _metrics, _tpct = _tm.petak_metrics(_cur, args.tahun)
        finally:
            _cur.close()
        # Agregat per KPH untuk pewarnaan dinamis klien: rerata capaian (oc/om)
        # + porsi petak aktif (sa/sam, 0..1). Kunci: 24 half + 12 full.
        _agg = {}
        for _ev, _m in _metrics.items():
            _kk = _m.get("kph") or ""
            _a = _agg.setdefault(_kk, {"n": 0, "cap": [[] for _ in range(36)],
                                       "act": [0] * 36})
            _a["n"] += 1
            _pp = _tm.period_props(_m, _tpct)
            for _i in range(24):
                _v = _pp.get("c%02d" % (_i + 1))
                if _v is not None and _v >= 0:
                    _a["cap"][_i].append(_v)
                if _m["act"][_i] > 0:
                    _a["act"][_i] += 1
            for _mi in range(12):
                _v = _pp.get("m%02d" % (_mi + 1))
                if _v is not None and _v >= 0:
                    _a["cap"][24 + _mi].append(_v)
                if (_m["act"][_mi * 2] + _m["act"][_mi * 2 + 1]) > 0:
                    _a["act"][24 + _mi] += 1
        with conn.cursor() as cur:
            cur.execute(
                """SELECT p.kode_kph,
                          SUM(COALESCE(a.penyadap, 0) = 0) AS bongkor,
                          SUM(COALESCE(a.penyadap, 0) > 0 AND COALESCE(a.luas_andil, 0) < p.luas_baku) AS kurang,
                          SUM(COALESCE(a.penyadap, 0) > 0 AND COALESCE(a.luas_andil, 0) >= p.luas_baku) AS terpenuhi
                   FROM getah_petak p
                   LEFT JOIN (
                       SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap,
                              SUM(luas_andil) AS luas_andil
                       FROM getah_andil GROUP BY kode_evapot
                   ) a ON a.kode_evapot = p.kode_evapot
                   WHERE p.tahun_rtt = %s
                   GROUP BY p.kode_kph""",
                (args.tahun,))
            shares = {str(r["kode_kph"]): dict(r) for r in cur.fetchall()}
    finally:
        conn.close()

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    files, colored = [], {}
    by_divre = {}
    for kode_kph, item in sorted(per_kph.items()):
        meta = item["meta"]
        sh = shares.get(kode_kph, {})
        warna, tot, b, k, t = classify(sh.get("bongkor"), sh.get("kurang"), sh.get("terpenuhi"))
        colored[kode_kph] = warna
        _ag = _agg.get(kode_kph, {"n": 0, "cap": [[] for _ in range(36)], "act": [0] * 36})
        _dyn = {}
        for _i in range(36):
            _vals = _ag["cap"][_i]
            _dyn["oc%02d" % (_i + 1) if _i < 24 else "om%02d" % (_i - 23)] = (
                round(sum(_vals) / len(_vals), 2) if _vals else -1)
            _dyn["sa%02d" % (_i + 1) if _i < 24 else "sam%02d" % (_i - 23)] = (
                round(_ag["act"][_i] / _ag["n"], 3) if _ag["n"] else -1)
        feat = {"type": "Feature",
                "geometry": item["geometry"],
                "properties": {"kode_kph": kode_kph,
                               "kph": meta.get("kph") or "",
                               "kode_divre": str(meta.get("kode_divre") or ""),
                               "warna": warna,
                               "b": int(b or 0), "k": int(k or 0),
                               "t": int(t or 0), "n": int(tot or 0),
                               **_dyn}}
        by_divre.setdefault(str(meta.get("kode_divre") or "0"), []).append(feat)
    for kode_divre, feats in sorted(by_divre.items()):
        out = out_dir / f"overview_{kode_divre}.ndjson"
        with out.open("w", encoding="utf-8") as f:
            for ft in feats:
                f.write(json.dumps(ft, ensure_ascii=False) + "\n")
        files.append({"file": out.name, "kode_divre": kode_divre,
                      "kph": len(feats), "bytes": out.stat().st_size})
    print(json.dumps({"ok": True, "tahun": args.tahun, "kph": len(per_kph),
                      "warna": colored, "bad_polygon": bad,
                      "degenerat": degenerat, "files": files}, ensure_ascii=False))


if __name__ == "__main__":
    main()
