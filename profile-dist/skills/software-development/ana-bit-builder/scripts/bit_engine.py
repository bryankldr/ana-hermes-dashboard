"""
bit_engine.py — BIT deterministic engine (v0.1 Target Gap).

1 engine reuse Business Data Engine (simoge_db), 0 LLM.
Panel (/api/bit/target_gap) dan ANNA (ana_bit_tool) panggil fungsi sama — angka identik.
Cache key = scope+periode+rule_version, TTL 300s.
"""
import time, hashlib, json

_RULE_VERSION = "bit-v0.6:robust + tren+distribusi+anomali+sensitivitas+stratified + kasus+rekomendasi"
_CACHE = {}
_TTL = 300

def _wilayah_where(scope, alias, sdb):
    """Wilayah filter global-aware: support kode_tpg_list (user TPG-level) via IN.
    Reuse sdb._wilayah_where untuk kode_divre/kph/bkph/rph/tpg single, tambah IN untuk list.
    Robust: digits-only, paramised. Tanpa list = perilaku lama."""
    base_sql, base_vals = sdb._wilayah_where({k: v for k, v in (scope or {}).items() if k != "kode_tpg_list"}, alias)
    tpg_list = (scope or {}).get("kode_tpg_list")
    if tpg_list and isinstance(tpg_list, (list, tuple)):
        clean = [str(x).strip() for x in tpg_list if str(x).strip() and str(x).strip().isdigit()]
        if clean:
            placeholders = ",".join(["%s"] * len(clean))
            base_sql += f" AND {alias}.kode_tpg IN ({placeholders})"
            base_vals = list(base_vals) + [int(x) for x in clean]
            return base_sql, base_vals
    return base_sql, base_vals


