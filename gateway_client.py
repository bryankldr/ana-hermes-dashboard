#!/usr/bin/env python3
"""
Hermes Gateway WebSocket Client for ana-hermes-dashboard.

Replaces runtime.py's spawn-hermes-chat architecture with persistent
WebSocket connection to Hermes Gateway (tui_gateway JSON-RPC over UNIX socket).

Protocol: JSON-RPC 2.0 over WebSocket at ws://localhost/api/ws (via UNIX socket proxy)
Contract: tui_gateway/contracts/registry.py (all methods/events declared)
"""

import asyncio
import json
import os
import uuid
import logging
from typing import Any, Callable, Awaitable, Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum

import websockets
from websockets.client import WebSocketClientProtocol as WSClientProtocol

logger = logging.getLogger(__name__)


class GatewayEventType(Enum):
    """Event types from gateway (tui_gateway/contracts/events.py)"""
    GATEWAY_READY = "gateway.ready"
    MESSAGE_START = "message.start"
    MESSAGE_DELTA = "message.delta"
    MESSAGE_INTERIM = "message.interim"
    MESSAGE_COMPLETE = "message.complete"
    REASONING_DELTA = "reasoning.delta"
    REASONING_AVAILABLE = "reasoning.available"
    THINKING_DELTA = "thinking.delta"
    TOOL_START = "tool.start"
    TOOL_COMPLETE = "tool.complete"
    TOOL_GENERATING = "tool.generating"
    TOOL_OUTPUT_RISK = "tool.output_risk"
    TODO_UPDATED = "todo.updated"
    STATUS_UPDATE = "status.update"
    SESSION_USAGE = "session.usage"
    SESSION_TITLE = "session.title"
    SESSION_INFO = "session.info"
    SESSION_RESUME_PROGRESS = "session.resume_progress"
    SESSION_RECLAIMED = "session.reclaimed"
    APPROVAL_CANCELLED = "approval.cancelled"
    SESSION_CONTROL_UPDATE = "session.control.update"
    BACKGROUND_COMPLETE = "background.complete"
    BTW_COMPLETE = "btw.complete"
    PREVIEW_RESTART_COMPLETE = "preview.restart.complete"
    PREVIEW_RESTART_PROGRESS = "preview.restart.progress"
    SUBAGENT_SPAWN_REQUESTED = "subagent.spawn_requested"
    SUBAGENT_START = "subagent.start"
    SUBAGENT_PROGRESS = "subagent.progress"
    SUBAGENT_THINKING = "subagent.thinking"
    SUBAGENT_TOOL = "subagent.tool"
    SUBAGENT_COMPLETE = "subagent.complete"
    ERROR = "error"
    NOTICE = "notice"
    REACTION = "reaction"
    REVIEW_SUMMARY = "review.summary"
    NOTIFICATION_SHOW = "notification.show"
    NOTIFICATION_CLEAR = "notification.clear"
    TIP_SHOW = "tip.show"
    PREVIEW_OPEN = "preview.open"
    PREVIEW_CLOSE = "preview.close"
    LAYOUT_APPLY = "layout.apply"
    PANE_REVEAL = "pane.reveal"
    MESSAGE_REACTION = "message.reaction"
    AGENT_TERMINAL_OUTPUT = "agent.terminal.output"
    TERMINAL_CLOSE = "terminal.close"
    BROWSER_PROGRESS = "browser.progress"
    BROWSER_CONTROLLER_COMMAND = "browser.controller.command"
    BROWSER_CONTROLLER_CANCEL = "browser.controller.cancel"
    VOICE_INTERRUPTED = "voice.interrupted"
    VOICE_STATUS = "voice.status"
    VOICE_TRANSCRIPT = "voice.transcript"
    WAKE_DETECTED = "wake.detected"
    PET_CHANGED = "pet.changed"
    PET_GENERATE_PROGRESS = "pet.generate.progress"
    PET_HATCH_PROGRESS = "pet.hatch.progress"
    CRON_CHANGED = "cron.changed"
    SESSIONS_CHANGED = "sessions.changed"
    PLATFORMS_CHANGED = "platforms.changed"
    PROJECTS_CHANGED = "projects.changed"
    PAIRING_CHANGED = "pairing.changed"
    BOT_RELAY_OUTBOX_PENDING = "bot_relay.outbox.pending"
    SKIN_CHANGED = "skin.changed"
    SETUP_READY = "setup.ready"


