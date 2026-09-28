"""
Command matrix for the Hermes-backed ANA dashboard.

Local commands keep the HUD fast for mission control/status while prompts and
unknown slash commands are handed to Hermes Agent. Hermes-native tool access comes
from the runtime subprocess (`hermes chat -q ...`) using the configured profile.
"""
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parent
STATE_FILE = pathlib.Path(os.environ.get("ANA_STATE", ROOT / "state.json"))
_LOCK = threading.Lock()
_DEFAULT = {"profile": [], "goal": "", "personality": "", "tasks": [], "missions": []}


def _load_unlocked():
    try:
        d = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        # A hand-edited or truncated state file can be a list, a number or null.
        # {**DEFAULT, **d} raises TypeError on anything but a mapping, and that
        # escaped the except below, so one bad file made every run and the
        # context block die instead of falling back to defaults.
        if not isinstance(d, dict):
            return dict(_DEFAULT)
        out = {**_DEFAULT, **d}
        # Same problem one level down: a task without "text" made the kanban
        # builder raise KeyError. Normalise the list fields to the right shape.
        for key in ("profile", "tasks", "missions"):
            if not isinstance(out.get(key), list):
                out[key] = []
        for t in out["tasks"] + out["missions"]:
            if not isinstance(t, dict):
                continue
            t.setdefault("text", t.get("mission", "") or "")
            t.setdefault("done", t.get("status") == "done")
        for key in ("goal", "personality"):
            if not isinstance(out.get(key), str):
                out[key] = ""
        return out
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULT)


def load():
    with _LOCK:
        return _load_unlocked()


