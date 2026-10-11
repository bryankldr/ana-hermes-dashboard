"""
Gateway-based runtime for the ANA HUD.

Replaces runtime.py's subprocess-based hermes chat with persistent
Hermes Gateway WebSocket connection. Provides the same event-stream
interface for server.py compatibility.
"""
import os
import re
import json
import time
import asyncio
import threading
from typing import Optional, Generator, Callable, Any, List, Dict

from gateway_client import HermesGatewayClient, DashboardGateway, GatewaySession, GatewayError


# Compatibility: same session ID pattern as runtime.py
_SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}$")


# Module-level attributes that server.py expects
MODEL = os.environ.get("ANA_MODEL", "").strip()
PROFILE = os.environ.get("HERMES_PROFILE", os.environ.get("ANA_PROFILE", "anna")).strip() or "anna"
SOURCE = os.environ.get("HERMES_SOURCE", "ana-dashboard").strip() or "ana-dashboard"
WORKDIR = os.path.expanduser(os.environ.get("ANA_WORKDIR", os.getcwd()))
PERMISSION = os.environ.get("ANA_PERMISSION", os.environ.get("HERMES_PERMISSION", "normal")).strip().lower()
RUNTIME = os.environ.get("ANA_RUNTIME", "auto").strip().lower()  # auto|hermes|mock
IDLE_TIMEOUT = int(os.environ.get("ANA_TIMEOUT", "120"))
RAW_LOG = os.environ.get("ANA_RAW_LOG", "").strip()
TOOLSETS = os.environ.get("HERMES_TOOLSETS", "").strip()

# Eksekusi paralel per-sesi-Hermes: tiap sid punya lock sendiri.
# Pola resmi Hermes (group_sessions_per_user): Alice dan Bob tak berbagi
# transcript — maka turn mereka pun tak boleh antre global. EXECUTION_LOCK
# dipertahankan sebagai fallback bila sid tak diketahui.
EXECUTION_LOCK = threading.RLock()
_SES_LOCKS: dict = {}
_SES_LOCKS_GUARD = threading.Lock()


def _ses_lock(sid):
    key = str(sid or "").strip() or "default"
    with _SES_LOCKS_GUARD:
        lk = _SES_LOCKS.get(key)
        if lk is None:
            lk = threading.RLock()
            _SES_LOCKS[key] = lk
        return lk
_ACTIVE_PROC = None
_ACTIVE_LOCK = threading.Lock()


def valid_session(sid):
    """Hermes emits timestamp-based IDs such as 20260808_031038_0ecb14.
    Gateway also uses shorter alphanumeric IDs like bce36bea."""
    if not sid:
        return False
    s = str(sid)
    # Hermes timestamp format: 20260808_031038_0ecb14
    # Gateway format: bce36bea (8+ alphanumeric)
    return bool(_SESSION_ID.match(s)) or (len(s) >= 8 and s.isalnum())


def _hermes_base():
    """Compatibility function - not used with gateway but kept for server.py imports."""
    return ["hermes"]
_GATEWAY_CLIENT: Optional[HermesGatewayClient] = None
_GATEWAY_LOCK = threading.Lock()
_GATEWAY_CONNECTED = threading.Event()
_GATEWAY_CONNECT_ERROR: Optional[str] = None
_GATEWAY_THREAD: Optional[threading.Thread] = None
_GATEWAY_LOOP: Optional[asyncio.AbstractEventLoop] = None
_CURRENT_SESSION_ID: Optional[str] = None
_SESSION_CREATED_EVENT = threading.Event()


def reset_session():
    """Drop cached gateway session so next run creates a fresh one.

    Root cause P0-A: server._clear_session() only clears SESSION id/meta,
    but _CURRENT_SESSION_ID persists -> fresh:true reuse old session.
    No gateway close needed; next run create_session() fresh.
    """
    global _CURRENT_SESSION_ID
    _CURRENT_SESSION_ID = None


