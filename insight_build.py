"""Insight Engine landing page — deterministik, tanpa LLM (v4).

Kalkulasi: cron 06:00 (scripts/rebuild_insight_daily.sh, marker
ana-insight-daily) → snapshot .ana_insight.json → live card baca file.
Scheduler thread = fallback bila cron tak ada.

Katalog v4 (N divre / ratusan KPH tanpa rombak — GROUP BY dinamis):
  prod_achieve   production   realisasi vs target kumulatif (%) + ranking
  aktiv_cur_prev field_ops    aktivitas + penyadap + petak aktif
  supply_recv    supply       terima → perni → angkut + efisiensi
                 + tren bulanan 3-seri; slides RENCANA digabung
                 (switch domain otomatis via rotasi)
  plan_check     plan         rencana_berat vs target periode + realisasi
                 rencana→aktivitas (join id_rencana terverifikasi)
  opt_bongkor    optimization bongkor per BKPH + PETA SCATTER nyata
                 (centroid polygon dihitung cron, ringan ~30KB)
  kph_trend      kphstrip     tren produksi per KPH 12 bulan + KORELASI
                 rencana→aktivitas→penerimaan (Pearson, switch otomatis)

Aturan slide v4: TIAP slide wajib bawa chart (komposisi 50% chart /
50% teks); tiap card ≥5 slides; headline ≤40, sub ≤90 char;
ranking ≤3 baris + baris "lainnya".
Pandas untuk MA + anomali tren; fallback Python murni bila tak ada.
Korelasi Pearson Python murni (tanpa dependensi).
"""
import datetime
import json
import os
import pathlib
import sys
import time

METRIC_VERSION = "v4-20261013"
SNAP_NAME = ".ana_insight.json"
ROOT = pathlib.Path(__file__).resolve().parent

# Label ramah publik (Q1): nama tabel internal tak keluar ke JSON.
SRC_LABEL = "DB operasional SIMOGE"

# Allowlist template (planner = pilihan eksplisit, bukan SQL bebas).
ALLOW = {
    "produksi_year_to_date", "aktivitas_trend", "aktivitas_agregat",
    "produksi_per_wilayah", "produksi_trend",
}

_DEF = None


