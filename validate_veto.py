"""Confirm the poison-veto lesion on the whole 127,400-neuron brain.

screen_types.js found, in the 4,000-neuron subnetwork, a set of cell types
whose removal makes the fly eat poison. The subnetwork could be missing
inhibition that lives outside it, so re-run the same lesion on everything.
"""

import json
from pathlib import Path

import numpy as np

from engine import build_subnet
from groups import MN9, resolve
from sim import T_RUN, load_network, run_trial, silence

HERE = Path(__file__).parent
TRIALS = 3
RATE = 150.0

types = json.loads((HERE / 'screen_types.json').read_text(encoding='utf-8'))
answer = types['history'][-1]['cumulative']
print(f'lesion found in the subnetwork: {answer}')

flyids, w0 = load_network()
id2idx = {f: i for i, f in enumerate(flyids)}
sub_ids, _ = build_subnet(flyids, w0, resolve('sugar') + resolve('bitter'),
                          hops=2, max_neurons=4000)

# the exact neurons the subnetwork screen silenced
lesion_ids = []
for t in answer:
    lesion_ids += [int(sub_ids[i]) for i in types['types'][t]]
print(f'that is {len(lesion_ids)} neurons: {lesion_ids}')

# the same cell types, but every member across the whole brain
full_ids = []
for t in answer:
    full_ids += [f for f in resolve(f'type:{t}') if f in id2idx]
print(f'the full cell types across the whole brain: {len(full_ids)} neurons\n')

sugar_idx = np.array([id2idx[f] for f in resolve('sugar') if f in id2idx], dtype=int)
bitter_idx = np.array([id2idx[f] for f in resolve('bitter') if f in id2idx], dtype=int)


def mn9(bitter, lesion):
    w = w0.copy()
    if lesion:
        silence(w, [id2idx[f] for f in lesion])
    stim = [(sugar_idx, RATE)]
    if bitter:
        stim.append((bitter_idx, RATE))
    total = 0
    for t in range(TRIALS):
        rng = np.random.default_rng(11 + t)
        st, si = run_trial(w, stim, rng)
        total += int(np.sum(flyids[si] == MN9))
    return total / TRIALS / T_RUN


rows = [
    ('健常・砂糖のみ',                False, None),
    ('健常・砂糖+苦味',               True,  None),
    ('病変(5個)・砂糖+苦味',          True,  lesion_ids),
    ('病変(5個)・砂糖のみ',           False, lesion_ids),
    ('病変(タイプ全体)・砂糖+苦味',    True,  full_ids),
]
out = []
print(f'{"condition":<26} {"MN9 (whole brain)":>18}')
for label, bitter, lesion in rows:
    hz = mn9(bitter, lesion)
    print(f'{label:<26} {hz:15.1f} Hz', flush=True)
    out.append({'label': label, 'bitter': bitter,
                'n_silenced': len(lesion) if lesion else 0, 'mn9_hz': hz})

(HERE / 'validate_veto.json').write_text(
    json.dumps({'answer': answer, 'lesion_ids': lesion_ids, 'trials': TRIALS,
                'rate_hz': RATE, 'results': out}, ensure_ascii=False), encoding='utf-8')
print('\nwrote validate_veto.json')
