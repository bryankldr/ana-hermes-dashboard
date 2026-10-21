"""Cek scope wilayah fail-closed — jalankan: .venv/bin/python3 tests/test_wilayah_scope.py

Aturan bisnis:
  DIREKSI/ADMINISTRATOR (tanpa kode wilayah) → akses semua divre + semua kph
  DIVRE  → hanya divre-nya (kode_divre wajib)
  ADM (KPH) → hanya kph-nya (kode_kph wajib)
  tanpa jabatan → TOLAK (bukan akses penuh)
  jabatan butuh kode tapi kosong → TOLAK
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import server  # noqa: E402


class H:
    """Handler palsu — _session_from_cookie di-monkeypatch."""

    def __init__(self, peer="127.0.0.1", headers=None):
        self.headers = headers or {}
        self.client_address = (peer, 54321)


def scope_for(sess):
    server._session_from_cookie = lambda h: sess
    return server._wilayah_scope_from_session(H())


def jab(code):
    return {"kode_jabatan": code, "nama_jabatan": code}


def sess(jabatan=None, kph=None, divre=None, bkph=None, rph=None, tpg=None):
    e = lambda v, k: None if not v else {k: v}  # noqa: E731
    return {
        "email": "x@example.com",
        "jabatan": jabatan,
        "kode_kph": e(kph, "kode_kph"),
        "kode_divre": e(divre, "kode_divre"),
        "kode_bkph": e(bkph, "kode_bkph"),
        "kode_rph": e(rph, "kode_rph"),
        "kode_tpg": tpg or [],
    }


DENY = server._SCOPE_DENY
fails = []


N = [0]


def eq(label, got, want):
    N[0] += 1
    if got != want:
        fails.append(f"{label}: got {got!r} want {want!r}")


def truthy(label, cond):
    N[0] += 1
    if not cond:
        fails.append(f"{label}: false")


# DIREKSI / ADMINISTRATOR tanpa kode = semua (tanpa clamp)
eq("DIREKSI", scope_for(sess(jab("DIREKSI"))), {})
eq("ADMINISTRATOR", scope_for(sess(jab("ADMINISTRATOR"))), {})
eq("DIREKSI meski ada kode", scope_for(sess(jab("DIREKSI"), kph=31211, divre=2)), {})

# DIVRE
eq("DIVRE ok", scope_for(sess(jab("DIVRE"), divre=2)), {"kode_divre": "2"})
eq("DIVRE abaikan kode_kph sisa", scope_for(sess(jab("DIVRE"), divre=2, kph=31211)),
   {"kode_divre": "2"})
truthy("DIVRE tanpa divre -> deny", DENY in scope_for(sess(jab("DIVRE"))))

# ADM (KPH)
eq("ADM ok", scope_for(sess(jab("ADM"), kph=31211, divre=2)),
   {"kode_divre": "2", "kode_kph": "31211"})
truthy("ADM tanpa kph -> deny", DENY in scope_for(sess(jab("ADM"), divre=2)))

# level lebih dalam
eq("K1 lengkap", scope_for(sess(jab("K1"), kph=31211, divre=2, bkph=9, rph=7)),
   {"kode_divre": "2", "kode_kph": "31211", "kode_bkph": "9", "kode_rph": "7"})
eq("MANTRI tanpa rph", scope_for(sess(jab("MANTRI"), kph=31211, divre=2, bkph=9)),
   {"kode_divre": "2", "kode_kph": "31211", "kode_bkph": "9"})

# fail-closed
truthy("tanpa jabatan -> deny", DENY in scope_for(sess(None)))
truthy("tanpa jabatan walau ada kode -> deny",
       DENY in scope_for(sess(None, kph=31211, divre=2)))
truthy("jabatan tanpa kode wilayah -> deny", DENY in scope_for(sess(jab("K4"))))
truthy("KPH (kode jabatan baru) tanpa kode -> deny", DENY in scope_for(sess(jab("KPH"))))
eq("KPH dengan kode -> clamp kph", scope_for(sess(jab("KPH"), kph=31211)).get("kode_kph"), "31211")

# TPG-only user tetap sah
eq("TPG-only", scope_for(sess(jab("K1"), tpg=[{"kode_tpg": "77"}])),
   {"kode_tpg_list": ["77"]})

# tanpa sesi: hanya pemanggil LOKAL (skrip/cron) yang boleh tanpa clamp.
# Klien jauh dengan token saja → TOLAK (dulu {} = data global = bypass jabatan).
server._session_from_cookie = lambda h: None
eq("tanpa sesi dari loopback = global", server._wilayah_scope_from_session(H("127.0.0.1")), {})
_remote = server._wilayah_scope_from_session(H("203.0.113.9"))
truthy("tanpa sesi dari klien jauh DITOLAK", server._SCOPE_DENY in _remote)
truthy("alasan menyebut sesi", "tanpa sesi" in str(_remote.get(server._SCOPE_DENY)))

# enforcement ikut menolak
server._session_from_cookie = lambda h: sess(jab("DIVRE"))
_p, _ov, deny, msg = server._enforce_wilayah_scope(H(), {"tahun": 2026})
truthy("enforce DIVRE tanpa divre deny", deny)
truthy("pesan menyebut alasan", "kode_divre" in msg)
ok, why = server._tiles_scope_ok(H(), "kph", "31211")
eq("tiles deny", ok, False)

server._session_from_cookie = lambda h: sess(jab("ADM"), kph=31211, divre=2)
_p2, _o2, deny2, _m2 = server._enforce_wilayah_scope(H(), {"kode_kph": "99999"})
eq("ADM clamp kode_kph", _p2.get("kode_kph"), "31211")
truthy("ADM tidak deny", not deny2)

if fails:
    print("FAIL")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("ALL PASS", "(%d cek)" % N[0])
