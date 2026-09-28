"""
Data sources for the ANA HUD panels.

Everything here is HTTP-free and import-safe: no BaseHTTPRequestHandler, no
response objects. Each function is a plain "collect and return a dict" call so
it can be unit tested without booting a server.

Subprocess calls are all bounded by a timeout and never raise — a panel that
cannot reach git/adb/the vault degrades to an `error` field instead of taking
the dashboard down.
"""
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent


def _run(cmd, cwd=None, timeout=10):
    """Run a command, return stripped stdout-or-stderr. Never raises."""
    try:
        r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return (r.stdout or r.stderr or "").strip()
    except Exception:
        return ""


# ── projects ────────────────────────────────────────────────

def scan_projects(workdir):
    """Scan WORKDIR for git repos, return project cards."""
    workdir = pathlib.Path(workdir).expanduser()
    projects = []
    try:
        for d in sorted(workdir.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            if not (d / ".git").exists():
                continue
            branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=d) or "?"
            last_commit = _run(["git", "log", "-1", "--format=%h %s (%cr)"], cwd=d) or "no commits"
            # A repo with no initial commit prints "fatal: ... does not have any
            # commits yet" — map it to a label, never leak raw stderr to the HUD.
            if "fatal:" in last_commit or "error:" in last_commit.lower():
                last_commit = "git error"
            dirty = _run(["git", "status", "--porcelain"], cwd=d)
            projects.append({
                "name": d.name,
                "path": str(d),
                "branch": branch,
                "last_commit": last_commit,
                "dirty": len([l for l in dirty.splitlines() if l.strip()]) if dirty else 0,
                "dirty_files": dirty.splitlines()[:5] if dirty else [],
            })
    except Exception as e:  # noqa: BLE001
        projects.append({"name": "error", "error": str(e)[:200]})
    return {"projects": projects, "workdir": str(workdir)}


# ── sessions ────────────────────────────────────────────────

def _age_days(la):
    """'3d ago' -> 3. Returns None when the string carries no day count.

    Substring check for the 'd' bucket first, then strip that suffix before
    converting: "1d".isdigit() is False, so a bare isdigit() scan over
    "1d ago" finds no number and every session fell into last_week/older.
    """
    if "d ago" not in la:
        return None
    m = re.match(r"(\d+)\s*d", la.strip())
    return int(m.group(1)) if m else None


def _group_by_age(sessions):
    groups = {"today": [], "yesterday": [], "last_week": [], "older": []}
    for s in sessions:
        la = s["last_active"].lower()
        if "m ago" in la or "h ago" in la or "just now" in la:
            groups["today"].append(s)
            continue
        days = _age_days(la)
        if days == 1:
            groups["yesterday"].append(s)
        elif days is not None and days <= 7:
            groups["last_week"].append(s)
        else:
            groups["older"].append(s)
    return groups


def list_sessions(hermes_base, workdir, valid_session, current):
    """Recent Hermes sessions grouped by age. `current` is the live session id."""
    empty = {"groups": {"today": [], "yesterday": [], "last_week": [], "older": []},
             "current": current}
    try:
        out = _run(hermes_base + ["sessions", "list"], cwd=workdir, timeout=15)
        sessions = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith(("Title", "─")):
                continue
            parts = line.split()
            # last_active is a relative string like "13m ago" — parse by
            # substring, never int(): int("13m") raises ValueError.
            if len(parts) >= 4 and valid_session(parts[-1]):
                sessions.append({
                    "id": parts[-1],
                    "title": " ".join(parts[:-3]) or "—",
                    "last_active": parts[-3] + " " + parts[-2],
                })
            if len(sessions) >= 50:
                break
        return {"groups": _group_by_age(sessions), "current": current}
    except Exception as e:  # noqa: BLE001
        return {**empty, "error": str(e)[:200]}


# ── vault + briefing ────────────────────────────────────────

def _vault_path():
    return os.environ.get("OBSIDIAN_VAULT_PATH", "").strip()


def load_briefing():
    """Read the latest daily note from the vault, extract its Briefing section."""
    vault = _vault_path()
    if not vault:
        return {"briefing": "", "source": "OBSIDIAN_VAULT_PATH not set", "date": ""}
    daily = pathlib.Path(vault) / "10 Daily"
    notes = sorted(daily.glob("*.md"), reverse=True) if daily.exists() else []
    if not notes:
        # Distinguish "vault configured but no daily notes yet" from
        # "the 10 Daily folder is missing entirely" — the panel shows the
        # source, so a bogus placeholder path would be a visible lie.
        return {"briefing": "", "source": str(daily), "date": ""}
    latest = notes[0]
    text = latest.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"##\s*Briefing\s*\n(.*?)(?=\n##\s|\Z)", text, re.S | re.I)
    return {"briefing": m.group(1).strip() if m else "",
            "source": str(latest), "date": latest.stem}


def vault_status():
    """Vault + skill inventory for the HUD vault panel."""
    try:
        skill_note = ROOT / "SKILL" / "skill_note.md"
        preview = ""
        if skill_note.exists():
            preview = skill_note.read_text(encoding="utf-8", errors="replace")[:800]
        vault, daily_count = _vault_path(), 0
        if vault:
            daily = pathlib.Path(vault) / "10 Daily"
            if daily.exists():
                daily_count = len(list(daily.glob("*.md")))
        return {"skill_note_exists": skill_note.exists(), "skill_preview": preview,
                "daily_count": daily_count, "vault": vault}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}


# ── android emulator ────────────────────────────────────────

ADB = "adb"
SERIAL = "emulator-5554"
AVD_NAME = "Pixel_9"


def _emulator_bin():
    return str(pathlib.Path.home() / "Android" / "Sdk" / "emulator" / "emulator")


def avd_status():
    """Emulator AVD list + adb device/boot state."""
    try:
        adb_out = _run([ADB, "devices"], timeout=5)
        device, boot = "offline", ""
        if SERIAL in adb_out:
            if "device" in adb_out:
                device = "device"
            boot = _run([ADB, "-s", SERIAL, "shell", "getprop", "sys.boot_completed"], timeout=5)
        return {"avds": _run([_emulator_bin(), "-list-avds"], timeout=8),
                "adb": adb_out[:500], "device": device, "boot_completed": boot}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}


def avd_action(action):
    """start|stop the AVD. Returns (ok, message) for the caller to serialise."""
    action = (action or "").strip().lower()
    if action not in ("start", "stop"):
        return None, {"error": "action must be start|stop"}
    if action == "stop":
        try:
            subprocess.run([ADB, "-s", SERIAL, "emu", "kill"],
                           text=True, timeout=10, capture_output=True)
        except Exception as e:  # noqa: BLE001
            return False, {"error": str(e)[:200]}
        return True, {"msg": "AVD stop signal sent"}
    out = _run([ADB, "devices"], timeout=5)
    if SERIAL in out and "device" in out:
        return True, {"msg": f"AVD already running ({SERIAL} device)"}
    subprocess.Popen([_emulator_bin(), "-avd", AVD_NAME, "-gpu", "host", "-no-snapshot-load"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    return True, {"msg": f"AVD {AVD_NAME} starting..."}
