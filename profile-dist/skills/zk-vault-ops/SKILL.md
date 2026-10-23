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

Umbrella for Obsidian + Hermes workflows with `anna` vault (`$OBSIDIAN_VAULT_PATH` fallback `$HOME/anna_brain/Anna's brain`) as canonical ZK via `OBSIDIAN_VAULT_PATH`.

## When to Use

- User says "integrasikan obsidian", "setup vault ZK", "vault terdeteksi N", or names multiple `~/.../Vault` paths.
- Syncing Hermes `state.db` sessions into Fleeting notes or building a sessions index.
- Consolidating Hermes profiles (`default` vs `ana-agent`) to a single canonical profile.
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

- Keep projects on disk (`/home/.../PROYEK_2026/<project>`); create MOC in `50 Projects/<project>.md` with frontmatter `path:` and wikilinks. Never move project files into vault.
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

## 9b. Known post-import quirks
- Root `ANNA-KNOWLEDGE/{index.md,log.md}` never get collected (`import ... total_files` = vault md count − 2) — only `SCHEMA.md` lands as page `anna-knowledge/schema`. Harmless stubs; do not chase.
- Fact vectors are pinned to a different model than the chunk provider: `gbrain embed --facts --stale ... --yes --max-cost-usd 0` fails `internal_error: Embedding configuration differs from the database; finish the reviewed model migration first` (doctor shows the fact expected as `voyage:voyage-4 (1024d)` while chunks are `ollama:mxbai-embed-large`). Expected; needs a user-approved model migration or a voyage key — never unattended. Page/chunk embeddings stay complete (`get_stats`: embedded_count == chunk_count).

## 10. Cron daily sync

- Schedule `cronjob_manage action=create schedule="0 22 * * *" skills=[obsidian]` with self-contained prompt: check `OBSIDIAN_VAULT_PATH`, ensure today's daily from template, scan `_Inbox.md`, count Fleeting/Permanent/Projects, report git status.
- Use `deliver: local` unless user asks for Telegram; verify with manual `run` and `read_file` cron output.

## 8. ANA HUD over the same Hermes profile (fork of JARVIS)

- ANA (`~/ana-hermes-dashboard`, fork of `Itsme23476/jarvis-hermes-dashboard`) is a face on the active Hermes profile — not a second agent. It inherits tools, skills, memory, browser automation, MCP servers, and third-party integrations from the active profile.
- `HERMES_PROFILE` in `~/ana-hermes-dashboard/.env` must be the profile **ID** (`default`), not the display name (`ANA`). Using the display name makes every `/api/run` fail with `Profile 'ana' does not exist` — set `HERMES_PROFILE=default` and restart `python3 server.py`.
- `persona.md` is read per-request; editing `## Bahasa` needs no restart. Slash replies (`/commands`, `/status`, `/tools`, `/personality`, `/goal`, etc.) are hardcoded in `commands.py` and bypass the LLM — patch `commands.py` strings to Indonesian separately or voice clicks stay English despite persona.
- Rebrand JARVIS→ANA: `mv ~/jarvis-hermes-dashboard ~/ana-hermes-dashboard`, replace `JARVIS/Jarvis/jarvis` → `ANA/Ana/ana` in `server.py`, `runtime.py`, `commands.py`, `voice.py`, `ui/index.html`, `ui/app.js`, `install.sh`, `start.sh`, `README.md`, `persona.md`; rename env vars `JARVIS_*` → `ANA_*` (`ANA_PORT=8730`, `ANA_TOKEN`, header `X-Ana-Token`, boundary `----ana`), title `ANA · Hermes Mission Control`, delete `__pycache__`, `grep -r JARVIS` must be 0.
- Chat extension (preserve voice): add `💬 Chat` button beside `VOICE` in `ui/index.html` missionbar and `chatbar` (`#chatInput`+`#chatSend`) inside `RESPONSE` panel footer; wire `sendFromChat()`/`autoChatSize()` in `ui/app.js` to same `POST /api/run` with `X-Ana-Token` — same Hermes stream/TTS, second input surface only. Style `.chatbar`/`#chatInput`/`.ctl.chat` in `ui/styles.css`. Refresh browser, no server restart needed for static assets.
- Preserve private `.env` on clone/update (`cp .env.example .env` only if missing); never print, commit, or log `ELEVENLABS_API_KEY`. Port `127.0.0.1:${ANA_PORT:-8730}`, `ANA_OPEN=1` auto-opens browser.
- Full sequence: `references/jarvis-hud.md` (clone → .env → persona → start → verify → NDJSON → rebrand → chat).

## 9. gbrain brain sync (cron)

- Source `default` lives in `~/.gbrain/content/<brain-id>/default` — a gbrain-owned content dir, **not** a Git checkout, so `mcp__gbrain__sync_brain` always returns `sync_not_applicable`. Do not retry it; catch up with the CLI instead.
- Real sync command: `export PATH="$HOME/.bun/bin:$PATH"; gbrain import /home/bryankldr/ana_journal/ana --source default --brain host --json` (journal vault is the import root; `ana_journal` is not a git repo either).
- Verify after: `mcp__gbrain__get_ingest_log limit=2` (new row `source_type: directory`) and `mcp__gbrain__get_stats` (embedded_count should equal chunk_count). A `missing_embeddings` spike right after import is transient — re-read health; `gbrain embed --stale` reports 0 because import already embedded.
- Health triage: `gbrain doctor --brain host | grep WARN`. Persistent warns on this brain: orphan pages ~33/53 (no_orphans_score 6/15), `schema_pack_consistency` (daily/fleeting/permanent/literature not declared by `gbrain-base-v2`), `backup_coverage` (`not_a_git_repo` — no verified recovery until git init + remote, which would also make sync_brain usable), `cycle_freshness` (never ran `gbrain dream`).

## References

- `references/zk-setup.md` — directories, templates, plugin configs, seed files.
- `references/session-export.md` — SQLite query, topic grouping, index table.
- `references/profile-merge.md` — export → verify → delete sequence.
