---
name: ana-briefing
description: Use when generating ANA proactive daily briefing.
---
# ANA Briefing

Generate concise morning briefing in Indonesian. Sections:

1. **Project Status** — scan `$PROYEK_ROOT` (default `$HOME/PROYEK_2026/`) for active projects, recent git commits, TODO markers
2. **Vault Updates** — recent notes in `$OBSIDIAN_VAULT_PATH/10 Daily/` (fallback `$HOME/anna_brain/Anna's brain/10 Daily/`) and `20 Fleeting/`
3. **Mission Queue** — open tasks from dashboard state
4. **System** — server status, disk space, pending updates

Format: short bullet points, max 15 lines. Lead with most important. No fluff.

## Workflow
1. `search_files` for TODO/FIXME in PROYEK_2026
2. `read_file` latest daily note
3. `terminal` git log --oneline -5 per project
4. Compose briefing

## Output
Send via chat or save to `10 Daily/YYYY-MM-DD.md` as `## Briefing` section.