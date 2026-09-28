"""
ANA Live — a HUD that drives Hermes Agent.

    python3 server.py

The brain is your own Hermes Agent CLI/profile. Hermes keeps access to the same
configured tools, browser/Chrome automation, MCP servers, skills, memory, and
third-party integrations that your normal Hermes sessions have. Voice can use the
browser Web Speech API, with optional server-side ElevenLabs STT/TTS if present.
"""
import json
import mimetypes
import os
import pathlib
import secrets
import sys
import threading
import queue
import re
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent
UI = ROOT / "ui"

# load .env before importing anything that reads os.environ
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import commands         # noqa: E402
import runtime          # noqa: E402
import services         # noqa: E402
import terminal as ana_terminal  # noqa: E402
import voice            # noqa: E402

PORT = int(os.environ.get("ANA_PORT", "8730"))
API_TOKEN = os.environ.get("ANA_TOKEN") or secrets.token_urlsafe(32)
# Persist the token so local tooling (smoke.py, the HUD) can pick it up
# without a restart loop. Only the token is written — never a secret value.
try:
    (ROOT / ".ana_token").write_text(API_TOKEN + "\n", encoding="utf-8")
except OSError:
    pass
RUN_LOCK = threading.Lock()
MAX_JSON_BODY = 1024 * 1024
MAX_AUDIO_BODY = 12 * 1024 * 1024

# The Ana persona, appended to every run. Without it, the model answers as a
# coding agent and narrates its own tooling — which is not what you want spoken
# out loud. Edit persona.md to change how it talks.
_PERSONA_FILE = ROOT / "persona.md"


MODE_FILE = ROOT / ".ana_mode"
def _load_mode():
    try:
        v = MODE_FILE.read_text().strip().lower()
        return v if v in ("asisten","coding") else "coding"
    except OSError:
        return os.environ.get("ANA_MODE","coding").strip().lower() or "coding"
MODE = {"v": _load_mode()}


def _clamp(value, lo, hi, default):
    """Terminal dimensions arrive as JSON, so they can be a string, a list or
    None. int() raises on any of those and would kill the request thread, so
    anything unusable falls back to the caller's default."""
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return default


def get_mode(): return MODE["v"]
def set_mode(v):
    v = (v or "").strip().lower()
    if v not in ("asisten","coding"): raise ValueError("mode must be asisten or coding")
    MODE["v"] = v
    try: MODE_FILE.write_text(v)
    except OSError: pass
    return v

# One continuing Hermes conversation until the user hits /new.
SESSION: dict[str, str | None] = {"id": None}

def persona():
    try:
        base = _PERSONA_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        base = ""
    extra = commands.context_block()
    mode = get_mode()
    overlay = "[MODE: asisten] Jawab 1-2 kalimat, no markdown/code/tabel, untuk TTS." if mode=="asisten" else "[MODE: coding] Mode agen koding: boleh markdown, code block, tabel, path exact. Jelaskan lengkap & verifikasi pakai output real."
    return "\n\n".join(x for x in (base, overlay, extra) if x)



