#!/usr/bin/env python3
"""
ana_kpi.py — Production KPI builder + narrator for ANNA (BI narrative).

Contract (docs/refaktor/anna_bi_agent.md):
- ANNA never touches SQL. This module is the ONLY path from named templates
  to narratable numbers. It calls `call_simoge_tool` (named templates only).
  No `simoge_db.q`, no docker/mysql, no hand-written SELECT. Ever.
- Output = KPI semantic objects (§3) + evidence trace (§7) + limitations (§6).
- Narrative = fixed 6-section structure (§9). Level-4 interpretation uses
  correlation language only — causal verbs fail hard (AssertionError, §13).
- `petak_simple.json` = dimension + YOY snapshot only (freshness stamp in
  `sources`). Never a KPI source — every narrated number comes from live DB.

Usage from ANA tool-call:
    from ana_kpi import answer_production
    answer_production(tahun=2026, bulan=8, periode=1)
    → {"kpi": {...}, "narrative": "...", "narrative_short": "..."}

    from ana_kpi import get_production_kpi, narrate
    kpi = get_production_kpi(tahun=2026, bulan=8, periode=1, kode_bkph="3121101")
"""
from ana_simoge_tool import call_simoge_tool

__all__ = ["get_production_kpi", "narrate", "answer_production", "resolve_wilayah", "answer_production_fuzzy"]

# Causal verbs that must never appear in Level-4 output (§4, §11).
_FORBIDDEN_CAUSAL = ("menyebab", "disebab", "akibat", "memicu", "dipicu")

_BULAN_ID = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
             "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

# Templates that accept server-side wilayah filter (simoge_db._wilayah_where).
_WILAYAH_KEYS = ("kode_divre", "kode_kph", "kode_bkph", "kode_rph", "kode_tpg")


def _f(x, default=None):
    """Decimal/None/str → float. None stays None (never zero-filled, §6)."""
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _idnum(x, digits=2):
    """12345.678 → '12.345,68' (id-ID)."""
    s = f"{x:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _ton(kg):
    return f"{_idnum(kg / 1000)} ton"


def _pct(x):
    return f"{_idnum(x)}%"


def _prev(tahun, bulan, periode):
    if periode == 2:
        return tahun, bulan, 1
    if bulan > 1:
        return tahun, bulan - 1, 2
    return tahun - 1, 12, 2


def _last_day(tahun, bulan):
    import calendar
    return calendar.monthrange(tahun, bulan)[1]


def _spatial_stamp():
    """Freshness stamp from petak_simple.json meta (dimension only, §5)."""
    import pathlib, json
    for root in pathlib.Path(__file__).resolve().parents:
        for cand in (root / "ana-hermes-dashboard" / "ui" / "data" / "petak_simple.json",
                     root / "ui" / "data" / "petak_simple.json"):
            if cand.exists():
                try:
                    meta = json.loads(cand.read_text(encoding="utf-8")).get("meta") or {}
                    return {"generated_at": meta.get("generated_at"),
                            "periode": meta.get("periode"),
                            "counts": meta.get("counts")}
                except Exception:
                    return None
    return None


def _scope_label(wilayah):
    """Resolve filter codes → human names via wilayah_labels template."""
    if not wilayah:
        return "KPH BANYUWANGI BARAT (31211) — seluruh petak RTT"
    try:
        r = call_simoge_tool("wilayah_labels", {})
        row = (r.get("rows") or [{}])[0]
    except Exception:
        row = {}
    name_key = {"kode_divre": "divre", "kode_kph": "kph", "kode_bkph": "bkph",
                "kode_rph": "rph", "kode_tpg": "nama_tpg"}
    parts = []
    for k in _WILAYAH_KEYS:
        if k in wilayah:
            nm = ""
            for w in (row.get(k.replace("kode_", "")) or []):
                if str(w.get(k) or w.get("kode_wilayah")) == str(wilayah[k]):
                    nm = (w.get(name_key[k]) or w.get("alias") or "").strip()
                    break
            parts.append(f"{k.replace('kode_', '').upper()} {nm or '?'} ({wilayah[k]})")
    return ", ".join(parts) if parts else "seluruh KPH"


