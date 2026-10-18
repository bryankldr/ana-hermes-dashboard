"""
auth_local.py — Local-DB auth for ANA HUD (mirror of server DB).

- Source truth: 127.0.0.1 kph_bwb_sandbox2.directus_users (argon2id password)
- Tidak lagi proxy ke https://sandbox2.kphbwb.web.id — sepenuhnya offline.
- HttpOnly SameSite=Lax cookie ana_session, server-side store .ana_sessions.json 0600
- 1 akun 1 perangkat: device_hash = sha256(UA|SALT)[:32]
- Custom 2FA: field `2fa` tinyint(1), `2fa_secret` varchar base32, `hud_access`, `panel_access`
  TOTP RFC6238 window +-1 via stdlib (hmac+hashlib)
"""

import base64
import hashlib
import hmac
import json
import os
import pathlib
import re
import secrets
import struct
import time
import threading

try:
    from argon2 import PasswordHasher as _PH
    from argon2.exceptions import VerifyMismatchError as _VME, InvalidHashError as _IHE
    try:
        from argon2.exceptions import InvalidHash as _IH
    except ImportError:
        _IH = _IHE
    _ARGON2_OK = True
except Exception:
    _PH = None
    _VME = _IHE = _IH = Exception
    _ARGON2_OK = False

ROOT = pathlib.Path(__file__).resolve().parent
SESS_FILE = ROOT / ".ana_sessions.json"
_LOCK = threading.Lock()

SESSION_TTL = int(os.environ.get("ANA_SESSION_TTL", "28800"))
DEVICE_SALT = os.environ.get("ANA_DEVICE_SALT", "ana-device-salt-v1")

# Rate limiting configuration
_RL_MAX_REQUESTS = int(os.environ.get("ANA_RATE_LIMIT_MAX", "5"))  # Default: 5 requests
_RL_WINDOW_SECONDS = int(os.environ.get("ANA_RATE_LIMIT_WINDOW", "60"))  # Default: 60 seconds
_RL_API_MAX_REQUESTS = int(os.environ.get("ANA_RATE_LIMIT_API_MAX", "100"))  # Default: 100 requests
_RL_API_WINDOW_SECONDS = int(os.environ.get("ANA_RATE_LIMIT_API_WINDOW", "60"))  # Default: 60 seconds

_RL = {}  # {ip: [timestamp, ...]}
_RL_API = {}  # {session_id: [timestamp, ...]} for API rate limiting
_RL_LOCK = threading.Lock()

# ── TOTP (RFC 6238) ───────────────────────────────────────────
def _b32_secret(nbytes=20):
    raw = secrets.token_bytes(nbytes)
    return base64.b32encode(raw).decode().rstrip("=")

