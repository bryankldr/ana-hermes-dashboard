#!/usr/bin/env python3
"""Export snapshot petak -> GeoJSONSeq tipis untuk tippecanoe (P2-1).

Atribut tipis saja: key (nomor_petak + kode_evapot) + warna + kategori.
Atribut live tetap via viewport GeoJSON override keyed on nomor_petak.
Geometry: pp.polygon (GeoJSON string) -> geometry Feature per baris.

Jalankan: python3 scripts/export_petak.py [--tahun 2026] [--out tiles/petak.ndjson]
"""
import argparse, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from refresh_petak_simple import load_env, db_conn  # reuse koneksi/env, bukan duplikat


def fetch(conn, tahun, kode_kph=None):
    sql = """
    SELECT p.nomor_petak, p.kode_evapot, pp.polygon AS polygon_json,
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
    JOIN petak_polygon pp ON pp.kode_evapot = p.kode_evapot
    LEFT JOIN (
        SELECT kode_evapot, COUNT(DISTINCT id_penyadap) AS penyadap,
               SUM(luas_andil) AS luas_andil
        FROM getah_andil GROUP BY kode_evapot
    ) a ON a.kode_evapot = p.kode_evapot
    WHERE p.tahun_rtt = %s AND pp.polygon IS NOT NULL AND pp.polygon != ''
    """
    vals = [tahun]
    if kode_kph:
        sql += " AND p.kode_kph = %s"
        vals.append(int(kode_kph))
    sql += " ORDER BY p.kode_evapot"
    with conn.cursor() as cur:
        cur.execute(sql, tuple(vals))
        return cur.fetchall()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tahun", type=int, default=2026)
    ap.add_argument("--out", default="tiles/petak.ndjson")
    ap.add_argument("--kode-kph", default="",
                    help="batasi satu KPH (untuk tiles/kph_<kode>.ndjson)")
    args = ap.parse_args()

    env = load_env()
    conn = db_conn(env)
    try:
        rows = fetch(conn, args.tahun, args.kode_kph or None)
        # Metrik bisnis per periode (produksi/aktivitas/matriks diwarnai klien
        # dari kunci ini — tile tak perlu rebuild tiap ganti periode).
        try:
            import tile_metrics as _tm
            _cur = conn.cursor()
            try:
                _metrics, _tpct = _tm.petak_metrics(_cur, args.tahun, args.kode_kph or None)
            finally:
                _cur.close()
            _props_by_ev = {ev: _tm.period_props(m, _tpct) for ev, m in _metrics.items()}
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": f"metrik: {e}"[:200]}))
            raise SystemExit(1)
    finally:
        conn.close()

    # dedupe kode_evapot duplikat: keep polygon terpanjang (sama spt refresh_petak_simple)
    seen = {}
    for r in rows:
        k = str(r["kode_evapot"])
        cur_len = len(r.get("polygon_json") or "")
        prev = seen.get(k)
        if prev is None or cur_len > len(prev.get("polygon_json") or ""):
            seen[k] = r

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as f:
        for r in seen.values():
            try:
                geom = json.loads(r["polygon_json"]) if isinstance(r["polygon_json"], str) else r["polygon_json"]
                if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
                    continue
            except Exception:
                continue
            feat = {"type": "Feature", "geometry": geom, "properties": {
                "n": str(r["nomor_petak"] or r["kode_evapot"]),
                "e": str(r["kode_evapot"]),
                "kategori": r["kategori"],
                "warna": r["warna"],
            }}
            try:
                feat["properties"].update(_props_by_ev.get(str(r["kode_evapot"]), {}))
            except Exception:
                pass
            f.write(json.dumps(feat, ensure_ascii=False) + "\n")
            n += 1
    print(json.dumps({"ok": True, "tahun": args.tahun, "features": n,
                      "raw_rows": len(rows), "out": str(out),
                      "bytes": out.stat().st_size}))


if __name__ == "__main__":
    main()
