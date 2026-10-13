# ANNA BI Workflow — Quick Reference Card

## One-Liner Usage (execute_code)

```python
# Production KPI — short (TTS). Tanpa hardcode path (aturan SKILL):
import os, sys
from pathlib import Path
_cands = [Path.home() / '.hermes/profiles/anna/skills/software-development/simoge-business/scripts']
if os.environ.get('ANA_WORKDIR'):
    _cands.append(Path(os.environ['ANA_WORKDIR']) / 'profile-dist/skills/software-development/simoge-business/scripts')
for _p in _cands:
    if (_p / 'ana_kpi.py').exists():
        sys.path.insert(0, str(_p))
        break
from run_kpi import main
# ... or just call answer_production directly
```

```python
# Direct function call (recommended for agent) — pola path sama seperti di atas
from ana_kpi import answer_production

out = answer_production(tahun=2026, bulan=2, periode=1, mode='asisten')
print(out['narrative_short'])  # TTS
print(out['narrative'])        # Full 6-section
```

## CLI Wrapper (from skill dir)

```bash
cd ~/.hermes/profiles/anna/skills/software-development/ana-bi-workflow/scripts
python run_kpi.py --tahun 2026 --bulan 2 --periode 1 --mode asisten
python run_kpi.py --tahun 2026 --bulan 3 --periode 2 --mode coding --output json
python run_kpi.py --tahun 2026 --bulan 2 --periode 1 --wilayah_nama "Licin" --mode asisten
python run_kpi.py --tahun 2026 --bulan 2 --periode 1 --kode_bkph 3121101 --mode asisten
# Bila skill belum diinstal via hermes (mode repo): cd "$ANA_WORKDIR/profile-dist/skills/software-development/ana-bi-workflow/scripts" dulu.
```

## Parameters

| Arg | Required | Values |
|---|---|---|
| `--tahun` | Yes | 2025, 2026, ... |
| `--bulan` | Yes | 1-12 |
| `--periode` | Yes | 1 (P1), 2 (P2) |
| `--mode` | No | `asisten` (short), `coding` (full) |
| `--wilayah_nama` | No | "Licin", "Glenmore", "Kalisetail", "Rogojampi", "Kalibaru" |
| `--kode_bkph` | No | 3121101, 3121104, ... |
| `--output` | No | `short`, `full`, `json` |

## Output Modes

- **asisten** → 1-2 sentences, TTS-ready
- **coding** → Full 6-section narrative + KPI object with evidence, limitations, sources

## Chart / Visualization

```python
from ana_chart_tool import show_spatial_chart
show_spatial_chart(type="bar", title="Produksi per BKPH", labels=["LICIN","GLENMORE"], datasets=[{"label":"Ton","data":[118,95]}])
```

```python
from simoge_business import call_simoge_packet, show_dashboard
# or use call_simoge_tool("show_on_map", {...})
```

## Diagnostic Workflow (why/how)

FACT → GAP → DIAGNOSIS → LOCATION → IMPACT → ACTION

Chart sequence: Target vs Realisasi → Plan vs Actual → Petak/Andil shortfall → Penyadap → Spasial → Contribution → Limitations

## Files in This Skill

```
ana-bi-workflow/
├── SKILL.md              # Full workflow documentation
├── references/           # Copied from simoge-business
│   ├── business_context.md
│   ├── business_rules.md
│   ├── chart_guide.md
│   ├── chart_transport.md
│   ├── map_ops.md
│   ├── production_kpi.md
│   ├── schema.md
│   ├── templates.md
│   └── troubleshooting.md
└── scripts/
    ├── ana_kpi.py        # Core KPI module
    ├── ana_simoge_tool.py # Simoge tool wrapper
    └── run_kpi.py        # CLI wrapper (this file)
```

## Key Principles

1. **No direct SQL** — only `answer_production` → `call_simoge_tool` (named templates)
2. **Evidence trace** — every number in `kpi.evidence`
3. **Missing ≠ zero** — limitations array documents gaps
4. **Correlation only** — "bergerak bersamaan", never "menyebabkan"
5. **Alias wilayah first** — resolve "Licin" → BKPH=3121101 before query