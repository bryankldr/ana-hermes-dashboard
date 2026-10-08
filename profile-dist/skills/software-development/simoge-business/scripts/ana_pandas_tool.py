#!/usr/bin/env python3
"""
ana_pandas_tool.py — Hermes tool wrapper untuk Pandas Analytical Layer.

Anna panggil ini, BUKAN pandas bebas.
1 batch call = N ops sequential, hanya final result ke LLM (hemat dynamic tokens).

Usage (via server /api/simoge/analyze atau direct import):
  from ana_pandas_tool import call_pandas_tool
  call_pandas_tool(template="produksi_per_wilayah", params={...},
                   operations=[{"type":"sort","by":"achievement_pct","ascending":True},
                               {"type":"limit","n":5}])

ponytail: dataset_id session belum ada — add when follow-up iteratif reuse dataset.
"""
import os, sys, json, traceback
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from ana_pandas_engine import analyze as pandas_analyze, analyze_template, SUPPORTED_OPS, HAS_PANDAS

def call_pandas_tool(template=None, params=None, operations=None, rows=None, max_result_rows=20):
    """
    template+params -> SQL -> pandas batch
    ATAU rows langsung -> pandas batch (jika template None)
    operations: list[{type, ...}]
    """
    params = params or {}
    operations = operations or []
    try:
        if not HAS_PANDAS:
            return {"ok": False, "error": "pandas not installed — pip install pandas"}
        if template:
            result = analyze_template(template, params, operations, max_result_rows=max_result_rows)
            # ringkas: jangan kembalikan sql panjang ke LLM kecuali debug
            return {"ok": True, "template": template, "params": params,
                    "elapsed_ms": result.get("elapsed_ms"),
                    "analytical": result["analytical"],
                    "explanation": result.get("explanation")}
        elif rows is not None:
            analytical = pandas_analyze(rows, operations, max_result_rows=max_result_rows)
            return {"ok": True, "analytical": analytical}
        else:
            return {"ok": False, "error": "template or rows required"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:500], "traceback": traceback.format_exc()[-600:]}

def list_ops():
    return sorted(SUPPORTED_OPS)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "ops":
        print(json.dumps(sorted(SUPPORTED_OPS), indent=2))
    elif len(sys.argv) > 1:
        # cli: template ops_json
        t = sys.argv[1]
        ops = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
        params = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        print(json.dumps(call_pandas_tool(template=t, params=params, operations=ops), indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps({"ops": sorted(SUPPORTED_OPS), "usage": "call_pandas_tool(template, params, operations)"}, indent=2))