def _discover_gateway_url() -> str | None:
    """Discover Hermes Gateway WS URL — single source of truth.

    Priority:
      1. ANA_GATEWAY_URL env (set by start.sh discovery or manual export)
      2. Live `hermes serve --port 0` via ss + curl __HERMES_SESSION_TOKEN__
      3. None (caller raises actionable error, no silent fallback to :37521)

    Port 37521 was a static fallback that never matches the actual
    `hermes serve --port 0` ephemeral port (e.g. 35405) and caused
    `[Errno 111] ('127.0.0.1', 37521)` when server.py ran without start.sh.
    """
    env_url = os.environ.get("ANA_GATEWAY_URL", "").strip()
    if env_url:
        return env_url
    # Try to discover from live hermes process (same logic as start.sh:108-122)
    try:
        import subprocess
        import re as _re
        ss = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, timeout=3)
        # Find hermes pid and sport
        m_pid = _re.search(r'"hermes".*?pid=(\d+)', ss.stdout)
        if m_pid:
            pid = m_pid.group(1)
            m_port = _re.search(rf"pid={pid}.*?127\.0\.0\.1:(\d+)", ss.stdout)
            # fallback: any 127.0.0.1:port on that pid line
            if not m_port:
                for line in ss.stdout.splitlines():
                    if f"pid={pid}" in line:
                        mm = _re.search(r"127\.0\.0\.1:(\d+)", line)
                        if mm:
                            m_port = mm
                            break
            if m_port:
                sport = m_port.group(1)
                # Fetch token from http://127.0.0.1:$SPORT/
                try:
                    import urllib.request
                    with urllib.request.urlopen(f"http://127.0.0.1:{sport}/", timeout=3) as resp:
                        html = resp.read().decode("utf-8", errors="ignore")
                        m_tok = _re.search(r'__HERMES_SESSION_TOKEN__="([^"]+)"', html)
                        if m_tok:
                            tok = m_tok.group(1)
                            os.environ["ANA_GATEWAY_URL"] = f"ws://127.0.0.1:{sport}/api/ws"
                            os.environ["ANA_GATEWAY_TOKEN"] = tok
                            return os.environ["ANA_GATEWAY_URL"]
                        # token not in page but port exists — still return URL
                        os.environ["ANA_GATEWAY_URL"] = f"ws://127.0.0.1:{sport}/api/ws"
                        return os.environ["ANA_GATEWAY_URL"]
                except Exception:
                    # port exists but http fetch failed — still try URL (token may be set separately)
                    os.environ["ANA_GATEWAY_URL"] = f"ws://127.0.0.1:{sport}/api/ws"
                    return os.environ["ANA_GATEWAY_URL"]
    except Exception:
        pass
    return None

def _get_gateway() -> HermesGatewayClient:
    """Get or create the singleton gateway client."""
    global _GATEWAY_CLIENT, _GATEWAY_THREAD, _GATEWAY_LOOP, _GATEWAY_CONNECTED, _GATEWAY_CONNECT_ERROR
    
    with _GATEWAY_LOCK:
        if _GATEWAY_CLIENT is not None and _GATEWAY_CLIENT.connected:
            return _GATEWAY_CLIENT
        
        # Create new gateway — discovered, never silent 37521 fallback
        gateway_url = _discover_gateway_url()
        if not gateway_url:
            raise RuntimeError(
                "ANA_GATEWAY_URL not set and Hermes Gateway not discoverable. "
                "Run via ./start.sh (auto-discovers `hermes serve --port 0`) or "
                "export ANA_GATEWAY_URL=ws://127.0.0.1:<SPORT>/api/ws and "
                "ANA_GATEWAY_TOKEN=$(curl -s http://127.0.0.1:<SPORT>/ | grep -o '__HERMES_SESSION_TOKEN__=\"[^\"]*\"')."
                " Check `ss -ltnp | grep hermes` and `ps aux | grep \"serve --port\"`."
            )
        profile = os.environ.get("HERMES_PROFILE", os.environ.get("ANA_PROFILE", "anna")).strip() or "anna"
        auth_token = os.environ.get("ANA_GATEWAY_TOKEN", "").strip() or None
        
        client = HermesGatewayClient(
            gateway_url=gateway_url,
            profile=profile,
            auth_token=auth_token,
        )
        _GATEWAY_CLIENT = client
        
        # Start background thread with event loop
        def run_loop():
            global _GATEWAY_LOOP
            _GATEWAY_LOOP = asyncio.new_event_loop()
            asyncio.set_event_loop(_GATEWAY_LOOP)
            try:
                connected = _GATEWAY_LOOP.run_until_complete(client.connect())
                if not connected:
                    _GATEWAY_CONNECT_ERROR = "Failed to connect to gateway"
                else:
                    _GATEWAY_CONNECTED.set()
                    # Create initial session
                    async def init_session():
                        global _CURRENT_SESSION_ID
                        try:
                            # Try to list and resume most recent session
                            sessions = await client.list_sessions(limit=1)
                            if sessions and sessions.get("sessions"):
                                latest = sessions["sessions"][0]
                                result = await client.resume_session(latest["id"])
                                _CURRENT_SESSION_ID = result.get("session_id")
                            else:
                                result = await client.create_session(title="ANA Dashboard Session")
                                _CURRENT_SESSION_ID = result.get("session_id")
                            _SESSION_CREATED_EVENT.set()
                        except Exception as e:
                            _GATEWAY_CONNECT_ERROR = str(e)
                            _SESSION_CREATED_EVENT.set()
                    
                    _GATEWAY_LOOP.run_until_complete(init_session())
            except Exception as e:
                _GATEWAY_CONNECT_ERROR = str(e)
                _SESSION_CREATED_EVENT.set()
                _GATEWAY_CONNECTED.set()
            _GATEWAY_LOOP.run_forever()
        
        _GATEWAY_THREAD = threading.Thread(target=run_loop, daemon=True, name="gateway-loop")
        _GATEWAY_THREAD.start()
        
        # Wait for connection and session init (with timeout)
        if not _GATEWAY_CONNECTED.wait(timeout=15):
            raise RuntimeError("Gateway connection timeout")
        
        if not _SESSION_CREATED_EVENT.wait(timeout=10):
            raise RuntimeError("Session creation timeout")
        
        if _GATEWAY_CONNECT_ERROR:
            raise RuntimeError(f"Gateway connection failed: {_GATEWAY_CONNECT_ERROR}")
        
        return client


