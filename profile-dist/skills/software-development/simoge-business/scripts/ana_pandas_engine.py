#!/usr/bin/env python3
"""
ana_pandas_engine.py — Pandas Analytical Layer untuk Anna-Hermes.

Kontrak: Dashboard owns raw data, Business Engine owns facts/rules,
         Pandas owns analytical processing, Anna owns interpretation.

Pola: RAW SQL rows -> DataFrame -> batch ops (1 call) -> small analytical result -> Anna
Bukan: RAW rows -> LLM hitung manual.

ponytail: dataset_id session & TTL belum ada — add when ada follow-up iteratif
          yang reuse dataset sama. Saat ini stateless one-shot batch.
ponytail: polars/duckdb upgrade path jika DataFrame >100K rows / butuh OLAP.
"""

import json
import math

try:
    import pandas as pd
    import numpy as np
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None
    np = None

# ops yang didukung — controlled tool, bukan exec bebas
SUPPORTED_OPS = frozenset({
    "filter", "group_by", "aggregate", "sort", "rank",
    "pivot", "compare_period", "percentage_change",
    "statistics", "anomaly", "describe", "limit",
})

def _to_df(rows):
    if not HAS_PANDAS:
        raise RuntimeError("pandas not installed — pip install pandas")
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # coerce numeric strings (Decimal/varchar numbers from DB)
    for col in df.columns:
        # coba coerce ke numeric jika looks numeric
        try:
            coerced = pd.to_numeric(df[col], errors="coerce")
            # hanya ganti jika >=50% berhasil coerce
            if coerced.notna().sum() >= len(df) * 0.5:
                df[col] = coerced
        except Exception:
            pass
    return df

def _apply_filter(df, spec):
    """spec: {column, op: eq/ne/gt/gte/lt/lte/in/contains, value} atau {where: {col: val}}"""
    if df.empty:
        return df
    where = spec.get("where")
    if where:
        for col, val in where.items():
            if col in df.columns:
                df = df[df[col] == val]
        return df
    col = spec.get("column")
    op = spec.get("op", "eq")
    val = spec.get("value")
    if not col or col not in df.columns:
        return df
    if op == "eq":
        return df[df[col] == val]
    if op == "ne":
        return df[df[col] != val]
    if op == "gt":
        return df[df[col] > val]
    if op == "gte":
        return df[df[col] >= val]
    if op == "lt":
        return df[df[col] < val]
    if op == "lte":
        return df[df[col] <= val]
    if op == "in":
        return df[df[col].isin(val if isinstance(val, (list, tuple)) else [val])]
    if op == "contains":
        return df[df[col].astype(str).str.contains(str(val), na=False)]
    return df

def _apply_group_aggregate(df, spec):
    """spec: {by: [col], metrics: {col: agg}} agg= sum|mean|count|min|max|nunique"""
    if df.empty:
        return df
    by = spec.get("by") or spec.get("columns") or spec.get("group_by")
    metrics = spec.get("metrics") or spec.get("agg") or {}
    if not by or not metrics:
        return df
    if isinstance(by, str):
        by = [by]
    agg_map = {}
    for col, func in metrics.items():
        if col in df.columns:
            agg_map[col] = func
    if not agg_map:
        return df
    grouped = df.groupby(by, dropna=False).agg(agg_map)
    # flatten jika perlu
    grouped = grouped.reset_index()
    return grouped

def _apply_sort(df, spec):
    if df.empty:
        return df
    by = spec.get("by") or spec.get("column") or spec.get("columns")
    asc = spec.get("ascending", True)
    if isinstance(asc, str):
        asc = asc.lower() not in ("false", "desc", "0")
    if isinstance(by, str):
        by = [by]
    by = [c for c in (by or []) if c in df.columns]
    if not by:
        return df
    return df.sort_values(by=by, ascending=asc)

def _apply_rank(df, spec):
    """spec: {column, ascending: false, limit: 5} -> sort + head"""
    if df.empty:
        return df
    col = spec.get("column") or spec.get("by")
    asc = spec.get("ascending", False)
    if isinstance(asc, str):
        asc = asc.lower() in ("true", "asc", "1")
    limit = int(spec.get("limit", 5))
    if col and col in df.columns:
        df = df.sort_values(by=col, ascending=asc)
    return df.head(limit)

def _apply_pivot(df, spec):
    if df.empty:
        return df
    index = spec.get("index")
    columns = spec.get("columns")
    values = spec.get("values")
    aggfunc = spec.get("aggfunc", "sum")
    if not index or not columns or not values:
        return df
    try:
        pivoted = df.pivot_table(index=index, columns=columns, values=values, aggfunc=aggfunc, fill_value=0, dropna=False)
        pivoted.columns = [str(c) for c in pivoted.columns]
        return pivoted.reset_index()
    except Exception:
        return df

def _apply_percentage_change(df, spec):
    """spec: {column, group_by?} -> tambah kolom <col>_pct_change"""
    if df.empty:
        return df
    col = spec.get("column")
    if not col or col not in df.columns:
        return df
    # jika ada group_by, pct_change per grup tidak relevan untuk 1-period batch;
    # untuk sekarang global pct_change vs prev row setelah sort
    # caller harus sort dulu by periode
    df = df.copy()
    df[f"{col}_pct_change"] = df[col].pct_change(fill_method=None) * 100
    return df

def _apply_statistics(df, spec):
    """return tidak ubah df — kumpulkan stats ringkas"""
    return df  # stats dikumpulkan di final summary, bukan transform