def _totp(secret_b32, at=None, step=30, digits=6):
    at = time.time() if at is None else at
    s = secret_b32.strip().replace(" ", "").upper()
    pad = "=" * ((8 - len(s) % 8) % 8)
    try:
        key = base64.b32decode(s + pad)
    except Exception:
        return None
    counter = int(at // step)
    msg = struct.pack(">Q", counter)
    hm = hmac.new(key, msg, hashlib.sha1).digest()
    o = hm[19] & 0x0F
    code = struct.unpack(">I", hm[o:o+4])[0] & 0x7FFFFFFF
    return str(code % (10 ** digits)).zfill(digits)

def totp_verify(secret_b32, otp, window=1, step=30, digits=6):
    otp = (otp or "").strip()
    if not secret_b32 or not otp or not otp.isdigit() or len(otp) != digits:
        return False
    now = time.time()
    for w in range(-window, window + 1):
        if _totp(secret_b32, at=now + w * step, step=step, digits=digits) == otp:
            return True
    return False

def totp_otpauth_url(secret_b32, email, issuer="ANA HUD"):
    import urllib.parse
    label = f"{issuer}:{email}"
    q = urllib.parse.urlencode({"secret": secret_b32, "issuer": issuer, "algorithm": "SHA1", "digits": "6", "period": "30"})
    return f"otpauth://totp/{urllib.parse.quote(label)}?{q}"

def device_hash(user_agent, ip="", device_id=""):
    """Hash pengenal perangkat: device_id (UUID persisten per browser,
    dari header X-Ana-Device) + UA + SALT.

    UA saja TIDAK cukup: Chrome laptop vs Chrome tablet sering identik
    ("Mozilla/5.0" + versi sama) → hash sama → evict tak jalan → dua
    perangkat hidup bareng. device_id membedakan; UA tetap ikut agar
    copy cookie mentah ke browser lain tidak lolos.
    device_id kosong = fallback UA-only (kompat sesi lama pra-patch)."""
    try:
        did = str(device_id or "").strip()
    except Exception:
        did = ""
    if did:
        return hashlib.sha256(f"{did}|{user_agent}|{DEVICE_SALT}".encode()).hexdigest()[:32]
    return hashlib.sha256(f"{user_agent}|{DEVICE_SALT}".encode()).hexdigest()[:32]


def device_short(device_id=""):
    """Label perangkat untuk log/banner (8 char, tak ada PII)."""
    try:
        return hashlib.sha256(str(device_id or "").encode()).hexdigest()[:8]
    except Exception:
        return "?"

def _load_sessions():
    try:
        return json.loads(SESS_FILE.read_text(encoding="utf-8"))
    except:
        return {}

def _save_sessions(d):
    # Tulis ATOMIK (tmp+rename): server ThreadingHTTPServer melayani banyak
    # thread; write_text langsung (truncate+isi) membuat thread pembaca lain
    # dapat JSON robek → terbaca {} → sesi valid dianggap hilang → 401
    # expired → mental ke login padahal sesi ada ("terkadang keluar sendiri",
    # makin sering saat 2 perangkat polling bersamaan). Rename POSIX atomik:
    # pembaca selalu lihat file lama utuh atau baru utuh. Pola sama
    # _layout_atomic_write / insight publish.
    try:
        tmp = SESS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=2), encoding="utf-8")
        try: tmp.chmod(0o600)
        except: pass
        os.replace(tmp, SESS_FILE)
    except: pass

def check_rate_limit(ip):
    """Check login rate limit per IP (brute force protection)."""
    now = time.time()
    with _RL_LOCK:
        arr = _RL.get(ip, [])
        arr = [t for t in arr if now - t < _RL_WINDOW_SECONDS]
        if len(arr) >= _RL_MAX_REQUESTS:
            _RL[ip] = arr
            return False
        arr.append(now)
        _RL[ip] = arr
        return True

def check_api_rate_limit(session_id: str) -> tuple[bool, int]:
    """
    Check API rate limit per session.
    
    Returns:
        (allowed, remaining): True if allowed, False if rate limited
    """
    now = time.time()
    with _RL_LOCK:
        arr = _RL_API.get(session_id, [])
        arr = [t for t in arr if now - t < _RL_API_WINDOW_SECONDS]
        if len(arr) >= _RL_API_MAX_REQUESTS:
            _RL_API[session_id] = arr
            return False, 0
        arr.append(now)
        _RL_API[session_id] = arr
        remaining = _RL_API_MAX_REQUESTS - len(arr)
        return True, remaining

# ── DB ────────────────────────────────────────────────────────
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

def _db_kwargs():
    try:
        import db_source
        kw = db_source.kwargs()
        # Auto-heal: source remote butuh tunnel 13307; coba hidupkan bila mati.
        try:
            if db_source.source() == "remote" and not db_source.tunnel_ok(kw.get("port", 13307)):
                db_source.ensure_tunnel(kw.get("port", 13307))
        except Exception:
            pass
        return kw
    except Exception:
        pass
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line=line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1)
            env[k.strip()]=_parse_env_value(v)
    return dict(
        host=env.get("DB_HOST","127.0.0.1"),
        port=int(env.get("DB_PORT","3306")),
        user=env.get("DB_USER","root"),
        password=env.get("DB_PASSWORD",""),
        database=env.get("DB_NAME","kph_bwb_sandbox2"),
        connect_timeout=5,
    )

def _conn():
    import pymysql
    return pymysql.connect(**_db_kwargs())

def _row_to_dict(cur, row):
    if row is None: return None
    cols=[d[0] for d in cur.description]
    return dict(zip(cols, row))

def _fetch_user_row(where_sql, params):
    conn=_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM directus_users WHERE {where_sql} LIMIT 1", params)
            row=cur.fetchone()
            if row is None: return None
            d=_row_to_dict(cur, row)
            # normalize panel_access if JSON string
            return d
    finally:
        conn.close()

