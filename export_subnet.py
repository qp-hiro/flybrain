"""Export the feeding subnetwork in a compact form the browser can simulate.

Produces subnet.json with the network as base64-packed typed arrays:
    indptr   int32   [n+1]   CSR row starts
    indices  uint16  [nnz]   postsynaptic neuron (n < 65536)
    syn      int16   [nnz]   signed synapse count (weight = syn * 0.275 mV)

plus per-neuron metadata and the group memberships the UI needs.
"""

import base64
import json
from pathlib import Path

import numpy as np

from engine import build_subnet
from groups import MN9, annotations, resolve
from sim import W_SYN, load_network

HERE = Path(__file__).parent
CAP = 4000          # validated: MN9 78 Hz vs 80 Hz whole-brain
HOPS = 2

flyids, w = load_network()
seeds = resolve('sugar') + resolve('bitter')
sub_ids, sub_w = build_subnet(flyids, w, seeds, hops=HOPS, max_neurons=CAP)
n = len(sub_ids)
assert n < 65536, 'indices must fit in uint16'

syn = np.rint(sub_w.data / W_SYN).astype(np.int32)
clipped = int(np.sum(np.abs(syn) > 32767))
syn = np.clip(syn, -32767, 32767).astype(np.int16)

b64 = lambda a: base64.b64encode(a.tobytes()).decode('ascii')

ann = annotations().drop_duplicates('root_id').set_index('root_id')
pos, nt, ctype, cls = [], [], [], []
for f in sub_ids:
    if f in ann.index and np.isfinite(ann.loc[f, 'pos_x']):
        r = ann.loc[f]
        pos.append([int(r.pos_x / 1000), int(r.pos_y / 1000), int(r.pos_z / 1000)])
        nt.append(r.top_nt if isinstance(r.top_nt, str) else 'unknown')
        ctype.append(r.cell_type if isinstance(r.cell_type, str) else '')
        cls.append(r.super_class if isinstance(r.super_class, str) else '')
    else:
        pos.append([0, 0, 0])
        nt.append('unknown')
        ctype.append('')
        cls.append('')

idx_of = {f: i for i, f in enumerate(sub_ids)}
groups = {
    'sugar': [idx_of[f] for f in resolve('sugar') if f in idx_of],
    'bitter': [idx_of[f] for f in resolve('bitter') if f in idx_of],
    'water': [idx_of[f] for f in resolve('subclass:sugar/water') if f in idx_of],
    'mn9': [idx_of[MN9]] if MN9 in idx_of else [],
    'motor': [i for i, c in enumerate(cls) if c == 'motor'],
}

out = {
    'meta': {
        'n': n, 'nnz': int(sub_w.nnz), 'hops': HOPS, 'cap': CAP,
        'w_syn_mV': W_SYN, 'clipped': clipped,
        'source': 'FlyWire FAFB v630, 2-hop feeding subnetwork',
        'validation': {'sugar_100Hz_MN9_Hz': 78, 'sugar_bitter_MN9_Hz': 0,
                       'wholebrain_sugar_100Hz_MN9_Hz': 80},
    },
    'indptr': b64(sub_w.indptr.astype(np.int32)),
    'indices': b64(sub_w.indices.astype(np.uint16)),
    'syn': b64(syn),
    'pos': pos,
    'nt': nt,
    'type': ctype,
    'cls': cls,
    'groups': groups,
}

dst = HERE / 'subnet.json'
dst.write_text(json.dumps(out, separators=(',', ':')), encoding='utf-8')
print(f'{dst}: {dst.stat().st_size/1e6:.2f} MB  ({n:,} neurons, {sub_w.nnz:,} synapses, '
      f'{clipped} weights clipped)')
print('groups:', {k: len(v) for k, v in groups.items()})
