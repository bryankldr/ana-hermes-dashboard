"""
Self-check for services.py. Run: python3 test_services.py

No framework, no mocks: the pure functions are asserted directly and the two
subprocess-backed ones are smoke-tested against real git/the vault, tolerating
"not present" so this passes on a bare machine too.
"""
import os
import pathlib
import sys
import tempfile

import services

_fail = 0


def check(label, got, want):
    global _fail
    if got == want:
        print(f"  ok   {label}")
    else:
        _fail += 1
        print(f"  FAIL {label}: got {got!r}, want {want!r}")


# ── session age grouping ────────────────────────────────────
# The bug this guards: `hermes sessions list` prints "13m ago" / "2h ago" /
# "3d ago". int("13m") raises ValueError, which silently dumped every session
# into "older". Grouping must use substring matching.
print("group_by_age")
g = services._group_by_age([
    {"id": "a", "last_active": "just now"},
    {"id": "b", "last_active": "13m ago"},
    {"id": "c", "last_active": "2h ago"},
    {"id": "d", "last_active": "1d ago"},
    {"id": "e", "last_active": "3d ago"},
    {"id": "f", "last_active": "9d ago"},
    {"id": "g", "last_active": "2w ago"},
])
check("just now -> today", g["today"][0]["id"], "a")
check("13m -> today", g["today"][1]["id"], "b")
check("2h -> today", g["today"][2]["id"], "c")
check("1d -> yesterday", [s["id"] for s in g["yesterday"]], ["d"])
check("3d -> last_week", [s["id"] for s in g["last_week"]], ["e"])
check("9d + 2w both -> older", [s["id"] for s in g["older"]], ["f", "g"])

# ── briefing extraction ─────────────────────────────────────
print("load_briefing")
with tempfile.TemporaryDirectory() as td:
    daily = pathlib.Path(td) / "10 Daily"
    daily.mkdir()
    (daily / "2026-09-28.md").write_text("## Briefing\nolder note\n", encoding="utf-8")
    (daily / "2026-09-29.md").write_text(
        "## Log\njunk\n\n## Briefing\n- titik satu\n- titik dua\n\n## Next\nnope\n",
        encoding="utf-8")
    os.environ["OBSIDIAN_VAULT_PATH"] = td
    b = services.load_briefing()
    check("picks latest note", b["date"], "2026-09-29")
    check("stops at next heading", b["briefing"], "- titik satu\n- titik dua")

    (daily / "2026-09-30.md").write_text("# no briefing section\n", encoding="utf-8")
    check("missing section -> empty", services.load_briefing()["briefing"], "")

os.environ["OBSIDIAN_VAULT_PATH"] = "/definitely/not/here"
missing = services.load_briefing()
check("missing vault -> empty briefing", missing["briefing"], "")
check("missing vault -> echoes 10 Daily path", missing["source"], "/definitely/not/here/10 Daily")
check("missing vault -> no date", missing["date"], "")

os.environ["OBSIDIAN_VAULT_PATH"] = ""
check("unset vault -> empty briefing", services.load_briefing()["briefing"], "")
check("unset vault -> reason", services.load_briefing()["source"],
      "OBSIDIAN_VAULT_PATH not set")
os.environ.setdefault("OBSIDIAN_VAULT_PATH", os.path.expanduser("~/MAX-research/vaults/anna"))

# ── vault_status ────────────────────────────────────────────
print("vault_status")
v = services.vault_status()
check("returns a dict", isinstance(v, dict), True)
check("no exception key on happy path", "error" in v, False)
check("reports skill_note presence", isinstance(v["skill_note_exists"], bool), True)

# ── avd ─────────────────────────────────────────────────────
print("avd")
ok, body = services.avd_action("ngawur")
check("bad action -> ok is None", ok, None)
check("bad action -> 400 message", body, {"error": "action must be start|stop"})
check("avd_status is a dict", isinstance(services.avd_status(), dict), True)

# ── projects ────────────────────────────────────────────────
print("scan_projects")
with tempfile.TemporaryDirectory() as td:
    r = services.scan_projects(td)
    check("empty dir -> no projects", r["projects"], [])
    check("echoes workdir", r["workdir"], td)
    # a non-git subdir must be ignored
    (pathlib.Path(td) / "bukan-git").mkdir()
    check("non-git dir skipped", services.scan_projects(td)["projects"], [])

    repo = pathlib.Path(td) / "repo-git"
    (repo / ".git").mkdir(parents=True)
    p = services.scan_projects(td)["projects"][0]
    check("finds repo", p["name"], "repo-git")
    # A repo with no commits: git log prints "fatal: ... no commits yet".
    # The HUD must show a label, never the raw stderr.
    check("no-commit repo -> 'git error'", p["last_commit"], "git error")
    check("no raw fatal: leaked", "fatal:" in p["last_commit"], False)

print()
if _fail:
    print(f"FAILED: {_fail} check(s)")
    sys.exit(1)
print("all checks passed")