def resolve_wilayah(nama):
    """Fuzzy nama -> kode wilayah dict. Returns {kode_*:value} or raises LookupError with candidates.

    Prioritas: level hint (mis. 'BKPH Licin') > exact nama/alias > LIKE.
    Jika exact multi-level dengan nama sama (Licin di BKPH/RPH/TPG), pilih hierarki tertinggi (kode terpendek) — BKPH induk RPH/TPG.
    Jika level sama tapi nama beda (Banyuwangi Barat vs Selatan) tetap ambigu -> minta spesifikasi.
    ponytail: LIKE %x% cukup untuk <10k wilayah, add FULLTEXT when >100k.
    """
    if not nama or not str(nama).strip():
        raise ValueError("nama wilayah kosong")
    raw = str(nama).strip()
    import re as _re
    # level hint: "BKPH Licin" / "tpg br" / "kph banyuwangi barat"
    m = _re.match(r"^(divre|kph|bkph|rph|tpg)\s+(.+)$", raw, _re.I)
    hint_level, hint_nama = (m.group(1).lower(), m.group(2).strip()) if m else (None, raw)
    lookup_nama = hint_nama
    rows = call_simoge_tool("wilayah_lookup", {"nama": lookup_nama}).get("rows") or []
    if not rows:
        raise LookupError(f"Wilayah '{raw}' tidak ditemukan di divre/kph/bkph/rph/tpg")
    if hint_level:
        rows = [r for r in rows if r["level"] == hint_level]
        if not rows:
            raise LookupError(f"Wilayah '{raw}' tidak ditemukan untuk level {hint_level.upper()}")
    low = lookup_nama.lower()
    exact = [r for r in rows if (r.get("nama") or "").lower() == low or (r.get("alias") or "").lower() == low]
    pool = exact if exact else rows
    if len(pool) == 1:
        r = pool[0]
        key = {"divre": "kode_divre", "kph": "kode_kph", "bkph": "kode_bkph", "rph": "kode_rph", "tpg": "kode_tpg"}[r["level"]]
        return {key: str(r["kode"]), "_resolved": {"level": r["level"], "nama": r["nama"], "kode": str(r["kode"])}}
    # multi exact dengan nama identik tapi level beda + hierarki induk-anak (kode prefix) -> pilih terpendek (BKPH > RPH > TPG)
    if exact and len({(r.get("nama") or "").lower() for r in exact}) == 1:
        # cek apakah kode-kode saling prefix (3121101 prefix dari 312110102)
        exact_sorted = sorted(exact, key=lambda r: len(str(r["kode"])))
        shortest = exact_sorted[0]
        # jika shortest adalah prefix dari semua lainnya, itu induk hierarkis -> auto pilih induk
        if all(str(r["kode"]).startswith(str(shortest["kode"])) for r in exact):
            r = shortest
            key = {"divre": "kode_divre", "kph": "kode_kph", "bkph": "kode_bkph", "rph": "kode_rph", "tpg": "kode_tpg"}[r["level"]]
            return {key: str(r["kode"]), "_resolved": {"level": r["level"], "nama": r["nama"], "kode": str(r["kode"]), "_auto_parent": True}}
    cands = ", ".join(f"{r['level'].upper()} {r['nama']} ({r['kode']})" + (f" alias:{r['alias']}" if r.get("alias") else "") for r in pool[:8])
    raise LookupError(f"Nama '{raw}' ambigu ({len(pool)} match): {cands}. Sebut lebih spesifik (mis. 'BKPH Licin' atau kode 3121101).")


def answer_production_fuzzy(tahun, bulan, periode, wilayah_nama=None, mode="coding", **wilayah):
    """Wrapper: terima nama fuzzy (licin/beringin) + kode eksplisit. Fuzzy di-resolve dulu baru KPI."""
    if wilayah_nama:
        resolved = resolve_wilayah(wilayah_nama)
        resolved.pop("_resolved", None)
        merged = {**resolved, **wilayah}
        return answer_production(tahun, bulan, periode, mode=mode, **merged)
    return answer_production(tahun, bulan, periode, mode=mode, **wilayah)


