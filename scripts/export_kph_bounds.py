#!/usr/bin/env python3
"""Export outline KPH (dissolve petak per kode_kph) -> ndjson per DIVRE.

Sumber bentuk = gabungan polygon petak (BUKAN batas resmi BPN) — cukup
sebagai konteks wilayah tetangga + dasar choropleth overview DIREKSI/DIVRE.
Atribut tipis: kode_kph, kph, kode_divre (tanpa atribut bisnis/nama sensitif).

Jalankan: python3 scripts/export_kph_bounds.py [--tahun 2026] [--out-dir tiles]
Hasil: tiles/bounds_{kode_divre}.ndjson per divre + ringkasan JSON di stdout.
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from refresh_petak_simple import load_env, db_conn  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tahun", type=int, default=2026)
    ap.add_argument("--out-dir", default="tiles")
    ap.add_argument("--simplify", type=float, default=0.0005,
                    help="toleransi simplify derajat (~50m), topologi dijaga")
    args = ap.parse_args()

    try:
        from shapely.geometry import shape as _shape
        from shapely.ops import unary_union as _union
        from shapely.validation import make_valid as _valid
    except ImportError as e:
        print(json.dumps({"ok": False, "error": f"shapely tak tersedia: {e}"}))
        raise SystemExit(1)

    env = load_env()
    conn = db_conn(env)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT kode_kph, kph, kode_divre, divre FROM kph ORDER BY kode_kph")
            kph_meta = {str(r["kode_kph"]): dict(r) for r in cur.fetchall()}
            cur.execute(
                """SELECT p.kode_kph, pp.polygon AS polygon_json
                   FROM getah_petak p
                   JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
                   WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL AND pp.polygon != ''""",
                (args.tahun,))
            rows = cur.fetchall()
    finally:
        conn.close()

    per_kph = {}
    bad = 0
    for r in rows:
        try:
            geom = json.loads(r["polygon_json"]) if isinstance(r["polygon_json"], str) else r["polygon_json"]
            if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
                bad += 1
                continue
            g = _shape(geom)
            if not g.is_valid:
                try:
                    g = _valid(g)
                except Exception:
                    bad += 1
                    continue
            per_kph.setdefault(str(r["kode_kph"]), []).append(g)
        except Exception:
            bad += 1

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    files, total_kph, fallback = [], 0, []
    by_divre = {}
    for kode_kph, geoms in sorted(per_kph.items()):
        if not geoms:
            continue
        try:
            u = _union(geoms)
            if not u.is_valid:
                try:
                    u = _valid(u)
                except Exception:
                    pass
            u = u.simplify(args.simplify, preserve_topology=True)
            if u.is_empty:
                continue
        except Exception:
            continue
        meta = kph_meta.get(kode_kph, {})
        gtype = u.geom_type
        if gtype not in ("Polygon", "MultiPolygon"):
            # hasil dissolve degenerat — catat, jangan masuk tile
            fallback.append(kode_kph)
            continue
        feat = {"type": "Feature",
                "geometry": u.__geo_interface__,
                "properties": {"kode_kph": kode_kph,
                               "kph": meta.get("kph") or "",
                               "kode_divre": str(meta.get("kode_divre") or "")}}
        by_divre.setdefault(str(meta.get("kode_divre") or "0"), []).append(feat)
        total_kph += 1

    for kode_divre, feats in sorted(by_divre.items()):
        out = out_dir / f"bounds_{kode_divre}.ndjson"
        with out.open("w", encoding="utf-8") as f:
            for ft in feats:
                f.write(json.dumps(ft, ensure_ascii=False) + "\n")
        files.append({"file": out.name, "kode_divre": kode_divre,
                      "kph": len(feats), "bytes": out.stat().st_size})
    print(json.dumps({"ok": True, "tahun": args.tahun, "kph": total_kph,
                      "bad_polygon": bad, "degenerat": fallback, "files": files}))


if __name__ == "__main__":
    main()
