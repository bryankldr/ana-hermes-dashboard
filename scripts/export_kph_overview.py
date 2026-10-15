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
        feat = {"type": "Feature",
                "geometry": item["geometry"],
                "properties": {"kode_kph": kode_kph,
                               "kph": meta.get("kph") or "",
                               "kode_divre": str(meta.get("kode_divre") or ""),
                               "warna": warna,
                               "b": int(b or 0), "k": int(k or 0),
                               "t": int(t or 0), "n": int(tot or 0)}}
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
