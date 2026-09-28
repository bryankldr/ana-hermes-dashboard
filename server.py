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
import subprocess
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
import terminal as ana_terminal  # noqa: E402
import voice            # noqa: E402

PORT = int(os.environ.get("ANA_PORT", "8730"))
API_TOKEN = secrets.token_urlsafe(32)
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



def _scan_projects():
    """Scan WORKDIR for git repos, return project cards."""
    import subprocess
    workdir = pathlib.Path(runtime.WORKDIR).expanduser()
    projects = []
    try:
        for d in sorted(workdir.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            git_dir = d / ".git"
            if not git_dir.exists():
                continue
            def _run(cmd):
                try:
                    r = subprocess.run(cmd, cwd=d, text=True, capture_output=True, timeout=10)
                    return (r.stdout or r.stderr).strip()
                except Exception:
                    return ""
            branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "?"
            last_commit = _run(["git", "log", "-1", "--format=%h %s (%cr)"]) or "no commits"
            if "fatal:" in last_commit or "error:" in last_commit.lower():
                last_commit = "git error"
            dirty = _run(["git", "status", "--porcelain"])
            dirty_count = len([l for l in dirty.splitlines() if l.strip()]) if dirty else 0
            projects.append({
                "name": d.name,
                "path": str(d),
                "branch": branch,
                "last_commit": last_commit,
                "dirty": dirty_count,
                "dirty_files": dirty.splitlines()[:5] if dirty else []
            })
    except Exception as e:
        projects.append({"name": "error", "error": str(e)[:200]})
    return {"projects": projects, "workdir": str(workdir)}


def _list_sessions():
    """Return recent Hermes sessions grouped by time period."""
    try:
        base = runtime._hermes_base()
        proc = subprocess.run(base + ["sessions", "list"], cwd=runtime.WORKDIR,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        out = (proc.stdout or proc.stderr or "").strip()
        sessions = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("Title") or line.startswith("─"):
                continue
            parts = line.split()
            if len(parts) >= 4:
                sid = parts[-1]
                if runtime.valid_session(sid):
                    title = " ".join(parts[:-3]) or "—"
                    last_active = parts[-3] + " " + parts[-2]
                    sessions.append({"id": sid, "title": title[:60], "last_active": last_active})
            if len(sessions) >= 50:
                break
        # Group by time period
        groups = {"today": [], "yesterday": [], "last_week": [], "older": []}
        for s in sessions:
            la = s["last_active"].lower()
            if "m ago" in la or "h ago" in la or "just now" in la:
                groups["today"].append(s)
            elif "d ago" in la:
                days = 0
                for part in la.split():
                    if part.isdigit():
                        days = int(part)
                        break
                if days == 1:
                    groups["yesterday"].append(s)
                elif days <= 7:
                    groups["last_week"].append(s)
                else:
                    groups["older"].append(s)
            else:
                groups["older"].append(s)
        return {"groups": groups, "current": SESSION["id"]}
    except Exception as e:
        return {"groups": {"today": [], "yesterday": [], "last_week": [], "older": []}, "current": SESSION["id"], "error": str(e)[:200]}


def _load_briefing():
    """Read latest daily note from vault, extract Briefing section."""
    import os
    vault = os.environ.get("OBSIDIAN_VAULT_PATH", "")
    if not vault:
        return {"briefing": "", "source": "OBSIDIAN_VAULT_PATH not set", "date": ""}
    daily = pathlib.Path(vault) / "10 Daily"
    if not daily.exists():
        return {"briefing": "", "source": str(daily), "date": ""}
    # find latest daily note
    notes = sorted(daily.glob("*.md"), reverse=True)
    if not notes:
        return {"briefing": "", "source": str(daily), "date": ""}
    latest = notes[0]
    text = latest.read_text(encoding="utf-8", errors="replace")
    # extract ## Briefing section
    m = re.search(r"##\s*Briefing\s*\n(.*?)(?=\n##\s|\Z)", text, re.S | re.I)
    briefing = m.group(1).strip() if m else ""
    return {"briefing": briefing, "source": str(latest), "date": latest.stem}

def _vault_status():
    """Vault + skill inventory for HUD panels."""
    try:
        skill_note = ROOT / "SKILL" / "skill_note.md"
        skill_exists = skill_note.exists()
        skill_preview = ""
        if skill_exists:
            t = skill_note.read_text(encoding="utf-8", errors="replace")
            skill_preview = t[:800]
        # count daily notes
        vault = os.environ.get("OBSIDIAN_VAULT_PATH", "")
        daily_count = 0
        if vault:
            daily = pathlib.Path(vault) / "10 Daily"
            if daily.exists():
                daily_count = len(list(daily.glob("*.md")))
        return {"skill_note_exists": skill_exists, "skill_preview": skill_preview, "daily_count": daily_count, "vault": vault}
    except Exception as e:
        return {"error": str(e)[:200]}

def _avd_status():
    """Check AVD Pixel_9 + adb status."""
    try:
        emu = pathlib.Path.home() / "Android" / "Sdk" / "emulator" / "emulator"
        avds = ""
        try:
            r = subprocess.run([str(emu), "-list-avds"], text=True, capture_output=True, timeout=8)
            avds = (r.stdout or "").strip()
        except Exception:
            pass
        adb_out = ""
        try:
            r2 = subprocess.run(["adb", "devices"], text=True, capture_output=True, timeout=5)
            adb_out = (r2.stdout or r2.stderr or "").strip()
        except Exception as e:
            adb_out = str(e)[:200]
        # parse device state
        device = "offline"
        boot = ""
        if "emulator-5554" in adb_out:
            if "device" in adb_out:
                device = "device"
            elif "offline" in adb_out:
                device = "offline"
            try:
                r3 = subprocess.run(["adb", "-s", "emulator-5554", "shell", "getprop", "sys.boot_completed"], text=True, capture_output=True, timeout=5)
                boot = (r3.stdout or "").strip()
            except Exception:
                pass
        return {"avds": avds, "adb": adb_out[:500], "device": device, "boot_completed": boot}
    except Exception as e:
        return {"error": str(e)[:200]}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

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
            return self._json(_scan_projects())
        if p == "/api/briefing":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            return self._json(_load_briefing())
        if p == "/api/sessions":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            return self._json(_list_sessions())
        if p == "/api/vault":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            return self._json(_vault_status())
        if p == "/api/avd":
            if not self._token_ok():
                return self._json({"error": "unauthorized"}, 401)
            return self._json(_avd_status())
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
        f = (UI / rel).resolve()
        if not str(f).startswith(str(UI.resolve())) or not f.is_file():
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

        if p == "/api/layout":
            try:
                payload = json.loads(raw or b"{}")
                layout_file = ROOT / "layout.json"
                # validate: layouts must be dict, each entry is dict
                layouts = payload.get("layouts", {})
                if not isinstance(layouts, dict):
                    return self._json({"error": "layouts must be dict"}, 400)
                for k, v in layouts.items():
                    if not isinstance(k, str) or not isinstance(v, dict):
                        return self._json({"error": "invalid layout entry"}, 400)
                data = {"locked": bool(payload.get("locked", True)), "layouts": layouts}
                layout_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                return self._json(data)
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            except Exception as e:
                return self._json({"error": str(e)[:200]}, 500)

        if p == "/api/session":
            try:
                payload = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            sid = payload.get("session_id")
            if sid and runtime.valid_session(sid):
                SESSION["id"] = str(sid)
                return self._json({"ok": True, "session": SESSION["id"]})
            SESSION["id"] = None
            return self._json({"ok": True, "session": None})

        if p == "/api/speak":
            try:
                text = (json.loads(raw or b"{}").get("text") or "").strip()
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
                body = json.loads(raw or b"{}")
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
                vid = (json.loads(raw or b"{}").get("voice_id") or "").strip()
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
                v = (json.loads(raw or b"{}").get("mode") or "").strip().lower()
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
                body = json.loads(raw or b"{}")
                action = (body.get("action") or "").strip().lower()
                if action == "start":
                    emu = str(pathlib.Path.home() / "Android" / "Sdk" / "emulator" / "emulator")
                    # check if already running
                    try:
                        r = subprocess.run(["adb", "devices"], text=True, capture_output=True, timeout=5)
                        if "emulator-5554" in (r.stdout or "") and "device" in (r.stdout or ""):
                            return self._json({"ok": True, "msg": "AVD already running (emulator-5554 device)"})
                    except Exception:
                        pass
                    subprocess.Popen([emu, "-avd", "Pixel_9", "-gpu", "host", "-no-snapshot-load"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                    return self._json({"ok": True, "msg": "AVD Pixel_9 starting..."})
                elif action == "stop":
                    try:
                        subprocess.run(["adb", "-s", "emulator-5554", "emu", "kill"], text=True, timeout=10, capture_output=True)
                    except Exception as e:
                        return self._json({"ok": False, "error": str(e)[:200]}, 500)
                    return self._json({"ok": True, "msg": "AVD stop signal sent"})
                else:
                    return self._json({"error": "action must be start|stop"}, 400)
            except Exception as e:
                return self._json({"error": str(e)[:300]}, 500)

        # ── terminal endpoints ──────────────────────────────
        if p == "/api/terminal":
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "bad json"}, 400)
            action = (body.get("action") or "").strip()
            if action == "create":
                cols = max(20, min(200, int(body.get("cols", 80))))
                rows = max(5, min(60, int(body.get("rows", 24))))
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
                cols = max(20, min(200, int(body.get("cols", t.cols))))
                rows = max(5, min(60, int(body.get("rows", t.rows))))
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

        if p == "/api/run":
            if not RUN_LOCK.acquire(blocking=False):
                return self._json({"error": "ANA is already processing a request"}, 409)
            try:
                return self._stream_run(raw)
            finally:
                RUN_LOCK.release()

        return self._json({"error": "no such endpoint"}, 404)

    # ── the run: NDJSON stream of events ─────────────────────
    def _stream_run(self, raw):
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "bad json"}, 400)
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
