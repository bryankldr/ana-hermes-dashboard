---
name: maxbi
category: software-development
description: Use for Metabase MAXBI questions (dashboards, cards, sadap/BKPH data) or showing MAXBI results on the ANA chart tile.
version: 1.0.0
metadata:
  hermes:
    tags: [maxbi, metabase, dashboard, chart, kph-bwb]
    related_skills: [simoge-business, ana-hud-dashboard]
---

## Source of Truth
Data via MCP server `maxbi` (tools: `list_dashboards`, `search_content`,
`search_dashboards`, `get_dashboard_cards`, `execute_card`, `execute_query`,
`list_databases`). Metabase = `https://bi.kphbwb.web.id`, 3 database MySQL:
`PRODUKSI KPH BWB` (id 9), `KPH BWB Reporting` (id 13), `SANDBOX2 KPHBWB` (id 45).

## When to Use
- Pertanyaan data yang tinggal di Metabase (dashboard Sadap, BKPH, dsb.)
- "tampilkan chart dari metabase/maxbi" → visualisasi via tile existing, BUKAN iframe.

## CRITICAL — Data dari MCP, tampil via tile existingJANGAN bikin panel/endpoint baru. Angka dari MCP `maxbi`, render via
`ana_chart_tool` yang sama dengan skill SIMOGE:

```python
import os, pathlib, sys
cands = []
if os.environ.get("ANA_WORKDIR"):
    cands.append(pathlib.Path(os.environ["ANA_WORKDIR"]) / "profile-dist/skills/software-development/simoge-business/scripts")
cands.append(pathlib.Path.home() / ".hermes/profiles" / os.environ.get("HERMES_PROFILE", "anna")
             / "skills/software-development/simoge-business/scripts")
for c in cands:
    if (c / "ana_chart_tool.py").is_file():
        sys.path.insert(0, str(c)); break
from ana_chart_tool import show_dashboard, show_spatial_chart, hide_spatial_chart

show_dashboard(
    title="Judul dari dashboard/card MAXBI",
    kpis=[{"label": "...", "value": 123, "unit": "...", "tone": "neutral"}],
    charts=[{"type": "bar", "title": "...", "labels": [...], "datasets": [{"label": "...", "data": [...]}]}],
    narration="Satu kalimat ringkas.",
    evidence=[{"statement": "...", "source": "MAXBI", "value": 123}],
    meta={"source": "MAXBI"},
)
```

Aturan:
- `meta={"source": "MAXBI"}` WAJIB di tiap push — penanda asal di arsip/evidence.
- Tipe chart valid: `bar, h_bar, line, stacked_bar, bullet, pareto, waterfall, scatter, doughnut, pie` (di luar itu store menormalisasi ke `bar`).
- Maks 48 label, 6 dataset per chart, 8 KPI.
- Angka HANYA dari hasil MCP (`execute_card`/`execute_query`), jangan karang.
- Tutup tile pakai `hide_spatial_chart()` bila diminta.
- Wajib verifikasi: sesudah push, panggil `get_spatial_chart()` dan pastikan
  `visible: true` + `meta.source == "MAXBI"` — sebutkan keduanya di jawaban.
  Tanpa verifikasi ini, display dianggap BELUM terjadi.
- `execute_query` (SQL native) hanya bila perlu agregat yang tak ada card-nya; utamakan card/dashboard yang sudah ada agar konsisten dengan definisi bisnis di Metabase.

## Jalur deterministik (tanpa MCP, untuk refresh terjadwal)
Dashboard punya proxy server-side `metabase.py` + slash command:
- `/maxbi dashboards` — daftar dashboard · `/maxbi cari <kata>` — cari card
- `/maxbi card <id>` — jalankan card + push ke tile (meta.source MAXBI)
- HTTP: `GET /api/metabase/status|dashboards|card/<id>`, `POST /api/metabase/query {card_id|database_id+sql, title?, push?}`
- Pakai jalur ini bila user minta angka pasti/berulang — jangan lewat LLM reasoning.