def get_production_kpi(tahun, bulan, periode, **wilayah):
    """Build the production KPI semantic object (§3). One call, 9 queries."""
    wilayah = {k: str(v) for k, v in wilayah.items() if k in _WILAYAH_KEYS and str(v).strip()}
    # Semua sumber KPI kini scoped di DB (rkap_map, status_petak_per_wilayah,
    # produksi_aktiv KPH-wide hanya bila tanpa filter; petak_count universe).
    blind_note = ""
    kpi = {"kpi": "production_period", "label": "Produksi Getah Periode Berjalan",
           "period": {"tahun": tahun, "bulan": bulan, "periode": f"P{periode}",
                      "label": f"P{periode} {_BULAN_ID[bulan]} {tahun}"},
           "scope": {"filters": wilayah, "label": _scope_label(wilayah)},
           "calculation": "actual=SUM(berat_penerimaan); achievement=SUM(realisasi)/SUM(target_periode)",
           "source": "business_engine", "confidence": "direct",
           "evidence": {}, "limitations": [], "sources": []}
    ev, lim, src = kpi["evidence"], kpi["limitations"], kpi["sources"]

    def _call(t, p):
        r = call_simoge_tool(t, p)
        if not r.get("ok", True) and r.get("error"):
            raise RuntimeError(f"{t}: {r['error']}")
        src.append({"template": t, "params": p, "row_count": r.get("row_count"),
                    "elapsed_ms": r.get("elapsed_ms")})
        return (r.get("rows") or [])

    # ── actual cur + prev (production totals: direct SUM, never via andil join)
    cur = (_call("produksi_aktiv", {"tahun": tahun, "bulan": bulan, "periode": periode, **wilayah}) or [{}])[0]
    py, pm, pp = _prev(tahun, bulan, periode)
    prev = (_call("produksi_aktiv", {"tahun": py, "bulan": pm, "periode": pp, **wilayah}) or [{}])[0]
    actual, pactual = _f(cur.get("total_kg")), _f(prev.get("total_kg"))
    kpi["production"] = {"actual_kg": actual, "actual_str": _ton(actual) if actual is not None else None,
                         "n_penerimaan": cur.get("n_terima"), "n_petak_aktif": cur.get("n_petak"),
                         "unit": "kg"}
    ev["production.actual"] = ["produksi_aktiv[current]"]
    if actual is None:
        lim.append(f"Periode P{periode} {_BULAN_ID[bulan]} {tahun}: data penerimaan belum masuk — "
                   "dilaporkan sebagai belum tersedia, bukan nol.")
    if pactual:
        kpi["trend"] = {"prev_kg": pactual,
                        "prev_label": f"P{pp} {_BULAN_ID[pm]} {py}",
                        "growth_pct": round(100 * (actual - pactual) / pactual, 2) if actual is not None else None}
        ev["trend.growth"] = ["produksi_aktiv[current]", "produksi_aktiv[prev]"]
    else:
        kpi["trend"] = {"prev_kg": pactual, "prev_label": f"P{pp} {_BULAN_ID[pm]} {py}", "growth_pct": None}
        lim.append(f"Pembanding {kpi['trend']['prev_label']} kosong/belum masuk — growth tidak dihitung.")

    # ── achievement from rkap_map aggregation.
    # Guard anti-distorsi: Σ target_periode wajib ≈ Σ target_rkap × persen skalar
    # (JOIN target per-baris × polygon ganda pernah gandakan target → 40,9% palsu).
    pct_rows = _call("target_pct", {"tahun": tahun, "bulan": bulan, "periode": periode})
    pct = _f((pct_rows or [{}])[0].get("pct"), 0)
    rows = _call("rkap_map", {"tahun": tahun, "bulan": bulan, "periode": periode, "limit": 2000, **wilayah})
    tr = sum(_f(x.get("realisasi"), 0) for x in rows)
    tt = sum(_f(x.get("target_periode"), 0) for x in rows)
    if tt > 0 and pct > 0:
        expect = sum(_f(x.get("target_rkap"), 0) for x in rows) * pct / 100
        if expect > 0 and abs(tt - expect) / expect > 0.01:
            raise RuntimeError(
                f"achievement guard: Σ target_periode {tt:,.1f} vs "
                f"Σ target_rkap × {pct}% = {expect:,.1f} (selisih >1%) — "
                "target double-count, perbaiki simoge_db sebelum narasi.")
    from collections import Counter
    wc = Counter(x.get("warna") for x in rows if x.get("warna"))
    ach = round(100 * tr / tt, 2) if tt > 0 else None
    kpi["achievement"] = {"value_pct": ach, "value_str": _pct(ach) if ach is not None else None,
                         "realisasi_kg": round(tr, 1), "target_kg": round(tt, 1),
                         "gap_kg": round(tr - tt, 1),
                         "gap_str": _ton(abs(tr - tt)) if tt > 0 else None,
                         "warna_dist": dict(wc)}
    ev["achievement.value"] = ["rkap_map→SUM(realisasi)/SUM(target_periode)"]
    if ach is None:
        lim.append("Target periode nol/tidak ketemu — achievement tidak dihitung.")

    # ── coverage: rkap rows vs RTT universe
    n_rtt = ((_call("petak_count", {"tahun": tahun}) or [{}])[0]).get("jumlah_petak")
    kpi["coverage"] = {"n_rkap": len(rows), "n_rtt": n_rtt,
                       "gap": (n_rtt - len(rows)) if n_rtt else None,
                       "scoped": bool(wilayah)}
    ev["coverage"] = ["rkap_map[row_count]", "petak_count"]
    if n_rtt and len(rows) < n_rtt:
        if wilayah:
            lim.append(f"Scope {kpi['scope']['label']}: {len(rows)} petak masuk hitungan; "
                       f"sisanya dari {n_rtt} RTT berada di luar scope filter ini.")
        else:
            lim.append(f"{n_rtt - len(rows)} petak RTT di luar cakupan RKAP (tanpa polygon/target) — "
                       "diekspos di sini, tidak disembunyikan.")

    # ── activity: satu pintu status_petak_per_wilayah (scoped-ready, nama manusia).
    # idle_petak (per-petak, definisi sama) hanya untuk detail; agregat narasi
    # dari sini agar angka = jumlah polygon idle_petak_map (pernah 301/162 palsu
    # karena idle_petak lama prev=bulan-lalu + strict join andil).
    # Label tegas: ini petak aktivitas SADAP (cur>0), bukan petak terima getah.
    st_rows = _call("status_petak_per_wilayah",
                    {"tahun": tahun, "bulan": bulan, "periode": periode,
                     "level": "kode_bkph", **wilayah})
    tot_a = sum(int(x.get("aktif") or 0) for x in st_rows)
    tot_i = sum(int(x.get("idle") or 0) for x in st_rows)
    tot_b = sum(int(x.get("bongkor") or 0) for x in st_rows)
    tot_p = sum(int(x.get("total_petak") or 0) for x in st_rows)
    if tot_a + tot_i + tot_b != tot_p:
        raise RuntimeError(
            f"activity guard: aktif {tot_a} + idle {tot_i} + bongkor {tot_b} "
            f"!= total {tot_p} — partisi status bocor, perbaiki simoge_db.")
    kpi["activity"] = {"aktif": tot_a, "idle": tot_i, "bongkor": tot_b,
                       "total": tot_p, "by_wilayah": [
                           {"kode": x.get("kode_wilayah"), "nama": x.get("nama_wilayah"),
                            "aktif": int(x.get("aktif") or 0), "idle": int(x.get("idle") or 0),
                            "bongkor": int(x.get("bongkor") or 0)} for x in st_rows],
                       "definisi": "petak aktivitas sadap (cur>0=aktif; cur=0+prev>0=idle; sisanya bongkor)"}
    ev["activity"] = ["status_petak_per_wilayah[level=kode_bkph]"]

    # ── effectiveness: bongkor struktural (tanpa penyadap) dari agregat sama.
    # Satu pintu dengan activity — bukan petak_effectiveness terpisah
    # (pernah 267 vs 347 karena definisi beda: tanpa-andil vs tanpa-aktivitas).
    tot_eb = tot_b  # bongkor operasional periode ini (definisi CASE diperjelas)
    kpi["effectiveness"] = {"bongkor": tot_eb, "by_wilayah": [
        {"kode": x["kode"], "nama": x["nama"], "bongkor": x["bongkor"]}
        for x in kpi["activity"]["by_wilayah"]]}
    ev["effectiveness"] = ["status_petak_per_wilayah:bongkor (sama pintu dengan activity)"]

    # ── productivity kg/ha (reuse petak_area scoped + production.actual)
    try:
        pa = (_call("petak_area", {"tahun": tahun, **wilayah}) or [{}])[0]
        luas = _f(pa.get("luas_baku_total"))
        if luas and actual is not None and luas > 0:
            kpi["productivity"] = {"kg_per_ha": round(actual / luas, 2),
                                   "luas_ha": luas,
                                   "n_petak": pa.get("jumlah_petak")}
            ev["productivity"] = ["produksi_aktiv[current]", "petak_area"]
        else:
            kpi["productivity"] = {"kg_per_ha": None, "luas_ha": luas, "n_petak": pa.get("jumlah_petak")}
            if luas is None or luas == 0:
                lim.append("Luas baku tidak tersedia — produktivitas kg/ha tidak dihitung.")
            elif actual is None:
                lim.append("Produksi belum tersedia — produktivitas kg/ha tidak dihitung.")
    except Exception as e:
        kpi["productivity"] = {"kg_per_ha": None, "luas_ha": None, "error": str(e)[:120]}
        lim.append(f"Produktivitas tidak terhitung: {e}"[:200])

    # ── plan achievement: rencana vs realisasi (getah_rencana_aktivitas)
    try:
        rr = (_call("rencana_aktivitas", {"tahun": tahun, "bulan": bulan, "periode": periode, **wilayah}) or [{}])[0]
        rencana = _f(rr.get("rencana_kg"))
        if rencana and rencana > 0 and actual is not None:
            kpi["plan"] = {"rencana_kg": rencana, "actual_kg": actual,
                           "achievement_pct": round(100 * actual / rencana, 2),
                           "gap_kg": round(actual - rencana, 1),
                           "n_rencana": rr.get("n_rencana")}
            ev["plan"] = ["rencana_aktivitas", "produksi_aktiv[current]"]
        elif rencana is not None and rencana == 0:
            kpi["plan"] = {"rencana_kg": 0, "actual_kg": actual, "achievement_pct": None, "n_rencana": 0}
            lim.append(f"Rencana P{periode} {_BULAN_ID[bulan]} {tahun} nol/belum disusun — plan achievement tidak dihitung.")
        else:
            kpi["plan"] = {"rencana_kg": rencana, "actual_kg": actual, "achievement_pct": None, "n_rencana": rr.get("n_rencana")}
            if rencana is None:
                lim.append(f"Rencana P{periode} {_BULAN_ID[bulan]} {tahun} belum tersedia — dilaporkan belum tersedia, bukan nol.")
    except Exception as e:
        kpi["plan"] = {"rencana_kg": None, "achievement_pct": None, "error": str(e)[:120]}
        lim.append(f"Rencana tidak terhitung: {e}"[:200])

    # ── penyadap productivity kg/penyadap (template ada, belum di KPI)
    try:
        pr = _call("penyadap_productivity", {"tahun": tahun, "bulan": bulan, "periode": periode, **wilayah})
        if pr:
            total_pen = sum(_f(x.get("total_penerimaan"), 0) for x in pr)
            n_pen = len(pr)
            avg = round(total_pen / n_pen, 1) if n_pen else None
            # top 3 and bottom 3 for narrative context
            sorted_pr = sorted(pr, key=lambda x: _f(x.get("total_penerimaan"), 0), reverse=True)
            kpi["penyadap"] = {"n_penyadap": n_pen, "total_kg": round(total_pen, 1),
                               "avg_kg_per_penyadap": avg,
                               "top3": [{"id": x.get("id_penyadap"), "kg": _f(x.get("total_penerimaan"))} for x in sorted_pr[:3]],
                               "bottom3": [{"id": x.get("id_penyadap"), "kg": _f(x.get("total_penerimaan"))} for x in sorted_pr[-3:]]}
            ev["penyadap"] = ["penyadap_productivity"]
        else:
            kpi["penyadap"] = {"n_penyadap": 0, "avg_kg_per_penyadap": None}
            lim.append(f"Tidak ada data penyadap P{periode} {_BULAN_ID[bulan]} {tahun}.")
    except Exception as e:
        kpi["penyadap"] = {"n_penyadap": None, "avg_kg_per_penyadap": None, "error": str(e)[:120]}
        lim.append(f"Produktivitas penyadap tidak terhitung: {e}"[:200])

    # ── YTD
    ytd = (_call("produksi_year_to_date",
                 {"tahun": tahun, "bulan": bulan,
                  "day": 15 if periode == 1 else _last_day(tahun, bulan), **wilayah}) or [{}])[0]
    kpi["ytd"] = {"total_kg": _f(ytd.get("total_kg")), "n_petak": ytd.get("n_petak")}
    ev["ytd"] = ["produksi_year_to_date"]

    stamp = _spatial_stamp()
    if stamp:
        src.append({"dimensi_spasial": "petak_simple.json", **stamp})
    else:
        lim.append("Stempel kesegaran dimensi spasial tidak terbaca — angka tetap sah (sumber DB live).")
    return kpi


