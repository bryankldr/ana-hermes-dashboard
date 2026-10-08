"""ana_mode_tool — ANNA switches HUD mode herself.

Dashboard owns mode state (.ana_mode + /api/mode). ANNA owns the decision:
if the question needs table/chart/grid, she switches to coding herself,
renders, then MUST switch back to asisten before the final TTS delta.

Usage from Hermes tool:
  from ana_mode_tool import set_mode, get_mode
  set_mode("coding")   # before heavy work
  ... show_spatial_chart / call_pandas_tool ...
  set_mode("asisten")  # before final answer — mandatory

Auto-restore: if ANNA switches to coding and forgets to restore, server
auto-restores to asisten 90s after the run completes (fallback, not primary).
"""
from __future__ import annotations
import json, os, pathlib, urllib.request, urllib.error

ROOT = pathlib.Path("/home/bryankldr/PROYEK_2026/ana-hermes-dashboard")  # fixed absolute
TOKEN_FILE = ROOT / ".ana_token"
MODE_FILE = ROOT / ".ana_mode"
HOST = "127.0.0.1:8730"

def _token() -> str:
    try: return TOKEN_FILE.read_text().strip()
    except OSError: return ""

def _post_mode(mode: str) -> dict:
    tok = _token()
    url = f"http://{HOST}/api/mode"
    body = json.dumps({"mode": mode}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type":"application/json","x-ana-token": tok,"Host": HOST,"Origin": f"http://{HOST}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try: j=json.loads(e.read().decode() or "{}")
        except: j={}
        raise RuntimeError(j.get("error") or f"HTTP {e.code}") from None
    except Exception as e:
        # fallback: direct file write (server down but local file still drives next restart)
        if mode in ("asisten","coding"):
            try: MODE_FILE.write_text(mode)
            except: pass
            return {"ok": True, "mode": mode, "fallback": "file"}
        raise RuntimeError(str(e)[:200]) from None

def get_mode() -> str:
    """Return current mode (asisten/coding) without switching."""
    # try server
    try:
        tok=_token()
        req=urllib.request.Request(f"http://{HOST}/api/mode", headers={"x-ana-token":tok,"Host":HOST,"Origin":f"http://{HOST}"})
        with urllib.request.urlopen(req, timeout=3) as r:
            j=json.loads(r.read().decode() or "{}")
            if j.get("mode") in ("asisten","coding"): return j["mode"]
    except: pass
    try: v=MODE_FILE.read_text().strip().lower()
    except: v=""
    return v if v in ("asisten","coding") else "asisten"

def set_mode(mode: str) -> dict:
    """Switch HUD mode. Returns {ok, mode}. ANNA must call set_mode('asisten') before final delta."""
    m=(mode or "").strip().lower()
    if m not in ("asisten","coding"): raise ValueError("mode must be asisten or coding")
    return _post_mode(m)

# CLI for terminal direct use
if __name__=="__main__":
    import sys
    if len(sys.argv)<2 or sys.argv[1] not in ("get","set"):
        print('usage: ana_mode_tool.py get | set [asisten|coding]'); raise SystemExit(2)
    if sys.argv[1]=="get": print(json.dumps({"mode": get_mode()}, ensure_ascii=False))
    else:
        if len(sys.argv)<3: print("need mode"); raise SystemExit(2)
        print(json.dumps(set_mode(sys.argv[2]), ensure_ascii=False))
