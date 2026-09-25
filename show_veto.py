import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
d = json.loads((Path(__file__).parent / 'validate_veto.json').read_text(encoding='utf-8'))
print('lesion:', ' + '.join(d['answer']), f"({len(d['lesion_ids'])} neurons)")
for r in d['results']:
    print(f"{r['label']:<26} {r['mn9_hz']:7.1f} Hz   silenced={r['n_silenced']}")
