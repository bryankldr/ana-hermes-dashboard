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

# One Hermes subprocess at a time. Hermes session state and profile resources are
# shared, so foreground runs and /background missions must not overlap. The active
# process handle lets the browser Escape key stop the backend work, not just the
# frontend fetch.
EXECUTION_LOCK = threading.RLock()
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


def _get_gateway() -> HermesGatewayClient:
    """Get or create the singleton gateway client."""
    global _GATEWAY_CLIENT, _GATEWAY_THREAD, _GATEWAY_LOOP, _GATEWAY_CONNECTED, _GATEWAY_CONNECT_ERROR
    
    with _GATEWAY_LOCK:
        if _GATEWAY_CLIENT is not None and _GATEWAY_CLIENT.connected:
            return _GATEWAY_CLIENT
        
        # Create new gateway
        gateway_url = os.environ.get("ANA_GATEWAY_URL", "ws://localhost:37521/api/ws")
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


def _run_async_stream(coro_func, *args, **kwargs):
    """Run an async generator in the gateway's event loop, yielding results."""
    if _GATEWAY_LOOP is None:
        raise RuntimeError("Gateway event loop not running")
    
    queue: List[Dict] = []
    lock = threading.Lock()
    done = threading.Event()
    error = [None]
    
    async def _runner():
        try:
            async for event in coro_func(*args, **kwargs):
                with lock:
                    queue.append(event)
        except Exception as e:
            error[0] = e
        finally:
            done.set()
    
    future = asyncio.run_coroutine_threadsafe(_runner(), _GATEWAY_LOOP)
    
    while not done.is_set() or queue:
        event = None
        with lock:
            if queue:
                event = queue.pop(0)
        if event is not None:
            yield event
        else:
            if done.is_set():
                break
            time.sleep(0.01)
    
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


def _run_hermes_locked(message, session_id=None, system=None):
    """Internal locked run - yields events compatible with runtime.py."""
    started = time.monotonic()
    
    # Initial status event
    yield dict(
        t="status",
        model="Hermes default",
        tools=1,
        mcp=[],
        permission=os.environ.get("ANA_PERMISSION", "normal").strip().lower(),
        profile=os.environ.get("HERMES_PROFILE", os.environ.get("ANA_PROFILE", "anna")).strip() or "anna",
        runtime="hermes",
        session_id=session_id
    )
    
    global _CURRENT_SESSION_ID
    
    # Use provided session_id or current session
    current_session_id = session_id or _CURRENT_SESSION_ID
    
    # If no valid session, create one
    if not current_session_id or not valid_session(current_session_id):
        result = _run_async(_get_gateway().create_session(title="ANA Dashboard Session"))
        current_session_id = result.get("session_id")
        if not current_session_id:
            yield dict(t="error", message="Failed to create session")
            return
        _CURRENT_SESSION_ID = current_session_id
    
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
        async def stream_run():
            async for event in client.submit_prompt_stream(current_session_id, prompt_text):
                yield event
        
        # Collect events from the async generator
        for event in _run_async_stream(stream_run):
            mapped = _map_gateway_event(event, started, first)
            for ev in mapped:
                if ev.get("t") == "session":
                    emitted_session = ev.get("session_id")
                if ev.get("t") == "delta":
                    text_seen = True
                if ev.get("t") == "complete":
                    complete_yielded = True
                yield ev
            first = False
            
    except Exception as e:
        if not complete_yielded:
            yield dict(t="error", message=str(e)[:300])
        return
        
        # Handle final result if we didn't get complete event
        if not complete_yielded:
            sid = result.get("session_id")
            if valid_session(sid):
                yield dict(t="session", session_id=sid)
            toks = result.get("tokens", {})
            yield dict(
                t="usage",
                input_tokens=toks.get("input", 0),
                output_tokens=toks.get("output", 0),
                total_tokens=toks.get("total", 0)
            )
            yield dict(t="complete", session_id=sid, ms=int((time.monotonic() - started) * 1000))
        
        # Update session id
        if emitted_session:
            _CURRENT_SESSION_ID = emitted_session
        elif result.get("session_id"):
            _CURRENT_SESSION_ID = result.get("session_id")
            
    except (BrokenPipeError, ConnectionResetError):
        # Client disconnected - silently ignore
        pass
    except Exception as e:
        # This shouldn't be reached since we handle errors in the loop
        yield dict(t="error", message=str(e)[:300])


def run_hermes(message, session_id=None, system=None):
    """Run Hermes via Gateway, yielding events compatible with runtime.py."""
    with EXECUTION_LOCK:
        yield from _run_hermes_locked(message, session_id, system)


def run_mock(message, session_id=None, system=None):
    yield dict(t="error", message="Hermes Gateway not reachable. Check ANA_GATEWAY_URL and ANA_GATEWAY_TOKEN.")


def run(message, session_id=None, system=None):
    """Main entry point - matches runtime.py interface."""
    if runtime_kind() != "hermes":
        yield from run_mock(message, session_id, system)
        return
    try:
        yield from run_hermes(message, session_id, system)
    except Exception as e:
        yield dict(t="error", message=f"could not start Hermes via Gateway: {e}")


def cancel_active():
    """Cancel the currently running request (best effort)."""
    # Gateway doesn't have a direct cancel yet; we could implement via approval.respond
    # For now, this is a no-op
    return False


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