def _cache_key(tahun, bulan, periode, scope, sampai_dengan: str = "ya", include_breakdown=False):
    raw = json.dumps([tahun, bulan, periode, sorted((scope or {}).items()), sampai_dengan, bool(include_breakdown), _RULE_VERSION], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def get_target_gap(tahun: int, bulan: int, periode: int, scope: dict | None = None, sampai_dengan: str = "ya", include_breakdown: bool = False):
    """
    Target vs Rencana vs Actual deterministik.
    scope = _wilayah_scope_from_session (kode_divre/kph/bkph/rph/tpg_list) — allowlist.
    Return {kpi, evidence, limitations, sources, meta}.
    """
    import pathlib, sys
    scope = dict(scope or {})
    # resolve simoge_db lazily — robust across hermes agent vs server env
    import importlib, os
    candidates = []
    # 1) explicit ANA_SIMOGE_SCRIPTS
    if os.environ.get("ANA_SIMOGE_SCRIPTS"):
        candidates.append(os.environ["ANA_SIMOGE_SCRIPTS"])
    # 2) relative to this file (server/standalone)
    ROOT = pathlib.Path(__file__).resolve().parent
    candidates.append(str(ROOT / "profile-dist" / "skills" / "software-development" / "simoge-business" / "scripts"))
    candidates.append(str(ROOT / "profile-dist" / "skills" / "software-development" / "simoge-business" / "scripts"))
    # 3) hermes profile — handle HERMES_HOME already being profile dir
    hhome = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    # if HERMES_HOME ends with profiles/xxx, strip to real home
    if "/profiles/" in hhome:
        hhome = hhome.split("/profiles/")[0]
    prof = os.environ.get("HERMES_PROFILE", os.environ.get("ANA_PROFILE", "anna")).strip() or "anna"
    candidates.append(os.path.join(hhome, "profiles", prof, "skills/software-development/simoge-business/scripts"))
    # also try absolute ana profile
    candidates.append(os.path.expanduser("~/.hermes/profiles/anna/skills/software-development/simoge-business/scripts"))
    sdb = None
    for cand in candidates:
        if not cand: continue
        if cand not in sys.path:
            sys.path.insert(0, cand)
        try:
            sdb = importlib.import_module("simoge_db")
            break
        except ModuleNotFoundError:
            continue
    if sdb is None:
        sdb = importlib.import_module("simoge_db")

    # normalize sampai_dengan: ya/tidak, default ya (kumulatif Jan..cutoff)
    sampai_dengan = str(sampai_dengan or "ya").strip().lower()
    if sampai_dengan not in ("ya","tidak","y","t","yes","n","no"):
        sampai_dengan = "ya"
    if sampai_dengan in ("y","yes","t","1"): sampai_dengan = "ya"
    if sampai_dengan in ("n","no","0"): sampai_dengan = "tidak"
    is_kumulatif = (sampai_dengan == "ya")

    ck = _cache_key(tahun, bulan, periode, scope, sampai_dengan, include_breakdown)
    hit = _CACHE.get(ck)
    if hit and (time.monotonic() - hit[0]) < _TTL:
        out = dict(hit[1]); out["cached"] = True; return out

    # periode bounds + pct sesuai sampai_dengan (business rule canonical)
    # Ya = kumulatif Jan 1 .. akhir periode (Penuh=Jan..Feb akhir, P1=Jan..15 Feb, P2=Jan..28 Feb)
    # Tidak = periode saja (Penuh=1..akhir bulan Feb saja, P1=1..15 Feb saja)
    kw = {"sampai_dengan": sampai_dengan}
    d0, d1 = sdb._range_bounds(tahun, bulan, periode, kw, default_kumulatif=True)
    pct = sdb._target_pct_sd(tahun, bulan, periode, kw, default_kumulatif=True)

    # wilayah where for petak & rencana/penerimaan — reuse _wilayah_where (ikut sampai_dengan scope not needed here, w_* from scope only)
    # target_rkap total (for expected) — via petak
    w_petak, wv_petak = _wilayah_where(scope, "p", sdb)
    w_r, wv_r = _wilayah_where(scope, "r", sdb)
    w_prod, wv_prod = _wilayah_where(scope, "p", sdb)

    # total target_rkap (DISTINCT petak in scope)
    r_target = sdb.q(f"SELECT COALESCE(SUM(p.target_rkap),0) AS s FROM getah_petak p WHERE p.tahun_rtt=%s{w_petak}", (tahun, *wv_petak))
    total_rkap = float((r_target["rows"][0]["s"] if r_target["rows"] else 0) or 0)
    target_expected = round(total_rkap * pct / 100, 1)
    target_total = round(total_rkap, 1)

    # rencana & actual — main (Ya=YTD, Tidak=periode) + YTD reference always
    d0y, dlast = sdb._range_bounds(tahun, bulan, periode, {"sampai_dengan":"ya"}, default_kumulatif=True)
    # periode murni for reference (selalu 1..15 / 16..akhir / 1..akhir)
    d0p, d1p = sdb.period_bounds(tahun, bulan, periode)
    # main queries respect sampai_dengan (Ya=Jan..cutoff, Tidak=periode saja)
    r_rencana = sdb.q(f"SELECT COUNT(*) AS n_rencana, ROUND(COALESCE(SUM(r.rencana_berat),0),1) AS rencana_kg FROM getah_rencana_aktivitas r WHERE r.tanggal_rencana BETWEEN %s AND %s{w_r}", (d0, d1, *wv_r))
    rencana_main_kg = float((r_rencana["rows"][0]["rencana_kg"] if r_rencana["rows"] else 0) or 0)
    n_rencana = int((r_rencana["rows"][0]["n_rencana"] if r_rencana["rows"] else 0) or 0)
    # YTD reference always
    r_rencana_ytd = sdb.q(f"SELECT COUNT(*) AS n_rencana, ROUND(COALESCE(SUM(r.rencana_berat),0),1) AS rencana_kg FROM getah_rencana_aktivitas r WHERE r.tanggal_rencana BETWEEN %s AND %s{w_r}", (d0y, dlast, *wv_r))
    rencana_ytd_kg = float((r_rencana_ytd["rows"][0]["rencana_kg"] if r_rencana_ytd["rows"] else 0) or 0)
    # periode reference always (for UI when Ya)
    r_rencana_p = sdb.q(f"SELECT COUNT(*) AS n_rencana, ROUND(COALESCE(SUM(r.rencana_berat),0),1) AS rencana_kg FROM getah_rencana_aktivitas r WHERE r.tanggal_rencana BETWEEN %s AND %s{w_r}", (d0p, d1p, *wv_r))
    rencana_period_kg = float((r_rencana_p["rows"][0]["rencana_kg"] if r_rencana_p["rows"] else 0) or 0)

    r_actual = sdb.q(f"SELECT ROUND(COALESCE(SUM(p.berat_penerimaan),0),1) AS total_kg, COUNT(*) AS n_terima FROM getah_aktivitas_penerimaan p WHERE p.tanggal BETWEEN %s AND %s{w_prod}", (d0, d1, *wv_prod))
    actual_main_kg = float((r_actual["rows"][0]["total_kg"] if r_actual["rows"] else 0) or 0)
    r_actual_ytd = sdb.q(f"SELECT ROUND(COALESCE(SUM(p.berat_penerimaan),0),1) AS total_kg FROM getah_aktivitas_penerimaan p WHERE p.tanggal BETWEEN %s AND %s{w_prod}", (d0y, dlast, *wv_prod))
    actual_ytd_kg = float((r_actual_ytd["rows"][0]["total_kg"] if r_actual_ytd["rows"] else 0) or 0)
    r_actual_p = sdb.q(f"SELECT ROUND(COALESCE(SUM(p.berat_penerimaan),0),1) AS total_kg FROM getah_aktivitas_penerimaan p WHERE p.tanggal BETWEEN %s AND %s{w_prod}", (d0p, d1p, *wv_prod))
    actual_period_kg = float((r_actual_p["rows"][0]["total_kg"] if r_actual_p["rows"] else 0) or 0)
    # legacy aliases for backward compat
    rencana_kg = rencana_period_kg
    actual_period_kg = actual_period_kg  # keep
    actual_kg = actual_ytd_kg
    # main aliases respect mode
    if is_kumulatif:
        rencana_kg_main = rencana_ytd_kg
        actual_kg_main = actual_ytd_kg
    else:
        rencana_kg_main = rencana_period_kg
        actual_kg_main = actual_period_kg

    # derived — main KPIs respect sampai_dengan (Ya=YTD, Tidak=periode saja)
    def _pct(a,b): return round(100*a/b,2) if b else None
    pct_ytd = sdb._target_pct_sd(tahun, bulan, periode, {"sampai_dengan":"ya"}, default_kumulatif=True)
    target_ytd = round(total_rkap * pct_ytd/100,1)
    # YTD ratios
    plan_coverage_ytd_val = _pct(rencana_ytd_kg, target_ytd)
    achievement_ytd = _pct(actual_ytd_kg, target_ytd)
    # periode ratios
    plan_coverage_period = _pct(rencana_period_kg, target_expected)
    achievement_period = _pct(actual_period_kg, target_expected)
    # main respects mode
    if is_kumulatif:
        plan_coverage = plan_coverage_ytd_val
        achievement = achievement_ytd
        plan_gap = round(target_ytd - rencana_ytd_kg, 1) if target_ytd else None
        execution_gap = round(rencana_ytd_kg - actual_ytd_kg, 1)
        current_gap = round(target_ytd - actual_ytd_kg, 1) if target_ytd else None
        # override target_expected to YTD when Ya
        target_expected = target_ytd
        pct = pct_ytd
        d0, d1 = d0y, dlast
        rencana_kg = rencana_ytd_kg
        actual_kg_main = actual_ytd_kg
        rencana_kg_main = rencana_ytd_kg
    else:
        plan_coverage = plan_coverage_period
        achievement = achievement_period
        plan_gap = round(target_expected - rencana_period_kg, 1) if target_expected else None
        execution_gap = round(rencana_period_kg - actual_period_kg, 1)
        current_gap = round(target_expected - actual_period_kg, 1) if target_expected else None
    plan_gap_period = round(sdb._target_pct_sd(tahun, bulan, periode, {"sampai_dengan":"tidak"}, default_kumulatif=True) and target_expected - rencana_period_kg,1) if target_expected else None
    # keep ytd current gap for reference
    current_gap_ytd = round(target_ytd - actual_ytd_kg,1) if target_ytd else None

    kpi = dict(
        tahun=tahun, bulan=bulan, periode=periode,
        sampai_dengan=sampai_dengan,
        period_bounds=[d0, d1], ytd_bounds=[d0y, dlast], period_only_bounds=[d0p, d1p],
        target_total_kg=target_total, target_expected_kg=target_expected, target_pct=pct,
        target_ytd_kg=target_ytd, target_ytd_pct=pct_ytd,
        rencana_kg=rencana_period_kg, n_rencana=n_rencana,
        rencana_ytd_kg=rencana_ytd_kg, rencana_main_kg=(rencana_ytd_kg if is_kumulatif else rencana_period_kg),
        actual_kg=actual_ytd_kg, actual_period_kg=actual_period_kg, actual_main_kg=(actual_ytd_kg if is_kumulatif else actual_period_kg),
        plan_coverage_pct=plan_coverage, plan_coverage_ytd_pct=plan_coverage_ytd_val, plan_coverage_period_pct=plan_coverage_period,
        achievement_pct=achievement, achievement_ytd_pct=achievement_ytd, achievement_period_pct=achievement_period,
        plan_gap_kg=plan_gap, plan_gap_period_kg=round(target_expected - rencana_period_kg,1) if target_expected else None,
        execution_gap_kg=execution_gap, execution_gap_period_kg=round(rencana_period_kg - actual_period_kg,1),
        current_gap_kg=current_gap, current_gap_ytd_kg=current_gap_ytd,
    )

    # provenance — label ikut mode (canonical business rule)
    mode_label = "kumulatif Jan 1 .. akhir periode" if is_kumulatif else "periode saja"
    # main = Ya => Jan..cutoff, Tidak => periode saja (Penuh=1..akhir bulan, P1=1..15)
    evidence = [
        {"statement": f"Target {mode_label} s/d P{periode} {bulan}/{tahun}: {target_expected} kg ({pct}% × {target_total} kg) [{d0}..{d1}]", "source": "getah_petak.target_rkap × getah_target_ro_nps via _target_pct_sd(sampai_dengan="+sampai_dengan+")", "value": pct},
        {"statement": f"Rencana {mode_label} {d0}..{d1}: {(rencana_ytd_kg if is_kumulatif else rencana_period_kg)} kg ({n_rencana} rencana) | periode {d0p}..{d1p}: {rencana_period_kg} kg | YTD {d0y}..{dlast}: {rencana_ytd_kg} kg", "source": "getah_rencana_aktivitas.rencana_berat WHERE tanggal_rencana BETWEEN _range_bounds(sampai_dengan)", "value": (rencana_ytd_kg if is_kumulatif else rencana_period_kg)},
        {"statement": f"Realisasi {mode_label} {d0}..{d1}: {(actual_ytd_kg if is_kumulatif else actual_period_kg)} kg | periode {d0p}..{d1p}: {actual_period_kg} kg | YTD {d0y}..{dlast}: {actual_ytd_kg} kg", "source": "getah_aktivitas_penerimaan.berat_penerimaan WHERE tanggal BETWEEN _range_bounds(sampai_dengan)", "value": (actual_ytd_kg if is_kumulatif else actual_period_kg)},
    ]
    limitations = []
    if pct == 0: limitations.append("DATA_QUALITY: _target_pct=0 — getah_target_ro_nps kosong untuk tahun/bulan ini")
    if rencana_kg == 0: limitations.append("Rencana nol/belum susun — plan_coverage null")
    if total_rkap == 0: limitations.append("DATA_QUALITY: SUM target_rkap=0 — petak RTT kosong/orphan")
    sources = [
        {"template": "target_pct", "pct": pct, "sql": "SELECT SUM(ro_periode_*) FROM getah_target_ro_nps"},
        {"template": "rencana_aktivitas", "elapsed_ms": r_rencana.get("elapsed_ms"), "row_count": r_rencana.get("row_count")},
        {"template": "produksi_aktiv_ytd", "elapsed_ms": r_actual_ytd.get("elapsed_ms")},
    ]
    meta = {"rule_version": _RULE_VERSION, "cached": False, "scope": scope, "sampai_dengan": sampai_dengan}

    out = {"ok": True, "kpi": kpi, "evidence": evidence, "limitations": limitations, "sources": sources, "meta": meta}

    # optional breakdown per Mandor*TPG (reuse laporan template - dedup already in sdb)
    if include_breakdown:
        try:
            import decimal
            rows = sdb.T["laporan_perencanaan_target_setor_vs_ro_nps"](tahun, bulan, periode, **scope)["rows"]
            # Decimal->float for JSON
            for r in rows:
                for k,v in list(r.items()):
                    if isinstance(v, decimal.Decimal): r[k]=float(v)
            out["breakdown"] = rows[:50]
            out["breakdown_truncated"] = len(rows) > 50
        except Exception as e:
            out["breakdown_error"] = str(e)[:200]

    _CACHE[ck] = (time.monotonic(), out)
    return out

def get_diagnostic(tahun: int, bulan: int, periode: int, scope: dict | None = None, sampai_dengan: str = "ya", include_activity_detail: bool = True):
    """
    L3 Diagnostic: Target → Rencana → Aktivitas (per jenis × pohon) → Penerimaan
    Q = N × A × F × Y  (pohon × aktivitas × frekuensi × yield)
    Reuse Business Data Engine (aktivitas_agregat + petak/penerimaan), 0 LLM.
    sampai_dengan Ya=kumulatif Jan..cutoff, Tidak=periode saja (canonical).
    Return {kpi, aktivitas, diagnostic, limitations, evidence, meta}
    """
    gap = get_target_gap(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan, include_breakdown=False)
    kpi = gap["kpi"]
    # resolve sdb same as get_target_gap
    import importlib, os, sys, pathlib as _pl
    candidates = []
    if os.environ.get("ANA_SIMOGE_SCRIPTS"):
        candidates.append(os.environ["ANA_SIMOGE_SCRIPTS"])
    ROOT = _pl.Path(__file__).resolve().parent
    candidates.append(str(ROOT / "profile-dist/skills/software-development/simoge-business/scripts"))
    hhome = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    if "/profiles/" in hhome:
        hhome = hhome.split("/profiles/")[0]
    prof = os.environ.get("HERMES_PROFILE", os.environ.get("ANA_PROFILE", "anna")).strip() or "anna"
    candidates.append(os.path.join(hhome, "profiles", prof, "skills/software-development/simoge-business/scripts"))
    candidates.append(os.path.expanduser("~/.hermes/profiles/anna/skills/software-development/simoge-business/scripts"))
    sdb = None
    for cand in candidates:
        if cand and cand not in sys.path:
            sys.path.insert(0, cand)
        try:
            sdb = importlib.import_module("simoge_db")
            break
        except ModuleNotFoundError:
            continue
    if sdb is None:
        sdb = importlib.import_module("simoge_db")
    kw = {"sampai_dengan": sampai_dengan, **(scope or {})}
    # bounds ikut kpi main (already sampai_dengan-aware)
    d0, d1 = kpi["period_bounds"]
    # ---- aktivitas per jenis (6 flag + pohon per jenis) ----
    # raw counts per flag (existing engine) + SUM(CAST(jml_phn_* AS UNSIGNED)) per jenis
    # jml_phn_* varchar snapshot 100% NULL -> SUM null; treat as DATA_QUALITY
    import decimal
    # use flag totals from simoge via q (single stmt per flag for diagnostic speed: one UNION would be bigger diff, keep 1 query with 6 sums)
    w, wv = _wilayah_where(scope or {}, "s", sdb)
    pw, pv = sdb._pembaharuan_where(kw, "s")
    # jenis filter none, we want per-jenis breakdown
    # ---- robust discovery: flags & pohon columns from DB, fallback to sdb.AKTIVITAS_FLAGS ----
    # 1 sumber kebenaran: sdb.AKTIVITAS_FLAGS + AKTIVITAS_LABEL; BIT discover kolom yang benar-benar ada via information_schema
    # sehingga tambah jenis baru (kolom baru) cukup di DB + sdb flag list (atau auto-discover tinyint flag baru) — BIT tidak dibongkar.
    try:
        _flags = list(getattr(sdb, "AKTIVITAS_FLAGS", ("quare","semprot_cas","budaya_bersih","kerok","naik_batok","pulung")))
        _labels = dict(getattr(sdb, "AKTIVITAS_LABEL", {}))
        _arti_fallback = {"quare":"Quare — lukai batang buka jalur","semprot_cas":"Semprot CAS — stimulan","budaya_bersih":"Budaya Bersih — kebersihan sadapan","kerok":"Kerok — panen getah beku","naik_batok":"Naik Batok — naikkan wadah","pulung":"Pulung — kumpul getah cair"}
        # discover kolom flag yang ada di DB (hindari Unknown column bila DB belum migrate)
        try:
            _cs = sdb.q("SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='getah_aktivitas_sadap'")["rows"]
            _existing = {r["COLUMN_NAME"] for r in _cs}
        except Exception:
            _existing = set(_flags) | {"jml_phn_quare","jml_phn_semprot_cas","jml_phn_bdy_bersih","jml_phn_kerok","jml_phn_naik_batok","jml_phn_pulung"}
        # flag yang ada
        _flags = [f for f in _flags if f in _existing]
        # auto-discover tinyint flag baru yang belum di list (kolom 1/0) — tanpa code change, ikut masuk diagnostic
        try:
            for c in _existing:
                if c.startswith("jml_phn_"): continue
                if c in _flags: continue
                if c in ("id","id_penyadap","kode_evapot","pembaharuan_ke","tgl_pembaharuan","tgl_aktivitas","lat","long","alt","cuaca","akses_lokasi","aktivitas_photo","local_id","id_rencana","id_andil","status","kode_divre","kode_kph","kode_bkph","kode_rph","kode_tpg","tpg"): continue
                # heuristik: kolom tinyint flag baru — cek tipe via information_schema
                _flags.append(c) if False else None  # keep allowlist strict; new flag must add to sdb.AKTIVITAS_FLAGS (1 tempat). Auto-discovery dimatikan agar tidak salah include.
                pass
        except Exception:
            pass
        # peta jml_phn: budaya_bersih -> jml_phn_bdy_bersih (legacy name)
        _phn_map = {"quare":"jml_phn_quare","semprot_cas":"jml_phn_semprot_cas","budaya_bersih":"jml_phn_bdy_bersih","kerok":"jml_phn_kerok","naik_batok":"jml_phn_naik_batok","pulung":"jml_phn_pulung"}
        # build select parts only for existing columns
        _sel = ["COUNT(*) AS n_aktivitas"]
        for f in _flags:
            if f in _existing:
                _sel.append(f"SUM(s.`{f}`=1) AS n_{f}")
        for f in _flags:
            col = _phn_map.get(f, f"jml_phn_{f}")
            if col in _existing:
                # varchar null-safe: NULLIF '' -> NULL -> CAST -> COALESCE 0 (future int also works)
                _sel.append(f"COALESCE(SUM(CAST(NULLIF(s.`{col}`,'') AS UNSIGNED)),0) AS pohon_{f}")
            else:
                _sel.append(f"0 AS pohon_{f}")
        _sel.append("COUNT(DISTINCT s.id_penyadap) AS n_penyadap")
        _sel.append("COUNT(DISTINCT s.kode_evapot) AS n_petak_aktiv")
        _sql = f"SELECT " + ", ".join(_sel) + f" FROM getah_aktivitas_sadap s WHERE s.tgl_pembaharuan BETWEEN %s AND %s{pw}{w}"
        r_flags = sdb.q(_sql, (d0, d1, *pv, *wv))
        af = r_flags["rows"][0] if r_flags["rows"] else {}
        for ak in list(af.keys()):
            v = af[ak]
            if isinstance(v, decimal.Decimal):
                af[ak] = int(v) if ak.startswith("n_") else float(v)
            elif v is None:
                af[ak] = 0
    except Exception as e:
        af = {"n_aktivitas": 0, "error": str(e)[:200]}
        _flags = list(getattr(sdb, "AKTIVITAS_FLAGS", ("quare","semprot_cas","budaya_bersih","kerok","naik_batok","pulung")))
        _labels = dict(getattr(sdb, "AKTIVITAS_LABEL", {}))
        _arti_fallback = {"quare":"Quare — lukai batang buka jalur","semprot_cas":"Semprot CAS — stimulan","budaya_bersih":"Budaya Bersih — kebersihan sadapan","kerok":"Kerok — panen getah beku","naik_batok":"Naik Batok — naikkan wadah","pulung":"Pulung — kumpul getah cair"}
        _phn_map = {"quare":"jml_phn_quare","semprot_cas":"jml_phn_semprot_cas","budaya_bersih":"jml_phn_bdy_bersih","kerok":"jml_phn_kerok","naik_batok":"jml_phn_naik_batok","pulung":"jml_phn_pulung"}
        _existing = set()
    # per-jenis list for UI (with arti short) — robust: label from sdb, arti from fallback, pohon 0 if col missing (future data auto-isi)
    jenis_list = []
    for f in _flags:
        col_n = f"n_{f}"
        col_p = f"pohon_{f}"
        label = _labels.get(f) or _arti_fallback.get(f, f.replace('_',' ').title()).split(" —")[0]
        arti_txt = _arti_fallback.get(f, "").split(" — ",1)[1] if " — " in _arti_fallback.get(f,"") else ""
        if f not in _arti_fallback and f in _labels:
            arti_txt = ""  # unknown flag, no arti yet — vault will fill
        jenis_list.append({"jenis": f, "label": label, "arti": arti_txt, "count": int(af.get(col_n,0) or 0), "pohon": int(af.get(col_p,0) or 0)})
    # pembaharuan breakdown — direct query pakai d0/d1 (sampai_dengan-aware, bukan period_bounds murni)
    try:
        r_pem = sdb.q(
            f"SELECT s.pembaharuan_ke AS dim, CONCAT('Pembaharuan ', s.pembaharuan_ke) AS label, COUNT(*) AS count,"
            f" SUM(s.aktivitas_photo IS NOT NULL AND s.aktivitas_photo<>'') AS photo_count, COUNT(DISTINCT s.kode_evapot) AS petak_count"
            f" FROM getah_aktivitas_sadap s WHERE s.tgl_pembaharuan BETWEEN %s AND %s{pw}{w} GROUP BY s.pembaharuan_ke ORDER BY s.pembaharuan_ke",
            (d0, d1, *pv, *wv)
        )
        pem_rows = r_pem.get("rows", [])
        for x in pem_rows:
            x["count"]=int(x.get("count")or 0)
    except Exception as e:
        pem_rows = [{"error": str(e)[:150]}]
    # petak diagnostic: rantai rencana->aktivitas->penerimaan gap handled in kpi; aktivitas top via template
    # N = jumlah pohon petak scope (live)
    try:
        w_p, wv_p = _wilayah_where(scope or {}, "p", sdb)
        r_n = sdb.q(f"SELECT COALESCE(SUM(p.jumlah_pohon),0) AS pohon, COALESCE(SUM(p.luas_baku),0) AS luas FROM getah_petak p WHERE p.tahun_rtt=%s{w_p}", (tahun, *wv_p))
        pohon_scope = int(float((r_n["rows"][0]["pohon"] if r_n["rows"] else 0) or 0))
        luas_scope = float((r_n["rows"][0]["luas"] if r_n["rows"] else 0) or 0)
    except Exception:
        pohon_scope = 0; luas_scope = 0.0
    aktivitas = {
        "n_aktivitas": int(af.get("n_aktivitas",0) or 0),
        "n_penyadap_aktiv": int(af.get("n_penyadap",0) or 0),
        "n_petak_aktiv": int(af.get("n_petak_aktiv",0) or 0),
        "per_jenis": jenis_list,
        "per_pembaharuan": pem_rows,
        "pohon_scope": pohon_scope,
        "luas_scope_ha": round(luas_scope,2),
        "pohon_tersentuh_total": int(sum(int(x["pohon"]) for x in jenis_list)),
    }
    # ---- diagnostic chain ----
    rencana_kg = kpi.get("rencana_main_kg", kpi.get("rencana_ytd_kg",0)) or 0
    actual_kg = kpi.get("actual_main_kg", kpi.get("actual_kg",0)) or 0
    target_kg = kpi.get("target_expected_kg",0) or 0
    # Q factorization (proxy bila pohon per jenis NULL: use count as A, n_aktivitas as F proxy, yield = actual/aktivitas or /pohon)
    _pct = lambda a,b: round(100*a/b,2) if b else None
    # robust Y: bila jml_phn_* terisi (pohon_tersentuh_total>0) pakai yield sebenarnya per pohon; bila masih 0 pakai proxy per aktivitas — tanpa bongkar kode
    _pohon_tersentuh = int(aktivitas["pohon_tersentuh_total"] or 0)
    if _pohon_tersentuh and actual_kg:
        yield_per_aktivitas = round(actual_kg / _pohon_tersentuh, 3)
        yield_per_pohon_scope = round(actual_kg / pohon_scope, 3) if pohon_scope else None
        yield_per_pohon = yield_per_aktivitas
        _y_note = f"Y=actual/pohon_tersentuh ({actual_kg}/{_pohon_tersentuh})"
    else:
        yield_per_aktivitas = round(actual_kg / aktivitas["n_aktivitas"],3) if aktivitas["n_aktivitas"] else None
        yield_per_pohon_scope = round(actual_kg / pohon_scope,3) if pohon_scope and actual_kg else None
        yield_per_pohon = yield_per_pohon_scope
        _y_note = f"Y proxy=actual/n_aktivitas ({actual_kg}/{aktivitas['n_aktivitas']}) — ponytail: auto riil bila jml_phn terisi"
    diagnostic = {
        "chain": [
            {"stage":"Target", "kg": target_kg, "note": f"{kpi.get('target_pct')}% x RKAP {kpi.get('target_total_kg')} [{d0}..{d1}]"},
            {"stage":"Rencana", "kg": rencana_kg, "pct_of_target": _pct(rencana_kg, target_kg), "gap": kpi.get("plan_gap_kg")},
            {"stage":"Aktivitas", "count": aktivitas["n_aktivitas"], "n_penyadap": aktivitas["n_penyadap_aktiv"], "n_petak": aktivitas["n_petak_aktiv"], "per_jenis": jenis_list, "yield_per_aktivitas_kg": yield_per_aktivitas},
            {"stage":"Penerimaan", "kg": actual_kg, "pct_of_target": _pct(actual_kg, target_kg), "pct_of_rencana": _pct(actual_kg, rencana_kg), "gap_rencana_vs_actual": kpi.get("execution_gap_kg"), "yield_per_pohon_kg": yield_per_pohon},
        ],
        "q_proxy": {"N_pohon_scope": pohon_scope, "A_jenis_unik": sum(1 for x in jenis_list if x["count"]>0), "F_n_aktivitas": aktivitas["n_aktivitas"], "Y_yield_per_aktivitas": yield_per_aktivitas, "Y_yield_per_pohon_scope": yield_per_pohon_scope, "pohon_tersentuh_total": _pohon_tersentuh, "Y_note": _y_note, "formula": "Q=N×A×F×Y — N=pohon_scope, A=jenis unik, F=n_aktivitas, Y=actual/pohon_tersentuh bila terisi else proxy actual/F"},
        "gaps": {"plan_gap_kg": kpi.get("plan_gap_kg"), "execution_gap_kg": kpi.get("execution_gap_kg"), "current_gap_kg": kpi.get("current_gap_kg")},
    }
    limitations = list(gap.get("limitations", []))
    if aktivitas["pohon_tersentuh_total"] == 0:
        limitations.append("DATA_QUALITY: jml_phn_* 100% NULL di getah_aktivitas_sadap (snapshot 2026-10-03 / live) — pohon per jenis (quare..pulung) belum diisi; coverage/intensitas pohon per jenis tidak bisa dihitung, hanya count flag tersedia")
    if aktivitas["n_aktivitas"] == 0:
        limitations.append("Aktivitas nol pada rentang ini — per_jenis & pembaharuan kosong")
    evidence = list(gap.get("evidence", []))
    evidence.append({"statement": f"Aktivitas {d0}..{d1}: {aktivitas['n_aktivitas']} baris, {aktivitas['n_penyadap_aktiv']} penyadap, {aktivitas['n_petak_aktiv']} petak; per jenis Quare {jenis_list[0]['count']} Semprot {jenis_list[1]['count']} Budaya {jenis_list[2]['count']} Kerok {jenis_list[3]['count']} Batok {jenis_list[4]['count']} Pulung {jenis_list[5]['count']}; pohon per jenis total {aktivitas['pohon_tersentuh_total']} (jml_phn_* sum)", "source": "getah_aktivitas_sadap flag + CAST(jml_phn_* AS UNSIGNED) WHERE tgl_pembaharuan BETWEEN _range_bounds(sampai_dengan)", "value": aktivitas["n_aktivitas"]})
    meta = dict(gap.get("meta", {}))
    meta["diagnostic"] = True
    out = {"ok": True, "kpi": kpi, "aktivitas": aktivitas, "diagnostic": diagnostic, "evidence": evidence, "limitations": limitations, "sources": gap.get("sources",[]), "meta": meta}
    return out

def _prev_periode(tahun, bulan, periode):
    """prev untuk H falsifiable: month-1 same periode (Ya) / same sampai_dengan."""
    if bulan > 1:
        return tahun, bulan-1, periode
    return tahun-1, 12, periode

def get_hypothesis(tahun: int, bulan: int, periode: int, scope: dict | None = None, sampai_dengan: str = "ya"):
    """
    H1-H4 falsifiable hypotheses (anna_spesialis_bisnis.md §E).
    Deterministik, 0 LLM. Reuse get_diagnostic (global DIVRE..petak, scope jabatan).
    Banding: periode sama bulan sebelumnya, sampai_dengan sama (fair).
    Status: Terkonfirmasi / Didukung / Belum teruji / Tidak didukung (§F).
    Tiap H punya kondisi gugur (falsifiable) — bila data menolak, status Tidak didukung.
    """
    cur = get_diagnostic(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)
    pt, pb, pp = _prev_periode(tahun, bulan, periode)
    # prev boleh gagal (awal data) -> Belum teruji
    try:
        prev = get_diagnostic(pt, pb, pp, scope=scope, sampai_dengan=sampai_dengan)
    except Exception as e:
        prev = None
        prev_err = str(e)[:150]
    else:
        prev_err = None
    k = cur["kpi"]; a = cur["aktivitas"]
    pk = prev["kpi"] if prev else None; pa = prev["aktivitas"] if prev else None
    # helpers
    def _delta(cur_v, prev_v):
        if prev_v is None or prev_v == 0:
            return None
        return round(100*(cur_v - prev_v)/prev_v, 1)
    # current vs prev key metrics
    curr_n_pen = a.get("n_penyadap_aktiv",0); prev_n_pen = pa.get("n_penyadap_aktiv") if pa else None
    curr_n_akt = a.get("n_aktivitas",0); prev_n_akt = pa.get("n_aktivitas") if pa else None
    curr_yield = cur["diagnostic"]["chain"][2].get("yield_per_aktivitas_kg")  # Aktivitas stage
    # actually yield per aktivitas stored there; for prev too
    prev_yield = prev["diagnostic"]["chain"][2].get("yield_per_aktivitas_kg") if prev else None
    # also rencana coverage change
    curr_cov = k.get("plan_coverage_pct"); prev_cov = pk.get("plan_coverage_pct") if pk else None
    # H definitions
    hypos = []
    # H1 Kapasitas tenaga kerja menurun
    d_pen = _delta(curr_n_pen, prev_n_pen)
    if prev is None:
        h1_status = "Belum teruji"; h1_reason = f"Pembanding {pt}-{pb:02d} P{pp} tidak tersedia — butuh sejarah untuk uji perubahan penyadap aktif (curr {curr_n_pen})."
    elif d_pen is None:
        h1_status = "Belum teruji"; h1_reason = "Prev penyadap 0 — tidak bisa hitung delta."
    elif d_pen <= -5:
        h1_status = "Didukung"; h1_reason = f"Penyadap aktif turun {d_pen}% ({prev_n_pen}→{curr_n_pen}) pada rentang {k['period_bounds'][0]}..{k['period_bounds'][1]} vs {pk['period_bounds'][0]}..{pk['period_bounds'][1]}."
    elif d_pen >= 0:
        h1_status = "Tidak didukung"; h1_reason = f"Penyadap aktif tidak turun ({d_pen}% {prev_n_pen}→{curr_n_pen}) — H1 gugur: kapasitas tenaga tidak menjelaskan gap."
    else:
        h1_status = "Belum teruji"; h1_reason = f"Penurunan kecil {d_pen}% ({prev_n_pen}→{curr_n_pen}) — belum cukup bukti, perlu stratifikasi per BKPH/TPG."
    hypos.append({"id":"H1","label":"Kapasitas tenaga kerja menurun","data_dibutuhkan":"Status penyadap, periode aktif, realisasi produksi (n_penyadap_aktiv cur vs prev)","kondisi_gugur":"Jika n_penyadap_aktiv tidak turun (delta ≥0%), H1 gugur","status":h1_status,"delta_pct":d_pen,"cur":curr_n_pen,"prev":prev_n_pen,"evidence":h1_reason})
    # H2 Aktivitas penyadapan berkurang
    d_akt = _delta(curr_n_akt, prev_n_akt)
    # also check per-jenis quare/semprot as proxy A? but use total for now
    # falsifiable: if frequency not turun, H2 gugur; but also consider rencana coverage
    if prev is None:
        h2_status = "Belum teruji"; h2_reason = f"Pembanding aktivitas tidak ada (curr {curr_n_akt} baris)."
    elif d_akt is None:
        h2_status = "Belum teruji"; h2_reason = "Prev aktivitas 0."
    elif d_akt <= -5:
        # which jenis turun? find
        turun_jenis = [j["label"] for j in a["per_jenis"] if j["count"]>0]
        # compare jenis counts
        prev_jenis = {j["jenis"]: j["count"] for j in pa["per_jenis"]}
        jenis_delta = []
        for j in a["per_jenis"]:
            pv = prev_jenis.get(j["jenis"],0)
            if pv and j["count"] < pv:
                jenis_delta.append(f"{j['label']} {pv}→{j['count']}")
        extra = (" — jenis turun: "+", ".join(jenis_delta[:3])) if jenis_delta else ""
        h2_status = "Didukung"; h2_reason = f"Aktivitas turun {d_akt}% ({prev_n_akt}→{curr_n_akt}){extra}. Rencana coverage {curr_cov}% vs prev {prev_cov}%."
    elif d_akt >= -2:
        h2_status = "Tidak didukung"; h2_reason = f"Aktivitas tidak berkurang ({d_akt}% {prev_n_akt}→{curr_n_akt}) — H2 gugur; frekuensi operasi bukan penyebab, cek yield (H3) atau data (H4)."
    else:
        h2_status = "Belum teruji"; h2_reason = f"Penurunan tipis {d_akt}% ({prev_n_akt}→{curr_n_akt}) — perlu segmentasi per petak/pembaharuan."
    hypos.append({"id":"H2","label":"Aktivitas penyadapan berkurang","data_dibutuhkan":"Rencana, aktivitas bertanggal per jenis (quare..pulung × pohon), luas petak","kondisi_gugur":"Jika frekuensi aktivitas tidak turun (delta ≥ -2%), H2 gugur","status":h2_status,"delta_pct":d_akt,"cur":curr_n_akt,"prev":prev_n_akt,"evidence":h2_reason})
    # H3 Produktivitas per aktivitas menurun (Y)
    d_yield = _delta(curr_yield, prev_yield)
    if prev is None or curr_yield is None or prev_yield is None:
        h3_status = "Belum teruji"; h3_reason = f"Yield per aktivitas curr {curr_yield} vs prev {prev_yield} — pembanding belum tersedia."
    elif d_yield <= -5:
        h3_status = "Didukung"; h3_reason = f"Yield per aktivitas turun {d_yield}% ({prev_yield}→{curr_yield} kg/aktivitas) — perlu uji stratifikasi cuaca/akses/petak sebanding."
    elif d_yield >= -2:
        h3_status = "Tidak didukung"; h3_reason = f"Yield tidak turun ({d_yield}% {prev_yield}→{curr_yield}) — H3 gugur; penurunan produksi bukan dari produktivitas per aktivitas."
    else:
        h3_status = "Belum teruji"; h3_reason = f"Yield turun tipis {d_yield}% ({prev_yield}→{curr_yield}) — belum cukup bukti, perlu before-after per petak."
    hypos.append({"id":"H3","label":"Produktivitas per aktivitas menurun","data_dibutuhkan":"Volume hasil, jumlah aktivitas valid, kondisi petak (cuaca/akses/alt)","kondisi_gugur":"Jika yield per aktivitas tidak turun, H3 gugur","status":h3_status,"delta_pct":d_yield,"cur":curr_yield,"prev":prev_yield,"evidence":h3_reason})
    # H4 Masalah pencatatan / integrasi data
    # deterministik: jml_phn 100% NULL, target 0, orphan petak, lag sync dll
    dq_issues = []
    if a.get("pohon_tersentuh_total",0)==0:
        dq_issues.append("jml_phn_* 100% NULL (pohon per jenis tidak terisi)")
    if k.get("target_pct")==0:
        dq_issues.append("target_pct 0 (getah_target_ro_nps kosong)")
    if any("target_rkap=0" in s for s in cur.get("limitations",[])):
        dq_issues.append("SUM target_rkap 0 (petak orphan)")
    # rencana vs aktivitas gap: rencana ada tapi aktivitas 0?
    if k.get("rencana_main_kg",0)>0 and curr_n_akt==0:
        dq_issues.append("rencana >0 tapi aktivitas 0 (lag catat / sync)")
    # Pulung 0? known baru
    if all(j["count"]==0 for j in a["per_jenis"] if j["jenis"]=="pulung"):
        pass  # not issue, pulung baru
    # Decide status: if any dq and current_gap large, H4 Didukung as alternative; if no dq, Tidak didukung
    if dq_issues:
        # but H4 only Didukung if other H not fully explains? For now mark Didukung with issues
        h4_status = "Didukung" if len(dq_issues)>=1 else "Belum teruji"
        h4_reason = "Kualitas data bermasalah: " + "; ".join(dq_issues) + " — rekonsiliasi ID/transaksi & log sync diperlukan sebelum klaim kausal."
    else:
        h4_status = "Tidak didukung"; h4_reason = "Tidak terdeteksi anomali pencatatan pada rentang ini."
    hypos.append({"id":"H4","label":"Masalah pencatatan / integrasi data","data_dibutuhkan":"Timestamp, ID transaksi, log sinkronisasi, rekonsiliasi rencana↔aktivitas↔penerimaan","kondisi_gugur":"Jika rekonsiliasi sumber konsisten (tidak ada missing/dup/lag), H4 gugur","status":h4_status,"evidence":h4_reason,"issues":dq_issues})
    # priority: Didukung first, then Belum teruji, then Tidak didukung; within Didukung by absolute delta magnitude
    order = {"Didukung":0, "Belum teruji":1, "Tidak didukung":2, "Terkonfirmasi": -1}
    hypos_sorted = sorted(hypos, key=lambda h: (order.get(h["status"],3), -abs(h.get("delta_pct") or 0)))
    evidence = list(cur.get("evidence", []))
    evidence.append({"statement": f"Hipotesis H1-H4 vs periode pembanding {pt}-{pb:02d} P{pp} [{pk['period_bounds'][0] if pk else '?'}..{pk['period_bounds'][1] if pk else '?'}]: " + "; ".join([f"{h['id']} {h['status']} ({h.get('delta_pct') if h.get('delta_pct') is not None else '—'}%)" for h in hypos]), "source": "get_diagnostic(cur) vs get_diagnostic(prev) metric delta", "value": len([h for h in hypos if h["status"]=="Didukung"])})
    limitations = list(cur.get("limitations", []))
    if prev is None:
        limitations.append(f"Pembanding prev {pt}-{pb:02d} P{pp} tidak tersedia — H1-H3 Belum teruji sampai data tersedia")
    # global scope note already via kpi scope
    return {"ok": True, "kpi": k, "aktivitas": a, "diagnostic": cur["diagnostic"], "hypotheses": hypos, "hypotheses_sorted": hypos_sorted, "prev": {"tahun":pt,"bulan":pb,"periode":pp,"kpi":pk,"aktivitas":pa,"error":prev_err} if prev else {"tahun":pt,"bulan":pb,"periode":pp,"error":prev_err}, "evidence": evidence, "limitations": limitations, "meta": {**cur.get("meta",{}), "hypothesis": True, "comparison": f"{pt}-{pb:02d} P{pp} vs {tahun}-{bulan:02d} P{periode} sampai_dengan={sampai_dengan}"}}


def get_sebaran(tahun: int, bulan: int, periode: int, scope: dict | None = None, sampai_dengan: str = "ya"):
    """
    L2 Lokalisasi: kontribusi gap per wilayah global DIVRE->KPH->BKPH->RPH->TPG.
    Deterministik, robust: pakai _wilayah_where + GROUP BY, nama via bkph/rph/kph tables coalesce.
    Return {level, rows:[kode,nama,total_rkap,target_expected,rencana,actual,ach,plan_cov,gap,share_gap], top_petak}
    Hormati scope jabatan — breakdown 1 level lebih dalam dari scope terdalam.
    """
    gap = get_target_gap(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)
    kpi = gap["kpi"]
    d0, d1 = kpi["period_bounds"]
    pct = float(kpi.get("target_pct") or 0)
    # resolve sdb
    import importlib, os, sys, pathlib as _pl
    cands = []
    if os.environ.get("ANA_SIMOGE_SCRIPTS"):
        cands.append(os.environ["ANA_SIMOGE_SCRIPTS"])
    ROOT = _pl.Path(__file__).resolve().parent
    cands.append(str(ROOT / "profile-dist/skills/software-development/simoge-business/scripts"))
    hhome = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    if "/profiles/" in hhome:
        hhome = hhome.split("/profiles/")[0]
    prof = os.environ.get("HERMES_PROFILE", os.environ.get("ANA_PROFILE", "anna")).strip() or "anna"
    cands.append(os.path.join(hhome, "profiles", prof, "skills/software-development/simoge-business/scripts"))
    cands.append(os.path.expanduser("~/.hermes/profiles/anna/skills/software-development/simoge-business/scripts"))
    sdb = None
    for cand in cands:
        if cand and cand not in sys.path:
            sys.path.insert(0, cand)
        try:
            sdb = importlib.import_module("simoge_db")
            break
        except ModuleNotFoundError:
            continue
    if sdb is None:
        sdb = importlib.import_module("simoge_db")
    scope = dict(scope or {})
    # level terdalam
    deepest = None
    for k in ("kode_tpg","kode_rph","kode_bkph","kode_kph","kode_divre"):
        if scope.get(k) or scope.get("kode_tpg_list"):
            deepest = k
            break
    # pilih breakdown level: 1 tingkat di bawah deepest, atau bkph jika global
    if deepest == "kode_tpg":
        # sudah terdalam — breakdown per petak (via top_petak)
        b_level = "petak"
    elif deepest == "kode_rph":
        b_level = "kode_tpg"
    elif deepest == "kode_bkph":
        b_level = "kode_rph"
    elif deepest == "kode_kph":
        b_level = "kode_bkph"
    elif deepest == "kode_divre":
        b_level = "kode_kph"
    else:
        b_level = "kode_bkph"  # global -> per BKPH (5) paling informatif; BWB data only

    rows = []
    top_petak = []
    # helper scope without level
    def _scope_without(exclude):
        return {k:v for k,v in scope.items() if k != exclude}

    try:
        if b_level == "petak":
            # LEVEL TERDALAM: sebaran per petak — ranking gap per kode_evapot (TPG sudah terdalam)
            w_p, wv_p = _wilayah_where(scope, "p", sdb)
            try:
                q_petak = f"SELECT p.kode_evapot AS kode, COALESCE(MAX(p.nomor_petak),'') AS nomor, COALESCE(MAX(p.nama_tpg),'') AS tpg_nama, COUNT(*) AS n_petak, COALESCE(SUM(p.target_rkap),0) AS total_rkap, COALESCE(SUM(p.jumlah_pohon),0) AS pohon FROM getah_petak p WHERE p.tahun_rtt=%s AND p.kode_evapot IS NOT NULL {w_p} GROUP BY p.kode_evapot ORDER BY total_rkap DESC LIMIT 50"
                r_petak = sdb.q(q_petak, (tahun, *wv_p))
                petak_map = {str(r["kode"]): r for r in r_petak.get("rows", [])}
            except Exception as e:
                petak_map = {}
            try:
                w_r, wv_r = _wilayah_where({k:v for k,v in scope.items() if k != "kode_evapot"}, "r", sdb)
                r_renc = sdb.q(f"SELECT r.kode_evapot AS kode, COALESCE(SUM(r.rencana_berat),0) AS rencana_kg FROM getah_rencana_aktivitas r WHERE r.tanggal_rencana BETWEEN %s AND %s AND r.kode_evapot IS NOT NULL {w_r} GROUP BY r.kode_evapot", (d0, d1, *wv_r))
                renc_map = {str(r["kode"]): float(r["rencana_kg"] or 0) for r in r_renc.get("rows", [])}
            except Exception:
                renc_map = {}
            try:
                w_a, wv_a = _wilayah_where({k:v for k,v in scope.items() if k != "kode_evapot"}, "p", sdb)
                r_act = sdb.q(f"SELECT p.kode_evapot AS kode, COALESCE(SUM(p.berat_penerimaan),0) AS actual_kg FROM getah_aktivitas_penerimaan p WHERE p.tanggal BETWEEN %s AND %s AND p.kode_evapot IS NOT NULL {w_a} GROUP BY p.kode_evapot", (d0, d1, *wv_a))
                act_map = {str(r["kode"]): float(r["actual_kg"] or 0) for r in r_act.get("rows", [])}
            except Exception:
                act_map = {}
            try:
                kw = {"sampai_dengan": sampai_dengan, **scope}
                r_top = sdb.T["aktivitas_top_petak"](tahun, bulan, periode, limit=5, **kw)
                top_petak = r_top.get("rows", [])[:5]
            except Exception:
                top_petak = []
            all_kodes = set(list(petak_map.keys()) + list(renc_map.keys()) + list(act_map.keys()))
            import decimal as _dec2
            tmp = []
            for kode in all_kodes:
                pm = petak_map.get(kode, {})
                total_rkap = float(pm.get("total_rkap") or 0)
                target_exp = round(total_rkap * pct / 100, 1) if pct else 0
                rencana = float(renc_map.get(kode, 0) or 0)
                actual = float(act_map.get(kode, 0) or 0)
                ach = round(100*actual/target_exp,1) if target_exp else None
                plan_cov = round(100*rencana/target_exp,1) if target_exp else None
                _gap_kg2 = round(target_exp - actual,1) if target_exp else None
                nomor = pm.get("nomor") or kode
                if isinstance(nomor, _dec2.Decimal):
                    nomor = str(nomor)
                tpgn = pm.get("tpg_nama") or ""
                if isinstance(tpgn, _dec2.Decimal):
                    tpgn = str(tpgn)
                tmp.append({"kode": kode, "nama": f"{nomor} ({tpgn})" if tpgn else str(nomor), "n_petak": 1, "pohon": int(float(pm.get("pohon") or 0)), "total_rkap": round(total_rkap,1), "target_expected": target_exp, "rencana_kg": round(rencana,1), "actual_kg": round(actual,1), "achievement_pct": ach, "plan_coverage_pct": plan_cov, "gap_kg": _gap_kg2})
            total_gap_p = sum(max(0, x["gap_kg"] or 0) for x in tmp) or 1
            for x in tmp:
                x["share_gap_pct"] = round(100*max(0, x["gap_kg"] or 0)/total_gap_p,1) if x["gap_kg"] and x["gap_kg"]>0 else 0
            tmp.sort(key=lambda x: (-(x["gap_kg"] if x["gap_kg"] is not None else -1e18), -(x["target_expected"] or 0)))
            rows = tmp[:12]
        else:
            # wilayah breakdown: 3 agregat GROUP BY b_level
            # 1) petak: total_rkap, n_petak
            # 2) rencana: rencana_kg
            # 3) actual: actual_kg
            col = b_level  # e.g. kode_bkph
            # petak agg
            scope_petak = _scope_without(col)
            w_petak, wv_petak = _wilayah_where(scope_petak, "p", sdb)
            # map level to name table/col
            name_map = {"kode_divre": ("divre","divre","divre"), "kode_kph": ("kph","kph","kph"), "kode_bkph": ("bkph","bkph","bkph"), "kode_rph": ("rph","rph","rph"), "kode_tpg": ("getah_daftar_tpg","nama_tpg","kode_tpg")}
            tbl, ncol, kcol = name_map.get(col, ("bkph","bkph","kode_bkph"))
            # petak rows
            try:
                # name via LEFT JOIN
                if col == "kode_bkph":
                    join = "LEFT JOIN bkph b ON b.kode_bkph = p.kode_bkph"
                    name_expr = "COALESCE(MAX(b.bkph), MAX(p.bkph))"
                elif col == "kode_rph":
                    join = "LEFT JOIN rph r ON r.kode_rph = p.kode_rph"
                    name_expr = "COALESCE(MAX(r.rph), MAX(p.rph))"
                elif col == "kode_kph":
                    join = "LEFT JOIN kph k ON k.kode_kph = p.kode_kph"
                    name_expr = "COALESCE(MAX(k.kph), MAX(p.kph))"
                elif col == "kode_divre":
                    join = "LEFT JOIN divre d ON d.kode_divre = p.kode_divre"
                    name_expr = "COALESCE(MAX(d.divre), MAX(p.divre))"
                elif col == "kode_tpg":
                    join = "LEFT JOIN getah_daftar_tpg t ON t.kode_tpg = p.kode_tpg"
                    name_expr = "COALESCE(MAX(t.nama_tpg), MAX(p.nama_tpg))"
                else:
                    join = ""
                    name_expr = f"MAX(p.{ncol})"
                q_petak = f"SELECT p.{col} AS kode, {name_expr} AS nama, COUNT(DISTINCT p.kode_evapot) AS n_petak, COALESCE(SUM(p.target_rkap),0) AS total_rkap, COALESCE(SUM(p.jumlah_pohon),0) AS pohon FROM getah_petak p {join} WHERE p.tahun_rtt=%s AND p.{col} IS NOT NULL {w_petak} GROUP BY p.{col} ORDER BY total_rkap DESC"
                r_petak = sdb.q(q_petak, (tahun, *wv_petak))
                petak_map = {str(r["kode"]): r for r in r_petak.get("rows", [])}
            except Exception as e:
                petak_map = {}
                rows_error = str(e)[:120]
            else:
                rows_error = None
            # rencana agg grouped by same col
            try:
                # rencana table col same name (kode_bkph etc)
                scope_r = _scope_without(col)
                w_r, wv_r = _wilayah_where(scope_r, "r", sdb)
                r_renc = sdb.q(f"SELECT r.{col} AS kode, COALESCE(SUM(r.rencana_berat),0) AS rencana_kg, COUNT(*) AS n_rencana FROM getah_rencana_aktivitas r WHERE r.tanggal_rencana BETWEEN %s AND %s AND r.{col} IS NOT NULL {w_r} GROUP BY r.{col}", (d0, d1, *wv_r))
                renc_map = {str(r["kode"]): float(r["rencana_kg"] or 0) for r in r_renc.get("rows", [])}
                renc_n_map = {str(r["kode"]): int(r["n_rencana"] or 0) for r in r_renc.get("rows", [])}
            except Exception:
                renc_map = {}; renc_n_map = {}
            # actual agg
            try:
                scope_a = _scope_without(col)
                w_a, wv_a = _wilayah_where(scope_a, "p", sdb)
                r_act = sdb.q(f"SELECT p.{col} AS kode, COALESCE(SUM(p.berat_penerimaan),0) AS actual_kg, COUNT(*) AS n FROM getah_aktivitas_penerimaan p WHERE p.tanggal BETWEEN %s AND %s AND p.{col} IS NOT NULL {w_a} GROUP BY p.{col}", (d0, d1, *wv_a))
                act_map = {str(r["kode"]): float(r["actual_kg"] or 0) for r in r_act.get("rows", [])}
            except Exception:
                act_map = {}
            # merge
            all_kodes = set(list(petak_map.keys()) + list(renc_map.keys()) + list(act_map.keys()))
            import decimal
            tmp = []
            for kode in all_kodes:
                pm = petak_map.get(kode, {})
                total_rkap = float(pm.get("total_rkap") or 0)
                target_exp = round(total_rkap * pct / 100, 1)
                rencana = float(renc_map.get(kode, 0) or 0)
                actual = float(act_map.get(kode, 0) or 0)
                n_renc = int(renc_n_map.get(kode, 0) or 0)
                n_petak = int(pm.get("n_petak") or 0)
                pohon = int(float(pm.get("pohon") or 0))
                ach = round(100*actual/target_exp,1) if target_exp else None
                plan_cov = round(100*rencana/target_exp,1) if target_exp else None
                _gap_kg = round(target_exp - actual,1) if target_exp else None
                nama = pm.get("nama") or kode
                if isinstance(nama, decimal.Decimal):
                    nama = str(nama)
                tmp.append({"kode": kode, "nama": str(nama or kode), "n_petak": n_petak, "pohon": pohon, "total_rkap": round(total_rkap,1), "target_expected": target_exp, "rencana_kg": round(rencana,1), "n_rencana": n_renc, "actual_kg": round(actual,1), "achievement_pct": ach, "plan_coverage_pct": plan_cov, "gap_kg": _gap_kg})
            # share_gap = gap / total_gap *100
            total_gap = sum(max(0, x["gap_kg"] or 0) for x in tmp) or 1
            for x in tmp:
                x["share_gap_pct"] = round(100*max(0, x["gap_kg"] or 0)/total_gap,1) if x["gap_kg"] and x["gap_kg"]>0 else 0
            # sort by gap desc (kesenjangan terbesar dulu), then target desc
            tmp.sort(key=lambda x: (-(x["gap_kg"] or -1e18), -(x["target_expected"] or 0)))
            rows = tmp
    except Exception as e:
        rows = [{"kode":"ERR","nama":f"sebaran error: {str(e)[:120]}","gap_kg":0}]

    # evidence
    evidence = list(gap.get("evidence", []))
    if rows and b_level != "petak":
        # top 2 penyumbang gap
        top2 = rows[:2]
        ev = "Sebaran " + b_level.replace("kode_","").upper() + f" ({d0}..{d1} s/d={sampai_dengan}): " + "; ".join([f"{r['nama']} gap {r['gap_kg']} kg ({r['share_gap_pct']}% dari total gap) capai {r['achievement_pct']}%" for r in top2])
        evidence.append({"statement": ev, "source": f"getah_petak target_rkap + rencana BETWEEN {d0}..{d1} + penerimaan GROUP BY {b_level}", "value": len(rows)})

    return {"ok": True, "kpi": kpi, "level": b_level, "rows": rows, "top_petak": top_petak, "evidence": evidence, "meta": {**gap.get("meta",{}), "sebaran": True, "period_bounds": [d0,d1], "sampai_dengan": sampai_dengan}}


def get_rekomendasi(tahun: int, bulan: int, periode: int, scope: dict | None = None, sampai_dengan: str = "ya"):
    """
    H Decision Intelligence — rekomendasi prioritas dari H1-H4 + sebaran.
    Deterministik, 0 LLM. Return {rekomendasi:[{masalah,faktor,tindakan,manfaat_kg,manfaat_pct,asumsi,biaya,sumber_daya,verifikasi,prioritas}], prioritas_sorted}
    Manfaat = estimasi kg bila faktor kembali ke periode pembanding (prev), asumsi eksplisit.
    Biaya = Rendah/Sedang/Tinggi kualitatif (tanpa data biaya riil → limitation).
    Global DIVRE..TPG + hormat scope jabatan via get_hypothesis/get_sebaran.
    """
    hypo = get_hypothesis(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)
    try:
        seb = get_sebaran(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)
    except Exception:
        seb = {"rows": [], "level": "kode_bkph"}
    kpi = hypo.get("kpi") or {}
    diag = hypo.get("diagnostic") or {}
    # fix diag chain access
    chain = diag.get("chain") or []
    # quick maps
    h_map = {h.get("id"): h for h in (hypo.get("hypotheses") or [])}
    top2 = (seb.get("rows") or [])[:2]
    top_nama = ", ".join([r.get("nama","") for r in top2]) if top2 else "wilayah dengan gap terbesar"
    # manfaat helpers
    target_exp = float(kpi.get("target_expected_kg") or 0)
    actual = float(kpi.get("actual_main_kg", kpi.get("actual_kg")) or 0)
    gap = float(kpi.get("current_gap_kg") or 0)
    recs = []
    def _manfaat_pct(kg):
        return round(100*kg/target_exp,1) if target_exp and kg else None
    # H1
    h1 = h_map.get("H1")
    if h1 and h1.get("status") == "Didukung":
        cur_n = h1.get("cur") or 0; prev_n = h1.get("prev") or 0
        # estimasi: jika penyadap kembali ke prev, tambahan kapasitas ~ (prev-cur)/cur * actual  (proxy linear)
        if cur_n and prev_n and cur_n < prev_n:
            need = prev_n - cur_n
            # need/cur * actual = tambahan bila kembali
            est = round((need/cur_n)*actual,1) if cur_n else 0
        else:
            est = round(0.05*actual,1) if actual else 0
            need = max(1, prev_n - cur_n) if prev_n else 1
        recs.append({
            "id": "R-H1",
            "masalah": f"Kekurangan tenaga di {top_nama} — gap {gap} kg vs target",
            "faktor": "H1 Kapasitas tenaga kerja",
            "tindakan": f"Tambah/aktifkan {need} penyadap di {top_nama}; cek andil menganggur + mutasi TPG",
            "manfaat_kg": est,
            "manfaat_pct": _manfaat_pct(est),
            "asumsi": f"Jika n_penyadap kembali {cur_n}→{prev_n} dan yield tetap {diag.get('q_proxy',{}).get('Y_yield_per_aktivitas')} kg/kegiatan",
            "biaya": "Sedang",
            "sumber_daya": "Rekrutmen/mutasi, verifikasi andil",
            "verifikasi": f"Banding periode {hypo.get('meta',{}).get('comparison','')} → cek n_penyadap & actual bulan depan",
            "prioritas": 1 if h1.get("delta_pct",0) and abs(h1["delta_pct"])>=10 else 2,
            "hypo_status": h1.get("status"),
        })
    # H2
    h2 = h_map.get("H2")
    if h2 and h2.get("status") == "Didukung":
        cur_a = h2.get("cur") or 0; prev_a = h2.get("prev") or 0
        if cur_a and prev_a and cur_a < prev_a:
            est = round((prev_a - cur_a) * (diag.get("q_proxy",{}).get("Y_yield_per_aktivitas") or (actual/cur_a if cur_a else 0)),1)
        else:
            est = round(0.07*actual,1) if actual else 0
        recs.append({
            "id": "R-H2",
            "masalah": f"Frekuensi kegiatan turun ({h2.get('delta_pct')}%) di {top_nama}",
            "faktor": "H2 Frekuensi aktivitas",
            "tindakan": f"Tingkatkan jadwal quare/semprot di {top_nama}; patroli kehadiran & foto bukti",
            "manfaat_kg": est,
            "manfaat_pct": _manfaat_pct(est),
            "asumsi": f"Jika frekuensi kembali {cur_a}→{prev_a} kegiatan dan Y tetap",
            "biaya": "Rendah",
            "sumber_daya": "Jadwal mandor, cek tgl_pembaharuan",
            "verifikasi": "Hitung n_aktivitas & per jenis quare..pulung periode depan",
            "prioritas": 1 if abs(h2.get("delta_pct") or 0)>=15 else 2,
            "hypo_status": h2.get("status"),
        })
    # H3
    h3 = h_map.get("H3")
    if h3 and h3.get("status") == "Didukung":
        cur_y = h3.get("cur"); prev_y = h3.get("prev")
        n_akt = (hypo.get("aktivitas") or {}).get("n_aktivitas") or 1
        if cur_y and prev_y and cur_y < prev_y:
            est = round((prev_y - cur_y) * n_akt,1)
        else:
            # fallback percent
            pct = abs(h3.get("delta_pct") or 10)/100
            est = round(pct * actual,1)
        recs.append({
            "id": "R-H3",
            "masalah": f"Yield per kegiatan turun {h3.get('delta_pct')}% ({prev_y}→{cur_y} kg)",
            "faktor": "H3 Produktivitas per kegiatan",
            "tindakan": f"Audit teknik quare 1..3 + semprot di {top_nama}; cek cuaca/akses/pohon per jenis bila jml_phn terisi",
            "manfaat_kg": est,
            "manfaat_pct": _manfaat_pct(est),
            "asumsi": f"Jika Y kembali {cur_y}→{prev_y} kg/kegiatan pada {n_akt} kegiatan",
            "biaya": "Rendah-Sedang",
            "sumber_daya": "Pelatihan SOP, cek pembaharuan_ke",
            "verifikasi": "Yield per kegiatan & per pohon periode depan; stratifikasi cuaca/akses",
            "prioritas": 1,
            "hypo_status": h3.get("status"),
        })
    # H4
    h4 = h_map.get("H4")
    if h4 and h4.get("status") == "Didukung":
        issues = "; ".join((h4.get("issues") or [])[:2])
        recs.append({
            "id": "R-H4",
            "masalah": f"Data belum lengkap: {issues or 'jml_phn null'}",
            "faktor": "H4 Pencatatan",
            "tindakan": "Wajib isi jml_phn_* per jenis + rekonsiliasi rencana↔aktivitas↔penerimaan; isi foto bukti",
            "manfaat_kg": None,
            "manfaat_pct": None,
            "asumsi": "Tanpa data pohon, manfaat tidak bisa diestimasi — perbaiki dulu baru ukur H1-H3",
            "biaya": "Rendah",
            "sumber_daya": "Update SIMOGE mobile, validasi server",
            "verifikasi": "Cek DATA_QUALITY hilang: jml_phn terisi & n_aktivitas sinkron penerimaan",
            "prioritas": 3,
            "hypo_status": h4.get("status"),
        })
    # Sebaran-based: fokus wilayah
    if top2:
        # jika sudah ada R-H3/H2, sebaran jadi pelengkap; jika belum ada reco (semua Tidak didukung) buat reco sebaran
        if not recs or len([r for r in recs if r["id"] in ("R-H1","R-H2","R-H3")]) == 0:
            # buat reco sebaran umum
            top = top2[0]
            est = round(float(top.get("gap_kg") or 0) * 0.3,1)  # asumsi tutup 30% gap top
            recs.append({
                "id": "R-SEBARAN",
                "masalah": f"Kesenjangan terkonsentrasi di {top.get('nama')} ({top.get('share_gap_pct')}% pangsa gap)",
                "faktor": f"Sebaran {seb.get('level','').replace('kode_','').upper()}",
                "tindakan": f"Fokus intervensi di {top.get('nama')} — cek petak & penyadap di wilayah itu dulu",
                "manfaat_kg": est,
                "manfaat_pct": _manfaat_pct(est),
                "asumsi": "Jika 30% gap top tertutup (konservatif)",
                "biaya": "Rendah",
                "sumber_daya": "Kunjungan lapangan prioritas",
                "verifikasi": f"Gap {top.get('nama')} periode depan vs {hypo.get('meta',{}).get('comparison','')}",
                "prioritas": 2,
                "hypo_status": "Sebaran",
            })
        else:
            # tambah catatan sebaran ke setiap reco (implisit via masalah sudah sebut top_nama)
            pass
    if not recs:
        recs.append({
            "id": "R-PANTAU",
            "masalah": "Tidak ada hipotesis Didukung — gap tidak dijelaskan H1-H3",
            "faktor": "Pemantauan",
            "tindakan": "Pertahankan jadwal; pantau tren 2 periode ke depan; lengkapi jml_phn",
            "manfaat_kg": None,
            "manfaat_pct": None,
            "asumsi": "Belum ada bukti kuat — jangan intervensi besar dulu",
            "biaya": "Rendah",
            "sumber_daya": "Dashboard harian",
            "verifikasi": "Banding bulan depan same sampai_dengan",
            "prioritas": 3,
            "hypo_status": "Pantau",
        })
    # sort prioritas 1->3, manfaat besar dulu
    recs_sorted = sorted(recs, key=lambda x: (x.get("prioritas",3), -(x.get("manfaat_kg") or 0)))
    evidence = list(hypo.get("evidence", []) or [])
    if recs:
        ev = "Rekomendasi: " + "; ".join([f"{r['id']} {r['tindakan'][:60]} (~{r['manfaat_kg']} kg)" if r.get('manfaat_kg') else f"{r['id']} {r['tindakan'][:60]}" for r in recs_sorted[:2]])
        evidence.append({"statement": ev, "source": "H1-H4 + sebaran top2", "value": len(recs)})
    limitations = list(hypo.get("limitations", []) or [])
    if any(r.get("biaya")=="Sedang" for r in recs):
        limitations.append("Biaya Sedang/Rendah = estimasi kualitatif; belum ada data biaya riil per intervensi")
    return {"ok": True, "kpi": kpi, "rekomendasi": recs, "rekomendasi_sorted": recs_sorted, "evidence": evidence, "limitations": limitations, "meta": {**hypo.get("meta",{}), "rekomendasi": True, "count": len(recs)}}


def get_analisis(tahun: int, bulan: int, periode: int, scope: dict | None = None, sampai_dengan: str = "ya"):
    """
    C Kuantitatif + D Kausal ringan: tren, distribusi, anomali, sensitivitas, stratified.
    Deterministik, 0 LLM. Reuse get_target_gap/get_sebaran.
    Tren: 6 bulan terakhir (same periode+sampai_dengan) + growth.
    Distribusi: mean/median/std + konsentrasi (pangsa top2).
    Anomali: achievement < mean-1.5*std atau gap lonjak >50%.
    Sensitivitas: kontribusi N/A/F/Y proxy terhadap gap (Q=NxAxFxY).
    Stratified: banding BKPH dalam KPH yang sama (kelompok sebanding) — contoh 2 BKPH terbesar.
    Global DIVRE..petak + Ya/Tidak Penuh.
    """
    # tren: 6 titik mundur
    tren = []
    try:
        for i in range(5, -1, -1):
            y, m = tahun, bulan - i
            while m <= 0:
                m += 12; y -= 1
            try:
                g = get_target_gap(y, m, periode, scope=scope, sampai_dengan=sampai_dengan)
                k = g.get("kpi", {})
                tren.append({"tahun": y, "bulan": m, "periode": periode, "label": f"{y}-{m:02d} P{periode}", "target": k.get("target_expected_kg"), "actual": k.get("actual_main_kg", k.get("actual_kg")), "achievement": k.get("achievement_pct"), "gap": k.get("current_gap_kg")})
            except Exception as e:
                tren.append({"tahun": y, "bulan": m, "periode": periode, "label": f"{y}-{m:02d} P{periode}", "error": str(e)[:80]})
    except Exception as e:
        tren = [{"error": str(e)[:120]}]
    # growth vs prev point
    for idx in range(1, len(tren)):
        cur = tren[idx].get("actual"); prev = tren[idx-1].get("actual")
        if cur is not None and prev and prev != 0:
            tren[idx]["growth_pct"] = round(100*(cur-prev)/prev,1)
    # distribusi & anomali via sebaran
    try:
        seb = get_sebaran(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)
        rows = seb.get("rows") or []
        achs = [r.get("achievement_pct") for r in rows if r.get("achievement_pct") is not None]
        gaps = [r.get("gap_kg") for r in rows if r.get("gap_kg") is not None]
        import statistics as _st
        distribusi = {}
        if achs:
            try:
                distribusi["achievement"] = {"mean": round(_st.mean(achs),1), "median": round(_st.median(achs),1), "stdev": round(_st.stdev(achs),1) if len(achs)>1 else 0, "min": min(achs), "max": max(achs), "n": len(achs)}
            except Exception:
                distribusi["achievement"] = {"mean": round(sum(achs)/len(achs),1), "n": len(achs)}
        if gaps:
            try:
                distribusi["gap"] = {"mean": round(_st.mean(gaps),1), "stdev": round(_st.stdev(gaps),1) if len(gaps)>1 else 0, "max": max(gaps), "n": len(gaps)}
            except Exception:
                distribusi["gap"] = {"mean": round(sum(gaps)/len(gaps),1)}
        # konsentrasi: pangsa top2
        shares = [r.get("share_gap_pct",0) for r in rows]
        top2_share = round(sum(sorted(shares, reverse=True)[:2]),1) if shares else 0
        konsentrasi = "terkonsentrasi" if top2_share >= 60 else ("merata" if top2_share <= 35 else "cukup merata")
        distribusi["konsentrasi"] = {"top2_share_pct": top2_share, "klasifikasi": konsentrasi}
        # anomali
        anomali = []
        if achs and distribusi.get("achievement",{}).get("mean") is not None:
            mean = distribusi["achievement"]["mean"]; sd = distribusi["achievement"].get("stdev",0)
            thresh = mean - 1.5*sd if sd else mean*0.7
            for r in rows:
                if r.get("achievement_pct") is not None and r["achievement_pct"] < thresh:
                    anomali.append({"kode": r.get("kode"), "nama": r.get("nama"), "achievement": r.get("achievement_pct"), "gap": r.get("gap_kg"), "jenis": "capaian rendah"})
        # gap lonjak vs tren titik terakhir
        if len(tren) >= 2 and tren[-1].get("gap") is not None and tren[-2].get("gap"):
            if abs(tren[-1]["gap"]) > abs(tren[-2]["gap"])*1.5:
                anomali.append({"label": tren[-1]["label"], "gap": tren[-1]["gap"], "prev_gap": tren[-2]["gap"], "jenis": "lonjakan kesenjangan"})
        if not anomali:
            anomali = [{"jenis": "tidak ada", "catatan": "Tidak terdeteksi anomali pada ambang mean-1.5sd / lonjak 50%"}]
    except Exception as e:
        distribusi = {"error": str(e)[:120]}
        anomali = [{"error": str(e)[:120]}]
        seb = {"rows": [], "level": "kode_bkph"}
    # sensitivitas (proxy): ubah masing-masing faktor 10% -> dampak kg
    try:
        # ambil diagnostic untuk N/A/F/Y
        hypo = get_hypothesis(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)
        diag = hypo.get("diagnostic", {}) or {}
        q = diag.get("q_proxy", {}) or {}
        actual = float((hypo.get("kpi") or {}).get("actual_main_kg", hypo.get("kpi",{}).get("actual_kg")) or 0)
        # proxy factors: N=pohon_scope, F=n_aktivitas, Y=yield
        n_akt = (hypo.get("aktivitas") or {}).get("n_aktivitas") or 1
        yld = q.get("Y_yield_per_aktivitas") or (actual/n_akt if n_akt else 0)
        # sensitivitas: +10% tiap faktor -> +10% actual (linear proxy) -> urut sama; bedakan via konteks
        sens = [
            {"faktor": "N (pohon/ luas)", "perubahan": "+10% N", "dampak_kg": round(actual*0.10,1), "keterangan": "Jika luas/pohon efektif +10% dengan F,Y tetap"},
            {"faktor": "F (frekuensi kegiatan)", "perubahan": "+10% F", "dampak_kg": round(actual*0.10,1), "keterangan": "Jika n_aktivitas +10% (kuare..pulung)"},
            {"faktor": "Y (hasil per kegiatan)", "perubahan": "+10% Y", "dampak_kg": round(actual*0.10,1), "keterangan": f"Jika yield {yld} kg/kegiatan +10%"},
        ]
        # yang paling berpengaruh = yang sedang Didukung (hipotesis)
        h_status = {h.get("id"): h.get("status") for h in (hypo.get("hypotheses") or [])}
        for s in sens:
            if "H3" in str(h_status) and h_status.get("H3")=="Didukung" and "Y (" in s["faktor"]:
                s["prioritas"] = 1
            elif h_status.get("H2")=="Didukung" and "F (" in s["faktor"]:
                s["prioritas"] = 1
            else:
                s["prioritas"] = 2
        sens_sorted = sorted(sens, key=lambda x: x.get("prioritas",2))
    except Exception as e:
        sens = [{"error": str(e)[:120]}]
        sens_sorted = sens
    # stratified: banding 2 BKPH dalam scope yang sama (kelompok sebanding) — contoh top2 sebaran
    stratified = []
    try:
        seb_rows = (seb.get("rows") or [])[:3] if isinstance(seb, dict) else []
        if len(seb_rows) >= 2:
            a, b = seb_rows[0], seb_rows[1]
            stratified.append({"kelompok": f"{a.get('nama')} vs {b.get('nama')}", "a_achievement": a.get("achievement_pct"), "b_achievement": b.get("achievement_pct"), "selisih": round((a.get("achievement_pct") or 0)-(b.get("achievement_pct") or 0),1) if a.get("achievement_pct") is not None and b.get("achievement_pct") is not None else None, "catatan": "Stratified: banding kelompok sebanding (level sama) — kontrol wilayah, periode & sampai_dengan sama; selisih bukan bukti kausal tanpa kontrol cuaca/akses/petak."})
        else:
            stratified.append({"catatan": "Stratified butuh ≥2 wilayah pada level sebaran; scope saat ini tidak cukup — coba global atau KPH."})
    except Exception as e:
        stratified = [{"error": str(e)[:120]}]
    return {"ok": True, "periode": {"tahun": tahun, "bulan": bulan, "periode": periode, "sampai_dengan": sampai_dengan, "scope": scope}, "tren": tren, "distribusi": distribusi, "anomali": anomali, "sensitivitas": sens, "sensitivitas_sorted": sens_sorted, "stratified": stratified, "meta": {"rule_version": _RULE_VERSION, "analisis": True}}

def clear_cache(): _CACHE.clear()





