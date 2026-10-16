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


def _tahun_list(args):
    # Tahun RTT yang ada datanya (bila --tahun diberi, hanya itu).
    if args.tahun:
        return [args.tahun]
    try:
        import pymysql
        import db_source
        kw = db_source.kwargs()
        conn = pymysql.connect(host=kw["host"], port=kw["port"], user=kw["user"],
                               password=kw["password"], database=kw["database"],
                               connect_timeout=8)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT tahun_rtt FROM getah_petak WHERE tahun_rtt IS NOT NULL ORDER BY tahun_rtt")
                return [int(r[0]) for r in cur.fetchall()]
        finally:
            conn.close()
    except Exception:
        return [2026]


def _kph_list():
    import pymysql
    import db_source
    kw = db_source.kwargs()
    conn = pymysql.connect(host=kw["host"], port=kw["port"], user=kw["user"],
                           password=kw["password"], database=kw["database"],
                           connect_timeout=8)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT kode_kph FROM petak_polygon WHERE kode_kph IS NOT NULL ORDER BY kode_kph")
            return [str(r[0]) for r in cur.fetchall()]
    finally:
        conn.close()


def _build_tahun(tahun, out):
    # Nama file bertahun (klien pilih by filter tahun): kph_<kode>_<thn>.
    try:
        kph_list = _kph_list()
    except Exception as e:  # noqa: BLE001
        out["errors"].append({"tahun": tahun, "error": f"DB tak terjangkau: {e}"[:200]})
        return
    for kode in kph_list:
        exp = _sh(["scripts/export_petak.py", "--tahun", str(tahun),
                   "--kode-kph", kode, "--out", f"tiles/kph_{kode}_{tahun}.ndjson"])
        if not exp.get("ok"):
            out["errors"].append({"tahun": tahun, "kph": kode, "tahap": "export", **exp})
            continue
        bld = _sh(["scripts/build_pmtiles.py", "--in", f"tiles/kph_{kode}_{tahun}.ndjson",
                   "--out", f"tiles/kph_{kode}_{tahun}.pmtiles"])
        rec = {"tahun": tahun, "kode": kode, "export": exp.get("detail"), "build": bld.get("detail") or bld}
        if not bld.get("ok"):
            out["errors"].append({"tahun": tahun, "kph": kode, "tahap": "build", **bld})
        out["kph"].append(rec)
    bexp = _sh(["scripts/export_kph_bounds.py", "--tahun", str(tahun)])
    out.setdefault("bounds_export", []).append(bexp.get("detail") or bexp)
    if bexp.get("ok"):
        for f in sorted((ROOT / "tiles").glob(f"bounds_*_{tahun}.ndjson")):
            divre = f.stem.split("_", 1)[1].rsplit("_", 1)[0]
            bld = _sh(["scripts/build_pmtiles.py", "--in", f"tiles/{f.name}",
                       "--out", f"tiles/bounds_{divre}_{tahun}.pmtiles",
                       "--layer", "kph", "--min-zoom", "4", "--max-zoom", "10"])
            out.setdefault("bounds", []).append({"tahun": tahun, "divre": divre, "build": bld.get("detail") or bld})
            if not bld.get("ok"):
                out["errors"].append({"tahun": tahun, "divre": divre, "tahap": "build", **bld})
    else:
        out["errors"].append({"tahun": tahun, "tahap": "bounds_export", **bexp})
    oexp = _sh(["scripts/export_kph_overview.py", "--tahun", str(tahun)])
    out.setdefault("overview_export", []).append(oexp.get("detail") or oexp)
    if oexp.get("ok"):
        import glob as _glob
        for _nd in sorted(_glob.glob(str(ROOT / "tiles" / f"overview_*_{tahun}.ndjson"))):
            _base = pathlib.Path(_nd).stem  # overview_<divre>_<tahun>
            _div = _base.split("_", 1)[1].rsplit("_", 1)[0]
            bld = _sh(["scripts/build_pmtiles.py", "--in", f"tiles/{_base}.ndjson",
                       "--out", f"tiles/overview_{_div}_{tahun}.pmtiles",
                       "--layer", "petak", "--min-zoom", "4", "--max-zoom", "10"])
            out.setdefault("overview", []).append({"tahun": tahun, "file": _base, "build": bld.get("detail") or bld})
            if not bld.get("ok"):
                out["errors"].append({"tahun": tahun, "file": _base, "tahap": "build", **bld})
    else:
        out["errors"].append({"tahun": tahun, "tahap": "overview_export", **oexp})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tahun", type=int, default=0,
                    help="bangun satu tahun saja; default semua tahun RTT di DB")
    args = ap.parse_args()
    out = {"ok": True, "tahun": args.tahun or "semua", "kph": [], "bounds": [], "errors": []}
    try:
        for _th in _tahun_list(args):
            _build_tahun(_th, out)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"DB tak terjangkau: {e}"[:200]}))
        raise SystemExit(1)
    # manifest (sumber kebenaran inventory untuk klien + status).
    # Nama bertahun: kph_<kode>_<thn>, bounds_<divre>_<thn>, overview_<divre>_<thn>.
    # Varian lama tanpa tahun (kph_<kode> dsb) tetap dibaca untuk kompat mundur.
    # Berkas scoped basi tanpa tahun dibersihkan (diganti varian bertahun);
    # petak.* legacy milik rantai lama — jangan sentuh.
    try:
        import re as _re
        for _stale in sorted((ROOT / "tiles").glob("*.pmtiles")):
            if _re.fullmatch(r"(kph_\d+|bounds_\d+|overview_\d+)\.pmtiles", _stale.name):
                try:
                    _stale.unlink()
                except OSError:
                    pass
        for _stale in sorted((ROOT / "tiles").glob("*.ndjson")):
            if _re.fullmatch(r"(kph_\d+|bounds_\d+|overview_\d+)\.ndjson", _stale.name):
                try:
                    _stale.unlink()
                except OSError:
                    pass
        files = []
        for f in sorted((ROOT / "tiles").glob("*.pmtiles")):
            scope = None
            _m = _re.fullmatch(r"kph_(\d+)_(\d{4})", f.stem)
            if _m:
                scope = {"level": "kph", "kode": _m.group(1), "tahun": int(_m.group(2))}
            else:
                _m = _re.fullmatch(r"bounds_(\d+)_(\d{4})", f.stem)
                if _m:
                    scope = {"level": "divre", "kode": _m.group(1), "tahun": int(_m.group(2))}
                else:
                    _m = _re.fullmatch(r"overview_(\d+)_(\d{4})", f.stem)
                    if _m:
                        scope = {"level": "divre", "kode": _m.group(1),
                                 "tahun": int(_m.group(2)), "kind": "overview"}
                    elif f.stem.startswith("kph_"):
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