def _apply_anomaly(df, spec):
    """tandai anomaly via z-score; spec: {column, threshold: 2.0}"""
    if df.empty:
        return df
    col = spec.get("column")
    thr = float(spec.get("threshold", 2.0))
    if not col or col not in df.columns:
        return df
    try:
        s = pd.to_numeric(df[col], errors="coerce")
        mean = s.mean()
        std = s.std(ddof=0)
        if std == 0 or pd.isna(std):
            return df
        z = (s - mean) / std
        df = df.copy()
        df["_zscore"] = z
        df["_is_anomaly"] = z.abs() > thr
        return df
    except Exception:
        return df

def _apply_limit(df, spec):
    n = int(spec.get("n") or spec.get("limit") or 20)
    return df.head(n)

_OP_HANDLERS = {
    "filter": _apply_filter,
    "group_by": _apply_group_aggregate,
    "aggregate": _apply_group_aggregate,
    "sort": _apply_sort,
    "rank": _apply_rank,
    "pivot": _apply_pivot,
    "percentage_change": _apply_percentage_change,
    "compare_period": _apply_percentage_change,  # alias
    "statistics": _apply_statistics,
    "anomaly": _apply_anomaly,
    "anomaly_detection": _apply_anomaly,
    "describe": _apply_statistics,
    "limit": _apply_limit,
}

def _collect_facts(df, original_rows):
    """facts: row_count, numeric summary ringkas"""
    facts = {"row_count": len(original_rows), "result_rows": len(df)}
    if df.empty:
        return facts
    # numeric cols summary
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist() if HAS_PANDAS else []
    for col in numeric_cols[:6]:  # cap 6 kolom
        try:
            facts[col] = {"sum": float(df[col].sum()), "mean": float(df[col].mean()), "min": float(df[col].min()), "max": float(df[col].max())}
        except Exception:
            pass
    return facts

def analyze(rows, operations, max_result_rows=20):
    """
    Batch analytical — 1 call, N ops sequential, hanya final result ke LLM.
    operations: list[{type: str, ...spec}]
    return: {facts, derived_metrics, comparisons, rankings, anomalies, result: [rows], truncated: bool}
    """
    if not HAS_PANDAS:
        raise RuntimeError("pandas not installed")
    if not isinstance(operations, (list, tuple)):
        raise ValueError("operations must be list")
    for op in operations:
        t = op.get("type")
        if t not in SUPPORTED_OPS:
            raise ValueError(f"unsupported op type: {t}. allowed: {sorted(SUPPORTED_OPS)}")

    original_rows = rows or []
    df = _to_df(original_rows)

    # jalankan ops sequential
    for op in operations:
        handler = _OP_HANDLERS.get(op.get("type"))
        if handler:
            df = handler(df, op)

    truncated = len(df) > max_result_rows
    result_df = df.head(max_result_rows)

    # build sections (§13)
    facts = _collect_facts(result_df, original_rows)

    # derived_metrics: kolom *_pct_change
    derived = {}
    for col in result_df.columns:
        if col.endswith("_pct_change"):
            vals = result_df[col].dropna().tolist()[:5]
            derived[col] = [round(float(v), 2) for v in vals]

    # comparisons: jika ada pct_change, ringkas
    comparisons = []
    for col in result_df.columns:
        if col.endswith("_pct_change") and not result_df.empty:
            try:
                last = result_df[col].dropna().iloc[-1] if not result_df[col].dropna().empty else None
                if last is not None:
                    comparisons.append({"metric": col.replace("_pct_change",""), "change_pct": round(float(last), 2)})
            except Exception:
                pass

    # rankings: jika ada rank op, result sudah terurut
    rankings = []
    has_rank = any(o.get("type") == "rank" for o in operations)
    if has_rank and not result_df.empty:
        # ambil 2 kolom pertama sebagai label+value
        cols = list(result_df.columns)
        for _, row in result_df.iterrows():
            rankings.append({k: (float(v) if isinstance(v, (np.floating, np.integer)) else v) for k, v in row.items()})
            if len(rankings) >= 5:
                break

    # anomalies
    anomalies = []
    if "_is_anomaly" in result_df.columns:
        anom = result_df[result_df["_is_anomaly"] == True]
        for _, row in anom.iterrows():
            anomalies.append({k: (float(v) if isinstance(v, (np.floating, np.integer)) else v) for k, v in row.items()})

    # statistics
    stats = {}
    if any(o.get("type") in ("statistics","describe") for o in operations) and not result_df.empty:
        try:
            desc = result_df.describe(include=[np.number]).to_dict()
            # keep only mean/std/min/max
            for col, d in desc.items():
                stats[col] = {k: round(float(v), 2) for k, v in d.items() if k in ("mean","std","min","max","count")}
        except Exception:
            pass

    # finalize result rows — coerce numpy types
    result_rows = json.loads(json.dumps(result_df.to_dict(orient="records"), default=str))

    return {
        "facts": facts,
        "derived_metrics": derived,
        "comparisons": comparisons,
        "rankings": rankings if has_rank else [],
        "anomalies": anomalies,
        "statistics": stats,
        "result": result_rows,
        "truncated": truncated,
        "total_result_rows": len(df),
        "operations_applied": [o.get("type") for o in operations],
    }

def analyze_template(template, params=None, operations=None, max_result_rows=20):
    """
    Helper: SQL (via simoge_db) -> pandas batch -> small result.
    Dipakai oleh server.py agar LLM tidak pernah terima 50K rows.
    """
    from simoge_db import run as simoge_run
    params = params or {}
    operations = operations or []
    r = simoge_run(template, **params)
    rows = r.get("rows") or []
    analytical = analyze(rows, operations, max_result_rows=max_result_rows)
    # packet envelope
    return {
        "template": template,
        "params": params,
        "sql": r.get("sql"),
        "elapsed_ms": r.get("elapsed_ms"),
        "analytical": analytical,
        "explanation": r.get("explanation"),
    }
