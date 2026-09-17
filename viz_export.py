"""Export visualization data for the browser-based 3D spike viewer.

Produces viz_data.json with:
  - backdrop: downsampled positions of ~40k neurons (static brain shape)
  - neurons:  positions + metadata of every neuron active in the chosen trial
  - spikes:   (time, neuron index) pairs of one representative trial

Positions are FAFB space in micrometres (nm / 1000, rounded to int).
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent

SUGAR_GRNS = {
    720575940624963786, 720575940630233916, 720575940637568838,
    720575940638202345, 720575940617000768, 720575940630797113,
    720575940632889389, 720575940621754367, 720575940621502051,
    720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543,
    720575940632425919, 720575940633143833, 720575940612670570,
    720575940628853239, 720575940629176663, 720575940611875570,
}
MN9 = 720575940660219265

spikes_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / 'results' / 'sugarR_150Hz_viz.parquet'
trial = int(sys.argv[2]) if len(sys.argv) > 2 else 0

ann = pd.read_csv(HERE / 'neuron_annotations.tsv', sep='\t',
                  usecols=['root_id', 'pos_x', 'pos_y', 'pos_z', 'super_class', 'cell_type', 'top_nt', 'side'])
ann = ann.dropna(subset=['pos_x']).drop_duplicates('root_id').set_index('root_id')

spk = pd.read_parquet(spikes_path)
spk = spk[spk.trial == trial].sort_values('t')
spk = spk[spk.flywire_id.isin(ann.index)]

active_ids = spk.flywire_id.unique()
sub = ann.loc[active_ids]
idx_of = {f: i for i, f in enumerate(active_ids)}

um = lambda s: (s.to_numpy() / 1000).round().astype(int).tolist()

neurons = {
    'x': um(sub.pos_x), 'y': um(sub.pos_y), 'z': um(sub.pos_z),
    'nt': sub.top_nt.fillna('unknown').tolist(),
    'cls': sub.super_class.fillna('unknown').tolist(),
    'type': sub.cell_type.fillna('').tolist(),
    'role': ['sugar' if f in SUGAR_GRNS else 'mn9' if f == MN9 else '' for f in active_ids],
}

# backdrop: every neuron with coordinates, subsampled
bd = ann.sample(n=min(40000, len(ann)), random_state=0)
backdrop = {'x': um(bd.pos_x), 'y': um(bd.pos_y), 'z': um(bd.pos_z)}

spikes = {
    't_ds': (spk.t.to_numpy() * 10000).round().astype(int).tolist(),  # 0.1 ms units
    'n': [idx_of[f] for f in spk.flywire_id],
}

out = {
    'meta': {
        'source': 'FlyWire FAFB v630 / Shiu et al. 2024 LIF model (NumPy reimplementation)',
        'experiment': spikes_path.stem,
        'trial': trial,
        'n_neurons_total': 127400,
        'n_active': len(active_ids),
        'n_spikes': len(spk),
        'duration_ms': 1000,
    },
    'neurons': neurons,
    'backdrop': backdrop,
    'spikes': spikes,
}

dst = HERE / 'viz_data.json'
dst.write_text(json.dumps(out, separators=(',', ':')), encoding='utf-8')
print(f'{dst}: {dst.stat().st_size/1e6:.1f} MB, {len(active_ids)} active neurons, {len(spk)} spikes')