def narrate(kpi, mode="coding"):
    """Render the fixed 6-section narrative (§9). Returns full + 2-sentence short."""
    p = kpi["period"]["label"]
    scope = kpi["scope"]["label"]
    prod, ach, tr, cov = kpi["production"], kpi["achievement"], kpi["trend"], kpi["coverage"]
    eff, act, ytd = kpi["effectiveness"], kpi["activity"], kpi["ytd"]
    S = []  # (section, text)

    # EXECUTIVE SUMMARY — Level 1 only. Bedakan tegas: n_petak_aktif =
    # petak TERIMA getah (produksi_aktiv), bukan petak aktivitas sadap.
    if prod["actual_kg"] is not None:
        S.append(("Ringkasan",
                  f"Produksi {p} tercatat {prod['actual_str']} dari {prod['n_petak_aktif']} petak terima getah "
                  f"({prod['n_penerimaan']} penerimaan), scope {scope}."))
    else:
        S.append(("Ringkasan",
                  f"Produksi {p} belum tersedia pada konteks saat ini (scope {scope}). "
                  "Bagian lain di bawah memakai periode terdekat yang ada datanya bila disebut."))

    # PERFORMANCE — Level 1+2
    if ach["value_pct"] is not None:
        S.append(("Target",
                  f"Pencapaian {ach['value_str']} dari target { _ton(ach['target_kg'])} "
                  f"(realisasi {_ton(ach['realisasi_kg'])}, gap {ach['gap_str']}). "
                  f"Sebaran petak: {', '.join(f'{k} {v}' for k, v in sorted(ach['warna_dist'].items()))}."))
    if cov["gap"]:
        S.append(("Cakupan",
                  f"Dari {cov['n_rtt']} petak RTT, {cov['n_rkap']} masuk hitungan RKAP — "
                  f"{cov['gap']} petak di luar cakupan (tanpa polygon/target)."))

    # TREND — Level 3 (only when both sides exist)
    if tr["growth_pct"] is not None:
        arah = "meningkat" if tr["growth_pct"] >= 0 else "menurun"
        S.append(("Tren",
                  f"Dibanding {tr['prev_label']} ({_ton(tr['prev_kg'])}), produksi {arah} "
                  f"{_pct(abs(tr['growth_pct']))}. Ini perbandingan objektif dua periode tercatat."))

    # DRIVER — Level 4, correlation language only. Angka = jumlah polygon
    # idle_petak_map (satu definisi). Beda pintu dengan "petak terima getah".
    drv = (f"Pada periode ini, {act['aktif']} petak aktivitas sadap, {act['idle']} idle, "
           f"{act['bongkor']} bongkor "
           f"(indikator aktivitas bergerak bersamaan dengan produksi pada data yang tersedia).")
    S.append(("Konteks operasional", drv))

    # ATTENTION — bongkor per BKPH (nama manusia, dari pintu yg sama).
    top = sorted(act["by_wilayah"], key=lambda x: -x["bongkor"])[:3]
    top_s = ", ".join(f"{x['nama']} {x['bongkor']}" for x in top)
    S.append(("Perhatian",
              f"Terdapat {act['bongkor']} petak bongkor (terbanyak: {top_s}) — "
              f"kelompok ini perlu evaluasi operasional."))
    prodv = kpi.get("productivity") or {}
    if prodv.get("kg_per_ha") is not None:
        S.append(("Produktivitas",
                  f"Produktivitas {prodv['kg_per_ha']} kg/ha (produksi {_ton(prod['actual_kg'])} / luas {prodv['luas_ha']} ha, {prodv['n_petak']} petak)."))
    plan = kpi.get("plan") or {}
    if plan.get("achievement_pct") is not None:
        arah_p = "di atas" if plan["achievement_pct"] >= 100 else "di bawah"
        per_label = kpi["period"]["periode"]
        S.append(("Rencana",
                  f"Rencana {per_label} {plan['rencana_kg']} kg, realisasi {_ton(plan['actual_kg'])} — pencapaian {plan['achievement_pct']}% {arah_p} rencana (gap {_ton(abs(plan['gap_kg']))})."))
    peny = kpi.get("penyadap") or {}
    if peny.get("avg_kg_per_penyadap") is not None:
        S.append(("Penyadap",
                  f"{peny['n_penyadap']} penyadap aktif, rata-rata {peny['avg_kg_per_penyadap']} kg/penyadap (total {_ton(peny['total_kg'])})."))
    if ytd["total_kg"]:
        S.append(("Tahun berjalan", f"Akumulasi tahun berjalan {_ton(ytd['total_kg'])} dari {ytd['n_petak']} petak."))

    # LIMITATION — §6, always last when non-empty
    if kpi["limitations"]:
        S.append(("Batasan data", " ".join(kpi["limitations"])))

    for title, text in S:
        for bad in _FORBIDDEN_CAUSAL:
            assert bad not in text.lower(), f"causal verb in [{title}]: {bad}"
    full = "\n\n".join(f"**{t}.** {x}" for t, x in S)
    first_two = ". ".join(S[0][1].split(". ")[:2])
    short = first_two if first_two.endswith(".") else first_two + "."
    if mode == "asisten":
        return {"narrative": short, "narrative_short": short}
    return {"narrative": full, "narrative_short": short}


def answer_production(tahun, bulan, periode, mode="coding", **wilayah):
    """One call: KPI + narrative. ANNA's only production entry point."""
    kpi = get_production_kpi(tahun, bulan, periode, **wilayah)
    return {"kpi": kpi, **narrate(kpi, mode=mode)}


if __name__ == "__main__":
    import sys, json
    kw = {}
    for a in sys.argv[1:]:
        k, v = a.split("=", 1)
        kw[k] = int(v) if v.lstrip("-").isdigit() else v
    mode = kw.pop("mode", "coding")
    out = answer_production(mode=mode, **kw)
    print(json.dumps(out, default=str, indent=1, ensure_ascii=False))