@dataclass
class PendingRequest:
    """Track pending JSON-RPC requests"""
    future: asyncio.Future
    method: str
    params: dict


@dataclass
class GatewaySession:
    """Live session state from gateway"""
    session_id: str
    stored_session_id: str | None = None
    title: str = ""
    message_count: int = 0
    status: str = "idle"
    model: str = ""
    cols: int = 120
    messages: list = field(default_factory=list)
    info: dict = field(default_factory=dict)
    inflight: dict | None = None
    queued: dict | None = None
    pending_approval: dict | None = None


class HermesGatewayClient:
    """
    WebSocket client for Hermes Gateway (TUI Gateway JSON-RPC).
    
    Replaces runtime.py's subprocess-based hermes chat with persistent
    WebSocket connection. Handles:
    - Connection lifecycle (connect, reconnect, heartbeat)
    - JSON-RPC request/response with streaming events
    - Session management (create, resume, close, list)
    - Prompt submission with streaming deltas
    - Tool call events
    - Capability discovery
    """
    
    def __init__(
        self,
        gateway_url: str | None = None,
        unix_socket_path: str | None = None,
        profile: str = "anna",
        auth_token: str | None = None,
        on_event: Optional[Callable[[str, dict], Any]] = None,
        on_session_change: Optional[Callable[[GatewaySession], Any]] = None,
    ):
        _resolved = (gateway_url or os.environ.get("ANA_GATEWAY_URL", "").strip())
        if not _resolved:
            raise RuntimeError(
                "gateway_url required: set ANA_GATEWAY_URL or pass gateway_url. "
                "Run via ./start.sh or export ANA_GATEWAY_URL=ws://127.0.0.1:<SPORT>/api/ws"
            )
        self.gateway_url: str = _resolved
        if unix_socket_path is None:
            _home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
            unix_socket_path = os.path.join(_home, "gateway.sock")
        self.unix_socket_path = unix_socket_path
        self.profile = profile
        self.auth_token = auth_token
        self.on_event = on_event
        self.on_session_change = on_session_change
        
        self.ws: Optional[WSClientProtocol] = None
        self.connected = False
        self._request_id = 0
        self._pending: Dict[str, PendingRequest] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._session: Optional[GatewaySession] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._closing = False
        
        # Token buffer for streaming (gateway flushes on 33ms timer)
        self._token_buffer = ""
        self._last_flush = 0.0
        
    async def connect(self) -> bool:
        """Connect to Hermes Gateway via WebSocket."""
        if self.connected:
            return True
            
        try:
            # For token auth, append token to URL
            url = self.gateway_url
            if self.auth_token:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}token={self.auth_token}"
            
            self.ws = await websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )
            self.connected = True
            self._closing = False
            
            # Start receive loop
            self._recv_task = asyncio.create_task(self._recv_loop())
            
            # Start heartbeat
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            logger.info("Connected to Hermes Gateway")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to gateway: {e}")
            self.connected = False
            return False
    
    async def connect_unix(self) -> bool:
        """Connect via UNIX socket using a custom connector."""
        # websockets doesn't natively support UNIX sockets.
        # We'll use aiohttp with unix connector or implement custom transport.
        # For now, fallback to TCP proxy (socat or gateway's built-in WS).
        return await self.connect()
    
    async def _recv_loop(self):
        """Main receive loop - handles JSON-RPC responses and server events."""
        try:
            if self.ws:
                async for message in self.ws:
                    await self._handle_message(message)
        except websockets.ConnectionClosed:
            logger.warning("Gateway connection closed")
            await self._handle_disconnect()
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
            await self._handle_disconnect()
    
    async def _handle_message(self, raw: str):
        """Parse and dispatch incoming message."""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from gateway: {raw[:200]}")
            return
        
        # JSON-RPC Response
        if "id" in msg and "method" not in msg:
            await self._handle_response(msg)
        # JSON-RPC Request (server->client, e.g., approval.request)
        elif "method" in msg and "id" in msg:
            await self._handle_server_request(msg)
        # JSON-RPC Notification (server->client event)
        elif "method" in msg and "id" not in msg:
            await self._handle_event(msg)
        else:
            logger.warning(f"Unknown message format: {msg}")
    
    async def _handle_response(self, msg: dict):
        """Handle JSON-RPC response to our request."""
        req_id = str(msg.get("id"))
        pending = self._pending.pop(req_id, None)
        
        if pending:
            if "error" in msg:
                error = msg["error"]
                pending.future.set_exception(
                    GatewayError(error.get("code", -1), error.get("message", "Unknown error"), error.get("data"))
                )
            else:
                pending.future.set_result(msg.get("result"))
        else:
            logger.warning(f"Response for unknown request id: {req_id}")
    
    async def _handle_server_request(self, msg: dict):
        """Handle server-to-client request (approval, clarify, sudo, secret)."""
        method = msg.get("method")
        params = msg.get("params", {})
        req_id = str(msg.get("id"))
        
        logger.info(f"Server request: {method}")
        
        # Emit to event handlers
        await self._emit_event(f"server_request.{method}", {
            "request_id": req_id,
            "method": method,
            "params": params,
        })
        
        # Default: deny/timeout - real implementation would wait for UI
        # For now, auto-deny approvals
        if method == "approval.request":
            await self._send_response(req_id, {"choice": "deny"})
        elif method == "clarify.request":
            await self._send_response(req_id, {"answers": {}})
        elif method == "sudo.request":
            await self._send_response(req_id, {"approved": False})
        elif method == "secret.request":
            await self._send_response(req_id, {"value": ""})
    
    async def _handle_event(self, msg: dict):
        """Handle server event notification."""
        method: str = msg.get("method", "")
        params = msg.get("params", {})
        
        # Update session state for key events
        if method == "session.info":
            await self._update_session(params)
        elif method == "session.resume_progress":
            await self._update_session(params)
        elif method == "gateway.ready":
            logger.info(f"Gateway ready: {params}")
        
        # Emit to handlers
        await self._emit_event(method, params)
        
        # Call user callback
        if self.on_event:
            try:
                if asyncio.iscoroutinefunction(self.on_event):
                    await self.on_event(method, params)
                else:
                    self.on_event(method, params)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
    
    async def _emit_event(self, event: str, payload: dict):
        """Emit to registered handlers."""
        handlers = self._event_handlers.get(event, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(payload)
                else:
                    handler(payload)
            except Exception as e:
                logger.error(f"Handler error for {event}: {e}")
    
    def on(self, event: str, handler: Callable):
        """Register event handler."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
    
    async def _update_session(self, params: dict):
        """Update local session state from gateway event."""
        if not self._session:
            self._session = GatewaySession(session_id="")
        
        # Merge relevant fields
        for key in ["session_id", "stored_session_id", "title", "message_count", 
                    "status", "model", "cols", "messages", "info", "inflight", 
                    "queued", "pending_approval"]:
            if key in params:
                setattr(self._session, key, params[key])
        
        if self.on_session_change and self._session:
            try:
                await self.on_session_change(self._session)
            except Exception as e:
                logger.error(f"Session change handler error: {e}")
    
    async def _handle_disconnect(self):
        """Handle unexpected disconnect."""
        self.connected = False
        if self._recv_task:
            self._recv_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        
        # Reject pending requests
        for pending in self._pending.values():
            pending.future.set_exception(GatewayError(-1, "Connection lost"))
        self._pending.clear()
        
        if not self._closing:
            await self._schedule_reconnect()
    
    async def _schedule_reconnect(self):
        """Schedule reconnection with exponential backoff."""
        if self._reconnect_task:
            self._reconnect_task.cancel()
        
        async def _reconnect():
            delay = 1
            max_delay = 30
            while not self._closing:
                await asyncio.sleep(delay)
                logger.info(f"Reconnecting to gateway (delay={delay}s)...")
                if await self.connect():
                    logger.info("Reconnected successfully")
                    # Re-attach to session if we had one
                    if self._session and self._session.session_id:
                        await self.resume_session(self._session.session_id)
                    return
                delay = min(delay * 2, max_delay)
        
        self._reconnect_task = asyncio.create_task(_reconnect())
    
    async def _heartbeat_loop(self):
        """Send periodic pings (handled by websockets ping_interval)."""
        while self.connected and not self._closing:
            await asyncio.sleep(30)
            if self.ws and self.connected:
                try:
                    await self.ws.ping()
                except Exception:
                    break
    
    async def _send_request(self, method: str, params: dict, timeout: float = 30.0) -> Any:
        """Send JSON-RPC request and wait for response."""
        if not self.connected or not self.ws:
            raise GatewayError(-1, "Not connected to gateway")
        
        self._request_id += 1
        req_id = str(self._request_id)
        
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }
        
        future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = PendingRequest(future, method, params)
        
        try:
            await self.ws.send(json.dumps(request))
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise GatewayError(-1, f"Request timeout: {method}")
        except Exception as e:
            self._pending.pop(req_id, None)
            raise GatewayError(-1, f"Send failed: {e}")
    
    async def _send_response(self, req_id: str, result: dict):
        """Send response to server request."""
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }
        if self.ws:
            await self.ws.send(json.dumps(response))
    
    # ── Session Methods ─────────────────────────────────────────────────
    
    async def create_session(
        self,
        title: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        cwd: str | None = None,
        cols: int = 120,
        messages: list | None = None,
        parent_session_id: str | None = None,
    ) -> dict:
        """Create a new session (session.create)."""
        params = {
            "profile": self.profile,
            "cols": cols,
            "source": "ana-dashboard",
        }
        if title:
            params["title"] = title
        if model:
            params["model"] = model
        if provider:
            params["provider"] = provider
        if cwd:
            params["cwd"] = cwd
            params["cwd_explicit"] = True
        if messages:
            params["messages"] = messages
        if parent_session_id:
            params["parent_session_id"] = parent_session_id
        
        result = await self._send_request("session.create", params)
        if result and "session_id" in result:
            self._session = GatewaySession(
                session_id=result["session_id"],
                stored_session_id=result.get("stored_session_id"),
                title=result.get("title", title or ""),
                message_count=result.get("message_count", 0),
            )
        return result
    
    async def resume_session(
        self,
        session_id: str,
        cols: int = 120,
        lazy: bool = False,
        defer_history: bool = False,
        omit_messages: bool = False,
    ) -> dict:
        """Resume a stored session (session.resume)."""
        params = {
            "session_id": session_id,
            "profile": self.profile,
            "cols": cols,
            "lazy": lazy,
            "defer_history": defer_history,
            "omit_messages": omit_messages,
        }
        
        result = await self._send_request("session.resume", params)
        if result and "session_id" in result:
            self._session = GatewaySession(
                session_id=result["session_id"],
                stored_session_id=result.get("stored_session_id"),
                title=result.get("title", ""),
                message_count=result.get("message_count", 0),
                messages=result.get("messages", []),
                info=result.get("info", {}),
                inflight=result.get("inflight"),
                queued=result.get("queued"),
                pending_approval=result.get("pending_approval"),
            )
        return result
    
    async def activate_session(self, session_id: str, cols: int = 120, omit_messages: bool = False) -> dict:
        """Activate a live session (session.activate)."""
        params = {
            "session_id": session_id,
            "profile": self.profile,
            "cols": cols,
            "omit_messages": omit_messages,
        }
        return await self._send_request("session.activate", params)
    
    async def close_session(self, session_id: str) -> dict:
        """Close a live session (session.close)."""
        params = {"session_id": session_id, "profile": self.profile}
        result = await self._send_request("session.close", params)
        if result and result.get("closed"):
            self._session = None
        return result
    
    async def list_sessions(self, limit: int = 50, include_hidden: bool = False) -> dict:
        """List stored sessions (session.list)."""
        params = {
            "profile": self.profile,
            "limit": limit,
            "include_hidden": include_hidden,
        }
        return await self._send_request("session.list", params)
    
    async def active_sessions(self) -> dict:
        """List live sessions (session.active_list)."""
        params = {"profile": self.profile}
        return await self._send_request("session.active_list", params)
    
    async def get_session_status(self, session_id: str) -> dict:
        """Get session status text (session.status)."""
        params = {"session_id": session_id, "profile": self.profile}
        return await self._send_request("session.status", params)
    
    async def get_session_history(self, session_id: str) -> dict:
        """Get session transcript (session.history)."""
        params = {"session_id": session_id, "profile": self.profile}
        return await self._send_request("session.history", params)
    
    async def interrupt_session(self, session_id: str) -> dict:
        """Interrupt running turn (session.interrupt)."""
        params = {"session_id": session_id, "profile": self.profile}
        return await self._send_request("session.interrupt", params)
    
    async def set_session_title(self, session_id: str, title: str) -> dict:
        """Set session title (session.title)."""
        params = {"session_id": session_id, "profile": self.profile, "title": title}
        return await self._send_request("session.title", params)

    # ── Prompt Methods ──────────────────────────────────────────────────

    async def submit_prompt(
        self,
        session_id: str,
        text: str,
        display_kind: str | None = None,
        interrupted: bool = False,
        queued: bool = False,
    ) -> dict:
        """Submit user prompt to session (prompt.submit)."""
        params = {
            "session_id": session_id,
            "profile": self.profile,
            "text": text,
            "interrupted": interrupted,
            "queued": queued,
        }
        if display_kind:
            params["display_kind"] = display_kind

        return await self._send_request("prompt.submit", params)

    async def submit_prompt_stream(
        self,
        session_id: str,
        text: str,
        display_kind: str | None = None,
        interrupted: bool = False,
        queued: bool = False,
    ):
        """Submit user prompt and stream events via async generator.

        Yields gateway events as they arrive (message.delta, tool_use, tool_result, etc.)
        Scoped via _event_handlers to avoid clobbering self.on_event (race if reused).
        Filters by session_id and ignores non-stream noise (sessions.changed, etc.).

        queued: teruskan flag antre gateway (prompt.submit {queued:true}).
        Gateway mendaftarkan turn sebagai antrean ("run after") — tanpa ini
        submit kedua ke sesi sibuk jadi barge-in interrupt yang MEMBUNUH turn
        pertama (kasus uji paralel: u1 diterima lalu hilang tanpa jejak,
        u2 menunggu 120s). Return RPC {"status"} diekspos via event
        t="submit" agar pemanggil tahu: streaming (jalan) vs queued (antre).
        """
        queue: asyncio.Queue = asyncio.Queue()
        # Whitelist: only stream-relevant methods enter the queue
        _STREAM_METHODS = {
            "message.delta", "message.complete", "delta", "text",
            "thinking.delta", "reasoning.delta",
            "tool.start", "tool.complete",
            "session.info", "session.usage", "session.resume_progress",
            "error",
        }
        _IGNORE_METHODS = {"sessions.changed", "platforms.changed", "message.start", "session.title", "reasoning.available", "gateway.ready"}

        def _should_queue(method: str, params: dict) -> bool:
            if method in _IGNORE_METHODS:
                return False
            if method not in _STREAM_METHODS:
                # Unknown but not ignored — allow (future-proof), but log
                pass
            # Filter by session_id when present — prevents cross-session bleed
            sid = params.get("session_id") or (params.get("payload") or {}).get("session_id") if isinstance(params.get("payload"), dict) else None
            if sid and sid != session_id:
                return False
            return True

        # Scoped collector added to _event_handlers (not replacing self.on_event)
        def _make_collector(m: str):
            def _h(payload: dict):
                if not _should_queue(m, payload):
                    return
                try:
                    queue.put_nowait({"type": m, **payload})
                except Exception as e:
                    logger.error(f"event_collector queue error: {e}")
            return _h

        # Register per-method collectors + a fallback via on_event wrapping
        collectors: list[tuple[str, callable]] = []
        for meth in _STREAM_METHODS:
            h = _make_collector(meth)
            self.on(meth, h)
            collectors.append((meth, h))

        # Also wrap on_event so any method we missed still flows through queue (filtered)
        orig_on_event = self.on_event
        def _wrapped_on_event(method: str, params: dict):
            # First: queue (filtered)
            if _should_queue(method, params):
                try:
                    queue.put_nowait({"type": method, **params})
                except Exception:
                    pass
            # Then: chain to original handler if any
            if orig_on_event is not None:
                try:
                    res = orig_on_event(method, params)  # type: ignore[call-arg,operator]
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)  # type: ignore[arg-type]
                except Exception as e:
                    logger.error(f"orig on_event error: {e}")
        self.on_event = _wrapped_on_event  # type: ignore[assignment]

        def _remove_collectors():
            for meth, h in collectors:
                lst = self._event_handlers.get(meth, [])
                if h in lst:
                    lst.remove(h)
            self.on_event = orig_on_event  # type: ignore[assignment]

        req_id: str | None = None
        try:
            # Start the prompt submission
            params = {
                "session_id": session_id,
                "profile": self.profile,
                "text": text,
                "interrupted": interrupted,
                "queued": queued,
            }
            if display_kind:
                params["display_kind"] = display_kind

            # Fire and forget - events will come via callback
            self._request_id += 1
            req_id = str(self._request_id)
            request = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "prompt.submit",
                "params": params,
            }

            future = asyncio.get_event_loop().create_future()
            self._pending[req_id] = PendingRequest(future, "prompt.submit", params)

            await self.ws.send(json.dumps(request))

            # Status submit diekspos sebagai event pertama: pemanggil tahu
            # turn-nya jalan ("streaming") atau antre ("queued") — tanpa ini
            # turn antre terlihat mati 120s lalu timeout.
            try:
                _submit_res = await asyncio.wait_for(future, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("prompt.submit ack timeout — proceeding anyway")
                _submit_res = None
            if isinstance(_submit_res, dict):
                yield {"type": "submit", "session_id": session_id,
                       "status": _submit_res.get("status", "streaming"),
                       "result": _submit_res}

            # Yield events until we get message.complete or error — 120s per-event (LLM/tool may take long)
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=120.0)
                except asyncio.TimeoutError:
                    logger.warning("submit_prompt_stream queue timeout 120s — no event for session %s", session_id)
                    raise GatewayError(-1, "stream timeout: no gateway event for 120s")
                yield event

                # Check for completion
                if event.get("type") == "message.complete":
                    break
                elif event.get("type") == "error":
                    break
        finally:
            # Restore original handler + remove scoped collectors
            _remove_collectors()
            if req_id is not None:
                self._pending.pop(req_id, None)

    async def submit_prompt_background(self, session_id: str, text: str) -> dict:
        """Run background side agent (prompt.background)."""
        params = {"session_id": session_id, "profile": self.profile, "text": text}
        return await self._send_request("prompt.background", params)
    
    async def submit_btw(self, session_id: str, text: str) -> dict:
        """Side question over snapshot (prompt.btw)."""
        params = {"session_id": session_id, "profile": self.profile, "text": text}
        return await self._send_request("prompt.btw", params)
    
    # ── Slash Commands ──────────────────────────────────────────────────
    
    async def dispatch_command(self, session_id: str, command: str, arg: str | None = None) -> dict:
        """Dispatch slash command (command.dispatch)."""
        params = {
            "session_id": session_id,
            "profile": self.profile,
            "name": command,
        }
        if arg:
            params["arg"] = arg
        return await self._send_request("command.dispatch", params)
    
    async def exec_cli(self, argv: list[str], timeout: int = 30) -> dict:
        """Execute hermes CLI command (cli.exec)."""
        params = {"argv": argv, "timeout": timeout, "profile": self.profile}
        return await self._send_request("cli.exec", params)
    
    # ── Attachments ─────────────────────────────────────────────────────
    
    async def attach_image(self, session_id: str, path: str) -> dict:
        """Attach image file (image.attach)."""
        params = {"session_id": session_id, "profile": self.profile, "path": path}
        return await self._send_request("image.attach", params)
    
    async def attach_image_bytes(self, session_id: str, content_base64: str, filename: str = "") -> dict:
        """Attach image from base64 (image.attach_bytes)."""
        params = {
            "session_id": session_id,
            "profile": self.profile,
            "content_base64": content_base64,
            "filename": filename,
        }
        return await self._send_request("image.attach_bytes", params)
    
    async def attach_pdf(self, session_id: str, path: str | None = None, content_base64: str | None = None,
                         first_page: int | None = None, last_page: int | None = None) -> dict:
        """Attach PDF (pdf.attach)."""
        params = {"session_id": session_id, "profile": self.profile}
        if path:
            params["path"] = path
        if content_base64:
            params["content_base64"] = content_base64
        if first_page:
            params["first_page"] = first_page
        if last_page:
            params["last_page"] = last_page
        return await self._send_request("pdf.attach", params)
    
    async def attach_file(self, session_id: str, path: str | None = None, data_url: str | None = None, name: str = "") -> dict:
        """Attach non-image file (file.attach)."""
        params = {"session_id": session_id, "profile": self.profile, "name": name}
        if path:
            params["path"] = path
        if data_url:
            params["data_url"] = data_url
        return await self._send_request("file.attach", params)
    
    # ── Approvals ───────────────────────────────────────────────────────
    
    async def get_pending_approvals(self, session_id: str) -> dict:
        """Get pending approvals (approval.pending)."""
        params = {"session_id": session_id, "profile": self.profile}
        return await self._send_request("approval.pending", params)
    
    async def respond_approval(self, session_id: str, choice: str = "deny", all: bool = False, request_id: str | None = None) -> dict:
        """Respond to approval (approval.respond)."""
        params = {"session_id": session_id, "profile": self.profile, "choice": choice}
        if all:
            params["all"] = "true"
        if request_id:
            params["request_id"] = request_id
        return await self._send_request("approval.respond", params)
    
    # ── Tools / Commands ────────────────────────────────────────────────
    
    async def get_commands_catalog(self, session_id: str | None = None) -> dict:
        """Get slash command catalog (commands.catalog)."""
        params = {"profile": self.profile}
        if session_id:
            params["session_id"] = session_id
        return await self._send_request("commands.catalog", params)
    
    async def shell_exec(self, command: str) -> dict:
        """Execute shell command (shell.exec)."""
        params = {"command": command, "profile": self.profile}
        return await self._send_request("shell.exec", params)
    
    async def process_list(self, session_id: str) -> dict:
        """List background processes (process.list)."""
        params = {"session_id": session_id, "profile": self.profile}
        return await self._send_request("process.list", params)
    
    async def process_kill(self, session_id: str, process_id: str) -> dict:
        """Kill background process (process.kill)."""
        params = {"session_id": session_id, "process_id": process_id, "profile": self.profile}
        return await self._send_request("process.kill", params)
    
    # ── Voice ───────────────────────────────────────────────────────────
    
    async def voice_toggle(self, action: str = "status") -> dict:
        """Toggle voice mode (voice.toggle)."""
        params = {"action": action, "profile": self.profile}
        return await self._send_request("voice.toggle", params)
    
    async def voice_tts(self, text: str) -> dict:
        """Speak text via TTS (voice.tts)."""
        params = {"text": text, "profile": self.profile}
        return await self._send_request("voice.tts", params)
    
    # ── Lifecycle ───────────────────────────────────────────────────────
    
    async def close(self):
        """Close connection gracefully."""
        self._closing = True
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._recv_task:
            self._recv_task.cancel()
        
        if self.ws and self.connected:
            try:
                await self.ws.close()
            except Exception:
                pass
        
        self.connected = False
        logger.info("Gateway client closed")


class GatewayError(Exception):
    """Gateway RPC error"""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"Gateway error {code}: {message}")


# ── Convenience: High-level Dashboard Integration ──────────────────────

class DashboardGateway:
    """
    High-level wrapper for dashboard integration.
    
    Exposes a simple async API matching the old runtime.py interface
    but backed by persistent Gateway connection.
    """
    
    def __init__(self, profile: str = "anna"):
        self.client = HermesGatewayClient(profile=profile)
        self._session_id: str | None = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._tool_results: dict[str, asyncio.Future] = {}
        
    async def start(self) -> bool:
        """Connect and ensure session exists."""
        if not await self.client.connect():
            return False
        
        # Try to resume most recent session
        sessions = await self.client.list_sessions(limit=1)
        if sessions and sessions.get("sessions"):
            latest = sessions["sessions"][0]
            await self.client.resume_session(latest["id"])
            self._session_id = latest["id"]
        else:
            # Create new session
            result = await self.client.create_session(title="ANA Dashboard Session")
            self._session_id = result.get("session_id")
        
        return self._session_id is not None
    
    async def send_message(self, text: str):
        """Send message and return submit result."""
        if not self._session_id:
            raise RuntimeError("No active session")
        
        # Submit prompt
        result = await self.client.submit_prompt(self._session_id, text)
        return result
    
    async def get_session(self) -> GatewaySession | None:
        return self.client._session
    
    async def close(self):
        await self.client.close()


# ── Testing ────────────────────────────────────────────────────────────

async def main():
    """Test gateway connection."""
    logging.basicConfig(level=logging.INFO)
    
    client = HermesGatewayClient(profile="anna")
    
    async def on_event(event: str, payload: dict):
        print(f"[EVENT] {event}: {json.dumps(payload)[:200]}")
    
    client.on_event = on_event
    
    if await client.connect():
        print("Connected!")
        
        # List sessions
        sessions = await client.list_sessions()
        print(f"Sessions: {json.dumps(sessions, indent=2)}")
        
        # Create session
        result = await client.create_session(title="Test from Dashboard")
        print(f"Created: {json.dumps(result, indent=2)}")
        
        # Submit prompt
        if result.get("session_id"):
            submit = await client.submit_prompt(result["session_id"], "Hello from ana-hermes-dashboard!")
            print(f"Submit: {json.dumps(submit, indent=2)}")
        
        await asyncio.sleep(2)
        await client.close()
    else:
        print("Failed to connect")


if __name__ == "__main__":
    asyncio.run(main())