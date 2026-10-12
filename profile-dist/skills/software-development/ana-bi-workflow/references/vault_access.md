# Vault Access Best Practice (Anna's brain)

## Principle
**Local vault = direct file access.** No REST API, no connector needed. Vault at:
```
~/MAX-research/vaults/anna/
```

## Tools to Use
| Task | Tool | Example |
|---|---|---|
| Find files by name | `search_files(target='files', pattern='*.md', path='~/MAX-research/vaults/anna')` | Cari file `*pembaharuan*.md` |
| Search content | `search_files(target='content', pattern='pembaharuan', path='~/MAX-research/vaults/anna')` | Cari kata 'pembaharuan' di semua .md |
| Read file | `read_file(path='~/MAX-research/vaults/anna/ANNA-KNOWLEDGE/...')` | Baca konten spesifik |
| List structure | `terminal('find ~/MAX-research/vaults/anna -type f -name "*.md" | head -50')` | Overview struktur |
| Grep with context | `terminal("grep -n -A 3 -B 3 'pembaharuan' ~/MAX-research/vaults/anna/ANNA-KNOWLEDGE/raw/articles/skema-database-kph-bwb-sandbox2.md")` | Cari dengan konteks |

## Search Strategy
1. **Start broad** — `search_files(target='content', pattern='keyword', path=vault_root)`
2. **Narrow** — filter by subfolder (`entities/`, `concepts/`, `queries/`, `raw/articles/`)
3. **Read** — `read_file` on matched files
4. **Cross-ref** — vault uses `[[wikilinks]]`, follow references

## Vault Structure (Anna's brain)
```
Anna's brain/
├── ANNA-KNOWLEDGE/
│   ├── entities/          # aktivitas-penyadapan, penyadap, petak, andil, TPG, KPH...
│   ├── concepts/          # medan-aktivitas, operasi-dashboard, tool-bisnis-anna
│   ├── queries/           # intent-ke-template-peta, skala-multi-divre, laporan templates
│   ├── raw/articles/      # simoge-business-ontology, skema-database-kph-bwb-sandbox2
│   └── ...
├── 10 Daily/              # Daily notes (2026-10-03.md, etc.)
└── SIMOGE Business Knowledge & Ontology.md  # Master overview
```

## Key Files for Business Context
| File | Purpose |
|---|---|
| `ANNA-KNOWLEDGE/raw/articles/skema-database-kph-bwb-sandbox2.md` | **Schema DB** — kolom tabel, flags (quare, semprot_cas, budaya_bersih, kerok, naik_batok), pembaharuan_ke |
| `ANNA-KNOWLEDGE/entities/aktivitas-penyadapan.md` | Entity definisi aktivitas penyadapan |
| `ANNA-KNOWLEDGE/concepts/medan-aktivitas.md` | Medan aktivitas, rantai verifikasi |
| `ANNA-KNOWLEDGE/raw/articles/simoge-business-ontology.md` | Ontology lengkap bisnis |
| `SIMOGE Business Knowledge & Ontology.md` | Master summary |

## Anti-Pattern (JANGAN)
- ❌ Coba pakai Obsidian REST API connector (perlu plugin, setup, auth)
- ❌ Asumsi skill `obsidian` bisa akses tanpa connector
- ❌ Manual `terminal('cat ...')` tanpa search dulu

## Best Practice Pattern
```python
# 1. Search
matches = search_files(pattern='pembaharuan', target='content', path=vault_root)
# 2. Read top matches
for m in matches[:3]:
    content = read_file(path=m['path'])
    # extract info
# 3. Update memory/skill with vault-confirmed fact
```

## Integration with ANNA Wiki (LLM Wiki)
- **Vault (Anna's brain)** = **source of truth** (authoritative, file-based)
- **ANNA Wiki (system prompt)** = **LLM Wiki** — semantic index/cheat sheet, already loaded in context, zero token cost for lookup
- **Skill references** = copied snippets for offline use

**Token efficiency rule:**
- Lookup di ANNA Wiki (system prompt) = **FREE** (already in context)
- Search vault via `search_files`/`read_file` = **tool call cost only**, no LLM tokens for reading
- Hanya kirim ke LLM: **extracted fact/insight** (1-2 kalimat), bukan full file content

**Workflow optimal:**
```
1. Check ANNA Wiki first (system prompt) — instant, zero token
2. If not found / need detail → search vault (search_files) — tool call only
3. Read specific file (read_file) — tool call only  
4. Extract → update ANNA Wiki / memory / skill — minimal token
```
```