def get_user_by_email(email):
    return _fetch_user_row("LOWER(email)=LOWER(%s)", (email,))

def get_user_by_id(uid):
    return _fetch_user_row("id=%s", (uid,))

def verify_password(hash_str, password):
    if not hash_str: return False
    try:
        # argon2id
        if hash_str.startswith("$argon2"):
            if not _ARGON2_OK or _PH is None:
                return False
            ph=_PH()
            try:
                ph.verify(hash_str, password)
                return True
            except (_VME, _IH, _IHE):
                return False
        # fallback bcrypt
        if hash_str.startswith("$2"):
            import bcrypt
            return bcrypt.checkpw(password.encode(), hash_str.encode())
        # plain fallback (should not happen)
        return secrets.compare_digest(hash_str, password)
    except Exception:
        return False

def fetch_user_profile_by_id(user_id):
    """Return enriched profile dict for authenticated user."""
    row=get_user_by_id(user_id)
    if not row: return None
    conn=_conn()
    try:
        with conn.cursor() as cur:
            # jabatan
            jab=None
            if row.get("jabatan"):
                cur.execute("SELECT id, kode_jabatan, nama_jabatan FROM jabatan WHERE id=%s", (row["jabatan"],))
                r=cur.fetchone()
                if r: jab=_row_to_dict(cur, r)
            # divre
            dv=None
            if row.get("kode_divre"):
                cur.execute("SELECT id, kode_divre, divre FROM divre WHERE id=%s", (row["kode_divre"],))
                r=cur.fetchone()
                if r: dv=_row_to_dict(cur, r)
            # kph
            kp=None
            if row.get("kode_kph"):
                cur.execute("SELECT id, kode_divre, kode_kph, divre, kph FROM kph WHERE id=%s", (row["kode_kph"],))
                r=cur.fetchone()
                if r: kp=_row_to_dict(cur, r)
            # bkph
            bk=None
            if row.get("kode_bkph"):
                cur.execute("SELECT id, kode_divre, kode_kph, kode_bkph, divre, kph, bkph FROM bkph WHERE id=%s", (row["kode_bkph"],))
                r=cur.fetchone()
                if r: bk=_row_to_dict(cur, r)
            # rph
            rp=None
            if row.get("kode_rph"):
                cur.execute("SELECT id, kode_divre, kode_kph, kode_bkph, kode_rph, divre, kph, bkph, rph FROM rph WHERE id=%s", (row["kode_rph"],))
                r=cur.fetchone()
                if r: rp=_row_to_dict(cur, r)
            # bidang
            bd=None
            if row.get("bidang"):
                cur.execute("SELECT id, kode_bidang, nama_bidang FROM bidang WHERE id=%s", (row["bidang"],))
                r=cur.fetchone()
                if r: bd=_row_to_dict(cur, r)
            # tpg via M2M (optional)
            tpg_list=[]
            try:
                cur.execute("SELECT getah_daftar_tpg_id FROM junction_directus_users_getah_daftar_tpg WHERE directus_users_id=%s", (row["id"],))
                ids=[r[0] for r in cur.fetchall()]
                if ids:
                    # try to resolve names from getah_daftar_tpg
                    fmt=",".join(["%s"]*len(ids))
                    cur.execute(f"SELECT id, kode_tpg, nama_tpg FROM getah_daftar_tpg WHERE id IN ({fmt}) LIMIT 20", ids)
                    for r in cur.fetchall():
                        d=_row_to_dict(cur, r)
                        tpg_list.append(d)
            except: pass

            # sanitize password etc
            row.pop("password", None)
            row.pop("token", None)
            row.pop("auth_data", None)
            # attach expanded
            row["jabatan"] = jab
            row["kode_divre"] = dv
            row["kode_kph"] = kp
            row["kode_bkph"] = bk
            row["kode_rph"] = rp
            row["bidang"] = bd
            row["kode_tpg"] = tpg_list
            return row
    finally:
        conn.close()

def fetch_user_profile_by_email(email):
    row=get_user_by_email(email)
    if not row: return None
    return fetch_user_profile_by_id(row["id"])

def update_user_2fa(user_id, enabled, secret):
    conn=_conn()
    try:
        with conn.cursor() as cur:
            if enabled:
                cur.execute("UPDATE directus_users SET `2fa`=1, `2fa_secret`=%s, tfa_secret=NULL WHERE id=%s", (secret, user_id))
            else:
                cur.execute("UPDATE directus_users SET `2fa`=0, `2fa_secret`=NULL, tfa_secret=NULL WHERE id=%s", (user_id,))
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)[:400]
    finally:
        conn.close()

