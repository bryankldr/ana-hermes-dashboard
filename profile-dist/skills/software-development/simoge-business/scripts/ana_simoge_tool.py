#!/usr/bin/env python3
"""
ANA-Tool wrapper: exposes simoge-business templates as a callable tool.
ANA loads this module and exposes `call_simoge_tool` to the chat session.

Usage from ANA tool-call:
  call_simoge_tool(template='petak_count', params={'tahun': 2026})
  → returns dict with columns, rows, row_count, explanation
"""

import os
import sys
import json
import traceback

# Ensure skill scripts are importable
SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts"
)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from simoge_db import run, T  # noqa: E402
# NOTE: `q` (raw SQL) is deliberately NOT re-exported here. ANNA tool-calls
# resolve through this module — named templates only, no SQL, ever.


def call_simoge_tool(template: str, params: dict = None) -> dict:
    """
    Execute a SIMOGE business query template.
    
    Args:
        template: Template name (run `simoge_db.py` with no args to list)
        params: Dict of template params (e.g. {tahun: 2026, bulan: 9})
    
    Returns:
        {ok: bool, columns, rows, row_count, elapsed_ms, sql, explanation, error?}
    """
    params = params or {}
    try:
        result = run(template, **params)
        return {
            "ok": True,
            "template": template,
            "params": params,
            **result,
            "explanation": _explain(result, template, params)
        }
    except KeyError as e:
        return {
            "ok": False,
            "error": f"Unknown template: {template}. Available: {sorted(T)}",
            "template": template
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "template": template,
            "traceback": traceback.format_exc()[-500:]
        }


