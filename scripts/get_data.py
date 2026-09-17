"""Download the connectome data files (not stored in git; ~120 MB total).

Usage: python scripts/get_data.py
"""

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent

FILES = [
    # (url, destination, expected size in bytes)
    ('https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/2023_03_23_connectivity_630_final.parquet',
     'connectivity_630.parquet', 86_630_944),
    ('https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/2023_03_23_completeness_630_final.csv',
     '2023_03_23_completeness_630_final.csv', 3_057_611),
    ('https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/supplemental_files/Supplemental_file1_neuron_annotations.tsv',
     'neuron_annotations.tsv', 31_718_505),
]


def fetch(url, dst, expected):
    path = ROOT / dst
    if path.exists() and path.stat().st_size == expected:
        print(f'ok       {dst}')
        return
    for attempt in range(5):
        print(f'fetching {dst} (attempt {attempt + 1}) ...', flush=True)
        try:
            urllib.request.urlretrieve(url, path)
        except OSError as e:
            print(f'  error: {e}')
            continue
        if path.stat().st_size == expected:
            print(f'ok       {dst} ({expected / 1e6:.1f} MB)')
            return
        print(f'  truncated ({path.stat().st_size} / {expected} bytes), retrying')
    sys.exit(f'failed to download {dst}')


for url, dst, size in FILES:
    fetch(url, dst, size)
print('all data ready')
