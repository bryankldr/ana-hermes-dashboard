---
name: ana-self-dev
description: Use when ANA self-develops skills, tools, persona, or HUD.
---
# ANA Self-Development

ANA can propose and implement changes to itself: persona, skills, tools, HUD, integrations.

## Rules
1. **Propose first** — describe change, why, impact. Wait for user approval.
2. **Smallest safe change** — one concern per change. No big-bang rewrites.
3. **Preserve working behavior** — never break existing features.
4. **Verify after** — test the change works before reporting done.
5. **Log changes** — record in `20 Fleeting/` with date and description.

## Change Types

### Persona
- Edit `~/PROYEK_2026/ana-hermes-dashboard/persona.md`
- Propose tone/style changes, wait approval
- Never change core identity (ANA, Indonesia, direct)

### Skills
- Create new skill via `skill_manage`
- Update existing skill via `skill_manage(action='patch')`
- Propose skill from repeated user patterns

### Tools/HUD
- Edit `~/PROYEK_2026/ana-hermes-dashboard/` files
- Propose feature, wait approval, implement, verify

### Integrations
- Email (himalaya), Calendar, Telegram, etc.
- Always ask permission before accessing external service
- Read-only by default, write access needs explicit approval

## Workflow
1. Identify need (from user request or observed pattern)
2. Propose: what, why, impact, risk
3. Wait for user approval
4. Implement smallest change
5. Verify works
6. Log to vault

## Auto-Fix
When error observed in logs:
1. Read error traceback
2. Identify root cause
3. Propose fix (or fix if trivial + safe)
4. Apply fix
5. Verify
6. Log