def _save_unlocked(d):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_FILE.with_name(f".{STATE_FILE.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, STATE_FILE)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def save(d):
    with _LOCK:
        _save_unlocked(d)


def update_state(mutator):
    """Apply one read-modify-write transaction without losing concurrent updates."""
    with _LOCK:
        d = _load_unlocked()
        result = mutator(d)
        _save_unlocked(d)
        return result


def context_block():
    d = load()
    out = []
    if d["profile"]:
        out.append("## User profile notes from ANA dashboard\n" + "\n".join(f"- {x}" for x in d["profile"][-40:]))
    if d["goal"]:
        out.append(f"## Standing objective\n{d['goal']}\nKeep it in mind; mention it only when relevant.")
    if d["personality"]:
        out.append(f"## Tone overlay\n{d['personality']}\nThis adjusts delivery; stay concise.")
    open_tasks = [t for t in d["tasks"] if not t.get("done")]
    if open_tasks:
        out.append("## Mission queue\n" + "\n".join(f"- {t['text']}" for t in open_tasks[:20]))
    return "\n\n".join(out)


JOBS = {}
_JOB_LOCK = threading.Lock()


def start_background(mission, runner):
    jid = uuid.uuid4().hex[:8]
    with _JOB_LOCK:
        JOBS[jid] = {"id": jid, "status": "running", "mission": mission,
                     "result": "", "started": time.time(), "finished": None}
    update_state(lambda d: d["missions"].append(
        {"id": jid, "mission": mission, "status": "running", "at": time.time()}))

    def _work():
        text = ""
        status = "done"
        try:
            for ev in runner(mission):
                if ev.get("t") == "delta":
                    text += ev["text"]
                elif ev.get("t") == "error":
                    status = "failed"
                    text = text or ("failed: " + str(ev.get("message", ""))[:260])
        except Exception as e:  # noqa: BLE001
            status = "failed"
            text = f"failed: {e}"[:260]
        with _JOB_LOCK:
            JOBS[jid].update(status="done", result=text.strip(), finished=time.time())
        def finish(d2):
            for item in d2.get("missions", []):
                if item.get("id") == jid:
                    item.update(status=status, finished=time.time(), result=text.strip()[:500])
        update_state(finish)

    threading.Thread(target=_work, daemon=True).start()
    return jid


def jobs_snapshot():
    with _JOB_LOCK:
        return [dict(j) for j in JOBS.values()]


def take_finished():
    with _JOB_LOCK:
        done = [dict(j) for j in JOBS.values() if j["status"] == "done"]
        for j in done:
            JOBS.pop(j["id"], None)
        return done


_CMD = re.compile(r"^\s*/(new|profile|goal|personality|mode|kanban|mission|missions|background|tools|toolsets|connectors|connect|status|commands|help|browser|clear)\b\s*(.*)$", re.I | re.S)


def _hermes_command(*args):
    configured = os.environ.get("HERMES_CMD", "").strip()
    if configured:
        return shlex.split(configured) + list(args)
    executable = shutil.which("hermes")
    if executable:
        return [executable, *args]
    return ["python3", "-m", "hermes_cli.main", *args]


def _shell(cmd, timeout=25):
    try:
        p = subprocess.run(cmd, text=True, cwd=os.getcwd(), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout)
        return (p.stdout or p.stderr or "").strip()[:3500]
    except Exception as e:  # noqa: BLE001
        return f"Unavailable: {e}"


def _commands_reply():
    return """Perintah slash dashboard tersedia:
/new — reset thread Hermes
/goal <text|status|clear> — atur/baca/hapus objektif
/profile <fact> — tambah catatan profil lokal
/personality <tone> — atur nada ANA
/mode [asisten|coding|status] — ganti/lihat mode ANA
/kanban [task] — baca/tambah antrean misi
/mission [task] — alias /kanban
/background <mission> — jalan misi Hermes background
/tools — tampil status tools Hermes
/connectors — jelaskan tools Hermes ikut ke dashboard
/connect <name> — tanya cara konek aplikasi pihak ketiga
/toolsets — minta daftar toolsets Hermes
/status — status runtime/profil lokal
/browser <task> — minta Hermes pakai tools browser/Chrome
/clear — bersihkan panel respons
/help atau /commands — tampil daftar ini

Ketik prompt Hermes normal juga bisa. Slash tidak dikenal diteruskan ke Hermes.
Minta "ganti ke mode asisten/coding" lewat chat juga bisa."""


def handle(message, runner=None):
    m = _CMD.match(message or "")
    if not m:
        return None
    cmd, arg = m.group(1).lower(), m.group(2).strip()
    d = load()

    if cmd in ("help", "commands"):
        return dict(message=None, reply=_commands_reply(), note="commands shown")

    if cmd == "mode":
        arg = arg.strip().lower()
        # Under `python3 server.py` the live module is __main__; `import server`
        # would load a SECOND copy with its own MODE dict, so /mode reported a
        # successful switch that never touched the running server. Reuse
        # whichever module object is actually live, and only fall back to a
        # plain import when this is used outside the server (tests, scripts).
        _srv = sys.modules.get("server") or sys.modules.get("__main__")
        if not hasattr(_srv, "get_mode"):
            try:
                import server as _srv  # noqa: F811
            except Exception:
                _srv = None
        if not arg or arg == "status":
            cur = _srv.get_mode() if _srv else "coding"
            return dict(message=None, reply=f"Mode ANA saat ini: {cur}", note=f"mode={cur}")
        if arg in ("asisten", "coding"):
            if _srv:
                _srv.set_mode(arg)
                cur = _srv.get_mode()
            else:
                cur = arg
            return dict(message=None, reply=f"Mode ANA diganti ke {cur}.", note=f"mode -> {cur}")
        return dict(message=None, reply="Pakai /mode asisten, /mode coding, atau /mode status.", note="mode help")

    if cmd == "clear":
        return dict(message=None, reply="Layar dibersihkan. Sesi Hermes tetap.", note="display clear")

    if cmd == "new":
        return dict(fresh=True, message=arg or "Mulai sesi Hermes baru. Sapa saya satu baris singkat gaya ANA dalam bahasa Indonesia.", note="Hermes thread reset")

    if cmd == "status":
        profile = os.environ.get("HERMES_PROFILE", os.environ.get("ANA_PROFILE", "default"))
        runtime = os.environ.get("HERMES_CMD", "hermes")
        return dict(message=None, reply=f"Dashboard Hermes online. profil={profile}; runtime={runtime}; workdir={os.getcwd()}; suara=browser Web Speech + ElevenLabs opsional.", note="status read")

    if cmd in ("tools", "toolsets"):
        if cmd == "tools":
            out = _shell(_hermes_command("tools", "list"))
            reply = out or "Daftar tools kosong. Jalankan di shell yang bisa `hermes tools list`, atau set HERMES_CMD."
            return dict(message=None, reply=reply, note="tools Hermes tampil")
        return dict(message="Daftarkan toolsets Hermes yang aktif dan tools pihak ketiga yang terkonek. Sertakan ketersediaan browser/Chrome. Ringkas, jawab penuh dalam bahasa Indonesia.", note="toolsets diminta")

    if cmd == "connectors":
        return dict(message=None, note="connector bridge explained", reply=(
            "Dashboard ini tidak perlu wiring terpisah. Ia jalankan Hermes pakai profil aktif, jadi aplikasi pihak ketiga yang sudah konek di Hermes otomatis ikut ke sini.\n\n"
            "Konek aplikasi di Hermes sendiri: hermes tools, hermes mcp, hermes gateway setup, atau skill terkait. Lalu restart dashboard.\n\n"
            "Pakai /tools atau /toolsets untuk lihat apa yang bisa dijangkau dashboard."
        ))

    if cmd == "connect":
        target = (arg or "third-party app").strip()
        return dict(message=(
            f"Jelaskan cara Hermes-native yang benar untuk konek {target} sebagai aplikasi/tools pihak ketiga dalam bahasa Indonesia. "
            "Jelaskan umum: dashboard mewarisi apa yang sudah konek di Hermes, tidak simpan kredensial terpisah. "
            "Sebut keluarga perintah Hermes relevan jika tahu, seperti hermes tools, hermes mcp, hermes gateway setup, atau skill. Jawab Indonesia."
        ), note=f"connector help: {target[:40]}")

    if cmd == "browser":
        task = arg or "buka atau inspeksi Google Chrome pakai tools browser/computer-use Hermes yang ada dan lapor apa yang tersedia"
        return dict(message=f"Pakai tooling browser/Google Chrome Hermes jika ada dalam bahasa Indonesia: {task}", note="browser mission armed")

    if cmd == "profile":
        if not arg:
            facts = d["profile"]
            return dict(message=None, reply=("\n".join(f"- {x}" for x in facts[-20:]) if facts else "Belum ada catatan profil."), note="profile read")
        update_state(lambda state: state["profile"].append(arg))
        return dict(message=f'User simpan catatan profil dashboard: "{arg}". Konfirmasi satu baris singkat dalam bahasa Indonesia.', note=f"profile += {arg[:50]}")

    if cmd == "goal":
        if arg.lower() == "clear":
            update_state(lambda state: state.__setitem__("goal", ""))
            return dict(message=None, reply="Objektif dibersihkan.", note="goal cleared")
        if not arg or arg.lower() == "status":
            return dict(message=None, reply=d["goal"] or "Belum ada objektif.", note="goal read")
        update_state(lambda state: state.__setitem__("goal", arg))
        return dict(message=f'User atur objektif: "{arg}". Konfirmasi satu baris singkat Indonesia.', note=f"goal set: {arg[:50]}")

    if cmd == "personality":
        if not arg:
            return dict(message=None, reply=d["personality"] or "Persona ANA default aktif.", note="persona read")
        update_state(lambda state: state.__setitem__("personality", arg))
        return dict(message=f'Overlay nada berubah ke: "{arg}". Balas satu baris singkat Indonesia pakai nada itu.', note=f"persona: {arg[:50]}")

    if cmd in ("kanban", "mission", "missions"):
        if arg:
            update_state(lambda state: state["tasks"].append(
                {"text": arg, "done": False, "at": time.time()}))
            return dict(message=f'Ditambah ke antrean misi: "{arg}". Konfirmasi satu baris Indonesia.', note=f"mission += {arg[:50]}")
        open_t = [t["text"] for t in d["tasks"] if not t.get("done")]
        if not open_t:
            return dict(message=None, reply="Antrean misi kosong.", note="queue read")
        return dict(message=None, reply="Antrean misi:\n" + "\n".join(f"- {t}" for t in open_t), note=f"queue read ({len(open_t)})")

    if cmd == "background":
        if not arg:
            return dict(message=None, reply="Beri saya misi.", note="background empty")
        if runner is None:
            return dict(message=None, reply="Misi background tidak tersedia.", note="background unavailable")
        jid = start_background(arg, runner)
        return dict(message=None, reply=f"Misi background Hermes {jid} diluncurkan. Saya lapor saat selesai.", note=f"mission {jid} started: {arg[:50]}")

    return None
