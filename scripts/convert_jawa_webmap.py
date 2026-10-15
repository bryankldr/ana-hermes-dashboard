#!/usr/bin/env python3
"""Ambil batas kabupaten/kota Pulau Jawa dari ArcGIS Online -> GeoJSON WGS84.

Sumber: webmap "Peta Provinsi di Pulau Jawa Indonesia"
(ArcGIS Online, owner niam18) — 6 layer shapefile kab/kota
(Jatim 38, Jateng 37, Banten 8, Jabar 28, Jakarta 6, DIY 5).

Konversi: Esri rings (Web Mercator 102100) -> WGS84, lubang dikenali dari
orientasi ring. Output: ui/data/ref_jawa_kabkot.geojson + ringkasan JSON.

Jalankan: python3 scripts/convert_jawa_webmap.py [--out ui/data/ref_jawa_kabkot.geojson]
Import ke DB: python3 scripts/import_ref_jawa_kabkot.py
"""
import argparse
import json
import math
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
WEBMAP_ID = "66c61c9dd8894dd3b3aa3257bfb6b018"
R = 20037508.34  # konstanta Mercator (setengah keliling), HANYA untuk x
# Meter per derajat lintang (WGS84, cukup untuk Jawa): y_sumber / ini = lat.
M_PER_DEG = 6378137 * math.pi / 180.0  # 111319.49 (jari-jari bumi, BUKAN R)


def merc_to_wgs(x, y):
    # ANOMALI SUMBER (terverifikasi dua titik: Pacitan & Kep. Seribu):
    # x = Web-Mercator sejati, TETAPI y = derajat_lintang × meter/derajat
    # (bukan Mercator). y/R*180... di bawah ini pemetaan empiris yang cocok
    # geografi (±0.01°): lat = y / meter-per-derajat.
    return [x / R * 180.0, y / M_PER_DEG]


def ring_area(r):
    s = 0.0
    n = len(r)
    for i in range(n):
        x1, y1 = r[i]
        x2, y2 = r[(i + 1) % n]
        s += (x2 - x1) * (y2 + y1)
    return s / 2.0  # Esri: >0 = searah jarum jam (outer), <0 = lubang


def point_in_ring(pt, ring):
    x, y = pt
    c = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                c = not c
    return c


def rings_to_polygons(rings):
    outers = []
    holes = []
    for r in rings:
        if len(r) < 4:
            continue
        (holes if ring_area(r) < 0 else outers).append(r)
    polys = [[o] for o in outers]
    for h in holes:
        for poly in polys:
            if point_in_ring(h[0], poly[0]):
                poly.append(h)
                break
    return polys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="ui/data/ref_jawa_kabkot.geojson")
    ap.add_argument("--webmap", default=WEBMAP_ID)
    args = ap.parse_args()
    with urllib.request.urlopen(
            f"https://www.arcgis.com/sharing/rest/content/items/{args.webmap}/data?f=json",
            timeout=60) as r:
        data = json.load(r)
    feats, n_holes = [], 0
    for lyr in data.get("operationalLayers", []):
        for sub in lyr.get("featureCollection", {}).get("layers", []):
            for f in sub.get("featureSet", {}).get("features", []):
                at = f.get("attributes") or {}
                rings = (f.get("geometry") or {}).get("rings") or []
                polys = rings_to_polygons(rings)
                n_holes += sum(len(p) - 1 for p in polys)
                if not polys:
                    continue
                geom = {"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1 \
                    else {"type": "MultiPolygon", "coordinates": polys}
                # proyeksikan ke WGS84
                def conv(c):
                    if isinstance(c[0], (int, float)):
                        return merc_to_wgs(c[0], c[1])
                    return [conv(e) for e in c]
                geom["coordinates"] = conv(geom["coordinates"])
                feats.append({"type": "Feature", "geometry": geom, "properties": {
                    "provinsi": at.get("PROVINSI"), "kabkot": at.get("KABKOT"),
                    "provno": str(at.get("PROVNO") or ""), "kabkotno": str(at.get("KABKOTNO") or ""),
                    "sumber": "arcgis:" + args.webmap}})
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "features": len(feats), "holes": n_holes,
                      "bytes": out.stat().st_size, "out": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