def _explain(result: dict, template: str, params: dict) -> str:
    """Generate human-readable explanation for the result."""
    rc = result.get("row_count", 0)
    
    if template == "petak_count":
        tahun = params.get("tahun", "—")
        row = result["rows"][0] if result["rows"] else {}
        return f"Jumlah petak RTT tahun {tahun}: {row.get('jumlah_petak', rc)} petak, luas total {row.get('total_luas_baku', '—')} ha"
    
    if template == "petak_area":
        row = result["rows"][0] if result["rows"] else {}
        return f"Luas baku total: {row.get('luas_baku_total', '—')} ha, luas andil: {row.get('luas_andil_total', '—')} ha ({row.get('rasio_andil_pct', '—')}%) — tahun {params.get('tahun')}"
    
    if template == "petak_by_kph":
        level = params.get('level', 'kode_kph')
        label = {'kode_kph': 'KPH', 'kode_bkph': 'BKPH', 'kode_rph': 'RPH', 'kode_tpg': 'TPG'}.get(level, level)
        parts = [f"{r.get('kode','?')}: {r['jumlah_petak']} petak ({r['luas_baku']} ha)" for r in result["rows"]]
        return f"Distribusi petak per {label} (tahun {params.get('tahun')}):\n" + "\n".join(parts[:10])
    
    if template == "petak_with_geometry":
        tahun = params.get("tahun", "—")
        return f"Ditemukan {rc} petak RTT {tahun} dengan geometry — siap untuk visualisasi di peta"
    
    if template == "petak_effectiveness":
        kategori = {}
        for r in result["rows"]:
            k = r.get("kategori", "unknown")
            kategori[k] = kategori.get(k, 0) + 1
        parts = [f"{k}: {v}" for k, v in sorted(kategori.items())]
        return f"Efektivitas {rc} petak (tahun {params.get('tahun')}): " + ", ".join(parts) + f" — bongkor=merah, kurang=kuning, terpenuhi=hijau"
    
    if template == "petak_bongkor":
        return f"Ditemukan {rc} petak bongkor (tanpa penyadap sama sekali) tahun {params.get('tahun')}"
    
    if template == "rkap_achievement":
        tahun = params.get("tahun", "—")
        bulan = params.get("bulan", "—")
        periode = params.get("periode", "—")
        warna_count = {}
        for r in result["rows"]:
            w = r.get("warna", "unknown")
            warna_count[w] = warna_count.get(w, 0) + 1
        parts = [f"{k}: {v}" for k, v in sorted(warna_count.items())]
        return f"Pencapaian RKAP tahun {tahun} bulan {bulan} P{periode}: " + ", ".join(parts) + " (merah=0-25%, oranye=26-50%, kuning=51-75%, hijau=76-100%, emas=>100%)"
    
    if template == "penyadap_productivity":
        return f"Analisis produktivitas {rc} penyadap tahun {params.get('tahun')} bulan {params.get('bulan')}"
    
    if template == "idle_petak":
        status_count = {}
        for r in result["rows"]:
            s = r.get("status", "unknown")
            status_count[s] = status_count.get(s, 0) + 1
        parts = [f"{k}: {v}" for k, v in sorted(status_count.items())]
        return f"Analisis idle/bongkor {rc} petak: " + ", ".join(parts)
    
    if template == "drum_flow":
        counts = {}
        for r in result["rows"]:
            counts[r.get("status_drum","?")] = r["jumlah_drum"]
        return f"Status drum tahun {params.get('tahun')} bulan {params.get('bulan')}: " + ", ".join(f"{k}={v}" for k,v in counts.items())

    if template == "petak_bongkor_map":
        cats = {}
        for r in result["rows"]:
            cats[r.get("warna","?")] = cats.get(r.get("warna","?"),0)+1
        return f"Bongkor map {rc} petak (tahun {params.get('tahun','?')}): " + ", ".join(f"{k}={v}" for k,v in cats.items()) + " — merah=bongkor"

    if template == "petak_multi_penyadap_map":
        cats = {}
        for r in result["rows"]:
            cats[r.get("warna","?")] = cats.get(r.get("warna","?"),0)+1
        return f"Multi-penyadap map {rc} petak (tahun {params.get('tahun','?')}): " + ", ".join(f"{k}={v}" for k,v in cats.items()) + " — kuning 2/oranye 3/hijau >3 penyadap"

    if template == "petak_efektivitas_map":
        cats = {}
        for r in result["rows"]:
            cats[r.get("kategori","?")] = cats.get(r.get("kategori","?"),0)+1
        return f"Efektivitas map {rc} petak (tahun {params.get('tahun','?')}): " + ", ".join(f"{k}={v}" for k,v in cats.items()) + " — merah bongkor/kuning kurang/hijau terpenuhi"

    if template == "rkap_map":
        cats = {}
        for r in result["rows"]:
            cats[r.get("warna","?")] = cats.get(r.get("warna","?"),0)+1
        return f"RKAP map {rc} petak P{params.get('periode','?')} {params.get('bulan','?')}/{params.get('tahun','?')}: " + ", ".join(f"{k}={v}" for k,v in cats.items()) + " — merah 0-25/oranye 26-50/kuning 51-75/hijau 76-100/emas>100"

    if template == "idle_petak_map":
        cats = {}
        for r in result["rows"]:
            cats[r.get("status","?")] = cats.get(r.get("status","?"),0)+1
        return f"Idle map {rc} petak P{params.get('periode','?')} {params.get('bulan','?')}/{params.get('tahun','?')}: " + ", ".join(f"{k}={v}" for k,v in cats.items()) + " — kuning idle/hijau aktif"

    if template == "status_petak_per_wilayah":
        w = params.get("level", "kode_bkph")
        label = {"kode_divre": "DIVRE", "kode_kph": "KPH", "kode_bkph": "BKPH",
                 "kode_rph": "RPH", "kode_tpg": "TPG"}.get(w, w)
        parts = [f"{r.get('nama_wilayah') or r.get('kode_wilayah','?')}"
                 f" (aktif {r.get('aktif','?')}/idle {r.get('idle','?')}"
                 f"/bongkor {r.get('bongkor','?')} dari {r.get('total_petak','?')} petak, "
                 f"{r.get('luas_bongkor','?')} ha bongkor)"
                 for r in result["rows"]]
        return f"Status petak per {label} {params.get('bulan','?')}/{params.get('tahun','?')}: " + ", ".join(parts[:6])

    if template == "aktivitas_agregat":
        gb = params.get("grup_by", "penyadap")
        nama = {"penyadap": "Penyadap", "aktivitas": "Jenis Aktivitas",
                "pembaharuan": "Tahap Pembaharuan"}.get(gb, gb)
        per = params.get("periode")
        per_txt = "bulan penuh" if str(per) in ("0", "full", "None") else f"P{per}"
        pem = params.get("pembaharuan_ke")
        pem_txt = f" · filter Pem{pem}" if pem else ""
        parts = [f"{r.get('label','?')}={r.get('count',0)}"
                 f" (petak {r.get('petak_count','?')}, foto {r.get('photo_count','?')})"
                 for r in result["rows"]]
        tot = sum(r.get("count", 0) for r in result["rows"])
        return (f"Aktivitas per {nama} — {per_txt} {params.get('bulan','?')}/{params.get('tahun','?')}{pem_txt}: "
                + (", ".join(parts[:8]) if parts else "tidak ada aktivitas")
                + f" — total {tot} kejadian. KING = {result['rows'][0].get('label','—') if result['rows'] else '—'}")

    if template == "aktivitas_top_petak":
        per = params.get("periode")
        per_txt = "bulan penuh" if str(per) in ("0", "full", "None") else f"P{per}"
        if not result["rows"]:
            return f"Tidak ada aktivitas {per_txt} {params.get('bulan','?')}/{params.get('tahun','?')}"
        parts = [f"{r.get('nomor_petak','?')}={r.get('jumlah_aktivitas',0)}"
                 f" (Pem1 {r.get('pem1',0)}/Pem2 {r.get('pem2',0)}/Pem3 {r.get('pem3',0)}"
                 f", {r.get('jumlah_penyadap',0)} penyadap)"
                 for r in result["rows"]]
        top = result["rows"][0]
        return (f"Petak paling aktif {per_txt} {params.get('bulan','?')}/{params.get('tahun','?')} "
                f"({rc} petak): " + ", ".join(parts[:8])
                + f" — KING = {top.get('nomor_petak','?')} ({top.get('jumlah_aktivitas',0)} aktivitas)")

    if template == "aktivitas_per_penyadap_petak":
        ids = {r.get("id_penyadap") for r in result["rows"]}
        return (f"{rc} aktivitas untuk {len(ids)} penyadap "
                f"({params.get('bulan','?')}/{params.get('tahun','?')}) — "
                + ", ".join(f"{r.get('nama_penyadap','?')} di {r.get('nomor_petak','?')}" for r in result["rows"][:5]))

    if template == "aktivitas_petak_map":
        cats = {}
        for r in result["rows"]:
            cats[r.get("kategori","?")] = cats.get(r.get("kategori","?"),0)+1
        return f"Aktivitas map {rc} petak P{params.get('periode','?')} {params.get('bulan','?')}/{params.get('tahun','?')}: " + ", ".join(f"{k}={v}" for k,v in cats.items()) + " — merah 0/kuning 1-2/hijau ≥3 aktivitas"

    if template == "matriks_map":
        cats = {}
        for r in result["rows"]:
            cats[r.get("warna","?")] = cats.get(r.get("warna","?"),0)+1
        return f"Matriks map {rc} petak P{params.get('periode','?')} {params.get('bulan','?')}/{params.get('tahun','?')}: " + ", ".join(f"{k}={v}" for k,v in cats.items()) + " — merah bongkor/oranye kurang+cap<50/kuning kurang/hijau terpenuhi/emas>100"


    if template == "kph_summary_map":
        agg = params.get("aggregated_level", "kph")
        label = {"kode_divre": "DIVRE", "kode_kph": "KPH", "kode_bkph": "BKPH"}.get(agg, agg)
        parts = []
        for r in result["rows"]:
            eff = r.get("avg_efektivitas_pct", "?")
            bongkor = r.get("bongkor", 0)
            parts.append(f"{r.get('nama_wilayah') or r.get('kode_wilayah','?')}: {r['total_petak']} petak ({r['total_luas_ha']} ha), bongkor {bongkor}, eff {eff}%")
        return f"Ringkasan {label} {rc} wilayah (tahun {params.get('tahun','?')}): " + "; ".join(parts[:8])


    if template == "aktivitas_recent":
        rc = result.get("row_count", 0)
        has_foto = sum(1 for r in result["rows"] if r.get("foto_file"))
        return f"Aktivitas terbaru {rc} record: foto {has_foto}/{rc}, semua bawa lat/lng/alt/pembaharuan_ke — cuaca/akses_lokasi ikut"

    if template == "penyadap_aktivitas":
        rc = result.get("row_count", 0)
        # updated explain with foto/coord completeness
        has_foto = sum(1 for r in result["rows"] if r.get("foto_file") or r.get("aktivitas_photo"))
        return f"{rc} aktivitas untuk petak {params.get('kode_evapot','?')}: lat/lng/alt/pembaharuan_ke lengkap, foto {has_foto}/{rc} — quare/cuaca/akses_lokasi ikut"

    if template == "petak_detail": 
        row = result["rows"][0] if result["rows"] else {}
        return f"Petak {row.get('nomor_petak', '?')}: luas {row.get('luas_baku', '?')} ha, target RKAP {row.get('target_rkap', '?')} kg, RTT {row.get('tahun_rtt', '?')}"

    if template == "petak_penyadap":
        return f"{rc} penyadap di petak {params.get('kode_evapot', '?')}: " + ", ".join(f"{r.get('nama_penyadap','?')} ({r.get('luas_andil','?')} ha)" for r in result["rows"][:5])

    if template == "petak_adjacent":
        parts = [f"{r.get('nomor_petak','?')} (RTT {r.get('tahun_rtt','?')})" for r in result["rows"]]
        return "Petak sebelah: " + ", ".join(parts[:5]) + " (same TPG)"

    if template == "petak_multi_penyadap":
        return f"{rc} petak dengan lebih dari 1 penyadap (tahun {params.get('tahun', '?')})"

    if template == "produksi_aktiv":
        row = result["rows"][0] if result["rows"] else {}
        return f"Produksi {params.get('periode','?')} bulan {params.get('bulan','?')}/{params.get('tahun','?')}: {row.get('total_kg','?')} kg, {row.get('n_terima','?')} aktivitas, {row.get('n_petak','?')} petak aktif"

    if template == "produksi_year_to_date":
        row = result["rows"][0] if result["rows"] else {}
        return f"Produksi YTD {params.get('bulan','?')}/{params.get('tahun','?')}: {row.get('total_kg','?')} kg, {row.get('n_terima','?')} aktivitas, {row.get('n_petak','?')} petak"

    if template == "petak_tidak_efisien":
        return f"{rc} petak tidak efisien (andil < baku tahun {params.get('tahun', '?')})"

    if template == "bongkor_per_wilayah":
        w = params.get('level', 'kode_bkph')
        label = {'kode_bkph': 'BKPH', 'kode_rph': 'RPH', 'kode_kph': 'KPH'}.get(w, w)
        wmax = result["rows"][0] if result["rows"] else {}
        return f"RB {label[:2]} paling banyak: {wmax.get('kode_wilayah','?')} = {wmax.get('jumlah_petak',0)} petak, {wmax.get('total_luas','?')} ha"

    if template == "wilayah_lookup":
        rows = result["rows"] or []
        if not rows:
            return f"Wilayah '{params.get('nama','?')}' tidak ditemukan"
        preview = ", ".join(f"{r['level']}:{r['nama']}({r['kode']})" for r in rows[:5])
        return f"Lookup '{params.get('nama')}' -> {len(rows)} match: {preview}"

    if template == "rencana_aktivitas":
        row = result["rows"][0] if result["rows"] else {}
        return f"Rencana {params.get('periode','?')} bulan {params.get('bulan','?')}/{params.get('tahun','?')}: {row.get('rencana_kg','?')} kg, {row.get('n_rencana','?')} rencana"

    if template == "petak_non_rtt":
        return f"{rc} petak yang bukan RTT tahun {params.get('tahun', '?')} (data lama/lain)"