def sanitize_profile_for_client(prof):
    if not prof: return None
    pa = prof.get("panel_access")
    if isinstance(pa, str):
        try: pa = json.loads(pa)
        except: pass
    tfa = bool(int(prof.get("2fa") or 0)) if "2fa" in prof else bool(prof.get("tfa_secret") or prof.get("2fa_secret"))
    out = {
        "id": prof.get("id"),
        "email": prof.get("email"),
        "first_name": prof.get("first_name"),
        "last_name": prof.get("last_name"),
        "role": prof.get("role"),
        "tfa_enabled": tfa,
        "2fa": tfa,
        "hud_access": bool(int(prof.get("hud_access") or 0)) if "hud_access" in prof and prof.get("hud_access") is not None else bool(prof.get("hud_access")),
        "panel_access": pa,
        "jabatan": prof.get("jabatan"),
        "bidang": prof.get("bidang"),
        "kode_divre": prof.get("kode_divre"),
        "kode_kph": prof.get("kode_kph"),
        "kode_bkph": prof.get("kode_bkph"),
        "kode_rph": prof.get("kode_rph"),
        "kode_tpg": prof.get("kode_tpg", []),
    }
    return out

# ── Session (local) ───────────────────────────────────────────
def create_session(user_profile, ua, ip, device_id="", pending_bind=False):
    sid = secrets.token_urlsafe(32)
    try:
        did = str(device_id or "").strip()[:64]
    except Exception:
        did = ""
    dh = device_hash(ua, ip, did)
    now=time.time()
    sess = {
        "id": sid,
        "user_id": user_profile.get("id"),
        "email": user_profile.get("email"),
        "first_name": user_profile.get("first_name"),
        "last_name": user_profile.get("last_name"),
        "role": user_profile.get("role"),
        "jabatan": user_profile.get("jabatan"),
        "kode_divre": user_profile.get("kode_divre"),
        "kode_kph": user_profile.get("kode_kph"),
        "kode_bkph": user_profile.get("kode_bkph"),
        "kode_rph": user_profile.get("kode_rph"),
        "kode_tpg": user_profile.get("kode_tpg", []),
        "hud_access": bool(user_profile.get("hud_access")),
        "panel_access": user_profile.get("panel_access"),
        "tfa_enabled": bool(int(user_profile.get("2fa") or 0)) if "2fa" in user_profile else bool(user_profile.get("tfa_secret")),
        "2fa": bool(int(user_profile.get("2fa") or 0)) if "2fa" in user_profile else False,
        "expires_at": now + SESSION_TTL,
        "device_hash": dh,
        "device_label": device_short(did) if did else "?",
        "ip": ip,
        "ua": ua[:200],
        "created": now,
        "last_seen": now,
    }
    if pending_bind:
        # Switch-QR: device mobile belum dikenal — diikat saat kontak pertama
        # (bind_session_device). Tanpa flag ini, did kosong = fallback UA-only
        # yang rapuh; dengan flag, bind eksplisit dan satu-kali.
        sess["pending_bind"] = True
    with _LOCK:
        db = _load_sessions()
        uid = sess["user_id"]
        evicted = []
        # Soft-revoke (BUKAN hapus fisik): sesi lama ditandai revoked agar
        # perangkat lama dapat reason evicted_by_new_device (banner + ambil
        # alih), bukan "expired" yang menyesatkan. Hapus fisik hanya saat
        # logout eksplisit (destroy_session) atau prune (>7 hari).
        for k, v in list(db.items()):
            if v.get("user_id") != uid:
                continue
            if v.get("device_hash") != dh:
                if not v.get("revoked_by"):
                    v["revoked_by"] = dh
                    v["revoked_at"] = now
                    v["revoked_label"] = device_short(did) if did else "?"
                    db[k] = v
                evicted.append(k)
            else:
                # A3: yatim se-device (retry login berkali-kali) dibuang —
                # browser selalu pegang cookie sesi terbaru, jadi aman.
                # Beda-device tetap soft-revoke (jalur banner di atas).
                db.pop(k, None)
        # Reclaim: revoked lama dengan device SAMA = milik login ini —
        # hidupkan kembali slotnya? Tidak — sesi baru tetap dibuat, tapi
        # revoked kembar-dh dibersihkan agar file tak menumpuk.
        for k, v in list(db.items()):
            if v.get("user_id") == uid and v.get("revoked_by") and v.get("device_hash") == dh:
                db.pop(k, None)
        # Prune revoked tua (>7 hari) milik user ini.
        for k, v in list(db.items()):
            if v.get("user_id") == uid and v.get("revoked_by"):
                try:
                    if now - float(v.get("revoked_at") or 0) > 7 * 86400:
                        db.pop(k, None)
                except Exception:
                    pass
        db[sid] = sess
        _save_sessions(db)
    # hardware_id di directus_users = truth persisten perangkat aktif.
    # Best-effort (DB mati = login tetap jalan, audit menyusul). Isi hash,
    # bukan device_id mentah (privasi). Admin NULL-kan untuk reset paksa.
    try:
        _write_hardware_id(uid, dh)
    except Exception:
        pass
    evict_info = None
    if evicted:
        try:
            evict_info = {"device_label": device_short(did) if did else "?",
                          "at": now,
                          "ua_short": str(ua or "")[:60]}
        except Exception:
            evict_info = {"at": now}
    return sid, sess, evicted, evict_info