class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # With HTTP/1.1 keep-alive and no socket timeout, a client that opens a
    # connection and then goes quiet pins its thread for the life of the
    # process, and ThreadingHTTPServer spawns one thread per connection without
    # a ceiling. 30s of silence is far longer than any real request here needs
    # and lets the server reap the thread itself.
    timeout = 30

    def log_message(self, fmt, *args):
        if os.environ.get("ANA_VERBOSE"):
            sys.stderr.write("  " + (fmt % args) + "\n")

    # ── helpers ──────────────────────────────────────────────
    def _json(self, body, code=200):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _bytes(self, data, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _read(self, limit):
        n = int(self.headers.get("Content-Length", 0))
        if n < 0 or n > limit:
            raise ValueError(f"request body exceeds {limit} bytes")
        return self.rfile.read(n) if n else b""

    def _host_ok(self):
        host = self.headers.get("Host", "")
        return host in {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        return origin in {
            f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"
        }

    def _token_ok(self):
        supplied = self.headers.get("X-Ana-Token", "")
        if supplied and secrets.compare_digest(supplied, API_TOKEN):
            return True
        # Query token only for GET streaming where headers cannot be set (still localhost-only)
        path_only = urlparse(self.path).path
        if self.command == "GET" and path_only == "/api/terminal-stream":
            try:
                qs = parse_qs(urlparse(self.path).query)
                qtoken = (qs.get("token", [""])[0] or qs.get("t", [""])[0] or "").strip()
                if qtoken and secrets.compare_digest(qtoken, API_TOKEN):
                    return True
            except Exception:
                pass
        return False

    # ── GET ──────────────────────────────────────────────────
    def do_GET(self):
        if not self._host_ok():
            return self._json({"error": "invalid host"}, 403)
        p = urlparse(self.path).path
        if p == "/api/status":
            return self._json(dict(
                runtime=runtime.runtime_kind(),
                permission=runtime.PERMISSION,
                profile=runtime.PROFILE,
                source=runtime.SOURCE,
                workdir=runtime.WORKDIR,
                model=runtime.MODEL or "Hermes default",
                tools=runtime.hermes_tools_snapshot(),
                browser_stt=True,
                browser_tts=True,
                voice_mode=os.environ.get("ANA_VOICE_MODE", "elevenlabs" if voice.available() else "browser"),
                voice_id=voice.voice_id() if voice.available() else "browser",
                stt="elevenlabs" if voice.available() else "browser",
                tts="elevenlabs" if voice.available() else "browser",
                session=SESSION["id"]))
        if p == "/api/voices":
            cur = voice.voice_id()
            has_el = voice.has_eleven() if hasattr(voice, "has_eleven") else bool(os.environ.get("ELEVENLABS_API_KEY"))
            return self._json(dict(current=cur, model=os.environ.get("ELEVENLABS_MODEL","eleven_multilingual_v2"), available=voice.available(), has_eleven=has_el, voices=voice.curated_voices()))
        if p == "/api/mode":
            return self._json(dict(mode=get_mode()))
        if p == "/api/jobs":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            # finished background missions, reported once each
            return self._json(dict(done=commands.take_finished(),
                                   running=[j for j in commands.jobs_snapshot()
                                            if j["status"] == "running"]))
        if p == "/api/terminals":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            with ana_terminal._LOCK:
                ana_terminal._cleanup_locked()
                sessions = {
                    sid: {"cols": t.cols, "rows": t.rows, "alive": t.alive,
                          "created_at": getattr(t, "created_at", 0),
                          "ttl": getattr(t, "ttl", 3600)}
                    for sid, t in ana_terminal._SESSIONS.items()
                }
            return self._json({"terminals": sessions, "count": len(sessions)})

        if p == "/api/projects":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            return self._json(services.scan_projects(runtime.WORKDIR))
        if p == "/api/briefing":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            return self._json(services.load_briefing())
        if p == "/api/sessions":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            return self._json(services.list_sessions(
                runtime._hermes_base(), runtime.WORKDIR, runtime.valid_session, SESSION["id"]))
        if p == "/api/vault":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            return self._json(services.vault_status())
        if p == "/api/avd":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            return self._json(services.avd_status())
        if p == "/api/missions":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            try:
                d = commands.load()
                tasks = d.get("tasks", [])[-20:]
                missions = d.get("missions", [])[-20:]
                return self._json({"tasks": tasks, "missions": missions, "goal": d.get("goal","")})
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 500)
        if p == "/api/layout":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            layout_file = ROOT / "layout.json"
            if layout_file.exists():
                try:
                    return self._json(json.loads(layout_file.read_text()))
                except Exception as e:
                    return self._json({"error": str(e)}, 500)
            return self._json({"locked": True, "layouts": {}})
        if p == "/api/terminal-stream":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            qs = parse_qs(urlparse(self.path).query)
            tid = (qs.get("id", [""])[0] or "").strip()
            return self._terminal_stream(tid)
        rel = "index.html" if p == "/" else p.lstrip("/")
        # A plain startswith() check passes for "../ui_secret" and
        # "../uix/anything" because there is no separator between the prefix
        # and the attacker-controlled part. relative_to() is exact.
        try:
            f = (UI / rel).resolve()
            f.relative_to(UI.resolve())
        except (ValueError, OSError):
            return self._bytes(b"not found", "text/plain", 404)
        if not f.is_file():
            return self._bytes(b"not found", "text/plain", 404)
        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        data = f.read_bytes()
        if rel == "index.html":
            data = data.replace(b"__ANA_TOKEN__", API_TOKEN.encode())
        return self._bytes(data, ctype)

    # ── terminal stream (GET long-poll) ──────────────
    def _terminal_stream(self, tid):
        t = ana_terminal.get(tid)
        if not t:
            return self._json({"error": "terminal not found"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            while t.alive:
                try:
                    data = t.queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                if not data:
                    continue
                self.wfile.write(data)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ── POST ─────────────────────────────────────────
    def do_POST(self):
        p = urlparse(self.path).path
        if not self._host_ok() or not self._origin_ok():
            return self._json({"error": "request origin rejected"}, 403)
        if not self._token_ok():
            return self._json({"error": "unauthorized"}, 401)
        ctype = self.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if p in {"/api/run", "/api/speak", "/api/new", "/api/cancel"} and ctype != "application/json":
            return self._json({"error": "application/json required"}, 415)
        if p == "/api/listen" and not ctype.startswith("audio/"):
            return self._json({"error": "audio content type required"}, 415)
        try:
            raw = self._read(MAX_AUDIO_BODY if p == "/api/listen" else MAX_JSON_BODY)
        except (TypeError, ValueError):
            return self._json({"error": "request body too large"}, 413)
        # Parse once, for every JSON endpoint. Valid JSON that is not an object
        # (a bare string, number or list) used to reach `.get()` outside the
        # try below, so the handler thread died and the client saw a closed
        # socket with no status line at all instead of a 400.
        if p not in {"/api/listen"} and ctype == "application/json":
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            if not isinstance(body, dict):
                return self._json({"error": "body must be a JSON object"}, 400)
        else:
            body = {}

        if p == "/api/layout":
            try:
                layout_file = ROOT / "layout.json"
                # validate: layouts must be dict, each entry is dict
                layouts = body.get("layouts", {})
                if not isinstance(layouts, dict):
                    return self._json({"error": "layouts must be dict"}, 400)
                for k, v in layouts.items():
                    if not isinstance(k, str) or not isinstance(v, dict):
                        return self._json({"error": "invalid layout entry"}, 400)
                data = {"locked": bool(body.get("locked", True)), "layouts": layouts, "disabled": body.get("disabled", [])}
                layout_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                return self._json(data)
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 500)

        if p == "/api/session":
            sid = body.get("session_id")
            if sid and runtime.valid_session(sid):
                SESSION["id"] = str(sid)
                return self._json({"ok": True, "session": SESSION["id"]})
            SESSION["id"] = None
            return self._json({"ok": True, "session": None})

        if p == "/api/speak":
            try:
                text = (body.get("text") or "").strip()
                return self._bytes(voice.speak(text), "audio/mpeg")
            except Exception as e:                        # noqa: BLE001
                return self._json({"error": str(e)[:200]}, 503)

        if p == "/api/listen":
            try:
                mime = self.headers.get("Content-Type", "audio/webm")
                return self._json({"text": voice.transcribe(raw, mime)})
            except Exception as e:                        # noqa: BLE001
                return self._json({"error": str(e)[:300], "text": ""}, 503)

        if p == "/api/voice-preview":
            try:
                vid = (body.get("voice_id") or "").strip()
                txt = (body.get("text") or "Halo Pak, ini preview suara ANA.").strip()[:400]
                # allow both ElevenLabs IDs and free Edge IDs
                if not __import__("re").match(r"^[A-Za-z0-9_\-]{8,60}$", vid):
                    raise ValueError("voice_id tidak valid")
                try:
                    data = voice.speak_with_voice(txt, vid)
                except Exception as he:
                    return self._json({"error": str(he)[:400]}, 502)
                return self._bytes(data, "audio/mpeg")
            except Exception as e:
                return self._json({"error": str(e)[:300]}, 500)
        if p == "/api/voice":
            try:
                vid = (body.get("voice_id") or "").strip()
                allowed = {v["id"] for v in voice.curated_voices()} | {v["id"] for v in getattr(voice, "FREE_VOICES", [])} | {"21m00Tcm4TlvDq8ikWAM"}
                if vid not in allowed: raise ValueError("voice_id tidak ada di daftar")
                # persist to .env
                envp = ROOT / ".env"
                txt = envp.read_text(encoding="utf-8") if envp.exists() else ""
                if "ELEVENLABS_VOICE_ID=" in txt:
                    txt = re.sub(r"ELEVENLABS_VOICE_ID=.*", f"ELEVENLABS_VOICE_ID={vid}", txt)
                else:
                    txt = txt.rstrip()+"\nELEVENLABS_VOICE_ID="+vid+"\n"
                envp.write_text(txt)
                os.environ["ELEVENLABS_VOICE_ID"] = vid
                return self._json(dict(ok=True, current=vid))
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 400)
        if p == "/api/mode":
            try:
                v = (body.get("mode") or "").strip().lower()
                set_mode(v)
                return self._json(dict(ok=True, mode=get_mode()))
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 400)
        if p == "/api/new":
            runtime.cancel_active()
            SESSION["id"] = None
            return self._json({"ok": True})

        if p == "/api/cancel":
            stopped = runtime.cancel_active()
            SESSION["id"] = None
            return self._json({"ok": True, "stopped": stopped})
        if p == "/api/avd":
            try:
                ok, info = services.avd_action(body.get("action"))
            except Exception as e:                        # noqa: BLE001
                return self._json({"error": str(e)[:200]}, 500)
            if ok is None:
                return self._json(info, 400)
            return self._json({"ok": ok, **info}, 200 if ok else 500)

        # ── terminal endpoints ──────────────────────────────
        if p == "/api/terminal":
            # A bad action, id or dimension is a client mistake, so nothing in
            # here may raise past this handler: the thread would die and the
            # client would see a closed socket rather than a status code.
            try:
                action = (body.get("action") or "").strip()
                if action == "create":
                    cols = _clamp(body.get("cols"), 20, 200, 80)
                    rows = _clamp(body.get("rows"), 5, 60, 24)
                    t = ana_terminal.create(cols, rows)
                    return self._json({"ok": True, "id": t.id, "cols": t.cols, "rows": t.rows})
                if action == "close":
                    tid = (body.get("id") or "").strip()
                    if not tid:
                        return self._json({"error": "id required"}, 400)
                    ok = ana_terminal.close(tid)
                    return self._json({"ok": ok})
                if action == "resize":
                    tid = (body.get("id") or "").strip()
                    t = ana_terminal.get(tid)
                    if not t:
                        return self._json({"error": "terminal not found"}, 404)
                    cols = _clamp(body.get("cols"), 20, 200, t.cols)
                    rows = _clamp(body.get("rows"), 5, 60, t.rows)
                    t.resize(cols, rows)
                    return self._json({"ok": True, "cols": t.cols, "rows": t.rows})
                if action == "input":
                    tid = (body.get("id") or "").strip()
                    t = ana_terminal.get(tid)
                    if not t:
                        return self._json({"error": "terminal not found"}, 404)
                    data = body.get("data", "")
                    if isinstance(data, str):
                        data = data.encode("utf-8", "surrogateescape")
                    if not isinstance(data, (bytes, bytearray)):
                        return self._json({"error": "data must be string"}, 400)
                    t.write(bytes(data))
                    return self._json({"ok": True})
                return self._json({"error": "unknown action"}, 400)
            except ValueError as e:
                return self._json({"error": str(e)[:200]}, 400)
            except OSError as e:
                # PTY creation can fail outright (no shell, fd exhaustion). The
                # terminal code closes its own fds, so this is a clean 503 and
                # not a dropped connection.
                return self._json({"error": str(e)[:200]}, 503)

        if p == "/api/run":
            if not RUN_LOCK.acquire(blocking=False):
                return self._json({"error": "ANA is already processing a request"}, 409)
            try:
                return self._stream_run(body)
            finally:
                RUN_LOCK.release()

        return self._json({"error": "no such endpoint"}, 404)

    # ── the run: NDJSON stream of events ─────────────────────
    def _stream_run(self, payload):
        # The body was parsed and type-checked in do_POST; re-reading the raw
        # bytes here meant a bare string or number crashed this thread after the
        # response headers were gone, so the client only saw a dropped socket.
        message = (payload.get("message") or "").strip()
        extra = (payload.get("system") or "").strip()
        system = "\n\n".join(x for x in (persona(), extra) if x) or None
        fresh = bool(payload.get("fresh"))
        if not message:
            return self._json({"error": "empty message"}, 400)
        if fresh:
            SESSION["id"] = None

        # -- natural language mode switch ("ganti ke mode asisten/coding", "ubah mode", etc.)
        _low = message.strip().lower()
        _m = None
        if any(k in _low for k in ("mode asisten", "mode coding")) or re.search(r"ganti.*mode|ubah.*mode|switch.*mode", _low):
            if "asisten" in _low: _m = "asisten"
            elif "coding" in _low: _m = "coding"
        if _m is not None:
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            def _emit(ev):
                self.wfile.write((json.dumps(ev) + "\n").encode())
                self.wfile.flush()
            try:
                set_mode(_m)
                _emit(dict(t="delta", text=f"Mode ANA diganti ke {_m}."))
            except Exception as e:
                _emit(dict(t="error", message=str(e)[:200]))
            _emit(dict(t="complete", ms=0))
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        def emit(ev):
            self.wfile.write((json.dumps(ev) + "\n").encode())
            self.wfile.flush()
        # -- the command matrix: /new /profile /goal /personality /kanban /mission /background /tools /status /browser
        cmd = commands.handle(
            message,
            runner=lambda m: runtime.run(m, None, persona()))
        if cmd:
            if cmd.get("note"):
                emit(dict(t="note", message=cmd["note"]))
            if cmd.get("fresh"):
                SESSION["id"] = None
            if cmd.get("message") is None:
                # answered locally — no model call needed
                emit(dict(t="delta", text=cmd.get("reply", "Done.")))
                emit(dict(t="complete", ms=0))
                return
            message = cmd["message"]
            system = "\n\n".join(x for x in (persona(), extra) if x) or None

        try:
            for ev in runtime.run(message, SESSION["id"], system):
                # Only remember a real Hermes session, never demo/mock identifiers.
                sid = ev.get("session_id")
                # Save session when Hermes emits it (from session_id: marker)
                if ev.get("t") == "session" and runtime.valid_session(sid):
                    SESSION["id"] = str(sid)
                # Only remember a session that actually COMPLETED. Storing it from
                # `status` (which fires at init) means one broken run poisons every
                # run after it with --resume <half-born session>.
                if ev.get("t") == "complete" and runtime.valid_session(sid):
                    SESSION["id"] = sid
                if ev.get("t") == "error":
                    SESSION["id"] = None       # drop a bad/stale session so the next run is fresh
                emit(ev)
        except (BrokenPipeError, ConnectionResetError):
            pass                                          # client navigated away
        except Exception as e:                            # noqa: BLE001
            try:
                emit(dict(t="error", message=str(e)[:300]))
            except OSError:
                pass


def main():
    kind = runtime.runtime_kind()
    brain = ("Hermes Agent (profile tools, skills, memory, MCP, browser integrations live)"
             if kind == "hermes" else "MOCK — Hermes CLI not reachable")
    vo = (f"ElevenLabs · {voice.voice_id()[:8]}…" if voice.available()
          else "none (add ELEVENLABS_API_KEY for voice)")
    perm = runtime.PERMISSION
    perm_note = ("  can run tools without asking — set ANA_PERMISSION=default to require approval"
                 if perm == "bypass" else "")

    print(f"""
  ANA · Hermes Live HUD
  ──────────────────────────────────────────────
  brain        {brain}
  profile      {runtime.PROFILE}
  workdir      {runtime.WORKDIR}
  permission   {perm}{perm_note}
  voice        {vo} + browser Web Speech fallback
  open         http://localhost:{PORT}
""", flush=True)

    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    if os.environ.get("ANA_OPEN", "1") != "0":
        webbrowser.open(f"http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  down.")
        srv.shutdown()


if __name__ == "__main__":
    main()