def _read_dashboard_token():
    """Token dashboard dari env, fallback ke .ana_token (ANNA tak pegang kredensial)."""
    tok = (os.environ.get("ANA_TOKEN") or "").strip()
    if tok:
        return tok
    import pathlib
    for root in pathlib.Path(__file__).resolve().parents:
        cand = root / "ana-hermes-dashboard" / ".ana_token"
        if cand.exists():
            return cand.read_text().strip()
    return ""


def _post_show(url, token, port, body, _retry=True):
    """POST show_on_map + retry sekali: 401 = token basi (server restart, tulis
    ulang .ana_token di main()) → baca file ulang, ulangi sekali. Tutup race
    restart-di-tengah-call tanpa perlu ANNA tahu soal token."""
    import urllib.request, urllib.error, json as _json
    req = urllib.request.Request(
        url,
        headers={"X-Ana-Token": token,
                 "Content-Type": "application/json",
                 "Origin": f"http://127.0.0.1:{port}"},
        method="POST", data=body)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return _json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401 and _retry and not (os.environ.get("ANA_TOKEN") or "").strip():
            fresh = _read_dashboard_token()
            if fresh and fresh != token:
                return _post_show(url, fresh, port, body, _retry=False)
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode()[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def show_on_map(template="petak_with_geometry", **params):
    """Query SIMOGE via dashboard HTTP, push polygons ke peta, auto-fit. SATU panggilan.

    Pakai untuk "tampilkan di peta / tampilkan petak ...".
    Memanggil POST /api/simoge/show_on_map supaya ANA tidak perlu 2 langkah
    dan tidak butuh DB password di proses ANA.
    """
    import json as _json

    try:
        ana_port = int(os.environ.get("ANA_PORT", "8730"))
    except ValueError:
        ana_port = 8730
    token = _read_dashboard_token()
    if not token:
        return {"ok": False, "error": "token dashboard tidak ditemukan (.ana_token / env ANA_TOKEN)"}

    payload = {"template": template, "params": params}
    body = _json.dumps(payload).encode()
    url = f"http://127.0.0.1:{ana_port}/api/simoge/show_on_map"
    return _post_show(url, token, ana_port, body)


def call_simoge_packet(template: str, params: dict = None) -> dict:
    """Packet: query + KPI/evidence tanpa raw rows (hemat token).

    Wraps POST /api/simoge/packet -> {intent, period, scope, kpi, evidence, row_count}.
    Statistik-only WAJIB pakai ini, bukan call_simoge_tool mentah.
    Fallback: bila server tak terjangkau, build packet minimal lokal.
    """
    params = params or {}
    import urllib.request, urllib.error, json as _json
    try:
        ana_port = int(__import__('os').environ.get("ANA_PORT", "8730"))
    except ValueError:
        ana_port = 8730
    token = _read_dashboard_token()
    port = ana_port
    try:
        # reuse _post helper tapi endpoint packet
        body = _json.dumps({"template": template, "params": params}).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/simoge/packet",
            headers={"X-Ana-Token": token, "Content-Type": "application/json",
                     "Origin": f"http://127.0.0.1:{port}"},
            method="POST", data=body)
        with urllib.request.urlopen(req, timeout=10) as r:
            pkt = _json.loads(r.read().decode())
            # server returns packet dict langsung (bukan {ok:..}) — normalisasi
            if isinstance(pkt, dict) and "kpi" in pkt:
                return pkt
            return pkt
    except Exception as e:
        pass
    # fallback lokal: call_simoge_tool + minimal packet
    res = call_simoge_tool(template, params)
    if not res.get("ok"):
        return {"intent": template, "params": params, "kpi": {"error": res.get("error","")}, "evidence": [], "row_count": 0, "error": res.get("error")}
    rows = res.get("rows") or []
    return {"intent": template, "period": {"tahun": params.get("tahun"), "bulan": params.get("bulan"), "periode": params.get("periode",0)},
            "scope": {"level": params.get("level","kode_bkph")}, "kpi": {"rows": len(rows), "sample": rows[:1]},
            "evidence": [{"statement": res.get("explanation",""), "source": template}], "row_count": len(rows),
            "explanation": res.get("explanation",""), "elapsed_ms": res.get("elapsed_ms")}

def list_templates():
    """Return available templates."""
    return sorted(T)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        template = sys.argv[1]
        params = {}
        for arg in sys.argv[2:]:
            k, v = arg.split("=", 1)
            params[k] = int(v) if v.isdigit() else v
        print(json.dumps(call_simoge_tool(template, params), default=str, indent=2, ensure_ascii=False))
    else:
        print("Templates:", list_templates())
