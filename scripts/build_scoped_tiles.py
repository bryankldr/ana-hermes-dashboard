#!/usr/bin/env python3
"""Build tileset ter-scope jabatan: per-KPH petak + per-DIVRE bounds + manifest.

Data-driven: loop DISTINCT kode_kph/divre dari DB — KPH/divre baru otomatis
dapat file di build berikut tanpa ubah kode. Idempoten, per-file best-effort
(gagal satu ≠ gagal semua). Dipanggil cron harian / /api/tiles/rebuild.

Jalankan: python3 scripts/build_scoped_tiles.py [--tahun 2026]
Hasil: tiles/kph_<kode>.pmtiles, tiles/bounds_<divre>.pmtiles, tiles/manifest.json
"""
import argparse
import datetime
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def _sh(args, timeout=300):
    try:
        r = subprocess.run([sys.executable] + args, cwd=str(ROOT),
                           capture_output=True, text=True, timeout=timeout)
        tail = (r.stdout.strip().splitlines() or [""])[-1]
        try:
            return {"ok": r.returncode == 0, "detail": json.loads(tail)}
        except Exception:
            return {"ok": r.returncode == 0, "tail": (r.stdout + r.stderr)[-300:]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:200]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tahun", type=int, default=2026)
    args = ap.parse_args()
    out = {"ok": True, "tahun": args.tahun, "kph": [], "bounds": [], "errors": []}
    try:
        import pymysql
        import db_source
        kw = db_source.kwargs()
        conn = pymysql.connect(host=kw["host"], port=kw["port"], user=kw["user"],
                               password=kw["password"], database=kw["database"],
                               connect_timeout=8)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT kode_kph FROM petak_polygon WHERE kode_kph IS NOT NULL ORDER BY kode_kph")
                kph_list = [str(r[0]) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"DB tak terjangkau: {e}"[:200]}))
        raise SystemExit(1)
    for kode in kph_list:
        exp = _sh(["scripts/export_petak.py", "--tahun", str(args.tahun),
                   "--kode-kph", kode, "--out", f"tiles/kph_{kode}.ndjson"])
        if not exp.get("ok"):
            out["errors"].append({"kph": kode, "tahap": "export", **exp})
            continue
        bld = _sh(["scripts/build_pmtiles.py", "--in", f"tiles/kph_{kode}.ndjson",
                   "--out", f"tiles/kph_{kode}.pmtiles"])
        rec = {"kode": kode, "export": exp.get("detail"), "build": bld.get("detail") or bld}
        if not bld.get("ok"):
            out["errors"].append({"kph": kode, "tahap": "build", **bld})
        out["kph"].append(rec)
    bexp = _sh(["scripts/export_kph_bounds.py", "--tahun", str(args.tahun)])
    out["bounds_export"] = bexp.get("detail") or bexp
    if bexp.get("ok"):
        for f in sorted((ROOT / "tiles").glob("bounds_*.ndjson")):
            divre = f.stem.split("_", 1)[1]
            bld = _sh(["scripts/build_pmtiles.py", "--in", f"tiles/{f.name}",
                       "--out", f"tiles/bounds_{divre}.pmtiles",
                       "--layer", "kph", "--min-zoom", "4", "--max-zoom", "10"])
            out["bounds"].append({"divre": divre, "build": bld.get("detail") or bld})
            if not bld.get("ok"):
                out["errors"].append({"divre": divre, "tahap": "build", **bld})
    else:
        out["errors"].append({"tahap": "bounds_export", **bexp})
    oexp = _sh(["scripts/export_kph_overview.py", "--tahun", str(args.tahun)])
    out["overview_export"] = oexp.get("detail") or oexp
    if oexp.get("ok"):
        import glob as _glob
        for _nd in sorted(_glob.glob(str(ROOT / "tiles" / "overview_*.ndjson"))):
            _name = pathlib.Path(_nd).stem  # overview_<divre>
            bld = _sh(["scripts/build_pmtiles.py", "--in", f"tiles/{_name}.ndjson",
                       "--out", f"tiles/{_name}.pmtiles",
                       "--layer", "petak", "--min-zoom", "4", "--max-zoom", "10"])
            out.setdefault("overview", []).append({"file": _name, "build": bld.get("detail") or bld})
            if not bld.get("ok"):
                out["errors"].append({"file": _name, "tahap": "build", **bld})
    else:
        out["errors"].append({"tahap": "overview_export", **oexp})
    # manifest (sumber kebenaran inventory untuk klien + status)
    try:
        files = []
        for f in sorted((ROOT / "tiles").glob("*.pmtiles")):
            scope = None
            if f.stem.startswith("kph_"):
                scope = {"level": "kph", "kode": f.stem[4:]}
            elif f.stem.startswith("bounds_"):
                scope = {"level": "divre", "kode": f.stem[7:]}
            elif f.stem.startswith("overview_"):
                scope = {"level": "divre", "kode": f.stem[9:], "kind": "overview"}
            elif f.stem == "petak":
                scope = {"level": "legacy"}
            files.append({"name": f.name, "scope": scope,
                          "bytes": f.stat().st_size, "mtime": f.stat().st_mtime})
        (ROOT / "tiles" / "manifest.json").write_text(json.dumps(
            {"built_at": datetime.datetime.now().isoformat(timespec="seconds"),
             "tahun": args.tahun, "files": files}, indent=1), encoding="utf-8")
        out["manifest"] = {"files": len(files)}
    except Exception as e:  # noqa: BLE001
        out["errors"].append({"tahap": "manifest", "error": str(e)[:200]})
    out["ok"] = not out["errors"]
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