def bind_session_device(sid, did, ua):
    """TOFU bind untuk sesi switch-QR (pending_bind): kunci device pertama
    yang kontak dengan did valid. Satu-kali (flag dibersihkan). Return True
    bila sesi kini terikat pada did tersebut (termasuk bila sudah cocok).

    Aman: hanya sesi ber-flag yang bisa di-bind; sesi normal tanpa flag
    menolak (perilaku anti-curi-cookie tetap seperti semula). Tanpa flag,
    perubahan device = evict seperti biasa di _session_from_cookie.
    """
    try:
        d = str(did or "").strip()[:64]
        if not d or not re.fullmatch(r"[A-Za-z0-9_=\-]{8,64}", d):
            return False
        with _LOCK:
            db = _load_sessions()
            s = db.get(sid)
            if not s or not s.get("pending_bind"):
                return False
            if s.get("device_hash") == device_hash(ua or "", "", d):
                s.pop("pending_bind", None)
                db[sid] = s
                _save_sessions(db)
                return True
            s["device_hash"] = device_hash(ua or "", "", d)
            s["device_label"] = device_short(d)
            s.pop("pending_bind", None)
            db[sid] = s
            _save_sessions(db)
            return True
    except Exception:
        return False


def _write_hardware_id(user_id, dh):
    try:
        if not user_id or not dh:
            return
        conn = _conn()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE directus_users SET hardware_id=%s WHERE id=%s",
                            (str(dh), str(user_id)))
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception:
        pass

def get_session(sid):
    with _LOCK:
        db = _load_sessions()
        s = db.get(sid)
        if not s: return None
        # Soft-revoked = mati untuk semua keperluan kecuali pesan evict.
        # Tanpa gate ini perangkat yang ditendang tetap lolos (bug lama).
        if s.get("revoked_by"):
            return dict(s)
        if time.time() > float(s.get("expires_at", 0)):
            db.pop(sid, None)
            _save_sessions(db)
            return None
        return s

def touch_session(sid):
    with _LOCK:
        db = _load_sessions()
        s = db.get(sid)
        if s:
            s["last_seen"] = time.time()
            db[sid] = s
            _save_sessions(db)

def refresh_session(sid):
    with _LOCK:
        db = _load_sessions()
        s = db.get(sid)
        if not s: return None, "session not found"
        if s.get("revoked_by"):
            return None, "evicted_by_new_device"
        if time.time() > float(s.get("expires_at", 0)):
            db.pop(sid, None)
            _save_sessions(db)
            return None, "session expired"
        s["expires_at"] = time.time() + SESSION_TTL
        s["last_seen"] = time.time()
        db[sid] = s
        _save_sessions(db)
        return s, None

def destroy_session(sid):
    with _LOCK:
        db = _load_sessions()
        db.pop(sid, None)
        _save_sessions(db)
    return True


def destroy_all_sessions():
    """Hapus semua sesi login — dipakai saat switch sumber DB (wajib login ulang)."""
    with _LOCK:
        _save_sessions({})
    return True
