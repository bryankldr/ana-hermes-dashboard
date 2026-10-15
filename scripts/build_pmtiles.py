#!/usr/bin/env python3
"""Build tiles/petak.pmtiles dari GeoJSONSeq tipis (pengganti tippecanoe, P2-2).

Gratis penuh: stdlib + mapbox-vector-tile (MIT) + pmtiles (BSD-3).
Tanpa API external, tanpa GPU, tanpa server tile (Martin/tippecanoe).

Pipeline: export_petak.py -> petak.ndjson -> build_pmtiles.py -> petak.pmtiles
Serve: GET /api/tiles/petak.pmtiles (Range 206) di server.py.
Atribut live tetap via viewport GeoJSON override keyed on nomor_petak.

Jalankan: python3 scripts/build_pmtiles.py [--in tiles/petak.ndjson]
         [--out tiles/petak.pmtiles] [--min-zoom 8] [--max-zoom 15]
"""
import argparse
import gzip
import json
import math
import pathlib

from mapbox_vector_tile import encode as mvt_encode

from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXTENTS = 4096


def lnglat_to_tile(lng, lat, z):
    n = 1 << z
    x = int((lng + 180.0) / 360.0 * n)
    lat = max(min(lat, 85.05112878), -85.05112878)
    rad = math.radians(lat)
    y = int((1.0 - math.log(math.tan(rad) + 1.0 / math.cos(rad)) / math.pi) / 2.0 * n)
    return max(0, min(x, n - 1)), max(0, min(y, n - 1))


def tile_to_bounds(x, y, z):
    n = 1 << z
    w = x / n * 360.0 - 180.0
    e = (x + 1) / n * 360.0 - 180.0

    def _lat(yy):
        t = math.pi * (1.0 - 2.0 * yy / n)
        return math.degrees(math.atan(math.sinh(t)))

    n_lat, s_lat = _lat(y), _lat(y + 1)
    return (w, s_lat, e, n_lat)


def _walk_coords(geom):
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "Polygon":
        for ring in c:
            yield from ring
    elif t == "MultiPolygon":
        for poly in c:
            for ring in poly:
                yield from ring


def feat_bbox(geom):
    xs, ys = [], []
    for lng, lat, *_ in _walk_coords(geom):
        xs.append(lng)
        ys.append(lat)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="tiles/petak.ndjson")
    ap.add_argument("--out", dest="out", default="tiles/petak.pmtiles")
    ap.add_argument("--min-zoom", type=int, default=8)
    ap.add_argument("--max-zoom", type=int, default=15)
    ap.add_argument("--layer", default="petak",
                    help="nama layer MVT (petak | kph)")
    args = ap.parse_args()

    feats = []
    with (ROOT / args.inp).open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            g = d.get("geometry") or {}
            if g.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            bb = feat_bbox(g)
            if bb is None:
                continue
            feats.append({"geometry": g, "properties": dict(d.get("properties") or {}),
                          "bbox": bb})
    if not feats:
        raise SystemExit("tidak ada fitur polygon di " + args.inp)

    glo = [feats[0]["bbox"][0], feats[0]["bbox"][1], feats[0]["bbox"][2], feats[0]["bbox"][3]]
    for ft in feats[1:]:
        b = ft["bbox"]
        glo[0] = min(glo[0], b[0])
        glo[1] = min(glo[1], b[1])
        glo[2] = max(glo[2], b[2])
        glo[3] = max(glo[3], b[3])

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    tiles_written = 0
    with write(str(out)) as w:
        for z in range(args.min_zoom, args.max_zoom + 1):
            x0, y1 = lnglat_to_tile(glo[0], glo[1], z)
            x1, y0 = lnglat_to_tile(glo[2], glo[3], z)
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    wb, sb, eb, nb = tile_to_bounds(x, y, z)
                    in_tile = [ft for ft in feats
                               if ft["bbox"][0] <= eb and ft["bbox"][2] >= wb
                               and ft["bbox"][1] <= nb and ft["bbox"][3] >= sb]
                    if not in_tile:
                        continue
                    # ponytail: tanpa clipping presisi (tippecanoe memotong di
                    # batas tile + buffer); renderer MVT memotong sendiri saat
                    # gambar. Upgrade ke shapely-intersection bila tile z
                    # rendah terbukti >500KB.
                    layer_feats = [{"geometry": ft["geometry"],
                                    "properties": ft["properties"]} for ft in in_tile]
                    raw = mvt_encode(
                        {"name": args.layer, "features": layer_feats},
                        default_options={"quantize_bounds": (wb, sb, eb, nb),
                                         "extents": EXTENTS},
                    )
                    w.write_tile(zxy_to_tileid(z, x, y), gzip.compress(raw, mtime=0))
                    tiles_written += 1
        cx, cy = (glo[0] + glo[2]) / 2, (glo[1] + glo[3]) / 2
        header = {
            "tile_type": TileType.MVT,
            "tile_compression": Compression.GZIP,
            "min_zoom": args.min_zoom,
            "max_zoom": args.max_zoom,
            "min_lon_e7": int(glo[0] * 1e7),
            "min_lat_e7": int(glo[1] * 1e7),
            "max_lon_e7": int(glo[2] * 1e7),
            "max_lat_e7": int(glo[3] * 1e7),
            "center_lon_e7": int(cx * 1e7),
            "center_lat_e7": int(cy * 1e7),
            "center_zoom": args.min_zoom,
        }
        metadata = {"name": args.layer, "format": "pbf",
                    "minzoom": args.min_zoom, "maxzoom": args.max_zoom,
                    "bounds": f"{glo[0]},{glo[1]},{glo[2]},{glo[3]}",
                    "center": f"{cx},{cy},{args.min_zoom}",
                    "vector_layers": [{"id": "petak", "fields": {
                        "n": "String", "e": "String",
                        "kategori": "String", "warna": "String"}}]}
        w.finalize(header, metadata)

    print(json.dumps({"ok": True, "features": len(feats), "tiles": tiles_written,
                      "out": str(out), "bytes": out.stat().st_size}))


if __name__ == "__main__":
    main()
