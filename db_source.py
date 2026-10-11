"""db_source.py — single truth untuk pilihan DB lokal vs remote (tunnel).

- Sumber: ANA_DB_SOURCE=local|remote di .env (default local).
- Lokal : DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD.
- Remote: REMOTE_DB_* via ssh tunnel kphbwb-tunnel
          127.0.0.1:13307 -> 127.0.0.1:3306 di server.
- Password tak pernah keluar lewat API/log (hanya pw_len di log).
"""
import pathlib
import socket
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"

REMOTE_LOCAL_PORT = 13307
TUNNEL_HOST = "kphbwb-tunnel"
TUNNEL_TARGET = "127.0.0.1:3306"


def _parse_env_value(raw: str) -> str:
    s = raw.strip()
    if not s:
        return ""
    if s[0] in ('"', "'"):
        q = s[0]
        end = s.find(q, 1)
        if end != -1:
            return s[1:end]
        return s.strip('"').strip("'")
    if " #" in s:
        s = s.split(" #", 1)[0].strip()
    return s.strip().strip('"').strip("'")


def _read_env() -> dict:
    env = {}
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = _parse_env_value(v)
    except FileNotFoundError:
        pass
    return env


def source() -> str:
    return (_read_env().get("ANA_DB_SOURCE", "local") or "local").strip().lower()


def kwargs(src: str = "") -> dict:
    env = _read_env()
    s = (src or source())
    if s == "remote":
        return dict(
            host=env.get("REMOTE_DB_HOST", "127.0.0.1"),
            port=int(env.get("REMOTE_DB_PORT", str(REMOTE_LOCAL_PORT))),
            user=env.get("REMOTE_DB_USER", "root"),
            password=env.get("REMOTE_DB_PASSWORD", ""),
            database=env.get("REMOTE_DB_NAME", env.get("DB_NAME", "kph_bwb_sandbox2")),
            connect_timeout=8,
        )
    return dict(
        host=env.get("DB_HOST", "127.0.0.1"),
        port=int(env.get("DB_PORT", "3306")),
        user=env.get("DB_USER", "root"),
        password=env.get("DB_PASSWORD", ""),
        database=env.get("DB_NAME", "kph_bwb_sandbox2"),
        connect_timeout=5,
    )


def public_info() -> dict:
    """Info aman untuk API (tanpa password)."""
    env = _read_env()
    return dict(
        source=source(),
        local=dict(host=env.get("DB_HOST", "127.0.0.1"),
                   port=int(env.get("DB_PORT", "3306")),
                   database=env.get("DB_NAME", "kph_bwb_sandbox2"),
                   user=env.get("DB_USER", "root")),
        remote=dict(host=env.get("REMOTE_DB_HOST", "127.0.0.1"),
                    port=int(env.get("REMOTE_DB_PORT", str(REMOTE_LOCAL_PORT))),
                    database=env.get("REMOTE_DB_NAME", env.get("DB_NAME", "kph_bwb_sandbox2")),
                    user=env.get("REMOTE_DB_USER", "root"),
                    has_password=bool(env.get("REMOTE_DB_PASSWORD", ""))),
        tunnel=tunnel_ok(),
    )


def tunnel_ok(port: int = REMOTE_LOCAL_PORT) -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=2)
        s.close()
        return True
    except OSError:
        return False


def watchdog_tick() -> dict:
    """Dipanggil tiap request auth: source remote wajib tunnel hidup.
    Return {healed: bool, tunnel: bool, source: str}."""
    src = source()
    if src != "remote":
        return dict(source=src, tunnel=True, healed=False)
    if tunnel_ok():
        return dict(source=src, tunnel=True, healed=False)
    healed = ensure_tunnel()
    return dict(source=src, tunnel=healed, healed=healed)


def ensure_tunnel(port: int = REMOTE_LOCAL_PORT) -> bool:
    if tunnel_ok(port):
        return True
    try:
        subprocess.run(
            ["ssh", "-fN",
             "-L", f"127.0.0.1:{port}:127.0.0.1:3306",
             "-o", "ExitOnForwardFailure=yes",
             "-o", "BatchMode=yes",
             "-o", "ConnectTimeout=5",
             TUNNEL_HOST],
            capture_output=True, timeout=20)
    except Exception:
        return tunnel_ok(port)
    return tunnel_ok(port)


def test(kw: dict) -> dict:
    """Test koneksi, return {ok, users|error}. Tak bocorkan password."""
    import pymysql
    c = pymysql.connect(**kw)
    try:
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM directus_users")
        n = cur.fetchone()[0]
        return dict(ok=True, users=n)
    finally:
        try:
            c.close()
        except Exception:
            pass


def set_source(src: str) -> dict:
    """Tulis ANA_DB_SOURCE ke .env. Tak restart — auth baca file tiap query."""
    src = (src or "").strip().lower()
    if src not in ("local", "remote"):
        raise ValueError("source harus 'local' atau 'remote'")
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    out, seen = [], False
    for ln in lines:
        s = ln.strip()
        if s.startswith("#") or "=" not in s:
            out.append(ln)
            continue
        k, _, _ = s.partition("=")
        if k.strip() == "ANA_DB_SOURCE":
            out.append(f"ANA_DB_SOURCE={src}")
            seen = True
        else:
            out.append(ln)
    if not seen:
        out.append(f"ANA_DB_SOURCE={src}")
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    return dict(ok=True, source=src)
