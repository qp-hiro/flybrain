"""Export the sensorimotor subnetwork that a robot body plugs into.

Inputs  : gustatory receptors, split left / right (the robot's two antennae)
Outputs : descending neurons, split left / right (the robot's two motors)

In a real fly the descending neurons are the only wires from the brain to the
legs and wings, so they are the honest place to tap a motor command. Nothing
is hand-wired between sensor and motor -- whatever steering exists comes out
of the connectome itself.
"""

import base64
import json
from pathlib import Path

import numpy as np

from engine import build_subnet
from groups import MN9, annotations, resolve
from sim import W_SYN, load_network

HERE = Path(__file__).parent
CAP = 5000
HOPS = 3          # sensory -> ... -> descending needs more reach than feeding

flyids, w = load_network()
id2idx = {f: i for i, f in enumerate(flyids)}

sugarL = resolve('subclass:sugar/water@L')
sugarR = resolve('subclass:sugar/water@R')
bitterL = resolve('subclass:bitter@L')
bitterR = resolve('subclass:bitter@R')
seeds = sugarL + sugarR + bitterL + bitterR
print(f'seeds: {len(sugarL)}+{len(sugarR)} sugar, {len(bitterL)}+{len(bitterR)} bitter')

sub_ids, sub_w = build_subnet(flyids, w, seeds, hops=HOPS, max_neurons=CAP)
n = len(sub_ids)
assert n < 65536
sub_set = set(int(f) for f in sub_ids)
idx_of = {int(f): i for i, f in enumerate(sub_ids)}
print(f'subnetwork: {n:,} neurons, {sub_w.nnz:,} synapses')

ann = annotations().drop_duplicates('root_id').set_index('root_id')
dn = ann[ann.super_class == 'descending']
dnL = [idx_of[int(f)] for f in dn[dn.side == 'left'].index if int(f) in sub_set]
dnR = [idx_of[int(f)] for f in dn[dn.side == 'right'].index if int(f) in sub_set]
print(f'descending neurons captured: {len(dnL)} left, {len(dnR)} right')
if len(dnL) < 5 or len(dnR) < 5:
    print('WARNING: few descending neurons in the subnetwork; raise HOPS or CAP')

syn = np.clip(np.rint(sub_w.data / W_SYN), -32767, 32767).astype(np.int16)
b64 = lambda a: base64.b64encode(a.tobytes()).decode('ascii')

pos, nt, ctype, cls, side = [], [], [], [], []
for f in sub_ids:
    f = int(f)
    if f in ann.index and np.isfinite(ann.loc[f, 'pos_x']):
        r = ann.loc[f]
        pos.append([int(r.pos_x / 1000), int(r.pos_y / 1000), int(r.pos_z / 1000)])
        nt.append(r.top_nt if isinstance(r.top_nt, str) else 'unknown')
        ctype.append(r.cell_type if isinstance(r.cell_type, str) else '')
        cls.append(r.super_class if isinstance(r.super_class, str) else '')
        side.append(r.side if isinstance(r.side, str) else '')
    else:
        pos.append([0, 0, 0]); nt.append('unknown')
        ctype.append(''); cls.append(''); side.append('')

pick = lambda ids: [idx_of[int(f)] for f in ids if int(f) in sub_set]
groups = {
    'sugarL': pick(sugarL), 'sugarR': pick(sugarR),
    'bitterL': pick(bitterL), 'bitterR': pick(bitterR),
    'dnL': dnL, 'dnR': dnR,
    'mn9': pick([MN9]),
}

out = {
    'meta': {'n': n, 'nnz': int(sub_w.nnz), 'hops': HOPS, 'w_syn_mV': W_SYN,
             'source': 'FlyWire FAFB v630, gustatory -> descending subnetwork',
             'groups': {k: len(v) for k, v in groups.items()}},
    'indptr': b64(sub_w.indptr.astype(np.int32)),
    'indices': b64(sub_w.indices.astype(np.uint16)),
    'syn': b64(syn),
    'pos': pos, 'nt': nt, 'type': ctype, 'cls': cls, 'side': side,
    'groups': groups,
}
dst = HERE / 'robotnet.json'
dst.write_text(json.dumps(out, separators=(',', ':')), encoding='utf-8')
print(f'{dst}: {dst.stat().st_size/1e6:.2f} MB')
print('groups:', {k: len(v) for k, v in groups.items()})
