"""Kredensial layanan Hermes (Opsi 2: gated serve).

Serve Hermes yang mengaktifkan auth gate (karena dashboard.public_url
non-loopback) MENOLAK legacy ?token= (403 selamanya) dan tak menyajikan
__HERMES_SESSION_TOKEN__ di `/`. Mekanisme resmi yang dipakai: login
username/password ke dashboard Hermes -> sesi cookie -> mint tiket WS
sekali-pakai (TTL 30 dtk) via POST /api/auth/ws-ticket -> WS ?ticket=.

Modul ini memegang sesi layanan (HERMES_SERVICE_USER/PASSWORD) + mint tiket
segar SETIAP connect/reconnect (tiket single-use, tak boleh dipakai ulang).
Tanpa kredensial terisi -> get_ws_ticket() kembalikan None (pemanggil pakai
jalur legacy seperti dulu; dev tanpa gate tak terpengaruh).

Kredensial HANYA dari env (tak pernah ditulis ke file/repo).
"""
import http.cookiejar
import json
import os
import threading
import urllib.request

_LOCK = threading.Lock()
_JAR = http.cookiejar.CookieJar()
_LOGGED_IN = False


def configured() -> bool:
    return bool(os.environ.get("HERMES_SERVICE_USER", "").strip()
                and os.environ.get("HERMES_SERVICE_PASSWORD", ""))


def _base() -> str:
    return (os.environ.get("HERMES_DASHBOARD_URL", "").strip()
            or "http://127.0.0.1:9121").rstrip("/")


def _opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_JAR))


def _post(path: str, body: dict, timeout: int = 15) -> tuple:
    req = urllib.request.Request(
        _base() + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _opener().open(req, timeout=timeout) as r:
            return r.status, r.read()[:512]
    except Exception as e:
        code = getattr(e, "code", None)
        return code or 0, str(e)[:200].encode()


def _login() -> bool:
    user = os.environ.get("HERMES_SERVICE_USER", "").strip()
    pw = os.environ.get("HERMES_SERVICE_PASSWORD", "")
    provider = os.environ.get("HERMES_SERVICE_PROVIDER", "").strip() or "basic"
    if not user or not pw:
        return False
    st, _ = _post("/auth/password-login",
                  {"provider": provider, "username": user, "password": pw})
    return st == 200


def get_ws_ticket() -> str | None:
    """Tiket WS segar (single-use) atau None bila layanan tak dikonfigurasi.

    Thread-safe; login ulang otomatis bila sesi kedaluwarsa (401 saat mint).
    """
    if not configured():
        return None
    with _LOCK:
        global _LOGGED_IN
        if not _LOGGED_IN and not _login():
            return None
        _LOGGED_IN = True
        st, body = _post("/api/auth/ws-ticket", {})
        if st == 200:
            try:
                t = json.loads(body.decode()).get("ticket", "")
                if t:
                    return t
            except Exception:
                pass
        # Sesi mungkin kedaluwarsa -> login sekali lagi lalu mint ulang.
        _LOGGED_IN = False
        if not _login():
            return None
        _LOGGED_IN = True
        st, body = _post("/api/auth/ws-ticket", {})
        if st == 200:
            try:
                return json.loads(body.decode()).get("ticket") or None
            except Exception:
                return None
        _LOGGED_IN = False
        return None
