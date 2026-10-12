---
name: zk-vault-ops
category: note-taking
description: 'Use when managing Obsidian ZK vaults and Hermes sync.'
version: 1.0.0
author: bryankldr
license: MIT
metadata:
  hermes:
    tags: [Obsidian, Zettelkasten, Vault, Hermes]
    related_skills: [obsidian]
---

# ZK Vault Ops

Umbrella for Obsidian + Hermes workflows with `anna` vault (`$OBSIDIAN_VAULT_PATH`, default `$HOME/MAX-research/vaults/anna`) as canonical ZK via `OBSIDIAN_VAULT_PATH`.

## When to Use

- User says "integrasikan obsidian", "setup vault ZK", "vault terdeteksi N", or names multiple `~/.../Vault` paths.
- Syncing Hermes `state.db` sessions into Fleeting notes or building a sessions index.
- Consolidating Hermes profiles (legacy `default`/`ana-agent`) to single canonical profile `anna`.
- Creating or maintaining the `obsidian-daily-sync` cron job for vault maintenance.

## 1. Multi-vault discovery → single default

- Discover all candidates (`search_files target='files'` over each vault root + `terminal ls` for directory listing) before choosing default; do not assume one vault.
- Resolve `OBSIDIAN_VAULT_PATH` from `${HERMES_HOME:-~/.hermes}/.env` (concrete absolute path, no shell variable). File tools do not expand env vars.
- After writing `OBSIDIAN_VAULT_PATH` to `.env` (`echo 'OBSIDIAN_VAULT_PATH=/path' >> .env`), restart gateway `hermes gateway restart` and verify `grep OBSIDIAN_VAULT_PATH .env` + `hermes gateway status`. Desktop app needs no restart.

## 2. ZK initialization

- Directories: `00 Inbox`, `10 Daily`, `20 Fleeting`, `30 Literature`, `40 Permanent`, `50 Projects`, `99 Templates`, `99 Attachments`.
- Templates `99 Templates/Daily.md`, `Fleeting.md`, `Literature.md`, `Permanent.md` with frontmatter (`type`, `tags`, `created`).
- Wire core plugins: `daily-notes.json` (`folder: 10 Daily`, `format: YYYY-MM-DD`, `template: 99 Templates/Daily.md`), `templates.json` (`folder: 99 Templates`), `app.json` (`attachmentFolderPath: 99 Attachments`).
- Seed `00 Inbox/_Dashboard.md`, `00 Inbox/_Inbox.md`, today's `10 Daily/YYYY-MM-DD.md`.
- Full file contents and plugin JSON: `references/zk-setup.md`.

## 3. Project MOC — link, don't move

- Keep projects on disk (`$HOME/<project>`, e.g. `$HOME/ana-hermes-dashboard`); create MOC in `50 Projects/<project>.md` with frontmatter `path:` and wikilinks. Never move project files into vault.
- Capture stack, structure, and standing decisions (e.g., drum nomor, baseUrl single source) in MOC.

## 4. read_file dedup pitfall

- `read_file` deduplicates an unchanged file within the same conversation turn (`status: unchanged`, no content). After shell patching (`terminal`/`python3`), verify with `terminal cat` or a fresh `read_file` in a new turn — do not trust a second immediate `read_file`.

## 5. Bulk session export → fleeting

- Query SQLite directly (`~/.hermes/state.db` for default, `~/.hermes/profiles/<name>/state.db` for others) — `session_search` paginates and is profile-scoped.
- Group sessions by topic (not 1:1) into ~10–12 fleeting notes; skip 0-msg sessions; record `session_id` in frontmatter `source:`; build master `00 Inbox/_Sessions Index.md` table.
- Query and grouping pattern: `references/session-export.md`.

## 6. Single-profile consolidation

- When user wants one canonical profile (`default` as ANA), export secondary first: `hermes profile export <name> --output /tmp/<name>-backup.zip.tar.gz` (tool appends `.tar.gz`), copy to `~/<name>-backup-*.tar.gz`, verify `tar tzf`.
- Then delete: `echo "<name>" | hermes profile delete <name>` or `hermes profile delete -y <name>`. Ensure all sessions already materialized as fleeting notes.
- Gateway is multiplexed — deleting secondary does not stop default gateway. Steps: `references/profile-merge.md`.

## 7. Cron daily sync

- Schedule `cronjob_manage action=create schedule="0 22 * * *" skills=[obsidian]` with self-contained prompt: check `OBSIDIAN_VAULT_PATH`, ensure today's daily from template, scan `_Inbox.md`, count Fleeting/Permanent/Projects, report git status.
- Use `deliver: local` unless user asks for Telegram; verify with manual `run` and `read_file` cron output.

## 8. ANA HUD over the same Hermes profile (fork of JARVIS)

- ANA (`~/ana-hermes-dashboard`, fork of `Itsme23476/jarvis-hermes-dashboard`) is a face on the active Hermes profile — not a second agent. It inherits tools, skills, memory, browser automation, MCP servers, and third-party integrations from the active profile.
- `HERMES_PROFILE` in `~/ana-hermes-dashboard/.env` must be the profile **ID** (`anna`), not the display name (`ANA`). Using the display name makes every `/api/run` fail with `Profile 'ANA' does not exist` — set `HERMES_PROFILE=anna` and restart `python3 server.py`.
- `persona.md` is read per-request; editing `## Bahasa` needs no restart. Slash replies (`/commands`, `/status`, `/tools`, `/personality`, `/goal`, etc.) are hardcoded in `commands.py` and bypass the LLM — patch `commands.py` strings to Indonesian separately or voice clicks stay English despite persona.
- Rebrand JARVIS→ANA: `mv ~/jarvis-hermes-dashboard ~/ana-hermes-dashboard`, replace `JARVIS/Jarvis/jarvis` → `ANA/Ana/ana` in `server.py`, `runtime.py`, `commands.py`, `voice.py`, `ui/index.html`, `ui/app.js`, `install.sh`, `start.sh`, `README.md`, `persona.md`; rename env vars `JARVIS_*` → `ANA_*` (`ANA_PORT=8730`, `ANA_TOKEN`, header `X-Ana-Token`, boundary `----ana`), title `ANA · Hermes Mission Control`, delete `__pycache__`, `grep -r JARVIS` must be 0.
- Chat extension (preserve voice): add `💬 Chat` button beside `VOICE` in `ui/index.html` missionbar and `chatbar` (`#chatInput`+`#chatSend`) inside `RESPONSE` panel footer; wire `sendFromChat()`/`autoChatSize()` in `ui/app.js` to same `POST /api/run` with `X-Ana-Token` — same Hermes stream/TTS, second input surface only. Style `.chatbar`/`#chatInput`/`.ctl.chat` in `ui/styles.css`. Refresh browser, no server restart needed for static assets.
- Preserve private `.env` on clone/update (`cp .env.example .env` only if missing); never print, commit, or log `ELEVENLABS_API_KEY`. Port `127.0.0.1:${ANA_PORT:-8730}`, `ANA_OPEN=1` auto-opens browser.
- Full sequence: `references/jarvis-hud.md` (clone → .env → persona → start → verify → NDJSON → rebrand → chat).

## References

- `references/zk-setup.md` — directories, templates, plugin configs, seed files.
- `references/session-export.md` — SQLite query, topic grouping, index table.
- `references/profile-merge.md` — export → verify → delete sequence.
