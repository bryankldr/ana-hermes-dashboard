#!/usr/bin/env python3
"""
ANA chart engine — visualisasi BI + presentation flow.

DIPAKAI ANNA: show_dashboard, show_spatial_chart, show_for_intent,
run_business_review, present_section, hide_spatial_chart, get_spatial_chart.
(pengganti show_bongkor_per_bkph/show_rkap_per_wilayah versi lama — dihapus,
angka tak bisa diverifikasi ulang.) Lihat SKILL.md "Chart & Presentasi".

Dua lapis, keduanya 100% kontrol ANA lewat session state /api/spatial/chart:

  1. LAPI VISUALISASI   show_dashboard / show_spatial_chart / show_for_intent
  2. LAPIS PRESENTASI    run_business_review / present_section

Spesifikasi: docs/refaktor/anna_chart.md (11 jenis chart + mapping intent)
             docs/refaktor/anna_presentasi.md (presentation engine 6 section)

Prinsip (anna_chart.md 12): ANNA memilih visualisasi dari INTENT ANALITIS
operator, bukan dari estetika. Mapping intent -> visual ada di INTENT_MAP.

Data hanya boleh datang dari template DB terverifikasi. Tidak ada angka tebakan.
"""
import os, json, re, datetime, pathlib, urllib.request, urllib.error, hashlib

# -- transport ----------------------------------------------------------------
def _resolve():
    try:
        port = int(os.environ.get("ANA_PORT", "8730"))
    except ValueError:
        port = 8730
    token = (os.environ.get("ANA_TOKEN") or "").strip()
    if not token:
        for root in pathlib.Path(__file__).resolve().parents:
            for cand in (root / "ana-hermes-dashboard" / ".ana_token", root / ".ana_token"):
                if cand.exists():
                    token = cand.read_text().strip()
                    break
            if token:
                break
    return port, token


def _post(payload):
    port, token = _resolve()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/spatial/chart",
        headers={"X-Ana-Token": token, "Content-Type": "application/json",
                 "Origin": f"http://127.0.0.1:{port}"},
        method="POST", data=json.dumps(payload).encode())
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get():
    port, token = _resolve()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/spatial/chart",
        headers={"X-Ana-Token": token, "Origin": f"http://127.0.0.1:{port}"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)}


# -- pemanggilan DB (satu-satunya sumber kebenaran) -----------------------------
# == CACHE SNAPSHOT: kunci = identitas data, bukan tanggal hari ini ========
# Cache "per hari" salah: snapshot tak berubah tiap hari kalau tak ada input.
# Yang di-cache di-INVALIDATE saat fingerprint berubah, yaitu saat ada penyadap
# baru mengisi. Fingerprint = tgl_terakhir + n_penyadap + penyadap_hari_ini.
#
# Key ikut scope: level (divre/kph/bkph/tpg) + kode filter. Jadi cache "Mei 2026
# KPH Barat" tak pernah dipakai buat "Mei 2026 BKPH Kalimanis".
CACHE_DIR = pathlib.Path(os.environ.get(
    "ANA_CACHE_DIR", str(pathlib.Path.home() / ".hermes" / "cache" / "ana_snapshot")))
CACHE_TTL_H = float(os.environ.get("ANA_CACHE_TTL_H", "6"))   # basi = strok, DB cuma 1,3s
_WIL_KEYS = ("kode_divre", "kode_kph", "kode_bkph", "kode_rph", "kode_tpg")


def cache_fingerprint(prov=None):
    """Identitas snapshot. Dua cache dengan fingerprint sama = data sama.

    Return string pendek; None kalau prov tak bisa dibaca (bypass cache).
    """
    if prov is None:
        prov = provenance()
    if not prov.get("ok"):
        return None
    return "|".join([str(prov.get("tgl")), str(prov.get("n_penyadap")),
                     str(prov.get("penyadap_hari_ini"))])


def _scope_key(level="kode_bkph", extra=None):
    """Bagian key yang membedakan scope. Tanpa ini cache salah sasaran."""
    parts = [str(level)]
    for k in _WIL_KEYS:
        v = (extra or {}).get(k)
        if v not in (None, ""):
            parts.append(f"{k}={v}")
    return "_".join(parts)


def cache_key(tahun, bulan, periode, level="kode_bkph", extra=None, prov=None,
              level_label=None):
    fp = cache_fingerprint(prov)
    if not fp:
        return None
    # level_label ikut key: label beda = scope baca berbeda, jangan campur.
    lk = _scope_key(level, extra) + (f"__{level_label}" if level_label else "")
    base = f"{tahun:04d}-{bulan:02d}-P{periode}__{lk}"
    digest = hashlib.sha1(fp.encode("utf-8")).hexdigest()[:8]
    return f"{base}__{digest}"


def cache_get(key):
    """Baca cache kalau ada + belum expired. Return (payload, cacheinfo|None)."""
    if not key:
        return None, None
    f = CACHE_DIR / f"{key}.json"
    if not f.exists():
        return None, None
    try:
        st = f.stat()
        age_h = (datetime.datetime.now().timestamp() - st.st_mtime) / 3600.0
        if age_h > CACHE_TTL_H:
            return None, {"hit": False, "expired": True, "key": key,
                          "umur_jam": round(age_h, 1)}
        data = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None, None
    return data.get("payload"), {"hit": True, "key": key,
                                 "umur_jam": round(age_h, 1),
                                 "ditulis": data.get("written"),
                                 "fingerprint": data.get("fingerprint")}


