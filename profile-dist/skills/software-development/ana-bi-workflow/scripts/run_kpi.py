#!/usr/bin/env python3
"""
ANNA BI Runner — quick CLI wrapper for answer_production.
Usage: python run_kpi.py --tahun 2026 --bulan 2 --periode 1 --mode asisten [--kode_bkph 3121101 ...]
"""
import sys
import json
import argparse
import re
from pathlib import Path

# Anti-hardcode (aturan SKILL simoge-business): resolve relatif terhadap file
# ini — struktur relatif identik di repo (profile-dist/...) maupun terinstal
# (~/.hermes/profiles/anna/...). Env ANA_SIMOGE_SCRIPTS menang bila di-set.
_env_sim = __import__('os').environ.get('ANA_SIMOGE_SCRIPTS', '').strip()
if _env_sim and Path(_env_sim).is_dir():
    SIMOGE_SCRIPTS = Path(_env_sim)
else:
    SIMOGE_SCRIPTS = Path(__file__).resolve().parents[2] / 'simoge-business' / 'scripts'
sys.path.insert(0, str(SIMOGE_SCRIPTS))
sys.path.insert(0, __file__.replace('run_kpi.py', ''))

from ana_kpi import answer_production, answer_production_fuzzy

# Human-readable name replacements for TTS
TTS_REPLACEMENTS = {
    r'\b31211\b': 'KPH Banyuwangi Barat',
    r'\b3121101\b': 'BKPH Licin',
    r'\b3121102\b': 'BKPH Rogojampi',
    r'\b3121103\b': 'BKPH Kalisetail',
    r'\b3121104\b': 'BKPH Glenmore',
    r'\b3121105\b': 'BKPH Kalibaru',
    r'\(KPH Banyuwangi Barat\)': '',
    r'\(31211\)': '',
    r'\(BKPH Licin\)': '',
    r'\(BKPH Rogojampi\)': '',
    r'\(BKPH Kalisetail\)': '',
    r'\(BKPH Glenmore\)': '',
    r'\(BKPH Kalibaru\)': '',
    r'kode_divre|kode_kph|kode_bkph|kode_rph|kode_tpg': '',
    r'scope KPH Banyuwangi Barat —': 'scope KPH Banyuwangi Barat —',
    r'scope KPH Banyuwangi Barat \(\)': 'scope KPH Banyuwangi Barat',
    r'scope BKPH LICIN —': 'scope BKPH Licin —',
    r'scope BKPH GLENMORE —': 'scope BKPH Glenmore —',
    r'scope BKPH KALISETAIL —': 'scope BKPH Kalisetail —',
    r'scope BKPH ROGOJAMPI —': 'scope BKPH Rogojampi —',
    r'scope BKPH KALIBARU —': 'scope BKPH Kalibaru —',
    r'scope BKPH LICIN \.': 'scope BKPH Licin',
    r'scope BKPH GLENMORE \.': 'scope BKPH Glenmore',
    r'scope BKPH KALISETAIL \.': 'scope BKPH Kalisetail',
    r'scope BKPH ROGOJAMPI \.': 'scope BKPH Rogojampi',
    r'scope BKPH KALIBARU \.': 'scope BKPH Kalibaru',
    r'BKPH LICIN': 'BKPH Licin',
    r'BKPH GLENMORE': 'BKPH Glenmore',
    r'BKPH KALISETAIL': 'BKPH Kalisetail',
    r'BKPH ROGOJAMPI': 'BKPH Rogojampi',
    r'BKPH KALIBARU': 'BKPH Kalibaru',
}

def clean_for_tts(text: str) -> str:
    """Replace technical codes with human names for TTS output."""
    result = text
    for pattern, repl in TTS_REPLACEMENTS.items():
        result = re.sub(pattern, repl, result)
    # Clean up double spaces, trailing punctuation artifacts
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'\s*[—\-]\s*$', '', result).strip()
    result = re.sub(r',\s*,', ',', result)
    return result

def main():
    parser = argparse.ArgumentParser(description='ANNA Production KPI Query')
    parser.add_argument('--tahun', type=int, required=True)
    parser.add_argument('--bulan', type=int, required=True, choices=range(1,13))
    parser.add_argument('--periode', type=int, required=True, choices=[1,2])
    parser.add_argument('--mode', choices=['asisten','coding'], default='asisten')
    parser.add_argument('--wilayah_nama', type=str, help='Fuzzy: nama wilayah (Licin, Glenmore, dll)')
    parser.add_argument('--kode_divre', type=str)
    parser.add_argument('--kode_kph', type=str)
    parser.add_argument('--kode_bkph', type=str)
    parser.add_argument('--kode_rph', type=str)
    parser.add_argument('--kode_tpg', type=str)
    parser.add_argument('--output', choices=['short','full','json'], default='short')
    args = parser.parse_args()

    wilayah = {k:v for k,v in vars(args).items() if k.startswith('kode_') and v}
    
    if args.wilayah_nama:
        out = answer_production_fuzzy(args.tahun, args.bulan, args.periode, args.wilayah_nama, args.mode, **wilayah)
    else:
        out = answer_production(args.tahun, args.bulan, args.periode, args.mode, **wilayah)

    if args.output == 'json':
        print(json.dumps(out, default=str, ensure_ascii=False, indent=2))
    elif args.output == 'full':
        print(out['narrative'])
    else:
        # Clean TTS output
        short = out['narrative_short']
        if args.mode == 'asisten':
            short = clean_for_tts(short)
        print(short)

if __name__ == '__main__':
    main()