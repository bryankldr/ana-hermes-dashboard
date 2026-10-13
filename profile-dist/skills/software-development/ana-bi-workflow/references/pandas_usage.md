# Pandas Engine Usage Guide

## Quick Reference

### 1. Basic Template Query (no pandas)
```python
from ana_kpi import answer_production
answer_production(tahun=2026, bulan=2, periode=1, mode='asisten')
```

### 2. Template → Pandas Analysis
```python
from ana_pandas_engine import analyze_template

# Group by BKPH, sum produksi, top 5
analyze_template('produksi_breakdown_bkph', 
    {'tahun': 2026, 'bulan': 2, 'periode': 1},
    operations=[
        {'op': 'groupby_agg', 'by': 'bkph', 'metrics': [{'col': 'produksi_kg', 'agg': 'sum'}]},
        {'op': 'top_n', 'n': 5}
    ])
```

### 3. Available Operations
| Op | Params | Use Case |
|---|---|---|
| `sort` | `by`, `ascending` | Urutkan rows |
| `filter` | `col`, `op` (==, !=, >, <, >=, <=, in, not_in, contains), `value` | Filter rows |
| `groupby_agg` | `by`, `metrics`[{col, agg}] | Agregasi per group (sum, mean, count, min, max, std) |
| `pivot` | `index`, `columns`, `values`, `aggfunc` | Pivot table |
| `top_n` / `bottom_n` | `n`, `by` | Top/bottom N |
| `pct_change` | `col`, `periods` | Persentase perubahan |
| `rolling` | `col`, `window`, `agg` | Rolling window |
| `stats_summary` | `cols`[] | Deskriptif statistik |
| `cross_tab` | `index`, `columns`, `values`, `aggfunc` | Cross tabulation |
| `growth_gap` | `current_col`, `prior_col`, `label_col` | Growth + gap analysis |
| `contribution` | `value_col`, `group_col`, `total_col` | % kontribusi per group |
| `rank` | `col`, `method`, `ascending` | Ranking |
| `zscore` | `col` | Z-score outlier |
| `outlier_iqr` | `col`, `multiplier` | IQR outlier |
| `correlation` | `cols`[], `method` | Korelasi matrix |

### 4. Predefined Templates (di ana_pandas_engine.py)
- `petak_status` — status petak per wilayah
- `produksi_breakdown_bkph` — breakdown produksi per BKPH
- `produksi_trend` — trend bulanan
- `penyadap_per_tpg` — penyadap per TPG

### 5. CLI Test
```bash
cd ~/.hermes/profiles/anna/skills/software-development/ana-bi-workflow/scripts
python3 -c "
from ana_pandas_engine import analyze_template
import json
print(json.dumps(analyze_template('produksi_breakdown_bkph', {'tahun':2026,'bulan':2,'periode':1}, 
    operations=[{'op':'groupby_agg','by':'bkph','metrics':[{'col':'produksi_kg','agg':'sum'}]}, {'op':'top_n','n':5}]), ensure_ascii=False, indent=2))
"
```

### 6. Integration Pattern (Business Question → Answer)
```
User Question
    ↓
Parse: metric, filter, grain, comparison
    ↓
Select template (call_simoge_packet for KPI)
    ↓
If need deeper analysis → analyze_template + operations
    ↓
Format: TTS (3-5 kalimat) OR coding mode (chart + full narrative)
```

### 7. Key Principle
- **Template does SQL** (server-side filter, join, aggregate)
- **Pandas does post-processing** (sort, pivot, stats, ranking)
- **Never raw SQL** — always via named template
- **Payload minimal** — packet/KPI only, not 50K rows
```