"""Does the extracted subnetwork still reproduce the whole-brain behaviour?

Whole-brain reference (30 trials / 3 trials, 100 Hz):
    sugar only     -> MN9 ~80 Hz
    sugar + bitter -> MN9   0 Hz
"""

import time

from engine import Brain, build_subnet
from groups import MN9, resolve
from sim import load_network

flyids, w = load_network()
seeds = resolve('sugar') + resolve('bitter')

for cap in (2000, 4000, 6000):
    sub_ids, sub_w = build_subnet(flyids, w, seeds, hops=2, max_neurons=cap)
    mn9_in = MN9 in set(sub_ids)
    line = f'cap={cap:5,}: {len(sub_ids):5,} neurons, {sub_w.nnz:8,} syn, MN9 present={mn9_in}'

    for label, rates in (('sugar', {'sugar': 100}),
                         ('sugar+bitter', {'sugar': 100, 'bitter': 100})):
        brain = Brain(sub_ids, sub_w)
        for grp, hz in rates.items():
            brain.set_stim([brain.id2idx[f] for f in resolve(grp) if f in brain.id2idx], hz)
        brain.run_steps(2000)                 # settle 200 ms
        t0 = time.time()
        counts = brain.run_steps(5000)        # measure 500 ms
        rt = 0.5 / (time.time() - t0)
        mn9 = counts.get(brain.id2idx.get(MN9), 0) / 0.5
        line += f'\n    {label:<13} MN9 {mn9:6.1f} Hz   (realtime x{rt:.2f})'
    print(line, flush=True)
