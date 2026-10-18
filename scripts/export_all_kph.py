#!/usr/bin/env python3
"""Export semua KPH sebagai PMTiles terpisah untuk skalabilitas DIREKSI/ADMINISTRATOR.

Reuse export_petak.py dan build_pmtiles.py via subprocess untuk menghindari duplikasi kode.
Pipeline: export_petak.py (per KPH) → build_pmtiles.py (per KPH)

Jalankan: python3 scripts/export_all_kph.py [--tahun 2026]
Manual rebuild untuk KPH tertentu: python3 scripts/export_petak.py --kode-kph GLENMORE
"""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

def fetch_all_kph(tahun):
    """Fetch semua kode_kph dari database."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from export_petak import load_env, db_conn
    
    env = load_env()
    conn = db_conn(env)
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT kode_kph FROM getah_petak WHERE tahun_rtt = %s AND kode_kph IS NOT NULL AND kode_kph != ''",
                (tahun,)
            )
            rows = cur.fetchall()
            
            kph_list = []
            for row in rows:
                # Cursor returns dict (from export_petak.py config)
                if isinstance(row, dict):
                    val = row.get('kode_kph')
                elif isinstance(row, (tuple, list)):
                    val = row[0] if len(row) > 0 else None
                else:
                    val = str(row) if row else None
                if val:
                    kph_list.append(val)
        return kph_list
    finally:
        conn.close()

def export_single_kph(kode_kph, tahun):
    """Export dan build PMTiles untuk satu KPH."""
    # Ensure kode_kph is string (not dict from JSON parse)
    if isinstance(kode_kph, dict):
        kode_kph = kode_kph.get('kode_kph') if 'kode_kph' in kode_kph else kode_kph.get('value', str(kode_kph))
    kode_kph = str(kode_kph).strip()
    
    if not kode_kph:
        print(f"Skipping invalid KPH: {kode_kph}")
        return False
    
    # Determine python binary (.venv for build_pmtiles dependency)
    pybin = sys.executable
    venv_py = ROOT / ".venv" / "bin" / "python"
    if venv_py.exists():
        pybin = str(venv_py)
    
    # Export NDJSON using subprocess to reuse existing scripts
    script_path = str(ROOT / "scripts" / "export_petak.py")
    cmd = [pybin, script_path, "--tahun", str(tahun), "--kode-kph", kode_kph, "--out", f"tiles/kph_{kode_kph}.ndjson"]
    
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        print(f"ERROR export_petak.py for KPH {kode_kph}: {result.stderr}")
        return False
    
    # Build PMTiles
    build_script = str(ROOT / "scripts" / "build_pmtiles.py")
    build_cmd = [pybin, build_script, "--in", f"tiles/kph_{kode_kph}.ndjson", "--out", f"tiles/kph_{kode_kph}.pmtiles"]
    
    result = subprocess.run(build_cmd, capture_output=True, text=True, cwd=ROOT)
    if result.returncode != 0:
        print(f"ERROR build_pmtiles.py for KPH {kode_kph}: {result.stderr}")
        return False
    
    # Cleanup NDJSON file (intermediate, tidak diperlukan setelah PMTiles dibuat)
    # Cleanup semua varian NDJSON untuk KPH ini (dengan/without tahun suffix)
    ndjson_path = ROOT / "tiles" / f"kph_{kode_kph}.ndjson"
    ndjson_path_tahun = ROOT / "tiles" / f"kph_{kode_kph}_{tahun}.ndjson"
    try:
        if ndjson_path.exists():
            ndjson_path.unlink()
        if ndjson_path_tahun.exists():
            ndjson_path_tahun.unlink()
    except Exception as e:
        print(f"WARNING: cleanup NDJSON failed for KPH {kode_kph}: {e}")
    
    return True

def main():
    import datetime
    current_year = datetime.date.today().year
    
    ap = argparse.ArgumentParser(description="Export semua KPH sebagai PMTiles terpisah")
    ap.add_argument("--tahun", type=int, default=current_year, help=f"Tahun data (default: {current_year} - tahun berjalan)")
    args = ap.parse_args()
    
    print(f"Memulai export semua KPH untuk tahun {args.tahun}...")
    
    # Fetch semua KPH
    kph_list = fetch_all_kph(args.tahun)
    
    if not kph_list:
        print("Tidak ada KPH ditemukan di database.")
        return
    
    print(f"Ditemukan {len(kph_list)} KPH untuk diexport.")
    
    # Export per KPH
    success_count = 0
    failed_kph = []
    
    for kode_kph in kph_list:
        print(f"  Memproses KPH {kode_kph}...", end=" ")
        if export_single_kph(kode_kph, args.tahun):
            print("✓")
            success_count += 1
        else:
            print("✗")
            failed_kph.append(kode_kph)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Export selesai: {success_count}/{len(kph_list)} KPH berhasil")
    if failed_kph:
        print(f"KPH gagal: {', '.join(str(k) for k in failed_kph)}")
    print(f"{'='*60}")
    
    # Output JSON untuk logging
    print(json.dumps({
        "ok": True,
        "total": len(kph_list),
        "success": success_count,
        "failed": len(failed_kph),
        "failed_kph": failed_kph
    }))

if __name__ == "__main__":
    main()
