"""Validate the browser-side single-neuron screen against the whole brain.

The screen runs on the 4,000-neuron subnetwork. Before trusting a hit, re-run
the top candidates on all 127,400 neurons and check the effect survives.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from groups import MN9
from sim import DT, T_RUN, load_network, run_trial, silence

HERE = Path(__file__).parent
TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 3
RATE = 150.0

screen = json.loads((HERE / 'screen.json').read_text(encoding='utf-8'))
subnet = json.loads((HERE / 'subnet.json').read_text(encoding='utf-8'))

rows = screen['sugar']['rows']
picks = rows[:4] + rows[-4:]          # strongest suppressors and strongest brakes

from engine import build_subnet
from groups import resolve

print('loading whole brain ...', flush=True)
flyids, w0 = load_network()
id2idx = {f: i for i, f in enumerate(flyids)}
sugar_idx = np.array([id2idx[f] for f in resolve('sugar') if f in id2idx], dtype=int)

# subnet.json stores indices, not ids: rebuild the same subnetwork to map back
sub_ids, _ = build_subnet(flyids, w0, resolve('sugar') + resolve('bitter'),
                          hops=2, max_neurons=4000)
assert len(sub_ids) == subnet['meta']['n'], 'subnet build no longer matches subnet.json'


def mn9_rate(silence_flyid=None):
    rows_out = []
    w = w0.copy()
    if silence_flyid is not None:
        silence(w, [id2idx[silence_flyid]])
    total = 0
    for t in range(TRIALS):
        rng = np.random.default_rng(7 + t)
        st, si = run_trial(w, [(sugar_idx, RATE)], rng)
        total += int(np.sum(flyids[si] == MN9))
    return total / TRIALS / T_RUN


print(f'whole-brain baseline ({TRIALS} trials, sugar {RATE:g} Hz) ...', flush=True)
base = mn9_rate()
print(f'  MN9 {base:.1f} Hz\n', flush=True)

print(f'{"cell type":<14} {"nt":<14} {"subnet Δ":>9} {"whole Δ":>9}  {"whole MN9":>9}')
out = []
for r in picks:
    fid = int(sub_ids[r['i']])
    hz = mn9_rate(fid)
    d = hz - base
    agree = 'same sign' if (d >= 0) == (r['delta'] >= 0) else 'DIFFERS'
    print(f'{r["type"]:<14} {r["nt"]:<14} {r["delta"]:+9.1f} {d:+9.1f}  {hz:9.1f}   {agree}',
          flush=True)
    out.append({'flywire_id': fid, 'type': r['type'], 'nt': r['nt'],
                'subnet_delta': r['delta'], 'whole_delta': d, 'whole_hz': hz})

(HERE / 'validate_hits.json').write_text(
    json.dumps({'baseline': base, 'trials': TRIALS, 'hits': out}), encoding='utf-8')
print('\nwrote validate_hits.json')
