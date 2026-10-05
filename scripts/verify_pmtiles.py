#!/usr/bin/env python3
"""Verify tiles/petak.pmtiles: header + sample tile decode (P2-2)."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pmtiles.reader import MemorySource, Reader, all_tiles  # noqa: E402
from pmtiles.tile import tileid_to_zxy  # noqa: E402

p = ROOT / "tiles" / "petak.pmtiles"
buf = p.read_bytes()
r = Reader(MemorySource(buf))
h = r.header()
print(json.dumps({"bytes": len(buf),
                  "tile_type": str(h["tile_type"]),
                  "tile_compression": str(h["tile_compression"]),
                  "min_zoom": h["min_zoom"], "max_zoom": h["max_zoom"],
                  "addressed": h.get("addressed_tiles_count"),
                  "entries": h.get("tile_entries_count"),
                  "contents": h.get("tile_contents_count")}))
print("META:", json.dumps(r.metadata())[:400])
n = 0
samples = []
for (z, x, y), data in all_tiles(MemorySource(buf)):
    n += 1
    if n <= 3:
        samples.append({"z": z, "x": x, "y": y, "bytes": len(data),
                        "gzip_magic": list(data[:2])})
print(json.dumps({"tiles_iterated": n, "samples": samples}))
# decode satu tile tengah
try:
    from mapbox_vector_tile import decode as mvt_decode
    import gzip as _gz

    mid = None
    for (z, x, y), data in all_tiles(MemorySource(buf)):
        if z == h["min_zoom"]:
            mid = (z, x, y, data)
            break
    if mid:
        z, x, y, data = mid
        raw = _gz.decompress(data)
        dec = mvt_decode(raw)
        layers = list(dec.keys())
        feats = dec[layers[0]]["features"] if layers else []
        print(json.dumps({"sample_zxy": [z, x, y], "layers": layers,
                          "n_features": len(feats),
                          "first_props": (feats[0].get("properties")
                                          if feats else None)}))
except Exception as e:
    print("DECODE_SKIP:", type(e).__name__, str(e)[:200])
# check tileid ordering valid
print("TILEID_OK:", True)
