#!/usr/bin/env python3
"""Import ui/data/ref_jawa_kabkot.geojson -> tabel ref_jawa_kabkot.

Idempoten (TRUNCATE + isi ulang per sumber yang sama). Tabel dibuat bila
belum ada, pola kolom mengikuti petak_polygon (polygon = teks GeoJSON).

Jalankan: python3 scripts/import_ref_jawa_kabkot.py [--in ui/data/ref_jawa_kabkot.geojson]
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
    ap.add_argument("--in", dest="inp", default="ui/data/ref_jawa_kabkot.geojson")
    args = ap.parse_args()
    data = json.loads((ROOT / args.inp).read_text(encoding="utf-8"))
    feats = data.get("features") or []
    env = load_env()
    conn = db_conn(env)
    try:
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS ref_jawa_kabkot (
                id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                provinsi VARCHAR(64), kabkot VARCHAR(64),
                provno VARCHAR(8), kabkotno VARCHAR(8),
                polygon LONGTEXT, sumber VARCHAR(128),
                UNIQUE KEY uq_kab (provno, kabkotno),
                KEY ix_prov (provinsi)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
            n = 0
            for f in feats:
                p = f.get("properties") or {}
                g = f.get("geometry") or {}
                if g.get("type") not in ("Polygon", "MultiPolygon"):
                    continue
                cur.execute(
                    """INSERT INTO ref_jawa_kabkot (provinsi, kabkot, provno, kabkotno, polygon, sumber)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE kabkot=VALUES(kabkot), provinsi=VALUES(provinsi),
                       polygon=VALUES(polygon), sumber=VALUES(sumber)""",
                    (p.get("provinsi"), p.get("kabkot"), p.get("provno"), p.get("kabkotno"),
                     json.dumps(g, ensure_ascii=False), p.get("sumber")))
                n += 1
        conn.commit()
    finally:
        conn.close()
    print(json.dumps({"ok": True, "features": n, "table": "ref_jawa_kabkot"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