def _run_async(coro):
    """Run a coroutine in the gateway's event loop and return result."""
    if _GATEWAY_LOOP is None:
        raise RuntimeError("Gateway event loop not running")
    
    future = asyncio.run_coroutine_threadsafe(coro, _GATEWAY_LOOP)
    return future.result(timeout=30)


def _run_async_stream(coro_func, *args, cancel_sid=None, stall_sec=None, **kwargs):
    """Run an async generator in the gateway's event loop, yielding results.

    cancel_sid (opsional): cek flag cancel milik sesi itu. Tanpa ini, fast-path
    barge-in membaca _CANCEL_EVENT global — cancel user A memutus stream
    user B yang sedang jalan paralel.

    stall_sec (opsional): batas detik tanpa event SAMA SEKALI sebelum stream
    dinyatakan macet (TimeoutError eksplisit). Tanpa ini submit ke sesi yang
    ditolak gateway diam-diam (session-scoped RPC rejected tanpa respons)
    menunggu selamanya: thread nyangkut pegang RUN_STATE, semua chat
    berikutnya 409 "already processing" — persis keluhan user 10:33/10:47
    (run 10:16 nyangkut, chat tak pernah sampai ANNA).
    """
    if _GATEWAY_LOOP is None:
        raise RuntimeError("Gateway event loop not running")
    import queue as _queue
    import time as _time
    q: _queue.Queue = _queue.Queue()
    done = threading.Event()
    error: list[Exception | None] = [None]
    try:
        stall = float(stall_sec) if stall_sec else 0.0
    except (TypeError, ValueError):
        stall = 0.0
    last_ev = _time.monotonic()

    async def _runner():
        try:
            async for event in coro_func(*args, **kwargs):
                q.put(event)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            error[0] = e
        finally:
            done.set()

    future = asyncio.run_coroutine_threadsafe(_runner(), _GATEWAY_LOOP)
    # Status submit gateway ("streaming" vs "queued"): turn antre resmi
    # BUKAN macet — stall watchdog tak boleh membunuhnya. Tanpa flag ini
    # turn antre (normal di gateway) dibunuh dashboard setelah 120s hening.
    _submit_queued = [False]
    def _cancel_flag():
        try:
            if cancel_sid:
                if _ses_cancelled(cancel_sid, int(_TURN_BY_SES.get(str(cancel_sid).strip() or "default", 0))):
                    return True
                # Global fallback HANYA untuk jalur legacy tanpa sid.
                # Tanpa gate ini, cancel user A memutus stream user B yang
                # sedang jalan paralel (kasus uji paralel 15:18).
                if str(cancel_sid).strip() in ("", "default"):
                    return _CANCEL_EVENT.is_set()
                return False
        except Exception:
            pass
        return _CANCEL_EVENT.is_set()
    try:
        while True:
            try:
                event = q.get(timeout=0.1)
                last_ev = _time.monotonic()
                try:
                    if isinstance(event, dict) and event.get("type") == "submit" and str(event.get("status") or "") == "queued":
                        _submit_queued[0] = True
                except Exception:
                    pass
                yield event
            except _queue.Empty:
                if done.is_set() and q.empty():
                    break
                # Barge-in fast path: if cancel flagged, nudge runner and keep draining
                if _cancel_flag():
                    try:
                        future.cancel()
                    except Exception:
                        pass
                    if done.is_set() and q.empty():
                        break
                # Stall watchdog: gateway menolak submit diam-diam (sesi
                # detached) = tak ada event sama sekali. Tanpa batas ini
                # thread menunggu selamanya dan pegang RUN_STATE.
                # PENGECUALIAN: turn antre resmi (status "queued") memang
                # hening sampai turn depan selesai — jangan bunuh. Batas
                # antre ikut ANA_RUN_STALL_SEC x3 (default 360s).
                _stall_lim = stall * 3 if _submit_queued[0] else stall
                if _stall_lim and (not done.is_set()) and (_time.monotonic() - last_ev) > _stall_lim:
                    try:
                        future.cancel()
                    except Exception:
                        pass
                    error[0] = TimeoutError(
                        f"gateway stall: no event for {stall:.0f}s "
                        f"(session detached/ditolak gateway?)")
                    done.set()
                    break
                continue
    finally:
        if not done.is_set():
            try:
                future.cancel()
            except Exception:
                pass
        if error[0]:
            raise error[0]