def _log(msg):
    try:
        sys.stderr.write(f"  [insight {time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _simoge():
    for cand in (
        ROOT / "profile-dist/skills/software-development/simoge-business/scripts",
        pathlib.Path.home() / ".hermes/profiles/anna/skills/software-development/simoge-business/scripts",
    ):
        if (cand / "simoge_db.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            import simoge_db  # noqa: E402
            return simoge_db
    raise RuntimeError("simoge_db tak ditemukan")


def _rows(res):
    return (res or {}).get("rows", []) if isinstance(res, dict) else []


def _fresh_ok(max_date, limit_days):
    """Stale = data terakhir lebih tua dari batas → fallback, bukan badge negatif."""
    try:
        if not max_date:
            return False
        if isinstance(max_date, str):
            max_date = datetime.date.fromisoformat(max_date[:10])
        elif isinstance(max_date, datetime.datetime):
            max_date = max_date.date()
        return (datetime.date.today() - max_date).days <= limit_days
    except Exception:
        return False


def _pct(cur, prev):
    try:
        if prev is None or float(prev) == 0:
            return None
        return round((float(cur) - float(prev)) * 100.0 / float(prev), 1)
    except Exception:
        return None


def _fmt_id(n):
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except Exception:
        return "0"


def _short(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _ma_anomaly(vals):
    """Moving-average(3) + flag anomali. Pandas bila ada, Python murni bila tak ada."""
    vals = [float(v or 0) for v in vals]
    try:
        import pandas as pd  # noqa: E402
        s = pd.Series(vals, dtype=float)
        ma = s.rolling(3, min_periods=1).mean().round(1).tolist()
        _std = s.std(skipna=True)
        try:
            std = float(_std)  # type: ignore[arg-type]
        except Exception:
            std = 0.0
        anom = [bool(std > 0 and abs(v - m) > 2 * std) for v, m in zip(vals, ma)]
        return [float(x) for x in ma], anom
    except Exception:
        ma = []
        for i, v in enumerate(vals):
            w = vals[max(0, i - 2): i + 1]
            ma.append(round(sum(w) / len(w), 1))
        avg = sum(vals) / len(vals) if vals else 0
        anom = [bool(avg > 0 and abs(v - avg) > 2 * avg) for v in vals]
        return ma, anom


def _tpl_text(label, cur, prev, pct, stale_info=None):
    """Template teks deterministik (tanpa narasi bebas)."""
    if stale_info:
        return (f"Data {label} belum diperbarui",
                f"Terakhir {stale_info} — angka kondisi terakhir.")
    if pct is None:
        return (f"Kondisi {label} relatif stabil",
                "Periode pembanding belum tersedia.")
    if abs(pct) < 10:
        return (f"Kondisi {label} relatif stabil",
                f"Perubahan {pct:+}% vs periode lalu.")
    arah = "meningkat" if pct > 0 else "menurun"
    return (f"{label} {arah} {abs(pct)}%",
            f"Dari {_fmt_id(prev)} menjadi {_fmt_id(cur)} vs lalu.")


def _card(domain, metric_key, label, value, unit, change, summary,
          p_start, p_end, calc_at, fresh, status, extra=None):
    c = {
        "domain": domain,
        "metric_key": metric_key,
        "metric_version": METRIC_VERSION,
        "title": "",
        "metric_label": label,
        "value": value,
        "unit": unit,
        "change_percent": change,
        "summary": _short(summary, 110),
        "period": {"start": p_start, "end": p_end},
        "calculated_at": calc_at,
        "data_terbaru": "",
        "freshness": fresh,
        "status": status,
        "sumber": SRC_LABEL,
    }
    if extra:
        c.update(extra)
    c["title"], _ = _tpl_text(label, value, None, change,
                              None if status == "valid" else summary)
    return c


def _slide(kind, title, headline, sub, extra=None):
    """Satu layar rotasi. kind: stat|rank|chart.

    v4: TIAP slide WAJIB bawa chart (komposisi 50/50) — panggil hanya
    dengan extra={"chart": ...} atau extra={"rows","chart"}. Teks pendek:
    headline ≤40, sub ≤90 char.
    """
    s = {"kind": kind, "title": _short(title, 24),
         "headline": _short(headline, 40), "sub": _short(sub, 90)}
    if extra:
        s.update(extra)
    return s


def _rank3(rank):
    """Ranking ringkas: 3 teratas + baris 'lainnya' (teks tak kepanjangan).

    Tiap baris bawa "c" = warna ambang bisnis pct-nya (sumber tunggal
    _ach_color) agar teks ranking frontend ikut aturan yang sama dengan
    batang chart-nya. pct None (tak diketahui) = abu netral bawaan aturan.
    """
    top = (rank or [])[:3]
    rest_n = max(len(rank or []) - 3, 0)
    rows = [{"nama": r["nama"], "kg": r["kg"], "pct": r.get("pct"),
             "c": _ach_color(r.get("pct")),
             "attn": _needs_attention(r.get("pct"))} for r in top]
    if rest_n:
        rows.append({"nama": f"+{rest_n} wilayah lain", "kg": None, "pct": None})
    return rows


def _pearson(xs, ys):
    """Korelasi Pearson Python murni. Return None bila tak terdefinisi."""
    try:
        n = len(xs)
        if n != len(ys) or n < 3:
            return None
        mx = sum(xs) / n
        my = sum(ys) / n
        sxx = sum((x - mx) ** 2 for x in xs)
        syy = sum((y - my) ** 2 for y in ys)
        if sxx <= 0 or syy <= 0:
            return None
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        return round(sxy / (sxx ** 0.5 * syy ** 0.5), 2)
    except Exception:
        return None


# Aturan warna capaian bisnis (v5): merah 0–50 · kuning 51–75 ·
# oranye 76–99 · hijau 100–110 · biru ≥111. Dipakai chart capaian +
# teks persentase agar artinya langsung terbaca.
_ACH_RED = "#DC2626"
_ACH_YELLOW = "#CA8A04"
_ACH_ORANGE = "#EA580C"
_ACH_GREEN = "#059669"
_ACH_BLUE = "#2563EB"
_ACH_NONE = "#64748B"


def _ach_color(pct):
    """Warna ambang bisnis untuk persen capaian. None = abu netral."""
    try:
        if pct is None:
            return _ACH_NONE
        v = float(pct)
        if v < 0:
            return _ACH_NONE
        if v <= 50:
            return _ACH_RED
        if v <= 75:
            return _ACH_YELLOW
        if v < 100:
            return _ACH_ORANGE
        if v <= 110:
            return _ACH_GREEN
        return _ACH_BLUE
    except Exception:
        return _ACH_NONE


def _ach_legend():
    """Legenda ambang bisnis untuk payload chart — sumber tunggal tampilan
    rentang+warna (frontend wajib render ini, bukan hardcode ulang)."""
    return [
        {"range": "0–50", "color": _ACH_RED},
        {"range": "51–75", "color": _ACH_YELLOW},
        {"range": "76–99", "color": _ACH_ORANGE},
        {"range": "100–110", "color": _ACH_GREEN},
        {"range": "111+", "color": _ACH_BLUE},
    ]


def _needs_attention(pct):
    """Capaian zona merah/kuning (<75%) wajib jadi perhatian di UI.

    Diturunkan dari WARNA — bukan ambang kedua — sehingga otomatis ikut
    bila rentang _ach_color berubah. Frontend hanya baca flag ini."""
    return _ach_color(pct) in (_ACH_RED, _ACH_YELLOW)


def _chart(ctype, labels, series, colors=None):
    """Payload chart generik: {ctype: line|bar|hbar|donut, labels, datasets:[{label,data}]}.

    colors opsional: list warna per kategori (hbar/bar) atau per dataset
    (line). Bila ada, painter memakainya — mis. warna ambang bisnis
    capaian. Tanpa colors = palet netral + highlight/muted slide.
    """
    c = {"ctype": ctype, "labels": [str(x) for x in labels],
         "datasets": [{"label": str(lb), "data": [float(v or 0) for v in data]}
                      for lb, data in series]}
    if colors:
        c["colors"] = [str(x) for x in colors]
    return c


def build():
    """Jalankan kalkulasi penuh. Return snapshot dict. Raise bila DB mati total."""
    t0 = time.time()
    sdb = _simoge()
    today = datetime.date.today()
    y, m = today.year, today.month
    calc_at = today.isoformat()
    log_lines = []
    half = 1 if today.day <= 15 else 2

    def run_logged(name, **kw):
        t = time.perf_counter()
        r = sdb.run(name, **kw)
        ms = round((time.perf_counter() - t) * 1000, 1)
        log_lines.append(f"{name} {kw} rows={r.get('row_count', '?')} {ms}ms")
        return r

    # ══ Domain 1: PRODUKSI — pencapaian vs target kumulatif ══
    ytd = run_logged("produksi_year_to_date", tahun=y, bulan=m, day=today.day)
    ytd_row = (_rows(ytd) or [{}])[0]
    real_kg = float(ytd_row.get("total_kg") or 0)
    try:
        mx = sdb.q("SELECT MAX(tanggal) AS mx FROM getah_aktivitas_penerimaan")
        prod_max = str((_rows(mx) or [{}])[0].get("mx") or "")
    except Exception:
        prod_max = ""
    try:
        qr = sdb.q("SELECT COALESCE(SUM(target_rkap),0) AS t FROM getah_petak"
                   " WHERE tahun_rtt=%s", (y,))
        base_target = float((_rows(qr) or [{}])[0].get("t") or 0)
    except Exception:
        base_target = 0.0
    try:
        pct_kum = float(sdb._target_pct(y, m, half) or 0)
    except Exception:
        pct_kum = 0.0
    target_kg = round(base_target * pct_kum / 100, 1)
    achieve = round(real_kg * 100 / target_kg, 1) if target_kg else None
    prod_fresh = _fresh_ok(prod_max, 21)
    tr = run_logged("produksi_trend", tahun=y)
    tmap = {(r.get("bulan"), r.get("periode")): float(r.get("total_kg") or 0)
            for r in _rows(tr)}
    series = [{"label": f"{b:02d}-P{p}", "value": tmap.get((b, p), 0)}
              for b in range(1, 13) for p in (1, 2)
              if (b, p) <= (m, half)][-6:]
    # tren bulanan penuh + MA + anomali (pandas bila ada)
    monthly = []
    for b in range(1, 13):
        v = round(tmap.get((b, 1), 0) + tmap.get((b, 2), 0), 1)
        monthly.append(v)
    ma3, _anoms_unused = _ma_anomaly(monthly)
    rk = []
    try:
        pw = run_logged("produksi_per_wilayah", tahun=y, bulan=m, periode=half,
                        level="kode_bkph")
        rk = sorted(_rows(pw), key=lambda r: float(r.get("actual_kg") or 0),
                    reverse=True)
        rank = [{"nama": r.get("nama_wilayah"),
                 "kg": float(r.get("actual_kg") or 0),
                 "pct": float(r.get("achievement_pct") or 0)
                 if r.get("achievement_pct") is not None else None}
                for r in rk[:5] if r.get("nama_wilayah")]
        rank_all = [{"nama": r.get("nama_wilayah"),
                     "kg": float(r.get("actual_kg") or 0)}
                    for r in rk if r.get("nama_wilayah")]
    except Exception as e:
        log_lines.append(f"ranking SKIP {type(e).__name__}")
        rank, rank_all = [], []
    if not prod_fresh or not target_kg:
        c1 = _card("production", "prod_achieve", "Pencapaian produksi",
                   achieve if achieve is not None else 0, "%", None,
                   f"Terakhir {prod_max or '—'}",
                   f"{y}-01-01", str(today), calc_at,
                   "stale", "stale",
                   {"realisasi_kg": real_kg, "target_kg": target_kg,
                    "ranking_wilayah": rank, "series": series,
                    "data_terbaru": prod_max})
        c1["title"], c1["summary"] = (
            f"Capaian {achieve}% dari target" if achieve is not None
            else "Data produksi belum diperbarui",
            f"Realisasi {_fmt_id(real_kg)} kg / target {_fmt_id(target_kg)} kg"
            f" — terakhir {prod_max or '—'}.")
    else:
        c1 = _card("production", "prod_achieve", "Pencapaian produksi",
                   achieve, "%", None,
                   f"Realisasi {_fmt_id(real_kg)} kg / target "
                   f"{_fmt_id(target_kg)} kg.",
                   f"{y}-01-01", str(today), calc_at, "fresh", "valid",
                   {"realisasi_kg": real_kg, "target_kg": target_kg,
                    "ranking_wilayah": rank, "series": series,
                    "data_terbaru": prod_max})
        c1["title"] = (f"Capaian {achieve}% dari target"
                       if achieve is not None else "Target belum tersedia")
    mon_lb = [f"{b:02d}" for b in range(1, 13)]
    rk3 = _rank3(rank)
    low_name = rank_all[-1]["nama"] if rank_all else "—"
    low_kg = rank_all[-1]["kg"] if rank_all else 0
    # Tren jujur v5.2: "tak ada anomali" ≠ "stabil". Ukur arah dari bulan
    # berisi data saja (ekor nol = data tertunda, bukan nol produksi):
    # rata-rata 3 bln terakhir berisi data vs 3 bln pertama.
    _dm = monthly[:m]
    _nz = [v for v in _dm if v > 0]
    if len(_nz) >= 4 and sum(_nz[:3]) > 0:
        _chg = round((sum(_nz[-3:]) / 3 - sum(_nz[:3]) / 3) * 100 / (sum(_nz[:3]) / 3), 1)
    else:
        _chg = None
    if _chg is None:
        _tren_head = "Belum ada tren"
    elif abs(_chg) < 10:
        _tren_head = "Tren stabil"
    elif _chg > 0:
        _tren_head = f"Tren naik {_chg}%"
    else:
        _tren_head = f"Tren turun {abs(_chg)}%"
    _tren_sub = "3 bln awal vs 3 bln akhir berisi data."
    if any(v == 0 for v in _dm):
        _tren_sub += " Ekor nol = data tertunda."
    c1["slides"] = [
        _slide("stat", "Pencapaian",
               "Target tercapai" if (achieve is not None and achieve >= 100) else "Belum tercapai",
               "Capaian vs sisa — angka di chart.",
               {"chart": _chart("hbar",
                                ["Realisasi", "Sisa target"],
                                [("kg", [real_kg, max(target_kg - real_kg, 0)])],
                                colors=[_ach_color(achieve), "#CBD5E1"]),
                "ach_color": _ach_color(achieve),
                 "attn": _needs_attention(achieve)}),
        _slide("rank", "Wilayah teratas",
               f"{rk3[0]['nama']} memimpin" if rk3 and rk3[0].get("kg") is not None else "—",
               "Urutan YTD — angka di chart.",
               {"rows": rk3,
                "chart": _chart("hbar", [r["nama"] for r in rk3 if r.get("kg") is not None],
                                [("kg", [r["kg"] for r in rk3 if r.get("kg") is not None])],
                                colors=[_ach_color(r.get("pct")) for r in rk3 if r.get("kg") is not None]),
                "highlight": 0}),
        _slide("chart", "Tren + rata-rata",
               _tren_head,
               _tren_sub,
               {"chart": _chart("line", mon_lb,
                                [("Kg", monthly), ("Rata-rata", ma3)])}),
        _slide("stat", "Cakupan wilayah",
               f"{len(rank_all)} wilayah · terbawah {low_name}",
               f"{low_name} {_fmt_id(low_kg)} kg — dorong kejar.",
               {"chart": _chart("bar", [r["nama"] for r in rk3 if r.get("kg") is not None],
                                [("kg", [r["kg"] for r in rk3 if r.get("kg") is not None])])}),
        _slide("stat", "Defisit target",
               f"Kurang {_fmt_id(max(target_kg - real_kg, 0))} kg",
               f"Akselerasi {round(max(target_kg - real_kg, 0) / max(target_kg, 1) * 100, 1)}% sisa target.",
               {"chart": _chart("hbar", ["Tercapai", "Kurang"],
                                [("kg", [real_kg, max(target_kg - real_kg, 0)])],
                                colors=[_ach_color(achieve), "#CBD5E1"]),
                "ach_color": _ach_color(achieve),
                 "attn": _needs_attention(achieve)}),
    ]

    # ══ Domain 2: LAPANGAN — aktivitas + penyadap ══
    atr = run_logged("aktivitas_trend", tahun=y)
    amap = {(r.get("bulan"), r.get("periode")): r for r in _rows(atr)}
    cur_r = amap.get((m, half), {})
    if half == 2:
        prev_r = amap.get((m, 1), {})
    else:
        pm = m - 1 if m > 1 else 12
        prev_r = amap.get((pm, 2), {})
    akt_val = int(cur_r.get("n_aktivitas") or 0)
    akt_prev = int(prev_r.get("n_aktivitas") or 0)
    akt_pct = _pct(akt_val, akt_prev)
    penyadap = int(cur_r.get("n_penyadap") or 0)
    petak_akt = int(cur_r.get("n_petak_aktif") or 0)
    try:
        mx2 = sdb.q("SELECT MAX(tgl_pembaharuan) AS mx FROM getah_aktivitas_sadap")
        akt_max = str((_rows(mx2) or [{}])[0].get("mx") or "")
    except Exception:
        akt_max = ""
    akt_fresh = _fresh_ok(akt_max, 14)
    d0, d1 = sdb.period_bounds(y, m, half)
    # komposisi tahap pembaharuan bulan berjalan (donut)
    try:
        ag = run_logged("aktivitas_agregat", tahun=y, bulan=m, periode=0,
                        grup_by="pembaharuan")
        comp = [(r.get("label") or r.get("dim"), int(r.get("count") or 0))
                for r in _rows(ag)]
    except Exception as e:
        log_lines.append(f"komposisi SKIP {type(e).__name__}")
        comp = []
    # tren aktivitas 6 periode + MA
    a6 = []
    yy, mm, hh = y, m, half
    for _ in range(6):
        a6.insert(0, amap.get((mm, hh), {}).get("n_aktivitas", 0))
        if hh == 1:
            hh = 2
            mm -= 1
            if mm < 1:
                mm, yy = 12, yy - 1
        else:
            hh = 1
    a6 = [int(v or 0) for v in a6]
    ama, _aa = _ma_anomaly(a6)
    if not akt_fresh:
        c2 = _card("field_ops", "aktiv_cur_prev", "Aktivitas sadap", akt_val,
                   "aktivitas", None, f"Terakhir {akt_max or '—'}",
                   d0, d1, calc_at, "stale", "stale",
                   {"penyadap_aktif": penyadap, "petak_aktif": petak_akt,
                    "data_terbaru": akt_max})
        c2["title"], c2["summary"] = _tpl_text("Aktivitas sadap", None, None, None, akt_max or "—")
    else:
        c2 = _card("field_ops", "aktiv_cur_prev", "Aktivitas sadap", akt_val,
                   "aktivitas", akt_pct, "", d0, d1, calc_at, "fresh", "valid",
                   {"penyadap_aktif": penyadap, "petak_aktif": petak_akt,
                    "prev": akt_prev, "data_terbaru": akt_max})
        c2["title"], c2["summary"] = _tpl_text("Aktivitas sadap", akt_val, akt_prev, akt_pct)
    c2["slides"] = [
        _slide("stat", "Aktivitas",
               f"{_fmt_id(akt_val)}" + (f" ({akt_pct:+}%)" if akt_pct is not None else ""),
               f"Periode {y}-{m:02d}-P{half} vs lalu {akt_prev}.",
               {"chart": _chart("line",
                                [f"P{i + 1}" for i in range(6)],
                                [("Aktivitas", a6), ("Rata-rata", ama)])}),
        _slide("stat", "Penyadap & petak",
               f"{_fmt_id(penyadap)} penyadap · {_fmt_id(petak_akt)} petak",
               "Aktif periode berjalan.",
               {"chart": _chart("hbar", ["Penyadap", "Petak"],
                                [("n", [penyadap, petak_akt])])}),
        _slide("chart", "Komposisi tahap",
               " · ".join(f"{lb or '?'} {c}" for lb, c in comp[:4]) or "—",
               "Bulan berjalan per tahap.",
               {"chart": _chart("donut", [lb or "?" for lb, _ in comp],
                                [("n", [c for _, c in comp])])}),
        _slide("chart", "Beban per penyadap",
               f"{round(akt_val / max(penyadap, 1), 1)} aktivitas/orang",
               "Rata-rata beban periode berjalan.",
               {"chart": _chart("hbar", ["Aktivitas", "Penyadap"],
                                [("n", [akt_val, penyadap])])}),
        _slide("stat", "Cakupan petak",
               f"{_fmt_id(petak_akt)} petak aktif",
               "Petak tersentuh sadapan periode ini.",
               {"chart": _chart("line",
                                [f"P{i + 1}" for i in range(6)],
                                [("Aktivitas", a6)])}),
    ]

    # ══ SCOREBOARD hero — angka GLOBAL: YTD + periode berjalan + hari ini ══
    # Satu hitung di cron (bukan query per pengunjung). Nol = data tertunda
    # (MAX tanggal 2026-08-27), bukan nol produksi — frontend wajib tulis jujur.
    try:
        q_per = sdb.q("SELECT COUNT(*) AS n, COALESCE(SUM(berat_penerimaan),0) AS kg,"
                      " MAX(tanggal) AS mx FROM getah_aktivitas_penerimaan"
                      " WHERE tanggal>=%s AND tanggal<=%s", (d0, d1))
        q_td = sdb.q("SELECT COUNT(*) AS n, COALESCE(SUM(berat_penerimaan),0) AS kg"
                     " FROM getah_aktivitas_penerimaan WHERE tanggal=%s", (str(today),))
        _rp = (_rows(q_per) or [{}])[0]
        _rt = (_rows(q_td) or [{}])[0]
        scoreboard = {
            "ytd_kg": real_kg, "target_kg": target_kg,
            "capaian_pct": achieve, "capaian_color": _ach_color(achieve),
            "ytd_attention": _needs_attention(achieve),
            "periode_kg": float(_rp.get("kg") or 0),
            "periode_n": int(_rp.get("n") or 0),
            "periode_label": f"{y}-{m:02d}-P{half}",
            "periode_max": str(_rp.get("mx") or ""),
            "hari_kg": float(_rt.get("kg") or 0),
            "hari_n": int(_rt.get("n") or 0),
            "hari_tgl": str(today),
            "periode_half": half,
            "tahun": y,
            "data_terbaru": prod_max,
        }
        log_lines.append(f"scoreboard ytd={real_kg} per={scoreboard['periode_kg']} today={scoreboard['hari_kg']}")
    except Exception as e:
        log_lines.append(f"scoreboard SKIP {type(e).__name__}: {str(e)[:120]}")
        scoreboard = None

    # ══ Domain RENCANA — rencana_berat vs target per periode ══
    # Akurasi skema: join rencana→aktivitas via id_rencana (varchar cocok
    # 19.578/20.184 = 97%). Target per periode = _target_pct = persen RO
    # kumulatif × Σ target_rkap (definisi tunggal simoge_db, skalar —
    # bukan JOIN per-baris yang menggandakan target).
    # Hasil digabung ke kartu SUPPLY (switch domain otomatis via rotasi).
    try:
        qr_m = sdb.q("SELECT MONTH(tanggal_rencana) AS b, COUNT(*) AS n,"
                     " COALESCE(SUM(rencana_berat),0) AS kg FROM getah_rencana_aktivitas"
                     " WHERE YEAR(tanggal_rencana)=%s GROUP BY b", (y,))
        plan_m = {int(r.get("b") or 0): (int(r.get("n") or 0), float(r.get("kg") or 0))
                  for r in _rows(qr_m)}
        qr_mx = sdb.q("SELECT MAX(tanggal_rencana) AS mx FROM getah_rencana_aktivitas"
                      " WHERE YEAR(tanggal_rencana)=%s", (y,))
        plan_max = str((_rows(qr_mx) or [{}])[0].get("mx") or "")
        plan_ytd = round(sum(kg for _b, (_n, kg) in plan_m.items() if _b <= m), 1)
        plan_cnt = sum(n for _b, (n, _kg) in plan_m.items() if _b <= m)
        tgt_cum = {}
        for _b in range(1, 13):
            try:
                _p = float(sdb._target_pct(y, _b, 2) or 0)
            except Exception:
                _p = 0.0
            tgt_cum[_b] = round(base_target * _p / 100, 1)
        plan_tgt = tgt_cum.get(m, 0)
        plan_pct = round(plan_ytd * 100 / plan_tgt, 1) if plan_tgt else None
        try:
            ql = sdb.q("SELECT COUNT(*) AS tot, SUM(CASE WHEN a.id_rencana IS NOT NULL"
                       " AND a.id_rencana<>'' THEN 1 ELSE 0 END) AS linkd"
                       " FROM getah_aktivitas_sadap a WHERE YEAR(a.tgl_pembaharuan)=%s", (y,))
            _lr = (_rows(ql) or [{}])[0]
            link_tot = int(_lr.get("tot") or 0)
            link_n = int(_lr.get("linkd") or 0)
        except Exception:
            link_tot, link_n = 0, 0
        link_pct = round(link_n * 100 / link_tot, 1) if link_tot else None
        plan_ok = True
    except Exception as e:
        log_lines.append(f"plan SKIP {type(e).__name__}: {str(e)[:120]}")
        plan_ok = False
        plan_m, plan_ytd, plan_cnt, plan_max = {}, 0, 0, ""
        plan_tgt, plan_pct, link_tot, link_n, link_pct, tgt_cum = 0, None, 0, 0, None, {}

    # ══ Domain 3: SUPPLY — terima → perni → angkut ══
    try:
        qt = sdb.q("SELECT COALESCE(SUM(berat_penerimaan),0) AS s, COUNT(*) AS n,"
                   " MAX(tanggal) AS mx FROM getah_aktivitas_penerimaan"
                   " WHERE YEAR(tanggal)=%s", (y,))
        qp = sdb.q("SELECT COALESCE(SUM(total_berat_pgt),0) AS s, COUNT(*) AS n,"
                   " MAX(tanggal) AS mx FROM getah_perni WHERE YEAR(tanggal)=%s", (y,))
        qa = sdb.q("SELECT COALESCE(SUM(total_berat_pgt),0) AS s, COUNT(*) AS n,"
                   " MAX(tanggal) AS mx FROM getah_pengangkutan WHERE YEAR(tanggal)=%s", (y,))
        rt, rp, ra = (_rows(qt) or [{}])[0], (_rows(qp) or [{}])[0], (_rows(qa) or [{}])[0]
        st, sp, sa = (float(rt.get("s") or 0), float(rp.get("s") or 0),
                      float(ra.get("s") or 0))
        mx3 = str(rt.get("mx") or rp.get("mx") or "")
        sup_fresh = _fresh_ok(mx3, 21)
        efi_tp = round(sp * 100 / st, 1) if st else None
        efi_pa = round(sa * 100 / sp, 1) if sp else None
        if not sup_fresh:
            c3 = _card("supply", "supply_recv", "Aliran hasil", st, "kg",
                       None, f"Terakhir {mx3 or '—'}",
                       f"{y}-01-01", str(today), calc_at, "stale", "stale",
                       {"terima_kg": st, "perni_kg": sp, "angkut_kg": sa,
                        "efi_terima_perni": efi_tp, "efi_perni_angkut": efi_pa,
                        "n_terima": int(rt.get("n") or 0),
                        "n_perni": int(rp.get("n") or 0),
                        "n_angkut": int(ra.get("n") or 0),
                        "data_terbaru": mx3})
            c3["title"], c3["summary"] = _tpl_text("Aliran hasil", None, None, None, mx3 or "—")
        else:
            c3 = _card("supply", "supply_recv", "Aliran hasil", st, "kg",
                       None,
                       f"Terima {_fmt_id(st)} → perni {_fmt_id(sp)} → "
                       f"angkut {_fmt_id(sa)} kg.",
                       f"{y}-01-01", str(today), calc_at, "fresh", "valid",
                       {"terima_kg": st, "perni_kg": sp, "angkut_kg": sa,
                        "efi_terima_perni": efi_tp, "efi_perni_angkut": efi_pa,
                        "n_terima": int(rt.get("n") or 0),
                        "n_perni": int(rp.get("n") or 0),
                        "n_angkut": int(ra.get("n") or 0),
                        "data_terbaru": mx3})
            c3["title"] = "Aliran terima → perni → angkut"
    except Exception as e:
        log_lines.append(f"supply SKIP {type(e).__name__}: {str(e)[:120]}")
        c3 = _card("supply", "supply_recv", "Aliran hasil", 0, "kg",
                   None, "Kalkulasi gagal — snapshot lama dipertahankan.",
                   f"{y}-01-01", str(today), calc_at, "unknown", "error")
    _fun = _chart("hbar", ["Terima", "Perni", "Angkut"],
                  [("kg", [c3.get("terima_kg", 0), c3.get("perni_kg", 0),
                           c3.get("angkut_kg", 0)])])
    # Tren bulanan 3-seri (terima/perni/angkut per bulan) — chart di tiap slide.
    try:
        qtm = sdb.q("SELECT MONTH(tanggal) AS b, COALESCE(SUM(berat_penerimaan),0) AS kg"
                    " FROM getah_aktivitas_penerimaan WHERE YEAR(tanggal)=%s GROUP BY b", (y,))
        qpm = sdb.q("SELECT MONTH(tanggal) AS b, COALESCE(SUM(total_berat_pgt),0) AS kg"
                    " FROM getah_perni WHERE YEAR(tanggal)=%s GROUP BY b", (y,))
        qam = sdb.q("SELECT MONTH(tanggal) AS b, COALESCE(SUM(total_berat_pgt),0) AS kg"
                    " FROM getah_pengangkutan WHERE YEAR(tanggal)=%s GROUP BY b", (y,))
        tmap_m = {int(r.get("b") or 0): float(r.get("kg") or 0) for r in _rows(qtm)}
        pmap_m = {int(r.get("b") or 0): float(r.get("kg") or 0) for r in _rows(qpm)}
        amap_m = {int(r.get("b") or 0): float(r.get("kg") or 0) for r in _rows(qam)}
    except Exception as e:
        log_lines.append(f"supply-tren SKIP {type(e).__name__}")
        tmap_m, pmap_m, amap_m = {}, {}, {}
    _tser = [round(tmap_m.get(b, 0), 1) for b in range(1, 13)]
    _pser = [round(pmap_m.get(b, 0), 1) for b in range(1, 13)]
    _aser = [round(amap_m.get(b, 0), 1) for b in range(1, 13)]
    _sup_tren = _chart("line", mon_lb, [("Terima", _tser), ("Perni", _pser), ("Angkut", _aser)])
    c3["slides"] = [
        _slide("chart", "Alur volume",
               f"{_fmt_id(c3.get('terima_kg', 0))} → "
               f"{_fmt_id(c3.get('angkut_kg', 0))} kg",
               "Penerimaan, Angkut, Perni — angkut mengurangi persediaan.", {"chart": _fun}),
        _slide("chart", "Tren 3 tahap",
               f"Puncak {max(range(12), key=lambda i: _tser[i]):02d}" if max(_tser or [0]) > 0 else "Belum ada data",
               "Terima vs angkut vs perni per bulan.",
               {"chart": _sup_tren}),
        _slide("stat", "Efisiensi terima→perni",
               f"{c3.get('efi_terima_perni')}%" if c3.get("efi_terima_perni") is not None else "—",
               f"{_fmt_id(c3.get('n_terima', 0))} terima · {_fmt_id(c3.get('n_perni', 0))} perni.",
               {"chart": _chart("hbar", ["Perni", "Susut"],
                                [("kg", [c3.get("perni_kg", 0),
                                         max(c3.get("terima_kg", 0) - c3.get("perni_kg", 0), 0)])]),
                "highlight": -1, "muted": [1]}),
        _slide("stat", "Perni vs angkut",
               f"{c3.get('efi_perni_angkut')}%" if c3.get("efi_perni_angkut") is not None else "—",
               "Rasio angkut/perni — angkut tarik stok, bisa >100%.",
               {"chart": _chart("hbar", ["Angkut", "Di jalan"],
                                [("kg", [c3.get("angkut_kg", 0),
                                         max(c3.get("perni_kg", 0) - c3.get("angkut_kg", 0), 0)])]),
                "highlight": -1, "muted": [1]}),
    ]
    # ── Switch domain otomatis: slides RENCANA digabung ke kartu ALIRAN ──
    if plan_ok:
        _plan_ser = [round(plan_m.get(b, (0, 0))[1], 1) for b in range(1, 13)]
        _tgt_ser = [tgt_cum.get(b, 0) for b in range(1, 13)]
        c3["slides"] += [
            _slide("chart", "Rencana vs target",
                   f"{plan_pct}%" if plan_pct is not None else "—",
                   f"Rencana {_fmt_id(plan_ytd)} / target {_fmt_id(plan_tgt)} kg.",
                   {"chart": _chart("line", mon_lb,
                                    [("Rencana", _plan_ser), ("Target", _tgt_ser)]),
                    "ach_color": _ach_color(plan_pct),
                     "attn": _needs_attention(plan_pct)}),
            _slide("stat", "Rencana terealisasi",
                   f"{link_pct}%" if link_pct is not None else "—",
                   f"{_fmt_id(link_n)} dari {_fmt_id(link_tot)} aktivitas berencana.",
                   {"chart": _chart("hbar", ["Berencana", "Tanpa rencana"],
                                    [("n", [link_n, max(link_tot - link_n, 0)])]),
                    "highlight": -1, "muted": [1]}),
        ]

    # ══ Domain 4: OPTIMASI — bongkor GROUP BY dinamis ══
    try:
        qd = sdb.q("SELECT COUNT(DISTINCT kode_divre) AS n FROM getah_petak"
                   " WHERE tahun_rtt=%s", (y,))
        n_divre = int((_rows(qd) or [{}])[0].get("n") or 0)
        if n_divre > 1:
            lvl, ncol = "kode_divre", "divre"
        else:
            lvl, ncol = "kode_bkph", "bkph"
        qb = sdb.q(
            f"SELECT p.{lvl} AS kode, MAX(p.{ncol}) AS nama, COUNT(*) AS n,"
            f" ROUND(COALESCE(SUM(p.luas_baku),0),1) AS luas"
            f" FROM getah_petak p WHERE p.tahun_rtt=%s AND NOT EXISTS"
            f" (SELECT 1 FROM getah_andil a WHERE a.kode_evapot=p.kode_evapot)"
            f" GROUP BY p.{lvl} ORDER BY n DESC", (y,))
        rows_b = _rows(qb)
        tot_b = sum(int(r.get("n") or 0) for r in rows_b)
        tot_l = round(sum(float(r.get("luas") or 0) for r in rows_b), 1)
        spots = [{"kode": r.get("kode"), "nama": r.get("nama"),
                  "n": int(r.get("n") or 0), "luas": float(r.get("luas") or 0)}
                 for r in rows_b]
        c4 = _card("optimization", "opt_bongkor", "Optimalisasi petak", tot_b,
                   "petak", None,
                   f"{_fmt_id(tot_b)} petak belum memiliki andil "
                   f"({_fmt_id(tot_l)} ha).",
                   f"{y}-01-01", str(today), calc_at, "fresh", "valid",
                   {"level": lvl, "total_luas": tot_l, "spots": spots,
                    "data_terbaru": str(today)})
        c4["title"] = f"{_fmt_id(tot_b)} petak belum memiliki andil"
        # ── Peta scatter nyata: centroid polygon bongkor dihitung cron ──
        # petak_polygon.polygon = GeoJSON text (~1,5KB rata-rata); yang
        # disimpan hanya 1 titik per petak (x,y 0-100 + nama + luas).
        # Akurasi: join kode_evapot persis (809/810 petak 2026 cocok).
        # Peta per wilayah: capaian BKPH = actual / target wilayah
        # (run produksi_per_wilayah sudah ada di atas) → tiap titik
        # scatter diwarnai ambang wilayahnya (bukan satu hijau).
        try:
            _ach_by_name = {str(r.get("nama_wilayah") or "").strip().upper(): r.get("achievement_pct")
                            for r in rk}
        except Exception:
            _ach_by_name = {}
        try:
            qp = sdb.q(
                "SELECT pp.kode_evapot AS ev, pp.polygon AS pg,"
                " MAX(pp.bkph) AS nama, MAX(pp.luas_ha) AS luas"
                " FROM petak_polygon pp JOIN getah_petak p"
                " ON p.kode_evapot=pp.kode_evapot AND p.tahun_rtt=%s"
                " WHERE NOT EXISTS (SELECT 1 FROM getah_andil a"
                " WHERE a.kode_evapot=p.kode_evapot)"
                " GROUP BY pp.kode_evapot, pp.polygon", (y,))
            _pts = []
            for r in _rows(qp):
                try:
                    g = json.loads(r.get("pg") or "")
                    ring = (g.get("coordinates") or [[[]]])[0]
                    if not ring:
                        continue
                    # centroid = rata-rata ring luar (cukup untuk scatter)
                    n = len(ring)
                    cx = sum(p[0] for p in ring) / n
                    cy = sum(p[1] for p in ring) / n
                    _nm = str(r.get("nama") or "")
                    _pts.append({"lon": cx, "lat": cy, "nama": _nm,
                                 "luas": float(r.get("luas") or 0),
                                 "c": _ach_color(_ach_by_name.get(_nm.strip().upper()))})
                except Exception:
                    continue
            if _pts:
                lons = [p["lon"] for p in _pts]
                lats = [p["lat"] for p in _pts]
                lo0, lo1 = min(lons), max(lons)
                la0, la1 = min(lats), max(lats)
                dx, dy = (lo1 - lo0) or 1, (la1 - la0) or 1
                for p in _pts:
                    p["x"] = round((p.pop("lon") - lo0) / dx * 100, 1)
                    p["y"] = round(100 - (p.pop("lat") - la0) / dy * 100, 1)
                    p["luas"] = round(p["luas"], 1)
            c4["scatter"] = _pts
            log_lines.append(f"scatter bongkor n={len(_pts)}")
        except Exception as e:
            log_lines.append(f"scatter SKIP {type(e).__name__}: {str(e)[:120]}")
            c4["scatter"] = []
        _big = spots[0] if spots else {"nama": "—", "n": 0, "luas": 0}
        _rk3o = [{"nama": s["nama"], "kg": s["n"], "pct": None} for s in spots[:3]]
        if len(spots) > 3:
            _rk3o.append({"nama": f"+{len(spots) - 3} wilayah lain", "kg": None, "pct": None})
        c4["slides"] = [
            _slide("chart", "Peta sebaran",
                   f"{len(c4['scatter'])} titik petak dipetakan",
                   "Posisi nyata dari polygon — bukan ilustrasi.",
                   {"chart": {"ctype": "scatter", "points": c4["scatter"],
                              "legend": _ach_legend()}}),
            _slide("chart", "Nasional",
                   f"{_fmt_id(tot_b)} petak · {_fmt_id(tot_l)} ha",
                   "Belum berandil — peluang perluasan.",
                   {"chart": _chart(
                       "hbar", [s["nama"] for s in spots],
                       [("petak", [s["n"] for s in spots])]),
                    "highlight": 0}),
            _slide("rank", "Wilayah teratas",
                   f"{_big['nama']} terluas menunggu",
                   "Urutan wilayah — angka di chart.",
                   {"rows": _rk3o,
                    "chart": _chart("hbar", [s["nama"] for s in spots[:5]],
                                    [("petak", [s["n"] for s in spots[:5]])]),
                    "highlight": 0}),
            _slide("chart", "Luas menunggu",
                   f"{_fmt_id(tot_l)} ha belum tergarap",
                   "Luas per wilayah — potensi sadapan.",
                   {"chart": _chart("bar", [s["nama"] for s in spots[:6]],
                                    [("ha", [s["luas"] for s in spots[:6]])]),
                    "highlight": 0}),
            _slide("stat", f"Sorotan {_big['nama']}",
                   f"{_fmt_id(_big['n'])} petak · {_fmt_id(_big['luas'])} ha",
                   "Prioritas andil berikutnya.",
                   {"chart": _chart("hbar", ["Petak", "Luas (ha)"],
                                    [("n", [_big["n"], _big["luas"]])]),
                    "highlight": -1, "muted": [1]}),
        ]
    except Exception as e:
        log_lines.append(f"bongkor SKIP {type(e).__name__}: {str(e)[:120]}")
        c4 = _card("optimization", "opt_bongkor", "Optimalisasi petak", 0,
                   "petak", None, "Kalkulasi gagal — snapshot lama dipertahankan.",
                   f"{y}-01-01", str(today), calc_at, "unknown", "error")
        c4["slides"] = []

    # ══ Domain 5: STRIP KPH — tren produksi per KPH 12 bulan ══
    # Kini fallback 1 KPH; N KPH masuk = seri baru otomatis (top-8 + Lainnya).
    try:
        qk = sdb.q("SELECT MONTH(p.tanggal) AS bl, p.kode_kph AS kode,"
                   " MAX(k.kph) AS nama, COALESCE(SUM(p.berat_penerimaan),0) AS kg"
                   " FROM getah_aktivitas_penerimaan p"
                   " LEFT JOIN kph k ON k.kode_kph = p.kode_kph"
                   " WHERE YEAR(p.tanggal)=%s"
                   " GROUP BY bl, p.kode_kph ORDER BY bl", (y,))
        per_bl = {}
        names = {}
        for r in _rows(qk):
            per_bl.setdefault(int(r.get("bl") or 0), {})[str(r.get("kode"))] = \
                float(r.get("kg") or 0)
            if r.get("nama"):
                names[str(r.get("kode"))] = r.get("nama")
        totals = {}
        for _bl, mp in per_bl.items():
            for k, v in mp.items():
                totals[k] = totals.get(k, 0) + v
        topk = sorted(totals, key=lambda k: totals[k], reverse=True)[:8]
        rest = [k for k in totals if k not in topk]
        sers, sers_lb = [], []
        for k in topk:
            sers.append({"nama": names.get(k, k),
                         "data": [round(per_bl.get(b, {}).get(k, 0), 1)
                                  for b in range(1, 13)]})
            sers_lb.append(names.get(k, k))
        if rest:
            sers.append({"nama": "Lainnya",
                         "data": [round(sum(per_bl.get(b, {}).get(k, 0)
                                            for k in rest), 1)
                                  for b in range(1, 13)]})
        qkm = sdb.q("SELECT MAX(tanggal) AS mx FROM getah_aktivitas_penerimaan"
                    " WHERE YEAR(tanggal)=%s", (y,))
        k_max = str((_rows(qkm) or [{}])[0].get("mx") or "")
        c5 = _card("kphstrip", "kph_trend", "Tren produksi per KPH",
                   round(sum(totals.values()), 1), "kg",
                   None,
                   f"{len(totals)} KPH terpantau — teratas "
                   f"{sers[0]['nama'] if sers else '—'}.",
                   f"{y}-01-01", str(today), calc_at,
                   "fresh" if _fresh_ok(k_max, 21) else "stale",
                   "valid" if _fresh_ok(k_max, 21) else "stale",
                   {"kph_series": sers, "data_terbaru": k_max})
        c5["title"] = "Tren produksi seluruh KPH"
        c5["chart"] = _chart("line", [f"{b:02d}" for b in range(1, 13)],
                             [(s["nama"], s["data"]) for s in sers])
        # ── Korelasi rencana→aktivitas→penerimaan per bulan ──
        # Rencana bulanan vs aktivitas (count) vs penerimaan (kg): 3 Pearson.
        try:
            qat = sdb.q("SELECT MONTH(tgl_pembaharuan) AS b, COUNT(*) AS n"
                        " FROM getah_aktivitas_sadap"
                        " WHERE YEAR(tgl_pembaharuan)=%s GROUP BY b", (y,))
            _am = {int(r.get("b") or 0): int(r.get("n") or 0) for r in _rows(qat)}
        except Exception:
            _am = {}
        _rser = [round(plan_m.get(b, (0, 0))[1], 1) for b in range(1, 13)] if plan_ok else [0] * 12
        _vser = [float(_am.get(b, 0)) for b in range(1, 13)]
        _yser = [round(tmap_m.get(b, 0), 1) for b in range(1, 13)]
        r_ra = _pearson(_rser, _vser)
        r_ap = _pearson(_vser, _yser)
        r_rp = _pearson(_rser, _yser)
        _corr = {"rencana_aktivitas": r_ra, "aktivitas_penerimaan": r_ap,
                 "rencana_penerimaan": r_rp}
        c5["korelasi"] = _corr
        log_lines.append(f"korelasi r_ra={r_ra} r_ap={r_ap} r_rp={r_rp}")
        _corr_txt = ", ".join(
            f"{k.split('_')[0][:3]}→{k.split('_')[1][:3]} {v if v is not None else '—'}"
            for k, v in _corr.items())
        c5["slides"] = [
            _slide("chart", "12 bulan", c5["title"],
                   f"{len(totals)} KPH · 12 bulan.", {"chart": c5["chart"]}),
            _slide("chart", "Korelasi rantai",
                   _corr_txt,
                   "Pearson bulanan — 1 = selaras, 0 = lepas.",
                   {"chart": _chart("hbar", ["Renc→Akt", "Akt→Terima", "Renc→Terima"],
                                    [("r", [r_ra or 0, r_ap or 0, r_rp or 0])]),
                    "highlight": [r_ra or 0, r_ap or 0, r_rp or 0].index(max([r_ra or 0, r_ap or 0, r_rp or 0]))}),
            _slide("chart", "Rencana vs terima",
                   f"r = {r_rp if r_rp is not None else '—'}",
                   "Apakah rencana berujung penerimaan.",
                   {"chart": _chart("line", [f"{b:02d}" for b in range(1, 13)],
                                    [("Rencana", _rser), ("Terima", _yser)])}),
            _slide("chart", "Aktivitas vs terima",
                   f"r = {r_ap if r_ap is not None else '—'}",
                   "Kerja lapangan berbuah produksi.",
                   {"chart": _chart("line", [f"{b:02d}" for b in range(1, 13)],
                                    [("Aktivitas", _vser), ("Terima", _yser)])}),
            _slide("stat", "KPH teratas",
                   f"{sers[0]['nama'] if sers else '—'} memimpin",
                   f"{len(totals)} KPH terpantau tahun ini.",
                   {"chart": _chart("hbar",
                                    [(s["nama"] or "?")[:12] for s in sers[:5]],
                                    [("kg", [round(sum(s["data"]), 1) for s in sers[:5]])]),
                    "highlight": 0}),
        ]
    except Exception as e:
        log_lines.append(f"kphstrip SKIP {type(e).__name__}: {str(e)[:120]}")
        c5 = _card("kphstrip", "kph_trend", "Tren produksi per KPH", 0, "kg",
                   None, "Kalkulasi gagal — snapshot lama dipertahankan.",
                   f"{y}-01-01", str(today), calc_at, "unknown", "error")
        c5["slides"] = []

    snap = {
        "ok": True,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "metric_version": METRIC_VERSION,
        "elapsed_ms": int((time.time() - t0) * 1000),
        "data_terbaru": {c["domain"]: c.get("data_terbaru", "") for c in
                         (c1, c2, c3, c4, c5)},
        "cards": [c1, c2, c3, c4, c5],
        "scoreboard": scoreboard,
        "log": log_lines,
    }
    return snap


def _snap_path():
    return ROOT / SNAP_NAME


def load_snapshot():
    try:
        return json.loads(_snap_path().read_text(encoding="utf-8"))
    except Exception:
        return None


def publish(snap):
    """Tulis atomik; gagal tulis = snapshot lama utuh (tak pernah korup)."""
    tmp = _snap_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, _snap_path())
    _log(f"published {METRIC_VERSION} {snap.get('elapsed_ms')}ms "
         f"cards={[(c['domain'], c['status']) for c in snap.get('cards', [])]}")


def refresh(force=False):
    """Satu siklus kalkulasi + publikasi. Gagal total = raise (panggil jaga lama)."""
    snap = build()
    publish(snap)
    return snap


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    s = refresh(force=a.force)
    print(json.dumps({k: v for k, v in s.items() if k != "log"},
                     ensure_ascii=False, default=str)[:2000])
    for line in s.get("log", []):
        print("  q:", line)
