"""PTY terminal manager for the ANA HUD.

Spawns real local shell sessions and exposes them through small HTTP endpoints.
Kept dependency-free: pty(7) + selectors only.
"""
import fcntl
import os
import pty
import re
import secrets
import signal
import struct
import subprocess
import termios
import threading
import time
import queue

import runtime

_SHELL = os.environ.get("ANA_SHELL", "/bin/bash").strip() or "/bin/bash"
_LOCK = threading.Lock()
_SESSIONS: dict[str, "_Terminal"] = {}
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{24,80}$")


def _new_id() -> str:
    return secrets.token_urlsafe(32)[:48]


class _Terminal:
    def __init__(self, cols: int = 80, rows: int = 24):
        self.id = _new_id()
        self.cols, self.rows = cols, rows
        self.master_fd, slave_fd = pty.openpty()
        self._set_winsize(rows, cols)

        env = dict(os.environ)
        env.update({
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "LANG": env.get("LANG", "C.UTF-8"),
        })

        self.proc = subprocess.Popen(
            [_SHELL, "--noprofile", "--norc"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=runtime.WORKDIR,
            env=env,
            preexec_fn=os.setsid,
            close_fds=True,
        )
        os.close(slave_fd)
        os.set_blocking(self.master_fd, False)

        self.queue: queue.Queue[bytes] = queue.Queue(maxsize=4096)
        self.alive = True
        self.created_at = time.monotonic()
        self.ttl = 3600
        self._thread = threading.Thread(target=self._read_loop, daemon=True, name=f"term-{self.id[:8]}")
        self._thread.start()

    def _set_winsize(self, rows: int, cols: int):
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def _read_loop(self):
        while self.alive:
            try:
                data = os.read(self.master_fd, 65536)
            except BlockingIOError:
                time.sleep(0.015)
                continue
            except OSError:
                break
            if not data:
                break
            try:
                self.queue.put_nowait(data)
            except queue.Full:
                # Drop oldest under pressure; interactive shell, not a pipe.
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    pass
                self.queue.put(data)
        self.alive = False

    def write(self, data: bytes):
        try:
            os.write(self.master_fd, data)
        except OSError:
            self.alive = False

    def resize(self, cols: int, rows: int):
        self.cols, self.rows = cols, rows
        self._set_winsize(rows, cols)

    def close(self):
        self.alive = False
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.close(self.master_fd)
        except OSError:
            pass


def create(cols: int, rows: int, ttl: int = 3600) -> _Terminal:
    t = _Terminal(cols=cols, rows=rows)
    t.created_at = time.monotonic()
    t.ttl = ttl
    with _LOCK:
        _cleanup_locked()
        _SESSIONS[t.id] = t
    return t


def get(term_id: str):
    if not _ID_RE.match(term_id):
        return None
    with _LOCK:
        _cleanup_locked()
        return _SESSIONS.get(term_id)


def close(term_id: str) -> bool:
    with _LOCK:
        t = _SESSIONS.pop(term_id, None)
    if not t:
        return False
    t.close()
    return True


def _cleanup_locked():
    now = time.monotonic()
    for tid, t in list(_SESSIONS.items()):
        if not t.alive or (now - getattr(t, "created_at", now)) > getattr(t, "ttl", 3600):
            t.close()
            _SESSIONS.pop(tid, None)


def cleanup_all():
    with _LOCK:
        sessions = list(_SESSIONS.values())
        _SESSIONS.clear()
    for t in sessions:
        t.close()