def runtime_kind():
    """Return 'hermes' if gateway is reachable, 'mock' otherwise."""
    try:
        client = _get_gateway()
        return "hermes" if client.connected else "mock"
    except Exception:
        return "mock"


def hermes_tools_snapshot(limit=36):
    """Return a compact list of enabled/visible Hermes toolsets/tools for UI status."""
    try:
        client = _get_gateway()
        if not client.connected:
            return []
        return ["gateway: connected to Hermes"]
    except Exception:
        return []


def _map_gateway_event(event: dict, started: float, first: bool) -> list:
    """Map gateway event to runtime.py event format."""
    events = []
    et = event.get("type") or event.get("method", "")
    
    # Gateway events have payload data inside "payload" field
    payload = event.get("payload", {})
    if isinstance(payload, dict):
        # Extract text from payload if present
        payload_text = payload.get("text", "")
    else:
        payload_text = ""
    
    # Also check for text at top level (backward compatibility)
    text = event.get("text", "") or event.get("delta", "") or payload_text
    
    if et == "session.info":
        sid = event.get("session_id")
        if valid_session(sid):
            events.append(dict(t="session", session_id=sid))

    elif et == "submit":
        # Status submit dari gateway: "streaming" (turn jalan) vs "queued"
        # (turn antre, jalan setelah turn aktif selesai). Tanpa event ini
        # turn antre terlihat mati 120s lalu timeout di sisi dashboard.
        st = str(event.get("status") or "streaming")
        if st == "queued":
            events.append(dict(t="note", message="Menunggu giliran (sesi sibuk) — jawaban menyusul otomatis."))
        else:
            events.append(dict(t="note", message="Turn diterima gateway."))
    
    elif et in ("message.delta", "delta", "text"):
        if first:
            events.append(dict(t="latency", ms=int((time.monotonic() - started) * 1000)))
        if text:
            events.append(dict(t="delta", text=text))
    
    # thinking.delta / reasoning.delta carry the CLI's kawaii spinner prose
    # ("(¬‿¬) reasoning...", "( •_•)>⌐■-■ deliberating...") and provider
    # wait notices, NOT answer text. Mapping them to `delta` put the whole
    # inner monologue in the RESPONSE panel and fed it to TTS, so ANA read
    # her own narration aloud before the real answer. They become `thinking`
    # events: the progress panel and core label get them, the answer and
    # speak() never see them.
    elif et in ("thinking.delta", "reasoning.delta"):
        # Keep the latency marker here: the caller clears `first` after the
        # first event of any kind, and thinking is usually the first to arrive.
        # Without this the HUD latency would never render on a turn that opens
        # with narration. Emitting it before the thinking event keeps the old
        # behaviour (this branch carried latency before too).
        if first and text:
            events.append(dict(t="latency", ms=int((time.monotonic() - started) * 1000)))
        if text:
            events.append(dict(t="thinking", text=text))
        else:
            events.append(dict(t="thinking"))
    
    elif et == "tool.start":
        if first:
            events.append(dict(t="latency", ms=int((time.monotonic() - started) * 1000)))
        # Gateway tool.start has name and args in payload
        tool_name = payload.get("name", "") or event.get("name", "")
        tool_args = payload.get("args", {}) or event.get("args", {})
        events.append(dict(
            t="tool",
            phase="use",
            name=tool_name,
            input=json.dumps(tool_args, ensure_ascii=False)[:300]
        ))
    
    elif et == "tool.complete":
        # Gateway tool.complete has result in payload
        out = payload.get("result_text", "") or payload.get("summary", "") or payload.get("result", "")
        if not isinstance(out, str):
            out = json.dumps(out, ensure_ascii=False)
        is_error = payload.get("is_error", False)
        tool_name = payload.get("name", "") or event.get("name", "")
        events.append(dict(
            t="tool",
            phase="result",
            name=tool_name,
            ok=not is_error,
            output=out[:2000]
        ))
    
    elif et == "session.usage":
        usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
        events.append(dict(
            t="usage",
            input_tokens=usage.get("input", 0),
            output_tokens=usage.get("output", 0),
            total_tokens=usage.get("total", 0)
        ))
    
    elif et == "message.complete":
        sid = event.get("session_id")
        if valid_session(sid):
            events.append(dict(t="session", session_id=sid))
        payload = event.get("payload", {})
        usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
        events.append(dict(
            t="usage",
            input_tokens=usage.get("input", 0),
            output_tokens=usage.get("output", 0),
            total_tokens=usage.get("total", 0)
        ))
        duration = event.get("duration_ms", int((time.monotonic() - started) * 1000))
        events.append(dict(t="complete", session_id=sid, ms=duration))
    
    elif et == "error":
        events.append(dict(t="error", message=event.get("message", "Unknown error")[:300]))
    
    # Ignore: sessions.changed, message.start, session.title, platforms.changed, reasoning.available
    
    return events