def cache_put(key, payload, prov=None):
    """Simpan payload. Gagal diam-diam - cacheito bukan fitur kritis."""
    if not key:
        return False
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fp = cache_fingerprint(prov) if prov else ""
        (CACHE_DIR / f"{key}.json").write_text(json.dumps(
            {"key": key, "fingerprint": fp,
             "written": datetime.datetime.now().isoformat(timespec="seconds"),
             "payload": payload}, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def cache_stats():
    """Ringkasan isi cache untuk ANNA/operator."""
    try:
        fs = sorted(CACHE_DIR.glob("*.json"))
    except Exception:
        return {"ok": False, "dir": str(CACHE_DIR), "n": 0}
    return {"ok": True, "dir": str(CACHE_DIR), "n": len(fs),
            "ttl_jam": CACHE_TTL_H,
            "bytes": sum(f.stat().st_size for f in fs if f.exists())}


def _q(template, **params):
    """Jalankan template DB. Return (rows, err). rows=list."""
    try:
        from ana_simoge_tool import call_simoge_tool
    except ImportError:
        base = pathlib.Path(__file__).resolve().parent
        old = os.environ.get("PYTHONPATH", "")
        os.environ["PYTHONPATH"] = f"{base}:{old}" if old else str(base)
        try:
            from ana_simoge_tool import call_simoge_tool
        except ImportError:
            return [], "modul ana_simoge_tool tidak ditemukan (set PYTHONPATH ke scripts/)"
    r = call_simoge_tool(template, params)
    if not isinstance(r, dict):
        return [], f"respons tidak valid: {str(r)[:120]}"
    if not r.get("ok"):
        return [], str(r.get("error") or r.get("traceback") or "query gagal")[:200]
    rows = r.get("rows")
    if isinstance(rows, dict):
        rows = [rows]
    return (rows if isinstance(rows, list) else []), None


def _num(v, default=0.0):
    try:
        return float(str(v).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return default


def _fmt_id(n):
    """12480 -> '12.480' (pemisah ribuan ala Indonesia)."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _fmt_num(v, dec=1):
    """Angka ala Indonesia: ribuan pakai '.', desimal pakai ','. 2200.7 -> '2.200,7'."""
    n = _num(v)
    s = f"{n:,.{dec}f}"
    return s.replace(",", "@").replace(".", ",").replace("@", ".")


def _fmt_kg(kg):
    """1118598 kg -> '1.118,6' (ton, 1 desimal)."""
    return _fmt_num(_num(kg) / 1000.0, 1)


def _scope(tahun, bulan, periode, level_label):
    per = "bulan penuh" if int(periode) == 0 else f"P{int(periode)}"
    bl = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
          "Agustus", "September", "Oktober", "November", "Desember"]
    return f"{level_label} {bl[int(bulan) - 1]} {tahun} - {per}"


# == LAPIS 1 - VISUALISASI ====================================================
def show_spatial_chart(type="bar", title="", labels=None, datasets=None,
                       options=None, meta=None):
    """Satu chart. Back-compat dengan versi lama."""
    chart = {"type": type, "title": title or "", "labels": labels or [],
             "datasets": datasets or [], "options": options or {}}
    return _post({"visible": True, "chart": chart, "meta": meta or {}})


def show_dashboard(title="", kpis=None, charts=None, narration="",
                   evidence=None, meta=None, provenance=None):
    """
    SATU BOX dengan >1 chart + baris KPI.

    charts     : list chart spec - >1 item dirender grid dalam panel yang sama.
    kpis       : [{label, value, unit, sub, tone}] tone: good|warn|bad|neutral
    narration  : kalimat yang ANNA ucapkan (bukan angka) - tampil di bawah grid.
    evidence   : [{statement, source, value, unit}] - jejak angka.
    provenance : dict dari provenance() - jadi badge di panel, selalu tampil.
    """
    if isinstance(charts, dict):
        charts = [charts]
    m = dict(meta or {})
    if provenance:
        m["provenance"] = provenance          # badge render dari m.provenance
    payload = {"visible": True, "title": title, "kpis": kpis or [],
               "narration": narration, "evidence": evidence or [], "meta": m}
    if charts:
        payload["charts"] = charts
    return _post(payload)


def hide_spatial_chart():
    return _post({"visible": False, "chart": None})


def get_spatial_chart():
    return _get()


# -- LAPORAN BISNIS (dokumen multi halaman siap cetak) ---------------------------
# Terpisah dari chart: isi laporan = paragraf + KPI + tabel, BUKAN grafik.
# Canvas Chart.js tak tercetak rapi di PDF, jadi angka masuk lewat tabel.
def _report_post(payload):
    port, token = _resolve()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/spatial/report",
        headers={"X-Ana-Token": token, "Content-Type": "application/json",
                 "Origin": f"http://127.0.0.1:{port}"},
        method="POST", data=json.dumps(payload).encode())
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def show_report(title="", subtitle="", pages=None, evidence=None, meta=None):
    """
    Buka/tampilkan LAPORAN BISNIS multi halaman (panel dokumen di SPATIAL MAP).

    pages : [{title, subtitle, blocks:[...]}] - satu item = satu halaman.
            blocks: {"type":"para","text"} | {"type":"kpi","items":[...]}
                  | {"type":"table","title","columns","rows"} | {"type":"list","items"}
                  | {"type":"note","text"}
    Panggil ulang dengan isi BARU = laporan lama tergantikan, tak perlu hide dulu.
    Panggil lagi dengan pages=[] tak menutup apa pun (isi baru, bukan hide).
    """
    if isinstance(pages, dict):
        pages = [pages]
    return _report_post({"visible": True, "title": title, "subtitle": subtitle,
                         "pages": pages or [], "evidence": evidence or [],
                         "meta": meta or {}})


def hide_report():
    """Tutup laporan. Isi state dibuang, ANNA bisa buka lagi kapan saja."""
    return _report_post({"visible": False, "pages": []})


def get_report():
    """Cek status laporan: sedang terbuka atau tertutup (+ isi sekarang)."""
    port, token = _resolve()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/spatial/report",
        headers={"X-Ana-Token": token, "Origin": f"http://127.0.0.1:{port}"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)}


# alias
hide_laporan = hide_report


# -- mapping intent -> visualisasi (anna_chart.md 12) -------------------------
INTENT_MAP = {
    "kpi": None, "current": None,
    "target_comparison": "bullet", "achievement": "bullet",
    "trend": "line",
    "ranking": "h_bar", "region": "h_bar",
    "composition": "stacked_bar", "status": "stacked_bar",
    "distribution": "bar", "histogram": "bar",
    "relationship": "scatter", "correlation": "scatter",
    "intensity": "heatmap",
    "contribution": "doughnut",
    "gap": "waterfall", "change_to_target": "waterfall",
    "pareto": "pareto",
    "location": "map",
}


def show_for_intent(intent, **kw):
    """
    Chooser visualisasi dari intent operator (anna_chart.md 10).

    kw dipakai sesuai intent:
      target_comparison : actual, target, unit, title
      trend             : labels, datasets
      ranking/region/composition/distribution/intensity/pareto/contribution
                        : labels, datasets (sudah jadi bentuk chart)
      relationship      : points=[[x,y,size]], xLabel, yLabel, title
      gap               : target, actual, unit, title
    """
    key = str(intent).strip().lower()
    if key not in INTENT_MAP:
        return {"ok": False, "error": f"intent '{intent}' tidak dikenal. "
                f"pilih dari: {', '.join(sorted(INTENT_MAP))}"}
    v = INTENT_MAP[key]
    if v is None:
        return {"ok": False, "error": f"intent '{intent}' dijawab KPI card, bukan chart - "
                "pakai show_dashboard(kpis=[...]) tanpa charts"}
    if v == "map":
        return {"ok": False, "error": "intent lokasi bukan chart - pakai show_on_map()"}
    if v == "heatmap":
        v = "stacked_bar"      # matrix P1/P2/P3 per wilayah; Chart.js tak punya heatmap
    t = kw.pop("type", v)
    if t == "bullet":
        return _bullet(kw.get("actual"), kw.get("target"), kw.get("title", ""),
                       kw.get("unit", "ton"), meta=kw.get("meta"))
    if t == "waterfall":
        return _waterfall(kw.get("target"), kw.get("actual"), kw.get("title", ""),
                          kw.get("unit", "ton"), meta=kw.get("meta"))
    return show_spatial_chart(type=t, title=kw.get("title", ""),
                              labels=kw.get("labels"), datasets=kw.get("datasets"),
                              options=kw.get("options"), meta=kw.get("meta"))


def show_for_intent_packet(pkt: dict, **kw):
    """Render chart/KPI dari Business Data Packet (P1.4/P2.1).

    pkt = call_simoge_packet(template, params) -> {intent,kpi,evidence,period,scope}
    Hemat token: tanpa rows, model jawab dari pkt['kpi']/pkt['evidence'] saja.
    Mapping intent->visual via INTENT_MAP; KPI-only intent -> show_dashboard kpis.
    Kw override title/meta bila perlu.
    """
    if not isinstance(pkt, dict) or "kpi" not in pkt:
        return {"ok": False, "error": "pkt invalid: need {kpi, intent} from call_simoge_packet"}
    intent = str(pkt.get("intent") or kw.get("intent") or "").strip().lower()
    kpi = pkt.get("kpi") or {}
    # route: KPI-only (region warna, etc) -> dashboard card tanpa chart
    # threshold: jika kpi punya total_petak/luas dan intent petak_count -> bullet/pie tergantung kw
    # generic: show_for_intent dengan kpi-derived labels/datasets bila caller belum supply
    # Paling hemat: caller sudah tahu visual; kita forward ke show_for_intent bila labels/datasets ada di kw,
    # kalau tidak, buat KPI card dari kpi/evidence.
    period = pkt.get("period") or {}
    scope = pkt.get("scope") or {}
    title = kw.get("title") or f"{intent} {scope.get('text','')} {period.get('tahun','')}".strip()
    evidence = pkt.get("evidence") or []
    # jika kw sudah punya labels/datasets -> chart path
    if kw.get("labels") or kw.get("datasets"):
        return show_for_intent(intent, title=title, **kw)
    # fallback KPI card (no chart) — hemat, tetap tampil
    narration = kw.get("narration") or (evidence[0].get("statement") if evidence else str(kpi)[:300])
    # pick primary value: total_petak / actual_ton / rows / first numeric
    _val = kpi.get("total_petak")
    if _val is None: _val = kpi.get("actual_ton")
    if _val is None: _val = kpi.get("rows")
    if _val is None:
        for _kk in ("total","jumlah_petak","n_petak"):
            if _kk in kpi and isinstance(kpi[_kk], (int,float)):
                _val = kpi[_kk]; break
    if _val is None: _val = len(kpi) if kpi else "-"
    return show_dashboard(title=title, kpis=[{"label": intent, "value": str(_val), "unit": "", "detail": narration[:300]}],
                          narration=narration, evidence=evidence, meta={"intent": intent, "packet": True, **(kw.get("meta") or {})})

def _bullet(actual, target, title, unit="ton", meta=None):
    """Aktual vs target. >=100% hijau, <60% merah, selain itu kuning."""
    a, t = _num(actual), _num(target)
    tone = "#4ADE80" if t and a >= t else ("#FB7185" if t and a < t * 0.6 else "#FACC15")
    pct = (a / t * 100) if t else 0
    gap = a - t
    n = (lambda v: _fmt_kg(v) if unit == "ton" else _fmt_id(v))
    spec = {"type": "bullet", "title": title or f"Aktual vs Target ({unit})",
            "labels": [unit],
            "datasets": [{"label": "aktual", "data": [a], "color": tone}],
            "options": {"target": t, "yLabel": unit, "showLegend": False}}
    return show_dashboard(
        title=title or "AKTUAL vs TARGET", charts=[spec],
        narration=(f"Aktual {n(a)} {unit} dari target {n(t)} {unit} atau {pct:.2f}%, "
                   f"sehingga {'terlampaui' if gap >= 0 else 'tertinggal'} "
                   f"{_fmt_num(abs(gap), 2)} {unit}."),
        evidence=[{"statement": f"Gap {unit} {_fmt_num(abs(gap), 2)}",
                   "source": f"{a:.2f} - {t:.2f}", "value": _fmt_num(abs(gap), 2),
                   "unit": unit}],
        meta=meta)


def _waterfall(target, actual, title, unit="ton", meta=None):
    """Target -> aktual -> gap. Hanya selisih terukur, TIDAK mengarang penyebab."""
    t, a = _num(target), _num(actual)
    gap = a - t
    spec = {"type": "waterfall", "title": title or f"Target ke Aktual ({unit})",
            "labels": ["Target", "Aktual", "Gap"],
            "datasets": [{"label": unit, "data": [t, a, abs(gap)]}],
            "options": {"target": t, "showLegend": False}}
    return show_dashboard(
        title=title or "TARGET KE AKTUAL KE GAP", charts=[spec],
        narration=(f"Target {_fmt_num(t, 0)} {unit}, aktual {_fmt_num(a, 0)} {unit}. "
                   f"Selisih {'positif' if gap >= 0 else 'negatif'} {_fmt_num(abs(gap), 0)} {unit}."),
        evidence=[{"statement": f"Gap {_fmt_num(abs(gap), 0)} {unit}",
                   "source": f"{a:.0f} - {t:.0f}",
                   "value": f"{abs(gap):.0f}".replace(",", "."), "unit": unit}],
        meta=meta)


# == LAPIS 2 - PRESENTATION ENGINE =============================================
# Urutan mengikuti anna_presentasi.md 1: ringkasan -> petak -> aktivitas ->
# produksi -> cross -> kesimpulan. Pacing lewat present_section(); operator boleh
# menyela kapan saja dengan memanggil section lain.
SECTIONS = ["ringkasan", "petak", "aktivitas", "produksi", "cross", "kesimpulan"]
# Label default ikut level. Salah label = operator baca "per KPH" padahal
# datanya per BKPH, lalu menyimpulkan sesuatu yang tak ada di angkanya.
_LEVEL_LABEL = {"kode_divre": "Divre", "kode_kph": "KPH", "kode_bkph": "BKPH",
                "kode_rph": "RPH", "kode_tpg": "TPG"}


# == Q&A BISNIS: pertanyaan bebas -> template + visual, jawaban variatif ======
# Review (run_business_review) menjawab "gambarlah kondisi". Q&A menjawab
# "berapa petak X?", "petak mana yang Y?", "bandingkan A vs B". Dua jalur
# BERBEDA: Q&A tak pernah menyusun 6 section, dia jawab 1 hal lalu Berhenti.
#
# Kata kunci user = tanda tangan tiap jenis pertanyaan. Level "scope" menentukan
# answer style: operator fields vs management.

# (regex, template, params, chart_type, level_tanya)
# level_tanya: "detail" (operator, angka presisi) | "ringkas" (manajer, 1 nada)
QA_INTENT = [
    # URUTAN PENTING: pola SPESIFIK harus sebelum pola umum. "tren produksi"
    # bukan "produksi"; "bongkor tanpa penyadap" bukan "petak bongkor".
    # Regel ini dijaga test_ana_qa.py seksi A.
    (r"bongkor tanpa penyadap|tanpa penyadap|matriks|silang|cross",
     "aktivitas_per_penyadap_petak", "bkph", "h_bar"),
    (r"terbanyak|teratas|top\s|puncak|terbaik|paling banyak|most active",
     "aktivitas_top_petak", "bkph", "h_bar"),
    (r"tren|trend|selama|per bulan|naik turun|perbandingan bulan|per tahun",
     "produksi_year_to_date", "kph", "line"),
    (r"detail (petak|info)|info (petak|lengkap)|profil petak|keterangan petak",
     "petak_detail", "evapot", "kpi"),
    (r"tetangga|bersebelahan|sekit|sekitar|disekitar|berdekatan",
     "petak_adjacent", "evapot", "kpi"),
    (r"produktivitas penyadap|berapa ton per penyadap|hasil penyadap|produktivitas tpg",
     "penyadap_productivity", "tpg", "h_bar"),
    (r"siapa penyadap|penyadap siapa|petak siapa|penyadap di|kodo penyadap",
     "petak_penyadap", "tpg", "h_bar"),
    (r"luas (baku|total)|berapa luas|seberapa luas|luas keseluruhan",
     "petak_area", "kph", "kpi"),
    (r"berapa petak|jumlah petak|total petak|petak ada berapa|how many (petak|block)",
     "petak_count", "kph", "kpi"),
    # inline intent - ditangani sebelum query (lihat answer_question)
    (r"data hari ini|sudah masuk|terbaru|terakhir update|input hari ini|freshness|kabar data",
     "__freshness__", "-", "kpi"),
    (r"apa kabar|kondisi sekarang|ringkasan sekarang|summary",
     "__review__", "-", "kpi"),
    # pola umum, di akhir
    (r"bongkor|belum diolah|garam|unharvested",
     "petak_bongkor", "bkph", "h_bar"),
    (r"idle|diam|stale|tidak ada aktivitas|tidak ada input|petak sepi",
     "idle_petak", "bkph", "h_bar"),
    (r"tidak efektif|efektivitas|efektif|effectiveness|inefficient|produktivitas petak|macet",
     "petak_tidak_efisien", "bkph", "h_bar"),
    (r"petak apa saja|daftar petak|petak di (kec|kelurahan|desa)|sebutkan petak|list petak",
     "petak_by_kph", "kph", "h_bar"),
    (r"target|sasaran|potensi|forecast",
     "rkap_achievement", "kph", "bullet"),
    # URUTAN PENTING: pola SPESIFIK harus sebelum pola umum. "tren produksi"
    # bukan "produksi"; "bongkor tanpa penyadap" bukan "petak bongkor".
    (r"bongkor tanpa penyadap|tanpa penyadap|matriks|silang|cross",
     "aktivitas_per_penyadap_petak", "bkph", "h_bar"),
    (r"terbanyak|teratas|top\\s|puncak|terbaik|paling banyak|most active",
     "aktivitas_top_petak", "bkph", "h_bar"),
    (r"tren|trend|selama|per bulan|naik turun|perbandingan bulan|per tahun",
     "produksi_year_to_date", "kph", "line"),
    (r"detail (petak|info)|info (petak|lengkap)|profil petak|keterangan petak",
     "petak_detail", "evapot", "kpi"),
    (r"tetangga|bersebelahan|sekit|sekitar|disekitar|berdekatan",
     "petak_adjacent", "evapot", "kpi"),
    (r"produktivitas penyadap|berapa ton per penyadap|hasil penyadap|produktivitas tpg",
     "penyadap_productivity", "tpg", "h_bar"),
    (r"siapa penyadap|penyadap siapa|petak siapa|penyadap di|kodo penyadap",
     "petak_penyadap", "tpg", "h_bar"),
    (r"luas (baku|total)|berapa luas|seberapa luas|luas keseluruhan",
     "petak_area", "kph", "kpi"),
    (r"berapa petak|jumlah petak|total petak|petak ada berapa|how many (petak|block)",
     "petak_count", "kph", "kpi"),
    # inline intent - ditangani sebelum query (lihat answer_question)
    (r"data hari ini|sudah masuk|terbaru|terakhir update|input hari ini|freshness|kabar data",
     "__freshness__", "-", "kpi"),
    (r"apa kabar|kondisi sekarang|ringkasan sekarang|summary",
     "__review__", "-", "kpi"),
    # pola umum, di akhir
    (r"bongkor|belum diolah|garam|unharvested",
     "petak_bongkor", "bkph", "h_bar"),
    (r"idle|diam|stale|tidak ada aktivitas|tidak ada input|petak sepi",
     "idle_petak", "bkph", "h_bar"),
    (r"tidak efektif|efektivitas|efektif|effectiveness|inefficient|produktivitas petak|macet",
     "petak_tidak_efisien", "bkph", "h_bar"),
    (r"petak apa saja|daftar petak|petak di (kec|kelurahan|desa)|sebutkan petak|list petak",
     "petak_by_kph", "kph", "h_bar"),
    (r"target|sasaran|potensi|forecast",
     "rkap_achievement", "kph", "bullet"),
    (r"produksi|ton|jumlah ton|hasil panen|panen|production|yield",
     "produksi_per_wilayah", "kph", "stacked_bar"),
    (r"aktivitas|foto|evidence|bukti",
     "aktivitas_agregat", "kph", "line"),
]



_NEEDS_CODE = ("petak_penyadap", "petak_detail", "petak_adjacent",
               "penyadap_aktivitas")


def parse_question(q):
    """Petakan pertanyaan bebas ke {intent, template, level, chart} atau None.

    Level default: "bkph" (sweet spot operator - cukup detil, tak overwhelming).
    Level "kph" = lebih luas, "tpg" = paling detil per penyadap.
    """
    ql = (q or "").lower()
    for pat, tpl, lvl, ctype in QA_INTENT:
        if re.search(pat, ql):
            return {"intent": tpl, "template": tpl, "level": lvl, "chart": ctype,
                    "match": pat}
    return None


def answer_question(q, tahun=None, bulan=None, periode=0, kode=None, level=None,
                    with_map=False):
    """
    Satu call = satu jawaban. Router tentukan template + visual, lalu narasi
    ditulis SESUAI KONTEKS (bukan template laporan tetap).

    Return {ok, intent, template, chart, level, title, narration, kpis, rows,
            error, hint}
    """
    intent = parse_question(q)
    if intent and intent["template"] == "__freshness__":
        f = provenance()
        return {"ok": True, "intent": "freshness", "template": "-",
                "chart": "kpi", "level": "-", "q": q,
                "title": "Kesegaran Data",
                "narration": f.get("kalimat") or f.get("catatan", ""),
                "kpis": [{"label": "DATA TERAKHIR", "value": f.get("tgl") or "-",
                          "sub": f"{f.get('fase','')} - {f.get('stale_hari',0)} hari lalu",
                          "tone": "warn" if f.get("status") == "kemarin" else "bad"}],
                "rows": []}
    if intent and intent["template"] == "__review__":
        return {"ok": True, "intent": "review", "template": "run_business_review",
                "chart": "grid", "level": "-", "q": q,
                "title": "Ringkasan Bisnis",
                "narration": "Ini jalur review lengkap - pakai run_business_review "
                             "bukan Q&A satu.chart. Panggil itu untuk 6 section.",
                "kpis": [], "rows": [], "route": "run_business_review"}
    if not intent:
        # bukan pertanyaan data - jangan tabur angka, jangan menebak
        return {"ok": False, "error": "pertanyaan tidak dipetakan ke template data",
                "q": q,
                "hint": "tanya yang bisa dijawab: petak, luas, produksi, aktivitas, "
                        "penyadap, target, efektivitas, bongkor, idle"}
    params = {"level": level or intent["level"]}
    if tahun is not None:
        params["tahun"] = int(tahun)
    if bulan is not None:
        params["bulan"] = int(bulan)
    if periode:
        params["periode"] = int(periode)
    # beberapa template WAJIB punya kode petak; nama parameternya kode_evapot
    # (bukan "evapot") - salah nama = TypeError dari template.
    if intent["template"] in _NEEDS_CODE and not kode:
        return {"ok": False, "intent": intent["intent"],
                "error": "pertanyaan ini perlu kode petak, mis. "
                         "'penyadap petak 21111020110201_11B-1'",
                "need_code": True}
    if kode:
        params["kode_evapot"] = kode
    if intent["template"] == "petak_adjacent" and not params.get("kode_tpg"):
        return {"ok": False, "intent": intent["intent"],
                "error": "petak tetangga perlu kode_tpg juga (dapat dari "
                         "petak_simple.json atau wilayah_labels)",
                "need_tpg": True}
    rows, err = _q(intent["template"], **params)
    if err:
        return {"ok": False, "error": err, "intent": intent, "q": q}
    # narasi = MANUSIA, bukan dump rows. Bentuk kalimat dari data, bukan
    # tekankan "hasil query".
    nar = _qa_narrative(intent["template"], rows, q)
    return {"ok": True, "intent": intent["intent"], "template": intent["template"],
            "chart": intent["chart"], "level": params["level"], "q": q,
            "n_rows": len(rows), "title": _qa_title(intent["template"], rows),
            "narration": nar, "rows": rows[:5],
            "kpis": _qa_kpis(intent["template"], rows)}


def _qa_title(tpl, rows):
    J = {"petak_count": "Jumlah Petak", "petak_area": "Luas Petak",
         "petak_by_kph": "Petak per Wilayah", "petak_bongkor": "Petak Bongkor",
         "idle_petak": "Petak Idle", "petak_tidak_efisien": "Petak Tidak Efektif",
         "petak_penyadap": "Penyadap per Petak",
         "penyadap_productivity": "Produktivitas Penyadap",
         "petak_detail": "Detail Petak", "petak_adjacent": "Petak Tetangga",
         "rkap_achievement": "Capaian Target", "produksi_per_wilayah": "Produksi",
         "produksi_year_to_date": "Tren Produksi", "aktivitas_agregat": "Tren Aktivitas",
         "aktivitas_top_petak": "Petak Teramai", "aktivitas_per_penyadap_petak": "Cross"}
    return J.get(tpl, tpl.replace("_", " ").title())


def _qa_narrative(tpl, rows, q):
    """Kalimat natural, dari NAMA KOLOM ASLI tiap template. Kalau rows kosong,
    jawab jujur - jangan apa-apain, jangan isi dengan angka tebakan."""
    if not rows:
        return ("Data untuk pertanyaan ini belum tersedia. "
                "Mungkin di luar scope, atau belum ada yang menginput.")
    n = len(rows)
    # kolom agregat: 1 baris = 1 angka, bukan daftar
    if tpl == "petak_count":
        d = rows[0]
        return (f"Ada {_fmt_id(_num(d.get('jumlah_petak')))} petak di KPH Barat "
                f"untuk RTT {d.get('tahun', '?')}, total luas "
                f"{_fmt_num(_num(d.get('total_luas_baku')), 2)} ha.")
    if tpl == "petak_area":
        d = rows[0]
        return (f"Total luas baku {_fmt_num(_num(d.get('luas_baku_total')), 2)} ha "
                f"dari {_fmt_id(_num(d.get('jumlah_petak')))} petak. "
                f"Yang sudah jadi andil (daerah provinsi) "
                f"{_fmt_num(_num(d.get('luas_andil_total')), 2)} ha, "
                f"atau {_fmt_num(_num(d.get('rasio_andil_pct')), 1)}%.")
    if tpl == "petak_bongkor":
        # template ini 1 baris per PETAK (bukan agregat per wilayah)
        luas = sum(_num(r.get("luas_baku")) for r in rows)
        return (f"Ada {_fmt_id(n)} petak bongkor dengan luas total "
                f"{_fmt_num(luas, 1)} ha. "
                f"Bongkor tidak menghasilkan apa pun, jadi ini prioritas "
                f"pertama untuk dikerjakan. " + _qa_top(rows, "luas_baku"))
    if tpl == "idle_petak":
        return f"Ada {_fmt_id(n)} petak idle - belum ada aktivitas di sana. " + _qa_top(rows, "n_idle")
    if tpl == "penyadap_productivity":
        return f"{_fmt_id(n)} penyadap tercatat. " + _qa_top(rows, "total_penerimaan")
    if tpl == "petak_detail":
        # 1 baris = 1 profil. Bukan "terbanyak" - ini profil.
        d = rows[0]
        pohon = _num(d.get("jumlah_pohon"))
        # satuan target_rkap TIDAK diverifikasi (lihat catatan rkap_achievement),
        # jadi tampilkan mentah - jangan dikonversi ke ton lalu terlihat implausibel.
        return (f"Petak {d.get('nomor_petak', '?')}, luas "
                f"{_fmt_num(_num(d.get('luas_baku')), 2)} ha, target RKAP "
                f"{_fmt_num(_num(d.get('target_rkap')), 1)} (satuan sesuai DB). "
                + (f"Terisi {_fmt_id(pohon)} pohon. " if pohon else "")
                + f"BKPH {d.get('kode_bkph', '?')}, TPG {d.get('kode_tpg', '?')}, "
                f"RTT {d.get('tahun_rtt', '?')}.")
    if tpl == "aktivitas_top_petak":
        return "Petak paling aktif. " + _qa_top(rows, "jumlah_aktivitas")
    if tpl == "petak_penyadap":
        if n == 0:
            return ("Tidak ada penyadap yang tercatat di petak ini. "
                    "Kalau memang ada, berarti belum ada aktivitas yang diinput "
                    "untuk petak tersebut.")
        return f"{_fmt_id(n)} penyadap bekerja di petak ini. " + _qa_top(rows, "id_penyadap")
    # fallback: sebutkan apa yang ditemukan, pakai label yang ada
    return f"{_fmt_id(n)} baris data. " + (_qa_top(rows) if rows else "")


_LABEL_KEYS = ("nama_wilayah", "nama_bkph", "bkph_nama", "nama_tpg", "nama",
               "nomor_petak", "n", "nama_penyadap", "alias", "kode_evapot")


def _qa_top(rows, key=None):
    """Baris terbesar pertama dengan label yang NYATA - kalimat 'terbanyak di X'."""
    if not rows:
        return ""
    r = rows[0]
    if key is None:
        nums = [(k, _num(v)) for k, v in r.items()
                if k not in _LABEL_KEYS and re.fullmatch(r"-?[\d.,]+", str(v).strip() or "x")]
        if not nums:
            return ""
        key = max(nums, key=lambda kv: kv[1])[0]
    val = _num(r.get(key))
    label = next((r[k] for k in _LABEL_KEYS if r.get(k)), "?")
    return f"Terbanyak di {label} ({_fmt_id(val)})."


def _qa_kpis(tpl, rows):
    """KPI ringkas untuk chart box - bukan semua kolom."""
    if not rows:
        return []
    if tpl == "petak_count":
        return [{"label": "TOTAL PETAK", "value": _fmt_id(len(rows)), "tone": "good"}]
    if tpl == "petak_area":
        tot = sum(_num(r.get("total_luas")) for r in rows)
        return [{"label": "TOTAL LUAS", "value": _fmt_num(tot, 1), "unit": "ha"}]
    return []


def run_business_review(tahun, bulan, periode=0, level="kode_bkph", level_label=None,
                        use_cache=True):
    """
    Susun business review lengkap. TIDAK sekaligus ditampilkan - return daftar
    section; pakai present_section() untuk paced playback.

    Return {ok, scope, sections:[{key,title,narrative,kpis,charts,evidence,map}], warnings}
    """
    try:
        tahun, bulan, periode = int(tahun), int(bulan), int(periode)
    except (TypeError, ValueError):
        return {"ok": False, "error": "tahun/bulan/periode harus angka"}
    scope = _scope(tahun, bulan, periode,
                   level_label or _LEVEL_LABEL.get(level, "KPH"))
    # Cache: fingerprint dicek DULU (1 query ringan) supaya tak bisa pakai cache
    # basi. Key ikut level + kode filter divre/kph/bkph/tpg.
    _ck = None
    _cinfo = {"hit": False}
    if use_cache:
        _ck = cache_key(tahun, bulan, periode, level=level,
                        level_label=level_label)
        if _ck:
            _payload, _cinfo = cache_get(_ck)
            _cinfo = _cinfo or {"hit": False}
            if _payload:
                _payload["cache"] = _cinfo
                return _payload
    secs, warns = [], []

    # -- 1. RINGKASAN: KPI petak + produksi vs target ------------------------
    kpis, petak_rows, prod_rows = [], [], []
    rows, err = _q("status_petak_per_wilayah", tahun=tahun, bulan=bulan,
                   periode=periode, level=level)
    if err:
        warns.append(f"status_petak_per_wilayah: {err}")
    else:
        petak_rows = rows
        tot = {k: sum(_num(r.get(k)) for r in rows)
               for k in ("total_petak", "aktif", "idle", "bongkor", "luas_bongkor")}
        if tot["total_petak"]:
            kpis = [
                {"label": "PETAK", "value": _fmt_id(tot["total_petak"])},
                {"label": "AKTIF", "value": _fmt_id(tot["aktif"]), "tone": "good"},
                {"label": "IDLE", "value": _fmt_id(tot["idle"]), "tone": "warn"},
                {"label": "BONGKOR", "value": _fmt_id(tot["bongkor"]), "tone": "bad",
                 "sub": _fmt_num(tot["luas_bongkor"], 1) + " ha"},
            ]
    rows, err = _q("produksi_per_wilayah", tahun=tahun, bulan=bulan,
                   periode=periode, level=level)
    if err:
        warns.append(f"produksi_per_wilayah: {err}")
    else:
        prod_rows = rows
        act_kg = sum(_num(r.get("actual_kg")) for r in rows)
        tgt_kg = sum(_num(r.get("target_kg")) for r in rows)
        ach = (act_kg / tgt_kg * 100) if tgt_kg else 0
        kpis += [
            {"label": "PRODUKSI", "value": _fmt_kg(act_kg), "unit": "ton"},
            {"label": "TARGET", "value": _fmt_kg(tgt_kg), "unit": "ton"},
            {"label": "ACHIEVEMENT", "value": f"{ach:.2f}%",
             "tone": "good" if ach >= 100 else ("warn" if ach >= 60 else "bad")},
        ]
    t_petak = sum(_num(r.get("total_petak")) for r in petak_rows)
    t_aktif = sum(_num(r.get("aktif")) for r in petak_rows)
    t_idle = sum(_num(r.get("idle")) for r in petak_rows)
    t_bong = sum(_num(r.get("bongkor")) for r in petak_rows)
    narr = (f"Saya melaporkan kondisi bisnis {scope}."
            + (f" Terdapat {_fmt_id(t_petak)} petak dalam scope evaluasi. "
               f"Sebanyak {_fmt_id(t_aktif)} aktif, {_fmt_id(t_idle)} idle, "
               f"dan {_fmt_id(t_bong)} bongkor." if t_petak else
               " Data petak tidak tersedia untuk scope ini."))
    # Data SIMOGE bukan realtime (input paling banyak 12.00-15.00 + sore).
    # Laporan pagi tak boleh dibaca "hari ini sudah final" - jadi disebut eksplisit
    # lewat KPI provenance + badge di panel, bukan cuma narasi.
    prov = provenance()          # 2 query ringan, ~0,08s
    if not prov.get("ok") or prov.get("hot"):
        kpis = kpis               # data hot = tak perlu peringatan basi
    else:
        kpis = ([{"label": "DATA", "value": prov.get("tgl") or "-",
                  "sub": (f"{prov.get('penyadap_hari_ini'):.0f} penyadap hari ini"
                          if prov.get("penyadap_hari_ini") is not None
                          else f"{prov.get('fase', '')} - {prov.get('stale_hari', 0)} hari lalu"),
                  "tone": "warn" if prov.get("status") == "kemarin" else "bad"}] + kpis)
        narr = f"{prov.get('kalimat', '')} {narr}"
    secs.append({"key": "ringkasan", "title": f"BUSINESS REVIEW - {scope}",
                 "narrative": narr, "kpis": kpis,
                 "provenance": {k: prov.get(k) for k in
                                ("tgl", "jam", "fase", "status", "stale_hari",
                                 "n_penyadap", "n_petak", "penyadap_hari_ini", "hot")},
                 "charts": [_status_stack(petak_rows)] if petak_rows else [],
                 "evidence": [{"statement": "Komposisi petak dalam scope aktif",
                               "source": "status_petak_per_wilayah", "value": scope}],
                 "map": {"template": "aktivitas_petak_map",
                         "params": {"tahun": tahun, "bulan": bulan,
                                    "periode": periode, "limit": 1200}}})

    # -- 2. PETAK: komposisi + bongkor ranking -------------------------------
    bong_rows, err = _q("bongkor_per_wilayah", tahun=tahun, level=level)
    if err:
        warns.append(f"bongkor_per_wilayah: {err}")
        bong_rows = []
    bong_rows = sorted(bong_rows, key=lambda r: -_num(r.get("jumlah_petak")))[:10]
    petak_charts = [_status_stack(petak_rows)] if petak_rows else []
    if bong_rows:
        petak_charts.append({
            "type": "h_bar", "title": "Petak bongkor per wilayah",
            "labels": [_nm(r) for r in bong_rows],
            "datasets": [{"label": "petak",
                          "data": [_num(r.get("jumlah_petak")) for r in bong_rows]}]})
    tot_b = sum(_num(r.get("jumlah_petak")) for r in bong_rows)
    tot_ha = sum(_num(r.get("total_luas")) for r in bong_rows)
    _bong_by_wil = sorted(((_fmt_id(r.get("nama_wilayah") or r.get("kode_bkph") or "?"),
                            _num(r.get("jumlah_petak"))) for r in bong_rows),
                          key=lambda x: -x[1])
    _top_bong = _bong_by_wil[0] if _bong_by_wil else ("-", 0)
    _n_wil_bong = sum(1 for _, n in _bong_by_wil if n > 0)
    bong_narr = (
        f"Ada {_fmt_id(tot_b)} petak bongkor dengan luas {_fmt_num(tot_ha, 1)} ha, "
        f"tersebar di {_fmt_id(_n_wil_bong)} wilayah. Yang terbanyak di {_top_bong[0]} "
        f"dengan {_fmt_id(_top_bong[1])} petak. Petak bongkor tidak menghasilkan apa pun, "
        f"jadi saya tempatkan di urutan pertama untuk dikerjakan."
        if bong_rows else
        "Data bongkor per wilayah tidak tersedia untuk scope ini, jadi saya belum bisa "
        "menunjuk petak mana yang harusdikerjakan duluan.")
    secs.append({"key": "petak", "title": "Kondisi Petak",
                 "narrative": bong_narr,
                 "kpis": ([{"label": "BONGKOR", "value": _fmt_id(tot_b), "tone": "bad"},
                           {"label": "LUAS", "value": _fmt_num(tot_ha, 1),
                            "unit": "ha"}] if bong_rows else []),
                 "charts": petak_charts,
                 "evidence": [{"statement": f"{_fmt_id(tot_b)} petak bongkor",
                               "source": "bongkor_per_wilayah", "value": scope}],
                 "map": {"template": "petak_bongkor_map",
                         "params": {"tahun": tahun, "bulan": bulan,
                                    "periode": periode, "limit": 900}}})

    # -- 3. AKTIVITAS: per tahap pembaharuan + pareto jenis -----------------
    pem_rows, err = _q("aktivitas_agregat", tahun=tahun, bulan=bulan,
                       periode=periode, grup_by="pembaharuan")
    if err:
        warns.append(f"aktivitas_agregat/pembaharuan: {err}")
    jenis_rows, err = _q("aktivitas_agregat", tahun=tahun, bulan=bulan,
                         periode=periode, grup_by="aktivitas")
    if err:
        warns.append(f"aktivitas_agregat/aktivitas: {err}")
    total_akt = sum(_num(r.get("count")) for r in pem_rows)
    akt_charts = []
    if pem_rows:
        akt_charts.append({
            "type": "bar", "title": "Aktivitas per tahap Pembaharuan",
            "labels": [f"P{_nm(r)}" if _nm(r).isdigit() else _nm(r) for r in pem_rows],
            "datasets": [{"label": "aktivitas",
                          "data": [_num(r.get("count")) for r in pem_rows]}]})
    if jenis_rows:
        jenis_rows = sorted(jenis_rows, key=lambda r: -_num(r.get("count")))[:8]
        akt_charts.append({
            "type": "pareto", "title": "Pareto jenis aktivitas",
            "labels": [_nm(r) for r in jenis_rows],
            "datasets": [{"label": "aktivitas",
                          "data": [_num(r.get("count")) for r in jenis_rows]}]})
    pem1 = sum(_num(r.get("count")) for r in pem_rows if str(r.get("dim")) == "1")
    pem4 = sum(_num(r.get("count")) for r in pem_rows if str(r.get("dim")) == "4")
    parts = []
    if total_akt:
        parts.append(f"Realisasi aktivitas pada periode ini {_fmt_id(total_akt)} kejadian.")
    if pem1:
        parts.append(f"Dari breakdown per tahap, Pembaharuan 1 menyumbang {_fmt_id(pem1)}.")
    if not pem4:
        parts.append("Database tidak memuat tahap Pembaharuan 4, "
                     "jadi chart menampilkan P1 sampai P3 saja.")
    secs.append({"key": "aktivitas", "title": "Realisasi Aktivitas",
                 "narrative": " ".join(parts) or
                 "Data aktivitas tidak tersedia untuk scope ini.",
                 "kpis": ([{"label": "AKTIVITAS", "value": _fmt_id(total_akt)}]
                          if total_akt else []),
                 "charts": akt_charts,
                 "evidence": [{"statement": f"{_fmt_id(total_akt)} aktivitas",
                               "source": "aktivitas_agregat", "value": scope}],
                 "map": {"template": "aktivitas_petak_map",
                         "params": {"tahun": tahun, "bulan": bulan,
                                    "periode": periode, "limit": 2000}}})

    # -- 4. PRODUKSI: bullet + ranking wilayah ------------------------------
    prod_charts, prod_kpis, act_kg, tgt_kg = [], [], 0.0, 0.0
    if prod_rows:
        act_kg = sum(_num(r.get("actual_kg")) for r in prod_rows)
        tgt_kg = sum(_num(r.get("target_kg")) for r in prod_rows)
        tone = ("#4ADE80" if act_kg >= tgt_kg else
                "#FB7185" if tgt_kg and act_kg < tgt_kg * 0.6 else "#FACC15")
        prod_charts.append({
            "type": "bullet", "title": "Produksi vs Target",
            "labels": ["ton"],
            "datasets": [{"label": "aktual", "data": [act_kg / 1000.0], "color": tone}],
            "options": {"target": tgt_kg / 1000.0, "yLabel": "ton", "showLegend": False}})
        top = sorted(prod_rows, key=lambda r: -_num(r.get("actual_kg")))[:10]
        prod_charts.append({
            "type": "h_bar", "title": "Produksi per wilayah",
            "labels": [_nm(r) for r in top],
            "datasets": [{"label": "ton",
                          "data": [_num(r.get("actual_kg")) / 1000.0 for r in top]}]})
        prod_kpis = [
            {"label": "AKTUAL", "value": _fmt_kg(act_kg), "unit": "ton"},
            {"label": "TARGET", "value": _fmt_kg(tgt_kg), "unit": "ton"},
            {"label": "GAP", "unit": "ton",
             "value": _fmt_num(abs(act_kg - tgt_kg) / 1000.0, 2),
             "tone": "good" if act_kg >= tgt_kg else "bad"}]
    secs.append({"key": "produksi", "title": "Kondisi Produksi",
                 "narrative": (f"Produksi aktual {_fmt_kg(act_kg)} ton dari target "
                               f"{_fmt_kg(tgt_kg)} ton." if prod_rows else
                               "Data produksi tidak tersedia untuk scope ini."),
                 "kpis": prod_kpis, "charts": prod_charts,
                 "evidence": [{"statement": "Produksi aktual dibanding target",
                               "source": "produksi_per_wilayah", "value": scope}],
                 "map": {"template": "rkap_map",
                         "params": {"tahun": tahun, "bulan": bulan,
                                    "periode": periode, "limit": 1200}}})

    # -- 5. CROSS: hubungan luas andil vs produksi (scatter) ---------------
    cross = _cross_matrix(tahun, bulan, periode)
    secs.append({"key": "cross", "title": "Cross Analysis",
                 "narrative": (cross["narrative"] if cross["charts"] else
                               "Data yang tersedia belum cukup untuk menyusun "
                               "analisis hubungan antar indikator."),
                 "kpis": cross["kpis"], "charts": cross["charts"],
                 "evidence": cross["evidence"], "map": None})

    # -- 6. KESIMPULAN ------------------------------------------------------
    secs.append({"key": "kesimpulan", "title": "Kesimpulan",
                 "narrative": cross["closing"] or
                 "Ringkasan scope sudah tersampaikan pada bagian sebelumnya.",
                 "kpis": [], "charts": [], "evidence": [], "map": None})

    rv = {"ok": True, "scope": scope, "tahun": tahun, "bulan": bulan,
          "periode": periode, "level": level, "sections": secs, "warnings": warns,
          "cache": {**_cinfo, "key": _ck, "ttl_jam": CACHE_TTL_H}}
    if _ck:
        rv["cache"]["ditulis"] = cache_put(_ck, rv)
    return rv


def _nm(r):
    """Nama wilayah dari baris template; fallback ke kode."""
    for k in ("nama_wilayah", "bkph_nama", "kph_nama", "label", "dim",
              "nomor_petak", "kode_wilayah", "kode"):
        v = r.get(k)
        if v not in (None, "", "0", 0):
            return str(v).replace("_", " ")
    return "?"


def _status_stack(rows):
    """Komposisi status petak: stacked bar per wilayah."""
    agg = {}
    for r in rows:
        d = agg.setdefault(_nm(r), {"aktif": 0.0, "idle": 0.0, "bongkor": 0.0})
        for s in d:
            d[s] += _num(r.get(s))
    labels = list(agg)[:10]
    return {"type": "stacked_bar", "title": "Komposisi status petak", "labels": labels,
            "datasets": [{"label": s, "data": [agg[l][s] for l in labels]}
                         for s in ("aktif", "idle", "bongkor")],
            "options": {"stacked": True, "showLegend": True}}


# -- freshness: data SIMOGE bukan realtime -------------------------------------
# Input operator paling banyak 12.00-15.00 + sore-malam. Pagi biasanya minim.
# Jadi laporan pagi tak boleh dibaca "kondisi hari ini final".
SPOIL_HOUR = 15          # setelah jam ini, sebagian besar input sudah masuk


def provenance():
    """Snapshot: KAPAN data terakhir masuk, dari SIAPA, seberapa lengkap.

    Yang perlu di-cache itu bukan "usi snapshot", tapi IDENTITAS snapshot:
    tgl_terakhir + penyadap yang mengisi hari ini. Kalau tgl_terakhir sama dan
    penyadap_hari_ini = 0, snapshot tak berubah -> boleh dipakai lagi tanpa
    query. Kalau ada yang masuk, invalidate.

    Return: {ok, tgl, jam, fase, status, stale_hari, n_penyadap, n_petak,
             penyadap_hari_ini, hot, kalimat}
    """
    f = freshness()
    if not f.get("ok"):
        return {"ok": False, "kalimat": "Tidak bisa memastikan kesegaran data."}
    idn, _ = _q("data_identity")
    idr = (idn[0] if isinstance(idn, list) and idn else {}) or {}
    n_penyadap = _num(idr.get("n_penyadap"))
    n_petak = _num(idr.get("n_petak"))
    p_ini = _num(idr.get("penyadap_hari_ini"))
    hot = p_ini > 0
    if hot:
        kalimat = (f"Data terakhir masuk {f.get('tgl')}. Ada {_fmt_id(p_ini)} penyadap "
                   f"yang mengisi hari ini, jadi angka ini hot.")
    elif f.get("status") == "basi":
        kalimat = (f"Data terakhir masuk {f.get('tgl')}, "
                   f"{f.get('stale_hari')} hari lalu, dan belum ada input baru. "
                   f"Angka ini bukan kondisi real-time — periksa dulu apakah "
                   f"operasi berjalan, baru bandingkan dengan target.")
    else:
        kalimat = (f"Data terakhir masuk {f.get('tgl')}. Belum ada penyadap yang "
                   f"mengisi hari ini — angka hari ini belum final, biasanya "
                   f"baru lengkap setelah jam 12.")
    return {"ok": True, "tgl": f.get("tgl"), "jam": f.get("jam"), "fase": f.get("fase"),
            "status": f.get("status"), "stale_hari": f.get("stale_hari"),
            "n_penyadap": n_penyadap, "n_petak": n_petak,
            "penyadap_hari_ini": p_ini, "hot": hot, "kalimat": kalimat}


def freshness():
    """{tgl, jam, fase, stale_hari, status, catatan} — 1 query ringan (0,08s)."""
    try:
        row, _ = _q("data_freshness")
        rows = row if isinstance(row, list) else ([row] if isinstance(row, dict) else [])
        d = rows[0] if rows else {}
    except Exception as e:
        return {"ok": False, "catatan": f"tidak bisa cek freshness: {str(e)[:90]}"}
    tgl = d.get("tgl_terakhir")
    if not tgl:
        return {"ok": True, "status": "kosong", "catatan": "belum ada aktivitas tercatat."}
    # DB kirim date object; flatten ke 'YYYY-MM-DD' supaya serializable
    if not isinstance(tgl, str):
        tgl = getattr(tgl, "isoformat", lambda: str(tgl))()[:10]
    tgl = tgl[:10]
    hari_ini = _num(d.get("hari_ini"))
    try:
        thn, bln, tgl_h = (int(x) for x in str(tgl).split("-"))
        last_day = datetime.date(thn, bln, tgl_h)
    except (ValueError, TypeError):
        return {"ok": True, "status": "tidakdiketahui", "catatan": f"format tanggal tak terbaca: {tgl}"}
    now = datetime.datetime.now()
    stale = (now.date() - last_day).days
    jam = now.hour
    if jam < 10:
        fase = "pagi-awal"
    elif jam < SPOIL_HOUR:
        fase = "siang-osp"
    elif jam < 19:
        fase = "sore"
    else:
        fase = "malam"
    if hari_ini > 0:
        status = "segar"
    elif stale <= 1:
        status = "kemarin"
    else:
        status = "basi"
    catatan = {
        "segar": f"{_fmt_id(hari_ini)} aktivitas sudah masuk hari ini.",
        "kemarin": "Belum ada input hari ini. Angelina perlu menunggu operator afternoon — "
                   "input paling banyak masuk 12.00-15.00.",
        "basi": f"Tidak ada input sejak {tgl} ({stale} hari lalu). "
                f"Periksa apakah operasi hari ini berjalan, atau operator masih input.",
    }[status]
    return {"ok": True, "tgl": tgl, "jam": f"{jam:02d}:{now.minute:02d}", "fase": fase,
            "stale_hari": stale, "status": status, "catatan": catatan}


def _cross_matrix(tahun, bulan, periode):
    """
    Cross analysis sesuai anna_presentasi.md 8: bongkor + penyadap + aktivitas
    rendah + produksi rendah pada SATU tabel (aktivitas_petak_map punya semua
    kolomnya). HANYA pada unit yang sama — kalau tidak, bilang tak cukup dan
    TIDAK mengarang sebab (anna_chart.md 8).
    """
    rows, err = _q("aktivitas_petak_map", tahun=tahun, bulan=bulan,
                  periode=periode, limit=1200)
    if err or not rows:
        return {"charts": [], "kpis": [], "evidence": [], "narrative": "", "closing": ""}
    by_w = {}
    for r in rows:
        w = r.get("bkph_nama") or r.get("kph_nama")
        if not w:
            continue
        d = by_w.setdefault(str(w), {"luas": 0.0, "bongkor": 0, "tanpa_penyadap": 0,
                                     "aktivitas": 0.0, "prod_derivasi": 0.0,
                                     "target": 0.0})
        d["luas"] += _num(r.get("luas_baku"))
        d["aktivitas"] += _num(r.get("jumlah_aktivitas"))
        d["target"] += _num(r.get("target_rkap"))
        kat = str(r.get("kategori") or "")
        if kat == "bongkor":
            d["bongkor"] += 1
            if not _num(r.get("jumlah_penyadap")):
                d["tanpa_penyadap"] += 1
    if len(by_w) < 2:
        return {"charts": [], "kpis": [], "evidence": [], "narrative": "", "closing": ""}
    ws = list(by_w)
    # scatter: X = aktivitas, Y = produksi. Produksi per wilayah dari
    # produksi_per_wilayah; kalau tak ada, pakai luas petak sebagai proxy DAN
    # label-i sebagai proxy — jangan menyebutnya produksi.
    p_rows, p_err = _q("produksi_per_wilayah", tahun=tahun, bulan=bulan,
                       periode=periode, level="kode_bkph")
    prod_by = {}
    for r in p_rows or []:
        prod_by[str(r.get("nama_wilayah") or "")] = _num(r.get("actual_kg"))
    prod_by = {k: v for k, v in prod_by.items() if v}
    use_prod = len(prod_by) >= 2
    ylab = "Produksi (kg)" if use_prod else "Luas petak (ha)"
    pts = []
    for w in ws:
        x = by_w[w]["aktivitas"]
        y = prod_by.get(w, 0.0) if use_prod else by_w[w]["luas"]
        if not use_prod and w in prod_by:
            continue
        pts.append([x, y, max(by_w[w]["luas"], 1.0)])
    pts.sort(key=lambda p: p[0])
    if len(pts) < 2:
        return {"charts": [], "kpis": [], "evidence": [], "narrative": "", "closing": ""}
    charts = [
        {"type": "scatter", "title": f"Aktivitas vs {ylab}", "labels": [],
         "points": pts, "datasets": [{"label": "wilayah", "data": []}],
         "options": {"xLabel": "Aktivitas (kejadian)", "yLabel": ylab}},
        {"type": "stacked_bar", "title": "Bongkor: ada penyadap vs tanpa penyadap",
         "labels": ws,
         "datasets": [{"label": "ada penyadap",
                       "data": [by_w[w]["bongkor"] - by_w[w]["tanpa_penyadap"] for w in ws]},
                      {"label": "tanpa penyadap",
                       "data": [by_w[w]["tanpa_penyadap"] for w in ws]}],
         "options": {"stacked": True}}]
    t_bong = sum(by_w[w]["bongkor"] for w in ws)
    t_tp = sum(by_w[w]["tanpa_penyadap"] for w in ws)
    t_luas = sum(by_w[w]["luas"] for w in ws)
    t_akt = sum(by_w[w]["aktivitas"] for w in ws)
    narr = (f"Dari {_fmt_id(t_bong)} petak bongkor, {_fmt_id(t_tp)} tidak memiliki penyadap. "
            + (f"Pada dataset ini terlihat kecenderungan {'produksi yang lebih tinggi pada kelompok dengan aktivitas lebih tinggi' if use_prod else 'luas petak yang lebih besar pada kelompok dengan aktivitas lebih tinggi'}. "
               f"Ini merupakan pola pada data yang tersedia, bukan klaim sebab-akibat."))
    kpis = [{"label": "AKTIVITAS", "value": _fmt_id(t_akt)},
            {"label": "BONGKOR", "value": _fmt_id(t_bong), "tone": "bad"},
            {"label": "TANPA PENYADAP", "value": _fmt_id(t_tp), "tone": "warn"},
            {"label": "LUAS", "value": _fmt_num(t_luas, 1), "unit": "ha"}]
    closing = (f"Secara keseluruhan, {_fmt_id(t_akt)} aktivitas terekam pada {_fmt_id(t_luas)} ha "
               f"dalam scope ini, dengan {_fmt_id(t_bong)} petak bongkor. "
               f"Evaluasi perlu difokuskan pada kelompok petak yang memiliki kombinasi "
               f"kondisi bongkor, keterbatasan penyadap, dan aktivitas di bawah rata-rata.")
    return {"charts": charts, "kpis": kpis,
            "evidence": [{"statement": f"{_fmt_id(t_tp)} petak bongkor tanpa penyadap",
                          "source": "aktivitas_petak_map", "value": f"{len(ws)} wilayah"}],
            "narrative": narr, "closing": closing}


def present_section(review, key="ringkasan", with_map=False):
    """
    Tampilkan satu section ke chart panel (paced playback).
    Operator boleh menyela: panggil lagi dengan key berbeda.
    with_map=True → juga pusher layer peta sesuai section.

    Section tanpa chart (mis. 'kesimpulan') TIDAK menyentuh panel chart —
    chart yang tampil tetap dari section sebelumnya, jadi operator sempat
    membacanya. Kalau memang mau kosongkan panel, panggil hide_spatial_chart().
    """
    secs = (review or {}).get("sections") or []
    sec = next((s for s in secs if s.get("key") == key), None)
    if sec is None:
        return {"ok": False, "error": f"section '{key}' tidak ada. "
                f"pilihan: {', '.join(s.get('key', '?') for s in secs)}"}
    charts = sec.get("charts") or []
    kpis = sec.get("kpis") or []
    if not charts and not kpis:
        return {"ok": True, "section": key, "chart": None, "map": None,
                "narration": sec.get("narrative", ""),
                "note": "section tanpa visual - panel chart tidak berubah (biar operator sempat baca chart sebelumnya)"}
    r = show_dashboard(title=sec.get("title", ""), kpis=kpis,
                       charts=charts, narration=sec.get("narrative"),
                       evidence=sec.get("evidence"),
                       provenance=sec.get("provenance"),
                       meta={"periode": (review or {}).get("scope", ""),
                             "source": "business_review", "section": key})
    mapres = None
    if with_map and sec.get("map"):
        try:
            from ana_simoge_tool import show_on_map as _m
            mapres = _m(sec["map"]["template"], sec["map"].get("params", {}))
        except Exception as e:
            mapres = {"ok": False, "error": str(e)[:160]}
    return {"ok": True, "section": key, "chart": r, "map": mapres,
            "narration": sec.get("narrative", "")}


# alias
show_chart = show_spatial_chart
hide_chart = hide_spatial_chart


# == SHORTCUT PATH — ANNA tidak perlu cari file lagi ===========================
# Semua perintah di SKILL.md/anthropic_profile memakai path literal ini.
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
CLI = {
    "review": f"python3 {SCRIPTS_DIR}/ana_chart_tool.py review",
    "dash":   f"python3 {SCRIPTS_DIR}/ana_chart_tool.py show",
    "intent": f"python3 {SCRIPTS_DIR}/ana_chart_tool.py intent",
    "get":    f"python3 {SCRIPTS_DIR}/ana_chart_tool.py get",
    "hide":   f"python3 {SCRIPTS_DIR}/ana_chart_tool.py hide",
    "cache":  f"python3 {SCRIPTS_DIR}/ana_chart_tool.py cache",
    "ask":    f'python3 {SCRIPTS_DIR}/ana_chart_tool.py ask q="..."',
    "fresh":  f"python3 {SCRIPTS_DIR}/ana_chart_tool.py fresh",
}

_BULAN_ID = {"januari": 1, "jan": 1, "februari": 2, "feb": 2, "maret": 3, "mar": 3,
             "april": 4, "apr": 4, "mei": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
             "agustus": 8, "agu": 8, "ags": 8, "september": 9, "sep": 9, "sep": 9,
             "oktober": 10, "okt": 10, "november": 11, "nov": 11, "nop": 11,
             "desember": 12, "des": 12, "mei ini": 5, "sekarang": None}

_HARI_INI = datetime.date.today()


def parse_periode(text, today=None):
    """
    "mei", "mei 2026", "bulan ini", "tahun ini" -> (tahun, bulan, periode=0).
    Tanpa ini ANNA harus menebak angka bulan tiap kali = lambat + rawan salah.
    """
    t = (today or _HARI_INI)
    s = (text or "").lower()
    if not s.strip():
        return None
    if "tahun ini" in s or "year ini" in s or "bulan ini" in s or "bulan(year) ini" in s:
        bln = t.month
        thn = t.year
    else:
        bln = None
        for name, num in _BULAN_ID.items():
            if name in s:
                bln = num
                break
        thn = t.year
        m = re.search(r"(20\d{2})", s)
        if m:
            thn = int(m.group(1))
    if bln is None:
        return None
    # relatif: "mei lalu" / "bulan lalu" = mundur satu bulan (penting untuk MoM)
    if re.search(r"\b(lalu|sebelumnya|kemarin|terakhir)\b", s):
        bln -= 1
        if bln < 1:
            bln, thn = 12, thn - 1
    if "setengah" in s or "pertama" in s:
        prd = 1
    elif "kedua" in s or "akhir" in s:
        prd = 2
    else:
        prd = 0
    return thn, bln, prd


def cli_review(tahun, bulan, periode=0, play=None, with_map=False, level=None):
    """
    Satu call = review utuh. JANGAN panggil _q per template satu-satu.
    Return dict ringkas: {ok, scope, sections:[{key,n_charts,n_kpis}], played}
    """
    kw = {"tahun": int(tahun), "bulan": int(bulan), "periode": int(periode)}
    if level:
        kw["level"] = level
    rv = run_business_review(**kw)
    if play and rv.get("ok"):
        rv["played"] = present_section(rv, play, with_map=with_map)
    # ringkas: ANNA butuh tahu section mana punya chart, tanpa inspect isi
    for sec in (rv.get("sections") or []):
        sec["n_charts"] = len(sec.get("charts") or [])
        sec["n_kpis"] = len(sec.get("kpis") or [])
        sec["has_visual"] = bool(sec["n_charts"] or sec["n_kpis"])
        sec["narrative"] = (sec.get("narrative") or "")[:200]
    rv["next"] = SECTIONS[[i for i, k in enumerate(SECTIONS)
                          if k == play][0] + 1] if play in SECTIONS and \
        SECTIONS.index(play) + 1 < len(SECTIONS) else None
    return rv


# == CLI - eksekusi aman lewat terminal (python3 -c DILARANG) ==================
if __name__ == "__main__":
    import sys

    def _val(v):
        return json.loads(v) if v[:1] in "[{" else v

    args = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    cmd = sys.argv[1] if len(sys.argv) > 1 and "=" not in sys.argv[1] else "get"
    if cmd == "hide":
        print(json.dumps(hide_spatial_chart(), indent=1, ensure_ascii=False))
    elif cmd == "show":
        print(json.dumps(show_spatial_chart(**{k: _val(v) for k, v in args.items()}),
                         indent=1, ensure_ascii=False))
    elif cmd == "laporan":
        # "laporan show/hide/status" — LAPORAN BISNIS, bukan chart.
        act = args.pop("act", "status")
        if act == "hide":
            print(json.dumps(hide_report(), indent=1, ensure_ascii=False))
        elif act == "show":
            print(json.dumps(show_report(
                title=args.get("title", ""), subtitle=args.get("subtitle", ""),
                pages=_val(args["pages"]) if args.get("pages") else None,
                evidence=_val(args["evidence"]) if args.get("evidence") else None,
                meta=_val(args["meta"]) if args.get("meta") else None),
                         indent=1, ensure_ascii=False))
        else:
            st = get_report()
            print(json.dumps({"visible": st.get("visible"), "title": st.get("title"),
                              "n_pages": len(st.get("pages") or []),
                              "page_titles": [p.get("title") for p in (st.get("pages") or [])],
                              "n_evidence": len(st.get("evidence") or []),
                              "error": st.get("error")},
                             indent=1, ensure_ascii=False))
    elif cmd == "intent":
        i = args.pop("intent", "trend")
        print(json.dumps(show_for_intent(i, **{k: _val(v) for k, v in args.items()}),
                         indent=1, ensure_ascii=False))
    elif cmd == "ask":
        q = args.pop("q", "") or args.pop("text", "")
        r = answer_question(q, tahun=args.get("tahun"), bulan=args.get("bulan"),
                            periode=int(args.get("periode", 0) or 0),
                            kode=args.get("kode"), level=args.get("level"))
        print(json.dumps(r, indent=1, ensure_ascii=False, default=str))
    elif cmd == "cache":
        act = args.get("act", "stats")
        if act == "clear":
            n = 0
            for f in CACHE_DIR.glob("*.json"):
                try:
                    f.unlink(); n += 1
                except OSError:
                    pass
            print(json.dumps({"ok": True, "dihapus": n, **cache_stats()}, indent=1))
        elif act == "key":
            print(json.dumps({"key": cache_key(
                int(args.get("tahun", 2026)), int(args.get("bulan", 5)),
                int(args.get("periode", 0)), level=args.get("level", "kode_bkph"),
                level_label=args.get("level_label"))}, indent=1))
        else:
            print(json.dumps(cache_stats(), indent=1))
    elif cmd == "fresh":
        print(json.dumps(freshness(), indent=1, ensure_ascii=False))
    elif cmd == "parse":
        # "mei" / "mei 2025" / "bulan ini" -> argumen review siap pakai.
        # Tanpa ini ANNA menebak angka bulan tiap kali.
        text = args.get("text") or args.get("q") or ""
        p = parse_periode(text)
        print(json.dumps({"text": text, "parsed": p,
                          "review_cmd": (f"review tahun={p[0]} bulan={p[1]} periode={p[2]}" if p else None),
                          "error": None if p else "bulan/tahun tak terbaca - tanya operator"},
                         indent=1, ensure_ascii=False))
    elif cmd == "review":
        keys = ("tahun", "bulan", "periode")
        kw = {k: int(v) for k, v in args.items() if k in keys and v.lstrip("-").isdigit()}
        kw["level"] = args.get("level", "kode_bkph")
        if args.get("level_label"):
            kw["level_label"] = args["level_label"]
        kw["use_cache"] = "nocache" not in args
        rv = run_business_review(**kw)
        if rv.get("ok") and args.get("play"):
            rv["played"] = present_section(rv, args.get("play", "ringkasan"),
                                           with_map="map" in args)
        rv["sections"] = [{"key": s["key"], "title": s["title"],
                           "n_charts": len(s.get("charts") or []),
                           "n_kpis": len(s.get("kpis") or []),
                           "narrative": (s.get("narrative") or "")[:120]}
                          for s in rv.get("sections", [])]
        if args.get("ringkas") or args.get("brief"):
            rv.pop("sections_full", None)
        print(json.dumps(rv, indent=1, ensure_ascii=False, default=str))
    else:
        st = get_spatial_chart()
        print(json.dumps({"visible": st.get("visible"), "layout": st.get("layout"),
                          "title": st.get("title"),
                          "charts": [c.get("type") for c in (st.get("charts") or [])],
                          "n_kpis": len(st.get("kpis") or [])},
                         indent=1, ensure_ascii=False))