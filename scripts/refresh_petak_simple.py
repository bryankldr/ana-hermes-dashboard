#!/usr/bin/env python3
"""Generate harian petak_simple.json {meta, features} dari kph_bwb_sandbox2.

Cadangan evaluasi hari ini — bukan sumber Business Map (map.js tetap DB 100% via 7 _map).
ANNA pakai cadangan + meta untuk YOY dengan identitas periode jelas.
Toleran: spatial_intel baca wrapper baru maupun array lama [{n,p}].

Jalankan: python3 scripts/refresh_petak_simple.py [--dry-run]
Cron harian: 0 6 * * * cd /home/bryan/ana-hermes-dashboard && python3 scripts/refresh_petak_simple.py >> logs/refresh_petak.log 2>&1
"""
import json, sys, pathlib, datetime, calendar
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "ui" / "data" / "petak_simple.json"
SNAP_DIR = ROOT / "ui" / "data" / "snapshots"
PERIODE_DIR = SNAP_DIR / "periode"
DAILY_DIR = SNAP_DIR / "daily"
MANIFEST = SNAP_DIR / "manifest.json"
WIB = ZoneInfo("Asia/Jakarta")

def load_env():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v=line.split("=",1)
            env[k.strip()] = v.strip()
    return env

def db_conn(env, retries=2):
    import pymysql, time
    last = None
    for i in range(retries+1):
        try:
            return pymysql.connect(
                host=env.get("DB_HOST","127.0.0.1"),
                port=int(env.get("DB_PORT","3306")),
                user=env.get("DB_USER","root"),
                password=env.get("DB_PASSWORD",""),
                database=env.get("DB_NAME","kph_bwb_sandbox2"),
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=8,
            )
        except Exception as e:
            last = e
            if i < retries:
                time.sleep(1.5*(i+1))
                continue
            raise last