def _run_hermes_locked(message, session_id=None, system=None, on_session=None):
    """Internal locked run - yields events compatible with runtime.py.

    P0 §19-20: turn_id/response_id + generation guard agar token/suara
    dari generasi yang sudah di-cancel tidak bocor ke turn baru.

    session_id WAJIB eksplisit (sid live milik user peminta, disiapkan
    server via _GW_LIVE). Jatuh ke global _CURRENT_SESSION_ID hanya bila
    None (kompat jalur lama/token-only). Sesi baru/resume DILAPORKAN via
    on_session(sid) — pemanggil (server, yang tahu user_key) yang
    menyimpan ke slot user. Tanpa callback ini dua user paralel saling
    timpa _CURRENT_SESSION_ID global (transcript campur).
    """
    started = time.monotonic()

    # Get new turn ID for this generation
    turn_id = _new_turn_id()
    response_id = f"{turn_id}-r1"
    _set_response_id(response_id)

    # Initial status event — client pakai turn_id untuk drop stale events
    yield dict(
        t="status",
        model="Hermes default",
        tools=1,
        mcp=[],
        permission=os.environ.get("ANA_PERMISSION", "normal").strip().lower(),
        profile=os.environ.get("HERMES_PROFILE", os.environ.get("ANA_PROFILE", "anna")).strip() or "anna",
        runtime="hermes",
        session_id=session_id,
        turn_id=turn_id,
        response_id=response_id
    )
    
    # Use provided session_id or current session (kompat: global hanya bila
    # pemanggil tak kirim sid eksplisit — jalur token-only/lama).
    current_session_id = session_id or _CURRENT_SESSION_ID

    def _report_sid(sid):
        try:
            if sid and valid_session(sid):
                if callable(on_session):
                    on_session(str(sid))
                else:
                    global _CURRENT_SESSION_ID
                    _CURRENT_SESSION_ID = str(sid)
        except Exception:
            pass

    # Turn guard per-sesi: nomor turn + flag cancel milik sid ini, supaya
    # barge-in/cancel user A tak membatalkan turn user B. Kompat: guard
    # global (_new_turn_id/_check_cancelled) tetap jalan di bawah.
    _ses_turn_id = None
    try:
        _ses_turn_id, _ = _ses_turn_next(current_session_id or "default")
    except Exception:
        pass

    # If no valid session, create one
    if not current_session_id or not valid_session(current_session_id):
        result = _run_async(_get_gateway().create_session(title="ANA Dashboard Session"))
        current_session_id = result.get("session_id")
        if not current_session_id:
            yield dict(t="error", message="Failed to create session")
            return
        _report_sid(current_session_id)
        try:
            _ses_turn_id, _ = _ses_turn_next(current_session_id)
        except Exception:
            pass
    else:
        # Sesi detached di gateway = submit ditolak DENGAN error 4001
        # (submit_prompt_stream) ATAU diam-diam (session-scoped RPC
        # rejected, 120s stall). Verifikasi live SEBELUM submit via
        # active_list; bila tak ada → resume stored (konteks kembali),
        # bila stored pun tak ada → create baru. Tanpa ini run ke sesi
        # basi 120s lalu error, dan RUN_STATE ditahan selama itu.
        try:
            _gw = _get_gateway()
            _live_ids = set()
            try:
                _al = _run_async(_gw.active_sessions())
                _items = (_al or {}).get("sessions") or []
                for _s in _items:
                    if isinstance(_s, dict) and _s.get("id"):
                        _live_ids.add(str(_s["id"]))
            except Exception:
                _live_ids = set()
            if _live_ids and str(current_session_id) not in _live_ids:
                _resumed = None
                try:
                    _r = _run_async(_gw.resume_session(str(current_session_id)))
                    _resumed = (_r or {}).get("session_id") or None
                except Exception:
                    _resumed = None
                if _resumed and valid_session(_resumed):
                    current_session_id = _resumed
                    _report_sid(current_session_id)
                else:
                    _nr = _run_async(_gw.create_session(title="ANA Dashboard Session"))
                    _nid = (_nr or {}).get("session_id")
                    if _nid and valid_session(_nid):
                        current_session_id = _nid
                        _report_sid(current_session_id)
                try:
                    _ses_turn_id, _ = _ses_turn_next(current_session_id)
                except Exception:
                    pass
        except Exception:
            pass
    
    # Submit prompt with system prompt if provided
    prompt_text = message
    if system:
        prompt_text = f"{system}\n\n## Current user request\n{message}\n\nAnswer the request now. Return only the words ANA should say aloud; never include session IDs, runtime metadata, headings, or process narration."
    
    # Stream events from gateway
    first = True
    text_seen = False
    complete_yielded = False
    emitted_session = None
    
    try:
        # Use submit_prompt_stream for streaming events
        client = _get_gateway()

        # Use the async generator for streaming
        # queued=True = turn antre resmi di gateway ("run after"), BUKAN
        # barge-in interrupt. Tanpa ini submit kedua ke sesi sibuk MEMBUNUH
        # turn pertama (interrupt+redirect), dan tak ada yang selesai.
        async def stream_run():
            async for event in client.submit_prompt_stream(current_session_id, prompt_text, interrupted=True, queued=True):
                yield event
        
        # Collect events from the async generator
        # Stall watchdog 120s: submit ke sesi detached ditolak gateway
        # diam-diam (session-scoped RPC rejected tanpa respons) — tanpa
        # batas, thread menunggu selamanya, pegang RUN_STATE, dan semua
        # chat berikutnya 409. TimeoutError di bawah ditangkap except umum
        # menjadi event error eksplisit ke klien (bukan gantung).
        _stall_sec = 120.0
        try:
            _stall_sec = float(os.environ.get("ANA_RUN_STALL_SEC", "120") or 120.0)
        except (TypeError, ValueError):
            _stall_sec = 120.0
        for event in _run_async_stream(stream_run, cancel_sid=current_session_id, stall_sec=_stall_sec):
            # Check if this turn was cancelled — per-sesi dulu, global fallback
            # HANYA untuk jalur legacy tanpa sid. Tanpa gate ini user B mulai
            # turn (bump _CURRENT_TURN_ID global via _new_turn_id) MEMBUNUH
            # stream user A yang sedang jalan: _check_cancelled(turnA) True,
            # generator return diam-diam → klien terima 200 terpotong tanpa
            # complete/error (kasus uji paralel 15:18: u1 386 bytes buntung).
            _cancelled = False
            try:
                if _ses_turn_id is not None:
                    _cancelled = _ses_cancelled(current_session_id, _ses_turn_id)
            except Exception:
                pass
            if not _cancelled:
                try:
                    if not current_session_id or current_session_id == "default":
                        _cancelled = _check_cancelled(turn_id)
                except Exception:
                    pass
            if _cancelled:
                return
            
            mapped = _map_gateway_event(event, started, first)
            for ev in mapped:
                if ev.get("t") == "session":
                    emitted_session = ev.get("session_id")
                if ev.get("t") == "delta":
                    text_seen = True
                if ev.get("t") == "complete":
                    complete_yielded = True
                # Add turn_id to all events
                ev["turn_id"] = turn_id
                yield ev
            first = False
            
    except (BrokenPipeError, ConnectionResetError):
        # Client disconnected - silently ignore
        pass
    except Exception as e:
        if not complete_yielded:
            yield dict(t="error", message=str(e)[:300], turn_id=turn_id)
        return
    finally:
        # Persist session id dari turn ini via callback (slot user pemanggil),
        # bukan global — dua user paralel tak saling timpa.
        if emitted_session and valid_session(emitted_session):
            _report_sid(emitted_session)


