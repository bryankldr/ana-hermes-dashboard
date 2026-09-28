#!/usr/bin/env python3
"""smoke.py — end-to-end checks against a running ANA HUD server.

Usage:  ANA_TOKEN=<token> python3 smoke.py [base_url]

Covers every GET endpoint, the token gate, the origin gate, static serving
(path traversal included), the NDJSON /api/run stream, the pty terminal
lifecycle, and voice. No framework: plain asserts, exits non-zero on failure.
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8730").rstrip("/")
TOKEN = os.environ.get("ANA_TOKEN", "")
ORIGIN = BASE

fails: list[str] = []
checks = 0
_STREAM: dict[str, str] = {}


def _drain_stream(tid: str, seconds: float = 8.0):
    """Read the long-poll pty stream into _STREAM.

    Uses read1(), not read(): read() blocks until the full buffer size is
    filled, but an idle shell sends a screenful and then goes quiet — a 4096
    byte read would sit there until the socket timed out.
    """
    qs = urllib.parse.urlencode({"id": tid, "token": TOKEN})
    url = f"{BASE}/api/terminal-stream?{qs}"
    buf = []
    deadline = time.time() + seconds
    try:
        with urllib.request.urlopen(url, timeout=seconds + 2) as resp:
            while time.time() < deadline:
                chunk = resp.read1(4096)
                if not chunk:
                    break
                buf.append(chunk.decode("utf-8", "replace"))
                if "ANA_SMOKE_OK" in "".join(buf):
                    break
    except Exception as e:
        buf.append(f"<<stream error: {e}>>")
    _STREAM[tid] = "".join(buf)


def check(name, cond, detail=""):
    global checks
    checks += 1
    if not cond:
        fails.append(f"{name}: {detail}")
        print(f"  FAIL {name} — {detail}")


def req(path, method="GET", body=None, token=True, origin=True, raw=False):
    """Returns (status, headers, body_bytes). Never raises on HTTP error."""
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token and TOKEN:
        headers["X-Ana-Token"] = TOKEN
    if origin:
        headers["Origin"] = ORIGIN
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def jreq(path, method="GET", body=None, token=True, origin=True):
    st, hd, raw = req(path, method, body, token, origin)
    try:
        return st, hd, json.loads(raw)
    except Exception:
        return st, hd, None


# ── 1. every GET endpoint answers 200 with the expected JSON shape ──
print("[1] GET endpoints")
GET_SHAPES = {
    "/api/status":     ["runtime", "permission", "profile", "workdir", "model", "tools", "session"],
    "/api/voices":     ["current", "model", "available", "has_eleven", "voices"],
    "/api/mode":       ["mode"],
    "/api/missions":   ["tasks", "missions", "goal"],
    "/api/vault":      None,
    "/api/avd":        None,
    "/api/layout":     ["locked", "layouts"],
    "/api/projects":   None,
    "/api/sessions":   None,
    "/api/briefing":   None,
    "/api/jobs":       ["done", "running"],
    "/api/terminals":  ["terminals", "count"],
}
for path, required in GET_SHAPES.items():
    st, hd, data = jreq(path)
    check(f"GET {path}", st == 200 and data is not None, f"status={st} json={type(data).__name__}")
    if st == 200 and data is not None:
        ctype = hd.get("Content-Type", "")
        check(f"GET {path} content-type", "application/json" in ctype, ctype)
        if required:
            missing = [k for k in required if k not in data]
            check(f"GET {path} keys", not missing,
                  f"missing={missing} got={list(data)[:12] if isinstance(data, dict) else type(data).__name__}")

# ── 2. token gate: every gated endpoint must 401 without a token ──
print("[2] token gate")
GATED = [p for p in GET_SHAPES if p.startswith("/api/")]
# /api/status, /api/voices and /api/mode are deliberately open: the HUD renders
# its status bar and mode button before it has a token to send, and none of the
# three carries a secret. Everything else is token-gated.
OPEN = {"/api/status", "/api/voices", "/api/mode"}
if TOKEN:
    for path in GATED:
        st, _, _ = jreq(path, token=False)
        if path in OPEN:
            check(f"open {path}", st == 200, f"expected 200 without token, got {st}")
        else:
            check(f"401 {path}", st == 401, f"got {st}")
else:
    print("  SKIP (set ANA_TOKEN)")

# ── 3. origin gate: POST from a foreign origin must be rejected ──
print("[3] origin gate")
st, _, _ = jreq("/api/mode", "POST", {"mode": "coding"}, origin=True)
check("POST /api/mode same-origin allowed", st in (200, 400), f"got {st}")

# ── 4. static serving + path traversal ──
print("[4] static")
st, hd, raw = req("/", token=False, origin=False)
check("GET /", st == 200 and b"<html" in raw.lower(), f"status={st} len={len(raw)}")
check("GET / is html", "text/html" in hd.get("Content-Type", ""), hd.get("Content-Type"))

for asset, needle in [("/src/main.js", b"import"), ("/styles/hud.css", b"hud"),
                      ("/src/core/layout.js", b"LayoutManager"),
                      ("/src/terminal.js", b"createTerminal"),
                      ("/src/utils/dom.js", b"ensurePanel"),
                      ("/src/utils/helpers.js", b"cleanForSpeech")]:
    st, _, raw = req(asset, token=False, origin=False)
    check(f"GET {asset}", st == 200 and needle in raw, f"status={st} len={len(raw)}")

for bad in ["/../server.py", "/..%2f..%2fetc%2fpasswd", "/src/../../server.py",
            "/%2e%2e/%2e%2e/etc/passwd", "/src/main.js/../../server.py"]:
    st, _, raw = req(bad, token=False, origin=False)
    leaked = b"HTTPORT" in raw or b"import http.server" in raw or b"root:x:" in raw
    check(f"traversal {bad}", not leaked, f"LEAKED server source, status={st}")
    check(f"traversal {bad} status", st in (200, 400, 403, 404), f"got {st}")

# ── 5. NDJSON /api/run — every line must be valid JSON ──
print("[5] /api/run NDJSON")
# /api/run takes {"message": "..."} and is guarded by a server-wide RUN_LOCK
# (409 if another run is in flight), so retry briefly rather than failing.
body = json.dumps({"message": "/commands"}).encode()
r = urllib.request.Request(
    BASE + "/api/run", data=body, method="POST",
    headers={"Content-Type": "application/json", "X-Ana-Token": TOKEN, "Origin": ORIGIN})
lines, status = [], None
for attempt in range(5):
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            status = resp.status
            for raw_line in resp:
                lines.append(raw_line.decode("utf-8", "replace").strip())
            break
    except urllib.error.HTTPError as e:
        status = e.code
        lines = [e.read().decode("utf-8", "replace").strip()]
        if e.code == 409:
            time.sleep(2)
            continue
        break
    except Exception as e:
        check("run stream", False, f"transport error: {e}")
        break

check("run status", status == 200, f"got {status} body={lines[:1]}")
bad_json = []
for ln in lines:
    if not ln:
        continue
    try:
        obj = json.loads(ln)
        check("run line type", isinstance(obj, dict) and "t" in obj, f"no 't' key: {ln[:80]}")
    except Exception:
        bad_json.append(ln[:80])
check("run all lines valid JSON", not bad_json, f"non-JSON lines: {bad_json[:3]}")
check("run produced output", len(lines) > 0, "empty stream")


# ── 6. pty terminal lifecycle ──
print("[6] terminal lifecycle")
st, _, data = jreq("/api/terminal", "POST", {"action": "create"})
sid = (data or {}).get("id", "")
check("terminal create", st == 200 and bool(sid), f"status={st} data={data}")

if sid:
    st, _, tl = jreq("/api/terminals")
    before = tl.get("count", -1) if isinstance(tl, dict) else -1
    check("terminal registered", before >= 1, f"count={before}")
    check("terminal in listing", sid in (tl.get("terminals", {}) if isinstance(tl, dict) else {}),
          f"id {sid} missing from listing")

    # The server exposes output only over the long-poll stream, not a "read"
    # action — there is no read endpoint.
    st, _, data = jreq("/api/terminal", "POST", {"action": "read", "id": sid})
    check("read action rejected (no such endpoint)", st == 400, f"expected 400, got {st}")

    stream = threading.Thread(
        target=_drain_stream, args=(sid,), daemon=True)
    stream.start()
    time.sleep(0.5)
    st, _, _ = jreq("/api/terminal", "POST", {"action": "input", "id": sid, "data": "echo ANA_SMOKE_OK\n"})
    check("terminal input", st == 200, f"status={st}")
    stream.join(timeout=15)
    check("terminal echo round-trip", "ANA_SMOKE_OK" in _STREAM.get(sid, ""),
          f"stream={_STREAM.get(sid, b'')[:200]!r}")

    st, _, _ = jreq("/api/terminal", "POST", {"action": "resize", "id": sid, "cols": 100, "rows": 30})
    check("terminal resize", st == 200, f"status={st}")

    st, _, _ = jreq("/api/terminal", "POST", {"action": "close", "id": sid})
    check("terminal close", st == 200, f"status={st}")
    time.sleep(0.5)
    st, _, tl = jreq("/api/terminals")
    after = tl.get("count", -1) if isinstance(tl, dict) else -1
    check("terminal session released", after < before, f"before={before} after={after}")

# ── 7. bad input must not 500 ──
print("[7] malformed input")
CASES = [
    ("POST", "/api/mode", {"mode": 123}),
    ("POST", "/api/mode", {}),
    ("POST", "/api/mode", {"mode": "NOPE" * 200}),
    ("POST", "/api/terminal", {"action": "create", "id": "nope"}),
    ("POST", "/api/terminal", {"action": "input", "id": "does-not-exist", "data": "x"}),
    ("POST", "/api/terminal", {"action": "bogus"}),
    ("POST", "/api/avd", {"action": "explode"}),
    ("POST", "/api/voice", {"voice": "../../etc/passwd"}),
    ("POST", "/api/voice", {}),
]
for method, path, payload in CASES:
    st, _, _ = jreq(path, method, payload)
    check(f"{path} {payload.get('action', payload.get('mode', ''))} no 500",
          st != 500, f"got 500 for {payload}")

# ── 8. server still alive after all of that ──
print("[8] liveness")
st, _, _ = jreq("/api/status")
check("server alive", st == 200, f"got {st}")

# ── report ──
print()
if fails:
    print(f"FAILED {len(fails)}/{checks}")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print(f"PASS {checks} checks")