def fetch_rows(conn):
    sql = """
    SELECT
      pp.kode_evapot AS n,
      pp.polygon AS polygon_json,
      gp.tahun_rtt, gp.nomor_petak, gp.kode_divre, gp.kode_kph, gp.kode_bkph, gp.kode_rph, gp.kode_tpg,
      gp.luas_baku, gp.target_rkap,
      pp.petak AS petak_no, pp.luas_ha AS pp_luas_ha
    FROM petak_polygon pp
    LEFT JOIN getah_petak gp ON gp.kode_evapot = pp.kode_evapot
      AND gp.tahun_rtt = (SELECT MAX(g2.tahun_rtt) FROM getah_petak g2 WHERE g2.kode_evapot = pp.kode_evapot)
    WHERE pp.polygon IS NOT NULL AND pp.polygon != ''
    ORDER BY pp.kode_evapot
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM petak_polygon WHERE polygon IS NOT NULL AND polygon!=''")
        with_polygon = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(DISTINCT tahun_rtt) AS c, GROUP_CONCAT(DISTINCT tahun_rtt) AS s FROM getah_petak")
        r = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS c FROM getah_petak WHERE tahun_rtt=2026")
        rtt2026 = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM getah_petak WHERE tahun_rtt=2025")
        rtt2025 = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM getah_petak gp JOIN petak_polygon pp ON pp.kode_evapot=gp.kode_evapot WHERE gp.tahun_rtt=2026 AND pp.polygon IS NOT NULL")
        join2026 = cur.fetchone()["c"]
    return rows, dict(with_polygon=with_polygon, distinct_tahun=r["c"], tahun_list=r["s"], rtt2026=rtt2026, rtt2025=rtt2025, join2026=join2026)

def build(now_wib, rows, counts):
    periode = 1 if now_wib.day <= 15 else 2
    periode_label = f"{now_wib.year}-{now_wib.month:02d}-P{periode}"
    tahun_rtt = 2026 if counts["rtt2026"] else (2025 if counts["rtt2025"] else now_wib.year)
    # dedupe: petak_polygon ada 4-5 kode_evapot duplikat (1003 rows -> 999 distinct). Keep polygon terpanjang (geometry paling lengkap).
    seen = {}
    for r in rows:
        k = str(r["n"])
        cur_len = len(r.get("polygon_json") or "")
        prev = seen.get(k)
        if prev is None or cur_len > len(prev.get("polygon_json") or ""):
            seen[k] = r
    rows = list(seen.values())
    deduped = len(rows)
    # rows sudah deduped; counts.with_polygon masih raw (1003) untuk referensi
    features = []
    for r in rows:
        n = r["n"]
        pj = r["polygon_json"]
        try:
            gj = json.loads(pj) if isinstance(pj, str) else pj
            typ = gj.get("type") if isinstance(gj, dict) else None
            coords = gj.get("coordinates") if isinstance(gj, dict) else None
            if typ == "MultiPolygon" and coords:
                # flatten polygons -> rings list [[[lon,lat],...], ...]
                p = [ring for poly in coords for ring in poly]
            else:
                p = coords if coords else []
        except Exception:
            p = []
        if not p:
            continue
        feat = {"n": str(n), "p": p}
        for k in ("tahun_rtt","nomor_petak","kode_divre","kode_kph","kode_bkph","kode_rph","kode_tpg","luas_baku","target_rkap"):
            v = r.get(k)
            if v is not None:
                if k in ("luas_baku","target_rkap"):
                    feat[k] = float(v)
                elif k.startswith("kode_") and str(v).lstrip("-").isdigit():
                    # kode_tpg bisa bigint, keep int
                    try: feat[k] = int(v)
                    except: feat[k] = v
                else:
                    feat[k] = v
        if "tahun_rtt" in feat and isinstance(feat["tahun_rtt"], float):
            feat["tahun_rtt"] = int(feat["tahun_rtt"])
        features.append(feat)
    orphan = sum(1 for f in features if f.get("tahun_rtt") is None)
    meta = {
        "generated_at": now_wib.isoformat(),
        "source": "kph_bwb_sandbox2",
        "source_db": "kph_bwb_sandbox2",
        "tahun_rtt": tahun_rtt,
        "periode": periode_label,
        "counts": {
            "total": len(features),
            "deduped": deduped,
            "raw_polygon_rows": counts["with_polygon"],
            "with_polygon": len(features),
            "distinct_evapot": deduped,
            "rtt_2026": counts["rtt2026"],
            "rtt_2025": counts["rtt2025"],
            "join_2026_polygon": counts["join2026"],
            "orphan_no_rtt": orphan,
        },
        "generator": "scripts/refresh_petak_simple.py",
        "version": 2,
    }
    return {"meta": meta, "features": features}

def _hash_out(out: dict) -> str:
    import hashlib
    # hash stabil dari counts + len features (cukup cepat, bukan full polygon hash)
    h = hashlib.sha256()
    h.update(json.dumps(out["meta"], sort_keys=True).encode())
    h.update(str(len(out["features"])).encode())
    # sample 3 polygon head untuk detect perubahan geometri tanpa hash 1.7M penuh
    for f in out["features"][:3]:
        h.update(str(f.get("n","")).encode())
        try:
            h.update(str(len(f.get("p") or [])).encode())
        except: pass
    return h.hexdigest()[:16]

def _update_manifest(now_wib, out, periode_label, hash16):
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    PERIODE_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if MANIFEST.exists():
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except: manifest = {}
    if "periods" not in manifest: manifest["periods"] = {}
    if "_meta" not in manifest: manifest["_meta"] = {}
    # finalize periode lama yang sudah lewat
    for k, v in list(manifest["periods"].items()):
        try:
            if k < periode_label:
                v["finalized"] = True
        except: pass
    entry = manifest["periods"].get(periode_label) or {}
    # jangan overwrite finalized lama yang bukan periode sekarang (immutable)
    # tapi untuk periode sekarang boleh update
    entry.update({
        "file": f"periode/petak_{periode_label}.json",
        "generated_at": out["meta"]["generated_at"],
        "hash": hash16,
        "counts": out["meta"]["counts"],
        "tahun_rtt": out["meta"]["tahun_rtt"],
        "periode": periode_label,
        "finalized": False,
        "size": 0,  # diisi setelah tulis
    })
    manifest["periods"][periode_label] = entry
    manifest["_meta"].update({"updated_at": now_wib.isoformat(), "version": 3, "retention": {"daily_days": 7, "periode_months": 24}})
    return manifest

def main():
    dry = "--dry-run" in sys.argv
    env = load_env()
    now_wib = datetime.datetime.now(WIB)
    print(f"[refresh] {now_wib.isoformat()} WIB dry={dry}")
    try:
        conn = db_conn(env)
    except Exception as e:
        print(f"[refresh] DB connect failed: {e}", file=sys.stderr)
        sys.exit(2)
    try:
        rows, counts = fetch_rows(conn)
        print(f"[refresh] polygon={counts['with_polygon']} rtt2026={counts['rtt2026']} rtt2025={counts['rtt2025']} join2026={counts['join2026']} fetched={len(rows)}")
        out = build(now_wib, rows, counts)
        print(f"[refresh] features={len(out['features'])} meta={out['meta']}")
        if dry:
            print(json.dumps(out["meta"], indent=2))
            return
        # --- Tier2 COLD: daily (7d) + periode (24 bulan) + manifest ---
        # daily rolling 7 hari
        DAILY_DIR.mkdir(parents=True, exist_ok=True)
        PERIODE_DIR.mkdir(parents=True, exist_ok=True)
        daily = DAILY_DIR / f"petak_{now_wib.date().isoformat()}.json"
        daily.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(f"[refresh] daily -> {daily} ({daily.stat().st_size} bytes)")
        # periode kanonik 1 file per P1/P2 (overwrite dalam jendela periode, freeze setelah lewat)
        periode_label = out["meta"]["periode"]
        periode_file = PERIODE_DIR / f"petak_{periode_label}.json"
        # cek finalized: bila periode ini sudah finalized (periode lama) jangan overwrite
        should_write_periode = True
        if MANIFEST.exists():
            try:
                mf = json.loads(MANIFEST.read_text(encoding="utf-8"))
                ent = (mf.get("periods") or {}).get(periode_label)
                if ent and ent.get("finalized") and ent.get("hash") == _hash_out(out):
                    # identik, skip tulis
                    should_write_periode = False
            except: pass
        if should_write_periode:
            periode_file.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            print(f"[refresh] periode -> {periode_file} ({periode_file.stat().st_size} bytes)")
        else:
            print(f"[refresh] periode {periode_label} finalized identik — skip")
        # manifest
        h16 = _hash_out(out)
        manifest = _update_manifest(now_wib, out, periode_label, h16)
        # isi size periode
        try:
            if periode_file.exists():
                manifest["periods"][periode_label]["size"] = periode_file.stat().st_size
        except: pass
        MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[refresh] manifest -> {MANIFEST} periods={len(manifest['periods'])}")
        # migrate legacy flat snapshots/petak_YYYY-MM-DD.json -> keep compat tapi jangan duplikat
        # (spatial_intel sudah fallback scan flat, jadi legacy tetap kebaca)
        # prune daily >7 hari
        try:
            import time as _tm
            cutoff_d = _tm.time() - 7*86400
            pruned_d = 0
            for f in DAILY_DIR.glob("petak_*.json"):
                try:
                    if f.stat().st_mtime < cutoff_d:
                        f.unlink(); pruned_d+=1
                except: pass
            if pruned_d: print(f"[refresh] pruned {pruned_d} daily (>7d)")
        except Exception as e:
            print(f"[refresh] prune daily warn: {e}")
        # prune periode >24 bulan (48 file)
        try:
            cutoff_p = _tm.time() - 730*86400
            pruned_p = 0
            for f in PERIODE_DIR.glob("petak_*.json"):
                try:
                    if f.stat().st_mtime < cutoff_p:
                        f.unlink(); pruned_p+=1
                except: pass
            # juga prune manifest entries yang file nya sudah hilang
            if pruned_p:
                print(f"[refresh] pruned {pruned_p} periode (>24mo)")
        except Exception as e:
            print(f"[refresh] prune periode warn: {e}")
        # prune legacy flat >30d (transisi)
        try:
            cutoff_legacy = _tm.time() - 30*86400
            for f in SNAP_DIR.glob("petak_*.json"):
                try:
                    if f.stat().st_mtime < cutoff_legacy:
                        f.unlink()
                except: pass
        except: pass
        tmp = DATA.with_suffix(".tmp")
        tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        tmp.replace(DATA)
        print(f"[refresh] live -> {DATA} ({DATA.stat().st_size} bytes)")
    finally:
        try: conn.close()
        except: pass

if __name__ == "__main__":
    main()