def run_hermes(message, session_id=None, system=None, on_session=None):
    """Run Hermes via Gateway, yielding events compatible with runtime.py.

    Lock per-sesi-Hermes: dua user beda sesi jalan paralel; satu sesi yang
    sama tetap antre (RLock) agar turn tak tumpuk dalam satu transcript.
    on_session(sid) diteruskan ke _run_hermes_locked (slot user, bukan global).
    """
    sid_key = (str(session_id).strip() if session_id else "")
    if sid_key:
        with _ses_lock(sid_key):
            yield from _run_hermes_locked(message, session_id, system, on_session=on_session)
    else:
        with EXECUTION_LOCK:
            yield from _run_hermes_locked(message, session_id, system, on_session=on_session)


def run_mock(message, session_id=None, system=None):
    yield dict(t="error", message="Hermes Gateway not reachable. Check ANA_GATEWAY_URL and ANA_GATEWAY_TOKEN.")


def run(message, session_id=None, system=None, on_session=None):
    """Main entry point - matches runtime.py interface."""
    if runtime_kind() != "hermes":
        yield from run_mock(message, session_id, system)
        return
    try:
        yield from run_hermes(message, session_id, system, on_session=on_session)
    except Exception as e:
        yield dict(t="error", message=f"could not start Hermes via Gateway: {e}")


