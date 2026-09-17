"""Resolve human-readable neuron group specs into FlyWire IDs.

Spec syntax (used by --stim / --silence and by the UDP bridge):

    sugar               built-in: the 21 right-hemisphere sugar GRNs of Shiu et al.
    mn9                 built-in: the MN9 proboscis motor neuron
    bitter              shorthand for subclass:bitter
    subclass:<name>     annotation cell_sub_class, e.g. subclass:sugar/water
    type:<name>         annotation cell_type,       e.g. type:ORN_DA1, type:R1-6
    class:<name>        annotation cell_class,      e.g. class:olfactory
    7205759...,7205...  explicit FlyWire IDs, comma separated

Append @R or @L to restrict to one side: type:R1-6@R

Run `python groups.py --list` to browse the available names.
"""

import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent

# the sugar-sensing GRNs used in Shiu et al. 2024 (right hemisphere)
SUGAR_GRNS = [
    720575940624963786, 720575940630233916, 720575940637568838,
    720575940638202345, 720575940617000768, 720575940630797113,
    720575940632889389, 720575940621754367, 720575940621502051,
    720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543,
    720575940632425919, 720575940633143833, 720575940612670570,
    720575940628853239, 720575940629176663, 720575940611875570,
]
MN9 = 720575940660219265  # proboscis motor neuron; the feeding readout

COLUMN_OF = {'type': 'cell_type', 'class': 'cell_class', 'subclass': 'cell_sub_class'}


@lru_cache(maxsize=1)
def annotations():
    """Annotations restricted to neurons that exist in the v630 model."""
    ann = pd.read_csv(HERE / 'neuron_annotations.tsv', sep='\t', low_memory=False,
                      usecols=['root_id', 'super_class', 'cell_class', 'cell_sub_class',
                               'cell_type', 'top_nt', 'side',
                               'pos_x', 'pos_y', 'pos_z'])
    comp = pd.read_csv(HERE / '2023_03_23_completeness_630_final.csv', index_col=0)
    return ann[ann.root_id.isin(set(comp.index))]


def resolve(spec):
    """Turn a spec string (or list of IDs) into a list of FlyWire IDs."""
    if isinstance(spec, (list, tuple)):
        return list(spec)

    spec = spec.strip()
    side = None
    if '@' in spec:
        spec, s = spec.rsplit('@', 1)
        side = {'R': 'right', 'L': 'left'}.get(s.upper())
        if side is None:
            raise ValueError(f'side must be @R or @L, got @{s}')

    if spec == 'sugar':
        ids = SUGAR_GRNS
    elif spec == 'mn9':
        ids = [MN9]
    elif spec == 'bitter':
        return resolve('subclass:bitter' + (f'@{side[0].upper()}' if side else ''))
    elif ':' in spec:
        kind, name = spec.split(':', 1)
        if kind not in COLUMN_OF:
            raise ValueError(f'unknown selector "{kind}:"; use type:, class:, or subclass:')
        ann = annotations()
        hit = ann[ann[COLUMN_OF[kind]] == name]
        if hit.empty:
            raise ValueError(f'no neurons matched {spec!r} '
                             f'(try: python groups.py --list {kind})')
        ids = hit.root_id.tolist()
        if side:
            ids = hit[hit.side == side].root_id.tolist()
        return ids
    else:
        try:
            ids = [int(x) for x in spec.split(',') if x.strip()]
        except ValueError:
            raise ValueError(f'could not parse spec {spec!r}; see groups.py docstring')

    if side:
        ann = annotations().set_index('root_id')
        ids = [i for i in ids if i in ann.index and ann.loc[i, 'side'] == side]
    return ids


def describe(spec):
    ids = resolve(spec)
    return f'{spec} -> {len(ids)} neurons'


if __name__ == '__main__':
    if '--list' in sys.argv:
        ann = annotations()
        kinds = sys.argv[sys.argv.index('--list') + 1:] or ['class', 'subclass']
        for kind in kinds:
            col = COLUMN_OF[kind]
            print(f'\n=== {kind}: (column {col}) ===')
            print(ann[col].value_counts().head(40).to_string())
    else:
        for spec in sys.argv[1:] or ['sugar', 'bitter', 'type:R1-6', 'type:ORN_DA1']:
            print(describe(spec))
