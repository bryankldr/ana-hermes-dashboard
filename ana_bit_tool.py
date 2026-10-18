"""
ana_bit_tool.py — ANNA wrapper for BIT (v0.1). 1 engine, same numbers as panel.
Hermes tool: call_bit_tool("target_gap", {tahun, bulan, periode, include_breakdown, ...scope})
No LLM math — delegates to bit_engine.get_target_gap.
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
import bit_engine
try:
    import bit_case_store
except Exception:
    bit_case_store = None

def call_bit_tool(template: str, params: dict | None = None):
    params = dict(params or {})
    template = (template or "").strip()
    if template in ("target_gap", "get_target_gap", "bit_target_gap"):
        tahun = int(params.pop("tahun", 2026))
        bulan = int(params.pop("bulan", 4))
        periode = int(params.pop("periode", 2))
        sampai_dengan = str(params.pop("sampai_dengan", params.pop("sampaiDengan", "ya")) or "ya").strip().lower()
        if sampai_dengan not in ("ya","tidak","y","t","yes","n","no"): sampai_dengan="ya"
        if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
        if sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
        include_breakdown = bool(params.pop("include_breakdown", params.pop("breakdown", False)))
        # remaining params = scope (kode_divre/kph/bkph/rph/tpg)
        scope = {k: v for k, v in params.items() if k.startswith("kode_")}
        # also accept kode_tpg alias
        if "kode_tpg" in params and "kode_tpg" not in scope:
            scope["kode_tpg"] = params["kode_tpg"]
        return bit_engine.get_target_gap(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan, include_breakdown=include_breakdown)
    if template in ("diagnostic", "bit_diagnostic", "get_diagnostic"):
        tahun = int(params.pop("tahun", 2026))
        bulan = int(params.pop("bulan", 4))
        periode = int(params.pop("periode", 2))
        sampai_dengan = str(params.pop("sampai_dengan", params.pop("sampaiDengan", "ya")) or "ya").strip().lower()
        if sampai_dengan not in ("ya","tidak","y","t","yes","n","no"): sampai_dengan="ya"
        if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
        if sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
        scope = {k: v for k, v in params.items() if k.startswith("kode_")}
        if "kode_tpg" in params and "kode_tpg" not in scope:
            scope["kode_tpg"] = params["kode_tpg"]
        return bit_engine.get_diagnostic(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)
    if template in ("hypothesis", "bit_hypothesis", "get_hypothesis", "h1h4"):
        tahun = int(params.pop("tahun", 2026))
        bulan = int(params.pop("bulan", 4))
        periode = int(params.pop("periode", 2))
        sampai_dengan = str(params.pop("sampai_dengan", params.pop("sampaiDengan", "ya")) or "ya").strip().lower()
        if sampai_dengan not in ("ya","tidak","y","t","yes","n","no"): sampai_dengan="ya"
        if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
        if sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
        scope = {k: v for k, v in params.items() if k.startswith("kode_")}
        if "kode_tpg" in params and "kode_tpg" not in scope:
            scope["kode_tpg"] = params["kode_tpg"]
        return bit_engine.get_hypothesis(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)
    if template in ("sebaran", "bit_sebaran", "get_sebaran", "localization"):
        tahun = int(params.pop("tahun", 2026))
        bulan = int(params.pop("bulan", 4))
        periode = int(params.pop("periode", 2))
        sampai_dengan = str(params.pop("sampai_dengan", params.pop("sampaiDengan", "ya")) or "ya").strip().lower()
        if sampai_dengan not in ("ya","tidak","y","t","yes","n","no"): sampai_dengan="ya"
        if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
        if sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
        scope = {k: v for k, v in params.items() if k.startswith("kode_")}
        if "kode_tpg" in params and "kode_tpg" not in scope:
            scope["kode_tpg"] = params["kode_tpg"]
        return bit_engine.get_sebaran(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)

    if template in ("cases", "bit_cases", "case_list", "list_cases"):
        if bit_case_store is None:
            raise RuntimeError("bit_case_store belum tersedia")
        limit = int((params or {}).pop("limit", 20))
        offset = int((params or {}).pop("offset", 0))
        status = (params or {}).pop("status", None)
        q = (params or {}).pop("q", (params or {}).pop("search", None))
        return bit_case_store.list_cases(limit=limit, offset=offset, status=status, q=q)
    if template in ("case", "bit_case", "get_case", "create_case"):
        if bit_case_store is None:
            raise RuntimeError("bit_case_store belum tersedia")
        # flexible: if params has gejala -> create, else get by id
        if params and (params.get("gejala") or params.get("symptom")):
            email = params.pop("email", params.pop("user_email", ""))
            scope = {k: v for k, v in params.items() if k.startswith("kode_")}
            # keep kode_tpg_list if present
            if params.get("kode_tpg_list"):
                scope["kode_tpg_list"] = params.get("kode_tpg_list")
            payload = {k: params[k] for k in ("gejala","pertanyaan","periode","snapshot","hipotesis","kesimpulan","kepastian","keputusan","hasil","tags") if k in params}
            if not payload.get("periode") and params.get("tahun"):
                payload["periode"] = {"tahun": params.get("tahun"), "bulan": params.get("bulan",2), "periode": params.get("periode",0), "sampai_dengan": params.get("sampai_dengan","ya"), "scope": scope}
            return bit_case_store.create_case(payload, user_email=email, scope=scope)
        cid = params.get("id") or params.get("case_id") or ""
        if not cid:
            raise ValueError("case: perlu id atau gejala untuk create")
        return bit_case_store.get_case(cid)
    if template in ("rekomendasi", "bit_rekomendasi", "get_rekomendasi", "recommendation"):
        tahun = int(params.pop("tahun", 2026))
        bulan = int(params.pop("bulan", 4))
        periode = int(params.pop("periode", 2))
        sampai_dengan = str(params.pop("sampai_dengan", params.pop("sampaiDengan", "ya")) or "ya").strip().lower()
        if sampai_dengan not in ("ya","tidak","y","t","yes","n","no"): sampai_dengan="ya"
        if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
        if sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
        scope = {k: v for k, v in params.items() if k.startswith("kode_")}
        if params.get("kode_tpg_list"):
            scope["kode_tpg_list"] = params.get("kode_tpg_list")
        return bit_engine.get_rekomendasi(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)
    if template in ("analisis", "bit_analisis", "get_analisis", "trend"):
        tahun = int(params.pop("tahun", 2026)); bulan = int(params.pop("bulan", 4)); periode = int(params.pop("periode", 2))
        sampai_dengan = str(params.pop("sampai_dengan", params.pop("sampaiDengan", "ya")) or "ya").strip().lower()
        if sampai_dengan not in ("ya","tidak","y","t","yes","n","no"): sampai_dengan="ya"
        if sampai_dengan in ("y","yes","t","1","true"): sampai_dengan="ya"
        if sampai_dengan in ("n","no","0","tidak","false"): sampai_dengan="tidak"
        scope = {k: v for k, v in params.items() if k.startswith("kode_")}
        if params.get("kode_tpg_list"): scope["kode_tpg_list"]=params.get("kode_tpg_list")
        return bit_engine.get_analisis(tahun, bulan, periode, scope=scope, sampai_dengan=sampai_dengan)
    raise ValueError(f"unknown BIT template {template!r} — available: target_gap, diagnostic, hypothesis, sebaran, analisis, rekomendasi, cases, case")
