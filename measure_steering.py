"""Can the fly brain steer a body?

In a real fly, the brain talks to the legs and wings through descending
neurons (DNs) that run down into the nerve cord. Those are the wires a robot
should be driven by. The question this asks is whether the connectome turns a
one-sided taste into a one-sided motor command -- if it does, a two-wheeled
body can be steered by the brain with no extra logic bolted on.

Stimulate the gustatory receptors on one side only, then compare the firing of
left-side and right-side descending neurons.

Usage: python measure_steering.py [trials]
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from groups import annotations, resolve
from sim import T_RUN, load_network, run_trial

HERE = Path(__file__).parent
TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 2
RATE = 150.0

print('loading whole brain ...', flush=True)
flyids, w = load_network()
id2idx = {f: i for i, f in enumerate(flyids)}

ann = annotations().drop_duplicates('root_id').set_index('root_id')
dn = ann[ann.super_class == 'descending']
dn_left = [f for f in dn[dn.side == 'left'].index if f in id2idx]
dn_right = [f for f in dn[dn.side == 'right'].index if f in id2idx]
print(f'descending neurons in the model: {len(dn_left)} left, {len(dn_right)} right')

CONDITIONS = [
    ('sugar left',   'subclass:sugar/water@L'),
    ('sugar right',  'subclass:sugar/water@R'),
    ('bitter left',  'subclass:bitter@L'),
    ('bitter right', 'subclass:bitter@R'),
]

rows = []
for label, spec in CONDITIONS:
    ids = resolve(spec)
    idx = np.array([id2idx[f] for f in ids if f in id2idx], dtype=int)
    counts = {}
    for t in range(TRIALS):
        rng = np.random.default_rng(23 + t)
        st, si = run_trial(w, [(idx, RATE)], rng)
        for f in flyids[si]:
            counts[f] = counts.get(f, 0) + 1
    hz = lambda group: sum(counts.get(f, 0) for f in group) / TRIALS / T_RUN

    l, r = hz(dn_left), hz(dn_right)
    # +1 means everything on the right, -1 everything on the left
    li = (r - l) / (r + l) if (r + l) else 0.0
    n_active = sum(1 for f in (dn_left + dn_right) if counts.get(f, 0))
    rows.append({'condition': label, 'spec': spec, 'n_stim': len(idx),
                 'dn_left_hz': l, 'dn_right_hz': r, 'lateralisation': li,
                 'dn_active': n_active, 'total_spikes': sum(counts.values()) / TRIALS})
    print(f'{label:<14} stim {len(idx):3d}  DN left {l:7.0f} Hz  right {r:7.0f} Hz  '
          f'index {li:+.3f}  ({n_active} DNs active)', flush=True)

# which individual DNs carry the difference?
print('\nmost side-selective descending neurons (sugar left vs right):')
left_ids = np.array([id2idx[f] for f in resolve('subclass:sugar/water@L') if f in id2idx])
right_ids = np.array([id2idx[f] for f in resolve('subclass:sugar/water@R') if f in id2idx])


def dn_profile(stim_idx):
    counts = {}
    for t in range(TRIALS):
        rng = np.random.default_rng(23 + t)
        st, si = run_trial(w, [(stim_idx, RATE)], rng)
        for f in flyids[si]:
            counts[f] = counts.get(f, 0) + 1
    return {f: counts.get(f, 0) / TRIALS / T_RUN for f in dn_left + dn_right}


pl, pr = dn_profile(left_ids), dn_profile(right_ids)
diff = sorted(((pr[f] - pl[f], f) for f in pl), key=lambda x: -abs(x[0]))[:12]
print(f'{"cell type":<12} {"side":<6} {"L-stim":>8} {"R-stim":>8} {"diff":>8}')
top = []
for d, f in diff:
    row = ann.loc[f]
    ct = row.cell_type if isinstance(row.cell_type, str) else '(未命名)'
    print(f'{ct:<12} {str(row.side):<6} {pl[f]:8.0f} {pr[f]:8.0f} {d:+8.0f}')
    top.append({'flywire_id': int(f), 'type': ct, 'side': str(row.side),
                'left_stim_hz': pl[f], 'right_stim_hz': pr[f], 'diff': d})

(HERE / 'steering.json').write_text(json.dumps(
    {'trials': TRIALS, 'rate_hz': RATE, 'conditions': rows, 'top_dns': top,
     'n_dn_left': len(dn_left), 'n_dn_right': len(dn_right)},
    ensure_ascii=False), encoding='utf-8')
print('\nwrote steering.json')