# Current turn/generation tracking for cancellation — PER SESI HERMES.
# Global (_CURRENT_TURN_ID/_CANCEL_EVENT) dipertahankan sebagai fallback
# kompat, tapi turn baru dicatat per-sid di _TURN_BY_SES + _CANCEL_BY_SES.
# Tanpa ini: cancel/barge-in user A membatalkan turn user B yang sedang jalan
# (sesi terisolasi tapi generation guard masih global).
_CURRENT_TURN_ID = 0
_CURRENT_RESPONSE_ID = None
_CURRENT_TTS_ID = None
_CANCEL_EVENT = threading.Event()
_TURN_BY_SES: dict = {}
_CANCEL_BY_SES: dict = {}
_TURN_GUARD = threading.Lock()


def _ses_turn_next(sid):
    key = str(sid or "").strip() or "default"
    with _TURN_GUARD:
        n = int(_TURN_BY_SES.get(key, 0)) + 1
        _TURN_BY_SES[key] = n
        ev = _CANCEL_BY_SES.get(key)
        if ev is None:
            ev = threading.Event()
            _CANCEL_BY_SES[key] = ev
        ev.clear()
        return n, ev


def _ses_cancel(sid):
    key = str(sid or "").strip() or "default"
    with _TURN_GUARD:
        n = int(_TURN_BY_SES.get(key, 0)) + 1
        _TURN_BY_SES[key] = n
        ev = _CANCEL_BY_SES.get(key)
        if ev is None:
            ev = threading.Event()
            _CANCEL_BY_SES[key] = ev
        ev.set()
        return n


def _ses_cancelled(sid, turn_id):
    key = str(sid or "").strip() or "default"
    with _TURN_GUARD:
        cur = int(_TURN_BY_SES.get(key, 0))
        ev = _CANCEL_BY_SES.get(key)
        flag = bool(ev and ev.is_set())
    return turn_id != cur or flag


def cancel_active(session_id=None):
    """Cancel the currently running request (best effort) — P0 barge-in.

    Sesuai improve_STT_TTS_VAD.md §19-20: setiap turn punya turn_id/response_id,
    generasi lama harus dibuang, LLM+TTS lama di-cancel, queue audio di-flush.
    Implementasi: bump _CURRENT_TURN_ID + set _CANCEL_EVENT agar token basi
    di-drop via _check_cancelled, lalu coba interupsi gateway secara nyata
    (session.interrupt) + deny approval bila ada tool yang nunggu approval.

    session_id (opsional): target interupsi eksplisit. Bila diisi, gateway
    diinterupsi pada sesi itu BUKAN _CURRENT_SESSION_ID — tanpa ini, user A
    menekan cancel bisa menginterupsi turn user B yang sedang jalan
    (sesi ANNA per-user, tapi target cancel masih global).
    """
    global _CURRENT_TURN_ID, _CURRENT_RESPONSE_ID, _CURRENT_TTS_ID
    _target_sid = (str(session_id).strip() if session_id else "") or _CURRENT_SESSION_ID
    # Guard lokal: global (kompat) + per-sesi (isolasi). Cancel tanpa target
    # = global seperti dulu; cancel dengan target = hanya sesi itu.
    _CANCEL_EVENT.set()
    _CURRENT_TURN_ID += 1
    if _target_sid:
        try:
            _ses_cancel(_target_sid)
        except Exception:
            pass
    _CURRENT_RESPONSE_ID = None
    _CURRENT_TTS_ID = None
    # Real interrupt: session.interrupt di gateway (bukan cuma approval deny).
    # Dua jalur dipanggil bersamaan — mana yang didukung gateway akan membatalkan
    # generasi yang sedang berpikir/tool-execution; yang tidak didukung diabaikan.
    # Target = sesi peminta bila diberikan, supaya cancel user A tak memutus turn user B.
    try:
        if _GATEWAY_CLIENT and _GATEWAY_LOOP and _target_sid:
            # session.interrupt — hentikan prompt yang sedang jalan
            try:
                asyncio.run_coroutine_threadsafe(
                    _GATEWAY_CLIENT.interrupt_session(_target_sid),
                    _GATEWAY_LOOP
                )
            except Exception:
                pass
            # approval.respond deny — bila Hermes sedang nunggu approval tool
            try:
                asyncio.run_coroutine_threadsafe(
                    _GATEWAY_CLIENT.respond_approval(_target_sid, "deny", all=True),
                    _GATEWAY_LOOP
                )
            except Exception:
                pass
    except Exception:
        pass
    return True


def _new_turn_id():
    global _CURRENT_TURN_ID
    _CURRENT_TURN_ID += 1
    _CANCEL_EVENT.clear()
    return _CURRENT_TURN_ID


def _get_current_turn_id():
    return _CURRENT_TURN_ID


def _set_response_id(rid):
    global _CURRENT_RESPONSE_ID
    _CURRENT_RESPONSE_ID = rid


def _set_tts_id(tid):
    global _CURRENT_TTS_ID
    _CURRENT_TTS_ID = tid


def _check_cancelled(turn_id):
    """Return True if this turn has been superseded."""
    return turn_id != _CURRENT_TURN_ID or _CANCEL_EVENT.is_set()


def shutdown():
    """Clean shutdown of gateway connection."""
    global _GATEWAY_CLIENT, _GATEWAY_LOOP, _GATEWAY_THREAD
    if _GATEWAY_CLIENT and _GATEWAY_LOOP:
        asyncio.run_coroutine_threadsafe(_GATEWAY_CLIENT.close(), _GATEWAY_LOOP)
        _GATEWAY_LOOP.call_soon_threadsafe(_GATEWAY_LOOP.stop)
    if _GATEWAY_THREAD:
        _GATEWAY_THREAD.join(timeout=2)
    _GATEWAY_CLIENT = None
    _GATEWAY_LOOP = None
    _GATEWAY_THREAD = None
    _GATEWAY_CONNECTED.clear()
    _SESSION_CREATED_EVENT.clear()


# Backwards compatibility exports
MODEL = os.environ.get("ANA_MODEL", "").strip()
PROFILE = os.environ.get("HERMES_PROFILE", os.environ.get("ANA_PROFILE", "default")).strip() or "default"
SOURCE = os.environ.get("HERMES_SOURCE", "ana-dashboard").strip() or "ana-dashboard"
WORKDIR = os.path.expanduser(os.environ.get("ANA_WORKDIR", os.getcwd()))
PERMISSION = os.environ.get("ANA_PERMISSION", os.environ.get("HERMES_PERMISSION", "normal")).strip().lower()
RUNTIME = os.environ.get("ANA_RUNTIME", "auto").strip().lower()
IDLE_TIMEOUT = int(os.environ.get("ANA_TIMEOUT", "120"))
RAW_LOG = os.environ.get("ANA_RAW_LOG", "").strip()
TOOLSETS = os.environ.get("HERMES_TOOLSETS", "").strip()